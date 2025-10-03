#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for Gemini image generation without AWS dependencies
"""

import os
import json
import boto3
import base64
import time
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Google Generative AI lazily (only when needed)
try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None

def get_secret(secret_name, region_name="us-east-1"):
    """Retrieve a secret from AWS Secrets Manager."""
    import boto3
    from botocore.exceptions import ClientError

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

# Read API key but don't raise at import time. The lambda will return a clear error
# message if the key is required but missing at runtime.
try:
    # Try to get Google API key from Secrets Manager
    google_secret = get_secret("aurora/google-api-key")
    GOOGLE_API_KEY = google_secret.get('api_key')
    print("Retrieved Google API key from Secrets Manager")
except Exception as e:
    print(f"Failed to retrieve Google API key from Secrets Manager: {e}")
    # Fallback to environment variable
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    print("Using Google API key from environment variable")

def test_gemini_image_generation(prompt_text, prompt_id, model_name='models/gemini-2.5-flash-image-preview'):
    """Test Gemini image generation for a single prompt"""
    print(f"--- Testing Gemini for prompt: {prompt_id} ---")
    print(f"Prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}")

    try:
        # Initialize Gemini model
        model = genai.GenerativeModel(model_name)

        # Generate image using Gemini
        enhanced_prompt = f"Generate an image: {prompt_text}"
        print(f"Sending to Gemini: {enhanced_prompt[:100]}{'...' if len(enhanced_prompt) > 100 else ''}")

        response = model.generate_content(enhanced_prompt)
        print(f"Gemini response type: {type(response)}")

        # Process the response
        if response and hasattr(response, 'candidates'):
            print(f"Found {len(response.candidates)} candidates")
            for candidate_idx, candidate in enumerate(response.candidates):
                print(f"Checking candidate {candidate_idx}")
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    print(f"Found {len(candidate.content.parts)} parts")
                    for part_idx, part in enumerate(candidate.content.parts):
                        print(f"Checking part {part_idx}, type: {type(part)}")

                        # Check for text parts first
                        if hasattr(part, 'text'):
                            text_content = part.text
                            print(f"Found text part: {text_content[:200]}...")

                            # Check if this is an error message
                            if any(keyword in text_content.lower() for keyword in ['cannot', 'unable', 'error', 'sorry']):
                                print(f"Gemini returned error: {text_content[:100]}...")
                                return False
                            continue

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
                                return False

                            # Try to detect if this is text
                            try:
                                text_check = image_bytes.decode('utf-8', errors='ignore')
                                if len(text_check) > 0 and not text_check.startswith('\x89PNG') and not text_check.startswith('\xff\xd8'):
                                    print(f"Image data appears to be text: {text_check[:200]}...")
                                    return False
                            except:
                                pass

                            # Decode base64 if needed
                            if isinstance(image_bytes, str):
                                print("Decoding base64 image data")
                                image_bytes = base64.b64decode(image_bytes)

                            # Try to create PIL Image
                            print("Creating PIL Image")
                            try:
                                image = Image.open(BytesIO(image_bytes))
                                print(f"Success! Image size: {image.size}, mode: {image.mode}, format: {image.format}")
                                return True
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

                                return False
                    else:
                        print("No inline_data found")
                        return False
                else:
                    print("Candidate has no valid content")
                    return False
            else:
                print("No candidates with image data found")
                return False
        else:
            print(f"Unexpected response format: {type(response)}")
            if hasattr(response, 'text'):
                print(f"Response text: {response.text}")
            return False

    except Exception as e:
        print(f"Error testing prompt {prompt_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_specific_prompting_for_2_5():
    """Test specific prompting strategies for gemini-2.5-flash-image-preview"""
    test_prompt = "Kubernetes Deployments hierarchy diagram showing relationship between Deployments, ReplicaSets, and Pods"
    
    print("Testing specific prompting for gemini-2.5-flash-image-preview:")
    print("=" * 60)
    
    # Try different prompt strategies
    prompt_strategies = [
        f"Generate an image: {test_prompt}",
        f"Create a visual diagram image of: {test_prompt}. Return only the image, no text.",
        f"Draw a diagram: {test_prompt}. Output format: image only.",
        f"Generate visual content for: {test_prompt}. Format: PNG image.",
        f"Create an illustration: {test_prompt}. Return as image data."
    ]
    
    for i, prompt in enumerate(prompt_strategies, 1):
        print(f"\n--- Strategy {i}: {prompt[:50]}... ---")
        try:
            model = genai.GenerativeModel('models/gemini-2.5-flash-image-preview')
            response = model.generate_content(prompt)
            
            if response and hasattr(response, 'candidates'):
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data'):
                                print(f"✅ SUCCESS! Strategy {i} returned image data!")
                                return True
                            elif hasattr(part, 'text'):
                                print(f"📝 Strategy {i} returned text: {part.text[:100]}...")
        except Exception as e:
            print(f"❌ Strategy {i} failed: {e}")
        
        # Wait between requests
        import time
        time.sleep(5)
    
    return False

def test_different_models():
    """Test different Gemini models for image generation"""
    models_to_test = [
        'models/gemini-2.5-flash-image-preview',
        'models/gemini-1.5-pro',
        'models/gemini-1.5-flash',
        'models/gemini-pro-vision'
    ]
    
    test_prompt = "Generate a simple diagram of a Kubernetes pod"
    
    for model_name in models_to_test:
        print(f"\n--- Testing model: {model_name} ---")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(test_prompt)
            
            if response and hasattr(response, 'candidates'):
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data'):
                                print(f"✅ {model_name} returned image data!")
                                return model_name
                            elif hasattr(part, 'text'):
                                print(f"📝 {model_name} returned text: {part.text[:100]}...")
        except Exception as e:
            print(f"❌ {model_name} failed: {e}")
    
    return None

def test_first_five_prompts():
    """Test with just the first 5 prompts from the logs with longer delays"""
    test_prompts = [
        {
            "id": "03-01-0001",
            "description": "Kubernetes Deployments hierarchy diagram showing relationship between Deployments, ReplicaSets, and Pods"
        },
        {
            "id": "03-01-0002", 
            "description": "Deployment architecture diagram showing Controller, ReplicaSets, and Pods"
        },
        {
            "id": "03-01-0003",
            "description": "Annotated Deployment YAML showing the relationship between different sections"
        },
        {
            "id": "03-01-0004",
            "description": "Timeline diagram showing Recreate deployment pattern with downtime"
        },
        {
            "id": "03-01-0005",
            "description": "Timeline diagram showing Rolling Update deployment pattern with no downtime"
        }
    ]
    
    print("Testing with first 5 prompts and longer delays")
    print("=" * 50)
    
    successful = 0
    total = len(test_prompts)
    
    for i, prompt in enumerate(test_prompts):
        print(f"\n--- Testing prompt {i+1}/{total} ---")
        result = test_gemini_image_generation(prompt['description'], prompt['id'])
        if result:
            successful += 1
        
        # Add longer delay between requests (except for the last one)
        if i < total - 1:
            print("⏱️  Waiting 10 seconds before next request...")
            import time
            time.sleep(10)
    
    print(f"\nResults: {successful}/{total} prompts successful ({successful/total*100:.1f}%)")

def test_improved_gemini_generation(prompt_text, prompt_id):
    """Test Gemini with improved prompting strategies"""
    print(f"--- Testing improved prompting for: {prompt_id} ---")
    print(f"Original prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}")

    try:
        # Initialize Gemini model
        model = genai.GenerativeModel('models/gemini-2.5-flash-image-preview')

        # Try multiple prompt styles
        prompt_styles = [
            f"Generate a visual diagram image showing: {prompt_text}. Create a clear, professional diagram with labels and visual elements.",
            f"Create an illustration of: {prompt_text}. Make it a graphical diagram with colors and clear labels.",
            f"Draw a diagram for: {prompt_text}. Use visual elements and make it easy to understand."
        ]
        
        for i, prompt_style in enumerate(prompt_styles):
            print(f"🤖 Trying prompt style {i+1}: {prompt_style[:50]}...")
            try:
                response = model.generate_content(prompt_style)
                print(f"📡 Response received")
                
                # Check if we got image data
                if response and hasattr(response, 'candidates'):
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data'):
                                    print(f"🖼️  SUCCESS! Found image data with prompt style {i+1}")
                                    return True
                                elif hasattr(part, 'text'):
                                    print(f"📝 Got text response: {part.text[:100]}...")
            except Exception as e:
                print(f"❌ Error with style {i+1}: {e}")
                continue
        
        print(f"❌ All prompt styles failed for {prompt_id}")
        return False
        
    except Exception as e:
        print(f"Error testing improved prompting for {prompt_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_improved_prompting():
    """Test with improved prompting strategies"""
    test_prompts = [
        {
            "id": "03-01-0001",
            "description": "Kubernetes Deployments hierarchy diagram showing relationship between Deployments, ReplicaSets, and Pods"
        },
        {
            "id": "03-01-0002", 
            "description": "Deployment architecture diagram showing Controller, ReplicaSets, and Pods"
        }
    ]
    
    print("Testing with improved prompting strategies")
    print("=" * 50)
    
    successful = 0
    total = len(test_prompts)
    
    for prompt in test_prompts:
        result = test_improved_gemini_generation(prompt['description'], prompt['id'])
        if result:
            successful += 1
        print()
    
    print(f"Results: {successful}/{total} prompts successful ({successful/total*100:.1f}%)")

def lambda_handler(event, context):
    """Simple Lambda handler for generating images from visual prompts."""
    try:
        print("--- Starting Simple Image Generation Lambda ---")
        
        # Get configuration
        # Support both direct invocation (root-level keys) and StepFunctions Execution.Input shape
        # Example StepFunctions shape: {"Execution": {"Input": { ... }}}
        if isinstance(event, dict) and 'Execution' in event and isinstance(event['Execution'], dict):
            exec_input = event['Execution'].get('Input', {})
        else:
            exec_input = event

        course_bucket = exec_input.get('course_bucket')
        project_folder = exec_input.get('project_folder', '250905-kubernetes-for-devops-engineers-09')
        # requested max images (may be missing)
        requested_max_images = exec_input.get('max_images')
        try:
            requested_max_images = int(requested_max_images) if requested_max_images is not None else None
        except Exception:
            requested_max_images = None
        
        # Initialize S3
        s3_client = boto3.client('s3')

        # If genai package or API key is not available, skip generation but return a
        # successful response so the Step Function can continue (or the caller can
        # decide next steps). This avoids failing the orchestration at import time.
        if genai is None:
            print("genai library not available; skipping image generation")
            return {
                "statusCode": 200,
                "message": "genai library not available; skipped image generation",
                "generated_images": []
            }

        if not GOOGLE_API_KEY:
            print("GOOGLE_API_KEY not set; skipping image generation")
            return {
                "statusCode": 200,
                "message": "GOOGLE_API_KEY not set; skipped image generation",
                "generated_images": []
            }

        # Configure genai at runtime
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
        except Exception as e:
            print(f"Failed to configure genai: {e}")
            return {"statusCode": 500, "error": f"Failed to configure genai: {e}"}

        model = genai.GenerativeModel('models/gemini-2.5-flash-image-preview')

        # Backend hard cap to avoid runaway expensive runs
        BACKEND_MAX = int(os.getenv('IMAGES_BACKEND_MAX', '50'))

        # If explicit prompts array provided by VisualPlanner / Step Functions, prefer it
        prompts_from_input = exec_input.get('prompts') if isinstance(exec_input, dict) else None

        generated_images = []

        if prompts_from_input and isinstance(prompts_from_input, list):
            print(f"Received {len(prompts_from_input)} prompts in input; processing up to backend cap {BACKEND_MAX}")
            # Truncate if over backend cap
            if len(prompts_from_input) > BACKEND_MAX:
                print(f"Truncating prompts from {len(prompts_from_input)} to backend cap {BACKEND_MAX}")
                prompts_iter = prompts_from_input[:BACKEND_MAX]
                extra_skipped = len(prompts_from_input) - BACKEND_MAX
            else:
                prompts_iter = prompts_from_input
                extra_skipped = 0

            for idx, prompt_obj in enumerate(prompts_iter, start=1):
                prompt_id = str(prompt_obj.get('id', f'prompt-{idx}'))
                prompt_text = prompt_obj.get('description', '')
                # Allow an optional s3_key (useful if VisualPlanner wrote more metadata)
                prompt_s3_key = prompt_obj.get('s3_key')

                try:
                    print(f"Processing prompt {prompt_id}")
                    prompt_style = f"Generate an image: {prompt_text}"
                    response = model.generate_content(prompt_style)

                    saved = False
                    if response and hasattr(response, 'candidates'):
                        for candidate in response.candidates:
                            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                                for part in candidate.content.parts:
                                    if hasattr(part, 'inline_data') and part.inline_data:
                                        image_data = part.inline_data
                                        if hasattr(image_data, 'data') and image_data.data:
                                            # Save to S3 using deterministic filename (prompt id)
                                            image_filename = f"{prompt_id}.png"
                                            images_key = f"{project_folder}/images/{image_filename}"

                                            image_bytes = image_data.data
                                            if isinstance(image_bytes, str):
                                                import base64
                                                image_bytes = base64.b64decode(image_bytes)

                                            image = Image.open(BytesIO(image_bytes))
                                            output_buffer = BytesIO()
                                            image.save(output_buffer, format='PNG')

                                            s3_client.put_object(
                                                Bucket=course_bucket,
                                                Key=images_key,
                                                Body=output_buffer.getvalue(),
                                                ContentType='image/png'
                                            )

                                            generated_images.append({
                                                'id': prompt_id,
                                                'filename': image_filename,
                                                's3_key': images_key,
                                                'status': 'ok'
                                            })
                                            print(f"✅ Generated: {images_key}")
                                            saved = True
                                            break
                                if saved:
                                    break

                    if not saved:
                        print(f"No image data returned for prompt {prompt_id}")
                        generated_images.append({
                            'id': prompt_id,
                            'status': 'failed',
                            'error': 'no image data from model'
                        })

                    # Small delay between requests
                    import time
                    time.sleep(10)

                except Exception as e:
                    print(f"Error processing prompt {prompt_id}: {e}")
                    generated_images.append({
                        'id': prompt_id,
                        'status': 'failed',
                        'error': str(e)
                    })

            # If we truncated due to backend cap, report skipped prompts
            if extra_skipped:
                print(f"Skipped {extra_skipped} prompts due to backend cap {BACKEND_MAX}")

        else:
            # Fallback: list prompts from S3 and use requested_max_images (defensive path)
            print("No prompts array provided in input; falling back to S3 listing behavior")
            prompts_response = s3_client.list_objects_v2(
                Bucket=course_bucket,
                Prefix=f"{project_folder}/prompts/"
            )

            if 'Contents' not in prompts_response:
                return {"statusCode": 404, "error": "No prompts found"}

            all_prompt_files = [obj['Key'] for obj in prompts_response['Contents'] if obj['Key'].endswith('.json')]

            # Determine effective max images: prefer requested_max_images if provided, otherwise default to 5
            default_max = 5
            if requested_max_images is None:
                max_images = default_max
                print(f"No max_images requested; using default {default_max}")
            else:
                max_images = requested_max_images
                print(f"Requested max_images: {requested_max_images}")

            # Cap to the number of available prompts and backend cap
            available_prompts = len(all_prompt_files)
            effective_max = min(max_images, available_prompts, BACKEND_MAX)
            if effective_max != max_images:
                print(f"Capping max images from {max_images} to available prompts {available_prompts} and backend cap {BACKEND_MAX} => effective_max={effective_max}")
            else:
                print(f"Using effective_max={effective_max} (available_prompts={available_prompts})")

            prompt_files = all_prompt_files[:effective_max]

            for prompt_key in prompt_files:
                try:
                    # Read prompt
                    prompt_response = s3_client.get_object(Bucket=course_bucket, Key=prompt_key)
                    prompt_data = json.loads(prompt_response['Body'].read().decode('utf-8'))

                    prompt_text = prompt_data.get('description', '')
                    prompt_id = prompt_data.get('id', 'unknown')

                    print(f"Processing: {prompt_id}")

                    # Generate image
                    prompt_style = f"Generate an image: {prompt_text}"
                    response = model.generate_content(prompt_style)

                    saved = False
                    if response and hasattr(response, 'candidates'):
                        for candidate in response.candidates:
                            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                                for part in candidate.content.parts:
                                    if hasattr(part, 'inline_data') and part.inline_data:
                                        image_data = part.inline_data
                                        if hasattr(image_data, 'data') and image_data.data:
                                            # Save to S3
                                            image_filename = f"{prompt_id}.png"
                                            images_key = f"{project_folder}/images/{image_filename}"

                                            # Handle the image data
                                            image_bytes = image_data.data
                                            if isinstance(image_bytes, str):
                                                import base64
                                                image_bytes = base64.b64decode(image_bytes)

                                            # Create PIL image
                                            image = Image.open(BytesIO(image_bytes))

                                            # Save to S3
                                            output_buffer = BytesIO()
                                            image.save(output_buffer, format='PNG')

                                            s3_client.put_object(
                                                Bucket=course_bucket,
                                                Key=images_key,
                                                Body=output_buffer.getvalue(),
                                                ContentType='image/png'
                                            )

                                            generated_images.append({
                                                "id": prompt_id,
                                                "filename": image_filename,
                                                "s3_key": images_key,
                                                'status': 'ok'
                                            })

                                            print(f"✅ Generated: {images_key}")
                                            saved = True
                                            break
                                if saved:
                                    break

                    if not saved:
                        print(f"No image data returned for {prompt_key}")
                        generated_images.append({
                            'id': prompt_id,
                            'status': 'failed',
                            'error': 'no image data from model'
                        })

                    # Rate limiting
                    import time
                    time.sleep(10)

                except Exception as e:
                    print(f"Error processing {prompt_key}: {e}")
                    generated_images.append({
                        'id': prompt_key,
                        'status': 'failed',
                        'error': str(e)
                    })
        
        return {
            "statusCode": 200,
            "message": f"Generated {len(generated_images)} images",
            "generated_images": generated_images
        }
        
    except Exception as e:
        return {"statusCode": 500, "error": str(e)}

if __name__ == '__main__':
    # For testing
    print("Simple Image Generation Script")
    print("Use SAM CLI to test: sam local invoke")
