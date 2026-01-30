import json
import os
import boto3
import logging
import base64
import re
from io import BytesIO
from xhtml2pdf import pisa
from jinja2 import Template
import markdown
import yaml

import datetime
import uuid

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')

# HTML Template for the PDF
# Designed to look like the "Professional" Netec style
PDF_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        @page {
            size: a4 portrait;
            margin: 2cm;
            margin-top: 3cm; /* More space for header */
            
            @frame header_frame {
                -pdf-frame-content: headerContent;
                top: 1cm;
                margin-left: 1cm;
                margin-right: 1cm;
                height: 1.5cm;
            }
            
            @frame footer_frame {
                -pdf-frame-content: footerContent;
                bottom: 1cm;
                margin-left: 1cm;
                margin-right: 1cm;
                height: 1cm;
            }
        }
        
        body {
            font-family: Helvetica, sans-serif;
            font-size: 12px;
            line-height: 1.5;
            color: #333333;
        }

        h1 {
            color: #003366;
            font-size: 24px;
            border-bottom: 2px solid #003366;
            padding-bottom: 5px;
            margin-top: 30px;
            -pdf-keep-with-next: true;
        }

        h2 {
            color: #005293;
            font-size: 18px;
            margin-top: 20px;
            border-bottom: 1px solid #ccc;
            -pdf-keep-with-next: true;
        }

        h3 {
            color: #0066cc;
            font-size: 14px;
            margin-top: 15px;
            -pdf-keep-with-next: true;
        }

        p {
            margin-bottom: 10px;
            text-align: justify;
        }

        ul, ol {
            margin-left: 20px;
            margin-bottom: 10px;
        }

        li {
            margin-bottom: 5px;
        }

        code {
            background-color: #f4f4f4;
            padding: 2px 4px;
            font-family: Courier, monospace;
            font-size: 11px;
        }

        pre {
            background-color: #f4f4f4;
            padding: 10px;
            border: 1px solid #ddd;
            font-family: Courier, monospace;
            font-size: 10px;
            white-space: pre-wrap;
            margin-bottom: 15px;
        }

        img {
            max-width: 100%;
            height: auto;
            margin: 10px 0;
        }
        
        /* Table Styling */
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 15px;
        }
        
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        
        th {
            background-color: #f2f2f2;
            color: #003366;
            font-weight: bold;
        }
        
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }

        /* Title Page */
        .title-page {
            text-align: center;
            padding-top: 4cm;
            page-break-after: always;
        }

        .logo-large {
            width: 200px;
            margin-bottom: 2cm;
        }

        .course-title {
            font-size: 32px;
            color: #003366;
            font-weight: bold;
            margin-bottom: 1cm;
        }
        
        .course-subtitle {
            font-size: 18px;
            color: #555;
            margin-bottom: 3cm;
        }
        
        /* About Page */
        .about-page {
            page-break-after: always;
        }
        
        .meta-section {
            margin-bottom: 20px;
        }
        
        .meta-label {
            color: #003366;
            font-weight: bold;
            display: block;
            margin-bottom: 5px;
            font-size: 14px;
        }

        .module-break {
            page-break-before: always;
        }

        #footerContent {
            text-align: center;
            font-size: 9px;
            color: #777;
            padding-top: 5px;
            border-top: 1px solid #eee;
        }
        
        #headerContent {
            text-align: right;
        }
        
        .logo-small {
            height: 30px;
        }
    </style>
</head>
<body>
    <div id="headerContent">
        {% if logo_path %}
        <img src="{{ logo_path }}" class="logo-small" />
        {% endif %}
    </div>

    <div id="footerContent">
        Contenido generado por IA, revisado por Netec
        <br/>
        Página <pdf:pagenumber />
    </div>

    <!-- Title Page -->
    <div class="title-page">
        {% if logo_path %}
        <img src="{{ logo_path }}" class="logo-large" />
        {% endif %}
        
        <div class="course-title">{{ title }}</div>
        
        <p style="margin-top: 5cm; color: #888;">{{ date }}</p>
    </div>
    
    <!-- About Page (Metadata) -->
    {% if description or audience or prerequisites %}
    <div class="about-page">
        <h1>Información del Curso</h1>
        
        {% if description %}
        <div class="meta-section">
            <span class="meta-label">Descripción</span>
            <p>{{ description }}</p>
        </div>
        {% endif %}
        
        {% if audience %}
        <div class="meta-section">
            <span class="meta-label">Audiencia</span>
            <p>{{ audience }}</p>
        </div>
        {% endif %}
        
        {% if prerequisites %}
        <div class="meta-section">
            <span class="meta-label">Prerrequisitos</span>
            <p>{{ prerequisites }}</p>
        </div>
        {% endif %}
    </div>
    {% endif %}

    <!-- Content -->
    {% for module in modules %}
    <div class="module-break">
        <h1>Módulo {{ module.number }}: {{ module.title }}</h1>
        
        {% for lesson in module.lessons %}
            <h2>{{ module.number }}.{{ lesson.number }} {{ lesson.title }}</h2>
            
            <div class="lesson-content">
                {{ lesson.html_content }}
            </div>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;"/>
        {% endfor %}
    </div>
    {% endfor %}
