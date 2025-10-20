#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    """
    Lambda handler for building a complete Lab Guide Book from generated lab content.

    Expected event format:
    {
        "course_bucket": "bucket-name",
        "project_folder": "250916-course-name-01",
        "lab_keys": ["path/to/lab1.md", "path/to/lab2.md"],  # optional
        "book_title": "Lab Guide Title",
        "author": "Author Name"
    }
    """
    try:
        print("--- Starting Lab Guide Builder ---")
        print(f"Event: {json.dumps(event, indent=2)}")

        # Handle API Gateway events
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
        lab_keys = request_data.get('lab_keys', [])
        book_title = request_data.get('book_title', 'Lab Guide')
        author = request_data.get('author', 'Aurora AI')

        if not course_bucket:
            raise ValueError("course_bucket is required")
        if not project_folder:
            raise ValueError("project_folder is required")

        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

        # Auto-discover lab files if not provided
        if not lab_keys:
            print(f"Auto-discovering lab guides in {project_folder}/labguide/")
            labguide_prefix = f"{project_folder}/labguide/"
            response = s3_client.list_objects_v2(
                Bucket=course_bucket,
                Prefix=labguide_prefix
            )

            if 'Contents' in response:
                lab_keys = [
                    obj['Key'] for obj in response['Contents'] 
                    if obj['Key'].endswith('.md') and 'lab-' in obj['Key'].lower()
                ]
                # Sort lab keys to ensure correct order
                lab_keys.sort()
                print(f"Found {len(lab_keys)} lab guide files: {lab_keys}")
            else:
                print(f"No lab guide files found in {labguide_prefix}")
                lab_keys = []

        if not lab_keys:
            raise ValueError("No lab guides found to build book from")

        # Process each lab guide
        all_labs = []
        modules = {}  # module_number -> {'title': str, 'labs': []}

        for lab_key in lab_keys:
            try:
                print(f"Processing lab: {lab_key}")
                
                # Download lab content
                obj = s3_client.get_object(Bucket=course_bucket, Key=lab_key)
                lab_content = obj['Body'].read().decode('utf-8')

                # Extract lab metadata
                lab_filename = lab_key.split('/')[-1]
                lab_title = extract_lab_title(lab_content, lab_filename)
                module_num, lab_num = extract_module_lab_numbers(lab_filename)
                
                # Normalize title to remove "Lab X-Y-Z:" prefixes
                lab_title = normalize_lab_title(lab_title, lab_num)

                # Extract lab metadata (duration, complexity, Bloom level)
                lab_metadata = extract_lab_metadata(lab_content)

                lab_data = {
                    'title': lab_title,
                    'filename': lab_filename,
                    'content': lab_content,
                    'word_count': len(lab_content.split()),
                    'module_number': module_num,
                    'lab_number': lab_num,
                    'metadata': lab_metadata
                }

                all_labs.append(lab_data)

                # Organize by module
                if module_num not in modules:
                    modules[module_num] = {
                        'title': f"Module {module_num} Labs",
                        'labs': []
                    }
                modules[module_num]['labs'].append(lab_data)

            except Exception as e:
                print(f"Warning: Failed to process lab {lab_key}: {e}")
                continue

        # Sort modules and labs
        sorted_modules = sorted(modules.items(), key=lambda x: x[0])
        for module_num, module_data in sorted_modules:
            module_data['labs'].sort(key=lambda x: x['lab_number'])

        # Generate table of contents
        toc_lines = []
        for module_num, module_data in sorted_modules:
            toc_lines.append(f"\n## {module_data['title']}")
            for lab in module_data['labs']:
                meta = lab['metadata']
                duration = meta.get('duration', 'N/A')
                complexity = meta.get('complexity', 'N/A')
                toc_lines.append(f"  - Lab {lab['lab_number']}: {lab['title']} ({duration}, {complexity})")
        
        toc_content = f"# Table of Contents\n" + "\n".join(toc_lines) + "\n\n---\n\n"

        # Generate front matter
        total_labs = len(all_labs)
        total_duration = sum_durations([lab['metadata'].get('duration', '0 minutos') for lab in all_labs])
        
        front_matter = f"""# {book_title}

**Author:** {author}  
**Generated by:** Aurora AI Lab Guide Generator  
**Total Lab Exercises:** {total_labs}  
**Estimated Total Time:** {total_duration}  
**Publication Date:** {datetime.now().strftime('%B %d, %Y')}

---

## About This Lab Guide

This lab guide was automatically generated to accompany the course material. It contains hands-on practical exercises designed to reinforce the theoretical concepts presented in the lessons. Each lab includes:

- **Learning Objectives**: Clear goals for what you'll accomplish
- **Prerequisites**: Required knowledge and resources
- **Step-by-step Instructions**: Detailed guidance through each exercise
- **Verification Steps**: How to validate your work
- **Troubleshooting**: Common issues and solutions

---

"""

        # Combine all content
        full_book_content = front_matter + toc_content

        for module_num, module_data in sorted_modules:
            # Add module header
            full_book_content += f"\n\n# {module_data['title']}\n\n"
            full_book_content += "---\n\n"
            
            # Add labs within this module
            for lab in module_data['labs']:
                meta = lab['metadata']
                full_book_content += f"## Lab {lab['lab_number']}: {lab['title']}\n\n"
                full_book_content += f"**Duration:** {meta.get('duration', 'N/A')}  \n"
                full_book_content += f"**Complexity:** {meta.get('complexity', 'N/A')}  \n"
                full_book_content += f"**Bloom Level:** {meta.get('bloom_level', 'N/A')}  \n\n"
                full_book_content += lab['content']
                full_book_content += "\n\n---\n\n"

        # Add book statistics
        total_words = sum(lab['word_count'] for lab in all_labs)
        stats_content = f"""## Lab Guide Statistics

- **Total Modules with Labs**: {len(modules)}
- **Total Lab Exercises**: {len(all_labs)}
- **Total Words**: {total_words:,}
- **Estimated Total Time**: {total_duration}
- **Average Words per Lab**: {total_words // len(all_labs) if all_labs else 0}
- **Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Generated by**: Aurora AI Lab Guide Generator

---

## Lab Exercise Summary

"""
        
        # Add detailed lab summary table
        stats_content += "| Module | Lab # | Title | Duration | Complexity |\n"
        stats_content += "|--------|-------|-------|----------|------------|\n"
        for lab in all_labs:
            meta = lab['metadata']
            stats_content += f"| {lab['module_number']} | {lab['lab_number']} | {lab['title'][:50]}... | {meta.get('duration', 'N/A')} | {meta.get('complexity', 'N/A')} |\n"

        full_book_content += stats_content

        # Save to S3
        book_filename = f"{project_folder}/book/{book_title.replace(' ', '_')}_LabGuide_complete.md"
        print(f"Saving lab guide book to: {book_filename}")
        
        s3_client.put_object(
            Bucket=course_bucket,
            Key=book_filename,
            Body=full_book_content.encode('utf-8'),
            ContentType='text/markdown'
        )

        # Create JSON metadata
        book_json = {
            'metadata': {
                'title': book_title,
                'author': author,
                'generated_at': datetime.now().isoformat(),
                'total_modules': len(modules),
                'total_labs': len(all_labs),
                'total_words': total_words,
                'estimated_time': total_duration,
                'project_folder': project_folder
            },
            'modules': [
                {
                    'module_number': module_num,
                    'module_title': module_data['title'],
                    'labs': [
                        {
                            'lab_number': lab['lab_number'],
                            'title': lab['title'],
                            'duration': lab['metadata'].get('duration', 'N/A'),
                            'complexity': lab['metadata'].get('complexity', 'N/A'),
                            'bloom_level': lab['metadata'].get('bloom_level', 'N/A'),
                            'word_count': lab['word_count']
                        }
                        for lab in module_data['labs']
                    ]
                }
                for module_num, module_data in sorted_modules
            ],
            's3_key': book_filename,
            'bucket': course_bucket
        }

        # Save JSON metadata
        json_filename = f"{project_folder}/book/{book_title.replace(' ', '_')}_LabGuide_data.json"
        s3_client.put_object(
            Bucket=course_bucket,
            Key=json_filename,
            Body=json.dumps(book_json, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

        print(f"Successfully created lab guide book with {len(all_labs)} labs")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "statusCode": 200,
                "message": f"Successfully built lab guide '{book_title}' with {len(all_labs)} labs",
                "book_title": book_title,
                "book_s3_key": book_filename,
                "book_json_key": json_filename,
                "course_bucket": course_bucket,
                "project_folder": project_folder,
                "module_count": len(modules),
                "lab_count": len(all_labs),
                "total_words": total_words,
                "estimated_time": total_duration
            })
        }

    except Exception as e:
        error_msg = f"Error building lab guide book: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
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


def extract_lab_title(content, filename):
    """Extract lab title from content or filename."""
    lines = content.split('\n')
    for line in lines[:10]:
        if line.strip().startswith('# '):
            return line.strip()[2:].strip()
    
    # Fallback to filename
    return filename.replace('.md', '').replace('_', ' ').title()


def normalize_lab_title(title, lab_num):
    """Normalize lab title to remove 'Lab XX-YY-ZZ:' prefixes."""
    import re
    
    # Remove "Lab 01-07-01:" or similar patterns
    patterns = [
        r'^Lab\s+\d+-\d+-\d+:\s*',  # Lab 01-07-01:
        r'^Lab\s+\d+:\s*',           # Lab 1:
        r'^Práctica\s+\d+:\s*',      # Práctica 1:
    ]
    
    cleaned_title = title
    for pattern in patterns:
        cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)
    
    return cleaned_title.strip()


def extract_module_lab_numbers(filename):
    """Extract module and lab numbers from filename.
    
    Expected formats:
    - lab-01-07-01-title.md (module 1, lesson 7, lab 1)
    - lab-02-06-01-title.md (module 2, lesson 6, lab 1)
    
    Returns: (module_num, lab_num) as integers
    """
    import re
    
    # Pattern: lab-MM-LL-NN (module-lesson-lab)
    pattern = r'lab-(\d+)-(\d+)-(\d+)'
    match = re.search(pattern, filename.lower())
    
    if match:
        module_num = int(match.group(1))
        # Use the third number as the lab number within that module
        lab_num = int(match.group(3))
        return module_num, lab_num
    
    # Fallback
    print(f"Warning: Could not extract module/lab numbers from {filename}, using defaults")
    return 1, 1


def extract_lab_metadata(content):
    """Extract metadata from lab content (duration, complexity, Bloom level)."""
    metadata = {
        'duration': 'N/A',
        'complexity': 'N/A',
        'bloom_level': 'N/A'
    }
    
    lines = content.split('\n')
    for line in lines[:20]:  # Check first 20 lines
        line_lower = line.lower()
        
        if 'duración:' in line_lower or 'duration:' in line_lower:
            # Extract duration (e.g., "**Duración:** 35 minutos")
            match = re.search(r'(\d+)\s*(minutos|minutes|min)', line, re.IGNORECASE)
            if match:
                metadata['duration'] = f"{match.group(1)} minutos"
        
        if 'complejidad:' in line_lower or 'complexity:' in line_lower:
            # Extract complexity (e.g., "**Complejidad:** Fácil")
            match = re.search(r'(?:complejidad|complexity):\*\*\s*(.+?)(?:\s+|$)', line, re.IGNORECASE)
            if match:
                metadata['complexity'] = match.group(1).strip()
            else:
                # Try without asterisks
                parts = line.split(':')
                if len(parts) > 1:
                    metadata['complexity'] = parts[1].strip().strip('*').strip()
        
        if 'bloom' in line_lower or 'nivel de bloom' in line_lower:
            # Extract Bloom level
            match = re.search(r'(?:bloom|nivel de bloom):\*\*\s*(.+?)(?:\s+|$)', line, re.IGNORECASE)
            if match:
                metadata['bloom_level'] = match.group(1).strip()
            else:
                parts = line.split(':')
                if len(parts) > 1:
                    metadata['bloom_level'] = parts[1].strip().strip('*').strip()
    
    return metadata


def sum_durations(duration_list):
    """Sum all durations in the list and return formatted string."""
    total_minutes = 0
    
    for duration in duration_list:
        # Extract number from strings like "35 minutos"
        match = re.search(r'(\d+)', str(duration))
        if match:
            total_minutes += int(match.group(1))
    
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    if hours > 0:
        return f"{hours}h {minutes}min ({total_minutes} min total)"
    else:
        return f"{minutes} min"
