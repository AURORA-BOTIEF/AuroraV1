#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import yaml
import boto3
import time
import urllib.request
import urllib.error
from datetime import datetime
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    """
    Lambda handler for building a complete book from generated content and images.

    Expected event format:
    {
        "course_bucket": "bucket-name",
        "project_folder": "250916-course-name-01",
        "lesson_keys": ["path/to/lesson1.md", "path/to/lesson2.md"],
        "image_mappings": {
            "lesson1.md": {
                "[VISUAL: diagram1]": "path/to/image1.png",
                "[VISUAL: diagram2]": "path/to/image2.png"
            }
        },
        "book_title": "Course Book Title",
        "author": "Author Name"
    }
    """
    try:
        print("--- Starting Book Builder ---")
        print(f"Event: {json.dumps(event, indent=2)}")

        # Handle API Gateway events where body is in event['body']
        if 'body' in event:
            if event.get('isBase64Encoded', False):
                import base64
                body = base64.b64decode(event['body']).decode('utf-8')
            else:
                body = event['body']
            request_data = json.loads(body)
        else:
            request_data = event

        # Extract parameters
        course_bucket = request_data.get('course_bucket')
        project_folder = request_data.get('project_folder')
        lesson_keys = request_data.get('lesson_keys', [])
        image_mappings = request_data.get('image_mappings', {})
        book_title = request_data.get('book_title', 'Generated Course Book')
        author = request_data.get('author', 'Aurora AI')
        model_provider = request_data.get('model_provider', 'bedrock')
        outline_s3_key = request_data.get('outline_s3_key')

        if not course_bucket:
            raise ValueError("course_bucket is required")
        if not project_folder:
            raise ValueError("project_folder is required")

        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

        # Load outline metadata and detect course language
        outline_data = load_outline_data(s3_client, course_bucket, outline_s3_key)
        is_spanish = detect_spanish_course(s3_client, course_bucket, outline_s3_key)
        module_term = "Capítulo" if is_spanish else "Module"

        # If no lesson_keys provided, auto-discover lessons from S3
        if not lesson_keys:
            print(f"Auto-discovering lessons in {project_folder}/lessons/")
            lessons_prefix = f"{project_folder}/lessons/"
            response = s3_client.list_objects_v2(
                Bucket=course_bucket,
                Prefix=lessons_prefix
            )

            if 'Contents' in response:
                lesson_keys = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.md')]
                print(f"Found {len(lesson_keys)} lesson files: {lesson_keys}")
            else:
                print(f"No lesson files found in {lessons_prefix}")
                lesson_keys = []

        # Normalize image_mappings: if it's a list of dicts, merge them into one dict
        print(f"DEBUG: image_mappings type: {type(image_mappings)}")
        print(f"DEBUG: image_mappings value: {json.dumps(image_mappings, default=str)[:500]}")
        
        if isinstance(image_mappings, list):
            print(f"✓ image_mappings is a list with {len(image_mappings)} items, merging...")
            merged_mappings = {}
            for idx, mapping_dict in enumerate(image_mappings):
                print(f"  - Batch {idx}: type={type(mapping_dict)}, keys={len(mapping_dict) if isinstance(mapping_dict, dict) else 'N/A'}")
                if isinstance(mapping_dict, dict):
                    merged_mappings.update(mapping_dict)
            image_mappings = merged_mappings
            print(f"✓ Merged result: {len(image_mappings)} total image mappings")
            print(f"DEBUG: Sample keys: {list(image_mappings.keys())[:5]}")
        else:
            print(f"  image_mappings is NOT a list, using as-is with {len(image_mappings) if isinstance(image_mappings, dict) else 0} mappings")
        
        # If no image_mappings provided, scan prompts folder to build correct mappings
        if not image_mappings:
            print("No image_mappings provided, scanning prompts folder to reconstruct mappings...")
            prompts_prefix = f"{project_folder}/prompts/"
            try:
                # Scan prompts folder for visual tag descriptions
                prompts_response = s3_client.list_objects_v2(
                    Bucket=course_bucket,
                    Prefix=prompts_prefix
                )
                if 'Contents' in prompts_response:
                    for prompt_obj in prompts_response['Contents']:
                        prompt_key = prompt_obj['Key']
                        if prompt_key.endswith('.json'):
                            # Download and parse prompt JSON
                            try:
                                prompt_response = s3_client.get_object(Bucket=course_bucket, Key=prompt_key)
                                prompt_data = json.loads(prompt_response['Body'].read().decode('utf-8'))
                                
                                # Extract description and ID
                                description = prompt_data.get('description', '')
                                img_id = prompt_data.get('id', '')
                                
                                if description and img_id:
                                    # Build visual tag with ID and description (new format)
                                    visual_tag = f"[VISUAL: {img_id} - {description}]"
                                    # Build image path (images are stored as id.png)
                                    image_path = f"{project_folder}/images/{img_id}.png"
                                    image_mappings[visual_tag] = image_path
                                    print(f"✅ Mapped: {visual_tag[:80]}... -> {img_id}.png")
                            except Exception as e:
                                print(f"Warning: Could not parse prompt {prompt_key}: {e}")
                                continue
                
                print(f"Created {len(image_mappings)} image mappings from prompts folder")
            except Exception as e:
                print(f"Warning: Could not scan prompts folder: {e}")
                # Fallback: try to scan images folder (old behavior)
                print("Falling back to image filename-based mapping...")
                images_prefix = f"{project_folder}/images/"
                try:
                    images_response = s3_client.list_objects_v2(
                        Bucket=course_bucket,
                        Prefix=images_prefix
                    )
                    if 'Contents' in images_response:
                        for img_obj in images_response['Contents']:
                            img_key = img_obj['Key']
                            if img_key.endswith('.png'):
                                img_filename = img_key.split('/')[-1]
                                img_id = img_filename.replace('.png', '')
                                visual_tag = f"[VISUAL: {img_id}]"
                                image_mappings[visual_tag] = img_key
                                print(f"✅ Fallback mapping: {visual_tag} -> {img_key}")
                    print(f"Created {len(image_mappings)} fallback image mappings")
                except Exception as fallback_error:
                    print(f"Warning: Fallback image scan also failed: {fallback_error}")
        
        print(f"Using {len(image_mappings)} image mappings for visual tag replacement")

        # Collect all lessons content and organize by module
        modules = {}  # module_number -> {'title': str, 'lessons': []}
        all_lessons = []

        # lesson_keys may be a list of strings (s3 keys) or list of objects with 's3_key'
        for entry in lesson_keys:
            # Normalize to s3_key string
            if isinstance(entry, dict):
                lesson_key = entry.get('s3_key') or entry.get('key') or entry.get('path')
            else:
                lesson_key = entry

            if not lesson_key:
                print(f"Skipping invalid lesson entry: {entry}")
                continue

            try:
                # Download lesson content
                response = s3_client.get_object(Bucket=course_bucket, Key=lesson_key)
                lesson_content = response['Body'].read().decode('utf-8')

                # Extract lesson title from filename or content
                lesson_filename = lesson_key.split('/')[-1]
                raw_title = extract_lesson_title(lesson_content, lesson_filename)

                # Extract module and lesson numbers from filename
                # Expected format: module-1-lesson-1-title.md or module-01-lesson-01-title.md
                module_num, lesson_num = extract_module_lesson_numbers(lesson_filename)
                
                # Normalize the title to remove incorrect "Lesson X.Y:" prefixes
                lesson_title = normalize_lesson_title(raw_title, lesson_num)
                lesson_title = normalize_spanish_terms(lesson_title, is_spanish)

                # Replace visual tags with images for this lesson
                processed_content = replace_visual_tags(lesson_content, image_mappings, course_bucket)
                processed_content = normalize_spanish_terms(processed_content, is_spanish)
                processed_content, bib_urls = extract_and_strip_bibliography(processed_content)
                processed_content = sanitize_resources_links_in_resources(processed_content)
                processed_content = strip_primary_lesson_heading(processed_content)

                lesson_data = {
                    'title': lesson_title,
                    'filename': lesson_filename,
                    'content': processed_content,
                    'word_count': len(processed_content.split()),
                    'module_number': module_num,
                    'lesson_number': lesson_num,
                    'ref_urls': bib_urls,
                }

                all_lessons.append(lesson_data)

                # Organize by module
                if module_num not in modules:
                    modules[module_num] = {
                        'title': f"{module_term} {module_num}",  # Will try to extract better title later
                        'lessons': []
                    }
                modules[module_num]['lessons'].append(lesson_data)

            except Exception as e:
                print(f"Warning: Failed to process lesson {lesson_key}: {e}")
                # continue processing remaining lessons instead of failing
                continue

        # Sort modules and lessons within each module
        sorted_modules = sorted(modules.items(), key=lambda x: x[0])
        for module_num, module_data in sorted_modules:
            module_data['lessons'].sort(key=lambda x: x['lesson_number'])

        # Try to extract module titles from first lesson of each module
        for module_num, module_data in sorted_modules:
            if module_data['lessons']:
                first_lesson = module_data['lessons'][0]
                # Look for module title in lesson content
                module_title = extract_module_title(first_lesson['content'], module_num, is_spanish)
                if module_title:
                    module_data['title'] = normalize_spanish_terms(module_title, is_spanish)

        # Build display lessons including mandatory module introduction and summary tab
        for module_num, module_data in sorted_modules:
            intro_title = "Introducción" if is_spanish else "Introduction"
            intro_content = generate_module_intro(module_num, module_data['title'], module_data['lessons'], is_spanish)
            summary_content = generate_module_summary(module_num, module_data['title'], module_data['lessons'], is_spanish)

            intro_lesson = {
                'title': intro_title,
                'filename': f"module-{module_num}-lesson-0-intro.md",
                'content': intro_content,
                'word_count': len(intro_content.split()),
                'module_number': module_num,
                'lesson_number': 0,
                'is_intro': True
            }

            summary_lesson = {
                'title': "Resumen del Capítulo" if is_spanish else "Chapter Summary",
                'filename': f"module-{module_num}-lesson-summary.md",
                'content': summary_content,
                'word_count': len(summary_content.split()),
                'module_number': module_num,
                'lesson_number': (module_data['lessons'][-1]['lesson_number'] + 1) if module_data['lessons'] else 1,
                'is_summary': True
            }

            module_data['display_lessons'] = [intro_lesson] + module_data['lessons'] + [summary_lesson]

        # Generate hierarchical table of contents
        toc_lines = []
        for module_num, module_data in sorted_modules:
            toc_lines.append(f"\n## {module_data['title']}")
            for lesson in module_data.get('display_lessons', module_data['lessons']):
                if lesson.get('is_intro'):
                    toc_lines.append(f"  - {lesson['title']}")
                elif lesson.get('is_summary'):
                    toc_lines.append(f"  - {lesson['title']}")
                else:
                    toc_lines.append(f"  - {module_num}.{lesson['lesson_number']}: {lesson['title']}")
        
        toc_title = "Tabla de Contenido" if is_spanish else "Table of Contents"
        toc_content = f"# {toc_title}\n" + "\n".join(toc_lines) + "\n\n---\n\n"

        # Generate book front matter
        total_lessons = len(all_lessons)
        front_matter = generate_front_matter(book_title, author, total_lessons)

        # Build course introduction from outline
        course_intro_content = generate_course_introduction(outline_data, is_spanish)

        # Combine all content with module hierarchy
        full_book_content = front_matter
        if course_intro_content:
            full_book_content += course_intro_content + "\n\n---\n\n"
        full_book_content += toc_content

        for module_num, module_data in sorted_modules:
            # Add module header
            full_book_content += f"\n\n# {module_data['title']}\n\n"
            full_book_content += "---\n\n"

            module_urls = collect_urls_for_module(module_data.get('lessons', []))
            
            # Add module introduction + lessons within this module
            for lesson in module_data.get('display_lessons', module_data['lessons']):
                if lesson.get('is_intro'):
                    full_book_content += f"## {lesson['title']}\n\n"
                elif lesson.get('is_summary'):
                    summary_title = f"Resumen del Capítulo {module_num}" if is_spanish else f"Chapter {module_num} Summary"
                    full_book_content += f"## {summary_title}\n\n"
                else:
                    full_book_content += f"## {module_num}.{lesson['lesson_number']}: {lesson['title']}\n\n"
                full_book_content += lesson['content']
                full_book_content += "\n\n---\n\n"

            ref_block = format_chapter_references_section(module_urls, model_provider, is_spanish)
            if ref_block:
                full_book_content += ref_block + "\n\n---\n\n"

        # Add book statistics
        total_words = sum(lesson['word_count'] for lesson in all_lessons)
        stats_content = f"""## Book Statistics

- **Total Modules**: {len(modules)}
- **Total Lessons**: {len(all_lessons)}
- **Total Words**: {total_words}
- **Average Words per Lesson**: {total_words // len(all_lessons) if all_lessons else 0}
- **Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Generated by**: Aurora AI Course Generator

---
"""

        full_book_content += stats_content

        # Add end-of-course glossary
        glossary_content = generate_course_glossary(sorted_modules, is_spanish)
        full_book_content += glossary_content

        # Save the complete book to S3
        book_filename = f"{project_folder}/book/{book_title.replace(' ', '_')}_complete.md"
        s3_client.put_object(
            Bucket=course_bucket,
            Key=book_filename,
            Body=full_book_content.encode('utf-8'),
            ContentType='text/markdown'
        )

        # Also save as JSON for easier frontend consumption
        special_sections = []
        if course_intro_content and course_intro_content.strip():
            special_sections.append({
                'section_type': 'course_intro',
                'title': 'Introducción del Curso' if is_spanish else 'Course Introduction',
                'content': course_intro_content.strip()
            })
        special_sections.append({
            'section_type': 'glossary',
            'title': 'Glosario' if is_spanish else 'Glossary',
            'content': (glossary_content or '').strip() or generate_default_glossary(is_spanish)
        })

        book_json = {
            'metadata': {
                'title': book_title,
                'author': author,
                'generated_at': datetime.now().isoformat(),
                'total_modules': len(modules),
                'total_lessons': len(all_lessons),
                'total_words': total_words,
                'course_introduction': course_intro_content,
                'course_glossary': glossary_content,
                'project_folder': project_folder
            },
            'modules': [
                {
                    'module_number': module_num,
                    'module_title': module_data['title'],
                    'lessons': module_data.get('display_lessons', module_data['lessons'])
                }
                for module_num, module_data in sorted_modules
            ],
            'special_sections': special_sections,
            's3_key': book_filename,
            'bucket': course_bucket
        }

        book_json_key = f"{project_folder}/book/{book_title.replace(' ', '_')}_data.json"
        s3_client.put_object(
            Bucket=course_bucket,
            Key=book_json_key,
            Body=json.dumps(book_json, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )

        response = {
            "statusCode": 200,
            "message": f"Successfully built book '{book_title}' with {len(all_lessons)} lessons",
            "book_title": book_title,
            "book_s3_key": book_filename,
            "book_json_key": book_json_key,
            "course_bucket": course_bucket,
            "project_folder": project_folder,
            "module_count": len(modules),
            "lesson_count": len(all_lessons),
            "total_words": total_words
            # Note: book_content removed to avoid States.DataLimitExceeded error
            # Full book content is already saved to S3 at book_s3_key and book_json_key
        }

        print(f"--- Book Builder Complete ---")
        print(f"Generated book: {book_filename}")
        print(f"Modules included: {len(modules)}")
        print(f"Lessons included: {len(all_lessons)}")

        # Check if this is a Step Functions invocation (no 'body' in event) or API Gateway (has 'body')
        # Step Functions passes parameters directly, API Gateway wraps them in 'body'
        is_step_functions = 'body' not in event
        
        if is_step_functions:
            # Return data directly for Step Functions (no API Gateway wrapper)
            return response
        else:
            # Return API Gateway response format
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps(response)
            }

    except Exception as e:
        error_msg = f"Error in book building: {str(e)}"
        print(f"ERROR: {error_msg}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "error": error_msg,
                "request_id": context.aws_request_id if context else "unknown"
            })
        }

