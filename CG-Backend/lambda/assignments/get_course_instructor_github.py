import json
import os
import urllib.parse
import boto3
from botocore.exceptions import ClientError

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
        path_params = event.get("pathParameters") or {}
        raw_project_folder = path_params.get("projectFolder")
        project_folder = urllib.parse.unquote(raw_project_folder) if raw_project_folder else None

        if not project_folder:
            return {
                "statusCode": 400,
                "headers": cors_headers(),
                "body": json.dumps({"error": "projectFolder is required"}),
            }

        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={"courseId": project_folder})
        item = response.get("Item", {})

        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps(
                {
                    "courseId": project_folder,
                    "githubUserId": item.get("githubUserId"),
                    "updatedAt": item.get("updatedAt"),
                    "updatedBy": item.get("updatedBy"),
                }
            ),
        }
    except ClientError as e:
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }
