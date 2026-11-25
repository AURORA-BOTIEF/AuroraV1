#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Gateway Lambda function to check Step Functions execution status.
Returns the current status and results of a course generation execution.
"""

import json
import os
import sys
import boto3
from urllib.parse import unquote
from botocore.exceptions import ClientError

_LAMBDA_DIR = os.path.dirname(os.path.abspath(__file__))
if _LAMBDA_DIR not in sys.path:
    sys.path.insert(0, _LAMBDA_DIR)

from course_generation_status import warnings_from_execution_output


def estado_visible_del_curso(execution_status, sf_error=None, sf_cause=None, parsed_output=None):
    """Fields the client status API shows. High-confidence gate failures are needs_review.

    Step Functions still reports FAILED for that execution. ``quality_status`` and
    ``course_status`` tell the UI it was a review gate, not an unknown crash.
    A succeeded execution that still carries the gate flag (shadow mode) is also
    surfaced as needs_review so it is not shown as a clean pass. The flag lives
    on ``lab_quality_decision.needs_review`` after Combine, and the older flat
    ``lab_quality_needs_review`` name is still accepted.
    Low-confidence warnings do not change the status.
    """
    salida = parsed_output if isinstance(parsed_output, dict) else {}
    decision = salida.get("lab_quality_decision")
    decision_needs = isinstance(decision, dict) and decision.get("needs_review") is True
    needs = (
        sf_error == "LabQualityNeedsReview"
        or salida.get("lab_quality_needs_review") is True
        or decision_needs
        or salida.get("quality_status") == "needs_review"
    )
    generation_warnings = warnings_from_execution_output(salida)
    if needs:
        quality_status = "needs_review"
        course_status = "needs_review"
    elif sf_error == "LinkAuditFailed":
        quality_status = "failed"
        course_status = "link_audit_failed"
    elif execution_status == "FAILED":
        quality_status = "failed"
        course_status = "failed"
    elif execution_status == "SUCCEEDED" and generation_warnings:
        # Lab gate passed, but a non-blocking tail (Setup Guide, audit, decks) failed.
        quality_status = "passed"
        course_status = "SUCCEEDED_WITH_WARNINGS"
    elif execution_status == "SUCCEEDED":
        quality_status = "passed"
        course_status = "passed"
    else:
        quality_status = None
        course_status = execution_status

    summaries = salida.get("lab_quality_summaries")
    summary_text = None
    if isinstance(summaries, list) and summaries:
        summary_text = json.dumps(summaries, ensure_ascii=False)
    error = None
    if needs or execution_status == "FAILED":
        error = (
            sf_cause
            or sf_error
            or salida.get("lab_quality_summary")
            or summary_text
            or salida.get("quality_summary")
            or (salida.get("error") if isinstance(salida.get("error"), str) else None)
            or "Unknown error"
        )
    return {
        "quality_status": quality_status,
        "course_status": course_status,
        "needs_review": bool(needs),
        "error": error,
        "quality_summary": (
            sf_cause
            or salida.get("lab_quality_summary")
            or summary_text
            or salida.get("quality_summary")
        ),
        "quality_warnings": salida.get("quality_warnings") or [],
        "labs_needing_review": salida.get("labs_needing_review") or [],
        "generation_warnings": generation_warnings,
    }

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

        # URL decode the execution ARN in case it's encoded
        execution_arn = unquote(execution_arn)
        print(f"Decoded execution ARN: {execution_arn}")

        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
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
        sf_error = execution_response.get('error')
        sf_cause = execution_response.get('cause')

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

        if execution_status == 'RUNNING':
            try:
                import provider_lock
                response_body["queue_status"] = provider_lock.get_queue_status(execution_arn)
            except Exception as queue_err:
                print(f"Could not read provider queue status: {queue_err}")
                response_body["queue_status"] = "unknown"
        else:
            response_body["queue_status"] = execution_status.lower() if execution_status else "unknown"

        visible = estado_visible_del_curso(
            execution_status, sf_error, sf_cause, parsed_output
        )
        response_body.update({
            "quality_status": visible["quality_status"],
            "course_status": visible["course_status"],
            "needs_review": visible["needs_review"],
            "quality_summary": visible["quality_summary"],
            "quality_warnings": visible["quality_warnings"],
            "labs_needing_review": visible["labs_needing_review"],
        })
        if visible["generation_warnings"]:
            response_body["generation_warnings"] = visible["generation_warnings"]
        print(
            f"Course status for client: {visible['course_status']} "
            f"(execution {execution_status}, quality {visible['quality_status']})"
        )

        # Add output if execution completed successfully
        if execution_status == 'SUCCEEDED' and parsed_output:
            response_body.update({
                "result": parsed_output,
                "content_statistics": parsed_output.get('content_statistics', {}),
                "generated_lessons": parsed_output.get('generated_lessons', []),
                "bucket": parsed_output.get('bucket'),
                "project_folder": parsed_output.get('project_folder')
            })

        # Add error details if execution failed or the quality gate blocked delivery
        if visible["error"]:
            response_body.update({
                "error": visible["error"],
                "error_info": parsed_output if parsed_output is not None else {
                    "error": sf_error,
                    "cause": sf_cause,
                },
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