#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    """
    Lambda handler for listing available infographic presentations.
    
    Returns a list of projects that have infographics with metadata.
    """
    try:
        print("--- Listing Infographic Presentations ---")
        
        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')
        
        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
        
        # Parse query parameters for pagination
        query_params = event.get('queryStringParameters') or {}
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 20))
        
        # List all project folders (common prefixes)
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Delimiter='/',
            Prefix=''
        )
        
        infographics = []
        excluded_folders = {'PPT_Templates', 'logo', 'uploads', 'images', 'book'}
        
        if 'CommonPrefixes' in response:
            for prefix_obj in response['CommonPrefixes']:
                project_folder = prefix_obj['Prefix'].rstrip('/')
                
                # Filter excluded folders
                if project_folder in excluded_folders or project_folder.startswith('.'):
                    continue
                
                # Check if this project has an infographic
                infographic_data = check_for_infographic(s3_client, bucket_name, project_folder)
                
                if infographic_data:
                    # Extract creation date from folder name (YYMMDD-...)
                    creation_date = extract_date_from_folder(project_folder)
                    
                    # Get course title from infographic structure (primary source)
                    # If not available, try outline.yaml, then metadata, then folder name
                    course_title = infographic_data.get('course_title', '')
                    description = infographic_data.get('course_description', '')
                    
                    # Always load metadata for course_topic and model_provider
                    outline_data = load_outline_data(s3_client, bucket_name, project_folder)
                    metadata = load_project_metadata(s3_client, bucket_name, project_folder)
                    
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
                    
                    if not creation_date:
                        creation_date = metadata.get('created', '')
                    
                    infographics.append({
                        'folder': project_folder,
                        'title': course_title,
                        'description': description,
                        'created': creation_date,
                        'html_url': infographic_data['html_url'],
                        'html_key': infographic_data['html_key'],
                        'structure_key': infographic_data['structure_key'],
                        'total_slides': infographic_data.get('total_slides', 0),
                        'last_modified': infographic_data.get('last_modified', ''),
                        'course_topic': metadata.get('course_topic', ''),
                        'model_provider': metadata.get('model_provider', 'bedrock')
                    })
        
        # Sort infographics by creation date (newest first)
        infographics.sort(key=lambda x: x.get('last_modified') or x.get('created') or '', reverse=True)
        
        # Calculate pagination
        total_count = len(infographics)
        total_pages = (total_count + limit - 1) // limit
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        paginated_infographics = infographics[start_idx:end_idx]
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps({
                "infographics": paginated_infographics,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            })
        }
        
        print(f"--- Found {total_count} infographics, returning page {page} with {len(paginated_infographics)} items ---")
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

def check_for_infographic(s3_client, bucket_name, project_folder):
    """Check if the project has an infographic and return its metadata."""
    try:
        # Check for HTML file
        html_key = f"{project_folder}/infographics/infographic_final.html"
        structure_key = f"{project_folder}/infographics/infographic_structure.json"
        
        # Check if HTML exists
        try:
            html_response = s3_client.head_object(Bucket=bucket_name, Key=html_key)
            html_exists = True
            last_modified = html_response['LastModified'].isoformat()
        except:
            html_exists = False
            last_modified = ''
        
        if not html_exists:
            return None
        
        # Try to get structure metadata including course title
        total_slides = 0
        course_title = ''
        course_description = ''
        try:
            structure_response = s3_client.get_object(Bucket=bucket_name, Key=structure_key)
            structure_data = json.loads(structure_response['Body'].read().decode('utf-8'))
            total_slides = structure_data.get('total_slides', len(structure_data.get('slides', [])))
            course_title = structure_data.get('course_title', '')
            
            # Get description from course_metadata if available
            course_metadata = structure_data.get('course_metadata', {})
            course_description = course_metadata.get('description', '')
        except:
            # Structure file doesn't exist, that's okay
            pass
        
        # Generate presigned URL for HTML (valid for 1 hour)
        html_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': html_key},
            ExpiresIn=3600
        )
        
        return {
            'html_url': html_url,
            'html_key': html_key,
            'structure_key': structure_key,
            'total_slides': total_slides,
            'last_modified': last_modified,
            'course_title': course_title,
            'course_description': course_description
        }
        
    except Exception as e:
        print(f"Error checking infographic for {project_folder}: {e}")
        return None

def extract_date_from_folder(folder_name):
    """Extract date from folder name if it starts with YYMMDD."""
    import re
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
