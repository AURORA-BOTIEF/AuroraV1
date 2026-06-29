#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Gateway Lambda function to start the Course Generator Step Functions execution.
This replaces the presigned URL approach with direct IAM-authorized API calls.
"""

import json
import io
import boto3
import os
import re
import base64
import yaml
from datetime import datetime
from botocore.exceptions import ClientError


DEFAULT_IMAGE_MODEL = 'models/gemini-2.5-flash-image'


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
    Attempt to repair common YAML syntax errors, especially unquoted wrapped scalars containing colons.
    """
    lines = yaml_content.splitlines()
    repaired_lines = []
    key_value_pattern = re.compile(r'^(\s*-?\s*[A-Za-z_][\w\-]*\s*:\s*)(.+)$')

    i = 0
    while i < len(lines):
        line = lines[i]
        match = key_value_pattern.match(line)
        if not match:
            repaired_lines.append(line)
            i += 1
            continue

        prefix, value = match.group(1), match.group(2).strip()
        base_indent = len(line) - len(line.lstrip(' '))

        # Merge wrapped continuation lines for plain scalars.
        j = i + 1
        merged_value = value
        while j < len(lines):
            next_line = lines[j]
            next_stripped = next_line.strip()
            next_indent = len(next_line) - len(next_line.lstrip(' '))

            if not next_stripped or next_indent <= base_indent:
                break
            if key_value_pattern.match(next_line):
                break

            merged_value = f"{merged_value} {next_stripped}"
            j += 1

        merged_value = re.sub(r'\s+', ' ', merged_value).strip()
        repaired_line = f"{prefix}{merged_value}"

        # Quote plain scalars that contain ': ' because YAML may interpret them as mappings.
        if merged_value and merged_value[0] not in ('\'', '"', '{', '[', '|', '>', '&', '*', '!') and ': ' in merged_value:
            escaped = merged_value.replace("'", "''")
            repaired_line = f"{prefix}'{escaped}'"
            print(f"🔧 Repaired YAML scalar: {line.strip()} -> {repaired_line.strip()}")

        repaired_lines.append(repaired_line)
        i = j if j > i + 1 else i + 1

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


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text pages from a raw PDF byte stream using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"❌ Error extracting PDF text: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(f"Could not parse PDF content: {e}")


