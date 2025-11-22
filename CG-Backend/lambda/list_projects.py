#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    """
    Lambda handler for listing available course projects.

    Returns a list of projects with their metadata for the Book Builder interface.
    """
    try:
        print("--- Listing Projects ---")

        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')

        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

        # Parse query parameters for pagination
        query_params = event.get('queryStringParameters') or {}
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 10))
        
        # List all project folders (common prefixes)
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Delimiter='/',
            Prefix=''
        )

        projects = []
        excluded_folders = {'PPT_Templates', 'logo', 'uploads', 'images', 'book'}

        if 'CommonPrefixes' in response:
            for prefix_obj in response['CommonPrefixes']:
                project_folder = prefix_obj['Prefix'].rstrip('/')
                
                # Filter excluded folders
                if project_folder in excluded_folders or project_folder.startswith('.'):
                    continue

                # Try to load project metadata
                metadata = load_project_metadata(s3_client, bucket_name, project_folder)

                # Check if this project has a book
                has_book = check_for_book(s3_client, bucket_name, project_folder)
                
                # Determine creation date with priority:
                # 1. Date from folder name (YYMMDD-...) - Most reliable for "creation"
                # 2. 'created' in metadata
                # 3. Fallback to empty string
                creation_date = extract_date_from_folder(project_folder) or metadata.get('created', '')

                projects.append({
                    'folder': project_folder,
                    'title': metadata.get('title', project_folder.split('-', 1)[1] if '-' in project_folder else project_folder),
                    'description': metadata.get('description', ''),
                    'created': creation_date,
                    'hasBook': has_book,
                    'lessonCount': metadata.get('lessonCount', 0),
                    'course_topic': metadata.get('course_topic', ''),
                    'model_provider': metadata.get('model_provider', 'bedrock')
                })

        # Sort projects by creation date (newest first)
        projects.sort(key=lambda x: x.get('created') or '', reverse=True)
        
        # Calculate pagination
        total_count = len(projects)
        total_pages = (total_count + limit - 1) // limit
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        paginated_projects = projects[start_idx:end_idx]

        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps({
                "projects": paginated_projects,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            })
        }

        print(f"--- Found {total_count} projects, returning page {page} with {len(paginated_projects)} items ---")
        return response

    except Exception as e:
        error_msg = f"Error listing projects: {str(e)}"
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

def load_project_metadata(s3_client, bucket_name, project_folder):
    """Load project metadata from S3 if available, or count lessons."""
    try:
        metadata_key = f"{project_folder}/metadata.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
        metadata = json.loads(response['Body'].read().decode('utf-8'))
        return metadata
    except Exception:
        # If no metadata.json, count lesson files
        try:
            lessons_prefix = f"{project_folder}/lessons/"
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=lessons_prefix,
                MaxKeys=100  # Limit to avoid too many requests
            )
            lesson_count = 0
            if 'Contents' in response:
                lesson_count = len([obj for obj in response['Contents'] if obj['Key'].endswith('.md')])

            return {
                'title': project_folder.split('-', 1)[1] if '-' in project_folder else project_folder,
                'description': f'Course project with {lesson_count} lessons',
                'created': extract_date_from_folder(project_folder) or '',
                'lessonCount': lesson_count,
                'course_topic': project_folder.split('-', 1)[1] if '-' in project_folder else project_folder,
                'model_provider': 'bedrock'
            }
        except Exception:
            return {
                'title': project_folder.split('-', 1)[1] if '-' in project_folder else project_folder,
                'description': 'Course project',
                'created': extract_date_from_folder(project_folder) or '',
                'lessonCount': 0,
                'course_topic': project_folder.split('-', 1)[1] if '-' in project_folder else project_folder,
                'model_provider': 'bedrock'
            }

def check_for_book(s3_client, bucket_name, project_folder):
    """Check if the project has a completed book."""
    try:
        # Check for book files
        book_prefix = f"{project_folder}/book/"
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=book_prefix,
            MaxKeys=1
        )
        return 'Contents' in response and len(response['Contents']) > 0
    except Exception:
        return False