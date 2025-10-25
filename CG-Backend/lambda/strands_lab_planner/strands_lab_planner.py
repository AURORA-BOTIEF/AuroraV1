"""
Lab Planner - Agent 1: Master Planning
Reads course outline and creates comprehensive lab guide plan.

Features:
- Extracts all lab_activities from outline
- Generates master plan with objectives, scope, duration
- Identifies hardware and software requirements
- Integrates user's additional requirements
- Outputs structured JSON plan for Lab Writer
"""

import os
import json
import yaml
import boto3
from botocore.config import Config
from datetime import datetime
from typing import Dict, List, Any, Optional

# AWS Clients with extended timeout for Bedrock (complex prompts can take 3-5 minutes)
bedrock_config = Config(
    read_timeout=600,  # 10 minutes
    connect_timeout=60,
    retries={'max_attempts': 3}
)
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=bedrock_config)
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
        # Return empty dict if secret not found
        return {}


def load_outline_from_s3(bucket: str, key: str) -> dict:
    """Load and parse course outline YAML from S3."""
    try:
        print(f"📥 Loading outline from s3://{bucket}/{key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        yaml_content = response['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(yaml_content)
        print(f"✅ Outline loaded successfully")
        return outline_data
    except Exception as e:
        print(f"❌ Error loading outline: {e}")
        raise


def extract_all_labs(outline_data: dict, modules_to_generate: any = "all") -> List[Dict[str, Any]]:
    """
    Extract lab activities from the outline, optionally filtering by modules.
    
    Args:
        outline_data: The course outline dictionary
        modules_to_generate: 
            - "all": Extract from all modules
            - int (e.g., 3): Single module
            - list of ints (e.g., [1, 3, 5]): Multiple modules
    
    Returns list of lab info with context:
    [
        {
            'module_number': 1,
            'module_title': 'Introduction',
            'lesson_number': 1,
            'lesson_title': 'Getting Started',
            'lab_index': 1,
            'lab_title': 'Setup environment',
            'duration_minutes': 30,
            'bloom_level': 'Apply',
            'context_topics': ['topic1', 'topic2']
        },
        ...
    ]
    """
    labs = []
    
    # Parse module filter
    target_modules = set()
    if modules_to_generate == "all" or modules_to_generate is None:
        target_modules = None  # Include all
    elif isinstance(modules_to_generate, list):
        target_modules = set(int(m) for m in modules_to_generate)
    elif isinstance(modules_to_generate, (int, str)):
        try:
            target_modules = {int(modules_to_generate)}
        except (ValueError, TypeError):
            print(f"⚠️  Invalid modules_to_generate value: {modules_to_generate}, treating as 'all'")
            target_modules = None
    
    # Modules can be at top level OR under 'course'
    modules = outline_data.get('modules', [])
    if not modules:
        course_data = outline_data.get('course', {})
        modules = course_data.get('modules', [])
    
    print(f"\n{'='*70}")
    print(f"🔍 EXTRACTING LAB ACTIVITIES FROM OUTLINE")
    if target_modules is None:
        print(f"🎯 Filtering: All modules")
    else:
        print(f"🎯 Filtering: Modules {sorted(target_modules)} only")
    print(f"{'='*70}")
    
    for mod_idx, module in enumerate(modules, 1):
        # Skip modules that don't match the filter
        if target_modules is not None and mod_idx not in target_modules:
            continue
            
        module_title = module.get('title', f'Module {mod_idx}')
        lessons = module.get('lessons', [])
        
        # OPTION 1: Extract labs from lessons (old format: lab_activities inside lessons)
        for les_idx, lesson in enumerate(lessons, 1):
            lesson_title = lesson.get('title', f'Lesson {les_idx}')
            lesson_bloom = lesson.get('bloom_level', module.get('bloom_level', 'Understand'))
            
            # Extract topics for context
            topics = lesson.get('topics', [])
            context_topics = []
            for topic in topics:
                if isinstance(topic, dict):
                    context_topics.append(topic.get('title', ''))
                else:
                    context_topics.append(str(topic))
            
            # Extract lab activities from lesson
            lab_activities = lesson.get('lab_activities', [])
            
            for lab_idx, lab in enumerate(lab_activities, 1):
                if isinstance(lab, dict):
                    lab_title = lab.get('title', f'Lab {lab_idx}')
                    lab_duration = lab.get('duration_minutes', 30)
                    lab_bloom = lab.get('bloom_level', lesson_bloom)
                    lab_objectives = lab.get('objectives', [])
                    lab_activities_list = lab.get('activities', [])
                else:
                    lab_title = str(lab)
                    lab_duration = 30
                    lab_bloom = lesson_bloom
                    lab_objectives = []
                    lab_activities_list = []
                
                lab_info = {
                    'module_number': mod_idx,
                    'module_title': module_title,
                    'lesson_number': les_idx,
                    'lesson_title': lesson_title,
                    'lab_index': lab_idx,
                    'lab_title': lab_title,
                    'duration_minutes': lab_duration,
                    'bloom_level': lab_bloom,
                    'context_topics': context_topics,
                    'lab_id': f"{mod_idx:02d}-{les_idx:02d}-{lab_idx:02d}",
                    'objectives': lab_objectives,
                    'activities': lab_activities_list
                }
                
                labs.append(lab_info)
                print(f"  ✓ Lab {lab_info['lab_id']}: {lab_title} ({lab_duration} min)")
        
        # OPTION 2: Extract labs from module level (supports both 'labs' and 'lab_activities' keys)
        module_labs = module.get('labs', []) or module.get('lab_activities', [])
        if module_labs:
            print(f"  📋 Found {len(module_labs)} module-level labs")
            
            # Collect all topics from all lessons for context
            all_context_topics = []
            for lesson in lessons:
                topics = lesson.get('topics', [])
                for topic in topics:
                    if isinstance(topic, dict):
                        all_context_topics.append(topic.get('title', ''))
                    else:
                        all_context_topics.append(str(topic))
            
            for lab_idx, lab in enumerate(module_labs, 1):
                # Handle both dict and string formats
                if isinstance(lab, dict):
                    lab_number = lab.get('number', lab_idx)
                    lab_title = lab.get('title', f'Lab {lab_number}')
                    lab_duration = lab.get('duration_minutes', 30)
                    lab_bloom = lab.get('bloom_level', module.get('bloom_level', 'Apply'))
                    lab_objectives = lab.get('objectives', [])
                    lab_activities_list = lab.get('activities', [])
                    lab_description = lab.get('description', '')
                else:
                    # String format (simple lab title)
                    lab_number = lab_idx
                    lab_title = str(lab)
                    lab_duration = 30
                    lab_bloom = module.get('bloom_level', 'Apply')
                    lab_objectives = []
                    lab_activities_list = []
                    lab_description = ''
                
                lab_info = {
                    'module_number': mod_idx,
                    'module_title': module_title,
                    'lesson_number': 0,  # Module-level lab, not tied to specific lesson
                    'lesson_title': 'Module Lab',
                    'lab_index': lab_number,
                    'lab_title': lab_title,
                    'duration_minutes': lab_duration,
                    'bloom_level': lab_bloom,
                    'context_topics': all_context_topics,
                    'lab_id': f"{mod_idx:02d}-00-{lab_number:02d}",
                    'objectives': lab_objectives,
                    'activities': lab_activities_list,
                    'description': lab_description
                }
                
                labs.append(lab_info)
                print(f"  ✓ Lab {lab_info['lab_id']}: {lab_title} ({lab_duration} min)")
    
    print(f"\n📊 Total labs found: {len(labs)}")
    print(f"{'='*70}\n")
    
    return labs


def call_bedrock_agent(prompt: str, model_id: str) -> str:
    """Call AWS Bedrock with Strands Agents pattern."""
    try:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 32000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7
        }
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(payload),
            contentType='application/json',
            accept='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    
    except Exception as e:
        print(f"❌ Bedrock API error: {e}")
        raise


