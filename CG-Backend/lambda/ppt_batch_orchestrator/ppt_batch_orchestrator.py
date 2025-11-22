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
from datetime import datetime
from typing import Optional

s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
stepfunctions_client = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
MAX_LESSONS_PER_BATCH_LIMIT = int(os.environ.get('MAX_LESSONS_PER_BATCH', '3'))
MAX_CONCURRENT_BATCHES = 2  # Step Functions concurrency
PPT_ORCHESTRATOR_STATE_MACHINE_ARN = os.environ.get(
    'PPT_ORCHESTRATOR_STATE_MACHINE_ARN',
    'arn:aws:states:us-east-1:746434296869:stateMachine:PptBatchOrchestrator'
)
INFOGRAPHIC_GENERATOR_FUNCTION = 'StrandsInfographicGenerator'


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


def load_book_from_s3(course_bucket: str, project_folder: str) -> dict:
    """Load the course book from S3."""
    try:
        book_key = f"{project_folder}/book/Generated_Course_Book_data.json"
        logger.info(f"📚 Loading book from s3://{course_bucket}/{book_key}")
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
    html_first: bool = True
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
            'timeout_seconds': 840  # 14 minutes, leaves 1 min buffer before 900s hard limit
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
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        # Parse input
        course_bucket = body.get('course_bucket')
        project_folder = body.get('project_folder')
        model_provider = body.get('model_provider', 'bedrock')
        html_first = body.get('html_first', True)
        
        # HTML-first architecture: Skip PPT merging and conversion (HTML is final output)
        # Legacy architecture: Merge batches and convert to PPT
        auto_combine = False if html_first else body.get('auto_combine', True)
        
        if not course_bucket or not project_folder:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters: course_bucket, project_folder'
                })
            }
        
        logger.info(f"🚀 Starting PPT batch orchestration")
        logger.info(f"📚 Course: {project_folder} in {course_bucket}")
        
        # Load book to determine lesson count
        book_data = load_book_from_s3(course_bucket, project_folder)
        
        # Count total lessons across all modules
        total_lessons = 0
        modules = book_data.get('modules', [])
        for module in modules:
            lessons_in_module = len(module.get('lessons', []))
            total_lessons += lessons_in_module
        
        if total_lessons == 0:
            return {
                'statusCode': 400,
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
            html_first=html_first  # Pass html_first to all batches
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
            'max_concurrent_batches': MAX_CONCURRENT_BATCHES
        }
        
        # Start Step Functions execution
        execution_name = f"ppt-orchestration-{project_folder}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
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
            'body': json.dumps({
                'error': str(e)
            })
        }
