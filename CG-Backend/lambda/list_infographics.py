#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Max parallel S3 calls (avoid throttling)
_DEFAULT_WORKERS = 16

def lambda_handler(event, context):
    """
    Lambda handler for listing available infographic presentations.
    
    Returns a list of projects that have infographics with metadata.
    """
    try:
        print("--- Listing Infographic Presentations (Two-Phase Optimization) ---")
        
        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')
        
        # Parse query parameters for pagination
        query_params = event.get('queryStringParameters') or {}
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 20))
        max_workers = min(
            int(os.getenv("LIST_INFOGRAPHICS_MAX_WORKERS", str(_DEFAULT_WORKERS))),
            32,
        )
        
        # Initialize S3 client with customized connection pool size
        from botocore.config import Config
        s3_config = Config(max_pool_connections=max_workers + 5)
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'), config=s3_config)
        
        # List all project folders (common prefixes)
        excluded_folders = {'PPT_Templates', 'logo', 'uploads', 'images', 'book'}
        all_folders = list_all_root_prefixes(s3_client, bucket_name, excluded_folders)
        print(f"--- Found {len(all_folders)} folders in S3 ---")
        
        # Phase 1: Filter out folders that have infographics using lightweight HEAD checks
        infographics_found = filter_folders_with_infographics(s3_client, bucket_name, all_folders, max_workers)
        print(f"--- Found {len(infographics_found)} valid infographics ---")
        
        # Sort infographics by creation date or last modified (newest first)
        infographics_found.sort(key=lambda x: x.get('last_modified') or x.get('created') or '', reverse=True)
        
        # Calculate pagination
        total_count = len(infographics_found)
        total_pages = (total_count + limit - 1) // limit
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        page_items = infographics_found[start_idx:end_idx]
        print(f"--- Paginating: page {page} with {len(page_items)} folders ---")
        
        # Phase 2: Enrich ONLY the items on the current page
        enriched_infographics = enrich_page_items(s3_client, bucket_name, page_items, max_workers)
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps({
                "infographics": enriched_infographics,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            })
        }
        
        print(f"--- Completed: returning {len(enriched_infographics)} items ---")
        return response
        
    except Exception as e:
        error_msg = f"Error listing infographics: {str(e)}"
        print(f"ERROR: {error_msg}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps({
                "error": error_msg,
                "request_id": context.aws_request_id if context else "unknown"
            })
        }

def list_all_root_prefixes(s3_client, bucket_name, excluded_folders):
    """All top-level folder names under the bucket (follows continuation token)."""
    prefixes = []
    token = None
    while True:
        kwargs = {
            "Bucket": bucket_name,
            "Delimiter": "/",
            "Prefix": "",
        }
        if token:
            kwargs["ContinuationToken"] = token
        
        resp = s3_client.list_objects_v2(**kwargs)
        for prefix_obj in resp.get("CommonPrefixes", []):
            project_folder = prefix_obj["Prefix"].rstrip("/")
            if project_folder in excluded_folders or project_folder.startswith("."):
                continue
            prefixes.append(project_folder)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return prefixes

def filter_folders_with_infographics(s3_client, bucket_name, folders, max_workers):
    """Phase 1: Filter folders to find which ones contain the infographic final HTML."""
    if not folders:
        return []
    workers = min(max_workers, len(folders))
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(check_infographic_exists, s3_client, bucket_name, folder): folder
            for folder in folders
        }
        for future in as_completed(futures):
            folder = futures[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"Error checking infographic existence for folder {folder}: {e}")
    return results

def check_infographic_exists(s3_client, bucket_name, project_folder):
    """Check if the project has an infographic using lightweight head_object."""
    try:
        html_key = f"{project_folder}/infographics/infographic_final.html"
        try:
            html_response = s3_client.head_object(Bucket=bucket_name, Key=html_key)
            last_modified = html_response['LastModified'].isoformat()
            return {
                'folder': project_folder,
                'last_modified': last_modified,
                'created': last_modified
            }
        except:
            return None
    except Exception as e:
        print(f"Error head-checking infographic for {project_folder}: {e}")
        return None

def enrich_page_items(s3_client, bucket_name, page_items, max_workers):
    """Phase 2: Enrich only the current page items."""
    if not page_items:
        return []
    workers = min(max_workers, len(page_items))
    results = [None] * len(page_items)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {
            executor.submit(enrich_single_infographic, s3_client, bucket_name, item): i
            for i, item in enumerate(page_items)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            item = page_items[idx]
            try:
                results[idx] = future.result()
            except Exception as e:
                print(f"Error enriching folder {item['folder']}: {e}")
                
    return [r for r in results if r is not None]

def enrich_single_infographic(s3_client, bucket_name, item):
    """Download structure/metadata details for a single presentation."""
    project_folder = item['folder']
    last_modified = item['last_modified']
    created = item['created']
    
    html_key = f"{project_folder}/infographics/infographic_final.html"
    structure_key = f"{project_folder}/infographics/infographic_structure.json"
    
    # Try to get structure metadata including course title and description
    total_slides = 0
    course_title = ''
    description = ''
    try:
        structure_response = s3_client.get_object(Bucket=bucket_name, Key=structure_key)
        structure_data = json.loads(structure_response['Body'].read().decode('utf-8'))
        total_slides = structure_data.get('total_slides', len(structure_data.get('slides', [])))
        course_title = structure_data.get('course_title', '')
        
        # Get description from course_metadata if available
        course_metadata = structure_data.get('course_metadata', {})
        description = course_metadata.get('description', '')
    except Exception as e:
        print(f"Error loading structure details for {project_folder}: {e}")
        
    # Generate presigned URL for HTML (valid for 1 hour)
    try:
        html_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': html_key},
            ExpiresIn=3600
        )
    except Exception as e:
        print(f"Error generating presigned URL for {project_folder}: {e}")
        html_url = ''
        
    # Load metadata for course_topic and model_provider
    metadata = load_project_metadata(s3_client, bucket_name, project_folder)
    
    # Try outline data ONLY if we still lack title/description
    outline_data = {}
    if not course_title or not description:
        outline_data = load_outline_data(s3_client, bucket_name, project_folder)
        
    if not course_title:
        course_title = (
            outline_data.get('course', {}).get('title') or 
            metadata.get('title') or 
            (project_folder.split('-', 1)[1] if '-' in project_folder else project_folder)
        )
    
    if not description:
        description = (
            outline_data.get('course', {}).get('description') or 
            metadata.get('description', '')
        )
        
    return {
        'folder': project_folder,
        'title': course_title,
        'description': description,
        'created': created or metadata.get('created', ''),
        'html_url': html_url,
        'html_key': html_key,
        'structure_key': structure_key,
        'total_slides': total_slides,
        'last_modified': last_modified,
        'course_topic': metadata.get('course_topic', ''),
        'model_provider': metadata.get('model_provider', 'bedrock')
    }

def extract_date_from_folder(folder_name):
    """Extract date from folder name if it starts with YYMMDD."""
    # Match YYMMDD at start of string
    match = re.match(r'^(\d{2})(\d{2})(\d{2})', folder_name)
    if match:
        year, month, day = match.groups()
        # Assume 20xx for year
        return f"20{year}-{month}-{day}"
    return None

def load_outline_data(s3_client, bucket_name, project_folder):
    """Load course outline from S3 if available."""
    try:
        # Try to import yaml - it might not be available in all Lambda environments
        import yaml
    except ImportError:
        print(f"PyYAML not available - skipping outline loading for {project_folder}")
        return {}
    
    try:
        # List files in the outline folder
        outline_prefix = f"{project_folder}/outline/"
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=outline_prefix,
            MaxKeys=10
        )
        
        # Find the first .yaml file in the outline folder
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('.yaml') or key.endswith('.yml'):
                    # Found a YAML file, load it
                    file_response = s3_client.get_object(Bucket=bucket_name, Key=key)
                    outline_content = file_response['Body'].read().decode('utf-8')
                    outline_data = yaml.safe_load(outline_content)
                    print(f"Loaded outline from: {key}")
                    return outline_data
        
        # No outline file found
        return {}
    except Exception as e:
        print(f"Error loading outline for {project_folder}: {e}")
        # Outline doesn't exist, return empty dict
        return {}

def load_project_metadata(s3_client, bucket_name, project_folder):
    """Load project metadata from S3 if available."""
    try:
        metadata_key = f"{project_folder}/metadata.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
        metadata = json.loads(response['Body'].read().decode('utf-8'))
        return metadata
    except Exception:
        # If no metadata.json, return defaults
        return {
            'title': project_folder.split('-', 1)[1] if '-' in project_folder else project_folder,
            'description': 'Presentación de curso',
            'created': extract_date_from_folder(project_folder) or '',
            'course_topic': project_folder.split('-', 1)[1] if '-' in project_folder else project_folder,
            'model_provider': 'bedrock'
        }