def call_openai_agent(prompt: str, api_key: str, model_id: str = "gpt-5") -> str:
    """Call OpenAI API with GPT-5 compatibility."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # GPT-5 (o1) models use max_completion_tokens instead of max_tokens
        # and don't support temperature or system messages
        if model_id.startswith("o1-") or model_id == "gpt-5":
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=32000
            )
        else:
            # GPT-4 and earlier models
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are an expert technical instructor and lab designer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=32000,
                temperature=0.7
            )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        raise


def generate_lab_master_plan(
    labs: List[Dict[str, Any]],
    course_info: dict,
    additional_requirements: Optional[str],
    model_provider: str = "bedrock"
) -> dict:
    """
    Generate comprehensive master plan for all labs using AI.
    
    The AI will analyze all labs and create:
    - Overall objectives for the lab guide
    - Hardware requirements (aggregated)
    - Software requirements (aggregated)
    - Detailed plan for each lab with objectives and scope
    """
    
    print(f"\n{'='*70}")
    print(f"🤖 GENERATING MASTER LAB PLAN")
    print(f"{'='*70}")
    print(f"Model Provider: {model_provider}")
    print(f"Total Labs: {len(labs)}")
    
    # Build course context
    course_title = course_info.get('title', 'Course')
    course_description = course_info.get('description', '')
    course_level = course_info.get('level', 'intermediate')
    prerequisites = course_info.get('prerequisites', [])
    
    # Build labs summary
    labs_summary = []
    for lab in labs:
        labs_summary.append(
            f"[{lab['lab_id']}] Module {lab['module_number']}.{lab['lesson_number']} - "
            f"{lab['lab_title']} ({lab['duration_minutes']} min, {lab['bloom_level']})\n"
            f"  Context Topics: {', '.join(lab['context_topics']) if lab['context_topics'] else 'N/A'}"
        )
    
    # Build prompt for AI
    prompt = f"""
