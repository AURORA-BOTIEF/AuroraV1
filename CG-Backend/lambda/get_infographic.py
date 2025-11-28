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
    print(f"Event received: {json.dumps(event)}")
    
    # Handle OPTIONS preflight request for CORS
    if event.get('httpMethod') == 'OPTIONS':
        print("Handling OPTIONS preflight request")
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,OPTIONS"
            },
            "body": ""
        }

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
        
        # Fetch HTML content from S3 and return direct S3 URLs
        # Frontend will use Cognito IAM credentials to fetch images
        print(f"Fetching HTML from s3://{bucket_name}/{html_key}")
        try:
            html_response = s3_client.get_object(Bucket=bucket_name, Key=html_key)
            html_content = html_response['Body'].read().decode('utf-8')
            print(f"✓ HTML fetched successfully, size: {len(html_content)} bytes")
        except s3_client.exceptions.NoSuchKey:
            print(f"✗ HTML file not found: {html_key}")
            html_content = "<html><body><h1>HTML file not found</h1></body></html>"
        
        # Return HTML as-is with direct S3 URLs for Cognito IAM access
        structure_data['html_content'] = html_content
        
        # Remove html_url since we're returning content directly
        if 'html_url' in structure_data:
            del structure_data['html_url']
        
        print(f"Response contains keys: {list(structure_data.keys())}")
        print(f"Returning HTML with direct S3 URLs for Cognito IAM access")
        
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
