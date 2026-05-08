#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
List course projects for Book Builder.

Optimizations:
- Paginate *before* S3 enrichment when there is no search (only enrich current page).
- Never download Generated_Course_Book_data.json for listing (was the main latency source).
- Parallel S3 calls per batch (ThreadPoolExecutor).
- Root ListObjectsV2 follows ContinuationToken for >1000 prefixes.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3

# Max parallel S3 calls (avoid throttling)
_DEFAULT_WORKERS = 16


def lambda_handler(event, context):
    """List projects with metadata for the Book Builder UI."""
    try:
        print("--- Listing Projects ---")

        bucket_name = os.getenv("COURSE_BUCKET", "crewai-course-artifacts")
        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        s3_client = boto3.client("s3", region_name=region)

        query_params = event.get("queryStringParameters") or {}
        page = max(int(query_params.get("page", 1)), 1)
        limit = min(max(int(query_params.get("limit", 10)), 1), 100)
        search_term = (query_params.get("search") or "").strip().lower()
        max_workers = min(
            int(os.getenv("LIST_PROJECTS_MAX_WORKERS", str(_DEFAULT_WORKERS))),
            32,
        )

        excluded_folders = {"PPT_Templates", "logo", "uploads", "images", "book"}
        all_folders = list_all_root_prefixes(s3_client, bucket_name, excluded_folders)
        print(f"--- {len(all_folders)} project prefixes (after exclusions) ---")

        # Sort by creation date string (newest first); folders without date sort last
        def sort_key(folder):
            d = extract_date_from_folder(folder)
            return (d or "0000-00-00", folder)

        all_folders.sort(key=sort_key, reverse=True)

        if not search_term:
            # Fast path: only enrich the current page
            total_count = len(all_folders)
            total_pages = max((total_count + limit - 1) // limit, 1)
            start_idx = (page - 1) * limit
            page_folders = all_folders[start_idx : start_idx + limit]
            projects = _enrich_folders_parallel(
                s3_client, bucket_name, page_folders, max_workers
            )
            # Keep stable order matching page_folders
            folder_order = {f: i for i, f in enumerate(page_folders)}
            projects.sort(key=lambda p: folder_order.get(p["folder"], 999))

            body = {
                "projects": projects,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
            }
        else:
            # Search: need title/description/topic — enrich all, then filter (parallel, no book JSON)
            print(f"--- Search mode: enriching {len(all_folders)} projects ---")
            projects_all = _enrich_folders_parallel(
                s3_client, bucket_name, all_folders, max_workers
            )
            projects_all.sort(key=lambda p: (p.get("created") or "", p.get("folder", "")), reverse=True)

            filtered = [
                p
                for p in projects_all
                if search_term in (p.get("title") or "").lower()
                or search_term in (p.get("folder") or "").lower()
                or search_term in (p.get("description") or "").lower()
                or search_term in (p.get("course_topic") or "").lower()
            ]
            print(f"--- Search '{search_term}': {len(filtered)} matches ---")

            total_count = len(filtered)
            total_pages = max((total_count + limit - 1) // limit, 1)
            start_idx = (page - 1) * limit
            paginated_projects = filtered[start_idx : start_idx + limit]

            body = {
                "projects": paginated_projects,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
            }

        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET",
            },
            "body": json.dumps(body),
        }
        print(
            f"--- Returning page {page}/{body['total_pages']}, {len(body['projects'])} items, total_count={body['total_count']} ---"
        )
        return response

    except Exception as e:
        error_msg = f"Error listing projects: {str(e)}"
        print(f"ERROR: {error_msg}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,GET",
            },
            "body": json.dumps(
                {
                    "error": error_msg,
                    "request_id": context.aws_request_id if context else "unknown",
                }
            ),
        }


def list_all_root_prefixes(s3_client, bucket_name, excluded_folders):
    """All top-level folder names under the bucket (follows continuation)."""
    prefixes = []
    token = None
    while True:
        kwargs = {
            "Bucket": bucket_name,
            "Delimiter": "/",
            "Prefix": "",
        }
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3_client.list_objects_v2(**kwargs)
        for prefix_obj in resp.get("CommonPrefixes", []):
            project_folder = prefix_obj["Prefix"].rstrip("/")
            if project_folder in excluded_folders or project_folder.startswith("."):
                continue
            prefixes.append(project_folder)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return prefixes