def detect_spanish_course(s3_client, course_bucket, outline_s3_key):
    """Spanish by default; English only when outline metadata explicitly requests English."""
    if not outline_s3_key:
        return True

    try:
        response = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
        outline_text = response['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_text) or {}
        course_info = outline_data.get('course', outline_data)
        language = str(course_info.get('language', outline_data.get('language', ''))).strip().lower()
        if not language:
            return True
        if language.startswith('en') or 'english' in language or 'inglés' in language or 'ingles' in language:
            return False
        return True
    except Exception as e:
        print(f"Warning: Could not detect course language from outline: {e}")
        return True


def load_outline_data(s3_client, course_bucket, outline_s3_key):
    """Load outline structure from S3 when available."""
    if not outline_s3_key:
        return {}

    try:
        response = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
        outline_text = response['Body'].read().decode('utf-8')
        return yaml.safe_load(outline_text) or {}
    except Exception as e:
        print(f"Warning: Could not load outline data: {e}")
        return {}


def normalize_spanish_terms(content: str, is_spanish: bool) -> str:
    """Normalize terms for Spanish theory books: Module/Módulo->Capítulo, Lesson->Lección."""
    if not is_spanish or not content:
        return content

    updated = content
    updated = re.sub(r'\b(M[oó]dulo|Module)\b', 'Capítulo', updated, flags=re.IGNORECASE)
    updated = re.sub(r'\bLesson\b', 'Lección', updated, flags=re.IGNORECASE)
    return updated


_BIB_SECTION_HEADER = re.compile(
    r'^##\s*(Bibliograf[ií]a|Referencias\s+Bibliográficas|Bibliography|References)\s*$',
    re.MULTILINE | re.IGNORECASE,
)


def extract_and_strip_bibliography(content: str) -> tuple[str, list[str]]:
    """Extract per-lesson bibliography URLs (but no longer strips the section)."""
    if not content:
        return '', []

    urls: list[str] = []

    for m in _BIB_SECTION_HEADER.finditer(content):
        rest = content[m.end():]
        nxt = re.search(r'^##\s+\S', rest, re.MULTILINE)
        block_len = nxt.start() if nxt else len(rest)
        block = rest[:block_len]
        for raw_u in re.findall(r'https?://[^\s\)\]\>\"\']+', block):
            u = raw_u.rstrip('.,);')
            if u not in urls:
                urls.append(u)

    return content, urls


_url_reach_cache: dict[str, bool] = {}


def _check_url_reachable(url: str, timeout: float = 5.0) -> bool:
    """GET-based reachability (HEAD alone fails on many CDNs). Cached per process."""
    u = url.strip().rstrip('.,);')
    if not u.lower().startswith(('http://', 'https://')):
        return False
    if u in _url_reach_cache:
        return _url_reach_cache[u]
    ua = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    )
    ok = False
    try:
        req = urllib.request.Request(u, headers={'User-Agent': ua})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = 200 <= int(resp.getcode()) < 400
    except urllib.error.HTTPError as e:
        ok = 200 <= int(e.code) < 400
    except Exception:
        ok = False
    _url_reach_cache[u] = ok
    return ok


