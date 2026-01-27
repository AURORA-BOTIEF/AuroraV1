import json
import boto3
import os
import logging
from html_to_ppt_styled import convert_html_to_pptx

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Export infographic to PowerPoint.
    
    Query Parameters:
        check_only=true: Skip generation, just return presigned URL if file exists
    
    Returns JSON with download_url for presigned S3 URL.
    """
    try:
        logger.info(f"Event: {json.dumps(event)}")
        
        path_params = event.get('pathParameters') or {}
        query_params = event.get('queryStringParameters') or {}
        project_folder = path_params.get('folder')
        check_only = query_params.get('check_only', '').lower() == 'true'
        
        if not project_folder:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Missing folder parameter'})
            }
            
        course_bucket = os.environ.get('COURSE_BUCKET', 'crewai-course-artifacts')
        filename = f"{project_folder}.pptx"
        ppt_key = f"{project_folder}/exports/{filename}"
        
        # Check-only mode: return URL if file exists (fast retry after timeout)
        if check_only:
            logger.info(f"Check-only mode: looking for {ppt_key}")
            try:
                head = s3_client.head_object(Bucket=course_bucket, Key=ppt_key)
                size_bytes = head['ContentLength']
                
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': course_bucket,
                        'Key': ppt_key,
                        'ResponseContentDisposition': f'attachment; filename="{filename}"'
                    },
                    ExpiresIn=3600
                )
                
                logger.info(f"✅ File exists, returning presigned URL")
                return {
                    'statusCode': 200,
                    'headers': cors_headers(),
                    'body': json.dumps({
                        'download_url': presigned_url,
                        'filename': filename,
                        'size_bytes': size_bytes,
                        'cached': True
                    })
                }
            except s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    return {
                        'statusCode': 404,
                        'headers': cors_headers(),
                        'body': json.dumps({'error': 'PPT not found. Please generate it first.'})
                    }
                raise
        
        # Full generation mode
        html_key = f"{project_folder}/infographics/infographic_final.html"
        logger.info(f"Downloading HTML from {html_key}")
        
        try:
            html_obj = s3_client.get_object(Bucket=course_bucket, Key=html_key)
            html_content = html_obj['Body'].read().decode('utf-8')
        except s3_client.exceptions.NoSuchKey:
            logger.error(f"HTML file not found: {html_key}")
            return {
                'statusCode': 404,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Infographic HTML not found. Please generate it first.'})
            }

        # Convert to PPT
        logger.info("Converting HTML to PPT with style mapping...")
        pptx_bytes = convert_html_to_pptx(html_content, s3_client=s3_client, course_bucket=course_bucket)
        
        # Upload PPT to S3
        logger.info(f"Uploading PPT to S3: {ppt_key} ({len(pptx_bytes)} bytes)")
        s3_client.put_object(
            Bucket=course_bucket,
            Key=ppt_key,
            Body=pptx_bytes,
            ContentType='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            ContentDisposition=f'attachment; filename="{filename}"'
        )
        
        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': course_bucket,
                'Key': ppt_key,
                'ResponseContentDisposition': f'attachment; filename="{filename}"'
            },
            ExpiresIn=3600
        )
        
        logger.info(f"✅ PPT uploaded, presigned URL generated")
        
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'download_url': presigned_url,
                'filename': filename,
                'size_bytes': len(pptx_bytes)
            })
        }

    except Exception as e:
        logger.error(f"Error exporting PPT: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Content-Type': 'application/json'
    }

