import json
import os

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

        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={"userId": user_id})
        item = response.get("Item", {})

        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps(
                {
                    "userId": user_id,
                    "githubUserId": item.get("githubUserId"),
                    "updatedAt": item.get("updatedAt"),
                }
            ),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }
