"""Bedrock model fallback for course generation.

Per-minute throttling waits with exponential backoff and jitter.
A daily token quota (``ThrottlingException`` whose message contains ``per day``),
``ServiceQuotaExceeded``, ``AccessDenied``, or repeated throttles after that
backoff switch immediately to the next id in ``BEDROCK_FALLBACK_MODELS``.

The helper does not call AWS. Callers pass an ``invoke(model_id)`` function
and, after every Bedrock id fails, their existing OpenAI or Gemini path.
"""

from __future__ import annotations

import os
from typing import Callable, Optional, Sequence

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - offline tests without botocore
    class ClientError(Exception):
        def __init__(self, error_response=None, operation_name=None):
            super().__init__(str(error_response))
            self.response = error_response or {}

DEFAULT_FALLBACK_MODELS = (
    "us.anthropic.claude-sonnet-4-6,"
    "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# Back off this many throttles on one model, then switch.
_THROTTLES_BEFORE_SWITCH = 2


def fallback_model_ids(primary: str, env_value: Optional[str] = None) -> list:
    """Primary model, then ``BEDROCK_FALLBACK_MODELS``, without duplicates."""
    if env_value is None:
        env_value = os.getenv("BEDROCK_FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS)
    ordered = []
    for raw in [primary, *(part.strip() for part in (env_value or "").split(","))]:
        model = (raw or "").strip()
        if model and model not in ordered:
            ordered.append(model)
    return ordered


def error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = ((response.get("Error") or {}).get("Code") or "")
        if code:
            return str(code)
    return ""


def _message(exc: BaseException) -> str:
    return f"{error_code(exc)} {exc}".lower()


def is_daily_quota(exc: BaseException) -> bool:
    """True for a per-day token cap or a service-quota rejection."""
    message = _message(exc)
    if "servicequotaexceeded" in message:
        return True
    if "per day" in message or "tokens per day" in message:
        return True
    return False


def is_throttle(exc: BaseException) -> bool:
    message = _message(exc)
    return "throttlingexception" in message or "toomanyrequestsexception" in message


def is_access_denied(exc: BaseException) -> bool:
    return "accessdenied" in _message(exc)


def classify_bedrock_error(exc: BaseException, throttles_on_model: int) -> str:
    """``switch`` now, ``backoff`` and retry this model, or ``give_up``.

    ``throttles_on_model`` counts throttles already seen on this model,
    including ``exc`` when it is a throttle.
    """
    if is_daily_quota(exc) or is_access_denied(exc):
        return "switch"
    if is_throttle(exc):
        if throttles_on_model > _THROTTLES_BEFORE_SWITCH:
            return "switch"
        return "backoff"
    return "give_up"


def run_model_chain(
    invoke: Callable[[str], str],
    models: Sequence[str],
    *,
    max_attempts: int = 5,
    sleep: Optional[Callable[[int], None]] = None,
    is_transient: Optional[Callable[[BaseException], bool]] = None,
) -> tuple:
    """Return ``(text, model_id)`` from the first model that answers.

    Per-minute throttles sleep before another attempt on the same model.
    A daily quota, access denial, or a throttle that keeps coming after the
    backoff moves to the next model without another wait.
    """
    if sleep is None:
        sleep = lambda _index: None
    if is_transient is None:
        is_transient = lambda _exc: False
    last_error: Optional[BaseException] = None
    attempts = max(1, int(max_attempts))
    for model_id in models:
        throttles = 0
        for attempt in range(1, attempts + 1):
            try:
                text = invoke(model_id)
                if not str(text or "").strip():
                    raise ValueError(f"Bedrock returned empty text for {model_id}")
                return text, model_id
            except Exception as exc:  # noqa: BLE001 - the caller decides the next provider
                last_error = exc
                if is_throttle(exc) and not is_daily_quota(exc):
                    throttles += 1
                decision = classify_bedrock_error(exc, throttles)
                if decision == "switch":
                    break
                if decision == "backoff" and attempt < attempts:
                    sleep(attempt - 1)
                    continue
                if decision == "give_up" and attempt < attempts and is_transient(exc):
                    sleep(attempt - 1)
                    continue
                if decision == "backoff" and attempt >= attempts:
                    break
                raise
    if last_error is None:
        raise RuntimeError("BEDROCK_FALLBACK_MODELS is empty")
    raise last_error
