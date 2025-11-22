#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3

def lambda_handler(event, context):
    """
    Lambda handler for getting infographic details and structure.
    
    Parameters (path or query):
    - project_folder: The project folder name
    
    Returns:
    - HTML content URL (presigned)
    - Structure JSON with all slides
    - Image URL mappings
    """
    try:
        print("--- Getting Infographic Details ---")
        
        # Get project folder from path or query parameters
        path_params = event.get('pathParameters') or {}
        query_params = event.get('queryStringParameters') or {}
        
        project_folder = path_params.get('folder') or query_params.get('folder')
        
        if not project_folder:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
                },
                "body": json.dumps({"error": "Missing 'folder' parameter"})
            }
        
        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')
        
        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
        
        # Get structure JSON
        structure_key = f"{project_folder}/infographics/infographic_structure.json"
        html_key = f"{project_folder}/infographics/infographic_final.html"
        
        try:
            structure_response = s3_client.get_object(Bucket=bucket_name, Key=structure_key)
            structure_data = json.loads(structure_response['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "OPTIONS,GET"
                },
                "body": json.dumps({"error": f"Infographic not found for project: {project_folder}"})
            }
        
        # Generate presigned URLs for HTML and images
        html_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': html_key},
            ExpiresIn=3600  # 1 hour
        )
        
        # Generate presigned URLs for all images in the mapping
        image_url_mapping = structure_data.get('image_url_mapping', {})
        presigned_image_mapping = {}
        
        for alt_text, s3_url in image_url_mapping.items():
            try:
                # Parse S3 URL to get bucket and key
                if 's3.amazonaws.com' in s3_url or s3_url.startswith('s3://'):
                    if s3_url.startswith('s3://'):
                        parts = s3_url.replace('s3://', '').split('/', 1)
                        img_bucket = parts[0]
                        img_key = parts[1] if len(parts) > 1 else ''
                    elif '.s3.amazonaws.com' in s3_url:
                        parts = s3_url.split('.s3.amazonaws.com/')
                        img_bucket = parts[0].split('//')[-1]
                        img_key = parts[1]
                    else:
                        parts = s3_url.replace('https://s3.amazonaws.com/', '').split('/', 1)
                        img_bucket = parts[0]
                        img_key = parts[1] if len(parts) > 1 else ''
                    
                    # Generate presigned URL
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': img_bucket, 'Key': img_key},
                        ExpiresIn=3600
                    )
                    presigned_image_mapping[alt_text] = presigned_url
                else:
                    # Not an S3 URL, keep as is
                    presigned_image_mapping[alt_text] = s3_url
            except Exception as e:
                print(f"Error generating presigned URL for {alt_text}: {e}")
                presigned_image_mapping[alt_text] = s3_url
        
        # Update structure with presigned URLs
        structure_data['image_url_mapping'] = presigned_image_mapping
        structure_data['html_url'] = html_url
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,GET,PUT"
            },
            "body": json.dumps(structure_data)
        }
        
        print(f"--- Successfully retrieved infographic for {project_folder} ---")
        return response
        
    except Exception as e:
        error_msg = f"Error getting infographic: {str(e)}"
        print(f"ERROR: {error_msg}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,GET"
            },
            "body": json.dumps({
                "error": error_msg,
                "request_id": context.aws_request_id if context else "unknown"
            })
        }
