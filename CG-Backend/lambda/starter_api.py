#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Gateway Lambda function to start the Course Generator Step Functions execution.
This replaces the presigned URL approach with direct IAM-authorized API calls.
"""

import json
import boto3
import os
import yaml
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


def normalize_outline_yaml(s3_client, bucket: str, s3_key: str) -> bool:
    """
    Normalize an outline YAML file to the standard nested format.
    
    Standard format (verified working):
        course:
          title: "..."
          modules:
            - title: "Module 1"
              lessons: [...]
              lab_activities: [...]
    
    Non-standard formats supported:
        1. Top-level modules: { modules: [...], title: "..." }
        2. Flat structure: { title: "...", modules: [...] }
    
    Returns True if normalization was performed, False if already normalized.
    """
    try:
        # Read the outline from S3
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        outline_content = response['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_content)
        
        if not outline_data:
            print(f"⚠️  Empty outline file: {s3_key}")
            return False
        
        # Check if already in standard format (course.modules exists)
        if 'course' in outline_data and 'modules' in outline_data.get('course', {}):
            print(f"✅ Outline already in standard format: {s3_key}")
            return False
        
        print(f"🔄 Normalizing outline to standard format: {s3_key}")
        
        # Build the normalized structure
        normalized = {'course': {}}
        
        # If there's a 'course' key but no modules under it, merge with top-level
        existing_course = outline_data.get('course', {})
        
        # Copy course-level metadata
        course_fields = ['title', 'description', 'language', 'level', 'audience', 
                        'prerequisites', 'total_duration_minutes', 'learning_outcomes',
                        'duration_hours', 'objectives']
        
        for field in course_fields:
            # Check top-level first, then existing course object
            if field in outline_data:
                normalized['course'][field] = outline_data[field]
            elif field in existing_course:
                normalized['course'][field] = existing_course[field]
        
        # Get modules from wherever they are
        modules = outline_data.get('modules', [])
        if not modules and existing_course:
            modules = existing_course.get('modules', [])
        
        if not modules:
            print(f"⚠️  No modules found in outline: {s3_key}")
            return False
        
        normalized['course']['modules'] = modules
        
        # Write back to S3
        normalized_yaml = yaml.dump(normalized, default_flow_style=False, allow_unicode=True, sort_keys=False)
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=normalized_yaml.encode('utf-8'),
            ContentType='application/x-yaml'
        )
        
        print(f"✅ Outline normalized successfully: {s3_key}")
        print(f"   - Modules: {len(modules)}")
        print(f"   - Title: {normalized['course'].get('title', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error normalizing outline: {e}")
        import traceback
        traceback.print_exc()
        return False


def parse_module_input(module_input, outline_s3_key=None, course_bucket=None):
    """
    Parse module input into list of module numbers.
    
    Supports:
    - Single int: 1 -> [1]
    - Array: [1, 3, 4] -> [1, 3, 4]
    - String single: "1" -> [1]
    - Comma-separated: "1,3" -> [1, 3]
    - Range: "1-3" -> [1, 2, 3]
    - Mixed: "1,3-5" -> [1, 3, 4, 5]
    - All: "all" -> [1, 2, ..., N] (requires outline to determine N)
    
    Returns: List[int] sorted module numbers
    """
    # Handle list/array input (from frontend)
    if isinstance(module_input, list):
        return sorted(list(set(module_input)))
    
    # Handle integer input
    if isinstance(module_input, int):
        return [module_input]
    
    # Convert to string
    module_str = str(module_input).strip().lower()
    
    # Handle "all" - need to count modules from outline
    if module_str == "all":
        if outline_s3_key and course_bucket:
            try:
                s3_client = boto3.client('s3')
                outline_obj = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
                outline_content = outline_obj['Body'].read().decode('utf-8')
                outline_data = yaml.safe_load(outline_content)
                
                # Outline should already be normalized by normalize_outline_yaml()
                # Standard format: course.modules
                course_data = outline_data.get('course', outline_data)
                modules = course_data.get('modules', [])
                
                total_modules = len(modules)
                print(f"📊 'all' detected: generating all {total_modules} modules")
                return list(range(1, total_modules + 1))
            except Exception as e:
                print(f"⚠️  Could not determine total modules for 'all': {e}")
                # Fallback to module 1
                return [1]
        else:
            print("⚠️  'all' specified but no outline provided, defaulting to module 1")
            return [1]
    
    # Parse comma-separated and ranges
    modules = []
    parts = module_str.split(',')
    
    for part in parts:
        part = part.strip()
        
        if '-' in part:
            # Range: "1-3" -> [1, 2, 3]
            try:
                start, end = part.split('-')
                start_num = int(start.strip())
                end_num = int(end.strip())
                for i in range(start_num, end_num + 1):
                    if i not in modules:
                        modules.append(i)
            except ValueError:
                print(f"⚠️  Invalid range format: {part}, skipping")
        else:
            # Single number
            try:
                num = int(part)
                if num not in modules:
                    modules.append(num)
            except ValueError:
                print(f"⚠️  Invalid module number: {part}, skipping")
    
    # Return sorted list
    modules.sort()
    print(f"📋 Parsed modules: {modules}")
    return modules if modules else [1]  # Default to [1] if parsing failed

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
        
        # Method 6: Check body for user_email (explicitly passed from frontend)
        # Parse request body first to check for email
        if isinstance(event.get('body'), str):
            body_for_email = json.loads(event['body'])
        else:
            body_for_email = event.get('body', {})
            
        if body_for_email.get('user_email'):
            user_email = body_for_email.get('user_email')
            print(f"User identified via request body: {user_email}")
            if not user_id:
                user_id = user_email.split('@')[0] # Fallback ID

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

        # Debug: Log the module parameter extraction
        module_from_body = body.get('module_number') or body.get('module_to_generate')
        print(f"🔍 Module parameter debug:")
        print(f"   - body.get('module_number'): {body.get('module_number')}")
        print(f"   - body.get('module_to_generate'): {body.get('module_to_generate')}")
        print(f"   - Final value: {module_from_body}")

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
        course_bucket = body.get('course_bucket', 'crewai-course-artifacts')  # Default bucket - must be defined early
        
        # ========================================================================
        # NORMALIZE OUTLINE YAML TO STANDARD FORMAT
        # ========================================================================
        # This ensures all downstream functions receive a consistent format:
        #   course:
        #     title: "..."
        #     modules:
        #       - title: "Module 1"
        #         lessons: [...]
        #         lab_activities: [...]
        # ========================================================================
        if outline_s3_key:
            s3_client = boto3.client('s3')
            normalize_outline_yaml(s3_client, course_bucket, outline_s3_key)
        
        # Get lab_ids_to_regenerate first - if present, extract modules from lab IDs
        lab_ids_to_regenerate = body.get('lab_ids_to_regenerate')
        
        # Support both 'module_number' (from GeneradorCursos) and 'module_to_generate' (from GeneradorContenido)
        # Can be: single int (1), string ("1"), "all", comma-separated ("1,3"), range ("1-3"), or mixed ("1,3-5")
        module_input = body.get('module_number') or body.get('module_to_generate')
        
        # If lab_ids_to_regenerate is provided, extract module numbers from lab IDs
        # Lab ID format is MM-LL-II (module-lesson-lab_index), e.g., "04-00-01" -> module 4
        if lab_ids_to_regenerate and not module_input:
            try:
                modules_from_lab_ids = set()
                for lab_id in lab_ids_to_regenerate:
                    if isinstance(lab_id, str) and '-' in lab_id:
                        module_num = int(lab_id.split('-')[0])
                        modules_from_lab_ids.add(module_num)
                if modules_from_lab_ids:
                    module_input = list(modules_from_lab_ids)
                    print(f"📋 Extracted modules from lab_ids: {module_input}")
            except (ValueError, IndexError) as e:
                print(f"⚠️  Could not extract modules from lab_ids: {e}, defaulting to 'all'")
                module_input = 'all'
        
        # Default to module 1 if no module specified
        if not module_input:
            module_input = 1
        
        # Parse module input into list of module numbers
        modules_to_generate = parse_module_input(module_input, outline_s3_key, course_bucket)
        
        lesson_to_generate = body.get('lesson_to_generate')  # Optional: generate specific lesson
        performance_mode = body.get('performance_mode', 'balanced')
        model_provider = body.get('model_provider', 'bedrock')
        max_images = body.get('max_images')  # Optional: will be determined by number of prompts
        project_folder = body.get('project_folder')
        # For OpenAI, disable fallback by default to ensure GPT-5 works or fails cleanly
        allow_openai_fallback = body.get('allow_openai_fallback', model_provider != 'openai')
        # Lab generation parameters - default to 'both' (theory + labs)
        content_type = body.get('content_type', 'both')  # 'theory', 'labs', or 'both'
        lab_requirements = body.get('lab_requirements', '')  # Optional additional requirements for labs (default to empty string)
        lesson_requirements = body.get('lesson_requirements', '')  # Optional additional requirements for lessons (default to empty string)

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
            "modules_to_generate": modules_to_generate,  # NEW: List of modules [1, 3, 5]
            "total_modules": len(modules_to_generate),  # Count for dynamic coordination delay
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
            "content_type": content_type,  # 'theory', 'labs', or 'both'
            "lab_requirements": lab_requirements,  # Always include (empty string if not provided)
            "lesson_requirements": lesson_requirements,  # Always include (empty string if not provided)
            "lab_ids_to_regenerate": body.get('lab_ids_to_regenerate'),  # NEW: Always include (None if not provided)
        }
        
        # Only include optional parameters if they were provided
        if max_images is not None:
            execution_input["max_images"] = max_images
            
        # Pass image_model if provided (default handled by Lambda)
        image_model = body.get('image_model')
        if image_model:
            execution_input["image_model"] = image_model

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
                "modules_to_generate": modules_to_generate,  # List of modules
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