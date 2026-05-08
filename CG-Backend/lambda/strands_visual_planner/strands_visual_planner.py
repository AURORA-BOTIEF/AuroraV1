#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strands Visual Planner Lambda - OPTIMIZED VERSION
==================================================
Extracts [VISUAL: ...] tags from multiple lesson contents and creates detailed
image generation prompts using a SINGLE LLM agent call per batch.

Modern LLMs (Sonnet 4.5, GPT-5) can easily process all visual tags from a module
in a single API call, drastically reducing cost and improving speed.

OPTIMIZATION:
- Previous: 2 API calls per lesson (classify + enhance) = ~60 calls for 30 lessons
- Optimized: 1 API call per batch (processes multiple lessons) = ~9 calls for 42 lessons

Expected event format:
{
    "lesson_keys": [
        {
            "s3_key": "project/lessons/01-01-lesson.md",
            "module_number": 1,
            "lesson_number": 1,
            "lesson_title": "Introduction to Docker"
        },
        ...
    ],
    "course_bucket": "bucket-name",
    "project_folder": "project-name",
    "model_provider": "bedrock|openai"
}
"""

import os
import json
import re
import random
import time
import boto3
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from botocore.config import Config
from botocore.exceptions import ClientError

# Configure boto3 with extended timeouts for long-running LLM calls
boto_config = Config(
    read_timeout=600,  # 10 minutes read timeout
    connect_timeout=60,  # 1 minute connection timeout
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

# Initialize S3 and Bedrock clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=boto_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # Changed from Sonnet to Haiku for performance
DEFAULT_OPENAI_MODEL = "gpt-5"

BEDROCK_APP_MAX_ATTEMPTS = max(1, int(os.getenv("BEDROCK_APP_MAX_ATTEMPTS", "5")))


def _bedrock_error_is_transient(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = (exc.response.get("Error") or {}).get("Code", "") or ""
        return code in (
            "ThrottlingException",
            "TooManyRequestsException",
            "ServiceUnavailableException",
            "ModelTimeoutException",
            "InternalServerException",
        )
    msg = str(exc)
    return any(
        x in msg
        for x in (
            "ThrottlingException",
            "TooManyRequestsException",
            "ServiceUnavailableException",
            "ModelTimeoutException",
            "InternalServerException",
            "unable to process your request",
        )
    )


def _sleep_before_bedrock_retry(attempt_index: int, base: float = 3.0, cap: float = 90.0) -> None:
    delay = min(cap, base * (2**attempt_index))
    jitter = random.uniform(0, min(8.0, delay * 0.25))
    total = delay + jitter
    print(f"⏳ Bedrock backoff (visual planner): sleep {total:.1f}s")
    time.sleep(total)


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"⚠️  Error retrieving secret {secret_name}: {e}")
        return {}


def create_unique_filename(description: str, prefix: str = "visual") -> str:
    """Create a unique, short, and sanitized filename using a hash."""
    hash_object = hashlib.sha1(description.encode())
    short_hash = hash_object.hexdigest()[:10]
    return f"{prefix}_{short_hash}.png"


def extract_visual_tags_from_lesson(lesson_content: str, lesson_id: str) -> List[Dict[str, Any]]:
    """
    Extract [VISUAL: MM-LL-NNNN - description] tags from lesson content.

    The keyword VISUAL is matched case-insensitively so tags like [visual: ...] from the
    LLM still route to image generation (strict uppercase-only matching skipped all tags).

    Returns:
        List of visual tags with ID and description: [{"id": "01-01-0001", "description": "...", "context": "..."}, ...]
    """
    visual_tag_regex = re.compile(
        r'\[visual:\s*(\d{2}-\d{2}-\d{4})\s*-\s*(.*?)\]',
        re.IGNORECASE | re.DOTALL,
    )

    visuals = []
    for m in visual_tag_regex.finditer(lesson_content):
        visual_id = m.group(1)
        desc = (m.group(2) or "").strip()
        start = max(0, m.start() - 100)
        end = min(len(lesson_content), m.end() + 100)
        context = lesson_content[start:end].strip()

        visuals.append({
            "id": visual_id,
            "lesson_id": lesson_id,
            "description": desc,
            "context": context,
        })

    return visuals


def call_bedrock(prompt: str, model_id: str = DEFAULT_BEDROCK_MODEL) -> str:
    """Call AWS Bedrock Claude API with transient-error backoff."""
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 16000,
        "temperature": 0.7,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    last_err: Optional[Exception] = None
    for attempt in range(1, BEDROCK_APP_MAX_ATTEMPTS + 1):
        try:
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
        except Exception as e:
            last_err = e
            print(f"❌ Bedrock API error (attempt {attempt}/{BEDROCK_APP_MAX_ATTEMPTS}): {e}")
            if attempt < BEDROCK_APP_MAX_ATTEMPTS and _bedrock_error_is_transient(e):
                _sleep_before_bedrock_retry(attempt - 1)
                continue
            raise
    assert last_err is not None
    raise last_err


def call_openai(prompt: str, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> str:
    """Call OpenAI API."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # GPT-5 uses max_completion_tokens instead of max_tokens
        if model.startswith("o1-") or model == "gpt-5":
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=16000
            )
        else:
            # GPT-4 and earlier
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert visual prompt engineer for image generation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=16000,
                temperature=0.7
            )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        raise


