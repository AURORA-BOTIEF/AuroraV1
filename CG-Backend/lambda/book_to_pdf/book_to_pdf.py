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
    <meta charset="UTF-8">
    <style>
        @page {
            size: a4 portrait;
            margin: 2cm;
        }

        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 12px;
            line-height: 1.6;
            color: #333;
        }

        /* Title Page */
        .title-page {
            text-align: center;
            padding-top: 5cm;
            page-break-after: always;
        }

        .logo-large {
            max-width: 200px;
            margin-bottom: 2cm;
        }

        .course-title {
            font-size: 28px;
            font-weight: bold;
            color: #1a237e;
            margin-bottom: 1cm;
        }

        .date-section {
            margin-top: 5cm;
            color: #555;
            font-size: 14px;
            font-weight: bold;
        }

        /* About/Meta Pages */
        .about-page {
            page-break-after: always;
        }

        .about-page h1 {
            color: #1a237e;
            border-bottom: 2px solid #1a237e;
            padding-bottom: 0.3cm;
        }

        .meta-section {
            margin-bottom: 1cm;
        }

        .meta-label {
            font-weight: bold;
            color: #1a237e;
            display: block;
            margin-bottom: 0.2cm;
        }

        /* IP Page */
        .ip-content {
            margin-top: 5cm;
            text-align: justify;
            font-size: 11px;
            line-height: 2;
        }

        /* Content */
        .module-break {
            page-break-before: always;
        }

        h1 {
            color: #1a237e;
            font-size: 20px;
            -pdf-keep-with-next: true;
        }

        h2 {
            color: #303f9f;
            font-size: 16px;
            -pdf-keep-with-next: true;
        }

        h3, h4, h5, h6 {
            -pdf-keep-with-next: true;
        }

        .lesson-content {
            margin-bottom: 1cm;
        }

        .lesson-content img {
            max-width: 100%;
            height: auto;
        }

        code, pre {
            background-color: #f5f5f5;
            padding: 2px 4px;
            font-family: monospace;
            font-size: 10px;
        }

        pre {
            padding: 10px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1cm 0;
        }

        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }

        th {
            background-color: #1a237e;
            color: white;
        }

        ul, ol {
            margin-left: 1cm;
        }

    </style>