def call_bedrock_ai(prompt: str) -> str:
    """Call AWS Bedrock Claude 3.5 Sonnet to process outline metadata."""
    bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
    model_id = os.environ.get("BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-6")
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8000,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    try:
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )
        response_body = json.loads(response['body'].read())
        if 'content' in response_body and len(response_body['content']) > 0:
            return response_body['content'][0]['text']
        raise ValueError("No content returned in Bedrock response")
    except Exception as e:
        print(f"❌ Bedrock AI call error: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(f"AI Service unavailable: {e}")


def convert_non_yaml_to_yaml(content: str, filename: str) -> str:
    """Use AI to align/convert text into a standard syllabus YAML string."""
    prompt = f"""You are an expert curriculum designer and syllabus alignment assistant.
Your task is to take the following course description, topics, or outline (uploaded as {filename}) and convert/align it into a standardized YAML format that matches our system's expected schema exactly.

Expected YAML Schema:
```yaml
course:
  title: "Course Title"
  description: "Detailed description of the course"
  language: "es" or "en" (Detect from content, default to "es" if not clear)
  level: "beginner" or "intermediate" or "advanced"
  audience:
    - "Target audience profile 1"
    - "Target audience profile 2"
  prerequisites:
    - "Prerequisite 1"
    - "Prerequisite 2"
  total_duration_minutes: integer (Sum of all module durations)
  learning_outcomes:
    - "Learning outcome 1"
    - "Learning outcome 2"
  modules:
    - title: "Module Title"
      summary: "Short summary of the module goals"
      duration_minutes: integer (Sum of all lessons and labs in this module)
      percent_theory: integer (Percentage of theory vs practice, e.g. 50)
      percent_practice: integer (Percentage of practice, e.g. 50)
      bloom_level: "Understand" or "Apply" or "Analyze" or "Remember"
      lessons:
        - title: "Lesson Title"
          duration_minutes: integer (Usually between 15 and 90 minutes)
          bloom_level: "Understand" or "Apply" or "Analyze" etc.
          topics:
            - title: "Topic 1 details"
              duration_minutes: integer
              bloom_level: "Understand"
            - title: "Topic 2 details"
              duration_minutes: integer
              bloom_level: "Apply"
          lab_activities:
            - title: "Hands-on activity details"
              duration_minutes: integer
              bloom_level: "Apply"
```

Important Alignment & Content Rules:
1. **100% Structural Alignment:** The output must match this exact schema. If any key details like audience, prerequisites, durations, or learning outcomes are missing from the input, you MUST generate sensible, professional defaults to ensure a complete, high-quality course syllabus.
2. **Durations & Calculations:** Ensure all durations are populated. Total duration must be the sum of all module durations, and each module duration must be the sum of its lessons and labs. Topics and lab activities should also have sub-durations.
3. **Module & Lesson Creation:**
   - If the user's input is a full detailed outline, map it cleanly to this structure.
   - If the user's input is just a short topic description (e.g. "A brief 2-day course on Docker basics"), you MUST act as an AI Curriculum Agent and expand/design a complete course with at least 3 distinct modules, logical lessons (each with specific topics), and practical hands-on labs (`lab_activities`).
4. **No Chat text:** Return ONLY the raw YAML block inside a markdown code block (delimited by ```yaml ... ```) so it can be safely parsed, or return just the YAML text. Do not include any greeting, conversational text, or explanations.
5. **YAML Safety:** Quote all plain scalar values containing colons, commas, or special characters (e.g., using double quotes for titles and descriptions) to avoid parsing issues.

Input Content:
---
{content}
---
"""
    ai_output = call_bedrock_ai(prompt)
    
    # Extract YAML content from markdown code block if present
    match = re.search(r'```(?:yaml)?\s*(.*?)\s*```', ai_output, re.DOTALL | re.IGNORECASE)
    if match:
        yaml_content = match.group(1)
    else:
        yaml_content = ai_output.strip()
        
    return yaml_content


def process_and_normalize_outline_s3(s3_client, bucket: str, s3_key: str) -> str:
    """
    Checks the extension of the outline file. If it is non-YAML, extracts text,
    converts it to normalized YAML using AI, saves it back to S3 under a .yaml extension,
    and returns the new key.
    """
    lower_key = s3_key.lower()
    is_yaml = lower_key.endswith('.yaml') or lower_key.endswith('.yml')
    
    if is_yaml:
        print(f"📄 File is already YAML: {s3_key}. Normalizing structure directly.")
        normalize_outline_yaml(s3_client, bucket, s3_key)
        return s3_key

    # For PDF, Markdown, or raw text, we convert.
    print(f"🔄 Detected non-YAML format for outline key: {s3_key}")
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        raw_bytes = response['Body'].read()
    except Exception as e:
        print(f"❌ Error reading file from S3: {e}")
        raise ValueError(f"Could not read outline from S3: {e}")

    # Extract text content
    if lower_key.endswith('.pdf'):
        print(f"📂 Extracting text from PDF file: {s3_key}")
        text_content = extract_text_from_pdf(raw_bytes)
    else:
        # Markdown, TXT, or unspecified
        print(f"📂 Decoding text file: {s3_key}")
        text_content = raw_bytes.decode('utf-8', errors='ignore')

    # Convert to YAML using AI
    print(f"🤖 Invoking AI syllabus agent to align content to YAML standard...")
    converted_yaml = convert_non_yaml_to_yaml(text_content, os.path.basename(s3_key))
    
    # Validate the generated YAML structure
    try:
        parsed_yaml = yaml.safe_load(converted_yaml)
        if not parsed_yaml:
            raise ValueError("Parsed YAML is empty")
    except Exception as parse_err:
        print(f"❌ Generated YAML is invalid: {parse_err}")
        print("Generated content was:")
        print(converted_yaml)
        raise ValueError(f"AI failed to generate a parseable YAML: {parse_err}")

    # Save the YAML content back to S3 with .yaml extension
    base_path, _ = os.path.splitext(s3_key)
    new_s3_key = f"{base_path}.yaml"
    
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=new_s3_key,
            Body=converted_yaml.encode('utf-8'),
            ContentType='application/x-yaml'
        )
        print(f"💾 Converted YAML saved to S3: {new_s3_key}")
    except Exception as s3_err:
        print(f"❌ Failed to save converted YAML to S3: {s3_err}")
        raise ValueError(f"Failed to upload converted outline: {s3_err}")

    # Run the standard normalization on the generated YAML to ensure absolute schema compliance
    normalize_outline_yaml(s3_client, bucket, new_s3_key)
    
    return new_s3_key


def normalize_course_language_code(lang) -> str:
    """Map outline/API language to 'es' or 'en'. Default Spanish; English only if explicitly requested."""
    if lang is None:
        return "es"
    s = str(lang).strip().lower()
    if not s:
        return "es"
    if s.startswith("en") or "english" in s or "inglés" in s or "ingles" in s:
        return "en"
    if s.startswith("es") or "español" in s or "espanol" in s:
        return "es"
    return "es"


