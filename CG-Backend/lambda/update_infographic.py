#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3

def lambda_handler(event, context):
    """
    Lambda handler for updating infographic slides.
    
    Accepts updated structure JSON and regenerates the HTML.
    
    Parameters (body):
    - project_folder: The project folder name
    - structure: Updated slide structure
    """
    try:
        print("--- Updating Infographic ---")
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        project_folder = body.get('project_folder')
        updated_structure = body.get('structure')
        
        if not project_folder or not updated_structure:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "OPTIONS,PUT"
                },
                "body": json.dumps({"error": "Missing 'project_folder' or 'structure' in request body"})
            }
        
        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')
        
        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
        
        # Import HTML generator
        import sys
        sys.path.insert(0, '/opt/python')  # Lambda layer path
        sys.path.insert(0, os.path.dirname(__file__))
        
        from html_first_generator import generate_html_output
        
        # Extract data from structure
        slides = updated_structure.get('slides', [])
        style = updated_structure.get('style', 'professional')
        image_url_mapping = updated_structure.get('image_url_mapping', {})
        course_title = updated_structure.get('course_title', 'Course Presentation')
        
        # Generate new HTML
        html_content = generate_html_output(
            slides=slides,
            style=style,
            image_url_mapping=image_url_mapping,
            course_title=course_title
        )
        
        # Save updated structure to S3
        structure_key = f"{project_folder}/infographics/infographic_structure.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=structure_key,
            Body=json.dumps(updated_structure, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        # Save updated HTML to S3
        html_key = f"{project_folder}/infographics/infographic_final.html"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=html_key,
            Body=html_content.encode('utf-8'),
            ContentType='text/html'
        )
        
        # Generate presigned URL for updated HTML
        html_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': html_key},
            ExpiresIn=3600
        )
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,PUT"
            },
            "body": json.dumps({
                "message": "Infographic updated successfully",
                "html_url": html_url,
                "html_key": html_key,
                "structure_key": structure_key,
                "total_slides": len(slides)
            })
        }
        
        print(f"--- Successfully updated infographic for {project_folder} ---")
        return response
        
    except Exception as e:
        error_msg = f"Error updating infographic: {str(e)}"
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,PUT"
            },
            "body": json.dumps({
                "error": error_msg,
                "request_id": context.aws_request_id if context else "unknown"
            })
        }
