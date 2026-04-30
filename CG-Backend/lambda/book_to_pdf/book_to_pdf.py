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
# HTML Template for the PDF
# Designed to look like the "Professional" Netec style
PDF_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        /* Default Page (Used for Page 1 / Cover) - Clean, no frames */
        @page {
            size: a4 portrait;
            margin: 2cm;
        }

        /* Content Page template (Used for Page 3+) - With Header/Footer */
        @page content {
            size: a4 portrait;
            margin: 2cm;
            margin-bottom: 2.5cm;
            margin-top: 2.5cm;
            
            @frame header_frame {
                -pdf-frame-content: headerContent;
                top: 0.8cm;
                left: 2cm;
                right: 2cm;
                height: 1.5cm;
            }

            @frame footer_frame {
                -pdf-frame-content: footerContent;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                height: 1cm;
            }
        }
        
        /* Info Page template (Used for Page 2) - Custom IP Footer */
        @page info_page {
            size: a4 portrait;
            margin: 2cm;
            margin-bottom: 3cm; /* More space for IP footer */
            margin-top: 2.5cm;

            @frame header_frame {
                -pdf-frame-content: headerContent;
                top: 0.8cm;
                left: 2cm;
                right: 2cm;
                height: 1.5cm;
            }
            
            @frame ip_footer_frame {
                -pdf-frame-content: ipContent;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                height: 2.5cm; /* Taller frame for IP text */
            }
        }

        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 12px;
            line-height: 1.5;
            color: #333;
        }

        /* Title Page Styling */
        .title-page {
            text-align: center;
            padding-top: 5cm;
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

        /* Info Page Styling */
        .about-page h1 {
            color: #1a237e;
            border-bottom: 2px solid #1a237e;
            padding-bottom: 0.3cm;
        }

        .meta-section {
            margin-bottom: 0.5cm;
        }

        .meta-label {
            font-weight: bold;
            color: #1a237e;
            display: block;
            margin-bottom: 0.1cm;
        }
        
        /* IP Info Text Style */
        .ip-text {
            font-size: 9px;
            color: #666;
            text-align: justify;
            line-height: 1.3;
        }

        /* Content Styling */
        .module-break {
            page-break-before: always;
        }

        h1 { color: #1a237e; font-size: 20px; -pdf-keep-with-next: true; margin-top: 0; }
        h2 { color: #303f9f; font-size: 16px; -pdf-keep-with-next: true; }
        h3, h4, h5 { -pdf-keep-with-next: true; }

        .lesson-content { margin-bottom: 1cm; }
        .lesson-content img { max-width: 100%; height: auto; }

        /* List Spacing Fix */
        ul, ol { margin-top: 0; margin-bottom: 8px; padding-left: 20px; }
        li { margin-bottom: 3px; line-height: 1.3; }

        code, pre {
            background-color: #f5f5f5;
            padding: 2px 4px;
            font-family: monospace;
            font-size: 10px;
        }
        pre { padding: 10px; white-space: pre-wrap; }
        
        table { width: 100%; border-collapse: collapse; margin: 1cm 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #1a237e; color: white; }
    </style>
</head>
<body>
    <!-- Header Content (Appears on 'content' and 'info_page') -->
    <div id="headerContent">
        <div style="text-align: right;">
            {% if logo_path %}<img src="{{ logo_path }}" style="height: 35px;" />{% endif %}
        </div>
    </div>

    <!-- Standard Footer Content (Appears on 'content' pages) -->
    <div id="footerContent">
        <div style="text-align: center; color: #888; font-size: 9px; border-top: 1px solid #eee; padding-top: 5px;">
            Contenido desarrollado por IA, revisado por Netec
            <br/>
            Page <pdf:pagenumber> of <pdf:pagecount>
        </div>
    </div>

    <!-- IP Footer Content (Appears ONLY on 'info_page' footer frame) -->
    <div id="ipContent">
        <div class="ip-text">
            <p><strong>Material didáctico preparado por la empresa Global K, S.A. de C.V. Registrado en Derechos de Autor.</strong></p>
            <p>Todos los contenidos de este Sitio (incluyendo, pero no limitado a: texto, logotipos, contenido, fotografías, audio, botones, nombres comerciales y videos) están sujetos a derechos de propiedad por las leyes de Derechos de Autor de la empresa Global K, S.A. de C.V. Queda prohibido copiar, reproducir, distribuir, publicar, transmitir, difundir, o en cualquier modo explotar cualquier parte de este documento sin la autorización previa por escrito.</p>
        </div>
    </div>

    <!-- Page 1: Cover (matches @page) -->
    <div class="title-page">
        {% if logo_path %}
        <img src="{{ logo_path }}" class="logo-large" />
        {% endif %}
        
        <div class="course-title">{{ title }}</div>
        
        <div class="date-section">{{ date }}</div>
    </div>

    <!-- Page 2: Info (Switch to 'info_page' template) -->
    <pdf:nexttemplate name="info_page" />
    <pdf:nextpage />

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

        {% if objectives %}
        <div style="margin-top: 1cm;">
            <h1>Objetivos de Aprendizaje</h1>
            <ul>
            {% for obj in objectives %}
                <li>{{ obj }}</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
    </div>

    <!-- IP Info removed from main flow, now in footer frame -->

    <!-- Page 3+: Content (Switch to 'content' template) -->
    <pdf:nexttemplate name="content" />
    
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

        # Safe Typography Normalization Helper (Recursive)
        def normalize_obj(obj):
            if isinstance(obj, str):
                # Replace smart quotes, dashes, etc.
                replacements = {
                    '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '-', '\u2014': '-', '\u2015': '-', '\u00ad': '',
                    '\u2018': "'", '\u2019': "'", '\u201a': "'", '\u201b': "'",
                    '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u201f': '"',
                    '\u2026': '...', '\u00a0': ' '
                }
                for char, rep in replacements.items():
                    obj = obj.replace(char, rep)
                return obj
            elif isinstance(obj, list):
                return [normalize_obj(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: normalize_obj(v) for k, v in obj.items()}
            return obj

        # ----------------------------------------
        # 2. FETCH OUTLINE & METADATA
        # ----------------------------------------
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
                outline_data_raw = yaml.safe_load(outline_res['Body'].read())
                
                # Normalize Outline Data
                outline_data = normalize_obj(outline_data_raw)
                
                # Helper to look deeply
                course_section = outline_data.get('course', {})
                if not isinstance(course_section, dict):
                     course_section = {}

                # Helper to clean stringified lists
                def clean_metadata_list_string(val):
                    if not val: return ''
                    if isinstance(val, list): return ", ".join(val)
                    if isinstance(val, str):
                        cleaned = re.sub(r"^\[\s*['\"]|['\"]\s*\]$", "", val)
                        cleaned = re.sub(r"['\"]\s*,\s*['\"]", ", ", cleaned)
                        return cleaned
                    return str(val)

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
                raw_audience = (
                    outline_data.get('target_audience') or
                    outline_data.get('audience') or
                    course_section.get('target_audience') or
                    course_section.get('audience')
                )
                course_meta['audience'] = clean_metadata_list_string(raw_audience)

                # 4. Prerequisites
                raw_prereq = (
                    outline_data.get('prerequisites') or
                    course_section.get('prerequisites')
                )
                course_meta['prerequisites'] = clean_metadata_list_string(raw_prereq)
                
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
        
        # Parse first, THEN normalize
        book_data_raw = json.loads(response['Body'].read().decode('utf-8'))
        book_data = normalize_obj(book_data_raw)
        
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
            # 1. Short paragraphs ending in colon
            # 2. Short paragraphs starting with bold (likely headers)
            def apply_orphan_fix(match):
                full_tag = match.group(0)
                attrs = match.group(1) or ""
                content = match.group(2)
                
                # Skip if already has keep-with-next
                if '-pdf-keep-with-next' in attrs:
                    return full_tag
                
                # Check 1: Length (Strip tags roughly for length check)
                text_content = re.sub(r'<[^>]+>', '', content).strip()
                if len(text_content) > 250: 
                    return full_tag

                should_keep = False
                
                # Heuristic A: Ends with colon
                if text_content.endswith(':'):
                    should_keep = True
                
                # Heuristic B: Starts with Bold (e.g. <strong>Title</strong> or <b>Title</b>)
                # We check the raw content string for this
                elif re.match(r'^\s*<(?:strong|b)>', content, re.IGNORECASE):
                    should_keep = True

                if should_keep:
                    if 'style="' in attrs:
                        return f'<p{attrs.replace("style=\u0022", "style=\u0022-pdf-keep-with-next: true; ")}>{content}</p>'
                    else:
                        return f'<p{attrs} style="-pdf-keep-with-next: true;">{content}</p>'
                
                return full_tag

            clean_html = re.sub(
                r'<p(\s+[^>]*)?>(.*?)</p>', 
                apply_orphan_fix, 
                clean_html, 
                flags=re.DOTALL | re.IGNORECASE
            )
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
