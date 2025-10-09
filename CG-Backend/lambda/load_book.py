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

        # Extract project folder from path parameters or query parameters
        path_params = event.get('pathParameters', {})
        query_params = event.get('queryStringParameters', {})

        project_folder = path_params.get('projectFolder') or query_params.get('projectFolder')

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

        book_data = None
        book_content = None

        # Try to load book JSON data first (look for any _data.json file)
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
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('_data.json'):
                        book_json_key = key
                    elif key.endswith('_complete.md'):
                        book_md_key = key
            
            # Load JSON data if found
            if book_json_key:
                response = s3_client.get_object(Bucket=bucket_name, Key=book_json_key)
                book_data = json.loads(response['Body'].read().decode('utf-8'))
                print(f"Loaded book JSON data from: {book_json_key}")
            
            # Load markdown content if found
            if book_md_key:
                response = s3_client.get_object(Bucket=bucket_name, Key=book_md_key)
                book_content = response['Body'].read().decode('utf-8')
                print(f"Loaded book markdown from: {book_md_key}")
                
        except Exception as e:
            print(f"Error loading book files: {str(e)}")

        # If neither exists, return error
        if not book_data and not book_content:
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

        response_data = {
            "projectFolder": project_folder,
            "bucket": bucket_name,
            "hasBookData": book_data is not None,
            "hasBookContent": book_content is not None
        }

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

