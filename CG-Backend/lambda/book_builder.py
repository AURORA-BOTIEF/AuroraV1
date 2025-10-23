#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import boto3
import time
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

        if not course_bucket:
            raise ValueError("course_bucket is required")
        if not project_folder:
            raise ValueError("project_folder is required")

        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

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
        if isinstance(image_mappings, list):
            print(f"Merging {len(image_mappings)} image mapping dictionaries into one")
            merged_mappings = {}
            for mapping_dict in image_mappings:
                if isinstance(mapping_dict, dict):
                    merged_mappings.update(mapping_dict)
            image_mappings = merged_mappings
            print(f"Merged result: {len(image_mappings)} total image mappings")
        
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
                                    # Build visual tag from description
                                    visual_tag = f"[VISUAL: {description}]"
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

                # Replace visual tags with images for this lesson
                processed_content = replace_visual_tags(lesson_content, image_mappings, course_bucket)

                lesson_data = {
                    'title': lesson_title,
                    'filename': lesson_filename,
                    'content': processed_content,
                    'word_count': len(processed_content.split()),
                    'module_number': module_num,
                    'lesson_number': lesson_num
                }

                all_lessons.append(lesson_data)

                # Organize by module
                if module_num not in modules:
                    modules[module_num] = {
                        'title': f"Module {module_num}",  # Will try to extract better title later
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
                module_title = extract_module_title(first_lesson['content'], module_num)
                if module_title:
                    module_data['title'] = module_title

        # Generate hierarchical table of contents
        toc_lines = []
        for module_num, module_data in sorted_modules:
            toc_lines.append(f"\n## {module_data['title']}")
            for lesson in module_data['lessons']:
                toc_lines.append(f"  - Lesson {lesson['lesson_number']}: {lesson['title']}")
        
        toc_content = f"# Table of Contents\n" + "\n".join(toc_lines) + "\n\n---\n\n"

        # Generate book front matter
        total_lessons = len(all_lessons)
        front_matter = generate_front_matter(book_title, author, total_lessons)

        # Combine all content with module hierarchy
        full_book_content = front_matter + toc_content

        for module_num, module_data in sorted_modules:
            # Add module header
            full_book_content += f"\n\n# {module_data['title']}\n\n"
            full_book_content += "---\n\n"
            
            # Add lessons within this module
            for lesson in module_data['lessons']:
                full_book_content += f"## Lesson {lesson['lesson_number']}: {lesson['title']}\n\n"
                full_book_content += lesson['content']
                full_book_content += "\n\n---\n\n"

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

        # Save the complete book to S3
        book_filename = f"{project_folder}/book/{book_title.replace(' ', '_')}_complete.md"
        s3_client.put_object(
            Bucket=course_bucket,
            Key=book_filename,
            Body=full_book_content.encode('utf-8'),
            ContentType='text/markdown'
        )

        # Also save as JSON for easier frontend consumption
        book_json = {
            'metadata': {
                'title': book_title,
                'author': author,
                'generated_at': datetime.now().isoformat(),
                'total_modules': len(modules),
                'total_lessons': len(all_lessons),
                'total_words': total_words,
                'project_folder': project_folder
            },
            'modules': [
                {
                    'module_number': module_num,
                    'module_title': module_data['title'],
                    'lessons': module_data['lessons']
                }
                for module_num, module_data in sorted_modules
            ],
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

def extract_module_title(lesson_content, module_num):
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
                return f"Module {module_num}: {title}"
        
        # Pattern 2: # Module X: Title
        match = re.match(r'#\s*M[oó]dulo\s+\d+:?\s*(.+)', line, re.IGNORECASE)
        if match:
            return f"Module {module_num}: {match.group(1).strip()}"
    
    # Fallback
    return f"Module {module_num}"

def replace_visual_tags(content, mappings, bucket):
    """Replace [VISUAL: description] tags with actual image references."""
    processed_content = content

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