_LEGACY_UNVERIFIED_MARK = re.compile(
    r'\s*\*\(enlace no verificado[^\)]*\)\*\s*',
    re.IGNORECASE,
)


def sanitize_resources_links_in_resources(content: str, max_checks: int = 20) -> str:
    """Under Recursos Adicionales: drop unreachable links (no footnotes). Bounded GET checks."""
    if not content:
        return content

    m = re.search(
        r'(^##\s*Recursos\s+Adicionales\s*$|^##\s*Additional\s+Resources\s*$|^##\s*Referencias\s+Bibliográficas\s*$|^##\s*Bibliographic\s+References\s*$)',
        content,
        re.MULTILINE | re.IGNORECASE,
    )
    if not m:
        return content

    rest = content[m.end():]
    nxt_sec = re.search(r'^##\s+\S', rest, re.MULTILINE)
    sec_body = rest[: nxt_sec.start()] if nxt_sec else rest

    sec_body = _LEGACY_UNVERIFIED_MARK.sub('', sec_body)

    checks_left = [max_checks]

    def reachable(raw_url: str) -> bool:
        u = raw_url.strip().rstrip('.,);')
        if checks_left[0] <= 0:
            return True  # budget exhausted: leave remaining URLs unchanged
        checks_left[0] -= 1
        return _check_url_reachable(u)

    md_link = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')

    def md_sub(mm: re.Match) -> str:
        label, url = mm.group(1).strip(), mm.group(2).strip()
        if reachable(url):
            return mm.group(0)
        return label if label else ''

    sec_body = md_link.sub(md_sub, sec_body)

    bare = re.compile(r'https?://[^\s\)\]\>\"\',\]]+')

    def bare_sub(bm: re.Match) -> str:
        raw = bm.group(0)
        url = raw.rstrip('.,);')
        if reachable(url):
            return raw
        return ''

    sec_body = bare.sub(bare_sub, sec_body)

    cleaned_lines: list[str] = []
    for line in sec_body.splitlines():
        s = line.strip()
        if re.match(r'^[-*]\s*$', s):
            continue
        cleaned_lines.append(line.rstrip())

    sec_body = '\n'.join(cleaned_lines)
    sec_body = re.sub(r'\n{3,}', '\n\n', sec_body).rstrip() + '\n'

    tail = rest[nxt_sec.start():] if nxt_sec else ''
    return content[: m.end()] + sec_body + tail


