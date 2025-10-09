#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Images Generation Lambda - Standard Python Lambda (NO DOCKER!)
Generates images from visual prompts using Google Gemini API.

Phase 4: ImagesGen Refactor - Remove Docker, keep Gemini integration
"""

import os
import json
import boto3
import base64
import time
from io import BytesIO
from PIL import Image
from typing import Dict, Any, List

# Import Google Generative AI
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("WARNING: google.generativeai not available")

# ============================================================================
# CONFIGURATION
# ============================================================================

# Gemini model to use
GEMINI_MODEL = 'models/gemini-2.5-flash-image'

# Backend hard cap to avoid expensive runs
BACKEND_MAX = int(os.getenv('IMAGES_BACKEND_MAX', '50'))

# Default max images if not specified
DEFAULT_MAX_IMAGES = 5

# Rate limiting delay between requests (seconds)
RATE_LIMIT_DELAY = 10

# ============================================================================
# AWS SECRETS MANAGER
# ============================================================================

def get_secret(secret_name: str, region_name: str = "us-east-1") -> Dict[str, Any]:
    """Retrieve a secret from AWS Secrets Manager."""
    from botocore.exceptions import ClientError
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e
    
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)


def get_google_api_key() -> str:
    """Get Google API key from Secrets Manager or environment."""
    print("🔍 Attempting to retrieve Google API key...")
    try:
        # Try Secrets Manager first
        print("📡 Calling get_secret('aurora/google-api-key')...")
        google_secret = get_secret("aurora/google-api-key")
        print(f"📦 Secret retrieved: {type(google_secret)}, keys: {list(google_secret.keys()) if isinstance(google_secret, dict) else 'N/A'}")
        api_key = google_secret.get('api_key')
        print(f"🔑 api_key value: {'<present>' if api_key else '<missing>'}")
        if api_key:
            print("✅ Retrieved Google API key from Secrets Manager")
            return api_key
        else:
            print("⚠️  api_key field is empty in secret")
    except Exception as e:
        print(f"⚠️  Failed to retrieve from Secrets Manager: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # Fallback to environment variable
    print("🔍 Checking environment variable GOOGLE_API_KEY...")
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        print("✅ Using Google API key from environment variable")
        return api_key
    
    print("❌ No Google API key found in Secrets Manager or environment")
    return None


# ============================================================================
# IMAGE GENERATION
# ============================================================================

def generate_image(model, prompt_id: str, prompt_text: str) -> tuple:
    """
    Generate an image using Gemini.
    
    Args:
        model: Gemini GenerativeModel instance
        prompt_id: Unique identifier for the prompt
        prompt_text: Description of image to generate
        
    Returns:
        tuple: (success: bool, image_bytes: bytes or None, error: str or None)
    """
    try:
        print(f"Generating image for prompt: {prompt_id}")
        print(f"Description: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}")
        
        # Generate image using Gemini
        enhanced_prompt = f"Generate an image: {prompt_text}"
        print(f"Sending to Gemini: {enhanced_prompt[:100]}{'...' if len(enhanced_prompt) > 100 else ''}")
        
        response = model.generate_content(enhanced_prompt)
        print(f"Gemini response type: {type(response)}")
        
        # Process the response
        if response and hasattr(response, 'candidates'):
            print(f"Found {len(response.candidates)} candidates")
            for candidate_idx, candidate in enumerate(response.candidates):
                print(f"Processing candidate {candidate_idx}")
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    print(f"Candidate has {len(candidate.content.parts)} parts")
                    for part_idx, part in enumerate(candidate.content.parts):
                        print(f"Processing part {part_idx}: {type(part)}")
                        
                        # Check for inline_data (image) first
                        if hasattr(part, 'inline_data'):
                            print(f"Found inline_data in part {part_idx}")
                            image_data = part.inline_data
                            image_bytes = image_data.data
                            mime_type = image_data.mime_type

                            print(f"Image data type: {type(image_bytes)}, size: {len(image_bytes) if hasattr(image_bytes, '__len__') else 'unknown'}")
                            print(f"MIME type: {mime_type}")

                            # Check if we have image data
                            if not image_bytes or len(image_bytes) == 0:
                                print(f"Empty image data for {prompt_id}")
                                continue  # Skip this part, check others

                            # Additional validation
                            if len(image_bytes) < 1000:  # Reasonable minimum size for an image
                                print(f"Image data too small ({len(image_bytes)} bytes), skipping")
                                continue

                            # Decode base64 if needed
                            if isinstance(image_bytes, str):
                                print("Decoding base64 image data")
                                image_bytes = base64.b64decode(image_bytes)

                            # Try to create PIL Image
                            print("Creating PIL Image")
                            try:
                                image = Image.open(BytesIO(image_bytes))
                                print(f"Success! Image size: {image.size}, mode: {image.mode}, format: {image.format}")
                                return True, image_bytes, None
                            except Exception as pil_error:
                                print(f"PIL Error: {pil_error}")

                                # Inspect the bytes
                                first_bytes = image_bytes[:20] if len(image_bytes) > 20 else image_bytes
                                print(f"First 20 bytes: {first_bytes}")

                                # Try different formats
                                if image_bytes.startswith(b'\xff\xd8\xff'):
                                    print("Detected JPEG signature")
                                elif image_bytes.startswith(b'\x89PNG'):
                                    print("Detected PNG signature")
                                elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:20]:
                                    print("Detected WebP signature")
                                else:
                                    print("Unknown format signature")

                                continue  # Try next part

                        # Check for text parts (but don't skip image processing)
                        if hasattr(part, 'text'):
                            text_content = part.text
                            print(f"Found text part: {text_content[:200]}...")

                            # Check if this is an error message
                            if any(keyword in text_content.lower() for keyword in ['cannot', 'unable', 'error', 'sorry', 'failed', 'not available']):
                                print(f"Gemini returned error: {text_content[:100]}...")
                                return False, None, f"Gemini error: {text_content[:100]}"
                            # Don't continue here - let it check other parts for images
                                
                    if not any(hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data and len(part.inline_data.data) >= 1000 for part in candidate.content.parts):
                        print("No valid image data found in any part")
                        return False, None, "No valid image data found in any part"
                else:
                    print(f"❌ Candidate {candidate_idx} has no valid content")
                    return False, None, "Candidate has no valid content"
            else:
                print("No candidates with image data found")
                return False, None, "No candidates with image data found"
        else:
            print(f"Unexpected response format: {type(response)}")
            if hasattr(response, 'text'):
                print(f"Response text: {response.text}")
            return False, None, f"Unexpected response format: {type(response)}"

    except Exception as e:
        print(f"Error generating image for {prompt_id}: {e}")
        import traceback
        traceback.print_exc()
        return False, None, str(e)


def save_image_to_s3(s3_client, bucket: str, key: str, image_bytes: bytes) -> bool:
    """
    Save image bytes to S3 as PNG.
    
    Args:
        s3_client: boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key
        image_bytes: Raw image bytes
        
    Returns:
        bool: Success status
    """
    try:
        # Convert to PNG using PIL
        image = Image.open(BytesIO(image_bytes))
        output_buffer = BytesIO()
        image.save(output_buffer, format='PNG')
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=output_buffer.getvalue(),
            ContentType='image/png'
        )
        
        print(f"✅ Saved to S3: {key}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving to S3: {e}")
        return False


# ============================================================================
# LAMBDA HANDLER
# ============================================================================

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for generating images from visual prompts.
    
    Expected event format:
    {
        "course_bucket": "bucket-name",
        "project_folder": "project-name",
        "prompts": [
            {
                "id": "01-01-0001",
                "description": "Kubernetes architecture diagram",
                "s3_key": "project/prompts/01-01-0001-name.json" 
            }
        ],
        "max_images": 10  # Optional, defaults to 5 if not provided
    }
    
    Also supports StepFunctions Execution.Input shape:
    {
        "Execution": {
            "Input": { ... }
        }
    }
    
    Returns:
    {
        "statusCode": 200,
        "message": "Generated N images",
        "generated_images": [
            {
                "id": "01-01-0001",
                "filename": "01-01-0001.png",
                "s3_key": "project/images/01-01-0001.png",
                "status": "ok"
            }
        ],
        "bucket": "bucket-name",
        "project_folder": "project-name",
        "lesson_keys": ["project/lessons/01-01-lesson.md"],
        "image_mappings": {
            "[VISUAL: 01-01-0001]": "project/images/01-01-0001.png"
        }
    }
    """
    try:
        print("=== Starting Image Generation Lambda ===")
        
        # Extract event data (support Step Functions format)
        if isinstance(event, dict) and 'Execution' in event and isinstance(event['Execution'], dict):
            exec_input = event['Execution'].get('Input', {})
        else:
            exec_input = event
        
        # Get parameters
        course_bucket = exec_input.get('course_bucket')
        project_folder = exec_input.get('project_folder')
        prompts_from_input = exec_input.get('prompts', [])
        prompts_prefix = exec_input.get('prompts_prefix')
        requested_max_images = exec_input.get('max_images')
        
        print(f"Bucket: {course_bucket}")
        print(f"Project: {project_folder}")
        print(f"Prompts provided: {len(prompts_from_input) if prompts_from_input else 0}")
        print(f"Prompts prefix: {prompts_prefix}")
        print(f"Max images: {requested_max_images}")
        
        # Validate required parameters
        if not course_bucket or not project_folder:
            print("❌ Missing required parameters")
            return {
                "statusCode": 400,
                "error": "Missing required parameters: course_bucket and project_folder",
                "generated_images": [],
                "bucket": course_bucket,
                "project_folder": project_folder
            }
        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # If prompts_prefix provided, read prompts from S3
        if prompts_prefix and not prompts_from_input:
            print(f"📂 Reading prompts from S3: {prompts_prefix}")
            try:
                # Build full S3 prefix
                full_prefix = f"{project_folder}/{prompts_prefix}" if not prompts_prefix.startswith(project_folder) else prompts_prefix
                
                # List all prompt files
                list_response = s3_client.list_objects_v2(
                    Bucket=course_bucket,
                    Prefix=full_prefix
                )
                
                if 'Contents' in list_response:
                    prompt_files = [obj['Key'] for obj in list_response['Contents'] if obj['Key'].endswith('.json')]
                    print(f"📄 Found {len(prompt_files)} prompt files in S3")
                    
                    # Read each prompt file
                    for prompt_key in prompt_files:
                        try:
                            prompt_obj = s3_client.get_object(Bucket=course_bucket, Key=prompt_key)
                            prompt_data = json.loads(prompt_obj['Body'].read().decode('utf-8'))
                            
                            # Only include if it has a description (the actual prompt text)
                            if 'description' in prompt_data and prompt_data['description']:
                                prompts_from_input.append({
                                    'id': prompt_data.get('id'),
                                    'description': prompt_data.get('description'),
                                    's3_key': prompt_key
                                })
                        except Exception as e:
                            print(f"⚠️  Failed to read prompt {prompt_key}: {e}")
                    
                    print(f"✅ Loaded {len(prompts_from_input)} prompts with descriptions from S3")
                else:
                    print(f"⚠️  No prompt files found at {full_prefix}")
            except Exception as e:
                print(f"❌ Error reading prompts from S3: {e}")
        
        # Check if genai is available
        if genai is None:
            print("⚠️  genai library not available; skipping image generation")
            return {
                "statusCode": 200,
                "message": "genai library not available; skipped image generation",
                "generated_images": [],
                "bucket": course_bucket,
                "project_folder": project_folder
            }
        
        # Get Google API key
        google_api_key = get_google_api_key()
        if not google_api_key:
            print("⚠️  Google API key not available; skipping image generation")
            return {
                "statusCode": 200,
                "message": "Google API key not available; skipped image generation",
                "generated_images": [],
                "bucket": course_bucket,
                "project_folder": project_folder
            }
        
        # Configure Gemini
        try:
            genai.configure(api_key=google_api_key)
            model = genai.GenerativeModel(GEMINI_MODEL)
            print(f"✅ Initialized Gemini model: {GEMINI_MODEL}")
        except Exception as e:
            print(f"❌ Failed to configure Gemini: {e}")
            return {
                "statusCode": 500,
                "error": f"Failed to configure Gemini: {e}",
                "generated_images": []
            }
        
        generated_images = []
        
        # Handle empty prompts list
        if not prompts_from_input or len(prompts_from_input) == 0:
            print("⚠️  No prompts to process")
            
            # Still discover lessons for BookBuilder
            lessons_prefix = f"{project_folder}/lessons/"
            lesson_keys = []
            try:
                list_response = s3_client.list_objects_v2(
                    Bucket=course_bucket,
                    Prefix=lessons_prefix
                )
                if 'Contents' in list_response:
                    lesson_keys = [obj['Key'] for obj in list_response['Contents'] if obj['Key'].endswith('.md')]
            except Exception as e:
                print(f"Error listing lessons: {e}")
            
            return {
                "statusCode": 200,
                "message": "No visual prompts to process",
                "generated_images": [],
                "bucket": course_bucket,
                "project_folder": project_folder,
                "lesson_keys": lesson_keys,
                "image_mappings": {}
            }
        
        # Determine how many to process
        num_prompts = len(prompts_from_input)
        effective_max = min(num_prompts, BACKEND_MAX)
        
        if num_prompts > BACKEND_MAX:
            print(f"⚠️  Truncating from {num_prompts} to backend cap {BACKEND_MAX}")
        
        prompts_to_process = prompts_from_input[:effective_max]
        print(f"Processing {len(prompts_to_process)} prompts")
        
        # Process each prompt
        for idx, prompt_obj in enumerate(prompts_to_process, start=1):
            prompt_id = str(prompt_obj.get('id', f'prompt-{idx}'))
            prompt_text = prompt_obj.get('description', '')
            
            print(f"\n[{idx}/{len(prompts_to_process)}] Processing: {prompt_id}")
            
            # Skip if no description
            if not prompt_text:
                print(f"⚠️  Skipping {prompt_id}: no description")
                generated_images.append({
                    'id': prompt_id,
                    'status': 'skipped',
                    'error': 'no description'
                })
                continue
            
            # Generate image
            success, image_bytes, error = generate_image(model, prompt_id, prompt_text)
            
            if success and image_bytes:
                # Save to S3
                image_filename = f"{prompt_id}.png"
                images_key = f"{project_folder}/images/{image_filename}"
                
                if save_image_to_s3(s3_client, course_bucket, images_key, image_bytes):
                    generated_images.append({
                        'id': prompt_id,
                        'filename': image_filename,
                        's3_key': images_key,
                        'status': 'ok'
                    })
                    print(f"✅ Generated: {images_key}")
                else:
                    generated_images.append({
                        'id': prompt_id,
                        'status': 'failed',
                        'error': 'failed to save to S3'
                    })
            else:
                print(f"❌ Failed: {error}")
                generated_images.append({
                    'id': prompt_id,
                    'status': 'failed',
                    'error': error or 'unknown error'
                })
            
            # Rate limiting delay
            if idx < len(prompts_to_process):
                print(f"⏳ Waiting {RATE_LIMIT_DELAY}s before next request...")
                time.sleep(RATE_LIMIT_DELAY)
        
        # Build image mappings for BookBuilder
        image_mappings = {}
        lesson_keys = []
        
        # Discover lessons in the project folder
        lessons_prefix = f"{project_folder}/lessons/"
        try:
            list_response = s3_client.list_objects_v2(
                Bucket=course_bucket,
                Prefix=lessons_prefix
            )
            if 'Contents' in list_response:
                lesson_keys = [obj['Key'] for obj in list_response['Contents'] if obj['Key'].endswith('.md')]
                print(f"Found {len(lesson_keys)} lesson files")
        except Exception as e:
            print(f"Error listing lessons: {e}")
        
        # Create mappings for each generated image
        for img_data in generated_images:
            if img_data.get('status') == 'ok' and 's3_key' in img_data:
                # Map the visual ID to the S3 key
                visual_tag = f"[VISUAL: {img_data['id']}]"
                image_mappings[visual_tag] = img_data['s3_key']
        
        # Also include mappings for existing images in the project
        images_prefix = f"{project_folder}/images/"
        try:
            images_response = s3_client.list_objects_v2(
                Bucket=course_bucket,
                Prefix=images_prefix
            )
            if 'Contents' in images_response:
                for img_obj in images_response['Contents']:
                    img_key = img_obj['Key']
                    if img_key.endswith('.png'):
                        # Extract ID from filename (e.g., "01-01-0001.png" -> "01-01-0001")
                        img_filename = img_key.split('/')[-1]
                        img_id = img_filename.replace('.png', '')
                        visual_tag = f"[VISUAL: {img_id}]"
                        # Only add if not already in mappings (newly generated take precedence)
                        if visual_tag not in image_mappings:
                            image_mappings[visual_tag] = img_key
                            print(f"✅ Included existing image mapping: {visual_tag} -> {img_key}")
        except Exception as e:
            print(f"Warning: Could not scan existing images: {e}")
        
        # Summary
        successful = len([img for img in generated_images if img.get('status') == 'ok'])
        print(f"\n{'='*60}")
        print(f"✅ Generated {successful}/{len(prompts_to_process)} images successfully")
        print(f"📊 Total prompts processed: {len(generated_images)}")
        print(f"{'='*60}\n")
        
        return {
            "statusCode": 200,
            "message": f"Generated {successful} images successfully",
            "generated_images": generated_images,
            "bucket": course_bucket,
            "project_folder": project_folder,
            "lesson_keys": lesson_keys,
            "image_mappings": image_mappings,
            "statistics": {
                "total_prompts": len(prompts_to_process),
                "successful": successful,
                "failed": len(generated_images) - successful,
                "skipped": num_prompts - len(prompts_to_process) if num_prompts > len(prompts_to_process) else 0
            }
        }
        
    except Exception as e:
        print(f"❌ Lambda error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "statusCode": 500,
            "error": str(e),
            "generated_images": []
        }


if __name__ == '__main__':
    print("Images Generation Lambda")
    print("Use SAM CLI to test: sam local invoke ImagesGen -e test-event.json")
