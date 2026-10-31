#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Gateway Lambda function to start the Course Generator Step Functions execution.
This replaces the presigned        # Return success response
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "message": "Course generation started successfully",
                "execution_arn": execution_arn,
                "execution_name": execution_name,
                "course_topic": course_topic,
                "module_to_generate": module_to_generate,
                "user_email": user_email,
                "status": "running"
            })
        }direct IAM-authorized API calls.
"""

import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    """
    Lambda handler for starting course generation via Step Functions.

    Expected event format from API Gateway:
    {
        "body": {
            "course_topic": "Kubernetes for DevOps Engineers",
            "course_duration_hours": 40,
            "module_to_generate": 1,
            "performance_mode": "balanced",
            "model_provider": "bedrock",
            "max_images": 4
        },
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user-id",
                    "email": "user@example.com"
                }
            }
        }
    }
    """

    try:
        print("--- Starting Course Generation API ---")
        print(f"DEBUG: Event keys: {list(event.keys())}")
        print(f"DEBUG: Event type of body: {type(event.get('body'))}")
        print(f"DEBUG: Event body (first 500 chars): {str(event.get('body'))[:500]}")
        
        if os.environ.get('DEBUG'):
            print(f"DEBUG: Full event: {json.dumps(event, indent=2, default=str)}")

        # Extract user information from IAM identity (when using IAM auth)
        # or from Cognito claims (when using Cognito auth)
        try:
            identity = event.get('requestContext', {}).get('identity', {})
            claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
            
            print(f"DEBUG: requestContext keys: {list(event.get('requestContext', {}).keys())}")
            print(f"DEBUG: identity: {json.dumps(identity, indent=2)}")
            print(f"DEBUG: claims: {json.dumps(claims, indent=2)}")
            
            # Try IAM identity first, then Cognito claims
            user_arn = identity.get('userArn', '')
            if user_arn:
                user_id = user_arn.split('/')[-1]
                user_email = user_id + '@iam.amazonaws.com'
            else:
                user_id = claims.get('sub', 'unknown-user')
                user_email = claims.get('email', 'unknown@example.com')

            print(f"DEBUG: Extracted user_id: {user_id}, user_email: {user_email}")
        except Exception as identity_error:
            print(f"DEBUG: Error extracting user identity: {str(identity_error)}")
            user_id = 'error-user'
            user_email = 'error@example.com'

        # Parse request body - handle both API Gateway and direct Lambda invocation
        body_raw = event.get('body')
        print(f"DEBUG: Raw body type: {type(body_raw)}")
        print(f"DEBUG: Raw body (first 200 chars): {str(body_raw)[:200]}")
        
        if body_raw is None:
            print("DEBUG: Body is None, using empty dict")
            body = {}
        elif isinstance(body_raw, str):
            print("DEBUG: Body is string, parsing JSON")
            try:
                body = json.loads(body_raw)
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSON decode error: {e}")
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "Invalid JSON in request body"})
                }
        elif isinstance(body_raw, dict):
            print("DEBUG: Body is already a dict")
            body = body_raw
        else:
            print(f"DEBUG: Body is unexpected type {type(body_raw)}, converting to string then parsing")
            try:
                body = json.loads(str(body_raw))
            except Exception as e:
                print(f"DEBUG: Failed to parse body as string: {e}")
                body = {}

        print(f"DEBUG: Parsed body: {json.dumps(body, indent=2)}")

        # Validate required parameters - accept either course_topic or outline_s3_key
        course_topic = body.get('course_topic')
        outline_s3_key = body.get('outline_s3_key')
        
        if not course_topic and not outline_s3_key:
            print("DEBUG: Missing required parameters")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "error": "Either course_topic or outline_s3_key is required"
                })
            }

        # Set defaults and extract parameters
        course_duration_hours = body.get('course_duration_hours', 40)
        module_to_generate = body.get('module_to_generate', 1)  # Default to module 1
        lesson_to_generate = body.get('lesson_to_generate')  # Optional: generate specific lesson
        performance_mode = body.get('performance_mode', 'balanced')
        model_provider = body.get('model_provider', 'bedrock')
        max_images = body.get('max_images', 4)
        course_bucket = body.get('course_bucket')
        project_folder = body.get('project_folder')

        # Get environment variables
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        print(f"DEBUG: STATE_MACHINE_ARN = {state_machine_arn}")
        if not state_machine_arn:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "error": "STATE_MACHINE_ARN environment variable not set"
                })
            }

        # Initialize Step Functions client
        sf_client = boto3.client('stepfunctions')

        # Prepare input for Step Functions
        execution_input = {
            "course_topic": course_topic or "Custom Course",
            "course_duration_hours": course_duration_hours,
            "module_to_generate": module_to_generate,
            "lesson_to_generate": lesson_to_generate,
            "performance_mode": performance_mode,
            "model_provider": model_provider,
            "max_images": max_images,
            "user_id": user_id,
            "user_email": user_email,
            "request_timestamp": datetime.now().isoformat(),
            "content_source": "s3" if outline_s3_key else "local",
            "outline_s3_key": outline_s3_key,
            "course_bucket": course_bucket,
            "project_folder": project_folder,
            # Include original request parameters for Step Functions
            "original": {
                "course_topic": course_topic,
                "course_duration_hours": course_duration_hours,
                "module_to_generate": module_to_generate,
                "lesson_to_generate": lesson_to_generate,
                "performance_mode": performance_mode,
                "model_provider": model_provider,
                "max_images": max_images,
                "course_bucket": course_bucket,
                "project_folder": project_folder,
                "outline_s3_key": outline_s3_key
            }
        }

        print(f"Starting Step Functions execution with input: {json.dumps(execution_input, indent=2)}")

        # Start the execution
        execution_name = f"course-gen-{user_id}-{int(datetime.now().timestamp())}"

        response = sf_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(execution_input)
        )

        execution_arn = response['executionArn']
        print(f"Started execution: {execution_arn}")

        # Return success response
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "message": "Course generation started successfully",
                "execution_arn": execution_arn,
                "execution_name": execution_name,
                "course_topic": course_topic,
                "module_to_generate": module_to_generate,
                "user_email": user_email,
                "status": "running"
            })
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"AWS Error: {error_code} - {error_message}")

        if error_code == 'AccessDenied':
            return {
                "statusCode": 403,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "error": "Access denied. Please check your IAM permissions."
                })
            }
        else:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "error": f"AWS service error: {error_message}"
                })
            }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

        # Return detailed error information for debugging
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "error": f"Internal server error: {str(e)}",
                "error_type": type(e).__name__,
                "event_keys": list(event.keys()) if isinstance(event, dict) else str(type(event)),
                "request_context": event.get('requestContext', {}) if isinstance(event, dict) else None,
                "body_type": type(event.get('body')) if isinstance(event, dict) else None,
                "body_length": len(str(event.get('body'))) if isinstance(event, dict) and event.get('body') else 0
            })
        }