def collect_urls_for_module(lessons: list) -> list[str]:
    """Aggregate unique URLs from lesson bodies + extracted bibliography URLs."""
    seen = set()
    out = []
    url_re = re.compile(r'https?://[^\s\)\]\>\"\']+')

    for les in lessons:
        if les.get('is_intro') or les.get('is_summary'):
            continue
        for u in les.get('ref_urls') or []:
            u = u.rstrip('.,);')
            if u not in seen:
                seen.add(u)
                out.append(u)
        for raw in url_re.findall(les.get('content', '')):
            u = raw.rstrip('.,);')
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def format_chapter_references_section(urls: list[str], model_provider: str, is_spanish: bool) -> str:
    """Single Referencias Bibliográficas block per chapter (THOR requirement)."""
    model_name = "OpenAI GPT-5" if str(model_provider).lower() == 'openai' else "Anthropic Claude Sonnet 4.6 (Amazon Bedrock)"
    if is_spanish:
        lines = ['## Referencias Bibliográficas', '']
        if urls:
            lines.extend(f'- {u}' for u in urls)
        else:
            lines.append(f'- Contenido elaborado con el modelo: {model_name}.')
    else:
        lines = ['## References', '']
        if urls:
            lines.extend(f'- {u}' for u in urls)
        else:
            lines.append(f'- Content developed using: {model_name}.')

    return '\n'.join(lines)


