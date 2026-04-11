import base64
import json
import os
from datetime import datetime, timezone

import boto3

from cognito_auth import cognito_user_id_from_payload, get_id_token_payload_from_event

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("USER_INSTRUCTOR_GITHUB_TABLE", "UserInstructorGithub")


def cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,x-amz-content-sha256",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
    }


def parse_event_body(event):
    if not isinstance(event, dict):
        return {}
    if isinstance(event.get("body"), dict):
        return event["body"]
    raw = event.get("body")
    if raw is None or raw == "":
        raw = "{}"
    if event.get("isBase64Encoded", False) and raw and raw != "{}":
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def lambda_handler(event, context):
    try:
        payload = get_id_token_payload_from_event(event)
        user_id = cognito_user_id_from_payload(payload)
        if not user_id:
            return {
                "statusCode": 401,
                "headers": cors_headers(),
                "body": json.dumps({"error": "Authorization Bearer (Cognito id token) required"}),
            }

        body = parse_event_body(event)
        github_user_id = (body.get("githubUserId") or "").strip().lstrip("@")
        if not github_user_id:
            return {
                "statusCode": 400,
                "headers": cors_headers(),
                "body": json.dumps({"error": "githubUserId is required"}),
            }

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "userId": user_id,
            "githubUserId": github_user_id,
            "updatedAt": now,
        }

        table = dynamodb.Table(TABLE_NAME)
        table.put_item(Item=item)

        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps({"message": "saved", **item}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }
