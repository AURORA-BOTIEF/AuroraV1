#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Repair Feature - Image Generation
Generates only missing images by comparing prompts vs existing images.
"""

import os
import sys
import json
import boto3
from typing import Dict, List, Set

def get_existing_images(s3_client, bucket: str, project_folder: str) -> Set[str]:
    """Get set of existing image IDs from S3."""
    print(f"📂 Checking existing images in s3://{bucket}/{project_folder}/images/")
    
    existing = set()
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=bucket,
            Prefix=f"{project_folder}/images/"
        )
        
        for page in pages:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                key = obj['Key']
                # Extract image ID from filename (e.g., "01-01-0001.png" -> "01-01-0001")
                filename = os.path.basename(key)
                if filename.endswith('.png'):
                    image_id = filename.replace('.png', '')
                    existing.add(image_id)
        
        print(f"✅ Found {len(existing)} existing images")
        return existing
    
    except Exception as e:
        print(f"⚠️  Error reading existing images: {e}")
        return set()


def get_all_prompts(s3_client, bucket: str, project_folder: str) -> Dict[str, dict]:
    """Get all prompts from S3."""
    print(f"📂 Loading prompts from s3://{bucket}/{project_folder}/prompts/")
    
    prompts = {}
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=bucket,
            Prefix=f"{project_folder}/prompts/"
        )
        
        for page in pages:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                key = obj['Key']
                filename = os.path.basename(key)
                
                if filename.endswith('.json'):
                    # Download and parse prompt
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    prompt_data = json.loads(response['Body'].read())
                    
                    # Extract prompt ID (e.g., "01-01-0001.json" -> "01-01-0001")
                    prompt_id = filename.replace('.json', '')
                    prompts[prompt_id] = prompt_data
        
        print(f"✅ Found {len(prompts)} prompts")
        return prompts
    
    except Exception as e:
        print(f"❌ Error reading prompts: {e}")
        return {}


def find_missing_images(prompts: Dict[str, dict], existing: Set[str]) -> List[str]:
    """Find prompt IDs that don't have corresponding images."""
    all_prompt_ids = set(prompts.keys())
    missing = all_prompt_ids - existing
    
    print(f"\n📊 Analysis:")
    print(f"   Total prompts:    {len(all_prompt_ids)}")
    print(f"   Existing images:  {len(existing)}")
    print(f"   Missing images:   {len(missing)}")
    
    return sorted(list(missing))