You are an expert technical instructor designing a comprehensive laboratory guide.

COURSE INFORMATION:
Title: {course_title}
Description: {course_description}
Level: {course_level}
Prerequisites: {', '.join(prerequisites) if prerequisites else 'None specified'}

LABS TO PLAN ({len(labs)} total):
{chr(10).join(labs_summary)}

ADDITIONAL REQUIREMENTS:
{additional_requirements if additional_requirements else 'None specified - use your best judgment'}

YOUR TASK:
Create a comprehensive master plan for the entire laboratory guide. This plan will be used by another AI agent to write detailed step-by-step instructions.

OUTPUT REQUIRED (JSON format):

{{
  "overall_objectives": [
    "Primary objective of the lab guide",
    "Secondary objective",
    ...
  ],
  "hardware_requirements": [
    "Specific hardware requirement 1",
    "Specific hardware requirement 2",
    ...
  ],
  "software_requirements": [
    {{
      "name": "Software name",
      "version": "Version or 'latest'",
      "purpose": "Why this software is needed",
      "installation_notes": "Brief installation guidance"
    }},
    ...
  ],
  "lab_plans": [
    {{
      "lab_id": "01-01-01",
      "lab_title": "Lab title from outline",
      "objectives": [
        "Specific learning objective 1",
        "Specific learning objective 2",
        ...
      ],
      "scope": "Detailed description of what this lab covers and what students will accomplish",
      "estimated_duration": 30,
      "bloom_level": "Apply",
      "prerequisites": [
        "Prerequisite 1",
        "Prerequisite 2"
      ],
      "key_technologies": [
        "Technology 1",
        "Technology 2"
      ],
      "expected_outcomes": [
        "Outcome 1",
        "Outcome 2"
      ],
      "complexity": "easy|medium|hard"
    }},
    ...
  ],
  "special_considerations": [
    "Important consideration 1",
    "Important consideration 2",
    ...
  ]
}}

IMPORTANT GUIDELINES:
1. Be SPECIFIC - avoid vague statements like "various tools"
2. Consider the Bloom level (Remember < Understand < Apply < Analyze < Evaluate < Create)
3. Ensure prerequisites build logically (later labs can depend on earlier ones)
4. Include troubleshooting considerations in special_considerations
5. Hardware requirements should be realistic and specific (RAM, CPU, disk space)
6. Software versions matter - specify if a specific version is required
7. Integrate the additional requirements throughout the plan
8. Duration estimates should account for setup, execution, and verification
9. Each lab should have 2-4 clear, measurable objectives
10. Scope should be detailed enough for another AI to write step-by-step instructions

