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
            bedrock_model_id = os.environ.get('BEDROCK_MODEL', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
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
        
        # Create prompt enhancement agent
        prompt_enhancer = Agent(
            model=model,
            system_prompt="""You are an expert visual prompt engineer specializing in creating detailed, precise image generation prompts.

Your PRIMARY GOAL is to create prompts that produce images with ZERO SPELLING ERRORS and MAXIMUM TECHNICAL ACCURACY.

**SPELLING ERROR PREVENTION (CRITICAL):**
1. **Double-check ALL text**: Every word that appears in the image must be spelled correctly
2. **Spell out acronyms**: First time: "Kubernetes (K8s)", then "K8s" is OK
3. **Verify technical terms**: API Server (not "API Sever"), etcd (not "etc"), kubectl (not "kubctl")
4. **Use spell-check mindset**: If unsure, spell it out letter by letter: "e-t-c-d"
5. **Common corrections**:
   - "Kubernetes" not "Kuberneties" or "Kubernates"
   - "scheduler" not "schedular"
   - "persistent" not "persistant"
   - "deployment" not "deployement"
   - "controller" not "controler"
   - "namespace" not "name space"

**ENHANCED PROMPT REQUIREMENTS:**
For every visual, you MUST specify:
1. **Exact text with correct spelling** - List every label, title, annotation
2. **Typography** - Font style (sans-serif), weight (bold/regular), size (large/medium/small), case (Title Case/lowercase)
3. **Layout** - Position (top/center/bottom/left/right), spacing, alignment
4. **Colors** - Specific hex codes or names: #0066CC (blue), #4CAF50 (green), white (#FFFFFF)
5. **Shapes and elements** - Boxes, circles, arrows, lines with specific styles
6. **Style** - Professional, modern, clean, technical, minimalist
7. **Text verification** - "Ensure all text is spelled correctly: [list critical terms]"

**For diagrams:**
- Title at top, bold, centered
- Component names in boxes: "Label: 'API Server' (correct spelling)"
- Arrow labels: "Flow arrow with label 'HTTPS request'"
- Color coding: "Use blue (#0066CC) for external, green (#4CAF50) for internal"
- Add instruction: "Verify spelling of: [list all technical terms]"

**For artistic images:**
- Any visible text must be specified: "Laptop screen shows code with visible text 'kubectl get pods'"
- Environment details: lighting, perspective, composition
- Subject details: clothing, expression, actions
- If code is visible, specify language and make it realistic

**VERIFICATION CHECKLIST** (include in every prompt):
Add this at the end of each enhanced_prompt:
"SPELLING CHECK: Verify correct spelling of: [list all technical terms, labels, and critical words that appear in the image]"

Format your response as a JSON object with a "visuals" array. Each visual should have:
- "id": original id
- "description": original description  
- "type": visual type (from classification)
- "enhanced_prompt": your detailed, comprehensive prompt

Example input:
[
  {"id": 1, "description": "AWS Lambda architecture diagram showing API Gateway, Lambda, and DynamoDB", "type": "diagram"},
  {"id": 2, "description": "Developer working on Kubernetes deployment", "type": "artistic_image"}
]

Example output:
{
  "visuals": [
    {
      "id": 1,
      "description": "AWS Lambda architecture diagram showing API Gateway, Lambda, and DynamoDB",
      "type": "diagram",
      "enhanced_prompt": "Professional technical architecture diagram with white background (#FFFFFF). Title at top center in bold sans-serif: 'AWS Lambda Architecture' (verify spelling: A-W-S L-a-m-b-d-a). Three main components arranged left to right: 1) Blue box (#0066CC) labeled 'API Gateway' (verify spelling: A-P-I G-a-t-e-w-a-y), 2) Orange box (#FF9900) labeled 'Lambda Function' (verify spelling: L-a-m-b-d-a), 3) Blue box (#0066CC) labeled 'DynamoDB' (verify spelling: D-y-n-a-m-o-D-B, capital D and B). Arrows connecting boxes: left to right with labels 'HTTP Request' and 'Store Data' in small gray text. Add footer text: 'Event-driven Architecture'. SPELLING CHECK: Verify correct spelling of: AWS, Lambda, API Gateway, DynamoDB, Architecture"
    },
    {
      "id": 2,
      "description": "Developer working on Kubernetes deployment",
      "type": "artistic_image",
      "enhanced_prompt": "Modern professional photograph of a DevOps engineer at a clean desk with dual monitors. Left monitor shows terminal with visible command 'kubectl apply -f deployment.yaml' (verify spelling: k-u-b-e-c-t-l). Right monitor displays YAML configuration file with clearly readable text including 'apiVersion: apps/v1' and 'kind: Deployment' (verify spelling: D-e-p-l-o-y-m-e-n-t). Developer wearing casual professional attire, focused expression. Lighting: soft natural light from window on left creating depth. Background: modern minimalist office with green plants. Color palette: blues and grays with warm wood desk. Monitor content must be sharp and readable with correct spelling. SPELLING CHECK: Verify correct spelling of: kubectl, deployment, apiVersion, Kubernetes-related terms"
    }
  ]
}

Return ONLY valid JSON with no markdown formatting."""
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
        
        print(f"Raw classification response length: {len(result_text)} characters")
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
        
        # Enhance prompts with detailed specifications
        print("Running prompt enhancement agent...")
        
        enhancement_prompt = f"""Enhance these visual descriptions with detailed, specific prompts that include exact text and spelling:

{json.dumps(classified_visuals, indent=2)}

For each visual, create an "enhanced_prompt" field with comprehensive details including exact text, typography, layout, colors, and style.
CRITICAL: Preserve correct spelling of all technical terms and ensure any text in the image is spelled correctly."""
        
        # Run enhancement
        enhancement_response = prompt_enhancer(enhancement_prompt)
        enhancement_text = str(enhancement_response)
        
        print(f"Raw enhancement response length: {len(enhancement_text)} characters")
        print(f"First 200 chars: {enhancement_text[:200]}")
        
        # Clean JSON response
        cleaned_enhancement = re.sub(r'^```json\s*|\s*```$', '', enhancement_text.strip(), flags=re.MULTILINE)
        cleaned_enhancement = cleaned_enhancement.strip()
        
        # Parse enhancement result
        try:
            enhancement_result = json.loads(cleaned_enhancement)
        except json.JSONDecodeError as e:
            print(f"JSON decode error in enhancement: {e}")
            print(f"Cleaned JSON: {cleaned_enhancement[:500]}")
            # Fallback: use classified visuals without enhancement
            print("Warning: Using classified visuals without enhancement")
            enhancement_result = {'visuals': classified_visuals}
        
        # Extract enhanced visuals
        enhanced_visuals = enhancement_result.get('visuals', classified_visuals)
        
        print(f"Enhanced {len(enhanced_visuals)} visual prompts")
        
        # Generate prompt files and save to S3
        generated_prompts = []
        request_id = context.aws_request_id if hasattr(context, 'aws_request_id') else 'unknown'
        
        for prompt_number, visual in enumerate(enhanced_visuals, start=1):
            # Get enhanced prompt or fall back to original description
            enhanced_prompt = visual.get('enhanced_prompt', visual.get('description', ''))
            original_description = visual.get('description', '')
            
            # Create prompt data structure
            prompt_data = {
                "id": f"{module_number:02d}-{lesson_number:02d}-{prompt_number:04d}",
                "module": module_number,
                "lesson": lesson_number,
                "prompt_number": prompt_number,
                "visual_type": visual.get('type', 'diagram'),
                "description": original_description,  # Keep original for reference
                "enhanced_prompt": enhanced_prompt,  # Use this for image generation
                "filename": visual.get('filename', f'visual_{prompt_number}.png'),
                "lesson_title": lesson_title,
                "module_title": module_title,
                "generated_at": datetime.now().isoformat(),
                "model_provider": model_provider,
                "request_id": request_id
            }
            
            # Create filename with short name
            short_name = original_description[:30].replace(' ', '_').replace(':', '').replace('[', '').replace(']', '').lower()
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
            
            print(f"  Saved prompt {prompt_number}/{len(enhanced_visuals)}: {s3_key}")
            if enhanced_prompt != original_description:
                print(f"    Original: {original_description[:80]}...")
                print(f"    Enhanced: {enhanced_prompt[:80]}...")
            
            generated_prompts.append({
                "id": prompt_data["id"],
                "description": original_description,
                "enhanced_prompt": enhanced_prompt,
                "visual_type": prompt_data["visual_type"],
                "filename": prompt_data["filename"],
                "s3_key": s3_key
            })
        
        # Update lesson content to replace [VISUAL: description] with [VISUAL: id]
        print(f"Updating lesson content to use visual IDs...")
        updated_lesson_content = lesson_content
        
        for prompt_number, visual in enumerate(enhanced_visuals, start=1):
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