def normalize_lesson_title(title, lesson_num):
    """Normalize lesson title to use correct lesson numbering.
    
    Converts titles like:
    - "Lesson 1.6: Title" -> "Title"
    - "Lesson 2.3: Title" -> "Title"
    - "Lesson 1: Title" -> "Title"
    
    The lesson number will be added separately in the book structure.
    """
    import re
    
    # Remove "Lesson X.Y:" or "Lesson X:" patterns (in English and Spanish)
    patterns = [
        r'^Lesson\s+\d+\.\d+:\s*',  # Lesson 1.6:
        r'^Lesson\s+\d+:\s*',        # Lesson 1:
        r'^Lección\s+\d+\.\d+:\s*',  # Lección 1.6:
        r'^Lección\s+\d+:\s*',       # Lección 1:
    ]
    
    cleaned_title = title
    for pattern in patterns:
        cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)
    
    return cleaned_title.strip()

def extract_lesson_title(content, filename):
    """Extract lesson title from content or filename."""
    # Try to find title in first heading
    lines = content.split('\n')
    for line in lines[:10]:  # Check first 10 lines
        if line.strip().startswith('# '):
            return line.strip()[2:].strip()

    # Fallback to filename
    return filename.replace('.md', '').replace('_', ' ').title()

def extract_module_lesson_numbers(filename):
    """Extract module and lesson numbers from filename.
    
    Expected formats:
    - module-1-lesson-1-title.md
    - module-01-lesson-01-title.md
    
    Returns: (module_num, lesson_num) as integers
    """
    import re
    
    # Pattern: module-X-lesson-Y (with optional leading zeros)
    pattern = r'module-(\d+)-lesson-(\d+)'
    match = re.search(pattern, filename.lower())
    
    if match:
        module_num = int(match.group(1))
        lesson_num = int(match.group(2))
        return module_num, lesson_num
    
    # Fallback: return 1, 1
    print(f"Warning: Could not extract module/lesson numbers from {filename}, using defaults")
    return 1, 1

def extract_module_title(lesson_content, module_num, is_spanish=False):
    """Try to extract module title from lesson content metadata or headings.
    
    Looks for patterns like:
    - **Module:** Title
    - Module X: Title
    - # Module X: Title
    """
    import re
    
    lines = lesson_content.split('\n')
    
    # Look in first 20 lines for module title
    for line in lines[:20]:
        # Pattern 1: **Module:** Title or **Módulo:** Title
        if re.match(r'\*\*M[oó]dulo:?\*\*', line, re.IGNORECASE):
            title = re.sub(r'\*\*M[oó]dulo:?\*\*\s*', '', line, flags=re.IGNORECASE).strip()
            if title:
                module_term = "Capítulo" if is_spanish else "Module"
                return f"{module_term} {module_num}: {title}"
        
        # Pattern 2: # Module X: Title
        match = re.match(r'#\s*M[oó]dulo\s+\d+:?\s*(.+)', line, re.IGNORECASE)
        if match:
            module_term = "Capítulo" if is_spanish else "Module"
            return f"{module_term} {module_num}: {match.group(1).strip()}"
    
    # Fallback
    module_term = "Capítulo" if is_spanish else "Module"
    return f"{module_term} {module_num}"


def strip_primary_lesson_heading(content: str) -> str:
    """Remove first H1 heading to avoid duplicated lesson title blocks in final book."""
    if not content:
        return content

    lines = content.splitlines()
    cleaned = []
    removed = False
    for line in lines:
        if not removed and re.match(r'^\s*#\s+.+', line):
            removed = True
            continue
        cleaned.append(line)

    cleaned_text = "\n".join(cleaned).lstrip()
    return cleaned_text if cleaned_text else content


def generate_module_intro(module_num: int, module_title: str, module_lessons: list, is_spanish: bool) -> str:
    """Generate contextual introduction section (internal lesson 0) for each module."""
    lesson_titles = [lesson.get('title', '').strip() for lesson in module_lessons if lesson.get('title')]
    lesson_preview = "\n".join([f"- {title}" for title in lesson_titles]) if lesson_titles else "- (Sin lecciones definidas)"

    module_topics = extract_module_key_topics(module_lessons, is_spanish=is_spanish, max_items=6)
    topic_preview = "\n".join([f"- {topic}" for topic in module_topics]) if module_topics else lesson_preview

    module_objectives = extract_module_objectives(module_lessons, max_items=4)
    objectives_preview = "\n".join([f"- {obj}" for obj in module_objectives]) if module_objectives else "- Comprender y aplicar los contenidos del capítulo."

    if is_spanish:
        return f"""### Objetivos del capítulo

{objectives_preview}

### Información general

Este capítulo desarrolla de forma aplicada el tema **{module_title}**. A continuación se muestran los contenidos reales que se abordan en las lecciones del capítulo.

### Temas principales del capítulo

{topic_preview}

### Lecciones incluidas

{lesson_preview}
"""

    return f"""### Chapter objectives

{objectives_preview}

### General information

This chapter develops **{module_title}** through practical and conceptual progression. The sections below summarize the real content covered in this chapter.

### Main chapter topics

{topic_preview}

### Included lessons

{lesson_preview}
"""


