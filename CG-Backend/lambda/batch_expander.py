"""
Batch Expander Lambda Function
================================
Reads course outline from S3 and expands modules into individual batch tasks.

This enables Step Functions to process batches in parallel using MaxConcurrency,
without complex coordination logic.

Input:
    {
        "course_bucket": "netec-course-generator-content",
        "outline_s3_key": "projects/xxx/outline.yaml",
        "modules_to_generate": [1, 2, 3, ...]
    }

Output:
    {
        "batches": [
            {
                "module_number": 1,
                "batch_index": 1,
                "total_batches": 2,
                "batch_start_idx": 0,
                "batch_end_idx": 3,
                "course_bucket": "...",
                "outline_s3_key": "...",
                "project_folder": "...",
                "model_provider": "..."
            },
            ...
        ]
    }
"""

import json
import boto3
import yaml
from typing import List, Dict, Any

s3_client = boto3.client('s3')

# Maximum lessons per batch (reduced to 3 to prevent Lambda timeouts)
# Large courses with complex lessons can take 15+ minutes for 5 lessons
# Batch size of 3 ensures completion within Lambda's 900s timeout
MAX_LESSONS_PER_BATCH = 3


def lambda_handler(event, context):
    """
    Expand modules into batch tasks for parallel processing.
    """
    
    try:
        print("=" * 70)
        print("BATCH EXPANDER - Converting Modules to Batches")
        print("=" * 70)
        
        # Extract parameters
        course_bucket = event.get('course_bucket')
        outline_s3_key = event.get('outline_s3_key')
        modules_to_generate = event.get('modules_to_generate', [])
        project_folder = event.get('project_folder')
        model_provider = event.get('model_provider', 'bedrock')
        content_source = event.get('content_source')
        
        if not all([course_bucket, outline_s3_key, project_folder]):
            raise ValueError("Missing required parameters: course_bucket, outline_s3_key, project_folder")
        
        print(f"\n📥 Loading outline from S3...")
        print(f"  Bucket: {course_bucket}")
        print(f"  Key: {outline_s3_key}")
        
        # Load outline from S3
        outline_obj = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
        outline_content = outline_obj['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_content)
        
        # Get modules from course structure
        course_data = outline_data.get('course', outline_data)  # Support both formats
        modules = course_data.get('modules', [])
        
        if not modules_to_generate:
            # If not specified, generate all modules
            modules_to_generate = list(range(1, len(modules) + 1))
        
        print(f"\n📋 Course has {len(modules)} modules")
        print(f"📋 Generating modules: {modules_to_generate}")
        
        # Expand each module into batches
        all_batches = []
        
        for module_num in modules_to_generate:
            if module_num > len(modules) or module_num < 1:
                print(f"⚠️  Warning: Module {module_num} not found, skipping")
                continue
            
            module_data = modules[module_num - 1]
            lessons = module_data.get('lessons', [])
            num_lessons = len(lessons)
            
            # Calculate number of batches needed
            num_batches = (num_lessons + MAX_LESSONS_PER_BATCH - 1) // MAX_LESSONS_PER_BATCH
            
            print(f"\n  Module {module_num}: {num_lessons} lessons → {num_batches} batch(es)")
            
            # Create batch tasks
            for batch_idx in range(num_batches):
                start_idx = batch_idx * MAX_LESSONS_PER_BATCH
                end_idx = min(start_idx + MAX_LESSONS_PER_BATCH, num_lessons)
                
                batch_task = {
                    'module_number': module_num,
                    'batch_index': batch_idx + 1,  # 1-based for logging
                    'total_batches': num_batches,
                    'batch_start_idx': start_idx,  # 0-based index
                    'batch_end_idx': end_idx,  # Python slice style (exclusive)
                    'course_bucket': course_bucket,
                    'outline_s3_key': outline_s3_key,
                    'project_folder': project_folder,
                    'model_provider': model_provider,
                    'content_source': content_source
                }
                
                all_batches.append(batch_task)
                
                print(f"    Batch {batch_idx + 1}/{num_batches}: Lessons {start_idx + 1}-{end_idx}")
        
        print(f"\n✅ Expanded {len(modules_to_generate)} module(s) into {len(all_batches)} batch(es)")
        print(f"📊 With MaxConcurrency=2, expected time: ~{(len(all_batches) / 2) * 7:.0f} minutes")
        print("=" * 70)
        
        return {
            'statusCode': 200,
            'batches': all_batches,
            'total_batches': len(all_batches),
            'total_modules': len(modules_to_generate),
            'course_bucket': course_bucket,
            'project_folder': project_folder,
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