</body>
</html>
"""

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

def handle_start(body, context):
    s3_key = body.get('s3Key')
    bucket_name = os.environ.get('COURSE_BUCKET', 'crewai-course-artifacts')
    
    if not s3_key:
        return cors_response(400, json.dumps({'error': 'Missing s3Key'}))

    # Generate Job ID
    job_id = str(uuid.uuid4())
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
        # ----------------------------------------
        # 1. DOWNLOAD LOGO
        # ----------------------------------------
        local_logo_path = None
        try:
            # Try specific bucket location
            logo_key = "logo/LogoNetec.png" 
            local_logo_path = "/tmp/LogoNetec.png"
            logger.info(f"Downloading logo from s3://{bucket_name}/{logo_key}")
            s3.download_file(bucket_name, logo_key, local_logo_path)
            logger.info("Logo downloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to download logo: {e}")
            local_logo_path = None

        # ----------------------------------------
        # 2. FETCH OUTLINE & METADATA
        # ----------------------------------------
        # Structure: project_folder/outline/ANY_NAME.yaml
        project_folder = os.path.dirname(os.path.dirname(s3_key))
        
        course_meta = {
            'title': 'Documento del Curso',
            'description': '',
            'audience': '',
            'prerequisites': ''
        }
        
        try:
            # List objects in the outline folder to find the file
            outline_prefix = f"{project_folder}/outline/"
            logger.info(f"Searching for outline in s3://{bucket_name}/{outline_prefix}")
            
            list_resp = s3.list_objects_v2(Bucket=bucket_name, Prefix=outline_prefix)
            outline_key = None
            
            if 'Contents' in list_resp:
                for obj in list_resp['Contents']:
                    key = obj['Key']
                    if key.lower().endswith(('.yaml', '.yml')):
                        outline_key = key
                        break
            
            if outline_key:
                logger.info(f"Found outline file: {outline_key}")
                outline_res = s3.get_object(Bucket=bucket_name, Key=outline_key)
                outline_data = yaml.safe_load(outline_res['Body'].read())
                
                # Extract fields with multiple fallbacks
                course_meta['title'] = outline_data.get('course_title', 
                                         outline_data.get('title', 
                                           outline_data.get('name', 'Curso Netec')))
                                           
                course_meta['description'] = outline_data.get('description', '')
                course_meta['audience'] = outline_data.get('target_audience', '')
                course_meta['prerequisites'] = outline_data.get('prerequisites', '')
                
                logger.info(f"Metadata extracted: {course_meta['title']}")
            else:
                logger.warning("No outline .yaml/.yml file found in outline/ folder")

        except Exception as e:
            logger.warning(f"Failed to fetch/parse outline: {e}")

        # ----------------------------------------
        # 3. DOWNLOAD BOOK DATA
        # ----------------------------------------
        logger.info(f"Downloading book data from s3://{bucket_name}/{s3_key}")
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        book_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # 4. Prepare Data Structure for Template
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

            # Strip duplicate title from content if present
            clean_html = re.sub(r'^\s*<h[1-6]>.*?</h[1-6]>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            
            # Orphan Fix: Add keep-with-next to:
            # 1. Paragraphs ending in ':'
            # 2. Paragraphs containing bold text (likely subheaders)
            # 3. Headers (already handled by CSS, but enforcing here too)
            
            def add_keep_with_next(match):
                tag = match.group(0)
                # Check if it already has style
                if 'style="' in tag:
                    if '-pdf-keep-with-next' not in tag:
                        return tag.replace('style="', 'style="-pdf-keep-with-next: true; ')
                    return tag
                else:
                    return tag.replace('<p', '<p style="-pdf-keep-with-next: true;"')

            # 1. Ends with :
            clean_html = re.sub(r'<p>(?:<[^>]+>)*.*?:(?:<[^>]+>)*</p>', add_keep_with_next, clean_html, flags=re.DOTALL)
            
            # 2. Contains bold (strong/b) or color spans - typical for "Aplicación Práctica"
            # We limit this to short paragraphs (< 200 chars) to avoid tagging long text blocks
            clean_html = re.sub(r'<p(?![^>]*keep-with-next)(?:[^>]*?)>(?:<[^>]+>)*\s*(?:<strong|<b|<span style="color)[^>]*>.*?</p>', 
                                lambda m: add_keep_with_next(m) if len(m.group(0)) < 300 else m.group(0), 
                                clean_html, flags=re.DOTALL)

            modules_map[mod_num]['lessons'].append({
                'number': lesson.get('lessonNumberInModule', idx + 1),
                'title': lesson.get('title', 'Lección sin título'),
                'html_content': clean_html
            })

        sorted_modules = []
        for mod_num in sorted(modules_map.keys(), key=lambda x: int(x)):
            mod = modules_map[mod_num]
            mod['lessons'].sort(key=lambda x: int(x['number']))
            sorted_modules.append(mod)

        # 5. Render HTML
        # Translation map for months
        months_es = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        now = datetime.datetime.now()
        date_str = f"{months_es[now.month]} {now.year}"

        template = Template(PDF_TEMPLATE)
        render_context = {
            'logo_path': local_logo_path,
            'title': course_meta['title'],
            'description': course_meta['description'],
            'audience': course_meta['audience'],
            'prerequisites': course_meta['prerequisites'],
            'date': date_str,
            'modules': sorted_modules
        }
        pdf_html = template.render(render_context)
        
        # 6. Generate PDF
        logger.info("Generating PDF with xhtml2pdf...")
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(pdf_html, dest=pdf_buffer)
        
        if pisa_status.err:
            raise Exception("PDF generation failed with pisa error")
            
        pdf_bytes = pdf_buffer.getvalue()
        logger.info(f"PDF generated successfully. Size: {len(pdf_bytes)} bytes")

        # 7. Upload PDF to S3
        output_key = s3_key.replace('.json', '.pdf')
        s3.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=pdf_bytes,
            ContentType='application/pdf'
        )
        
        # 8. Generate Presigned URL
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