def normalize_visual_course_language(lang: str | None) -> str:
    """Default Spanish; English only when explicitly requested."""
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


def process_visual_batch(
    visuals: List[Dict[str, Any]],
    model_provider: str = "bedrock",
    course_language: str = "es",
) -> List[Dict[str, Any]]:
    """
    Process all visual tags in a single LLM API call.

    Classifies each as diagram/artistic_image and creates enhanced prompts.
    Instructions match the course language (Spanish vs English) so on-image text aligns with lessons.
    """
    if not visuals:
        return []

    lang = normalize_visual_course_language(course_language)
    visuals_json = json.dumps(visuals, indent=2)

    if lang == "es":
        prompt = f"""You are an expert visual prompt engineer specializing in creating detailed, precise image generation prompts.

⚠️ REQUISITO DE IDIOMA (CURSO EN ESPAÑOL) ⚠️
TODO el contenido que generes (en especial el campo enhanced_prompt) DEBE estar en ESPAÑOL.
Todo texto que deba aparecer DENTRO de la imagen (rótulos, títulos, anotaciones, botones, mensajes de error, leyendas) DEBE estar en ESPAÑOL, coherente con el curso.
NO traduzcas el contenido didáctico al inglés salvo nombres propios de productos, APIs o comandos que en la práctica se muestran siempre en inglés.

Recibirás una lista de descripciones visuales extraídas de lecciones técnicas. Para cada elemento:

1. **Clasifica el tipo**:
   - "diagram": diagramas de flujo, arquitectura, secuencias, gráficos
   - "artistic_image": escenas, fotos conceptuales, metáforas visuales

2. **OBLIGATORIO: Todo en español** (salvo excepciones técnicas citadas):
   - El campo enhanced_prompt DEBE estar 100% en español
   - Las etiquetas dentro de la imagen en español (p. ej. "Base de datos", "Cliente", "Servidor")
   - Conserva la precisión técnica; no cambies el significado

3. **Crea un enhanced_prompt detallado EN ESPAÑOL** con:
   - Texto exacto y ortografía correcta para cada etiqueta visible (en español)
   - Tipografía: estilo, peso, tamaño
   - Disposición: posición, espaciado, alineación
   - Colores: códigos hex o nombres (#0066CC azul, etc.)
   - Estilo: profesional, moderno, limpio, técnico
   - Verificación: "Comprueba que todo el texto visible esté en español: [lista de términos críticos]"

INPUT VISUALS:
{visuals_json}

Devuelve SOLO JSON válido (sin markdown ni bloques de código) en este formato exacto:
{{
  "visuals": [
    {{
      "id": "01-01-0001",
      "lesson_id": "01-01",
      "description": "descripción original",
      "type": "diagram|artistic_image",
      "enhanced_prompt": "Prompt detallado EN ESPAÑOL con especificaciones exactas..."
    }},
    ...
  ]
}}

CRÍTICO: El campo "id" DEBE copiarse EXACTAMENTE del input. NO lo modifiques.

⚠️ LISTA DE VERIFICACIÓN:
1. ✓ ¿El "id" coincide exactamente con el input?
2. ✓ ¿enhanced_prompt está 100% en español?
3. ✓ ¿Todo texto dentro de la imagen está en español (salvo nombres de API/producto si aplica)?
4. ✓ ¿Ortografía y términos técnicos correctos?
5. ✓ ¿Colores y tipografía especificados?

Si hay texto para la imagen que no esté en español sin justificación técnica, corrígelo antes de responder."""

    else:
        prompt = f"""You are an expert visual prompt engineer specializing in creating detailed, precise image generation prompts.

⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
ALL output MUST be 100% in ENGLISH. This is mandatory for optimal image generation quality when the course is in English.

You will receive a list of visual descriptions extracted from technical course lessons. For each visual:

1. **Classify the type**:
   - "diagram": flowcharts, architecture diagrams, technical diagrams, charts, graphs, sequences
   - "artistic_image": scenes, photos, illustrations, metaphors, artistic representations

2. **MANDATORY: Write everything in English** (CRITICAL - NON-NEGOTIABLE):
   - The enhanced_prompt field MUST be 100% in English
   - ALL text that will appear IN the diagram/image MUST be in English
   - If the original description is in another language, translate it completely while preserving technical accuracy

3. **Create an enhanced prompt** (IN ENGLISH) with:
   - **Exact text with correct spelling**: List every label, title, annotation IN ENGLISH
   - **Typography**: Font style, weight, size, case
   - **Layout**: Position, spacing, alignment
   - **Colors**: Specific hex codes or names (#0066CC blue, #4CAF50 green, etc.)
   - **Style**: Professional, modern, clean, technical, minimalist
   - **Verification**: "Ensure all text is spelled correctly: [list critical English terms]"

INPUT VISUALS:
{visuals_json}

Return ONLY valid JSON (no markdown, no code blocks) in this exact format:
{{
  "visuals": [
    {{
      "id": "01-01-0001",
      "lesson_id": "01-01",
      "description": "original description",
      "type": "diagram|artistic_image",
      "enhanced_prompt": "Detailed, comprehensive prompt IN ENGLISH with exact specifications..."
    }},
    ...
  ]
}}

CRITICAL: The "id" field MUST be copied EXACTLY from the input (e.g., "02-01-0005"). Do NOT modify or regenerate IDs.

⚠️ FINAL CHECKLIST - VERIFY BEFORE RESPONDING:
1. ✓ Is the "id" field copied EXACTLY from input? (CRITICAL - DO NOT CHANGE IDs)
2. ✓ Is the enhanced_prompt 100% in English? (MANDATORY)
3. ✓ Are ALL labels, titles, and annotations in English?
4. ✓ Are technical terms spelled correctly?
5. ✓ Did you include specific color codes?
6. ✓ Did you specify text placement and typography?

If ANY text in enhanced_prompt is not in English, FIX IT before responding."""

    print(f"🤖 Calling {model_provider.upper()} with {len(visuals)} visual tags (course_language={lang})...")
    
    try:
        if model_provider == 'bedrock':
            response_text = call_bedrock(prompt)
        elif model_provider == 'openai':
            openai_key = get_secret("aurora/openai-api-key").get('api_key')
            if not openai_key:
                raise ValueError("OpenAI API key not found in Secrets Manager")
            response_text = call_openai(prompt, openai_key)
        else:
            raise ValueError(f"Unknown model provider: {model_provider}")
        
        print(f"✅ API call completed")
        print(f"Response length: {len(response_text)} characters")
        
        # Clean JSON response (remove markdown if present)
        cleaned_json = re.sub(r'^```json\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE)
        cleaned_json = cleaned_json.strip()
        
        # Parse response
        result = json.loads(cleaned_json)
        enhanced_visuals = result.get('visuals', [])
        
        print(f"✅ Processed {len(enhanced_visuals)} visual prompts")
        return enhanced_visuals
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print(f"Response preview: {response_text[:500]}")
        # Return unenhanced visuals as fallback
        return [{"lesson_id": v["lesson_id"], "description": v["description"], "type": "diagram", "enhanced_prompt": v["description"]} for v in visuals]
    except Exception as e:
        print(f"❌ Error processing visual batch: {e}")
        raise


def lambda_handler(event: Dict[str, Any], context):
    """
    Lambda handler for batch visual planning.
    
    Processes multiple lessons' visual tags in a single API call.
    """
    try:
        print("=" * 70)
        print("VISUAL PLANNER - OPTIMIZED BATCH PROCESSING")
        print("=" * 70)
        
        # Extract parameters
        lesson_keys = event.get('lesson_keys', [])
        course_bucket = event.get('course_bucket')
        project_folder = event.get('project_folder')
        model_provider = event.get('model_provider', 'bedrock').lower()
        course_language = normalize_visual_course_language(event.get('course_language'))

        print(f"📦 Bucket: {course_bucket}")
        print(f"📁 Project: {project_folder}")
        print(f"🤖 Model: {model_provider}")
        print(f"🌐 Course language (visuals): {course_language}")
        print(f"📚 Processing {len(lesson_keys)} lessons")
        
        if not lesson_keys:
            print("⚠️  No lessons provided")
            return {
                "statusCode": 200,
                "message": "No lessons to process",
                "prompts": []
            }
        
        # Step 1: Read all lesson content and extract visual tags
        all_visuals = []
        
        for lesson_info in lesson_keys:
            s3_key = lesson_info['s3_key']
            lesson_id = f"{lesson_info['module_number']:02d}-{lesson_info['lesson_number']:02d}"
            
            print(f"📖 Reading lesson: {s3_key}")
            
            try:
                # Read lesson content from S3
                response = s3_client.get_object(Bucket=course_bucket, Key=s3_key)
                lesson_content = response['Body'].read().decode('utf-8')
                
                # Extract visual tags
                visuals = extract_visual_tags_from_lesson(lesson_content, lesson_id)
                
                if visuals:
                    print(f"   Found {len(visuals)} visual tags")
                    all_visuals.extend(visuals)
                else:
                    print(f"   No visual tags found")
            
            except Exception as e:
                print(f"⚠️  Error reading lesson {s3_key}: {e}")
                continue
        
        if not all_visuals:
            print("ℹ️  No visual tags found in any lesson")
            return {
                "statusCode": 200,
                "message": "No visual tags found",
                "prompts": []
            }
        
        print(f"\n📊 Total visual tags: {len(all_visuals)}")
        
        # Step 2: Process ALL visuals in a SINGLE API call
        enhanced_visuals = process_visual_batch(all_visuals, model_provider, course_language)
        
        # Step 3: Generate prompt files and save to S3
        generated_prompts = []
        request_id = context.aws_request_id if hasattr(context, 'aws_request_id') else 'unknown'
        
        # Create lookup by ID for fallback matching
        original_lookup_by_id = {orig['id']: orig for orig in all_visuals}
        # Also create lookup by lesson_id + description as secondary fallback
        original_lookup_by_desc = {}
        for orig in all_visuals:
            key = f"{orig['lesson_id']}::{orig['description']}"
            original_lookup_by_desc[key] = orig
        
        print(f"📝 Processing enhanced visuals with IDs...")
        
        for idx, enhanced in enumerate(enhanced_visuals, start=1):
            # PREFERRED: Use the ID directly from the enhanced visual (LLM should preserve it)
            enhanced_id = enhanced.get('id')
            
            if enhanced_id and enhanced_id in original_lookup_by_id:
                # Best case: ID was preserved by LLM
                prompt_id = enhanced_id
                original_visual = original_lookup_by_id[enhanced_id]
                print(f"  ✓ ID preserved: {prompt_id}")
            else:
                # Fallback 1: Try matching by lesson_id + description
                lookup_key = f"{enhanced.get('lesson_id', '')}::{enhanced.get('description', '')}"
                original_visual = original_lookup_by_desc.get(lookup_key)
                
                if original_visual:
                    prompt_id = original_visual['id']
                    print(f"  ⚠️  ID not preserved, matched by description: {prompt_id}")
                else:
                    # Fallback 2: Generate a new ID (last resort)
                    print(f"  ❌ No match found for: {enhanced.get('id', 'unknown')} - using fallback")
                    prompt_id = f"{enhanced.get('lesson_id', '00-00')}-{idx:04d}"
                    original_visual = None
            
            description = original_visual.get('description', enhanced.get('description', '')) if original_visual else enhanced.get('description', '')
            visual_type = enhanced.get('type', 'diagram')
            enhanced_prompt = enhanced.get('enhanced_prompt', description)
            # Get lesson_id safely - handle case where original_visual is None
            lesson_id = original_visual.get('lesson_id', '00-00') if original_visual else enhanced.get('lesson_id', '00-00')
            
            filename = create_unique_filename(description, prefix=prompt_id)
            
            # Create prompt JSON
            prompt_data = {
                "id": prompt_id,
                "lesson_id": lesson_id,
                "description": description,
                "visual_type": visual_type,
                "enhanced_prompt": enhanced_prompt,
                "filename": filename,
                "created_at": datetime.utcnow().isoformat(),
                "request_id": request_id
            }
            
            # Save to S3
            prompt_key = f"{project_folder}/prompts/{prompt_id}.json"
            s3_client.put_object(
                Bucket=course_bucket,
                Key=prompt_key,
                Body=json.dumps(prompt_data, indent=2),
                ContentType='application/json'
            )
            
            generated_prompts.append({
                "id": prompt_id,
                "description": description,
                "visual_type": visual_type,
                "filename": filename,
                "s3_key": prompt_key
            })
            
            print(f"💾 Saved prompt: {prompt_id} ({visual_type})")
        
        print(f"\n✅ Generated {len(generated_prompts)} visual prompts")
        
        return {
            "statusCode": 200,
            "message": f"Successfully generated {len(generated_prompts)} visual prompts",
            "prompts": generated_prompts,
            "prompts_s3_prefix": f"{project_folder}/prompts/"
        }
    
    except Exception as e:
        print(f"❌ Error in Visual Planner: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "statusCode": 500,
            "error": str(e),
            "prompts": []
        }
