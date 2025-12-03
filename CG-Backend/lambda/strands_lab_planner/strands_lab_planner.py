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


def extract_all_labs(
    outline_data: dict,
    modules_to_generate: any = "all",
    lab_ids_to_filter: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract lab activities from the outline, optionally filtering by modules or specific lab IDs.
    
    Args:
        outline_data: The course outline dictionary
        modules_to_generate: 
            - "all": Extract from all modules
            - int (e.g., 3): Single module
            - list of ints (e.g., [1, 3, 5]): Multiple modules
        lab_ids_to_filter:
            - None: No lab ID filtering (use module filtering if specified)
            - list of lab IDs (e.g., ["01-00-01", "02-00-01"]): Only extract these specific labs
    
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
    # Support both nested and flat formats (prefer nested)
    course_data = outline_data.get('course', outline_data)
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
    
    # NEW: Filter by specific lab IDs if requested
    if lab_ids_to_filter:
        print(f"🎯 Filtering for specific lab IDs: {lab_ids_to_filter}")
        original_count = len(labs)
        labs = [lab for lab in labs if lab['lab_id'] in lab_ids_to_filter]
        print(f"✓ Filtered from {original_count} to {len(labs)} lab(s)")
    
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
    model_provider: str = "bedrock",
    batch_size: int = 10
) -> dict:
    """
    Generate comprehensive master plan for all labs using AI with batching for large courses.
    
    The AI will analyze labs in batches and create:
    - Overall objectives for the lab guide
    - Hardware requirements (aggregated)
    - Software requirements (aggregated)
    - Detailed plan for each lab with objectives and scope
    
    Args:
        labs: List of lab dictionaries
        course_info: Course metadata
        additional_requirements: User-specified requirements
        model_provider: "bedrock" or "openai"
        batch_size: Number of labs to process per AI call (default 10)
    """
    
    print(f"\n{'='*70}")
    print(f"🤖 GENERATING MASTER LAB PLAN (OPTIMIZED FOR LARGE COURSES)")
    print(f"{'='*70}")
    print(f"Model Provider: {model_provider}")
    print(f"Total Labs: {len(labs)}")
    print(f"Batch Size: {batch_size} labs per AI call")
    
    # Build course context
    course_title = course_info.get('title', 'Course')
    course_description = course_info.get('description', '')
    course_level = course_info.get('level', 'intermediate')
    prerequisites = course_info.get('prerequisites', [])
    
    # For large courses, process labs in batches to avoid token limits and timeouts
    num_batches = (len(labs) + batch_size - 1) // batch_size
    print(f"📦 Processing {len(labs)} labs in {num_batches} batch(es)")
    
    all_lab_plans = []
    all_hardware_reqs = set()
    all_software_reqs = []
    all_overall_objectives = set()
    all_special_considerations = []
    
    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, len(labs))
        batch_labs = labs[start_idx:end_idx]
        
        print(f"\n🔄 Processing batch {batch_idx + 1}/{num_batches} ({len(batch_labs)} labs)...")
        
        # Build labs summary for this batch
        labs_summary = []
        for lab in batch_labs:
            labs_summary.append(
                f"[{lab['lab_id']}] Module {lab['module_number']}.{lab['lesson_number']} - "
                f"{lab['lab_title']} ({lab['duration_minutes']} min, {lab['bloom_level']})\n"
                f"  Context Topics: {', '.join(lab['context_topics']) if lab['context_topics'] else 'N/A'}"
            )
        
        # Build prompt for AI - OPTIMIZED with shorter instructions for batches
        if num_batches == 1:
            # Single batch - full prompt
            prompt_prefix = "Create a comprehensive master plan for the entire laboratory guide."
        else:
            # Multiple batches - streamlined prompt
            prompt_prefix = f"Create a detailed plan for this batch of labs (batch {batch_idx + 1} of {num_batches})."
        
        # Build prompt for AI - OPTIMIZED with shorter instructions for batches
        if num_batches == 1:
            # Single batch - full prompt
            prompt_prefix = "Create a comprehensive master plan for the entire laboratory guide."
        else:
            # Multiple batches - streamlined prompt
            prompt_prefix = f"Create a detailed plan for this batch of labs (batch {batch_idx + 1} of {num_batches})."
        
        prompt = f"""
You are an expert technical instructor designing laboratory guides.

COURSE: {course_title}
Level: {course_level}
{'Prerequisites: ' + ', '.join(prerequisites) if prerequisites else ''}

LABS IN THIS BATCH ({len(batch_labs)} labs):
{chr(10).join(labs_summary)}

REQUIREMENTS: {additional_requirements if additional_requirements else 'None specified'}

{prompt_prefix}

Return JSON with:
{{
  "overall_objectives": ["objective 1", "objective 2"],
  "hardware_requirements": ["requirement 1", "requirement 2"],
  "software_requirements": [{{"name": "Software", "version": "1.0", "purpose": "Why needed", "installation_notes": "Brief notes"}}],
  "lab_plans": [
    {{
      "lab_id": "01-01-01",
      "lab_title": "Title",
      "objectives": ["objective 1", "objective 2"],
      "scope": "Detailed description",
      "estimated_duration": 30,
      "bloom_level": "Apply",
      "prerequisites": ["prereq 1"],
      "key_technologies": ["tech 1"],
      "expected_outcomes": ["outcome 1"],
      "complexity": "easy|medium|hard"
    }}
  ],
  "special_considerations": ["consideration 1"]
}}

BE SPECIFIC. Include all {len(batch_labs)} labs. Return ONLY JSON.
"""
        
        try:
            if model_provider == "openai":
                secret_data = get_secret("aurora/openai-api-key")
                api_key = secret_data.get('api_key') or os.environ.get('OPENAI_API_KEY')
                if not api_key:
                    print("⚠️  OpenAI API key not found, falling back to Bedrock")
                    model_provider = "bedrock"
                else:
                    response_text = call_openai_agent(prompt, api_key, DEFAULT_OPENAI_MODEL)
            
            if model_provider == "bedrock":
                response_text = call_bedrock_agent(prompt, DEFAULT_BEDROCK_MODEL)
            
            # Parse JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            batch_plan = json.loads(response_text.strip())
            
            # Aggregate results from this batch
            all_lab_plans.extend(batch_plan.get('lab_plans', []))
            all_hardware_reqs.update(batch_plan.get('hardware_requirements', []))
            
            # Merge software requirements (avoid duplicates by name)
            for sw in batch_plan.get('software_requirements', []):
                if not any(s['name'] == sw['name'] for s in all_software_reqs):
                    all_software_reqs.append(sw)
            
            all_overall_objectives.update(batch_plan.get('overall_objectives', []))
            all_special_considerations.extend(batch_plan.get('special_considerations', []))
            
            print(f"✅ Batch {batch_idx + 1} completed: {len(batch_plan.get('lab_plans', []))} lab plans generated")
        
        except Exception as e:
            print(f"❌ Error processing batch {batch_idx + 1}: {e}")
            # Continue with next batch instead of failing completely
            print(f"⚠️  Continuing with remaining batches...")
            continue
    
    # Compile final master plan
    master_plan = {
        'overall_objectives': list(all_overall_objectives),
        'hardware_requirements': list(all_hardware_reqs),
        'software_requirements': all_software_reqs,
        'lab_plans': all_lab_plans,
        'special_considerations': all_special_considerations
    }
    
    print(f"\n✅ Master plan generation complete")
    print(f"   - Overall objectives: {len(master_plan['overall_objectives'])}")
    print(f"   - Hardware requirements: {len(master_plan['hardware_requirements'])}")
    print(f"   - Software requirements: {len(master_plan['software_requirements'])}")
    print(f"   - Lab plans: {len(master_plan['lab_plans'])}")
    print(f"   - Special considerations: {len(master_plan['special_considerations'])}")
    
    return master_plan


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
        
        # Support both old (modules) and new (lab_ids) parameters
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
        
        # NEW: Get lab IDs to regenerate (takes priority over module filtering)
        lab_ids_to_regenerate = event.get('lab_ids_to_regenerate')
        
        print(f"📦 Bucket: {course_bucket}")
        print(f"📄 Outline: {outline_key}")
        print(f"📁 Project: {project_folder}")
        print(f"🤖 Model: {model_provider}")
        print(f"🎯 Module Scope: {modules_to_generate}")
        if lab_ids_to_regenerate:
            print(f"🆔 Lab IDs to Regenerate: {lab_ids_to_regenerate}")
        print(f"📋 Additional Requirements: {lab_requirements if lab_requirements else 'None'}")
        
        # Step 1: Load outline
        outline_data = load_outline_from_s3(course_bucket, outline_key)
        course_info = outline_data.get('course', {})
        
        # Step 2: Extract labs (filtered by lab_ids if specified, otherwise by modules)
        labs = extract_all_labs(
            outline_data,
            modules_to_generate=modules_to_generate,
            lab_ids_to_filter=lab_ids_to_regenerate
        )
        
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
