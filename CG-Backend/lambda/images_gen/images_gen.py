#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Images Generation Lambda - Standard Python Lambda (NO DOCKER!)
Generates images from visual prompts using Google Gemini API or OpenAI Images (gpt-image-2).

Supports:
- Gemini 2.5 Flash Image / Gemini 3 Pro Image (Google Generative AI)
- OpenAI GPT Image 2 (gpt-image-2) via Images API

GEMINI IMPROVEMENTS (for >80% success rate):
1. Prompt Optimization: Automatically enhances prompts with style guidance
2. Safety Settings: More permissive for educational content
3. Retry Logic: Up to 2 retries with simplified prompts on failure
4. Text-Heavy Detection: Converts tables/screenshots to conceptual illustrations
5. Error Recovery: Intelligent fallback strategies for blocked/failed generations
"""

import os
import json
import boto3
import base64
import time
import logging
import urllib.error
import urllib.request
from functools import partial
from io import BytesIO
from PIL import Image
from typing import Dict, Any, List, Optional
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import Google Generative AI (for Gemini)
try:
    import google.generativeai as genai
    logger.info("✅ google.generativeai imported successfully")
except ImportError:
    genai = None
    logger.error("❌ WARNING: google.generativeai not available")



# ============================================================================
# CONFIGURATION
# ============================================================================

# Gemini model to use
GEMINI_MODEL = 'models/gemini-3-pro-image-preview'

# Default image generation model
DEFAULT_IMAGE_MODEL = 'models/gemini-2.5-flash-image'

# Backend hard cap to avoid expensive runs
BACKEND_MAX = int(os.getenv('IMAGES_BACKEND_MAX', '50'))

# Model-specific batch limits (to prevent Lambda timeout)
# Gemini 3 Pro: ~25s per image, limit batch to prevent 15-min timeout
# Gemini 2.5 Flash: ~7s per image, can handle more
GEMINI3_MAX_BATCH = int(os.getenv('GEMINI3_MAX_BATCH', '4'))  # ~100s + overhead = safe for 15min
GEMINI25_MAX_BATCH = int(os.getenv('GEMINI25_MAX_BATCH', '15'))  # ~105s + overhead = safe for 15min

# OpenAI GPT Image (tiered IPM limits — default spacing avoids Tier-1 throttling)
GPT_IMAGE_MAX_BATCH = int(os.getenv('GPT_IMAGE_MAX_BATCH', '4'))
OPENAI_IMAGE_RATE_DELAY = float(os.getenv('OPENAI_IMAGE_RATE_DELAY', '13'))
OPENAI_IMAGES_GENERATIONS_URL = 'https://api.openai.com/v1/images/generations'
DEFAULT_OPENAI_IMAGE_MODEL = 'gpt-image-2'

# Default max images if not specified
DEFAULT_MAX_IMAGES = 5

# Rate limiting to avoid hitting Google API quotas
# Gemini has generous limits but we still want to be respectful
RATE_LIMIT_DELAY = 2  # Optimized to 2 seconds based on performance testing (was 5s)

# Safety buffer before Lambda timeout (seconds)
TIMEOUT_SAFETY_BUFFER = 60  # Stop processing 60 seconds before timeout



# Retry configuration for failed image generations
MAX_RETRIES = 2  # Retry failed generations up to 2 times
RETRY_DELAY = 3  # Wait 3 seconds between retries

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
    logger.info("🔍 Attempting to retrieve Google API key...")
    try:
        # Try Secrets Manager first
        logger.info("📡 Calling get_secret('aurora/google-api-key')...")
        google_secret = get_secret("aurora/google-api-key")
        logger.info(f"📦 Secret retrieved: {type(google_secret)}, keys: {list(google_secret.keys()) if isinstance(google_secret, dict) else 'N/A'}")
        api_key = google_secret.get('api_key')
        logger.info(f"🔑 api_key value: {'<present>' if api_key else '<missing>'}")
        if api_key:
            logger.info("✅ Retrieved Google API key from Secrets Manager")
            return api_key
        else:
            logger.warning("⚠️  api_key field is empty in secret")
    except Exception as e:
        logger.error(f"⚠️  Failed to retrieve from Secrets Manager: {type(e).__name__}: {e}", exc_info=True)
    
    # Fallback to environment variable
    logger.info("🔍 Checking environment variable GOOGLE_API_KEY...")
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        logger.info("✅ Using Google API key from environment variable")
        return api_key
    
    logger.error("❌ No Google API key found in Secrets Manager or environment")
    return None


def get_openai_api_key() -> str | None:
    """OpenAI API key from Secrets Manager (aurora/openai-api-key) or OPENAI_API_KEY."""
    try:
        secret = get_secret('aurora/openai-api-key')
        api_key = secret.get('api_key') if isinstance(secret, dict) else None
        if api_key:
            logger.info('✅ Retrieved OpenAI API key from Secrets Manager')
            return api_key
    except Exception as e:
        logger.warning(f'⚠️ OpenAI secret not loaded: {type(e).__name__}: {e}')
    env_key = os.getenv('OPENAI_API_KEY')
    if env_key:
        logger.info('✅ Using OpenAI API key from environment')
        return env_key
    return None


def is_openai_image_model(image_model: str) -> bool:
    """True when image_model selects OpenAI Images (e.g. gpt-image-2)."""
    return 'gpt-image' in (image_model or '').lower()


def get_google_service_account() -> Dict[str, Any]:
    """Get Google Service Account credentials from Secrets Manager."""
    logger.info("🔍 Attempting to retrieve Google Service Account...")
    try:
        # Try Secrets Manager first
        logger.info("📡 Calling get_secret('aurora/google-service-account')...")
        service_account_secret = get_secret("aurora/google-service-account")
        logger.info(f"📦 Secret retrieved: {type(service_account_secret)}")
        if service_account_secret:
            logger.info("✅ Retrieved Google Service Account from Secrets Manager")
            return service_account_secret
    except Exception as e:
        logger.error(f"⚠️  Failed to retrieve from Secrets Manager: {type(e).__name__}: {e}", exc_info=True)
    
    logger.error("❌ No Google Service Account found in Secrets Manager")
    return None


# ============================================================================
# IMAGE GENERATION
# ============================================================================

def normalize_image_locale(lang: Optional[str]) -> str:
    """Default Spanish for on-image text; English only when course_language is explicitly English."""
    if lang is None:
        return 'es'
    s = str(lang).strip().lower()
    if not s:
        return 'es'
    if s.startswith('en') or 'english' in s or 'inglés' in s or 'ingles' in s:
        return 'en'
    return 'es'


def optimize_prompt_for_image_generation(prompt_text: str, image_locale: str = 'es') -> str:
    """
    Optimize prompt for Gemini/OpenAI image APIs.

    Preserves detailed enhanced_prompts from Visual Planner; enforces on-image text
    language to match the course (Spanish vs English).
    """
    loc = normalize_image_locale(image_locale)

    if loc == 'es':
        lang_prefix = (
            '⚠️ INSTRUCCIÓN CRÍTICA: TODO EL TEXTO LEGIBLE EN LA IMAGEN DEBE ESTAR EN ESPAÑOL. '
            'Rótulos, títulos, anotaciones, botones y leyendas en español (salvo nombres propios de productos/APIs '
            'que deban mantenerse como marca). No sustituir por inglés salvo esos casos.\n\n'
        )
        detailed_prompt_indicators = [
            'typography:', 'exact on-canvas text', 'layout:', 'colors and styling:',
            'verification:', 'style notes:', 'alignment and spacing:', 'font:',
            'spell exactly', 'professional illustration', '#ffffff', '1920x1080',
            'tipografía:', 'texto exacto', 'disposición:', 'colores y estilo:',
        ]
        is_detailed_prompt = any(indicator in prompt_text.lower() for indicator in detailed_prompt_indicators)
        if is_detailed_prompt:
            logger.info('📝 Detected detailed enhanced_prompt — preserving with Spanish on-image text enforcement')
            return f'{lang_prefix}{prompt_text}'

        logger.info('📝 Simple description — applying Spanish template optimization')
        text_heavy_keywords = [
            'tabla', 'screenshot', 'captura', 'texto', 'fragmento de código', 'terminal',
            'línea de comandos', 'hoja de cálculo', 'documento', 'formulario',
            'table', 'screenshot', 'text', 'code snippet', 'terminal',
            'command line', 'spreadsheet', 'document', 'form',
        ]
        is_text_heavy = any(keyword in prompt_text.lower() for keyword in text_heavy_keywords)
        if is_text_heavy:
            prefix = 'Crea una ilustración conceptual profesional EN ESPAÑOL que represente: '
            suffix = '. Estilo: limpio, moderno, minimalista, basado en iconos. Todas las etiquetas y textos visibles en español.'
        else:
            prefix = 'Crea una ilustración educativa profesional EN ESPAÑOL: '
            suffix = '. Estilo: limpio, moderno, alta calidad, bien compuesto. Todo texto, etiquetas y anotaciones en español.'
        return f'{lang_prefix}{prefix}{prompt_text}{suffix}'

    # English (default)
    english_prefix = (
        '⚠️ CRITICAL INSTRUCTION: ALL TEXT RENDERED IN THE IMAGE MUST BE IN ENGLISH. '
        'Labels, titles, annotations, and UI copy in English unless the lesson explicitly requires another language.\n\n'
    )
    detailed_prompt_indicators = [
        'typography:', 'exact on-canvas text', 'layout:', 'colors and styling:',
        'verification:', 'style notes:', 'alignment and spacing:', 'font:',
        'spell exactly', 'professional illustration', '#ffffff', '1920x1080',
    ]
    is_detailed_prompt = any(indicator in prompt_text.lower() for indicator in detailed_prompt_indicators)
    if is_detailed_prompt:
        logger.info('📝 Detected detailed enhanced_prompt — preserving with English enforcement')
        return f'{english_prefix}{prompt_text}'

    logger.info('📝 Simple description detected — applying English template optimization')
    text_heavy_keywords = ['table', 'screenshot', 'text', 'code snippet', 'terminal',
                          'command line', 'spreadsheet', 'document', 'form']
    is_text_heavy = any(keyword in prompt_text.lower() for keyword in text_heavy_keywords)
    if is_text_heavy:
        prefix = 'Create a professional conceptual illustration IN ENGLISH representing: '
        suffix = '. Style: clean, modern, minimalist, icon-based design. All labels and text in English.'
    else:
        prefix = 'Create a professional educational illustration IN ENGLISH: '
        suffix = '. Style: clean, modern, high-quality, well-composed. All text, labels, and annotations in English.'
    return f'{english_prefix}{prefix}{prompt_text}{suffix}'


def generate_image_gemini(model, prompt_id: str, prompt_text: str, retry_count: int = 0, *, image_locale: str = 'es') -> tuple:
    """
    Generate an image using Gemini with optimized prompts and retry logic.

    Args:
        model: Gemini GenerativeModel instance
        prompt_id: Unique identifier for the prompt
        prompt_text: Detailed description/prompt for image generation
        retry_count: Current retry attempt (0 = first attempt)

    Returns:
        tuple: (success: bool, image_bytes: bytes or None, error: str or None)
    """
    try:
        logger.info(f"Generating image for prompt: {prompt_id} (attempt {retry_count + 1}/{MAX_RETRIES + 1})")
        logger.info(f"Prompt text length: {len(prompt_text)} characters")
        logger.info(f"Prompt preview: {prompt_text[:150]}{'...' if len(prompt_text) > 150 else ''}")

        optimized_prompt = optimize_prompt_for_image_generation(prompt_text, image_locale)
        logger.info(f"Optimized prompt: {optimized_prompt[:200]}{'...' if len(optimized_prompt) > 200 else ''}")
        
        # Configure safety settings to be more permissive for educational content
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH"
            }
        ]
        
        # Generate with safety settings
        response = model.generate_content(
            optimized_prompt,
            safety_settings=safety_settings
        )
        logger.info(f"Gemini response type: {type(response)}")
        
        # Log prompt_feedback for debugging (safety filters, blocking reasons)
        if hasattr(response, 'prompt_feedback'):
            logger.info(f"Prompt feedback: {response.prompt_feedback}")
            
            # Check if blocked by safety filters
            if hasattr(response.prompt_feedback, 'block_reason'):
                block_reason = response.prompt_feedback.block_reason
                if block_reason and block_reason != 0:  # 0 = not blocked
                    logger.warning(f"⚠️ Content blocked by safety filter: {block_reason}")
                    
                    # If blocked and we have retries left, try with simplified prompt
                    if retry_count < MAX_RETRIES:
                        logger.info(f"Retrying with simplified prompt...")
                        time.sleep(RETRY_DELAY)
                        # Use original prompt without optimization
                        return generate_image_gemini(
                            model, prompt_id, f"Simple illustration: {prompt_text[:100]}",
                            retry_count + 1, image_locale=image_locale,
                        )
                    
                    return False, None, f"Blocked by safety filter: {block_reason}"
        
        # Process the response
        if response and hasattr(response, 'candidates'):
            logger.info(f"Found {len(response.candidates)} candidates")
            for candidate_idx, candidate in enumerate(response.candidates):
                logger.info(f"Processing candidate {candidate_idx}")
                
                # Log finish_reason and safety ratings for debugging
                if hasattr(candidate, 'finish_reason'):
                    logger.info(f"Candidate finish_reason: {candidate.finish_reason}")
                if hasattr(candidate, 'safety_ratings'):
                    logger.info(f"Candidate safety_ratings: {candidate.safety_ratings}")
                    
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    logger.info(f"Candidate has {len(candidate.content.parts)} parts")
                    for part_idx, part in enumerate(candidate.content.parts):
                        logger.info(f"Processing part {part_idx}: {type(part)}")
                        
                        # Check for inline_data (image) first
                        if hasattr(part, 'inline_data'):
                            logger.info(f"Found inline_data in part {part_idx}")
                            image_data = part.inline_data
                            image_bytes = image_data.data
                            mime_type = image_data.mime_type

                            logger.info(f"Image data type: {type(image_bytes)}, size: {len(image_bytes) if hasattr(image_bytes, '__len__') else 'unknown'}")
                            logger.info(f"MIME type: {mime_type}")

                            # Check if we have image data
                            if not image_bytes or len(image_bytes) == 0:
                                logger.info(f"Empty image data for {prompt_id}")
                                continue  # Skip this part, check others

                            # Additional validation
                            if len(image_bytes) < 1000:  # Reasonable minimum size for an image
                                logger.info(f"Image data too small ({len(image_bytes)} bytes), skipping")
                                continue

                            # Decode base64 if needed
                            if isinstance(image_bytes, str):
                                logger.info("Decoding base64 image data")
                                image_bytes = base64.b64decode(image_bytes)

                            # Try to create PIL Image
                            logger.info("Creating PIL Image")
                            try:
                                image = Image.open(BytesIO(image_bytes))
                                logger.info(f"Success! Image size: {image.size}, mode: {image.mode}, format: {image.format}")
                                return True, image_bytes, None
                            except Exception as pil_error:
                                logger.info(f"PIL Error: {pil_error}")

                                # Inspect the bytes
                                first_bytes = image_bytes[:20] if len(image_bytes) > 20 else image_bytes
                                logger.info(f"First 20 bytes: {first_bytes}")

                                # Try different formats
                                if image_bytes.startswith(b'\xff\xd8\xff'):
                                    logger.info("Detected JPEG signature")
                                elif image_bytes.startswith(b'\x89PNG'):
                                    logger.info("Detected PNG signature")
                                elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:20]:
                                    logger.info("Detected WebP signature")
                                else:
                                    logger.info("Unknown format signature")

                                continue  # Try next part

                        # Check for text parts (but don't skip image processing)
                        if hasattr(part, 'text'):
                            text_content = part.text
                            logger.info(f"Found text part: {text_content[:200]}...")

                            # Check if this is an error message
                            if any(keyword in text_content.lower() for keyword in ['cannot', 'unable', 'error', 'sorry', 'failed', 'not available']):
                                logger.info(f"Gemini returned error: {text_content[:100]}...")
                                return False, None, f"Gemini error: {text_content[:100]}"
                            # Don't continue here - let it check other parts for images
                                
                    if not any(hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data and len(part.inline_data.data) >= 1000 for part in candidate.content.parts):
                        logger.warning(f"⚠️ No valid image data found in any part for {prompt_id}")
                        
                        # Retry with different approach if we have retries left
                        if retry_count < MAX_RETRIES:
                            logger.info(f"🔄 Retrying image generation (attempt {retry_count + 2}/{MAX_RETRIES + 1})...")
                            time.sleep(RETRY_DELAY)
                            # Try with a more direct, simplified prompt
                            simplified_prompt = f"Professional illustration: {prompt_text[:150]}"
                            return generate_image_gemini(
                                model, prompt_id, simplified_prompt, retry_count + 1, image_locale=image_locale,
                            )
                        
                        return False, None, "No valid image data found in any part"
                else:
                    logger.info(f"❌ Candidate {candidate_idx} has no valid content")
                    return False, None, "Candidate has no valid content"
            else:
                logger.info("No candidates with image data found")
                return False, None, "No candidates with image data found"
        else:
            logger.info(f"Unexpected response format: {type(response)}")
            if hasattr(response, 'text'):
                logger.info(f"Response text: {response.text}")
            return False, None, f"Unexpected response format: {type(response)}"

    except Exception as e:
        logger.error(f"❌ Error generating image for {prompt_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Retry on exception if we have retries left
        if retry_count < MAX_RETRIES:
            logger.info(f"🔄 Retrying after exception (attempt {retry_count + 2}/{MAX_RETRIES + 1})...")
            time.sleep(RETRY_DELAY)
            return generate_image_gemini(model, prompt_id, prompt_text, retry_count + 1, image_locale=image_locale)
        
        return False, None, str(e)




def generate_image_openai(
    api_key: str,
    model_id: str,
    prompt_id: str,
    prompt_text: str,
    retry_count: int = 0,
    *,
    image_locale: str = 'es',
) -> tuple:
    """Generate one image via OpenAI Images API (e.g. gpt-image-2)."""
    try:
        optimized_prompt = optimize_prompt_for_image_generation(prompt_text, image_locale)
        if len(optimized_prompt) > 32000:
            optimized_prompt = optimized_prompt[:32000]

        payload: Dict[str, Any] = {
            'model': model_id,
            'prompt': optimized_prompt,
            'n': 1,
            'size': '1024x1024',
        }
        # Note: do not send response_format — gpt-image-* rejects it (400 unknown_parameter).
        # Response may include either data[0].b64_json or data[0].url depending on model/version.
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            OPENAI_IMAGES_GENERATIONS_URL,
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        logger.info(f'OpenAI Images request model={model_id} prompt_id={prompt_id}')
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode('utf-8')
        data = json.loads(raw)
        items = data.get('data') or []
        if not items:
            return False, None, 'OpenAI response missing data[]'

        b64 = items[0].get('b64_json')
        if b64:
            image_bytes = base64.b64decode(b64)
            if image_bytes and len(image_bytes) >= 100:
                return True, image_bytes, None
            return False, None, 'Decoded image too small'

        url = items[0].get('url')
        if url:
            with urllib.request.urlopen(url, timeout=120) as url_resp:
                image_bytes = url_resp.read()
            if image_bytes and len(image_bytes) >= 100:
                return True, image_bytes, None
            return False, None, 'Downloaded image too small'

        return False, None, 'No b64_json or url in OpenAI response'

    except urllib.error.HTTPError as e:
        err_txt = e.read().decode('utf-8', errors='replace')
        logger.error(f'OpenAI HTTP {e.code} for {prompt_id}: {err_txt[:800]}')
        if retry_count < MAX_RETRIES and e.code in (429, 500, 502, 503):
            time.sleep(RETRY_DELAY * (retry_count + 1))
            return generate_image_openai(
                api_key, model_id, prompt_id, prompt_text, retry_count + 1, image_locale=image_locale,
            )
        return False, None, f'OpenAI HTTP {e.code}: {err_txt[:400]}'

    except Exception as e:
        logger.error(f'❌ OpenAI image generation error for {prompt_id}: {e}', exc_info=True)
        if retry_count < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return generate_image_openai(
                api_key, model_id, prompt_id, prompt_text, retry_count + 1, image_locale=image_locale,
            )
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
        
        logger.info(f"✅ Saved to S3: {key}")
        return True
        
    except Exception as e:
        logger.info(f"❌ Error saving to S3: {e}")
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
        logger.info("=== Starting Image Generation Lambda ===")
        
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
        
        # DEBUG: Log raw image_model parameter before processing
        raw_image_model = exec_input.get('image_model')
        logger.info(f"🔍 DEBUG - Raw image_model from input: {repr(raw_image_model)} (type: {type(raw_image_model).__name__})")
        logger.info(f"🔍 DEBUG - DEFAULT_IMAGE_MODEL: {DEFAULT_IMAGE_MODEL}")
        logger.info(f"🔍 DEBUG - GEMINI_MODEL: {GEMINI_MODEL}")
        
        image_model = (raw_image_model or DEFAULT_IMAGE_MODEL).lower()  # Safe None handling
        logger.info(f"🔍 DEBUG - Final image_model after processing: {image_model}")
        use_openai = is_openai_image_model(image_model)

        course_language_norm = normalize_image_locale(exec_input.get('course_language'))
        logger.info(f"🌐 course_language for image prompts: {course_language_norm}")

        rate_limit_override = exec_input.get('rate_limit_override')  # For performance testing

        # Override rate limit if specified (for testing)
        global RATE_LIMIT_DELAY
        if rate_limit_override is not None:
            original_rate = RATE_LIMIT_DELAY
            RATE_LIMIT_DELAY = rate_limit_override
            logger.info(f"⚙️  Rate limit overridden: {original_rate}s → {RATE_LIMIT_DELAY}s (TEST MODE)")
        elif use_openai:
            RATE_LIMIT_DELAY = OPENAI_IMAGE_RATE_DELAY
            logger.info(f"⚙️  OpenAI GPT Image: rate limit spacing {RATE_LIMIT_DELAY}s")
        
        # Get Lambda timeout information for dynamic batching
        try:
            timeout_ms = context.get_remaining_time_in_millis()
            logger.info(f"⏱️  Lambda timeout: {timeout_ms/1000:.1f}s available, Safety buffer: {TIMEOUT_SAFETY_BUFFER}s")
        except Exception as e:
            timeout_ms = 900000  # Default 15 minutes
            logger.warning(f"⚠️  Could not get remaining time, using default: {timeout_ms/1000}s")
        
        logger.info(f"Bucket: {course_bucket}")
        logger.info(f"Project: {project_folder}")
        logger.info(f"Prompts provided: {len(prompts_from_input) if prompts_from_input else 0}")
        logger.info(f"Prompts prefix: {prompts_prefix}")
        logger.info(f"Max images: {requested_max_images}")
        logger.info(f"Image Model: {image_model}")
        logger.info(f"Rate Limit: {RATE_LIMIT_DELAY}s")
        
        # Validate required parameters
        if not course_bucket or not project_folder:
            logger.info("❌ Missing required parameters")
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
            logger.info(f"📂 Reading prompts from S3: {prompts_prefix}")
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
                    logger.info(f"📄 Found {len(prompt_files)} prompt files in S3")
                    
                    # Read each prompt file
                    for prompt_key in prompt_files:
                        try:
                            prompt_obj = s3_client.get_object(Bucket=course_bucket, Key=prompt_key)
                            prompt_data = json.loads(prompt_obj['Body'].read().decode('utf-8'))
                            
                            # Prefer enhanced_prompt over description for better quality
                            # enhanced_prompt includes exact text, typography, and detailed specifications
                            prompt_text = prompt_data.get('enhanced_prompt') or prompt_data.get('description', '')
                            
                            # Only include if it has a prompt text
                            if prompt_text:
                                prompts_from_input.append({
                                    'id': prompt_data.get('id'),
                                    'description': prompt_text,  # Use enhanced prompt as description
                                    's3_key': prompt_key
                                })
                        except Exception as e:
                            logger.info(f"⚠️  Failed to read prompt {prompt_key}: {e}")
                    
                    logger.info(f"✅ Loaded {len(prompts_from_input)} prompts with descriptions from S3")
                else:
                    logger.info(f"⚠️  No prompt files found at {full_prefix}")
            except Exception as e:
                logger.info(f"❌ Error reading prompts from S3: {e}")
        
        # Initialize the selected model (Gemini or OpenAI Images API)
        model = None
        generate_func = None

        if use_openai:
            logger.info(f"🤖 Initializing OpenAI Images for model: {image_model}...")
            openai_api_key = get_openai_api_key()
            if not openai_api_key:
                logger.info("⚠️  OpenAI API key not available; skipping image generation")
                return {
                    "statusCode": 200,
                    "message": "OpenAI API key not available; skipped image generation",
                    "generated_images": [],
                    "bucket": course_bucket,
                    "project_folder": project_folder,
                }
            openai_model_id = (raw_image_model or DEFAULT_OPENAI_IMAGE_MODEL).strip()
            if not openai_model_id:
                openai_model_id = DEFAULT_OPENAI_IMAGE_MODEL

            def openai_wrapped(_m, pid: str, txt: str):
                return generate_image_openai(
                    openai_api_key, openai_model_id, pid, txt, image_locale=course_language_norm,
                )

            generate_func = openai_wrapped
            logger.info(f"✅ OpenAI Images ready (model_id={openai_model_id})")
        else:
            logger.info(f"🤖 Initializing Gemini with model: {image_model}...")

            if genai is None:
                logger.info("⚠️  genai library not available; skipping image generation")
                return {
                    "statusCode": 200,
                    "message": "genai library not available; skipped image generation",
                    "generated_images": [],
                    "bucket": course_bucket,
                    "project_folder": project_folder,
                }

            google_api_key = get_google_api_key()
            if not google_api_key:
                logger.info("⚠️  Google API key not available; skipping image generation")
                return {
                    "statusCode": 200,
                    "message": "Google API key not available; skipped image generation",
                    "generated_images": [],
                    "bucket": course_bucket,
                    "project_folder": project_folder,
                }

            try:
                genai.configure(api_key=google_api_key)
                model_to_use = image_model if image_model else GEMINI_MODEL
                model = genai.GenerativeModel(model_to_use)
                generate_func = partial(generate_image_gemini, image_locale=course_language_norm)
                logger.info(f"✅ Initialized Gemini model: {model_to_use}")
            except Exception as e:
                logger.info(f"❌ Failed to configure Gemini: {e}")
                return {
                    "statusCode": 500,
                    "error": f"Failed to configure Gemini: {e}",
                    "generated_images": [],
                }
        
        generated_images = []
        
        # Handle empty prompts list
        if not prompts_from_input or len(prompts_from_input) == 0:
            logger.info("⚠️  No prompts to process")
            
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
                logger.info(f"Error listing lessons: {e}")
            
            return {
                "statusCode": 200,
                "message": "No visual prompts to process",
                "generated_images": [],
                "bucket": course_bucket,
                "project_folder": project_folder,
                "lesson_keys": lesson_keys,
                "image_mappings": {}
            }
        
        # Determine how many to process with start_index support
        start_index = exec_input.get('start_index', 0)
        num_prompts = len(prompts_from_input)
        
        # REPAIR MODE: Filter to only missing images
        repair_mode = exec_input.get('repair_mode', False)
        missing_image_ids = exec_input.get('missing_image_ids', [])
        
        if repair_mode and missing_image_ids:
            logger.info(f"🔧 REPAIR MODE ENABLED")
            logger.info(f"   Filtering to {len(missing_image_ids)} missing images")
            
            # Convert to set for faster lookup
            missing_set = set(missing_image_ids)
            
            # Filter prompts to only missing ones
            original_count = len(prompts_from_input)
            prompts_from_input = [
                p for p in prompts_from_input
                if str(p.get('id', '')) in missing_set
            ]
            filtered_count = len(prompts_from_input)
            
            logger.info(f"   Filtered {original_count} → {filtered_count} prompts")
            num_prompts = filtered_count
        
        # Apply start_index offset (only if not in repair mode)
        elif start_index > 0:
            logger.info(f"📍 Starting from index {start_index}")
            prompts_from_input = prompts_from_input[start_index:]
            num_prompts = len(prompts_from_input)
        
        # Apply model-specific batch limits to prevent Lambda timeout
        if use_openai:
            model_max_batch = GPT_IMAGE_MAX_BATCH
            logger.info(f"⚙️  OpenAI GPT Image: limiting batch to {model_max_batch} images")
        elif 'gemini-3' in image_model.lower():
            model_max_batch = GEMINI3_MAX_BATCH
            logger.info(f"⚙️  Gemini 3 Pro detected: limiting batch to {model_max_batch} images (slower model)")
        else:
            model_max_batch = GEMINI25_MAX_BATCH
            logger.info(f"⚙️  Gemini 2.5 Flash: batch limit {model_max_batch} images")
        
        effective_max = min(num_prompts, model_max_batch, BACKEND_MAX)
        
        if num_prompts > BACKEND_MAX:
            logger.info(f"⚠️  Truncating from {num_prompts} to backend cap {BACKEND_MAX}")
            if not repair_mode:
                logger.info(f"📊 Processing prompts {start_index} to {start_index + BACKEND_MAX - 1}")
        
        prompts_to_process = prompts_from_input[:effective_max]
        logger.info(f"Processing {len(prompts_to_process)} prompts")
        
        # Track detailed statistics
        failed_images = []
        successful_images = []
        skipped_images = []
        
        # Track processing start time for timeout monitoring
        processing_start_time = time.time()
        processed_count = 0
        stopped_due_to_timeout = False
        
        # Process each prompt
        for idx, prompt_obj in enumerate(prompts_to_process, start=1):
            # Check remaining time before processing each image
            elapsed_time = time.time() - processing_start_time
            try:
                remaining_ms = context.get_remaining_time_in_millis()
                remaining_seconds = remaining_ms / 1000
            except:
                # Fallback calculation if context not available
                remaining_seconds = timeout_ms / 1000 - elapsed_time
            
            # Check if we should stop (safety buffer + estimated time for next image)
            estimated_next_image_time = 50 if use_openai else 15  # OpenAI gpt-image often slower per image
            if remaining_seconds < (TIMEOUT_SAFETY_BUFFER + estimated_next_image_time):
                logger.warning(f"⏱️  TIMEOUT APPROACHING - Stopping after {processed_count}/{len(prompts_to_process)} images")
                logger.warning(f"   Elapsed: {elapsed_time:.1f}s, Remaining: {remaining_seconds:.1f}s, Buffer needed: {TIMEOUT_SAFETY_BUFFER + estimated_next_image_time}s")
                stopped_due_to_timeout = True
                break
            
            prompt_id = str(prompt_obj.get('id', f'prompt-{idx}'))
            prompt_text = prompt_obj.get('description', '')
            
            logger.info(f"\n[{idx}/{len(prompts_to_process)}] Processing: {prompt_id}")
            
            # Skip if no description
            if not prompt_text:
                logger.warning(f"⚠️  Skipping {prompt_id}: no description")
                error_detail = {
                    'id': prompt_id,
                    'status': 'skipped',
                    'error': 'no description',
                    'timestamp': datetime.utcnow().isoformat()
                }
                generated_images.append(error_detail)
                skipped_images.append(error_detail)
                continue
            
                # Check if image already exists (Resume capability)
                image_filename = f"{prompt_id}.png"
                images_key = f"{project_folder}/images/{image_filename}"
                
                # OPTIMIZATION: Check HEAD object to avoid re-generating existing images
                try:
                    s3_client.head_object(Bucket=course_bucket, Key=images_key)
                    logger.info(f"⏩ Image already exists: {images_key} (Skipping generation)")
                    
                    success_detail = {
                        'id': prompt_id,
                        'filename': image_filename,
                        's3_key': images_key,
                        'status': 'ok',
                        'timestamp': datetime.utcnow().isoformat(),
                        'skipped': True  # Mark as skipped/existing
                    }
                    generated_images.append(success_detail)
                    successful_images.append(prompt_id)
                    processed_count += 1
                    continue
                except Exception:
                    # Object does not exist, proceed with generation
                    pass

            try:
                # Generate image using the selected model
                logger.info(f"📸 Generating image for {prompt_id} using {image_model}")
                success, image_bytes, error = generate_func(model, prompt_id, prompt_text)
                
                if success and image_bytes:
                    # Save to S3
                    image_filename = f"{prompt_id}.png"
                    images_key = f"{project_folder}/images/{image_filename}"
                    
                    logger.info(f"💾 Saving to S3: {images_key}")
                    if save_image_to_s3(s3_client, course_bucket, images_key, image_bytes):
                        success_detail = {
                            'id': prompt_id,
                            'filename': image_filename,
                            's3_key': images_key,
                            'status': 'ok',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        generated_images.append(success_detail)
                        successful_images.append(prompt_id)
                        logger.info(f"✅ Generated: {images_key}")
                        processed_count += 1
                    else:
                        error_detail = {
                            'id': prompt_id,
                            'status': 'failed',
                            'error': 'failed to save to S3',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        generated_images.append(error_detail)
                        failed_images.append(error_detail)
                        logger.error(f"❌ S3 Save failed for {prompt_id}")
                else:
                    error_detail = {
                        'id': prompt_id,
                        'status': 'failed',
                        'error': error or 'unknown error',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    generated_images.append(error_detail)
                    failed_images.append(error_detail)
                    logger.error(f"❌ Generation failed for {prompt_id}: {error}")
                    
            except Exception as e:
                error_detail = {
                    'id': prompt_id,
                    'status': 'failed',
                    'error': f'Exception: {str(e)}',
                    'error_type': type(e).__name__,
                    'timestamp': datetime.utcnow().isoformat()
                }
                generated_images.append(error_detail)
                failed_images.append(error_detail)
                logger.error(f"❌ Exception processing {prompt_id}: {e}", exc_info=True)
            
            # Rate limiting delay
            if idx < len(prompts_to_process):
                logger.info(f"⏳ Waiting {RATE_LIMIT_DELAY}s before next request...")
                time.sleep(RATE_LIMIT_DELAY)
        
        # Build image mappings for BookBuilder
        # NEW FORMAT: Use image ID as key to avoid Step Functions size limits
        # Structure: { "image_id": { "s3_key": "path", "description": "text" } }
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
                logger.info(f"Found {len(lesson_keys)} lesson files")
        except Exception as e:
            logger.info(f"Error listing lessons: {e}")
        
        # Create mappings for each generated image
        # Build a lookup table for descriptions from prompts
        prompts_lookup = {p.get('id'): p.get('description', '') for p in prompts_from_input if p.get('id')}
        
        for img_data in generated_images:
            if img_data.get('status') == 'ok' and 's3_key' in img_data:
                img_id = img_data['id']
                # Get description from prompts_lookup
                description = prompts_lookup.get(img_id, '')
                # NEW FORMAT: Use ID as key, store s3_key and description as values
                image_mappings[img_id] = {
                    's3_key': img_data['s3_key'],
                    'description': description if description else ''
                }
        
        # Also include mappings for existing images in the project
        # CRITICAL: Only scan if we didn't process new prompts.
        # In batch processing, scanning all images every time causes O(N^2) data growth
        # and hits Step Functions 256KB payload limit.
        images_prefix = f"{project_folder}/images/"
        prompts_prefix = f"{project_folder}/prompts/"
        
        # Only scan if specifically requested or if we are not in a generation batch
        scan_all = exec_input.get('scan_all_images', False)
        
        if scan_all or not prompts_to_process:
            try:
                # First, load all prompt files to get descriptions
                prompts_dict = {}
                try:
                    prompts_response = s3_client.list_objects_v2(
                        Bucket=course_bucket,
                        Prefix=prompts_prefix
                    )
                    if 'Contents' in prompts_response:
                        for prompt_obj in prompts_response['Contents']:
                            if prompt_obj['Key'].endswith('.json'):
                                try:
                                    prompt_data_response = s3_client.get_object(Bucket=course_bucket, Key=prompt_obj['Key'])
                                    prompt_json = json.loads(prompt_data_response['Body'].read().decode('utf-8'))
                                    prompt_id = prompt_json.get('id', '')
                                    prompt_desc = prompt_json.get('description', '')
                                    if prompt_id and prompt_desc:
                                        prompts_dict[prompt_id] = prompt_desc
                                except Exception as e:
                                    logger.info(f"Could not load prompt {prompt_obj['Key']}: {e}")
                except Exception as e:
                    logger.info(f"Could not scan prompts folder: {e}")
                
                # Now scan images and create mappings with descriptions
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
                            
                            # Only add if not already in mappings (newly generated take precedence)
                            if img_id not in image_mappings:
                                # Get description from prompts_dict
                                description = prompts_dict.get(img_id, '')
                                image_mappings[img_id] = {
                                    's3_key': img_key,
                                    'description': description if description else ''
                                }
                                logger.info(f"✅ Included existing image mapping: {img_id} -> {img_key}")
            except Exception as e:
                logger.info(f"Warning: Could not scan existing images: {e}")
        
        # Summary with detailed statistics
        successful_count = len(successful_images)
        failed_count = len(failed_images)
        skipped_count = len(skipped_images)
        total_processed = processed_count
        
        # Calculate remaining prompts (those not processed due to timeout)
        remaining_prompts = []
        if stopped_due_to_timeout and processed_count < len(prompts_to_process):
            remaining_prompts = prompts_to_process[processed_count:]
            logger.warning(f"⏱️  TIMEOUT: {len(remaining_prompts)} prompts remaining for next batch")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 EXECUTION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"✅ Successful: {successful_count}/{len(prompts_to_process)}")
        logger.info(f"❌ Failed:     {failed_count}/{len(prompts_to_process)}")
        logger.info(f"⏭️  Skipped:    {skipped_count}/{len(prompts_to_process)}")
        if remaining_prompts:
            logger.info(f"⏱️  Remaining:  {len(remaining_prompts)}/{len(prompts_to_process)} (timeout)")
        logger.info(f"{'='*60}")
        
        if failed_images:
            logger.warning(f"\n❌ FAILED IMAGES ({failed_count}):")
            for fail in failed_images:
                logger.warning(f"   - {fail['id']}: {fail['error']}")
        
        if successful_images:
            logger.info(f"\n✅ SUCCESSFUL IMAGES ({successful_count}):")
            for img_id in successful_images[:10]:  # Show first 10
                logger.info(f"   - {img_id}")
            if successful_count > 10:
                logger.info(f"   ... and {successful_count - 10} more")
        
        logger.info(f"\n{'='*60}\n")
        
        # Determine status code based on results
        status_code = 200 if failed_count == 0 else 207  # 207 = Multi-Status (partial success)
        
        return {
            "statusCode": status_code,
            "message": f"Generated {successful_count}/{total_processed} images successfully",
            "generated_images": generated_images,
            "bucket": course_bucket,
            "project_folder": project_folder,
            "lesson_keys": lesson_keys,
            "image_mappings": image_mappings,
            "remaining_prompts": remaining_prompts,  # NEW: For automatic resume
            "statistics": {
                "total_requested": len(prompts_to_process),
                "total_processed": total_processed,
                "successful": successful_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "remaining": len(remaining_prompts),  # NEW: Count of unprocessed prompts
                "success_rate": f"{(successful_count/total_processed*100):.1f}%" if total_processed > 0 else "0%",
                "timeout_stopped": stopped_due_to_timeout  # NEW: Flag indicating if stopped early
            },
            "failed_details": failed_images if failed_images else []
        }
        
    except Exception as e:
        logger.error(f"❌ FATAL ERROR in lambda_handler: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }


if __name__ == '__main__':
    logger.info("Images Generation Lambda")
    logger.info("Use SAM CLI to test: sam local invoke ImagesGen -e test-event.json")
