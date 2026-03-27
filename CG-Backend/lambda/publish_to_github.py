#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3

try:
    import jwt
except Exception:  # pragma: no cover
    jwt = None

s3_client = boto3.client("s3")
secrets_client = boto3.client("secretsmanager")


def cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
    }


def gh_request(method, path, token, payload=None):
    url = f"https://api.github.com{path}"
    body = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "aurora-thor-publisher",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url=url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        data = {}
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw}
        return e.code, data


def get_secret_json(secret_name):
    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString") or "{}"
    return json.loads(secret_string)


def generate_app_jwt(app_id, private_key_pem):
    if jwt is None:
        raise RuntimeError("PyJWT is required in Lambda runtime for GitHub App auth.")

    now = datetime.now(timezone.utc)
    payload = {
        "iat": int(now.timestamp()) - 30,
        "exp": int((now + timedelta(minutes=9)).timestamp()),
        "iss": str(app_id),
    }
    token = jwt.encode(payload, private_key_pem, algorithm="RS256")
    return token if isinstance(token, str) else token.decode("utf-8")


def get_installation_token(app_id, private_key_pem, installation_id):
    app_jwt = generate_app_jwt(app_id, private_key_pem)
    status, data = gh_request(
        "POST",
        f"/app/installations/{installation_id}/access_tokens",
        app_jwt,
        payload={},
    )
    if status not in (200, 201):
        raise RuntimeError(f"Failed to get installation token: {status} {data}")
    return data["token"]


def sanitize_repo_name(name):
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "-", name.strip())
    return sanitized.strip("-")


def get_outline_metadata(bucket, project_folder):
    prefix = f"{project_folder}/outline/"
    listed = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=20)
    yaml_key = None
    for obj in listed.get("Contents", []):
        key = obj.get("Key", "")
        if key.endswith(".yaml") or key.endswith(".yml"):
            yaml_key = key
            break
    if not yaml_key:
        return {}
    body = s3_client.get_object(Bucket=bucket, Key=yaml_key)["Body"].read().decode("utf-8")
    try:
        import yaml
        data = yaml.safe_load(body) or {}
    except Exception:
        return {}
    return data.get("course", data)


def list_latest_labs_by_module(bucket, project_folder):
    prefix = f"{project_folder}/labguide/"
    listed = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
    files = []
    for obj in listed.get("Contents", []):
        key = obj["Key"]
        if not key.lower().endswith(".md"):
            continue
        filename = key.split("/")[-1]
        match = re.search(r"lab-(\d+)-(\d+)-(\d+)", filename, re.IGNORECASE)
        if not match:
            continue
        files.append(
            {
                "key": key,
                "module": int(match.group(1)),
                "lesson": int(match.group(2)),
                "lab": int(match.group(3)),
                "last_modified": obj.get("LastModified"),
            }
        )

    files.sort(key=lambda x: (x["module"], x["lesson"], x["lab"], x["last_modified"]))
    by_module = {}
    for f in files:
        by_module.setdefault(f["module"], []).append(f)
    return by_module


