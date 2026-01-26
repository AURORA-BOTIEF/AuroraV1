import json
import boto3
import os
import base64
import logging
from html_to_ppt_converter import convert_html_to_pptx_new

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Export infographic to PowerPoint.
    
    Path Parameters:
        folder: The project folder name
        
    Returns:
        Binary PPTX file
    """
    try:
        logger.info(f"Event: {json.dumps(event)}")
        
        # Extract folder from path parameters
        path_params = event.get('pathParameters') or {}
        project_folder = path_params.get('folder')
        
        if not project_folder:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing folder parameter'})
            }
            
        course_bucket = os.environ.get('COURSE_BUCKET', 'crewai-course-artifacts')
        
        # Load Final HTML
        html_key = f"{project_folder}/infographics/infographic_final.html"
        logger.info(f"Downloading HTML from {html_key}")
        
        try:
            html_obj = s3_client.get_object(Bucket=course_bucket, Key=html_key)
            html_content = html_obj['Body'].read().decode('utf-8')
        except s3_client.exceptions.NoSuchKey:
            logger.error(f"HTML file not found: {html_key}")
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Infographic HTML not found. Please generate it first.'})
            }
            
        # Load Structure (for metadata/colors)
        structure_key = f"{project_folder}/infographics/infographic_structure.json"
        logger.info(f"Downloading Structure from {structure_key}")
        
        try:
            structure_obj = s3_client.get_object(Bucket=course_bucket, Key=structure_key)
            structure = json.loads(structure_obj['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            logger.warning(f"Structure file not found: {structure_key}. Using empty structure.")
            structure = {}

        # Convert to PPT
        logger.info("Converting HTML to PPT...")
        pptx_bytes = convert_html_to_pptx_new(
            html_content=html_content,
            structure=structure,
            course_bucket=course_bucket,
            project_folder=project_folder,
            s3_client=s3_client
        )
        
        # Encode binary data to base64 for API Gateway
        pptx_base64 = base64.b64encode(pptx_bytes).decode('utf-8')
        
        filename = f"{project_folder}.pptx"
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization'
            },
            'body': pptx_base64,
            'isBase64Encoded': True
        }

    except Exception as e:
        logger.error(f"Error exporting PPT: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
