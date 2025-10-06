#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    """
    Lambda handler for saving book data from the Book Editor interface.

    Saves book content and metadata to S3.
    """
    try:
        print("--- Saving Book Data ---")

        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        project_folder = body.get('projectFolder')
        book_data = body.get('bookData')

        if not project_folder:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps({
                    "error": "projectFolder is required"
                })
            }

        if not book_data:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST"
                },
                "body": json.dumps({
                    "error": "bookData is required"
                })
            }

        # Get bucket name from environment or default
        bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')

        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

        # Save as JSON
        book_json_key = f"{project_folder}/book/course_book_data.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=book_json_key,
            Body=json.dumps(book_data, indent=2),
            ContentType='application/json'
        )

        # Generate and save as Markdown
        markdown_content = generate_markdown_from_book(book_data)
        book_md_key = f"{project_folder}/book/course_book_complete.md"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=book_md_key,
            Body=markdown_content,
            ContentType='text/markdown'
        )

        response_data = {
            "success": True,
            "message": "Book saved successfully",
            "bookJsonKey": book_json_key,
            "bookMdKey": book_md_key,
            "savedAt": datetime.now().isoformat()
        }

        print(f"Book saved successfully for project: {project_folder}")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps(response_data)
        }

    except Exception as e:
        error_msg = f"Error saving book data: {str(e)}"
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

def generate_markdown_from_book(book_data):
    """Generate markdown content from book data structure."""
    metadata = book_data.get('metadata', {})
    lessons = book_data.get('lessons', [])
    toc = book_data.get('table_of_contents', [])

    markdown = f"# {metadata.get('title', 'Course Book')}\n\n"
    markdown += f"**Author:** {metadata.get('author', 'Aurora AI')}\n"
    markdown += f"**Generated:** {metadata.get('generated_at', datetime.now().isoformat())}\n\n"
    markdown += "---\n\n"
    markdown += "# Table of Contents\n\n"

    for item in toc:
        markdown += f"{item}\n"

    markdown += "\n---\n\n"

    for i, lesson in enumerate(lessons):
        markdown += f"# Lesson {i + 1}: {lesson.get('title', f'Lesson {i + 1}')}\n\n"
        markdown += lesson.get('content', '')
        markdown += "\n---\n\n"

    markdown += "## Book Statistics\n\n"
    markdown += f"- **Total Lessons**: {metadata.get('total_lessons', len(lessons))}\n"
    markdown += f"- **Total Words**: {metadata.get('total_words', 0)}\n"
    markdown += f"- **Last Updated**: {datetime.now().isoformat()}\n"

    return markdown