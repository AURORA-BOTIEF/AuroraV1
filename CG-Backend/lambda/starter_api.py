#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Gateway Lambda function to start the Course Generator Step Functions execution.
This replaces the presigned URL approach with direct IAM-authorized API calls.
"""

import json
import boto3
import os
import re
import base64
import yaml
from datetime import datetime
from botocore.exceptions import ClientError


def decode_jwt_payload_unverified(token: str) -> dict | None:
    """
    Decode JWT payload (middle segment) without signature verification.
    Same approach as lambda/assignments/cognito_auth.py — does not require PyJWT.
    Cognito ID/access tokens use standard base64url JSON payloads.
    """
    if not token or not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    payload += "=" * (4 - len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except Exception as e:
        print(f"Failed to decode JWT payload: {e}")
        return None


def normalize_event_headers(event: dict) -> dict:
    """API Gateway REST vs HTTP API: header keys may differ in casing."""
    headers = event.get("headers") or {}
    return {str(k).lower(): v for k, v in headers.items()}


def merge_authorizer_claims(event: dict) -> dict:
    """
    REST (Cognito pool authorizer): requestContext.authorizer.claims
    HTTP API (JWT authorizer): requestContext.authorizer.jwt.claims
    Values may be nested or duplicate; later keys override.
    """
    rc = event.get("requestContext") or {}
    auth = rc.get("authorizer") or {}
    merged: dict = {}
    for block in (auth.get("claims"), auth.get("jwt", {}).get("claims")):
        if isinstance(block, dict):
            merged.update(block)
    return merged


def derive_user_id_from_claims(claims: dict) -> str | None:
    """Prefer human-readable id (email local part / username); fallback to sub (UUID)."""
    if not claims:
        return None
    email = (claims.get("email") or claims.get("cognito:email") or "").strip()
    if email and "@" in email:
        local = email.split("@", 1)[0]
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", local).strip("-")
        if slug:
            return slug[:64]
    for key in ("cognito:username", "username", "preferred_username"):
        v = (claims.get(key) or "").strip()
        if v:
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", v).strip("-")
            if slug:
                return slug[:64]
    sub = (claims.get("sub") or "").strip()
    return sub if sub else None


def derive_user_email_from_claims(claims: dict) -> str | None:
    if not claims:
        return None
    for key in ("email", "cognito:email"):
        v = (claims.get(key) or "").strip()
        if v:
            return v
    return None


def repair_malformed_yaml(yaml_content: str) -> str:
    """
    Attempt to repair common YAML syntax errors, specifically unquoted strings containing colons.
    """
    import re
    lines = yaml_content.split('\n')
    repaired_lines = []
    
    # Pattern to find keys like 'title:', 'description:' followed by unquoted text with colons
    # capturing groups: 1=indent+key, 2=value
    # Look for lines that:
    # 1. Start with spaces/dashes, then a key (title|description|objective)
    # 2. Have a value that does NOT start with quote
    # 3. Value contains a colon followed by space
    target_keys = ['title', 'description', 'objective', 'summary']
    key_pattern = '|'.join(target_keys)
    
    # Regex:
    # ^(\s*(?:-\s+)?(?:{key_pattern}):\s+)  -> Group 1: indentation + key + colon + space
    # (?!["'])                              -> Negative lookahead: value doesn't start with quote
    # (.*:\s.*)                             -> Group 2: value containing ': '
    # $                                     -> End of line
    pattern = re.compile(f'^(\\s*(?:-\\s+)?(?:{key_pattern}):\\s+)(?!["\'])(.*:\\s.*)$')

    for line in lines:
        match = pattern.match(line)
        if match:
            prefix = match.group(1)
            value = match.group(2).strip()
            # Escape existing quotes if needed
            value = value.replace('"', '\\"')
            repaired_lines.append(f'{prefix}"{value}"')
            print(f"🔧 Repaired YAML line: {line.strip()} -> {prefix.strip()}\"{value}\"")
        else:
            repaired_lines.append(line)
            
    return '\n'.join(repaired_lines)



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
    # Normalize logic
    was_repaired = False
    try:
        # Read the outline from S3
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        outline_content = response['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_content)
        
        if not outline_data:
            print(f"⚠️  Empty outline file: {s3_key}")
            return False
    except yaml.YAMLError as e:
        print(f"⚠️  Initial YAML parse failed: {e}")
        print("🔧 Attempting to repair malformed YAML...")
        try:
            # Rewind and read again if needed, or use cached content
            repaired_content = repair_malformed_yaml(outline_content)
            outline_data = yaml.safe_load(repaired_content)
            
            # If repair worked, we MUST save the normalized/repaired version back
            print("✅ YAML repair successful! Proceeding with normalization.")
            was_repaired = True
        except Exception as repair_e:
            print(f"❌ YAML repair failed: {repair_e}")
            return False
            
    try:
        # Check if already in standard format (course.modules exists)
        # BUT if it was repaired, we MUST write it back even if structure is standard
        if not was_repaired and 'course' in outline_data and 'modules' in outline_data.get('course', {}):
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
        headers_norm = normalize_event_headers(event)
        authorizer_claims = merge_authorizer_claims(event)

        print(f"RequestContext debug: {json.dumps(event.get('requestContext', {}), indent=2)}")
        print(f"Headers debug (normalized keys): {json.dumps(headers_norm, indent=2)}")

        user_id = None
        user_email = None

        # Method 1: IAM identity (for IAM auth)
        user_arn = identity.get('userArn') if identity else None
        if user_arn:
            user_id = user_arn.split('/')[-1]
            user_email = f"{user_id}@iam.amazonaws.com"
            print(f"User identified via IAM: {user_email} ({user_id})")

        # Method 2: API Gateway authorizer claims (Cognito pool / JWT authorizer)
        if not user_id and authorizer_claims:
            user_email = derive_user_email_from_claims(authorizer_claims)
            user_id = derive_user_id_from_claims(authorizer_claims)
            if user_id:
                print(f"User identified via authorizer claims: {user_email} ({user_id})")

        # Method 3: Direct claims on requestContext (some setups)
        if not user_id:
            direct_claims = event.get('requestContext', {}).get('claims', {})
            if direct_claims:
                user_email = derive_user_email_from_claims(direct_claims) or user_email
                user_id = derive_user_id_from_claims(direct_claims)
                if user_id:
                    print(f"User identified via direct requestContext.claims: {user_email} ({user_id})")

        # Method 4: Bearer token in Authorization header (/start-job uses Auth NONE; client must send token)
        if not user_id:
            auth_header = headers_norm.get('authorization') or ''
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1].strip()
                print(f"🔐 Bearer token present (prefix): {token[:12]}...")
                jwt_claims = decode_jwt_payload_unverified(token)
                if jwt_claims:
                    user_email = derive_user_email_from_claims(jwt_claims) or user_email
                    user_id = derive_user_id_from_claims(jwt_claims)
                    if user_id:
                        print(f"User identified via Bearer JWT payload: {user_email} ({user_id})")
            else:
                print("⚠️ No Bearer Authorization header (Cognito ID token not passed to Lambda)")

        # Method 5: Cognito Identity Pool (unauthenticated / federated id)
        if not user_id and identity:
            cognito_identity_id = identity.get('cognitoIdentityId')
            if cognito_identity_id:
                user_id = cognito_identity_id.split(':')[-1]
                user_email = f"cognito-user-{user_id}@example.com"
                print(f"User identified via Cognito Identity: {user_email} ({user_id})")

        # Method 6: Request body user_email (fallback id only; notifications override applied later)
        body_for_email = {}
        try:
            if isinstance(event.get('body'), str):
                if event['body'].strip():
                    body_for_email = json.loads(event['body'])
            else:
                body_for_email = event.get('body', {}) or {}
        except Exception as e:
            print(f"⚠️ Error parsing body for email extraction: {e}")
            body_for_email = {}

        if body_for_email.get('user_email'):
            if not user_email:
                user_email = body_for_email.get('user_email')
            print(f"Request body user_email: {body_for_email.get('user_email')}")
            if not user_id:
                raw = body_for_email.get('user_email') or ''
                user_id = re.sub(r'[^a-zA-Z0-9_-]+', '-', raw.split('@')[0]).strip('-') or None

        if not user_id:
            user_id = 'unknown-user'
            user_email = user_email or 'unknown@example.com'
            print(f"WARNING: Could not identify user, using fallback: {user_email} ({user_id})")

        print(f"Final user identification: {user_email} ({user_id})")

        # Parse request body (MAIN PARSING)
        try:
            raw_body = event.get('body')
            
            # handle base64 encoding
            if event.get('isBase64Encoded') and raw_body:
                import base64
                raw_body = base64.b64decode(raw_body).decode('utf-8')

            if isinstance(raw_body, str):
                if raw_body.strip():
                    body = json.loads(raw_body)
                else:
                    body = {}
            else:
                body = raw_body or {}
        except Exception as e:
            print(f"❌ Error parsing request body JSON: {e}")
            print(f"Raw body: {event.get('body')}")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps({
                    "error": "Invalid JSON in request body"
                })
            }

        print(f"Request body: {json.dumps(body, indent=2)}")

        # Prefer explicit user_email from JSON body for SES notifications (overrides auth fallback)
        if body.get("user_email"):
            user_email = body.get("user_email")
            print(f"Using user_email from request body for notifications: {user_email}")

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