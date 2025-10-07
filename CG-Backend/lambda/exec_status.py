#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Gateway Lambda function to check Step Functions execution status.
Returns the current status and results of a course generation execution.
"""

import json
import boto3
import os
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    """
    Lambda handler for checking course generation execution status.

    Expected event format from API Gateway:
    {
        "pathParameters": {
            "executionArn": "arn:aws:states:region:account:execution:stateMachineName:executionName"
        },
        "queryStringParameters": {
            "include_history": "false"
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
        print("--- Checking Course Generation Status ---")
        print(f"Event: {json.dumps(event, indent=2)}")

        # Extract user information from Cognito claims
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        user_id = claims.get('sub', 'unknown-user')
        user_email = claims.get('email', 'unknown@example.com')

        print(f"User: {user_email} ({user_id})")

        # Extract execution ARN from path parameters
        path_params = event.get('pathParameters', {})
        execution_arn = path_params.get('executionArn')

        if not execution_arn:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
                },
                "body": json.dumps({
                    "error": "executionArn path parameter is required"
                })
            }

        # Extract query parameters
        query_params = event.get('queryStringParameters', {})
        include_history = query_params.get('include_history', 'false').lower() == 'true'

        print(f"Checking execution: {execution_arn}")
        print(f"Include history: {include_history}")

        # Initialize Step Functions client
        sf_client = boto3.client('stepfunctions')

        # Get execution details
        execution_response = sf_client.describe_execution(
            executionArn=execution_arn
        )

        execution_status = execution_response['status']
        execution_input = json.loads(execution_response.get('input', '{}'))
        execution_output = execution_response.get('output')

        # Parse execution output if available
        parsed_output = None
        if execution_output:
            try:
                parsed_output = json.loads(execution_output)
            except json.JSONDecodeError:
                parsed_output = {"raw_output": execution_output}

        # Get execution history if requested and execution is complete
        execution_history = None
        if include_history and execution_status in ['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
            try:
                history_response = sf_client.get_execution_history(
                    executionArn=execution_arn,
                    maxResults=100  # Limit to prevent large responses
                )
                execution_history = history_response.get('events', [])
            except ClientError as e:
                print(f"Could not get execution history: {e}")
                execution_history = None

        # Prepare response
        response_body = {
            "execution_arn": execution_arn,
            "status": execution_status,
            "start_date": execution_response.get('startDate').isoformat() if execution_response.get('startDate') else None,
            "stop_date": execution_response.get('stopDate').isoformat() if execution_response.get('stopDate') else None,
            "user_email": user_email,
            "course_topic": execution_input.get('course_topic'),
            "module_to_generate": execution_input.get('module_to_generate'),
            "model_provider": execution_input.get('model_provider'),
            "performance_mode": execution_input.get('performance_mode')
        }

        # Add output if execution completed successfully
        if execution_status == 'SUCCEEDED' and parsed_output:
            response_body.update({
                "result": parsed_output,
                "content_statistics": parsed_output.get('content_statistics', {}),
                "generated_lessons": parsed_output.get('generated_lessons', []),
                "bucket": parsed_output.get('bucket'),
                "project_folder": parsed_output.get('project_folder')
            })

        # Add error details if execution failed
        elif execution_status == 'FAILED':
            response_body.update({
                "error": parsed_output.get('error') if parsed_output else 'Unknown error',
                "error_info": parsed_output
            })

        # Add execution history if requested
        if execution_history:
            # Simplify history events for frontend consumption
            simplified_history = []
            for event in execution_history:
                simplified_event = {
                    "timestamp": event.get('timestamp').isoformat() if event.get('timestamp') else None,
                    "type": event.get('type'),
                    "state_entered_event_details": event.get('stateEnteredEventDetails', {}),
                    "lambda_function_scheduled_event_details": event.get('lambdaFunctionScheduledEventDetails', {}),
                    "lambda_function_succeeded_event_details": event.get('lambdaFunctionSucceededEventDetails', {}),
                    "lambda_function_failed_event_details": event.get('lambdaFunctionFailedEventDetails', {})
                }
                simplified_history.append(simplified_event)

            response_body["execution_history"] = simplified_history

        # Determine HTTP status code based on execution status
        if execution_status == 'SUCCEEDED':
            status_code = 200
        elif execution_status == 'FAILED':
            status_code = 200  # Still return 200, but with error details
        elif execution_status == 'RUNNING':
            status_code = 200
        else:
            status_code = 200  # For other states like TIMED_OUT, ABORTED

        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps(response_body)
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"AWS Error: {error_code} - {error_message}")

        if error_code == 'ExecutionDoesNotExist':
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
                },
                "body": json.dumps({
                    "error": "Execution not found",
                    "execution_arn": execution_arn
                })
            }
        elif error_code == 'AccessDenied':
            return {
                "statusCode": 403,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
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
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
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
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps({
                "error": f"Internal server error: {str(e)}"
            })
        }