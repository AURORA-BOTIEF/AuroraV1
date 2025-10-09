#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strands Visual Planner Lambda
Extracts [VISUAL: ...] tags from lesson content and creates prompt files for image generation.
Uses a single Strands Agent for classification (diagram vs artistic_image).
"""

import os
import json
import re
import boto3
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from strands import Agent
from strands.models import BedrockModel

# Try to import OpenAIModel dynamically
try:
    from strands.models.openai import OpenAIModel
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAIModel = None
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI model not available in this environment")

# Initialize S3 client
s3_client = boto3.client('s3')

def create_unique_filename(description: str, prefix: str = "visual") -> str:
    """Create a unique, short, and sanitized filename using a hash."""
    hash_object = hashlib.sha1(description.encode())
    short_hash = hash_object.hexdigest()[:10]
    return f"{prefix}_{short_hash}.png"


def lambda_handler(event: Dict[str, Any], context):
    """
    Lambda handler for generating visual plans from lesson content.
    
    Expected event format:
    {
        "lesson_key": "project-name/lessons/01-01-lesson.md",  # S3 key to lesson file
        "course_bucket": "bucket-name",
        "project_folder": "project-name",
        "module_number": 1,
        "lesson_number": 1,
        "module_title": "Module Title",
        "lesson_title": "Lesson Title"
    }
    
    Returns:
    {
        "statusCode": 200,
        "message": "Successfully generated N visual prompts",
        "prompts": [
            {
                "id": "01-01-0001",
                "description": "...",
                "visual_type": "diagram|artistic_image",
                "filename": "visual_abc123.png",
                "s3_key": "project/prompts/01-01-0001-short-name.json"
            }
        ],
        "prompts_s3_prefix": "project/prompts/"
    }
    """
    try:
        print("=== Starting Strands Visual Planner ===")
        print(f"Event: {json.dumps(event, indent=2)}")
        
        # Extract parameters
        lesson_key = event.get('lesson_key')
        course_bucket = event.get('course_bucket')
        project_folder = event.get('project_folder')
        module_number = event.get('module_number', 1)
        lesson_number = event.get('lesson_number', 1)
        module_title = event.get('module_title', f'Module {module_number}')
        lesson_title = event.get('lesson_title', f'Lesson {lesson_number}')
        model_provider = event.get('model_provider', 'bedrock').lower()
        
        if not lesson_key or not course_bucket:
            raise ValueError("lesson_key and course_bucket are required")
        
        print(f"Processing: {lesson_key}")
        print(f"Bucket: {course_bucket}")
        print(f"Module {module_number}, Lesson {lesson_number}")
        print(f"Model Provider: {model_provider}")
        
        # Read lesson content from S3
        print(f"Reading lesson from S3: {lesson_key}")
        s3_response = s3_client.get_object(Bucket=course_bucket, Key=lesson_key)
        lesson_content = s3_response['Body'].read().decode('utf-8')
        
        print(f"Lesson content length: {len(lesson_content)} characters")
        
        # Extract visual tags using regex
        visual_tag_regex = re.compile(r'\[VISUAL:\s*(.*?)\]')
        descriptions = visual_tag_regex.findall(lesson_content)
        
        if not descriptions:
            print("No visual tags found in lesson")
            return {
                "statusCode": 200,
                "message": "No visual tags found",
                "prompts": [],
                "lesson_key": lesson_key,
                "project_folder": project_folder
            }
        
        print(f"Found {len(descriptions)} visual tags")
        
        # Prepare visual plans for classification
        visual_plans = []
        for idx, desc in enumerate(descriptions, start=1):
            visual_plans.append({
                "id": idx,
                "description": desc.strip(),
                "filename": create_unique_filename(desc),
                "module": module_number,
                "lesson": lesson_number
            })
        
        # Configure model based on provider
        if model_provider == 'openai':
            if not OPENAI_AVAILABLE or OpenAIModel is None:
                raise ValueError("OpenAI model provider requested but OpenAIModel is not available")
            
            # Get OpenAI API key from Secrets Manager
            openai_key = get_secret("aurora/openai-api-key").get('api_key')
            if not openai_key:
                raise ValueError("OPENAI_API_KEY not found in Secrets Manager")
            
            # Create OpenAI model instance
            model = OpenAIModel(
                client_args={"api_key": openai_key},
                model_id="gpt-4o"  # Use GPT-4o for visual planning
            )
            print(f"🔵 Using OpenAI: gpt-4o")
            
        else:  # bedrock (default)
            # Get Bedrock model from environment
            bedrock_model_id = os.environ.get('BEDROCK_MODEL', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
            model = BedrockModel(model_id=bedrock_model_id)
            print(f"🟠 Using Bedrock: {bedrock_model_id}")
        
        print(f"Creating Strands Agent with model provider: {model_provider}")
        
        # Create classification agent
        classifier = Agent(
            model=model,
            system_prompt="""You are a visual asset classifier. 
            
