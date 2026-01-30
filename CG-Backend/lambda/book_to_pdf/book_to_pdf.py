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
        @page ip_page {
            size: a4 portrait;
            margin: 2cm;
            @frame footer_frame {
                -pdf-frame-content: footerContent;
                bottom: 1cm;
                height: 1cm;
            }
        }

        /* ... existing styles ... */
        
        /* Date Styling */
        .date-section {
            margin-top: 5cm;
            color: #555;
            font-size: 14px;
            font-weight: bold;
        }

        /* IP Page Styling */
        .ip-content {
             margin-top: 5cm;
             text-align: justify;
             font-size: 11px;
             line-height: 2;
        }

    /* ... */
    
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

    <!-- Objectives Page (New) -->
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

    <!-- IP Page (New) -->
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
    {% endfor %}"""

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
            # 1. Paragraphs ending in ':'
            # 2. Paragraphs containing bold text (likely subheaders) - STRICTER
            
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
            clean_html = re.sub(r'<p[^>]*>.*?:(?:<[^>]+>)*</p>', add_keep_with_next, clean_html, flags=re.DOTALL)
            
            # 2. Contains bold (strong/b) or color spans - typical for "Aplicación Práctica"
            # STRICTER LIMIT: < 80 chars, AND must NOT end in '.' (avoids normal sentences)
            # Matches <p ...> ... <strong> ... </p>
            clean_html = re.sub(r'<p(?![^>]*keep-with-next)(?:[^>]*?)>(?:<[^>]+>)*\s*(?:<strong|<b|<span style="color)[^>]*>.*?(?<!\.)</p>', 
                                lambda m: add_keep_with_next(m) if len(m.group(0)) < 80 else m.group(0), 
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
