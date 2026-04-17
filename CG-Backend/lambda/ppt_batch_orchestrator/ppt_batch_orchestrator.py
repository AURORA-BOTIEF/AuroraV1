"""
PPT Batch Orchestrator Lambda Function

Automatically generates PowerPoint presentations for all lessons in a course
by coordinating multiple invocations of the StrandsInfographicGenerator.

This function:
1. Loads the course book from S3
2. Determines total lesson count
3. Creates a Step Functions execution to process lessons in batches
4. Each batch is processed independently to respect Lambda 15-minute timeout
5. Combines all PPT batches into a single final presentation
"""

import json
import boto3
import logging
import os
import re
from datetime import datetime
from typing import Optional

s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
stepfunctions_client = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
MAX_LESSONS_PER_BATCH_LIMIT = int(os.environ.get('MAX_LESSONS_PER_BATCH', '50'))  # Increased for HTML-First architecture
MAX_CONCURRENT_BATCHES = 2  # Step Functions concurrency
PPT_ORCHESTRATOR_STATE_MACHINE_ARN = os.environ.get(
    'PPT_ORCHESTRATOR_STATE_MACHINE_ARN',
    'arn:aws:states:us-east-1:746434296869:stateMachine:PptBatchOrchestrator'
)
INFOGRAPHIC_GENERATOR_FUNCTION = 'StrandsInfographicGenerator'


def sanitize_for_execution_name(project_name: str, max_length: int = 45) -> str:
    """
    Sanitize project folder name for use in Step Functions execution names.
    AWS Step Functions execution names can only contain:
    - Alphanumeric characters (a-z, A-Z, 0-9)
    - Hyphens (-)
    - Underscores (_)
    Spaces and other special characters are not allowed.
    """
    # Replace spaces with hyphens
    sanitized = project_name.replace(' ', '-')
    # Remove any characters that are not alphanumeric, hyphens, or underscores
    sanitized = re.sub(r'[^a-zA-Z0-9\-_]', '', sanitized)
    # Replace multiple consecutive hyphens with a single one
    sanitized = re.sub(r'-+', '-', sanitized)
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized


def resolve_batch_size(requested_batch_size: Optional[int]) -> int:
    if requested_batch_size is None:
        return MAX_LESSONS_PER_BATCH_LIMIT
    try:
        size = int(requested_batch_size)
    except (TypeError, ValueError):
        return MAX_LESSONS_PER_BATCH_LIMIT
    if size <= 0:
        return 1
    if size > MAX_LESSONS_PER_BATCH_LIMIT:
        logger.warning(
            f"Requested batch size {size} exceeds limit {MAX_LESSONS_PER_BATCH_LIMIT}; capping to limit"
        )
        return MAX_LESSONS_PER_BATCH_LIMIT
    return size


def load_book_from_s3(course_bucket: str, project_folder: str, book_version_key: str = None, book_type: str = 'theory') -> dict:
    """Load the course book from S3.
    
    Args:
        course_bucket: S3 bucket name
        project_folder: Project folder path
        book_version_key: Optional specific book version key (full S3 path)
        book_type: 'theory' or 'lab'
    """
    try:
        if book_version_key:
            # Use specific version provided
            book_key = book_version_key
            logger.info(f"📚 Loading specific book version from s3://{course_bucket}/{book_key}")
        else:
            # FIXED: Search ALL folders and pick the NEWEST book by LastModified date
            # This ensures we always use the most recent version regardless of folder
            possible_folders = [
                f"{project_folder}/{book_type}-book/",
                f"{project_folder}/book/",
                f"{project_folder}/versions/",
                f"{project_folder}/"
            ]
            
            all_book_files = []
            for folder in possible_folders:
                try:
                    response = s3_client.list_objects_v2(Bucket=course_bucket, Prefix=folder, Delimiter='/')
                    for obj in response.get('Contents', []):
                        key = obj['Key']
                        if key.endswith('.json') and (
                            'book' in key.lower() or 
                            'course' in key.lower()
                        ) and 'lab' not in key.lower():  # Exclude lab books for theory
                            all_book_files.append({
                                'Key': key,
                                'LastModified': obj.get('LastModified'),
                                'Size': obj.get('Size', 0)
                            })
                            logger.info(f"   Found: {key} (modified: {obj.get('LastModified')}, size: {obj.get('Size', 0)})")
                except Exception as e:
                    logger.debug(f"Could not search {folder}: {e}")
                    continue
            
            if not all_book_files:
                raise ValueError(f"No book found in: {', '.join(possible_folders)}")
            
            # Sort by LastModified (newest first) to always use the latest version
            all_book_files.sort(key=lambda x: x.get('LastModified') or '', reverse=True)
            
            logger.info(f"📚 Found {len(all_book_files)} book candidates:")
            for idx, bf in enumerate(all_book_files[:3]):
                logger.info(f"   #{idx+1}: {bf['Key']} (modified: {bf.get('LastModified')}, size: {bf.get('Size')})")
            
            book_key = all_book_files[0]['Key']
            logger.info(f"✅ Selected NEWEST book: {book_key}")
        
        response = s3_client.get_object(Bucket=course_bucket, Key=book_key)
        book_data = json.loads(response['Body'].read().decode('utf-8'))
        return book_data
    except Exception as e:
        logger.error(f"❌ Error loading book: {str(e)}")
        raise


