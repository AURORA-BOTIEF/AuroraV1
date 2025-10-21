"""
Content Generation - OPTIMIZED FOR MODERN LLMs
===============================================
Generates ONE batch of lessons per invocation (max 5 lessons).
Step Functions handles parallelization with MaxConcurrency.

Modern LLMs (Sonnet 4.5, GPT-5) can easily handle 5+ lessons with rich content
and visual tags in a single API call, reducing cost and improving speed.

Expected event parameters:
    - module_number: int (which module to generate)
    - batch_start_idx: int (0-based index of first lesson in batch)
    - batch_end_idx: int (0-based index of last lesson + 1, Python slice style)
    - batch_index: int (1-based batch number for logging)
    - total_batches: int (total batches in this module, for logging)
    - course_bucket, outline_s3_key, project_folder: S3 paths
    - model_provider: 'bedrock' or 'openai'
"""

import os
import json
import yaml
import boto3
import time
from botocore.config import Config
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure boto3 with extended timeouts for long-running LLM calls
boto_config = Config(
    read_timeout=600,  # 10 minutes read timeout
    connect_timeout=60,  # 1 minute connection timeout
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

# AWS Clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=boto_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-5"
DEFAULT_REGION = "us-east-1"


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        raise


def format_lesson_filename(module_num: int, lesson_index: int, lesson_title: str) -> str:
    """Format lesson filename."""
    safe_title = lesson_title.lower()
    safe_title = ''.join(c if c.isalnum() or c.isspace() else '' for c in safe_title)
    safe_title = '-'.join(safe_title.split())
    return f"module-{module_num}-lesson-{lesson_index + 1}-{safe_title}.md"


def calculate_target_words(lesson_data: dict, module_info: dict) -> int:
    """Calculate target word count for a lesson."""
    lesson_duration = lesson_data.get('duration_minutes', module_info.get('duration_minutes', 45))
    lesson_bloom = lesson_data.get('bloom_level', module_info.get('bloom_level', 'Understand'))
    
    # Handle compound bloom levels
    if '/' in lesson_bloom:
        bloom_parts = [b.strip() for b in lesson_bloom.split('/')]
        bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
        lesson_bloom = max(bloom_parts, key=lambda x: bloom_order.index(x) if x in bloom_order else 0)
    
    # Bloom multipliers
    bloom_multipliers = {
        'Remember': 1.0,
        'Understand': 1.1,
        'Apply': 1.2,
        'Analyze': 1.3,
        'Evaluate': 1.4,
        'Create': 1.5
    }
    
    bloom_mult = bloom_multipliers.get(lesson_bloom, 1.1)
    
    # Base calculation: 15 words per minute (concise content that teacher expands)
    base_words = lesson_duration * 15
    base_words = int(base_words * bloom_mult)
    
    # Add for topics and labs
    topics_count = len(lesson_data.get('topics', []))
    labs_count = len(lesson_data.get('lab_activities', []))
    
    total_words = base_words + (topics_count * 80) + (labs_count * 120)
    
    # Bounds
    return max(500, min(3000, total_words))


def build_course_context(course_data: dict) -> str:
    """Build complete course outline context."""
    course_title = course_data.get('title', 'Course')
    modules = course_data.get('modules', [])
    
    context_lines = [
        "════════════════════════════════════════════════════════════════════════",
        "COMPLETE COURSE OUTLINE - MUST REFERENCE THIS EXACT STRUCTURE",
        "════════════════════════════════════════════════════════════════════════",
        f"Course: {course_title}",
        f"Total Modules: {len(modules)}",
        ""
    ]
    
    for i, module in enumerate(modules, 1):
        context_lines.append(f"MODULE {i}: {module.get('title', 'Untitled')}")
        lessons = module.get('lessons', [])
        for j, lesson in enumerate(lessons, 1):
            context_lines.append(f"  Lesson {i}.{j}: {lesson.get('title', 'Untitled')}")
    
    context_lines.append("════════════════════════════════════════════════════════════════════════")
    
    return "\n".join(context_lines)


def generate_batch_single_call(
    module_number: int,
    batch_start_idx: int,
    batch_end_idx: int,
    module_data: dict,
    course_data: dict,
    model_provider: str = 'bedrock',
    openai_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate a single batch of lessons (3 lessons max) in ONE LLM call.
    
    Returns:
        List of lesson dictionaries with content, metadata, etc.
    """
    
    module_title = module_data.get('title', 'Module')
    module_description = module_data.get('description', '')
    module_duration = module_data.get('duration_minutes', 45)
    module_bloom = module_data.get('bloom_level', 'Understand')
    lessons = module_data.get('lessons', [])
    
    # Extract the batch of lessons
    batch_lessons = lessons[batch_start_idx:batch_end_idx]
    num_lessons = len(batch_lessons)
    
    print(f"\n📚 Module {module_number}: {module_title}")
    print(f"📝 Generating batch: Lessons {batch_start_idx + 1}-{batch_end_idx} ({num_lessons} lessons)")
    
    # Build course context
    course_context = build_course_context({'title': course_data.get('title', 'Course'), 'modules': course_data.get('modules', [])})
    
    # Build lesson specifications
    lesson_specs = []
    for i, lesson in enumerate(batch_lessons, start=batch_start_idx):
        target_words = calculate_target_words(lesson, module_data)
        
        topics_list = lesson.get('topics', [])
        topics_str = "\n".join([f"      - {topic}" for topic in topics_list])
        
        lab_activities = lesson.get('lab_activities', [])
        labs_str = "\n".join([f"      - {lab}" for lab in lab_activities])
        
        spec = f"""
    Lesson {i + 1}: {lesson.get('title', 'Untitled')}
    Duration: {lesson.get('duration_minutes', module_duration)} minutes
    Bloom Level: {lesson.get('bloom_level', module_bloom)}
    Target Length: ~{target_words} words
    Topics:
{topics_str if topics_str else "      (None specified)"}
    Lab Activities:
{labs_str if labs_str else "      (None specified)"}
"""
        lesson_specs.append(spec)
    
    lessons_specification = "\n".join(lesson_specs)
    
    # Build the prompt
    prompt = f"""You are an expert technical educator creating lesson content for a professional course.

{course_context}

TASK: Generate complete, detailed lesson content for {num_lessons} lesson(s) in Module {module_number}.

MODULE {module_number}: {module_title}
Description: {module_description}

LESSONS TO GENERATE:
{lessons_specification}

REQUIREMENTS:
1. Generate EXACTLY {num_lessons} complete lesson(s)
2. Each lesson must be comprehensive, detailed, and ready to teach
3. Each lesson MUST start with a clear heading: # Lesson N: [Title]
4. Include all specified topics and activities (if provided)
5. Use Markdown formatting with proper headings, lists, code blocks
6. Meet the target word count for each lesson
7. Maintain technical accuracy and professional tone
8. Include practical examples where appropriate
9. **IMPORTANT**: When a concept would benefit from visual representation (diagrams, screenshots, illustrations), add a visual tag using this format: [VISUAL: Brief description of the image needed]
   - Place visual tags inline where the image should appear
   - Be specific about what the image should show
   - Examples: [VISUAL: Diagram showing the MVC architecture flow], [VISUAL: Screenshot of the IDE debugger panel], [VISUAL: Flowchart of the authentication process]

OUTPUT FORMAT:
Generate the lessons separated by this exact delimiter:
═══════════════════════════════════════════════════════════════════════

Begin generating now:
"""
    
    print(f"🤖 Calling {model_provider.upper()} API...")
    start_time = time.time()
    
    try:
        if model_provider == 'bedrock':
            response_text = call_bedrock(prompt)
        elif model_provider == 'openai':
            if not openai_api_key:
                raise ValueError("OpenAI API key required for openai provider")
            response_text = call_openai(prompt, openai_api_key)
        else:
            raise ValueError(f"Unknown model provider: {model_provider}")
        
        elapsed = time.time() - start_time
        print(f"✅ API call completed in {elapsed:.1f}s")
        print(f"📄 Response length: {len(response_text):,} characters")
        
        # Parse the response into individual lessons
        parsed_lessons = parse_lessons_from_response(
            response_text=response_text,
            module_number=module_number,
            batch_lessons=batch_lessons,
            batch_start_idx=batch_start_idx,
            module_data=module_data
        )
        
        if len(parsed_lessons) != num_lessons:
            print(f"⚠️  Warning: Expected {num_lessons} lessons, got {len(parsed_lessons)}")
        
        return parsed_lessons
    
    except Exception as e:
        print(f"❌ Error generating batch: {str(e)}")
        raise


def call_bedrock(prompt: str, model_id: str = DEFAULT_BEDROCK_MODEL) -> str:
    """Call AWS Bedrock Claude API."""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 32000,
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
        
        if 'content' in response_body and len(response_body['content']) > 0:
            return response_body['content'][0]['text']
        else:
            raise ValueError("No content in Bedrock response")
    
    except Exception as e:
        print(f"Bedrock API Error: {str(e)}")
        raise


def call_openai(prompt: str, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> str:
    """Call OpenAI API."""
    try:
        import openai
        openai.api_key = api_key
        
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert technical educator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=32000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        raise


def parse_lessons_from_response(
    response_text: str,
    module_number: int,
    batch_lessons: List[dict],
    batch_start_idx: int,
    module_data: dict
) -> List[Dict[str, Any]]:
    """Parse LLM response into individual lesson objects."""
    
    # Split by delimiter
    delimiter = "═" * 71
    parts = response_text.split(delimiter)
    
    # Filter out empty parts
    lesson_contents = [part.strip() for part in parts if part.strip()]
    
    print(f"📝 Parsed {len(lesson_contents)} lesson(s) from response")
    
    parsed_lessons = []
    
    for i, content in enumerate(lesson_contents):
        if i >= len(batch_lessons):
            print(f"⚠️  Warning: More lessons in response than expected, truncating")
            break
        
        lesson_data = batch_lessons[i]
        lesson_index = batch_start_idx + i
        lesson_title = lesson_data.get('title', f'Lesson {lesson_index + 1}')
        
        # Calculate word count
        word_count = len(content.split())
        
        # Format filename
        filename = format_lesson_filename(module_number, lesson_index, lesson_title)
        
        parsed_lesson = {
            'module_number': module_number,
            'lesson_number': lesson_index + 1,
            'lesson_title': lesson_title,
            'filename': filename,
            'lesson_content': content,
            'word_count': word_count,
            'topics': lesson_data.get('topics', []),
            'bloom_level': lesson_data.get('bloom_level', module_data.get('bloom_level', 'Understand')),
            'duration_minutes': lesson_data.get('duration_minutes', module_data.get('duration_minutes', 45))
        }
        
        parsed_lessons.append(parsed_lesson)
        
        print(f"  ✅ Lesson {lesson_index + 1}: {lesson_title} ({word_count} words)")
    
    return parsed_lessons


def lambda_handler(event, context):
    """
    AWS Lambda handler - SIMPLIFIED SINGLE-BATCH VERSION
    
    Generates ONE batch of lessons per invocation (max 3 lessons).
    Step Functions handles parallelization with MaxConcurrency.
    """
    
    try:
        print("=" * 70)
        print("CONTENT GENERATION LAMBDA - SINGLE BATCH MODE")
        print("=" * 70)
        
        # Debug: Print full event
        print(f"\n📥 Received event:")
        print(json.dumps(event, indent=2, default=str))
        
        # Extract batch parameters
        module_num = event.get('module_number')
        batch_start_idx = event.get('batch_start_idx', 0)
        batch_end_idx = event.get('batch_end_idx')
        batch_index = event.get('batch_index', 1)
        total_batches = event.get('total_batches', 1)
        
        model_provider = event.get('model_provider', 'bedrock').lower()
        
        # S3 configuration
        outline_s3_key = event.get('outline_s3_key')
        course_bucket = event.get('course_bucket')
        project_folder = event.get('project_folder')
        
        if not all([module_num, outline_s3_key, course_bucket, project_folder]):
            raise ValueError("Missing required parameters: module_number, outline_s3_key, course_bucket, project_folder")
        
        module_num = int(module_num)
        batch_start_idx = int(batch_start_idx)
        
        print(f"\n📋 Batch Info:")
        print(f"  Module: {module_num}")
        print(f"  Batch: {batch_index}/{total_batches}")
        print(f"  Lessons: {batch_start_idx + 1}-{batch_end_idx if batch_end_idx else 'all'}")
        print(f"  Model: {model_provider}")
        print(f"  Outline: s3://{course_bucket}/{outline_s3_key}")
        
        # Load outline from S3
        print(f"\n📥 Loading outline from S3...")
        outline_obj = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
        outline_content = outline_obj['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_content)
        
        # Support both 'course' and 'course_metadata' keys
        course_info = outline_data.get('course', outline_data.get('course_metadata', {}))
        modules = outline_data.get('modules', [])
        
        # Validate module
        if module_num > len(modules) or module_num < 1:
            raise ValueError(f"Module {module_num} not found (outline has {len(modules)} modules)")
        
        module_data = modules[module_num - 1]
        module_lessons = module_data.get('lessons', [])
        
        # If batch_end_idx not specified, generate all lessons
        if batch_end_idx is None:
            batch_end_idx = len(module_lessons)
        else:
            batch_end_idx = int(batch_end_idx)
        
        # Validate batch range
        if batch_start_idx >= len(module_lessons) or batch_end_idx > len(module_lessons):
            raise ValueError(f"Invalid batch range [{batch_start_idx}:{batch_end_idx}] for module with {len(module_lessons)} lessons")
        
        # Get OpenAI key if needed
        openai_api_key = None
        if model_provider == 'openai':
            try:
                secret = get_secret("aurora/openai-api-key")
                openai_api_key = secret.get('api_key')
            except Exception as e:
                print(f"⚠️  Could not get OpenAI key: {e}")
                openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # GENERATE THIS BATCH
        print(f"\n{'='*70}")
        print(f"📚 GENERATING MODULE {module_num} - BATCH {batch_index}/{total_batches}")
        print(f"{'='*70}")
        
        generated_lessons = generate_batch_single_call(
            module_number=module_num,
            batch_start_idx=batch_start_idx,
            batch_end_idx=batch_end_idx,
            module_data=module_data,
            course_data={'title': course_info.get('title', 'Course'), 'modules': modules},
            model_provider=model_provider,
            openai_api_key=openai_api_key
        )
        
        # Save lessons to S3
        print(f"\n💾 Saving {len(generated_lessons)} lesson(s) to S3...")
        
        lesson_keys = []
        total_words = 0
        
        for lesson in generated_lessons:
            lesson_key = f"{project_folder}/lessons/{lesson['filename']}"
            
            s3_client.put_object(
                Bucket=course_bucket,
                Key=lesson_key,
                Body=lesson['lesson_content'].encode('utf-8'),
                ContentType='text/markdown'
            )
            
            print(f"  ✅ Saved: {lesson_key}")
            
            # Build structured lesson info for VisualPlanner (OPTIMIZED: batch processing)
            lesson_keys.append({
                "s3_key": lesson_key,
                "module_number": lesson['module_number'],
                "lesson_number": lesson['lesson_number'],
                "lesson_title": lesson['lesson_title']
            })
            
            total_words += lesson['word_count']
        
        # Return success response
        print(f"\n{'='*70}")
        print(f"✅ BATCH COMPLETE: Generated {len(generated_lessons)} lesson(s)")
        print(f"📊 Total words: {total_words:,}")
        print(f"{'='*70}")
        
        return {
            'statusCode': 200,
            'message': f'Batch {batch_index}/{total_batches} completed successfully',
            'lesson_keys': lesson_keys,  # Required by Step Functions
            'bucket': course_bucket,
            'project_folder': project_folder,
            'module_number': module_num,
            'batch_index': batch_index,
            'total_batches': total_batches,
            'lessons_generated': len(generated_lessons),
            'total_words': total_words,
            'model_provider': model_provider
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'error': str(e),
            'errorType': type(e).__name__
        }