def create_batch_payloads(
    missing_ids: List[str],
    bucket: str,
    project_folder: str,
    batch_size: int = 50
) -> List[dict]:
    """Create Lambda invocation payloads for missing images in batches."""
    batches = []
    
    for i in range(0, len(missing_ids), batch_size):
        batch = missing_ids[i:i + batch_size]
        
        payload = {
            "course_bucket": bucket,
            "project_folder": project_folder,
            "prompts_prefix": f"{project_folder}/prompts/",
            "repair_mode": True,
            "missing_image_ids": batch
        }
        
        batches.append({
            "batch_number": (i // batch_size) + 1,
            "start_index": i,
            "end_index": min(i + batch_size, len(missing_ids)),
            "count": len(batch),
            "payload": payload
        })
    
    return batches


def invoke_image_generation(lambda_client, function_name: str, batches: List[dict], dry_run: bool = False):
    """Invoke Lambda for each batch of missing images."""
    print(f"\n🚀 Image Generation Plan:")
    print(f"   Function: {function_name}")
    print(f"   Total batches: {len(batches)}")
    print(f"   Dry run: {dry_run}")
    
    for batch_info in batches:
        batch_num = batch_info['batch_number']
        count = batch_info['count']
        payload = batch_info['payload']
        
        print(f"\n📦 Batch {batch_num}:")
        print(f"   Images: {batch_info['start_index']}-{batch_info['end_index']} ({count} images)")
        print(f"   Sample IDs: {payload['missing_image_ids'][:3]}...")
        
        if dry_run:
            print(f"   ⏸️  Skipping (dry run)")
            continue
        
        try:
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='Event',  # Async
                Payload=json.dumps(payload)
            )
            
            if response['StatusCode'] == 202:
                print(f"   ✅ Invoked successfully")
            else:
                print(f"   ⚠️  Unexpected status: {response['StatusCode']}")
        
        except Exception as e:
            print(f"   ❌ Error invoking Lambda: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Repair Feature - Generate Missing Images'
    )
    parser.add_argument(
        '--bucket',
        default='crewai-course-artifacts',
        help='S3 bucket name'
    )
    parser.add_argument(
        '--project',
        required=True,
        help='Project folder (e.g., 251018-JS-06)'
    )
    parser.add_argument(
        '--function',
        default='ImagesGen',
        help='Lambda function name'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Images per batch'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually invoking'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔧 REPAIR FEATURE - IMAGE GENERATION")
    print("=" * 80)
    print(f"\n📋 Configuration:")
    print(f"   Bucket: {args.bucket}")
    print(f"   Project: {args.project}")
    print(f"   Function: {args.function}")
    print(f"   Batch size: {args.batch_size}")
    print(f"   Dry run: {args.dry_run}")
    print(f"   Region: {args.region}")
    
    # Initialize AWS clients
    s3_client = boto3.client('s3', region_name=args.region)
    lambda_client = boto3.client('lambda', region_name=args.region)
    
    # Step 1: Get existing images
    print(f"\n{'=' * 80}")
    print("STEP 1: Analyze Existing Images")
    print("=" * 80)
    existing_images = get_existing_images(s3_client, args.bucket, args.project)
    
    # Step 2: Get all prompts
    print(f"\n{'=' * 80}")
    print("STEP 2: Load All Prompts")
    print("=" * 80)
    all_prompts = get_all_prompts(s3_client, args.bucket, args.project)
    
    if not all_prompts:
        print("❌ No prompts found. Cannot proceed.")
        sys.exit(1)
    
    # Step 3: Find missing images
    print(f"\n{'=' * 80}")
    print("STEP 3: Identify Missing Images")
    print("=" * 80)
    missing_ids = find_missing_images(all_prompts, existing_images)
    
    if not missing_ids:
        print("\n✅ All images already exist! Nothing to repair.")
        sys.exit(0)
    
    print(f"\n📝 Missing images:")
    # Show first 10 and last 10
    if len(missing_ids) <= 20:
        for img_id in missing_ids:
            print(f"   - {img_id}")
    else:
        for img_id in missing_ids[:10]:
            print(f"   - {img_id}")
        print(f"   ... ({len(missing_ids) - 20} more)")
        for img_id in missing_ids[-10:]:
            print(f"   - {img_id}")
    
    # Step 4: Create batches
    print(f"\n{'=' * 80}")
    print("STEP 4: Create Batch Payloads")
    print("=" * 80)
    batches = create_batch_payloads(
        missing_ids,
        args.bucket,
        args.project,
        args.batch_size
    )
    
    # Step 5: Invoke Lambda
    print(f"\n{'=' * 80}")
    print("STEP 5: Invoke Image Generation")
    print("=" * 80)
    invoke_image_generation(lambda_client, args.function, batches, args.dry_run)
    
    # Summary
    print(f"\n{'=' * 80}")
    print("✅ REPAIR COMPLETE")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Existing images: {len(existing_images)}")
    print(f"   Missing images:  {len(missing_ids)}")
    print(f"   Batches created: {len(batches)}")
    
    if args.dry_run:
        print(f"\n⏸️  Dry run completed - no images were generated")
        print(f"   Run without --dry-run to actually generate images")
    else:
        print(f"\n🚀 Lambda invocations sent!")
        print(f"   Monitor progress with:")
        print(f"   aws logs tail /aws/lambda/{args.function} --follow")
        print(f"\n   Check final count with:")
        print(f"   aws s3 ls s3://{args.bucket}/{args.project}/images/ | wc -l")


if __name__ == '__main__':
    main()