def calculate_batch_configuration(total_lessons: int, batch_size: int = MAX_LESSONS_PER_BATCH_LIMIT) -> list:
    """
    Calculate batch configuration for all lessons.
    
    Returns: List of dicts with lesson_start, lesson_end, batch_index
    """
    batches = []
    batch_index = 0
    
    for lesson_start in range(1, total_lessons + 1, batch_size):
        lesson_end = min(lesson_start + batch_size - 1, total_lessons)
        batches.append({
            'batch_index': batch_index,
            'lesson_start': lesson_start,
            'lesson_end': lesson_end,
            'total_lessons': total_lessons,
            'batch_size': lesson_end - lesson_start + 1
        })
        batch_index += 1
    
    return batches


def create_ppt_batch_tasks(
    course_bucket: str,
    project_folder: str,
    batches: list,
    model_provider: str = 'bedrock',
    html_first: bool = True,
    book_version_key: str = None,
    book_type: str = 'theory'
) -> list:
    """Create Lambda invocation tasks for each batch."""
    tasks = []
    
    for batch in batches:
        task = {
            'batch_index': batch['batch_index'],
            'course_bucket': course_bucket,
            'project_folder': project_folder,
            'lesson_start': batch['lesson_start'],
            'lesson_end': batch['lesson_end'],
            'max_lessons_per_batch': batch['batch_size'],
            'total_lessons': batch['total_lessons'],
            'model_provider': model_provider,
            'html_first': html_first,  # NEW: Enable HTML-first architecture
            'timeout_seconds': 840,  # 14 minutes, leaves 1 min buffer before 900s hard limit
            'book_version_key': book_version_key,  # Pass specific version to use
            'book_type': book_type  # 'theory' or 'lab'
        }
        tasks.append(task)
    
    return tasks


