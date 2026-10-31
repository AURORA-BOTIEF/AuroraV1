#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cross-execution provider locks for CourseGenerator and PPT state machines.

Three independent mutexes: bedrock, google, openai. A job may start only when it
can take every provider it needs in one transaction. Waiters are FIFO by
enqueued_at; a later job with no overlap can still proceed.
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("PROVIDER_LOCKS_TABLE", "ProviderExecutionLocks")
TTL_SECONDS = 24 * 60 * 60
WAIT_SECONDS_MIN = 45
WAIT_SECONDS_MAX = 75
KNOWN_PROVIDERS = ("bedrock", "google", "openai")
LOCK_SK = "lock"
PENDING_PK = "PENDING"

_dynamodb_resource = None
_dynamodb_client = None
_sf_client = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ttl_epoch() -> int:
    return int(time.time()) + TTL_SECONDS


def _table():
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource.Table(TABLE_NAME)


def _ddb_client():
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


def _stepfunctions():
    global _sf_client
    if _sf_client is None:
        _sf_client = boto3.client("stepfunctions")
    return _sf_client


def normalize_text_provider(model_provider: Optional[str]) -> str:
    p = (model_provider or "bedrock").strip().lower()
    if p in ("google", "gemini"):
        return "google"
    if p == "openai":
        return "openai"
    return "bedrock"


def image_provider_for(image_model: Optional[str]) -> str:
    if "gpt-image" in (image_model or "").lower():
        return "openai"
    return "google"


def uses_image_provider(
    job_kind: str,
    content_type: Optional[str] = None,
    resume_from: Optional[str] = None,
) -> bool:
    if (job_kind or "course").lower() == "ppt":
        return False
    if (resume_from or "") == "post_theory":
        return False
    if (content_type or "both") == "labs":
        return False
    return True


def providers_for(
    *,
    job_kind: str = "course",
    model_provider: Optional[str] = None,
    image_model: Optional[str] = None,
    content_type: Optional[str] = None,
    resume_from: Optional[str] = None,
) -> List[str]:
    providers: Set[str] = {normalize_text_provider(model_provider)}
    if uses_image_provider(job_kind, content_type, resume_from):
        providers.add(image_provider_for(image_model))
    return sorted(providers)


def simulate_assignments(
    pending_jobs: Sequence[Dict[str, Any]],
    held_by: Dict[str, str],
) -> Dict[str, str]:
    """
    Walk waiters oldest-first. A job is assigned iff every provider it needs is free
    (not in held_by and not already given to an older waiter). Currently held
    providers stay with their holder.
    """
    assigned = dict(held_by)
    for job in pending_jobs:
        arn = job["execution_arn"]
        needed = list(job["providers"])
        if all(assigned.get(p) == arn for p in needed):
            continue
        if any(p in assigned for p in needed):
            continue
        for p in needed:
            assigned[p] = arn
    return assigned


def wait_seconds() -> int:
    return random.randint(WAIT_SECONDS_MIN, WAIT_SECONDS_MAX)


def _lock_pk(provider: str) -> str:
    return f"LOCK#{provider}"


def _exec_pk(execution_arn: str) -> str:
    return f"EXEC#{execution_arn}"