def read_s3_text(bucket, key):
    return s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def ensure_repo(org, repo_name, token):
    status, _ = gh_request("GET", f"/repos/{org}/{repo_name}", token)
    if status == 200:
        # Keep org repos public for instructor/student access without team seats.
        status, data = gh_request("PATCH", f"/repos/{org}/{repo_name}", token, payload={"private": False})
        if status not in (200, 201):
            raise RuntimeError(f"Failed to set repository visibility to public: {status} {data}")
        return False

    payload = {
        "name": repo_name,
        "private": False,
        "auto_init": True,
        "description": f"Laboratorios del curso {repo_name}",
        "has_issues": True,
        "has_projects": False,
        "has_wiki": False,
    }
    status, data = gh_request("POST", f"/orgs/{org}/repos", token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Failed to create repository: {status} {data}")
    return True


def get_file_sha(org, repo, path, token, branch="main"):
    encoded_path = urllib.parse.quote(path, safe="/")
    status, data = gh_request("GET", f"/repos/{org}/{repo}/contents/{encoded_path}?ref={branch}", token)
    if status == 200 and isinstance(data, dict):
        return data.get("sha")
    return None


def put_file(org, repo, path, content_bytes, token, message, branch="main"):
    sha = get_file_sha(org, repo, path, token, branch=branch)
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    encoded_path = urllib.parse.quote(path, safe="/")
    status, data = gh_request("PUT", f"/repos/{org}/{repo}/contents/{encoded_path}", token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Failed to put file {path}: {status} {data}")


def configure_repo_settings(org, repo, token):
    payload = {
        "allow_squash_merge": True,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "delete_branch_on_merge": True,
    }
    status, data = gh_request("PATCH", f"/repos/{org}/{repo}", token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Failed to configure repo settings: {status} {data}")


def create_branch_if_missing(org, repo, token, branch_name, source_branch="main"):
    status, data = gh_request("GET", f"/repos/{org}/{repo}/git/ref/heads/{source_branch}", token)
    if status != 200:
        raise RuntimeError(f"Cannot read source branch {source_branch}: {status} {data}")
    sha = data["object"]["sha"]

    status, _ = gh_request("GET", f"/repos/{org}/{repo}/git/ref/heads/{branch_name}", token)
    if status == 200:
        return
    payload = {"ref": f"refs/heads/{branch_name}", "sha": sha}
    status, data = gh_request("POST", f"/repos/{org}/{repo}/git/refs", token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Failed to create branch {branch_name}: {status} {data}")


def try_configure_branch_protection_main(owner, repo, token):
    """
    Best-effort: GitHub Free on personal accounts often rejects advanced branch protection.
    Returns (ok: bool, detail: str|None).
    """
    payload = {
        "required_status_checks": None,
        "enforce_admins": False,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "required_approving_review_count": 1,
        },
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    status, data = gh_request("PUT", f"/repos/{owner}/{repo}/branches/main/protection", token, payload=payload)
    if status in (200, 201):
        return True, None
    return False, f"main branch protection: {status} {data}"


def try_configure_branch_protection_changes(owner, repo, token):
    """Best-effort branch protection for changes_course. Returns (ok, detail)."""
    payload = {
        "required_status_checks": None,
        "enforce_admins": False,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    status, data = gh_request(
        "PUT", f"/repos/{owner}/{repo}/branches/changes_course/protection", token, payload=payload
    )
    if status in (200, 201):
        return True, None
    return False, f"changes_course branch protection: {status} {data}"


def invite_collaborator(org, repo, token, github_user):
    """
    Invite instructor as collaborator (push). Does not raise.
    Organization-owned repos may return 422 seat_limit; user-owned repos typically avoid org seat billing.
    Returns (success: bool, detail: str|None).
    """
    if not github_user:
        return True, None
    payload = {"permission": "push"}
    status, data = gh_request(
        "PUT",
        f"/repos/{org}/{repo}/collaborators/{urllib.parse.quote(github_user)}",
        token,
        payload=payload,
    )
    if status in (200, 201, 204):
        return True, None
    # Common: 422 seat_limit — billing must add seats; repo is still usable
    msg = f"{status} {data}"
    return False, msg


def clean_lab_title(raw_title):
    title = (raw_title or "").strip()
    title = re.sub(r"^lab\s+\d{2}-\d{2}-\d{2}\s*:\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^(laboratorio|laboratorio:)\s*:\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^práctica\s*\d+\s*[:.-]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^practica\s*\d+\s*[:.-]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^\d+\s*[:.-]\s*", "", title)
    return title.strip() or (raw_title or "").strip()


def parse_lab_summary(markdown_text, module_number, lesson_number, lab_number):
    lines = [ln.strip() for ln in markdown_text.splitlines() if ln.strip()]
    title = f"Laboratorio {module_number}.{lesson_number}.{lab_number}"
    description = None
    duration = None
    for line in lines:
        if line.startswith("#"):
            title = re.sub(r"^#+\s*", "", line).strip() or title
            break
    title = clean_lab_title(title)
    for line in lines:
        normalized = line.lstrip("-* ").replace("**", "").strip()
        low = normalized.lower()
        if description is None and low.startswith(("descripción", "descripcion")):
            description = re.sub(r"^(descripción|descripcion)\s*:\s*", "", normalized, flags=re.IGNORECASE).strip()
        if duration is None and (low.startswith("duración") or low.startswith("duracion")):
            duration = re.sub(r"^(duración|duracion)\s*(estimada)?\s*:\s*", "", normalized, flags=re.IGNORECASE).strip()
        if description and duration:
            break
    return {"title": title, "description": description, "duration": duration}


def markdown_anchor(text):
    slug = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "laboratorio"


def normalize_lab_markdown(markdown_text):
    lines = markdown_text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            raw_title = re.sub(r"^#+\s*", "", stripped).strip()
            cleaned_title = clean_lab_title(raw_title)
            lines[idx] = f"# {cleaned_title}"
            break
    return "\n".join(lines).strip()


def build_root_readme(project_folder, outline, module_index):
    title = outline.get("title") or project_folder
    description = outline.get("description") or "Repositorio de laboratorios generado por THOR."
    parts = [
        f"# {title}\n\n"
        f"{description}\n\n"
        "## Estructura\n\n"
        "- `CapituloXX/README.md`: guía de laboratorio por capítulo.\n\n",
        "## Lista de laboratorios\n\n",
    ]
    for module_number in sorted(module_index.keys()):
        parts.append(f"### Capítulo {module_number}\n\n")
        for lab in module_index[module_number]:
            chapter_path = f"Capitulo{module_number:02d}/README.md"
            anchor = markdown_anchor(lab["title"])
            parts.append(f"- [{lab['title']}]({chapter_path}#{anchor})\n")
            if lab.get("description"):
                parts.append(f"  - Descripción: {lab['description']}\n")
            if lab.get("duration"):
                parts.append(f"  - Duración estimada: {lab['duration']}\n")
        parts.append("\n")
    parts.append(
        "## Flujo de colaboración\n\n"
        "- Trabajar en `changes_course`.\n"
        "- Crear Pull Request hacia `main`.\n"
        "- Merge por `Squash and merge`.\n"
    )
    return "".join(parts)


def parse_event_body(event):
    """API Gateway may base64-encode the body when BinaryMediaTypes includes */* (see template Globals)."""
    if not isinstance(event, dict):
        return {}
    if isinstance(event.get("body"), dict):
        return event["body"]
    if "body" not in event:
        return event if isinstance(event, dict) and "project_folder" in event else {}
    raw = event.get("body")
    if raw is None or raw == "":
        raw = "{}"
    if event.get("isBase64Encoded", False) and raw and raw != "{}":
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def lambda_handler(event, context):
    try:
        body = parse_event_body(event)
        project_folder = (body.get("project_folder") or "").strip()
        if not project_folder:
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "project_folder is required"})}

        bucket = os.getenv("COURSE_BUCKET", "crewai-course-artifacts")
        secret_name = os.getenv("GITHUB_APP_SECRET_NAME", "netec/github-app/aurora-publisher")
        lucy_owner = os.getenv("CODE_OWNER_USERNAME", "NetecGK").lstrip("@")

        secret = get_secret_json(secret_name)
        app_id = secret.get("app_id")
        installation_id = secret.get("installation_id")
        if installation_id is not None:
            installation_id = str(installation_id).strip()
        if not installation_id:
            installation_id = (os.getenv("GITHUB_INSTALLATION_ID") or "").strip()
        private_key = secret.get("private_key")
        org = secret.get("org") or os.getenv("GITHUB_ORG", "Netec-Mx")
        if not app_id or not private_key:
            raise RuntimeError("GitHub App secret is incomplete (app_id, private_key).")
        if not installation_id:
            raise RuntimeError(
                "GitHub App installation_id is missing: install the App on the GitHub org or user "
                "that will own the repositories, add installation_id to Secrets Manager JSON, "
                "or set GITHUB_INSTALLATION_ID on the Lambda."
            )

        token = get_installation_token(app_id, private_key, installation_id)
        repo_name = sanitize_repo_name(project_folder)
        repo_created = ensure_repo(org, repo_name, token)

        codeowners = f"* @{lucy_owner}\n"
        put_file(org, repo_name, ".github/CODEOWNERS", codeowners.encode("utf-8"), token, "chore: configure code owners")

        module_labs = list_latest_labs_by_module(bucket, project_folder)
        module_index = {}
        for module_number, labs in module_labs.items():
            chapter_dir = f"Capitulo{module_number:02d}"
            parts = []
            module_index[module_number] = []
            for lab in labs:
                content = normalize_lab_markdown(read_s3_text(bucket, lab["key"]))
                parts.append(content)
                module_index[module_number].append(
                    parse_lab_summary(
                        content,
                        module_number=lab["module"],
                        lesson_number=lab["lesson"],
                        lab_number=lab["lab"],
                    )
                )
            chapter_md = "\n\n---\n\n".join(parts) + "\n"
            put_file(
                org,
                repo_name,
                f"{chapter_dir}/README.md",
                chapter_md.encode("utf-8"),
                token,
                f"docs: sync chapter {module_number:02d} lab guide",
            )

        outline = get_outline_metadata(bucket, project_folder)
        readme_text = build_root_readme(project_folder, outline, module_index)
        put_file(org, repo_name, "README.md", readme_text.encode("utf-8"), token, "docs: update repository root index")

        configure_repo_settings(org, repo_name, token)
        create_branch_if_missing(org, repo_name, token, "changes_course", source_branch="main")
        bp_main_ok, bp_main_detail = try_configure_branch_protection_main(org, repo_name, token)
        bp_changes_ok, bp_changes_detail = try_configure_branch_protection_changes(
            org, repo_name, token
        )
        if not bp_main_ok:
            print(f"WARN branch protection main: {bp_main_detail}")
        if not bp_changes_ok:
            print(f"WARN branch protection changes_course: {bp_changes_detail}")

        instructor_user = str(body.get("instructor_github_user") or "").strip().lstrip("@")
        invite_ok, invite_detail = invite_collaborator(org, repo_name, token, instructor_user)

        response_body = {
            "message": "Repositorio publicado/actualizado en GitHub",
            "repository_owner": org,
            "repository_owner_type": "organization",
            "organization": org,
            "repository": repo_name,
            "repository_url": f"https://github.com/{org}/{repo_name}",
            "repository_visibility": "public",
            "created": repo_created,
            "branch_protection_main_ok": bp_main_ok,
            "branch_protection_main_detail": bp_main_detail,
            "branch_protection_changes_ok": bp_changes_ok,
            "branch_protection_changes_detail": bp_changes_detail,
            "instructor_github_user": instructor_user or None,
            "chapters_synced": len(module_labs),
            "collaborator_invite_ok": invite_ok,
            "collaborator_invite_detail": invite_detail,
        }
        return {"statusCode": 200, "headers": cors_headers(), "body": json.dumps(response_body)}
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}