def extract_takeaway_bullets_from_lesson(content: str, max_bullets: int = 8) -> list:
    """Collect bullets from ### Puntos Clave / Key Takeaways blocks."""
    if not content:
        return []
    lines = content.splitlines()
    in_section = False
    bullets = []
    pk_headers = frozenset({
        'puntos clave', 'key takeaways', 'key takeaway', 'takeaways', 'ideas clave', 'ideas principales',
    })
    for line in lines:
        line_st = line.strip()
        if re.match(r'^###\s+', line_st):
            title = re.sub(r'^###\s+', '', line_st).strip().lower().rstrip(':').strip()
            in_section = title in pk_headers
            continue
        if in_section:
            if re.match(r'^##\s+', line_st):
                break
            if re.match(r'^###\s+', line_st):
                break
            mb = re.match(r'^[-*]\s+(.+)$', line_st)
            if mb:
                bullets.append(mb.group(1).strip())
                if len(bullets) >= max_bullets:
                    break
    return bullets


def _dedupe_strings_preserve_order(items: list, max_n: int, min_len: int = 10) -> list:
    seen = set()
    out = []
    for x in items:
        if not isinstance(x, str):
            continue
        s = x.strip()
        if len(s) < min_len:
            continue
        key = re.sub(r'\s+', ' ', s.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_n:
            break
    return out


def _format_lesson_title_run(titles: list, is_spanish: bool) -> str:
    clean = [t for t in titles if t and len(t.strip()) > 1]
    if not clean:
        return 'el contenido planificado para este capítulo' if is_spanish else 'the planned lessons for this chapter'
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f'{clean[0]} y {clean[1]}' if is_spanish else f'{clean[0]} and {clean[1]}'
    sep = ', '
    conj = ' y ' if is_spanish else ', and '
    return sep.join(clean[:-1]) + conj + clean[-1]


def generate_module_summary(module_num: int, module_title: str, module_lessons: list, is_spanish: bool) -> str:
    """Chapter summary: reinforce learning with takeaways from lessons + topic map (not template headings)."""
    lessons = [
        l for l in module_lessons
        if not l.get('is_intro') and not l.get('is_summary')
    ]
    takeaways: list = []
    for les in lessons:
        takeaways.extend(extract_takeaway_bullets_from_lesson(les.get('content', '')))
        if len(takeaways) >= 24:
            break
    takeaways = _dedupe_strings_preserve_order(takeaways, 10, min_len=8)

    topics = extract_module_key_topics(module_lessons, is_spanish=is_spanish, max_items=10)
    titles = [les.get('title', '').strip() for les in lessons if les.get('title')]
    title_run = _format_lesson_title_run(titles, is_spanish)

    if is_spanish:
        lines = [
            f'Este resumen te ayuda a **recordar y aplicar** lo esencial de **{module_title}**.',
            '',
            f'Las lecciones de este capítulo abordan: {title_run}.',
            '',
        ]
        if takeaways:
            lines.extend([
                '### Ideas clave para reforzar tu aprendizaje',
                '',
                *[f'- {t}' for t in takeaways],
                '',
            ])
        lines.extend([
            '### Mapa de contenidos',
            '',
        ])
        if topics:
            lines.extend(f'- {t}' for t in topics)
        else:
            lines.append('- Consulta las lecciones del capítulo para repasar objetivos y práctica.')
        lines.append('')
        return '\n'.join(lines).strip() + '\n'

    lines = [
        f'This summary helps you **remember and apply** what matters in **{module_title}**.',
        '',
        f'Lessons in this chapter cover: {title_run}.',
        '',
    ]
    if takeaways:
        lines.extend([
            '### Key ideas to reinforce your learning',
            '',
            *[f'- {t}' for t in takeaways],
            '',
        ])
    lines.extend([
        '### Content map',
        '',
    ])
    if topics:
        lines.extend(f'- {t}' for t in topics)
    else:
        lines.append('- Review the chapter lessons for objectives and hands-on practice.')
    lines.append('')
    return '\n'.join(lines).strip() + '\n'


def generate_course_glossary(sorted_modules: list, is_spanish: bool) -> str:
    """Generate glossary with term definitions inferred from lesson content."""
    glossary_entries = extract_glossary_entries(sorted_modules, is_spanish=is_spanish, max_entries=20)
    glossary_title = "Glosario" if is_spanish else "Glossary"

    lines = [f"\n## {glossary_title}\n"]
    if not glossary_entries:
        lines.extend(generate_default_glossary_lines(is_spanish))
        return "\n".join(lines) + "\n"

    for term, definition in glossary_entries:
        lines.append(f"- **{term}**: {definition}")

    return "\n".join(lines) + "\n"


def generate_course_introduction(outline_data: dict, is_spanish: bool) -> str:
    """Create a course introduction section using metadata from the outline file."""
    if not outline_data:
        return ""

    course = outline_data.get('course', outline_data)
    title = course.get('title') or course.get('name') or ""
    description = course.get('description') or course.get('summary') or ""
    level = course.get('level') or course.get('difficulty') or ""
    audience = normalize_to_list(course.get('audience') or course.get('target_audience'))
    prerequisites = normalize_to_list(course.get('prerequisites'))
    objectives = normalize_to_list(
        course.get('objectives')
        or course.get('learning_objectives')
        or course.get('learning_outcomes')
        or course.get('learning outcomes')
        or outline_data.get('learning_outcomes')
        or outline_data.get('learning outcomes')
    )
    modules = course.get('modules') or outline_data.get('modules') or []

    agenda_items = []
    for idx, module in enumerate(modules, 1):
        module_title = module.get('title', f"{('Capítulo' if is_spanish else 'Module')} {idx}")
        agenda_items.append(f"{idx}. {module_title}")

    audience_text = "\n".join([f"- {item}" for item in audience]) if audience else ("- No especificada" if is_spanish else "- Not specified")
    prereq_text = "\n".join([f"- {item}" for item in prerequisites]) if prerequisites else ("- No especificado" if is_spanish else "- Not specified")
    objective_text = "\n".join([f"- {item}" for item in objectives]) if objectives else ("- No especificado" if is_spanish else "- Not specified")
    agenda_text = "\n".join(agenda_items) if agenda_items else ("- No especificado" if is_spanish else "- Not specified")

    if is_spanish:
        return f"""## Introducción del Curso

### Título del curso

{title or 'No especificado'}

### Descripción

{description or 'No especificada'}

### Nivel

{level or 'No especificado'}

### Audiencia

{audience_text}

### Prerrequisitos

{prereq_text}

### Objetivos

{objective_text}

### Temario

{agenda_text}
"""

    return f"""## Course Introduction

### Course title

{title or 'Not specified'}

### Description

{description or 'Not specified'}

### Level

{level or 'Not specified'}

### Audience

{audience_text}

### Prerequisites

{prereq_text}

### Objectives

{objective_text}

### Agenda

{agenda_text}
"""


def normalize_to_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            text = f"{k}: {v}" if v else str(k)
            if text.strip():
                items.append(text.strip())
        return items
    return [str(value).strip()]


def extract_module_key_topics(module_lessons: list, is_spanish: bool, max_items: int = 6) -> list:
    """Extract key topic headings (H2/H3) from real module lesson content."""
    stop_words_es = {
        'objetivos de aprendizaje', 'introducción', 'resumen', 'puntos clave', 'próximos pasos',
        'recursos adicionales', 'referencias bibliográficas', 'bibliografía', 'metadatos', 'validación y pruebas', 'solución de problemas',
        'visión general del concepto', 'detalles técnicos', 'aplicación práctica',
        'información general', 'temas principales del capítulo', 'lecciones incluidas',
    }
    stop_words_en = {
        'learning objectives', 'introduction', 'summary', 'key takeaways', "what's next",
        'additional resources', 'bibliographic references', 'bibliography', 'metadata', 'validation & testing', 'troubleshooting',
        'concept overview', 'technical details', 'practical application',
        'general information', 'main chapter topics', 'included lessons',
    }
    stop_words = stop_words_es if is_spanish else stop_words_en

    topics = []
    seen = set()

    for lesson in module_lessons:
        content = lesson.get('content', '')
        for line in content.splitlines():
            match = re.match(r'^###?\s+(.+)$', line.strip())
            if not match:
                continue
            heading = match.group(1).strip().rstrip(':').strip()
            normalized = re.sub(r'\s+', ' ', heading.lower())
            if normalized in stop_words:
                continue
            if len(heading) < 3 or len(heading) > 90:
                continue
            if normalized not in seen:
                seen.add(normalized)
                topics.append(heading)
            if len(topics) >= max_items:
                return topics

    return topics


def extract_module_objectives(module_lessons: list, max_items: int = 4) -> list:
    """Extract objective bullets from module lessons."""
    objectives = []
    for lesson in module_lessons:
        content = lesson.get('content', '')
        for line in content.splitlines():
            if re.match(r'^\s*[-*]\s+.+', line):
                bullet = re.sub(r'^\s*[-*]\s+', '', line).strip()
                if 8 <= len(bullet) <= 160 and bullet not in objectives:
                    objectives.append(bullet)
                if len(objectives) >= max_items:
                    return objectives
    return objectives


def extract_glossary_entries(sorted_modules: list, is_spanish: bool, max_entries: int = 20) -> list:
    """Extract term-definition pairs from lesson headings and emphasized terms."""
    terms = []
    term_set = set()
    term_sources = {}

    for _, module_data in sorted_modules:
        for lesson in module_data.get('lessons', []):
            content = lesson.get('content', '')

            # Candidate terms from headings
            for line in content.splitlines():
                heading_match = re.match(r'^###?\s+(.+)$', line.strip())
                if heading_match:
                    candidate = heading_match.group(1).strip().rstrip(':').strip()
                    candidate = re.sub(r'^(\d+\.\d+\s*:\s*)', '', candidate)
                    if is_valid_glossary_term(candidate):
                        norm = candidate.lower()
                        if norm not in term_set:
                            term_set.add(norm)
                            terms.append(candidate)
                            term_sources[candidate] = content

            # Candidate terms from bold markers
            for candidate in re.findall(r'\*\*([^*]{2,80})\*\*', content):
                candidate = candidate.strip().rstrip(':').strip()
                if is_valid_glossary_term(candidate):
                    norm = candidate.lower()
                    if norm not in term_set:
                        term_set.add(norm)
                        terms.append(candidate)
                        term_sources[candidate] = content

            if len(terms) >= max_entries:
                break
        if len(terms) >= max_entries:
            break

    entries = []
    for term in terms[:max_entries]:
        source_content = term_sources.get(term, '')
        definition = infer_definition_from_content(term, source_content, is_spanish=is_spanish)
        entries.append((term, definition))

    return entries


def is_valid_glossary_term(term: str) -> bool:
    """Basic filter for glossary candidate terms."""
    if not term:
        return False
    t = term.strip()
    if len(t) < 3 or len(t) > 80:
        return False
    if re.match(r'^(objetivos de aprendizaje|introducción|resumen|bibliograf[íi]a|learning objectives|summary|bibliography)$', t, re.IGNORECASE):
        return False
    if re.match(r'^\d+([\.:]\d+)*$', t):
        return False
    return True


def infer_definition_from_content(term: str, content: str, is_spanish: bool) -> str:
    """Infer a concise definition from the first sentence that mentions the term."""
    if content:
        sentences = re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', content))
        term_lower = term.lower()
        for sentence in sentences:
            if term_lower in sentence.lower() and 30 <= len(sentence) <= 220:
                cleaned = sentence.strip()
                cleaned = re.sub(r'^[-*]\s*', '', cleaned)
                return cleaned

    if is_spanish:
        return "Concepto clave abordado en este curso."
    return "Key concept covered in this course."


def generate_default_glossary_lines(is_spanish: bool) -> list:
    """Default glossary entries when extraction has low confidence."""
    if is_spanish:
        return [
            "- **Contenedor**: Unidad ligera y portátil que empaqueta aplicación y dependencias para ejecutarse de forma consistente.",
            "- **Imagen**: Plantilla inmutable que define el sistema de archivos y configuración base de un contenedor.",
            "- **Volumen**: Mecanismo de persistencia para almacenar datos fuera del ciclo de vida del contenedor.",
            "- **Red de contenedores**: Configuración que permite comunicación segura entre contenedores y servicios.",
            "- **Dockerfile**: Archivo de instrucciones para construir imágenes de forma reproducible."
        ]

    return [
        "- **Container**: Lightweight portable unit that packages an application and its dependencies for consistent execution.",
        "- **Image**: Immutable template that defines the filesystem and baseline configuration for a container.",
        "- **Volume**: Persistence mechanism used to store data outside the container lifecycle.",
        "- **Container network**: Configuration that enables secure communication between containers and services.",
        "- **Dockerfile**: Instruction file used to build images reproducibly."
    ]


def generate_default_glossary(is_spanish: bool) -> str:
    """Return fallback glossary markdown content."""
    title = "## Glosario" if is_spanish else "## Glossary"
    return title + "\n\n" + "\n".join(generate_default_glossary_lines(is_spanish)) + "\n"

def replace_visual_tags(content, mappings, bucket):
    """
    Replace [VISUAL: description] tags with actual image references.
    Supports both old format (visual_tag -> s3_key) and new format (id -> {s3_key, description}).
    """
    processed_content = content
    
    print(f"DEBUG replace_visual_tags: Processing {len(mappings)} mappings")
    
    # Detect format: if any value is a dict with 's3_key', it's the new format
    is_new_format = False
    if mappings:
        first_value = next(iter(mappings.values()))
        if isinstance(first_value, dict) and 's3_key' in first_value:
            is_new_format = True
            print(f"  Using NEW FORMAT (id -> {{s3_key, description}})")
    
    if is_new_format:
        # NEW FORMAT: { "image_id": { "s3_key": "path", "description": "text" } }
        for img_id, img_data in mappings.items():
            s3_key = img_data.get('s3_key', '')
            
            if not s3_key:
                continue
            
            # Use regex to match [VISUAL: img_id - ...] or [VISUAL: img_id]
            # This ignores the description part which may be truncated
            import re
            pattern = rf'\[VISUAL:\s*{re.escape(img_id)}(?:\s*-[^\]]+)?\]'
            
            matches = re.findall(pattern, processed_content)
            if matches:
                print(f"  ✓ Found {len(matches)} instance(s) of visual tag for {img_id}")
                image_url = f"https://{bucket}.s3.amazonaws.com/{s3_key}"
                image_markdown = f"\n\n![{img_id}]({image_url})\n\n"
                processed_content = re.sub(pattern, image_markdown, processed_content)
            else:
                print(f"  ✗ No visual tag found for {img_id}")
    else:
        # OLD FORMAT: { "visual_tag": "s3_key" }
        print(f"  Using OLD FORMAT (visual_tag -> s3_key)")
        for visual_tag, image_key in mappings.items():
            if visual_tag in processed_content:
                # Create markdown image reference
                image_url = f"https://{bucket}.s3.amazonaws.com/{image_key}"
                image_markdown = f"\n\n![{visual_tag}]({image_url})\n\n"
                processed_content = processed_content.replace(visual_tag, image_markdown)

    return processed_content

def generate_front_matter(title, author, lesson_count):
    """Generate book front matter."""
    return f"""# {title}

**Author:** {author}  
**Generated by:** Aurora AI Course Generator  
**Total Lessons:** {lesson_count}  
**Publication Date:** {datetime.now().strftime('%B %d, %Y')}

---

## About This Book

This book was automatically generated using Aurora's AI-powered course generation system. It combines structured lesson content with relevant visual aids to create a comprehensive learning resource.

---

"""