def _unwrap_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Support SM payload, EventBridge, and nested execution_input."""
    if not isinstance(event, dict):
        return {}
    if event.get("source") == "aws.states" or event.get("detail-type") == "Step Functions Execution Status Change":
        detail = event.get("detail") or {}
        return {
            "action": "release",
            "execution_arn": detail.get("executionArn") or event.get("execution_arn"),
            "status": detail.get("status"),
        }
    inner = event.get("execution_input")
    if isinstance(inner, dict):
        merged = dict(inner)
        for key in (
            "action",
            "job_kind",
            "execution_arn",
            "model_provider",
            "image_model",
            "content_type",
            "resume_from",
            "project_folder",
        ):
            if event.get(key) not in (None, ""):
                merged[key] = event[key]
        return merged
    return event


def _is_execution_running(execution_arn: str) -> bool:
    if not execution_arn:
        return False
    try:
        resp = _stepfunctions().describe_execution(executionArn=execution_arn)
        status = (resp.get("status") or "").upper()
        running = status == "RUNNING"
        print(f"ProviderLock: describe {execution_arn} status={status} running={running}")
        return running
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        print(f"ProviderLock: describe failed for {execution_arn}: {code} {e}")
        # Only steal when the execution is gone. IAM/throttling errors must not
        # look like a dead holder or we would yank locks from a live job.
        if code in ("ExecutionDoesNotExist", "InvalidArn"):
            return False
        return True
    except Exception as e:
        print(f"ProviderLock: describe unexpected error for {execution_arn}: {e}")
        return True


def _get_lock_item(provider: str) -> Optional[Dict[str, Any]]:
    resp = _table().get_item(Key={"pk": _lock_pk(provider), "sk": LOCK_SK})
    return resp.get("Item")


def _load_held_by() -> Dict[str, str]:
    held: Dict[str, str] = {}
    for provider in KNOWN_PROVIDERS:
        item = _get_lock_item(provider)
        if not item:
            continue
        holder = item.get("holder_arn")
        if holder:
            held[provider] = holder
    return held


def _steal_stale_locks(except_arn: Optional[str] = None) -> List[str]:
    stolen: List[str] = []
    held = _load_held_by()
    checked: Set[str] = set()
    for provider, holder in list(held.items()):
        if holder == except_arn:
            continue
        if holder in checked:
            continue
        checked.add(holder)
        if _is_execution_running(holder):
            continue
        # Steal every lock this dead holder owns.
        for p, h in list(_load_held_by().items()):
            if h != holder:
                continue
            try:
                _table().delete_item(Key={"pk": _lock_pk(p), "sk": LOCK_SK})
                stolen.append(p)
                print(f"ProviderLock: stole stale lock {p} from {holder}")
            except ClientError as e:
                print(f"ProviderLock: steal delete failed for {p}: {e}")
    return stolen


def _list_pending_jobs() -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {
        "KeyConditionExpression": "pk = :pk",
        "ExpressionAttributeValues": {":pk": PENDING_PK},
        "ScanIndexForward": True,
    }
    while True:
        resp = _table().query(**kwargs)
        for item in resp.get("Items") or []:
            arn = item.get("execution_arn")
            providers = item.get("providers") or []
            if isinstance(providers, (list, tuple)):
                providers = [str(p) for p in providers]
            if arn:
                jobs.append(
                    {
                        "execution_arn": arn,
                        "providers": providers,
                        "enqueued_at": item.get("enqueued_at") or item.get("sk"),
                        "sk": item.get("sk"),
                    }
                )
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    jobs.sort(key=lambda j: (j.get("enqueued_at") or "", j["execution_arn"]))
    return jobs


def _get_pointer(execution_arn: str) -> Optional[Dict[str, Any]]:
    resp = _table().get_item(Key={"pk": _exec_pk(execution_arn), "sk": "pending"})
    return resp.get("Item")


def _ensure_pending(
    execution_arn: str,
    providers: Sequence[str],
    job_kind: str,
    project_folder: str,
) -> str:
    pointer = _get_pointer(execution_arn)
    if pointer and pointer.get("pending_sk"):
        enqueued_at = pointer.get("enqueued_at") or _now_iso()
        print(f"ProviderLock: pending already exists for {execution_arn} enqueued_at={enqueued_at}")
        return str(enqueued_at)

    enqueued_at = _now_iso()
    pending_sk = f"{enqueued_at}#{execution_arn}"
    ttl = _ttl_epoch()
    _table().put_item(
        Item={
            "pk": PENDING_PK,
            "sk": pending_sk,
            "execution_arn": execution_arn,
            "enqueued_at": enqueued_at,
            "providers": list(providers),
            "job_kind": job_kind,
            "project_folder": project_folder or "",
            "ttl": ttl,
        }
    )
    _table().put_item(
        Item={
            "pk": _exec_pk(execution_arn),
            "sk": "pending",
            "pending_sk": pending_sk,
            "enqueued_at": enqueued_at,
            "providers": list(providers),
            "job_kind": job_kind,
            "ttl": ttl,
        }
    )
    print(f"ProviderLock: enqueued {execution_arn} providers={list(providers)} enqueued_at={enqueued_at}")
    return enqueued_at


def _already_holds(execution_arn: str, providers: Sequence[str], held_by: Dict[str, str]) -> bool:
    return bool(providers) and all(held_by.get(p) == execution_arn for p in providers)


def _transact_acquire(
    execution_arn: str,
    providers: Sequence[str],
    job_kind: str,
    project_folder: str,
    pending_sk: Optional[str],
) -> bool:
    now = _now_iso()
    ttl = _ttl_epoch()
    transact_items: List[Dict[str, Any]] = []
    for provider in providers:
        transact_items.append(
            {
                "Put": {
                    "TableName": TABLE_NAME,
                    "Item": {
                        "pk": {"S": _lock_pk(provider)},
                        "sk": {"S": LOCK_SK},
                        "holder_arn": {"S": execution_arn},
                        "job_kind": {"S": job_kind},
                        "project_folder": {"S": project_folder or ""},
                        "providers": {"L": [{"S": p} for p in providers]},
                        "acquired_at": {"S": now},
                        "ttl": {"N": str(ttl)},
                    },
                    "ConditionExpression": "attribute_not_exists(pk) OR holder_arn = :me",
                    "ExpressionAttributeValues": {":me": {"S": execution_arn}},
                }
            }
        )
    if pending_sk:
        transact_items.append(
            {
                "Delete": {
                    "TableName": TABLE_NAME,
                    "Key": {"pk": {"S": PENDING_PK}, "sk": {"S": pending_sk}},
                }
            }
        )
        transact_items.append(
            {
                "Delete": {
                    "TableName": TABLE_NAME,
                    "Key": {"pk": {"S": _exec_pk(execution_arn)}, "sk": {"S": "pending"}},
                }
            }
        )
    try:
        _ddb_client().transact_write_items(TransactItems=transact_items)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        print(f"ProviderLock: transact acquire failed for {execution_arn}: {code} {e}")
        return False


def acquire(
    *,
    execution_arn: str,
    job_kind: str = "course",
    model_provider: Optional[str] = None,
    image_model: Optional[str] = None,
    content_type: Optional[str] = None,
    resume_from: Optional[str] = None,
    project_folder: str = "",
) -> Dict[str, Any]:
    providers = providers_for(
        job_kind=job_kind,
        model_provider=model_provider,
        image_model=image_model,
        content_type=content_type,
        resume_from=resume_from,
    )
    print(
        f"ProviderLock: acquire start arn={execution_arn} kind={job_kind} "
        f"providers={providers} project={project_folder} "
        f"text={model_provider} image={image_model} content_type={content_type} resume={resume_from}"
    )
    if not execution_arn:
        return {
            "acquired": False,
            "wait_seconds": wait_seconds(),
            "providers": providers,
            "reason": "missing_execution_arn",
        }

    _steal_stale_locks(except_arn=execution_arn)
    held_by = _load_held_by()
    if _already_holds(execution_arn, providers, held_by):
        pointer = _get_pointer(execution_arn)
        if pointer and pointer.get("pending_sk"):
            _delete_pending(execution_arn, pointer.get("pending_sk"))
        print(f"ProviderLock: acquired (already held) {execution_arn} providers={providers}")
        return {
            "acquired": True,
            "wait_seconds": wait_seconds(),
            "providers": providers,
            "reason": "already_held",
        }

    enqueued_at = _ensure_pending(execution_arn, providers, job_kind, project_folder)
    pending_jobs = _list_pending_jobs()
    held_by = _load_held_by()
    assigned = simulate_assignments(pending_jobs, held_by)
    winner = all(assigned.get(p) == execution_arn for p in providers)
    if not winner:
        reason = "providers_busy"
        print(
            f"ProviderLock: waiting {execution_arn} providers={providers} "
            f"held_by={held_by} assigned={assigned}"
        )
        return {
            "acquired": False,
            "wait_seconds": wait_seconds(),
            "providers": providers,
            "reason": reason,
            "held_by": held_by,
            "enqueued_at": enqueued_at,
        }

    pointer = _get_pointer(execution_arn)
    pending_sk = (pointer or {}).get("pending_sk")
    ok = _transact_acquire(execution_arn, providers, job_kind, project_folder, pending_sk)
    if not ok:
        print(f"ProviderLock: waiting {execution_arn} (transaction lost race)")
        return {
            "acquired": False,
            "wait_seconds": wait_seconds(),
            "providers": providers,
            "reason": "race_lost",
            "enqueued_at": enqueued_at,
        }
    print(f"ProviderLock: acquired {execution_arn} providers={providers} project={project_folder}")
    return {
        "acquired": True,
        "wait_seconds": wait_seconds(),
        "providers": providers,
        "reason": "acquired",
    }


def _delete_pending(execution_arn: str, pending_sk: Optional[str] = None) -> None:
    if not pending_sk:
        pointer = _get_pointer(execution_arn)
        pending_sk = (pointer or {}).get("pending_sk")
    if pending_sk:
        try:
            _table().delete_item(Key={"pk": PENDING_PK, "sk": pending_sk})
        except ClientError as e:
            print(f"ProviderLock: delete pending row failed: {e}")
    try:
        _table().delete_item(Key={"pk": _exec_pk(execution_arn), "sk": "pending"})
    except ClientError as e:
        print(f"ProviderLock: delete pending pointer failed: {e}")
    # Fallback: scan PENDING partition for this arn (pointer missing / partial write)
    if not pending_sk:
        for job in _list_pending_jobs():
            if job["execution_arn"] == execution_arn and job.get("sk"):
                try:
                    _table().delete_item(Key={"pk": PENDING_PK, "sk": job["sk"]})
                except ClientError:
                    pass


def _locks_held_by(execution_arn: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {
        "IndexName": "holder_arn-index",
        "KeyConditionExpression": "holder_arn = :arn",
        "ExpressionAttributeValues": {":arn": execution_arn},
    }
    while True:
        resp = _table().query(**kwargs)
        items.extend(resp.get("Items") or [])
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def release(execution_arn: str) -> Dict[str, Any]:
    print(f"ProviderLock: release {execution_arn}")
    released: List[str] = []
    if not execution_arn:
        return {"released": released, "reason": "missing_execution_arn"}
    for item in _locks_held_by(execution_arn):
        pk = item.get("pk")
        sk = item.get("sk") or LOCK_SK
        if not pk:
            continue
        try:
            _table().delete_item(Key={"pk": pk, "sk": sk})
            provider = str(pk).split("#", 1)[-1]
            released.append(provider)
            print(f"ProviderLock: released {provider} from {execution_arn}")
        except ClientError as e:
            print(f"ProviderLock: release delete lock {pk} failed: {e}")
    # Also drop locks by known keys in case GSI is eventually consistent
    for provider in KNOWN_PROVIDERS:
        item = _get_lock_item(provider)
        if item and item.get("holder_arn") == execution_arn:
            try:
                _table().delete_item(Key={"pk": _lock_pk(provider), "sk": LOCK_SK})
                if provider not in released:
                    released.append(provider)
            except ClientError:
                pass
    _delete_pending(execution_arn)
    print(f"ProviderLock: release done {execution_arn} providers={released}")
    return {"released": released, "reason": "released"}


def get_queue_status(execution_arn: str) -> str:
    if not execution_arn:
        return "unknown"
    held = _load_held_by()
    if any(h == execution_arn for h in held.values()):
        return "running"
    pointer = _get_pointer(execution_arn)
    if pointer:
        return "waiting"
    for job in _list_pending_jobs():
        if job["execution_arn"] == execution_arn:
            return "waiting"
    return "unknown"


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    print(f"ProviderLock: event={json.dumps(event, default=str)[:4000]}")
    payload = _unwrap_event(event or {})
    action = (payload.get("action") or "acquire").lower()
    execution_arn = payload.get("execution_arn") or ""

    if action == "release":
        result = release(execution_arn)
        result["acquired"] = False
        result["wait_seconds"] = wait_seconds()
        result["providers"] = []
        return result

    result = acquire(
        execution_arn=execution_arn,
        job_kind=payload.get("job_kind") or "course",
        model_provider=payload.get("model_provider"),
        image_model=payload.get("image_model"),
        content_type=payload.get("content_type"),
        resume_from=payload.get("resume_from"),
        project_folder=payload.get("project_folder") or "",
    )
    return result
