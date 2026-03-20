import json
import os
from datetime import datetime, timezone
import boto3

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("INSTRUCTOR_GITHUB_TABLE", "CourseInstructorGithub")


def cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
    }


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        project_folder = (body.get("courseId") or "").strip()
        github_user_id = (body.get("githubUserId") or "").strip().lstrip("@")
        updated_by = (body.get("updatedBy") or "system").strip()

        if not project_folder:
            return {
                "statusCode": 400,
                "headers": cors_headers(),
                "body": json.dumps({"error": "courseId is required"}),
            }

        if not github_user_id:
            return {
                "statusCode": 400,
                "headers": cors_headers(),
                "body": json.dumps({"error": "githubUserId is required"}),
            }

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "courseId": project_folder,
            "githubUserId": github_user_id,
            "updatedAt": now,
            "updatedBy": updated_by,
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
