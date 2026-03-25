"""
Lab Batch Expander Lambda Function
===================================
Reads lab master plan from S3 and expands labs into individual batch tasks.

This enables Step Functions to process lab batches in parallel using MaxConcurrency,
following the same pattern as theory content generation.

Input:
    {
        "course_bucket": "crewai-course-artifacts",
        "master_plan_key": "project/labguide/lab-master-plan.json",
        "project_folder": "251014-course-name",
        "model_provider": "bedrock"
    }

Output:
    {
        "batches": [
            {
                "batch_index": 1,
                "total_batches": 5,
                "lab_ids": ["01-01-01"],
                "course_bucket": "...",
                "master_plan_key": "...",
                "project_folder": "...",
                "model_provider": "..."
            },
            ...
        ]
    }
"""

import json
import os
import boto3
from typing import List, Dict, Any

s3_client = boto3.client('s3')

# One lab per Step Functions batch item so StrandsLabWriter stays under Lambda 15m limit.
MAX_LABS_PER_BATCH = max(1, int(os.getenv("MAX_LABS_PER_BATCH", "1")))


def lambda_handler(event, context):
    """
    Expand labs from master plan into batch tasks for parallel processing.
    """
    
    try:
        print("=" * 70)
        print("LAB BATCH EXPANDER - Converting Labs to Batches")
        print("=" * 70)
        
        # Extract parameters
        course_bucket = event.get('course_bucket')
        master_plan_key = event.get('master_plan_key')
        project_folder = event.get('project_folder')
        model_provider = event.get('model_provider', 'bedrock')
        
        if not all([course_bucket, master_plan_key, project_folder]):
            raise ValueError("Missing required parameters: course_bucket, master_plan_key, project_folder")
        
        print(f"\n📥 Loading master plan from S3...")
        print(f"  Bucket: {course_bucket}")
        print(f"  Key: {master_plan_key}")
        
        # Load master plan from S3
        plan_obj = s3_client.get_object(Bucket=course_bucket, Key=master_plan_key)
        plan_content = plan_obj['Body'].read().decode('utf-8')
        master_plan = json.loads(plan_content)
        
        # Get all labs
        lab_plans = master_plan.get('lab_plans', [])
        
        if not lab_plans:
            print("⚠️  No labs found in master plan")
            return {
                'statusCode': 200,
                'batches': [],
                'total_batches': 0,
                'total_labs': 0,
                'course_bucket': course_bucket,
                'project_folder': project_folder,
                'model_provider': model_provider
            }
        
        print(f"\n📋 Master plan contains {len(lab_plans)} labs")
        
        # Extract lab IDs
        lab_ids = [lab['lab_id'] for lab in lab_plans]
        num_labs = len(lab_ids)
        
        # Calculate number of batches needed
        num_batches = (num_labs + MAX_LABS_PER_BATCH - 1) // MAX_LABS_PER_BATCH
        
        print(f"📊 {num_labs} labs → {num_batches} batch(es)")
        print(f"📏 Batch size: {MAX_LABS_PER_BATCH} labs per batch")
        
        # Discover existing lesson content
        print(f"\n🔍 Discovering lesson content in {project_folder}/lessons/...")
        lesson_files = list_lesson_files(course_bucket, project_folder)
        lesson_map = map_lessons_to_keys(lesson_files)
        print(f"📄 Found {len(lesson_files)} lesson files, mapped {len(lesson_map)} lessons")

        # Create batch tasks
        all_batches = []
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * MAX_LABS_PER_BATCH
            end_idx = min(start_idx + MAX_LABS_PER_BATCH, num_labs)
            
            batch_lab_ids = lab_ids[start_idx:end_idx]
            
            # Map labs to their corresponding lesson content keys
            batch_lesson_keys = {}
            for lab_id in batch_lab_ids:
                # Extract module and lesson from lab_id (MM-LL-NN)
                try:
                    parts = lab_id.split('-')
                    if len(parts) >= 2:
                        mod_num = int(parts[0])
                        les_num = int(parts[1])
                        
                        # Check if we have content for this lesson
                        if (mod_num, les_num) in lesson_map:
                            batch_lesson_keys[lab_id] = lesson_map[(mod_num, les_num)]
                            print(f"    🔗 Lab {lab_id} mapped to lesson content: {lesson_map[(mod_num, les_num)].split('/')[-1]}")
                        elif les_num == 0 and (mod_num, 1) in lesson_map:
                            # Fallback: if lab is 00 (module level) and lesson 1 exists, use lesson 1
                            batch_lesson_keys[lab_id] = lesson_map[(mod_num, 1)]
                            print(f"    🔗 Lab {lab_id} (Module Level) mapped to lesson 1 content: {lesson_map[(mod_num, 1)].split('/')[-1]}")
                except Exception as e:
                    print(f"    ⚠️ Could not map lab {lab_id} to lesson: {e}")

            batch_task = {
                'batch_index': batch_idx + 1,  # 1-based for logging
                'total_batches': num_batches,
                'lab_ids': batch_lab_ids,
                'lab_lesson_keys': batch_lesson_keys,  # NEW: Pass content keys
                'course_bucket': course_bucket,
                'master_plan_key': master_plan_key,
                'project_folder': project_folder,
                'model_provider': model_provider
            }
            
            all_batches.append(batch_task)
            
            print(f"\n  Batch {batch_idx + 1}/{num_batches}:")
            print(f"    Lab IDs: {', '.join(batch_lab_ids)}")
        
        print(f"\n✅ Expanded {num_labs} lab(s) into {num_batches} batch(es)")
        print(f"📊 With MaxConcurrency=2, expected time: ~{(num_batches / 2) * 3:.0f} minutes")
        print("=" * 70)
        
        return {
            'statusCode': 200,
            'batches': all_batches,
            'total_batches': num_batches,
            'total_labs': num_labs,
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


def list_lesson_files(bucket: str, project_folder: str) -> List[str]:
    """List all markdown files in the lessons directory."""
    try:
        prefix = f"{project_folder}/lessons/"
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        files = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.endswith('.md'):
                        files.append(key)
        return files
    except Exception as e:
        print(f"⚠️ Error listing lesson files: {e}")
        return []


def map_lessons_to_keys(lesson_keys: List[str]) -> Dict[tuple, str]:
    """
    Map (module_num, lesson_num) -> s3_key
    Expected filename format: module-M-lesson-L-title.md
    """
    mapping = {}
    import re
    
    # Pattern: module-M-lesson-L-title.md
    # Configured to be flexible with separators
    pattern = re.compile(r'module-(\d+)-lesson-(\d+)', re.IGNORECASE)
    
    for key in lesson_keys:
        filename = key.split('/')[-1]
        match = pattern.search(filename)
        if match:
            try:
                mod_num = int(match.group(1))
                les_num = int(match.group(2))
                mapping[(mod_num, les_num)] = key
            except ValueError:
                continue
                
    return mapping
