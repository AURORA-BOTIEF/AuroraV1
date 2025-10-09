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

# Try to import PyJWT, but don't fail if it's not available
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    print("PyJWT not available, JWT token decoding disabled")

def decode_cognito_jwt(token, region="us-east-1"):
    """
    Decode a Cognito JWT token to extract user claims.
    Note: This doesn't validate the signature, just decodes the payload.
    In production, you should validate the token signature.
    """
    if not JWT_AVAILABLE:
        print("JWT decoding not available")
        return None
        
    try:
        # Split the token to get the payload (second part)
        header, payload, signature = token.split('.')
        
        # Add padding if needed
        payload += '=' * (4 - len(payload) % 4)
        
        # Decode the payload
        import base64
        decoded_payload = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded_payload.decode('utf-8'))
        
        return claims
    except Exception as e:
        print(f"Failed to decode JWT token: {e}")
        return None

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

        # Extract user information from multiple sources
        identity = event.get('requestContext', {}).get('identity', {})
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        headers = event.get('headers', {})
        
        # Debug: Log the full requestContext and headers to understand the structure
        print(f"RequestContext debug: {json.dumps(event.get('requestContext', {}), indent=2)}")
        print(f"Headers debug: {json.dumps(headers, indent=2)}")
        
        # Try multiple ways to extract user information
        user_id = None
        user_email = None
        
        # Method 1: IAM identity (for IAM auth)
        user_arn = identity.get('userArn') if identity else None
        if user_arn:
            user_id = user_arn.split('/')[-1]
            user_email = f"{user_id}@iam.amazonaws.com"
            print(f"User identified via IAM: {user_email} ({user_id})")
        
        # Method 2: Cognito claims from authorizer (API Gateway Lambda authorizer)
        if not user_id and claims:
            user_id = claims.get('sub') or claims.get('username') or claims.get('cognito:username')
            user_email = claims.get('email') or claims.get('cognito:email')
            if user_id:
                print(f"User identified via Cognito claims: {user_email} ({user_id})")
        
        # Method 3: Direct claims in requestContext (some Cognito setups)
        if not user_id:
            direct_claims = event.get('requestContext', {}).get('claims', {})
            if direct_claims:
                user_id = direct_claims.get('sub') or direct_claims.get('username') or direct_claims.get('cognito:username')
                user_email = direct_claims.get('email') or direct_claims.get('cognito:email')
                if user_id:
                    print(f"User identified via direct claims: {user_email} ({user_id})")
        
        # Method 4: JWT token from Authorization header (Amplify API with Cognito)
        if not user_id and JWT_AVAILABLE:
            auth_header = headers.get('Authorization') or headers.get('authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
                jwt_claims = decode_cognito_jwt(token)
                if jwt_claims:
                    user_id = jwt_claims.get('sub') or jwt_claims.get('username') or jwt_claims.get('cognito:username')
                    user_email = jwt_claims.get('email') or jwt_claims.get('cognito:email')
                    if user_id:
                        print(f"User identified via JWT token: {user_email} ({user_id})")
        
        # Method 5: Check for identity.cognitoIdentityId (Cognito Identity Pool)
        if not user_id and identity:
            cognito_identity_id = identity.get('cognitoIdentityId')
            if cognito_identity_id:
                user_id = cognito_identity_id.split(':')[-1]  # Extract the actual ID
                user_email = f"cognito-user-{user_id}@example.com"
                print(f"User identified via Cognito Identity: {user_email} ({user_id})")
        
        # Fallback to unknown-user if nothing worked
        if not user_id:
            user_id = 'unknown-user'
            user_email = 'unknown@example.com'
            print(f"WARNING: Could not identify user, using fallback: {user_email} ({user_id})")

        print(f"Final user identification: {user_email} ({user_id})")

        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        print(f"Request body: {json.dumps(body, indent=2)}")

        # Validate required parameters - accept either course_topic or outline_s3_key
        course_topic = body.get('course_topic')
        outline_s3_key = body.get('outline_s3_key')
        
        if not course_topic and not outline_s3_key:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-content-sha256",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
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
        max_images = body.get('max_images')  # Optional: will be determined by number of prompts
        course_bucket = body.get('course_bucket', 'crewai-course-artifacts')  # Default bucket
        project_folder = body.get('project_folder')
        # For OpenAI, disable fallback by default to ensure GPT-5 works or fails cleanly
        allow_openai_fallback = body.get('allow_openai_fallback', model_provider != 'openai')

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
            "course_topic": course_topic or "Custom Course",
            "course_duration_hours": course_duration_hours,
            "module_to_generate": module_to_generate,
            "lesson_to_generate": lesson_to_generate,
            "performance_mode": performance_mode,
            "model_provider": model_provider,
            "user_id": user_id,
            "user_email": user_email,
            "request_timestamp": datetime.now().isoformat(),
            "content_source": "s3" if outline_s3_key else "local",
            "outline_s3_key": outline_s3_key,
            "course_bucket": course_bucket,
            "project_folder": project_folder,
            "allow_openai_fallback": allow_openai_fallback,
        }
        
        # Only include max_images if it was provided
        if max_images is not None:
            execution_input["max_images"] = max_images

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