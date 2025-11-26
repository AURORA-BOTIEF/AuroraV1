#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3
import logging # Added logging import

def lambda_handler(event, context):
    print("DEBUG: STARTING LAMBDA HANDLER")
    print(f"DEBUG: Event received: {json.dumps(event)}")
    
    try:
        # Check if we can import dependencies
        import boto3
        print("DEBUG: boto3 imported successfully")
        
        # Setup logging
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        logger.info("Received event: " + json.dumps(event))
        
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
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': "Missing 'project_folder' or 'structure' in request body"})
            }
        
        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')
        
        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
        
        # Import HTML generator
        import sys
        sys.path.insert(0, '/opt/python')  # Lambda layer path
        sys.path.insert(0, os.path.dirname(__file__))
        
        from html_first_generator import generate_html_output as html_generator_generate_html_output
        
        # Extract data from structure
        slides = updated_structure.get('slides', [])
        style = updated_structure.get('style', 'professional') # Changed from 'modern' in diff, keeping original
        image_url_mapping = updated_structure.get('image_url_mapping', {})
        course_title = updated_structure.get('course_title', 'Course Presentation')
        
        # Get existing HTML content
        html_key = f"{project_folder}/infographics/infographic_final.html"
        try:
            html_response = s3_client.get_object(Bucket=bucket_name, Key=html_key)
            existing_html = html_response['Body'].read().decode('utf-8')
            logger.info(f"Found existing HTML for {html_key}")
        except s3_client.exceptions.NoSuchKey:
            # Fallback if no HTML exists (shouldn't happen in editor flow)
            logger.warning(f"No existing HTML found at {html_key}, falling back to full regeneration")
            existing_html = None
        except Exception as e:
            logger.error(f"Error retrieving existing HTML for {html_key}: {e}")
            existing_html = None

        html_content = ""
        if existing_html:
            # PATCH EXISTING HTML
            try:
                from html_patcher import patch_html_content
                logger.info("Patching existing HTML content...")
                updated_html = patch_html_content(
                    existing_html=existing_html, 
                    updated_slides=slides,
                    image_mapping=image_url_mapping
                )
                html_content = updated_html
            except ImportError as ie:
                logger.error(f"Failed to import html_patcher: {ie}")
                # Fallback to regeneration if patching fails due to import error
                logger.warning("Falling back to regeneration due to import error")
                html_content = html_generator_generate_html_output(
                    slides=slides,
                    style=style,
                    image_url_mapping=image_url_mapping,
                    course_title=course_title
                )
        else:
            # Fallback to regeneration (legacy path)
            logger.info("Regenerating HTML content (fallback)...")
            html_content = html_generator_generate_html_output(
                slides=slides,
                style=style,
                image_url_mapping=image_url_mapping,
                course_title=course_title
            )
            
        # Save updated HTML to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=html_key,
            Body=html_content.encode('utf-8'),
            ContentType='text/html',
            CacheControl='no-cache' # Added CacheControl
        )
        logger.info(f"Updated HTML saved to s3://{bucket_name}/{html_key}")

        # Save updated structure to S3
        structure_key = f"{project_folder}/infographics/infographic_structure.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=structure_key,
            Body=json.dumps(updated_structure, indent=2, ensure_ascii=False),
            ContentType='application/json',
            CacheControl='no-cache' # Added CacheControl
        )
        logger.info(f"Updated structure saved to s3://{bucket_name}/{structure_key}")
        
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