Your task is to classify visual descriptions into two categories:
1. "diagram" - for flowcharts, architecture diagrams, layered models, sequences, technical diagrams, charts, graphs
2. "artistic_image" - for scenes, metaphors, concepts, illustrations, photos, artistic representations

You will receive a JSON list of visual descriptions. For each one, add a "type" field with either "diagram" or "artistic_image".

Return ONLY valid JSON with no markdown formatting, no code blocks, no explanations. Just the JSON object.

Example input:
[
  {"id": 1, "description": "Kubernetes architecture diagram"},
  {"id": 2, "description": "A developer working at a computer"}
]

Example output:
{
  "visuals": [
    {"id": 1, "description": "Kubernetes architecture diagram", "type": "diagram"},
    {"id": 2, "description": "A developer working at a computer", "type": "artistic_image"}
  ]
}"""
        )
        
        # Create classification prompt
        classification_prompt = f"""Classify these visual descriptions:

{json.dumps(visual_plans, indent=2)}

For each visual, add a "type" field with either "diagram" or "artistic_image".
Return the result as a JSON object with a "visuals" key containing the array."""
        
        print("Running classification agent...")
        
        # Run classification
        response = classifier(classification_prompt)
        result_text = str(response)
        
        print(f"Raw agent response length: {len(result_text)} characters")
        print(f"First 200 chars: {result_text[:200]}")
        
        # Clean JSON response (remove markdown code blocks if present)
        cleaned_json = re.sub(r'^```json\s*|\s*```$', '', result_text.strip(), flags=re.MULTILINE)
        cleaned_json = cleaned_json.strip()
        
        # Parse classification result
        try:
            classification_result = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Cleaned JSON: {cleaned_json[:500]}")
            raise ValueError(f"Failed to parse agent response as JSON: {e}")
        
        # Extract classified visuals
        classified_visuals = classification_result.get('visuals', [])
        
        if not classified_visuals:
            print("Warning: No visuals in classification result")
            classified_visuals = visual_plans  # Fallback to unclassified
        
        print(f"Classified {len(classified_visuals)} visuals")
        
        # Generate prompt files and save to S3
        generated_prompts = []
        request_id = context.aws_request_id if hasattr(context, 'aws_request_id') else 'unknown'
        
        for prompt_number, visual in enumerate(classified_visuals, start=1):
            # Create prompt data structure
            prompt_data = {
                "id": f"{module_number:02d}-{lesson_number:02d}-{prompt_number:04d}",
                "module": module_number,
                "lesson": lesson_number,
                "prompt_number": prompt_number,
                "visual_type": visual.get('type', 'diagram'),
                "description": visual.get('description', ''),
                "filename": visual.get('filename', f'visual_{prompt_number}.png'),
                "lesson_title": lesson_title,
                "module_title": module_title,
                "generated_at": datetime.now().isoformat(),
                "model_provider": model_provider,
                "request_id": request_id
            }
            
            # Create filename with short name
            short_name = visual.get('description', '')[:30].replace(' ', '_').replace(':', '').replace('[', '').replace(']', '').lower()
            if not short_name:
                short_name = f"visual_{prompt_number}"
            
            prompt_filename = f"{module_number:02d}-{lesson_number:02d}-{prompt_number:04d}-{short_name}.json"
            
            # Save to S3 in the prompts folder
            s3_key = f"{project_folder}/prompts/{prompt_filename}"
            
            s3_client.put_object(
                Bucket=course_bucket,
                Key=s3_key,
                Body=json.dumps(prompt_data, indent=2),
                ContentType='application/json'
            )
            
            print(f"  Saved prompt {prompt_number}/{len(classified_visuals)}: {s3_key}")
            
            generated_prompts.append({
                "id": prompt_data["id"],
                "description": prompt_data["description"],
                "visual_type": prompt_data["visual_type"],
                "filename": prompt_data["filename"],
                "s3_key": s3_key
            })
        
        # Update lesson content to replace [VISUAL: description] with [VISUAL: id]
        print(f"Updating lesson content to use visual IDs...")
        updated_lesson_content = lesson_content
        
        for prompt_number, visual in enumerate(classified_visuals, start=1):
            visual_id = f"{module_number:02d}-{lesson_number:02d}-{prompt_number:04d}"
            description = visual.get('description', '').strip()
            
            # Replace [VISUAL: description] with [VISUAL: id]
            # Use regex to match the exact description within the visual tag
            pattern = r'\[VISUAL:\s*' + re.escape(description) + r'\]'
            replacement = f'[VISUAL: {visual_id}]'
            
            updated_lesson_content = re.sub(pattern, replacement, updated_lesson_content)
            print(f"  Replaced [VISUAL: {description}] with [VISUAL: {visual_id}]")
        
        # Save updated lesson content back to S3
        print(f"Saving updated lesson content to S3: {lesson_key}")
        s3_client.put_object(
            Bucket=course_bucket,
            Key=lesson_key,
            Body=updated_lesson_content.encode('utf-8'),
            ContentType='text/markdown'
        )
        print(f"✅ Updated lesson content saved successfully")
        
        # Calculate execution time
        execution_time = None
        if hasattr(context, 'get_remaining_time_in_millis'):
            remaining_time = context.get_remaining_time_in_millis()
            # Approximate execution time (timeout - remaining)
            timeout_ms = 900000  # 900 seconds default
            execution_time = (timeout_ms - remaining_time) / 1000.0
        
        # Return success response
        response_data = {
            "statusCode": 200,
            "message": f"Successfully generated {len(generated_prompts)} visual prompts",
            "prompts": generated_prompts,
            "lesson_key": lesson_key,
            "project_folder": project_folder,
            "prompts_s3_prefix": f"{project_folder}/prompts/",
            "bucket": course_bucket,
            "statistics": {
                "total_prompts": len(generated_prompts),
                "diagrams": sum(1 for p in generated_prompts if p['visual_type'] == 'diagram'),
                "artistic_images": sum(1 for p in generated_prompts if p['visual_type'] == 'artistic_image'),
                "execution_time_seconds": execution_time
            }
        }
        
        print("=== Visual Planning Complete ===")
        print(f"Generated {len(generated_prompts)} prompts")
        print(f"Statistics: {response_data['statistics']}")
        
        return response_data
        
    except Exception as e:
        error_msg = f"Error in visual planning: {str(e)}"
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        
        request_id = context.aws_request_id if hasattr(context, 'aws_request_id') else 'unknown'
        
        return {
            "statusCode": 500,
            "error": error_msg,
            "request_id": request_id,
            "lesson_key": event.get('lesson_key'),
            "project_folder": event.get('project_folder')
        }


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


if __name__ == '__main__':
    print("Strands Visual Planner Lambda Function")
    print("Use SAM CLI to test: sam local invoke StrandsVisualPlanner -e test-event.json")