def _enrich_folders_parallel(s3_client, bucket_name, folders, max_workers):
    if not folders:
        return []
    workers = min(max_workers, len(folders))
    results = [None] * len(folders)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {
            executor.submit(build_project_row, s3_client, bucket_name, folder): i
            for i, folder in enumerate(folders)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                folder = folders[idx]
                print(f"ERROR enriching {folder}: {e}")
                results[idx] = _fallback_row(folder, str(e))
    return [r for r in results if r is not None]


def _fallback_row(project_folder, err):
    print(f"_fallback_row for {project_folder}: {err}")
    return {
        "folder": project_folder,
        "title": project_folder.split("-", 1)[1] if "-" in project_folder else project_folder,
        "description": "",
        "created": extract_date_from_folder(project_folder) or "",
        "hasBook": False,
        "hasLabGuide": False,
        "lessonCount": 0,
        "course_topic": project_folder.split("-", 1)[1] if "-" in project_folder else project_folder,
        "model_provider": "bedrock",
    }


def build_project_row(s3_client, bucket_name, project_folder):
    """
    Build one project descriptor. Does NOT download Generated_Course_Book_data.json
    (too large for list endpoints).
    """
    metadata = load_project_metadata(s3_client, bucket_name, project_folder)
    has_book, has_lab_guide = check_for_book(s3_client, bucket_name, project_folder)

    course_title = get_course_title_from_outline(s3_client, bucket_name, project_folder)
    if not course_title or course_title == "Generated Course Book":
        course_title = metadata.get(
            "title",
            project_folder.split("-", 1)[1] if "-" in project_folder else project_folder,
        )

    creation_date = extract_date_from_folder(project_folder) or metadata.get("created", "")

    return {
        "folder": project_folder,
        "title": course_title,
        "description": metadata.get("description", ""),
        "created": creation_date,
        "hasBook": has_book,
        "hasLabGuide": has_lab_guide,
        "lessonCount": metadata.get("lessonCount", 0),
        "course_topic": metadata.get("course_topic", ""),
        "model_provider": metadata.get("model_provider", "bedrock"),
    }


def extract_date_from_folder(folder_name):
    """Extract date from folder name if it starts with YYMMDD."""
    match = re.match(r"^(\d{2})(\d{2})(\d{2})", folder_name)
    if match:
        year, month, day = match.groups()
        return f"20{year}-{month}-{day}"
    return None


def load_project_metadata(s3_client, bucket_name, project_folder):
    """Load project metadata from S3 if available, or count lessons."""
    try:
        metadata_key = f"{project_folder}/metadata.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
        metadata = json.loads(response["Body"].read().decode("utf-8"))
        return metadata
    except Exception:
        try:
            lessons_prefix = f"{project_folder}/lessons/"
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=lessons_prefix,
                MaxKeys=100,
            )
            lesson_count = 0
            if "Contents" in response:
                lesson_count = len(
                    [obj for obj in response["Contents"] if obj["Key"].endswith(".md")]
                )

            return {
                "title": project_folder.split("-", 1)[1] if "-" in project_folder else project_folder,
                "description": f"Course project with {lesson_count} lessons",
                "created": extract_date_from_folder(project_folder) or "",
                "lessonCount": lesson_count,
                "course_topic": project_folder.split("-", 1)[1]
                if "-" in project_folder
                else project_folder,
                "model_provider": "bedrock",
            }
        except Exception:
            return {
                "title": project_folder.split("-", 1)[1] if "-" in project_folder else project_folder,
                "description": "Course project",
                "created": extract_date_from_folder(project_folder) or "",
                "lessonCount": 0,
                "course_topic": project_folder.split("-", 1)[1]
                if "-" in project_folder
                else project_folder,
                "model_provider": "bedrock",
            }


def check_for_book(s3_client, bucket_name, project_folder):
    """Check if the project has a completed book and/or lab guide."""
    has_book = False
    has_lab_guide = False

    book_key = f"{project_folder}/book/Generated_Course_Book_data.json"
    try:
        s3_client.head_object(Bucket=bucket_name, Key=book_key)
        has_book = True
    except Exception:
        pass

    lab_key = f"{project_folder}/book/Generated_Lab_Guide_data.json"
    try:
        s3_client.head_object(Bucket=bucket_name, Key=lab_key)
        has_lab_guide = True
    except Exception:
        pass

    return has_book, has_lab_guide


def get_course_title_from_outline(s3_client, bucket_name, project_folder):
    """Extract course title from outline.yaml if available."""
    try:
        outline_prefix = f"{project_folder}/outline/"
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=outline_prefix,
            MaxKeys=10,
        )

        if "Contents" in response:
            for obj in response["Contents"]:
                key = obj["Key"]
                if key.endswith(".yaml") or key.endswith(".yml"):
                    file_response = s3_client.get_object(Bucket=bucket_name, Key=key)
                    outline_content = file_response["Body"].read().decode("utf-8")

                    try:
                        import yaml

                        outline_data = yaml.safe_load(outline_content)
                        if (
                            outline_data
                            and "course" in outline_data
                            and "title" in outline_data["course"]
                        ):
                            return outline_data["course"]["title"]
                    except ImportError:
                        pass
                    except Exception:
                        pass

                    match = re.search(
                        r'course:\s*\n\s*title:\s*["\']?([^"\'\n]+)["\']?',
                        outline_content,
                    )
                    if match:
                        return match.group(1).strip()

        return None
    except Exception as e:
        print(f"Error loading outline for {project_folder}: {e}")
        return None
