import json
import os
import boto3
import logging
import base64
from io import BytesIO
from xhtml2pdf import pisa
from jinja2 import Template
import markdown

import datetime
import uuid

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')

# ... (PDF_TEMPLATE remains same) ...

def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # ----------------------------------------
        # 0. HANDLE WORKER MODE (Async Execution)
        # ----------------------------------------
        if event.get('mode') == 'worker':
            return handle_worker(event)

        # ----------------------------------------
        # 1. HANDLE API GATEWAY REQUESTS
        # ----------------------------------------
        
        # A. CORS Preflight (OPTIONS)
        if event.get('httpMethod') == 'OPTIONS':
            return cors_response(200, '')

        # B. Parse Body (Handle Base64)
        is_base64 = event.get('isBase64Encoded', False)
        raw_body = event.get('body', '{}')
        if is_base64 and raw_body:
            raw_body = base64.b64decode(raw_body).decode('utf-8')
        
        body = json.loads(raw_body)
        action = body.get('action', 'start') # Default to start
        
        if action == 'check':
            return handle_check(body)
        else:
            return handle_start(body, context)

    except Exception as e:
        logger.error(f"Error in dispatcher: {str(e)}", exc_info=True)
        return cors_response(500, json.dumps({'error': str(e)}))

def cors_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization'
        },
        'body': body
    }

def get_status_key(s3_key):
    # s3Key = "folder/exports/file.json"
    # statusKey = "folder/exports/file_status.json"
    # But checking by JobId is safer if we pass JobId.
    # Let's assume we store status next to the export
    return s3_key.replace('.json', '_status.json')

def handle_start(body, context):
    s3_key = body.get('s3Key')
    bucket_name = os.environ.get('COURSE_BUCKET', 'crewai-course-artifacts')
    
    if not s3_key:
        return cors_response(400, json.dumps({'error': 'Missing s3Key'}))

    # Generate Job ID
    job_id = str(uuid.uuid4())
    
    # Define a clean status file path. 
    # Use a hashed filename or separate folder? 
    # Let's put it in exports/jobs/{job_id}.json
    # OR simpler: Use the s3Key base but with job_id
    # "exports/JOB_{jobId}.json"
    status_key = os.path.dirname(s3_key) + f"/JOB_{job_id}.json"

    # Init Status
    status_data = {
        'jobId': job_id,
        'status': 'processing',
        'startTime': str(datetime.datetime.now()),
        's3Key': s3_key # Original input
    }
    s3.put_object(
        Bucket=bucket_name,
        Key=status_key,
        Body=json.dumps(status_data),
        ContentType='application/json'
    )

    # Invoke Worker (Self)
    payload = {
        'mode': 'worker',
        'jobId': job_id,
        's3Key': s3_key,
        'statusKey': status_key,
        'bucketName': bucket_name
    }
    
    # We need the function name. Context provides it.
    function_name = context.function_name
    
    logger.info(f"Invoking worker {function_name} for Job {job_id}")
    lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='Event', # Async
        Payload=json.dumps(payload)
    )

    return cors_response(202, json.dumps({
        'jobId': job_id,
        'message': 'PDF generation started',
        'statusKey': status_key 
    }))

def handle_check(body):
    bucket_name = os.environ.get('COURSE_BUCKET', 'crewai-course-artifacts')
    job_id = body.get('jobId')
    status_key = body.get('statusKey')
    
    # If frontend only sends jobId, we need to know the path. 
    # Frontend should ideally send statusKey returned by start.
    
    if not status_key:
         return cors_response(400, json.dumps({'error': 'Missing statusKey'}))

    try:
        response = s3.get_object(Bucket=bucket_name, Key=status_key)
        status_data = json.loads(response['Body'].read().decode('utf-8'))
        return cors_response(200, json.dumps(status_data))
    except Exception as e:
        logger.warning(f"Status check failed: {str(e)}")
        # If file missing, maybe job failed or never started
        return cors_response(404, json.dumps({'error': 'Job not found', 'details': str(e)}))

def handle_worker(event):
    job_id = event.get('jobId')
    s3_key = event.get('s3Key')
    status_key = event.get('statusKey')
    bucket_name = event.get('bucketName')
    
    logger.info(f"WORKER STARTED: Job {job_id}")
    
    try:
        # --- ORIGINAL LOGIC STARTS HERE ---
        
        # 2. Download JSON from S3
        logger.info(f"Downloading book data from s3://{bucket_name}/{s3_key}")
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        book_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # 3. Prepare Data Structure for Template
        modules_map = {}
        lessons = book_data.get('lessons', [])
        
        for idx, lesson in enumerate(lessons):
            mod_num = lesson.get('moduleNumber', 1)
            if mod_num not in modules_map:
                modules_map[mod_num] = {'number': mod_num, 'title': f"Módulo {mod_num}", 'lessons': []}
            
            raw_content = lesson.get('content', '')
            html_content = markdown.markdown(
                raw_content,
                extensions=['fenced_code', 'tables', 'nl2br']
            )
            
            modules_map[mod_num]['lessons'].append({
                'number': lesson.get('lessonNumberInModule', idx + 1),
                'title': lesson.get('title', 'Lección sin título'),
                'html_content': html_content
            })

        sorted_modules = []
        for mod_num in sorted(modules_map.keys(), key=lambda x: int(x)):
            mod = modules_map[mod_num]
            mod['lessons'].sort(key=lambda x: int(x['number']))
            sorted_modules.append(mod)

        # 4. Render HTML
        template = Template(PDF_TEMPLATE)
        render_context = {
            'title': book_data.get('title', 'Documento del Curso'),
            'type_label': 'Guía de Laboratorios' if 'lab' in s3_key.lower() else 'Libro del Curso',
            'modules': sorted_modules
        }
        pdf_html = template.render(render_context)
        
        # 5. Generate PDF
        logger.info("Generating PDF with xhtml2pdf...")
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(pdf_html, dest=pdf_buffer)
        
        if pisa_status.err:
            raise Exception("PDF generation failed with pisa error")
            
        pdf_bytes = pdf_buffer.getvalue()
        logger.info(f"PDF generated successfully. Size: {len(pdf_bytes)} bytes")

        # 6. Upload PDF to S3
        output_key = s3_key.replace('.json', '.pdf')
        s3.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=pdf_bytes,
            ContentType='application/pdf'
        )
        
        # 7. Generate Presigned URL
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': output_key},
            ExpiresIn=3600
        )
        
        # --- SUCCESS UPDATE ---
        s3.put_object(
            Bucket=bucket_name,
            Key=status_key,
            Body=json.dumps({
                'jobId': job_id,
                'status': 'completed',
                'downloadUrl': presigned_url,
                'completedAt': str(datetime.datetime.now())
            }),
            ContentType='application/json'
        )
        logger.info(f"WORKER COMPLETED: Job {job_id}")
        return {'status': 'success'}

    except Exception as e:
        logger.error(f"WORKER FAILED: {str(e)}", exc_info=True)
        # --- FAILURE UPDATE ---
        try:
            s3.put_object(
                Bucket=bucket_name,
                Key=status_key,
                Body=json.dumps({
                    'jobId': job_id,
                    'status': 'failed',
                    'error': str(e),
                    'failedAt': str(datetime.datetime.now())
                }),
                ContentType='application/json'
            )
        except:
            pass # Can't write status?
        raise e
