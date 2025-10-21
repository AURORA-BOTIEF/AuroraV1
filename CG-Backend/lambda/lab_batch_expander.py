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
                "lab_ids": ["01-01-01", "01-01-02"],
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
import boto3
from typing import List, Dict, Any

s3_client = boto3.client('s3')

# Maximum labs per batch
# LabWriter already processes 2 labs per internal batch, so we keep it aligned
MAX_LABS_PER_BATCH = 2


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
        
        # Create batch tasks
        all_batches = []
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * MAX_LABS_PER_BATCH
            end_idx = min(start_idx + MAX_LABS_PER_BATCH, num_labs)
            
            batch_lab_ids = lab_ids[start_idx:end_idx]
            
            batch_task = {
                'batch_index': batch_idx + 1,  # 1-based for logging
                'total_batches': num_batches,
                'lab_ids': batch_lab_ids,
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