def lambda_handler(event, context):
    """
    Main handler for PPT batch orchestration.
    
    Input event:
    {
        "course_bucket": "crewai-course-artifacts",
        "project_folder": "251031-databricks-ciencia-datos",
        "model_provider": "bedrock",  # optional, defaults to bedrock
        "auto_combine": true  # optional, automatically combine PPTs at end
    }
    """
    try:
        logger.info("=" * 80)
        logger.info("🎨 PPT BATCH ORCHESTRATOR")
        logger.info("=" * 80)
        
        # Parse event - handle both API Gateway format and direct invocation
        body = {}
        try:
            raw_body = event.get('body')
            
            # handle base64 encoding
            if event.get('isBase64Encoded') and raw_body:
                import base64
                raw_body = base64.b64decode(raw_body).decode('utf-8')

            if isinstance(raw_body, str):
                if raw_body.strip():
                    body = json.loads(raw_body)
                else:
                    body = {}
            else:
                body = raw_body or event
        except Exception as e:
            logger.error(f"❌ Error parsing request body: {e}")
            body = {}
        
        # Parse input
        course_bucket = body.get('course_bucket')
        project_folder = body.get('project_folder')
        model_provider = body.get('model_provider', 'bedrock')
        html_first = body.get('html_first', True)
        user_email = body.get('user_email')  # Optional: for end-user notifications
        book_version_key = body.get('book_version_key')  # Specific book version to use
        book_type = body.get('book_type', 'theory')  # 'theory' or 'lab'
        
        # HTML-first architecture: Skip PPT merging and conversion (HTML is final output)
        # Legacy architecture: Merge batches and convert to PPT
        auto_combine = False if html_first else body.get('auto_combine', True)
        
        if not course_bucket or not project_folder:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'error': 'Missing required parameters: course_bucket, project_folder'
                })
            }
        
        logger.info(f"🚀 Starting PPT batch orchestration")
        logger.info(f"📚 Course: {project_folder} in {course_bucket}")
        if book_version_key:
            logger.info(f"📖 Using specific book version: {book_version_key}")
        else:
            logger.info(f"📖 Using auto-discovered book ({book_type})")
        
        # Load book to determine lesson count
        book_data = load_book_from_s3(course_bucket, project_folder, book_version_key, book_type)
        
        # Count total lessons - prefer top-level 'lessons' array (newer/more reliable format)
        # Fall back to counting from 'modules' for older books
        total_lessons = 0
        if 'lessons' in book_data and len(book_data.get('lessons', [])) > 0:
            total_lessons = len(book_data.get('lessons', []))
            logger.info(f"📖 Found {total_lessons} lessons in top-level array")
        else:
            # Fall back to counting from modules
            modules = book_data.get('modules', [])
            for module in modules:
                lessons_in_module = len(module.get('lessons', []))
                total_lessons += lessons_in_module
            logger.info(f"📖 Found {total_lessons} lessons across {len(modules)} modules")
        
        if total_lessons == 0:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'error': 'No lessons found in course book'
                })
            }
        
        logger.info(f"📖 Total lessons in course: {total_lessons}")
        
        # Determine batch size
        requested_batch_size = body.get('batch_size')
        batch_size = resolve_batch_size(requested_batch_size)
        logger.info(f"📦 Using batch size = {batch_size} lessons (env limit {MAX_LESSONS_PER_BATCH_LIMIT})")

        logger.info(f"🔧 Architecture: {'HTML-FIRST (new)' if html_first else 'JSON-based (legacy)'}")
        if html_first:
            logger.info(f"   ✅ HTML is FINAL OUTPUT (no PPT conversion)")
            logger.info(f"   ✅ auto_combine disabled (HTML-first doesn't need merging)")
        else:
            logger.info(f"   ⚠️  Legacy mode: Will generate JSON + PPT")
            logger.info(f"   ⚠️  auto_combine={auto_combine}")

        # Calculate batch configuration
        batches = calculate_batch_configuration(total_lessons, batch_size)
        num_batches = len(batches)
        
        logger.info(f"📦 Batch configuration:")
        for batch in batches:
            logger.info(f"   Batch {batch['batch_index']}: Lessons {batch['lesson_start']}-{batch['lesson_end']} ({batch['batch_size']} lessons)")
        
        # Create batch tasks
        ppt_batch_tasks = create_ppt_batch_tasks(
            course_bucket=course_bucket,
            project_folder=project_folder,
            batches=batches,
            model_provider=model_provider,
            html_first=html_first,  # Pass html_first to all batches
            book_version_key=book_version_key,  # Pass specific book version
            book_type=book_type  # 'theory' or 'lab'
        )
        
        # Prepare Step Functions execution input
        state_machine_input = {
            'course_bucket': course_bucket,
            'project_folder': project_folder,
            'model_provider': model_provider,
            'auto_combine': auto_combine,
            'ppt_batch_tasks': ppt_batch_tasks,
            'total_batches': num_batches,
            'total_lessons': total_lessons,
            'max_concurrent_batches': MAX_CONCURRENT_BATCHES,
            'book_version_key': book_version_key,  # Pass through for each batch
            'book_type': book_type  # 'theory' or 'lab'
        }
        
        # Add user_email if provided (for notifications)
        if user_email:
            state_machine_input['user_email'] = user_email
            logger.info(f"📧 User email for notifications: {user_email}")
        
        # Start Step Functions execution
        # AWS Step Functions execution name max length: 80 characters
        # Format: "ppt-orchestration-{project}-{timestamp}"
        # Reserve: 18 (prefix) + 1 (dash) + 15 (timestamp) + 1 (dash) = 35 chars
        # Available for project folder: 80 - 35 = 45 chars
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        max_project_length = 45
        # Sanitize project folder name (remove spaces and special characters)
        sanitized_project = sanitize_for_execution_name(project_folder, max_project_length)
        execution_name = f"ppt-orchestration-{sanitized_project}-{timestamp}"
        logger.info(f"Generated execution name: {execution_name} (from project: {project_folder})")
        
        
        try:
            sf_response = stepfunctions_client.start_execution(
                stateMachineArn=PPT_ORCHESTRATOR_STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(state_machine_input)
            )
            
            execution_arn = sf_response['executionArn']
            logger.info(f"✅ Step Functions execution started")
            logger.info(f"   Execution ARN: {execution_arn}")
            logger.info(f"   Name: {execution_name}")
            
            return {
                'statusCode': 202,  # Accepted
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'message': f'PPT batch orchestration started',
                    'execution_arn': execution_arn,
                    'execution_name': execution_name,
                    'total_lessons': total_lessons,
                    'total_batches': num_batches,
                    'batch_size': batch_size,
                    'batches': [
                        {
                            'batch_index': b['batch_index'],
                            'lesson_start': b['lesson_start'],
                            'lesson_end': b['lesson_end']
                        }
                        for b in batches
                    ]
                })
            }
        
        except Exception as e:
            logger.error(f"❌ Error starting Step Functions execution: {str(e)}")
            raise
    
    except Exception as e:
        logger.error(f"❌ Error in PPT batch orchestrator: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }
