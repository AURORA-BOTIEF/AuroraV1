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
        
        # If no image_mappings provided, scan for existing images and create mappings
        if not image_mappings:
            print("No image_mappings provided, scanning for existing images...")
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
                            # Extract ID from filename (e.g., "01-01-0001.png" -> "[VISUAL: 01-01-0001]")
                            img_filename = img_key.split('/')[-1]
                            img_id = img_filename.replace('.png', '')
                            visual_tag = f"[VISUAL: {img_id}]"
                            image_mappings[visual_tag] = img_key
                            print(f"✅ Found existing image mapping: {visual_tag} -> {img_key}")
                print(f"Created {len(image_mappings)} image mappings from existing images")
            except Exception as e:
                print(f"Warning: Could not scan existing images: {e}")
        
        print(f"Using {len(image_mappings)} image mappings for visual tag replacement")

        # Collect all lessons content
        book_content = []
        toc_entries = []

        for lesson_key in lesson_keys:
            try:
                # Download lesson content
                response = s3_client.get_object(Bucket=course_bucket, Key=lesson_key)
                lesson_content = response['Body'].read().decode('utf-8')

                # Extract lesson title from filename or content
                lesson_filename = lesson_key.split('/')[-1]
                lesson_title = extract_lesson_title(lesson_content, lesson_filename)

                # Replace visual tags with images for this lesson
                processed_content = replace_visual_tags(lesson_content, image_mappings, course_bucket)

                book_content.append({
                    'title': lesson_title,
                    'filename': lesson_filename,
                    'content': processed_content,
                    'word_count': len(processed_content.split())
                })

                toc_entries.append(f"- {lesson_title}")

            except Exception as e:
                print(f"Warning: Failed to process lesson {lesson_key}: {e}")
                continue

        # Generate table of contents
        toc_content = f"# Table of Contents\n\n" + "\n".join(toc_entries) + "\n\n---\n\n"

        # Generate book front matter
        front_matter = generate_front_matter(book_title, author, len(book_content))

        # Combine all content
        full_book_content = front_matter + toc_content

        for i, lesson in enumerate(book_content, 1):
            full_book_content += f"# Lesson {i}: {lesson['title']}\n\n"
            full_book_content += lesson['content']
            full_book_content += "\n\n---\n\n"

        # Add book statistics
        total_words = sum(lesson['word_count'] for lesson in book_content)
        stats_content = f"""## Book Statistics

- **Total Lessons**: {len(book_content)}
- **Total Words**: {total_words}
- **Average Words per Lesson**: {total_words // len(book_content) if book_content else 0}
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
                'total_lessons': len(book_content),
                'total_words': total_words,
                'project_folder': project_folder
            },
            'table_of_contents': toc_entries,
            'lessons': book_content,
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
            "message": f"Successfully built book '{book_title}' with {len(book_content)} lessons",
            "book_title": book_title,
            "book_s3_key": book_filename,
            "book_json_key": book_json_key,
            "course_bucket": course_bucket,
            "project_folder": project_folder,
            "lesson_count": len(book_content),
            "total_words": total_words,
            "book_content": book_json
        }

        print(f"--- Book Builder Complete ---")
        print(f"Generated book: {book_filename}")
        print(f"Lessons included: {len(book_content)}")

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

def extract_lesson_title(content, filename):
    """Extract lesson title from content or filename."""
    # Try to find title in first heading
    lines = content.split('\n')
    for line in lines[:10]:  # Check first 10 lines
        if line.strip().startswith('# '):
            return line.strip()[2:].strip()

    # Fallback to filename
    return filename.replace('.md', '').replace('_', ' ').title()

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