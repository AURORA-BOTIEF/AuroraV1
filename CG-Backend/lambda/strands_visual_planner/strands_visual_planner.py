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
import boto3
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from botocore.config import Config

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
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-5"


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
    Extract [VISUAL: ...] tags from lesson content.
    
    Returns:
        List of visual tags with context: [{"lesson_id": "01-01", "description": "...", "context": "..."}, ...]
    """
    visual_tag_regex = re.compile(r'\[VISUAL:\s*(.*?)\]')
    descriptions = visual_tag_regex.findall(lesson_content)
    
    visuals = []
    for desc in descriptions:
        # Extract surrounding context (100 chars before/after the tag)
        match = re.search(re.escape(f'[VISUAL: {desc}]'), lesson_content)
        if match:
            start = max(0, match.start() - 100)
            end = min(len(lesson_content), match.end() + 100)
            context = lesson_content[start:end].strip()
        else:
            context = ""
        
        visuals.append({
            "lesson_id": lesson_id,
            "description": desc.strip(),
            "context": context
        })
    
    return visuals


def call_bedrock(prompt: str, model_id: str = DEFAULT_BEDROCK_MODEL) -> str:
    """Call AWS Bedrock Claude API."""
    try:
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
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    
    except Exception as e:
        print(f"❌ Bedrock API error: {e}")
        raise


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


def process_visual_batch(visuals: List[Dict[str, Any]], model_provider: str = "bedrock") -> List[Dict[str, Any]]:
    """
    Process all visual tags in a single LLM API call.
    
    Classifies each as diagram/artistic_image and creates enhanced prompts.
    Modern LLMs can handle dozens of visuals in one call.
    
    Args:
        visuals: List of visual tags from multiple lessons
        model_provider: "bedrock" or "openai"
    
    Returns:
        List of enhanced visual prompts with classification
    """
    
    if not visuals:
        return []
    
    # Build the unified prompt for classification + enhancement
    prompt = f"""You are an expert visual prompt engineer specializing in creating detailed, precise image generation prompts.

You will receive a list of visual descriptions extracted from technical course lessons. For each visual:

1. **Classify the type**:
   - "diagram": flowcharts, architecture diagrams, technical diagrams, charts, graphs, sequences
   - "artistic_image": scenes, photos, illustrations, metaphors, artistic representations

2. **Create an enhanced prompt** with:
   - **Exact text with correct spelling**: List every label, title, annotation
   - **Typography**: Font style, weight, size, case
   - **Layout**: Position, spacing, alignment
   - **Colors**: Specific hex codes or names (#0066CC blue, #4CAF50 green, etc.)
   - **Style**: Professional, modern, clean, technical, minimalist
   - **Verification**: "Ensure all text is spelled correctly: [list critical terms]"

INPUT VISUALS:
{json.dumps(visuals, indent=2)}

Return ONLY valid JSON (no markdown, no code blocks) in this exact format:
{{
  "visuals": [
    {{
      "lesson_id": "01-01",
      "description": "original description",
      "type": "diagram|artistic_image",
      "enhanced_prompt": "Detailed, comprehensive prompt with exact specifications..."
    }},
    ...
  ]
}}

CRITICAL: 
- Preserve correct spelling of all technical terms
- Be specific about text placement and typography
- Include color codes
- Verify spelling of technical terms at the end of each prompt"""

    print(f"🤖 Calling {model_provider.upper()} with {len(visuals)} visual tags...")
    
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
        
        print(f"📦 Bucket: {course_bucket}")
        print(f"📁 Project: {project_folder}")
        print(f"🤖 Model: {model_provider}")
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
        enhanced_visuals = process_visual_batch(all_visuals, model_provider)
        
        # Step 3: Generate prompt files and save to S3
        generated_prompts = []
        request_id = context.aws_request_id if hasattr(context, 'aws_request_id') else 'unknown'
        
        # Create a lookup for original descriptions to preserve them
        original_descriptions = {f"{v['lesson_id']}-{i+1}": v['description'] for i, v in enumerate(all_visuals)}
        
        for idx, visual in enumerate(enhanced_visuals, start=1):
            lesson_id = visual.get('lesson_id', '00-00')
            # IMPORTANT: Use original description from lesson, not LLM's rewritten version
            original_key = f"{lesson_id}-{idx}"
            description = original_descriptions.get(original_key, visual.get('description', ''))
            visual_type = visual.get('type', 'diagram')
            enhanced_prompt = visual.get('enhanced_prompt', description)
            
            # Create unique prompt ID
            prompt_id = f"{lesson_id}-{idx:04d}"
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