def read_course_language_from_outline(s3_client, bucket: str, s3_key: str | None) -> str | None:
    """Return raw language field from outline YAML, or None."""
    if not s3_key or not bucket:
        return None
    try:
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        outline_content = response["Body"].read().decode("utf-8")
        outline_data = yaml.safe_load(outline_content)
        if not outline_data:
            return None
        course = outline_data.get("course", outline_data)
        raw = course.get("language")
        return str(raw).strip() if raw else None
    except Exception as e:
        print(f"⚠️ Could not read course language from outline: {e}")
        return None


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
                try:
                    outline_data = yaml.safe_load(outline_content)
                except yaml.YAMLError:
                    repaired_content = repair_malformed_yaml(outline_content)
                    outline_data = yaml.safe_load(repaired_content)
                
                # Outline should already be normalized by normalize_outline_yaml()
                # Standard format: course.modules
                course_data = outline_data.get('course', outline_data)
                modules = course_data.get('modules', [])
                
                total_modules = len(modules)
                if total_modules == 0:
                    raise ValueError("No modules found in outline")
                print(f"📊 'all' detected: generating all {total_modules} modules")
                return list(range(1, total_modules + 1))
            except Exception as e:
                raise ValueError(f"Could not determine total modules for 'all': {e}")
        else:
            raise ValueError("'all' specified but outline_s3_key/course_bucket are missing")
    
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
    if not modules:
        raise ValueError(f"Invalid module selection: {module_input}")
    return modules

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

        # Check if this is an async background execution
        is_async = body.get('async_processing', False)
        outline_s3_key = body.get('outline_s3_key')
        
        # Determine if we should handle this request asynchronously.
        # We run it asynchronously if it is a non-YAML outline upload and NOT already running in the background.
        if outline_s3_key and not is_async and context and getattr(context, 'function_name', None):
            lower_key = str(outline_s3_key).lower()
            is_non_yaml = not (lower_key.endswith('.yaml') or lower_key.endswith('.yml'))
            if is_non_yaml:
                print(f"⚡ Non-YAML format detected. Triggering asynchronous execution in background to avoid API timeouts...")
                # Construct the payload to trigger the lambda asynchronously
                # Add 'async_processing: True' inside request body
                body['async_processing'] = True
                
                # Re-serialize event body
                async_event = dict(event)
                async_event['body'] = json.dumps(body)
                async_event['isBase64Encoded'] = False
                
                # Invoke ourselves asynchronously
                try:
                    lambda_client = boto3.client('lambda')
                    lambda_client.invoke(
                        FunctionName=context.function_name,
                        InvocationType='Event',
                        Payload=json.dumps(async_event)
                    )
                    print("✅ Successfully triggered background Lambda execution. Returning 200 OK to client.")
                    return {
                        "statusCode": 200,
                        "headers": {
                            "Content-Type": "application/json",
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                            "Access-Control-Allow-Methods": "OPTIONS,POST"
                        },
                        "body": json.dumps({
                            "message": "Syllabus conversion and generation started asynchronously in the background.",
                            "project_folder": body.get('project_folder')
                        })
                    }
                except Exception as invoke_err:
                    print(f"⚠️ Failed to invoke background Lambda: {invoke_err}. Falling back to synchronous processing.")
                    # If invocation fails, we fall back to normal synchronous execution
                    pass

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
        s3_client = None
        if outline_s3_key:
            s3_client = boto3.client('s3')
            outline_s3_key = process_and_normalize_outline_s3(s3_client, course_bucket, outline_s3_key)
        
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
        
        # Default to full-course generation if no module is specified by the UI
        if not module_input:
            module_input = 'all'
        
        # Parse module input into list of module numbers
        modules_to_generate = parse_module_input(module_input, outline_s3_key, course_bucket)
        
        lesson_to_generate = body.get('lesson_to_generate')  # Optional: generate specific lesson
        performance_mode = body.get('performance_mode', 'balanced')
        model_provider = body.get('model_provider', 'bedrock')
        image_model = (body.get('image_model') or DEFAULT_IMAGE_MODEL).strip()
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

        # Course language: outline YAML is source of truth; optional API override if outline has no language
        raw_outline_lang = (
            read_course_language_from_outline(s3_client, course_bucket, outline_s3_key)
            if outline_s3_key and s3_client
            else None
        )
        if raw_outline_lang and str(raw_outline_lang).strip():
            course_language = normalize_course_language_code(raw_outline_lang)
            print(f"🌐 course_language from outline: raw={raw_outline_lang!r} -> {course_language}")
        elif body.get("course_language") is not None and str(body.get("course_language") or "").strip():
            course_language = normalize_course_language_code(body.get("course_language"))
            print(f"🌐 course_language from API body (no outline language): {course_language}")
        else:
            course_language = "es"
            print(f"🌐 course_language default (no outline key): {course_language}")

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
            "course_language": course_language,
            "image_model": image_model,
        }
        
        # Only include optional parameters if they were provided
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