#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Gateway Lambda function to start the Course Generator Step Functions execution.
This replaces the presigned URL approach with direct IAM-authorized API calls.
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
        print(f"Event: {json.dumps(event, indent=2)}")

        # Extract user information from Cognito claims
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        user_id = claims.get('sub', 'unknown-user')
        user_email = claims.get('email', 'unknown@example.com')

        print(f"User: {user_email} ({user_id})")

        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        print(f"Request body: {json.dumps(body, indent=2)}")

        # Validate required parameters
        course_topic = body.get('course_topic')
        if not course_topic:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps({
                    "error": "course_topic is required"
                })
            }

        # Set defaults and extract parameters
        course_duration_hours = body.get('course_duration_hours', 40)
        module_to_generate = body.get('module_to_generate', 1)  # Default to module 1
        performance_mode = body.get('performance_mode', 'balanced')
        model_provider = body.get('model_provider', 'bedrock')
        max_images = body.get('max_images', 4)

        # Get environment variables
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        if not state_machine_arn:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps({
                    "error": "STATE_MACHINE_ARN environment variable not set"
                })
            }

        # Initialize Step Functions client
        sf_client = boto3.client('stepfunctions')

        # Prepare input for Step Functions
        execution_input = {
            "course_topic": course_topic,
            "course_duration_hours": course_duration_hours,
            "module_to_generate": module_to_generate,
            "performance_mode": performance_mode,
            "model_provider": model_provider,
            "max_images": max_images,
            "user_id": user_id,
            "user_email": user_email,
            "request_timestamp": datetime.now().isoformat(),
            "content_source": "local"  # Use local YAML outline
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
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps({
                    "error": "Access denied. Please check your IAM permissions."
                })
            }
        else:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps({
                    "error": f"AWS service error: {error_message}"
                })
            }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "error": f"Internal server error: {str(e)}"
            })
        }