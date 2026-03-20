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
dynamodb = boto3.resource("dynamodb")


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


def list_images(bucket, project_folder):
    prefix = f"{project_folder}/images/"
    listed = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
    keys = []
    for obj in listed.get("Contents", []):
        key = obj["Key"]
        if key.endswith("/"):
            continue
        keys.append(key)
    return keys


def ensure_repo(org, repo_name, token):
    status, _ = gh_request("GET", f"/repos/{org}/{repo_name}", token)
    if status == 200:
        return False

    payload = {
        "name": repo_name,
        "private": True,
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


def configure_branch_protection_main(org, repo, token):
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
    status, data = gh_request("PUT", f"/repos/{org}/{repo}/branches/main/protection", token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Failed to configure main branch protection: {status} {data}")


def configure_branch_protection_changes(org, repo, token):
    payload = {
        "required_status_checks": None,
        "enforce_admins": False,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    status, data = gh_request("PUT", f"/repos/{org}/{repo}/branches/changes_course/protection", token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Failed to configure changes_course branch protection: {status} {data}")


def invite_collaborator(org, repo, token, github_user):
    if not github_user:
        return
    payload = {"permission": "push"}
    status, data = gh_request(
        "PUT",
        f"/repos/{org}/{repo}/collaborators/{urllib.parse.quote(github_user)}",
        token,
        payload=payload,
    )
    if status not in (200, 201, 204):
        raise RuntimeError(f"Failed to invite collaborator @{github_user}: {status} {data}")


def build_root_readme(project_folder, outline):
    title = outline.get("title") or project_folder
    description = outline.get("description") or "Repositorio de laboratorios generado por THOR."
    return (
        f"# {title}\n\n"
        f"{description}\n\n"
        "## Estructura\n\n"
        "- `images/`: imágenes compartidas de laboratorios.\n"
        "- `CapituloXX/README.md`: laboratorio por capítulo.\n\n"
        "## Flujo de colaboración\n\n"
        "- Trabajar en `changes_course`.\n"
        "- Crear Pull Request hacia `main`.\n"
        "- Merge por `Squash and merge`.\n"
    )


def get_instructor_github_user(project_folder, body):
    if body.get("instructor_github_user"):
        return str(body.get("instructor_github_user")).strip().lstrip("@")
    table_name = os.getenv("INSTRUCTOR_GITHUB_TABLE", "CourseInstructorGithub")
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={"courseId": project_folder})
    item = response.get("Item")
    if not item:
        return ""
    return str(item.get("githubUserId", "")).strip().lstrip("@")


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
                "GitHub App installation_id is missing: install the App on the org (Netec-Mx), "
                "add installation_id to Secrets Manager JSON, or set GITHUB_INSTALLATION_ID on the Lambda."
            )

        token = get_installation_token(app_id, private_key, installation_id)
        repo_name = sanitize_repo_name(project_folder)
        repo_created = ensure_repo(org, repo_name, token)

        outline = get_outline_metadata(bucket, project_folder)
        readme_text = build_root_readme(project_folder, outline)
        put_file(org, repo_name, "README.md", readme_text.encode("utf-8"), token, "chore: initialize course labs repository")

        codeowners = f"* @{lucy_owner}\n"
        put_file(org, repo_name, ".github/CODEOWNERS", codeowners.encode("utf-8"), token, "chore: configure code owners")

        # Ensure image directory exists in git.
        put_file(org, repo_name, "images/.gitkeep", b"", token, "chore: ensure images directory")
        for image_key in list_images(bucket, project_folder):
            filename = image_key.split("/")[-1]
            image_bytes = s3_client.get_object(Bucket=bucket, Key=image_key)["Body"].read()
            put_file(org, repo_name, f"images/{filename}", image_bytes, token, f"chore: sync image {filename}")

        module_labs = list_latest_labs_by_module(bucket, project_folder)
        for module_number, labs in module_labs.items():
            chapter_dir = f"Capitulo{module_number:02d}"
            parts = []
            for lab in labs:
                content = read_s3_text(bucket, lab["key"]).strip()
                parts.append(content)
            chapter_md = "\n\n---\n\n".join(parts) + "\n"
            put_file(
                org,
                repo_name,
                f"{chapter_dir}/README.md",
                chapter_md.encode("utf-8"),
                token,
                f"docs: sync chapter {module_number:02d} lab guide",
            )

        configure_repo_settings(org, repo_name, token)
        create_branch_if_missing(org, repo_name, token, "changes_course", source_branch="main")
        configure_branch_protection_main(org, repo_name, token)
        configure_branch_protection_changes(org, repo_name, token)

        instructor_user = get_instructor_github_user(project_folder, body)
        invite_collaborator(org, repo_name, token, instructor_user)

        response_body = {
            "message": "Repositorio publicado/actualizado en GitHub",
            "organization": org,
            "repository": repo_name,
            "repository_url": f"https://github.com/{org}/{repo_name}",
            "created": repo_created,
            "instructor_github_user": instructor_user or None,
            "chapters_synced": len(module_labs),
        }
        return {"statusCode": 200, "headers": cors_headers(), "body": json.dumps(response_body)}
    except Exception as e:
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": str(e)})}
