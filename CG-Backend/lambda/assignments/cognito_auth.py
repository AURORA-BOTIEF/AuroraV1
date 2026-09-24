"""Decode Cognito ID token payload from API Gateway (no signature verification; same pattern as starter_api)."""
import base64
import json


def decode_jwt_payload(token: str) -> dict | None:
    if not token or not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    payload += "=" * (4 - len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None


def get_id_token_payload_from_event(event: dict) -> dict | None:
    headers = event.get("headers") or {}
    low = {k.lower(): v for k, v in headers.items()}
    auth = low.get("authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    return decode_jwt_payload(token)


def cognito_user_id_from_payload(payload: dict | None) -> str | None:
    """Prefer email; fallback to sub (required for stable partition key)."""
    if not payload:
        return None
    email = (payload.get("email") or "").strip()
    if email:
        return email
    sub = (payload.get("sub") or "").strip()
    return sub or None