</head>
<body>
    <!-- Title Page -->
    <div class="title-page">
        {% if logo_path %}
        <img src="{{ logo_path }}" class="logo-large" />
        {% endif %}
        
        <div class="course-title">{{ title }}</div>
        
        <div class="date-section">{{ date }}</div>
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

    <!-- Objectives Page -->
    {% if objectives %}
    <div class="about-page">
        <h1>Objetivos de Aprendizaje</h1>
        <ul>
        {% for obj in objectives %}
            <li>{{ obj }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    <!-- IP Page -->
    <div style="page-break-before: always;">
        <div class="ip-content">
            <p><strong>Material didáctico preparado por la empresa Global K, S.A. de C.V. Registrado en Derechos de Autor.</strong></p>
            
            <p>Todos los contenidos de este Sitio (incluyendo, pero no limitado a: texto, logotipos, contenido, fotografías, audio, botones, nombres comerciales y videos) están sujetos a derechos de propiedad por las leyes de Derechos de Autor de la empresa Global K, S.A. de C.V.</p>
            
            <p>Queda prohibido copiar, reproducir, distribuir, publicar, transmitir, difundir, o en cualquier modo explotar cualquier parte de este documento sin la autorización previa por escrito de Global K, S.A. de C.V. o de los titulares correspondientes.</p>
        </div>
    </div>

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

# Updated Handler for Step Functions Execution
def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract parameters from Step Function input
    # Expected format: { "s3Key": "...", "book_data": {...}, "action": "generate" }
    
    try:
        # Default to 'generate' if not specified, compatible with direct invoke test
        action = event.get('action', 'generate')
        
        if action == 'generate':
            return generate_pdf_task(event)
        else:
            raise ValueError(f"Unknown action: {action}")

    except Exception as e:
        logger.error(f"Error in PDF Task: {str(e)}", exc_info=True)
        # return error to Step Function Catch block
        raise e

def generate_pdf_task(payload):
    s3_key = payload.get('s3Key')
    bucket_name = payload.get('course_bucket') or os.environ.get('COURSE_BUCKET', 'crewai-course-artifacts')
    
    if not s3_key:
        raise ValueError("Missing s3Key")

    # Create a compatible event for handle_worker
    # handle_worker expects: jobId, s3Key, statusKey, bucketName
    # We create synthetic values since we're running in Step Functions mode
    job_id = f"sf-job-{uuid.uuid4()}"
    status_key = s3_key.replace('.json', '_sf_status.json')  # Dummy key, SF tracks status
    
    worker_event = {
        'jobId': job_id,
        's3Key': s3_key,
        'statusKey': status_key,
        'bucketName': bucket_name
    }
    
    logger.info(f"Calling handle_worker with: {json.dumps(worker_event)}")
    
    # Call the existing worker logic
    result = handle_worker(worker_event)
    
    # handle_worker returns {'status': 'success'} and writes to S3
    # We need to read back the status to get the downloadUrl
    status_response = s3.get_object(Bucket=bucket_name, Key=status_key)
    status_data = json.loads(status_response['Body'].read().decode('utf-8'))
    
    return {
        'statusCode': 200,
        'status': status_data.get('status', 'completed'),
        's3Key': s3_key.replace('.json', '.pdf'),
        'downloadUrl': status_data.get('downloadUrl'),
        'metadata': {}
    }

# Deprecated/Removed: handle_start, handle_check, cors_response


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
            # SEARCH STRATEGY 1: outline/ subdirectory
            outline_prefix = f"{project_folder}/outline/"
            logger.info(f"Searching for outline in s3://{bucket_name}/{outline_prefix}")
            
            list_resp = s3.list_objects_v2(Bucket=bucket_name, Prefix=outline_prefix)
            outline_key = None
            
            if 'Contents' in list_resp:
                for obj in list_resp['Contents']:
                    if obj['Key'].lower().endswith(('.yaml', '.yml')):
                        outline_key = obj['Key']
                        break
            
            # SEARCH STRATEGY 2: Project root (fallback)
            if not outline_key:
                logger.info(f"Not found in outline/. Searching root: s3://{bucket_name}/{project_folder}/")
                list_resp_root = s3.list_objects_v2(Bucket=bucket_name, Prefix=f"{project_folder}/")
                if 'Contents' in list_resp_root:
                    for obj in list_resp_root['Contents']:
                        if obj['Key'].lower().endswith(('.yaml', '.yml')):
                            outline_key = obj['Key']
                            break

            if outline_key:
                logger.info(f"Found outline file: {outline_key}")
                outline_res = s3.get_object(Bucket=bucket_name, Key=outline_key)
                outline_data = yaml.safe_load(outline_res['Body'].read())
                
                # Helper to look deeply
                course_section = outline_data.get('course', {})
                if not isinstance(course_section, dict):
                     course_section = {}

                # 1. Title (Clean it)
                raw_title = (
                    outline_data.get('course_title') or
                    outline_data.get('title') or
                    outline_data.get('name') or
                    course_section.get('title') or
                    course_section.get('course_title') or
                    'Curso Netec'
                )
                # Remove "CURSO:" prefix if present (case insensitive)
                course_meta['title'] = re.sub(r'^CURSO:\s*', '', raw_title, flags=re.IGNORECASE)

                # 2. Description
                course_meta['description'] = (
                    outline_data.get('description') or
                    course_section.get('description') or
                    ''
                )

                # 3. Audience
                course_meta['audience'] = (
                    outline_data.get('target_audience') or
                    outline_data.get('audience') or
                    course_section.get('target_audience') or
                    course_section.get('audience') or
                    ''
                )

                # 4. Prerequisites
                course_meta['prerequisites'] = (
                    outline_data.get('prerequisites') or
                    course_section.get('prerequisites') or
                    ''
                )
                
                # 5. Objectives (New)
                course_meta['objectives'] = (
                    outline_data.get('learning_outcomes') or
                    outline_data.get('learning_objectives') or
                    outline_data.get('objectives') or
                    course_section.get('learning_outcomes') or
                    course_section.get('learning_objectives') or
                    course_section.get('objectives') or
                    []
                )
                if isinstance(course_meta['objectives'], str):
                     course_meta['objectives'] = [course_meta['objectives']]
                        
                logger.info(f"Metadata extracted: {course_meta['title']}")
            else:
                logger.warning("No outline .yaml/.yml file found in project or outline/ folder")

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
            # 1. HEADERS (Handled via CSS h1-h6)
            # We removed all regex-based paragraph heuristics (bold text, ends-with-colon) 
            # because they caused improper infinite loops in xhtml2pdf when content overflowed a page.
            
            def add_keep_with_next(match):
                # Utility kept if needed for future, but currently unused for paragraphs
                tag = match.group(0)
                if 'style="' in tag:
                    if '-pdf-keep-with-next' not in tag:
                        return tag.replace('style="', 'style="-pdf-keep-with-next: true; ')
                    return tag
                else:
                    return tag.replace('<p', '<p style="-pdf-keep-with-next: true;"')

            # 1. Ends with :  <-- REMOVED to prevent infinite loops
            # clean_html = re.sub(r'<p[^>]*>.*?:(?:<[^>]+>)*</p>', add_keep_with_next, clean_html, flags=re.DOTALL)
            
            # Removed aggressive "bold text" heuristic to prevent pagination infinite loops.
            # Relying on H1-H6 and colon-ending paragraphs is safer.

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
