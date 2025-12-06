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
                has_book, has_lab_guide = check_for_book(s3_client, bucket_name, project_folder)
                
                # Get course title with priority:
                # 1. outline.yaml (most authoritative)
                # 2. book structure
                # 3. metadata.json
                # 4. folder name
                course_title = get_course_title_from_outline(s3_client, bucket_name, project_folder)
                
                if not course_title:
                    course_title = get_course_title_from_book(s3_client, bucket_name, project_folder)
                
                # Finally, fall back to metadata or folder name
                if not course_title or course_title == "Generated Course Book":
                    course_title = metadata.get('title', project_folder.split('-', 1)[1] if '-' in project_folder else project_folder)
                
                # Determine creation date with priority:
                # 1. Date from folder name (YYMMDD-...) - Most reliable for "creation"
                # 2. 'created' in metadata
                # 3. Fallback to empty string
                creation_date = extract_date_from_folder(project_folder) or metadata.get('created', '')

                projects.append({
                    'folder': project_folder,
                    'title': course_title,
                    'description': metadata.get('description', ''),
                    'created': creation_date,
                    'hasBook': has_book,
                    'hasLabGuide': has_lab_guide,
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
    """Check if the project has a completed book and/or lab guide."""
    has_book = False
    has_lab_guide = False
    
    try:
        # Check for theory book
        book_key = f"{project_folder}/book/Generated_Course_Book_data.json"
        try:
            s3_client.head_object(Bucket=bucket_name, Key=book_key)
            has_book = True
        except:
            pass
        
        # Check for lab guide
        lab_key = f"{project_folder}/book/Generated_Lab_Guide_data.json"
        try:
            s3_client.head_object(Bucket=bucket_name, Key=lab_key)
            has_lab_guide = True
        except:
            pass
            
        return has_book, has_lab_guide
    except Exception:
        return False, False

def get_course_title_from_book(s3_client, bucket_name, project_folder):
    """Extract course title from book structure JSON."""
    try:
        book_key = f"{project_folder}/book/Generated_Course_Book_data.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=book_key)
        book_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Try course_metadata first (most reliable)
        if 'course_metadata' in book_data and 'title' in book_data['course_metadata']:
            return book_data['course_metadata']['title']
        
        # Fallback to metadata
        if 'metadata' in book_data and 'title' in book_data['metadata']:
            return book_data['metadata']['title']
            
        return None
    except Exception as e:
        print(f"Could not load course title from book for {project_folder}: {e}")
        return None

def get_course_title_from_outline(s3_client, bucket_name, project_folder):
    """Extract course title from outline.yaml if available."""
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
                    # Found a YAML file, load it as text and parse manually
                    file_response = s3_client.get_object(Bucket=bucket_name, Key=key)
                    outline_content = file_response['Body'].read().decode('utf-8')
                    
                    # Try PyYAML if available
                    try:
                        import yaml
                        outline_data = yaml.safe_load(outline_content)
                        if 'course' in outline_data and 'title' in outline_data['course']:
                            return outline_data['course']['title']
                    except ImportError:
                        # PyYAML not available, parse manually with regex
                        import re
                        # Look for: course:\n  title: "Title Here"
                        match = re.search(r'course:\s*\n\s*title:\s*["\']?([^"\'\n]+)["\']?', outline_content)
                        if match:
                            return match.group(1).strip()
        
        return None
    except Exception as e:
        print(f"Error loading outline for {project_folder}: {e}")
        return None