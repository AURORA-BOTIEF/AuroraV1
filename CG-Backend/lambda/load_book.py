#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    """
    Lambda handler for loading book data for the Book Editor interface.

    Returns book content and metadata for editing.
    """
    try:
        print("--- Loading Book Data ---")

        # Extract project folder and book type from path parameters or query parameters
        path_params = event.get('pathParameters', {})
        query_params = event.get('queryStringParameters', {})

        project_folder = path_params.get('projectFolder') or query_params.get('projectFolder')
        book_type = query_params.get('bookType') or 'theory'  # 'theory' or 'lab'
        
        print(f"Project: {project_folder}, Book Type: {book_type}")

        if not project_folder:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
                },
                "body": json.dumps({
                    "error": "projectFolder parameter is required"
                })
            }

        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')

        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
        cw_client = boto3.client('cloudwatch', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

        book_data = None
        book_content = None

        # Prepare response data early so we can add presigned URLs without reassigning
        response_data = {
            "projectFolder": project_folder,
            "bucket": bucket_name,
            "hasBookData": False,
            "hasBookContent": False
        }

        # Try to discover book JSON/markdown keys in S3, but avoid returning large
        # object bodies directly (Lambda response size limit ~6MB). If an object
        # is small we'll inline it; otherwise we return a short presigned URL so
        # the client can download it directly from S3.
        try:
            # List files in the book folder
            book_prefix = f"{project_folder}/book/"
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=book_prefix,
                MaxKeys=50
            )

            book_json_key = None
            book_md_key = None

            if 'Contents' in response:
                # Prioritize files ending with _data.json and _complete.md
                # Filter by book_type: 'theory' looks for Generated_Course_Book, 'lab' looks for Lab_Guide
                json_files = []
                md_files = []
                
                for obj in response['Contents']:
                    key = obj['Key']
                    last_modified = obj.get('LastModified')
                    
                    # Filter based on book_type
                    if book_type == 'lab':
                        # Lab guide: Look for files with 'Lab_Guide' or 'LabGuide' in name
                        if key.endswith('_data.json') and ('Lab_Guide' in key or 'LabGuide' in key):
                            json_files.append((key, last_modified))
                        elif key.endswith('_complete.md') and ('Lab_Guide' in key or 'LabGuide' in key):
                            md_files.append((key, last_modified))
                    else:
                        # Theory book: Look for Generated_Course_Book or exclude Lab_Guide
                        if key.endswith('_data.json') and 'Lab_Guide' not in key and 'LabGuide' not in key:
                            json_files.append((key, last_modified))
                        elif key.endswith('_complete.md') and 'Lab_Guide' not in key and 'LabGuide' not in key:
                            md_files.append((key, last_modified))
                
                # Sort by last modified (most recent first) and pick the first
                if json_files:
                    json_files.sort(key=lambda x: x[1], reverse=True)
                    book_json_key = json_files[0][0]
                    print(f"Selected JSON file: {book_json_key} (from {len(json_files)} available)")
                
                if md_files:
                    md_files.sort(key=lambda x: x[1], reverse=True)
                    book_md_key = md_files[0][0]
                    print(f"Selected MD file: {book_md_key} (from {len(md_files)} available)")

            # Helper to decide whether to inline or presign
            def prepare_object(key):
                """Return either {'inline': parsed_json} or {'presignedUrl': url, 'key': key}
                depending on object size."""
                if not key:
                    return None
                try:
                    head = s3_client.head_object(Bucket=bucket_name, Key=key)
                    size = head.get('ContentLength', 0)
                    # If object is less than 800KB, inline it safely; otherwise presign
                    if size and size < 800_000:
                        obj = s3_client.get_object(Bucket=bucket_name, Key=key)
                        body = obj['Body'].read()
                        # If JSON, parse; if markdown, return text
                        if key.endswith('_data.json'):
                            try:
                                return {'inline': json.loads(body.decode('utf-8'))}
                            except Exception:
                                return {'presignedUrl': s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': key}, ExpiresIn=900), 'key': key}
                        else:
                            return {'inline': body.decode('utf-8')}
                    else:
                        url = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': key}, ExpiresIn=900)
                        return {'presignedUrl': url, 'key': key}
                except Exception as e:
                    print(f"Error preparing object {key}: {str(e)}")
                    return None

            # Prepare JSON and markdown entries
            json_entry = prepare_object(book_json_key)
            md_entry = prepare_object(book_md_key)

            if json_entry:
                if 'inline' in json_entry:
                    book_data = json_entry['inline']
                    print(f"Loaded book JSON data from: {book_json_key} (inlined)")
                else:
                    response_data['bookJsonKey'] = book_json_key
                    response_data['bookJsonUrl'] = json_entry.get('presignedUrl')
                    # Emit CloudWatch metric indicating we returned a presigned URL
                    try:
                        cw_client.put_metric_data(
                            Namespace='Aurora/LoadBook',
                            MetricData=[
                                {
                                    'MetricName': 'PresignedUrlsReturned',
                                    'Dimensions': [
                                        {'Name': 'Type', 'Value': 'JSON'}
                                    ],
                                    'Value': 1.0,
                                    'Unit': 'Count'
                                }
                            ]
                        )
                    except Exception as me:
                        print(f"Failed to emit CloudWatch metric for JSON presign: {str(me)}")
                    print(f"Provided presigned URL for JSON: {book_json_key}")

            if md_entry:
                if 'inline' in md_entry:
                    book_content = md_entry['inline']
                    print(f"Loaded book markdown from: {book_md_key} (inlined)")
                else:
                    response_data['bookMdKey'] = book_md_key
                    response_data['bookMdUrl'] = md_entry.get('presignedUrl')
                    # Emit CloudWatch metric indicating we returned a presigned URL
                    try:
                        cw_client.put_metric_data(
                            Namespace='Aurora/LoadBook',
                            MetricData=[
                                {
                                    'MetricName': 'PresignedUrlsReturned',
                                    'Dimensions': [
                                        {'Name': 'Type', 'Value': 'Markdown'}
                                    ],
                                    'Value': 1.0,
                                    'Unit': 'Count'
                                }
                            ]
                        )
                    except Exception as me:
                        print(f"Failed to emit CloudWatch metric for Markdown presign: {str(me)}")
                    print(f"Provided presigned URL for markdown: {book_md_key}")

        except Exception as e:
            print(f"Error loading book files: {str(e)}")

        # If neither exists, return error
        if not book_data and not book_content and not response_data.get('bookJsonUrl') and not response_data.get('bookMdUrl'):
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
                },
                "body": json.dumps({
                    "error": "No book data found for this project"
                })
            }

        # Update presence flags and include inlined content if available
        response_data['hasBookData'] = book_data is not None
        response_data['hasBookContent'] = book_content is not None

        if book_data:
            response_data["bookData"] = book_data

        if book_content:
            response_data["bookContent"] = book_content

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps(response_data)
        }

    except Exception as e:
        error_msg = f"Error loading book data: {str(e)}"
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