Return ONLY the JSON object, no additional text.
"""
    
    print("🚀 Calling AI model to generate master plan...")
    
    try:
        if model_provider == "openai":
            # Get OpenAI API key
            secret_data = get_secret("aurora/openai-api-key")
            api_key = secret_data.get('api_key') or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                print("⚠️  OpenAI API key not found, falling back to Bedrock")
                model_provider = "bedrock"
            else:
                response_text = call_openai_agent(prompt, api_key, DEFAULT_OPENAI_MODEL)
        
        if model_provider == "bedrock":
            response_text = call_bedrock_agent(prompt, DEFAULT_BEDROCK_MODEL)
        
        print("✅ AI response received, parsing JSON...")
        
        # Parse JSON from response
        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        master_plan = json.loads(response_text.strip())
        
        print(f"✅ Master plan generated successfully")
        print(f"   - Overall objectives: {len(master_plan.get('overall_objectives', []))}")
        print(f"   - Hardware requirements: {len(master_plan.get('hardware_requirements', []))}")
        print(f"   - Software requirements: {len(master_plan.get('software_requirements', []))}")
        print(f"   - Lab plans: {len(master_plan.get('lab_plans', []))}")
        
        return master_plan
    
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse AI response as JSON: {e}")
        print(f"Response text: {response_text[:500]}...")
        raise
    except Exception as e:
        print(f"❌ Error generating master plan: {e}")
        raise


def save_master_plan_to_s3(
    bucket: str,
    project_folder: str,
    master_plan: dict
) -> str:
    """Save master plan JSON to S3."""
    try:
        key = f"{project_folder}/labguide/lab-master-plan.json"
        
        print(f"💾 Saving master plan to s3://{bucket}/{key}")
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(master_plan, indent=2),
            ContentType='application/json'
        )
        
        print(f"✅ Master plan saved successfully")
        return key
    
    except Exception as e:
        print(f"❌ Error saving master plan: {e}")
        raise


def lambda_handler(event, context):
    """
    Lambda handler for Lab Planner (Agent 1).
    
    Input event:
    {
        "course_bucket": "crewai-course-artifacts",
        "outline_s3_key": "uploads/xxx/outline.yaml",
        "project_folder": "251014-kubernetes-course",
        "model_provider": "bedrock",
        "lab_requirements": "Use Docker containers, focus on AWS services"
    }
    
    Output:
    {
        "statusCode": 200,
        "master_plan_key": "project/labguide/lab-master-plan.json",
        "total_labs": 15,
        "total_duration_minutes": 600,
        "project_folder": "251014-kubernetes-course",
        "bucket": "crewai-course-artifacts",
        "model_provider": "bedrock"
    }
    """
    
    print("\n" + "="*70)
    print("🧪 LAB PLANNER - AGENT 1: MASTER PLANNING")
    print("="*70)
    
    try:
        # Extract parameters
        course_bucket = event.get('course_bucket', 'crewai-course-artifacts')
        outline_key = event['outline_s3_key']
        project_folder = event['project_folder']
        model_provider = event.get('model_provider', 'bedrock')
        lab_requirements = event.get('lab_requirements')
        
        # Support both old (single module) and new (multiple modules) formats
        modules_to_generate = event.get('modules_to_generate')
        if modules_to_generate is None:
            # Fallback to old single-module parameter
            module_to_generate = event.get('module_to_generate', 'all')
            if module_to_generate == 'all':
                modules_to_generate = 'all'
            else:
                modules_to_generate = [int(module_to_generate)]
        elif not isinstance(modules_to_generate, list):
            modules_to_generate = [int(modules_to_generate)]
        
        print(f"📦 Bucket: {course_bucket}")
        print(f"📄 Outline: {outline_key}")
        print(f"📁 Project: {project_folder}")
        print(f"🤖 Model: {model_provider}")
        print(f"🎯 Module Scope: {modules_to_generate}")
        print(f"📋 Additional Requirements: {lab_requirements if lab_requirements else 'None'}")
        
        # Step 1: Load outline
        outline_data = load_outline_from_s3(course_bucket, outline_key)
        course_info = outline_data.get('course', {})
        
        # Step 2: Extract labs (filtered by modules if specified)
        labs = extract_all_labs(outline_data, modules_to_generate)
        
        if not labs:
            print("⚠️  No labs found in outline! Returning success with empty plan.")
            # Return success with empty lab plan instead of error
            # This allows the workflow to continue with theory-only content
            return {
                'statusCode': 200,
                'master_plan_key': None,
                'total_labs': 0,
                'total_duration_minutes': 0,
                'project_folder': project_folder,
                'bucket': course_bucket,
                'model_provider': model_provider,
                'message': 'No lab activities found in outline - skipping lab generation'
            }
        
        # Step 3: Generate master plan with AI
        master_plan = generate_lab_master_plan(
            labs=labs,
            course_info=course_info,
            additional_requirements=lab_requirements,
            model_provider=model_provider
        )
        
        # Add metadata (including language for LabWriter)
        course_language = course_info.get('language', 'en')
        master_plan['metadata'] = {
            'generated_at': datetime.utcnow().isoformat(),
            'model_provider': model_provider,
            'course_title': course_info.get('title', 'Unknown'),
            'course_language': course_language,  # NEW: Pass language to LabWriter
            'total_labs': len(labs),
            'total_duration_minutes': sum(lab['duration_minutes'] for lab in labs),
            'additional_requirements': lab_requirements
        }
        
        # Step 4: Save to S3
        master_plan_key = save_master_plan_to_s3(
            bucket=course_bucket,
            project_folder=project_folder,
            master_plan=master_plan
        )
        
        print(f"\n{'='*70}")
        print(f"✅ LAB PLANNING COMPLETED SUCCESSFULLY")
        print(f"{'='*70}\n")
        
        return {
            'statusCode': 200,
            'master_plan_key': master_plan_key,
            'total_labs': len(labs),
            'total_duration_minutes': sum(lab['duration_minutes'] for lab in labs),
            'project_folder': project_folder,
            'bucket': course_bucket,
            'model_provider': model_provider
        }
    
    except KeyError as e:
        print(f"❌ Missing required parameter: {e}")
        return {
            'statusCode': 400,
            'error': f'Missing required parameter: {e}'
        }
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'error': str(e)
        }
