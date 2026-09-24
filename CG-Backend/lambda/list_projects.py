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

        query_params = event.get("queryStringParameters") or {}
        page = max(int(query_params.get("page", 1)), 1)
        limit = min(max(int(query_params.get("limit", 10)), 1), 100)
        search_term = (query_params.get("search") or "").strip().lower()
        max_workers = min(
            int(os.getenv("LIST_PROJECTS_MAX_WORKERS", str(_DEFAULT_WORKERS))),
            32,
        )

        # Initialize S3 client with configured connection pool size
        from botocore.config import Config
        s3_config = Config(max_pool_connections=max_workers + 5)
        s3_client = boto3.client("s3", region_name=region, config=s3_config)

        excluded_folders = {"PPT_Templates", "logo", "uploads", "images", "book"}
        all_folders = list_all_root_prefixes(s3_client, bucket_name, excluded_folders)
        print(f"--- {len(all_folders)} project prefixes (after exclusions) ---")

        # Sort by creation date string (newest first); folders without date query S3 object timestamps
        folder_dates_cache = {}

        def sort_key(folder):
            d = extract_date_from_folder(folder)
            if d:
                return (d, folder)
            if folder in folder_dates_cache:
                return (folder_dates_cache[folder], folder)
            try:
                res = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f"{folder}/", MaxKeys=3)
                contents = res.get("Contents", [])
                if contents:
                    d = max(obj["LastModified"] for obj in contents).strftime("%Y-%m-%d")
                    folder_dates_cache[folder] = d
                    return (d, folder)
            except Exception:
                pass
            return ("0000-00-00", folder)

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
            # Search all folders by name + outline/metadata title, then enrich only the page.
            print(f"--- Search mode: resolving titles for {len(all_folders)} projects ---")
            search_rows = _map_folders_parallel(
                s3_client,
                bucket_name,
                all_folders,
                max_workers,
                load_search_fields,
            )
            search_rows.sort(
                key=lambda p: (p.get("created") or "", p.get("folder", "")),
                reverse=True,
            )

            matched_folders = [
                row["folder"]
                for row in search_rows
                if _matches_search(search_term, row)
            ]
            print(f"--- Search '{search_term}': {len(matched_folders)} matches ---")

            total_count = len(matched_folders)
            total_pages = max((total_count + limit - 1) // limit, 1)
            start_idx = (page - 1) * limit
            page_folders = matched_folders[start_idx : start_idx + limit]
            projects = _enrich_folders_parallel(
                s3_client, bucket_name, page_folders, max_workers
            )
            folder_order = {f: i for i, f in enumerate(page_folders)}
            projects.sort(key=lambda p: folder_order.get(p["folder"], 999))

            body = {
                "projects": projects,
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


def _folder_slug(project_folder):
    return project_folder.split("-", 1)[1] if "-" in project_folder else project_folder


def _title_is_generic(title, project_folder):
    """True when title is missing or just the folder name (not the real course title)."""
    if not title:
        return True
    t = str(title).strip()
    if not t or t == "Generated Course Book":
        return True
    return t in {project_folder, _folder_slug(project_folder)}


def _matches_search(search_term, row):
    haystack = " ".join(
        [
            row.get("folder") or "",
            row.get("title") or "",
            row.get("description") or "",
            row.get("course_topic") or "",
        ]
    ).lower()
    return search_term in haystack


def _map_folders_parallel(s3_client, bucket_name, folders, max_workers, worker, on_error=None):
    if not folders:
        return []
    workers = min(max_workers, len(folders))
    results = [None] * len(folders)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {
            executor.submit(worker, s3_client, bucket_name, folder): i
            for i, folder in enumerate(folders)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                folder = folders[idx]
                print(f"ERROR mapping {folder}: {e}")
                results[idx] = on_error(folder, str(e)) if on_error else None
    return [r for r in results if r is not None]


def _enrich_folders_parallel(s3_client, bucket_name, folders, max_workers):
    return _map_folders_parallel(
        s3_client,
        bucket_name,
        folders,
        max_workers,
        build_project_row,
        on_error=_fallback_row,
    )


def _fallback_row(project_folder, err):
    print(f"_fallback_row for {project_folder}: {err}")
    slug = _folder_slug(project_folder)
    return {
        "folder": project_folder,
        "title": slug,
        "description": "",
        "created": extract_date_from_folder(project_folder) or "",
        "hasBook": False,
        "hasLabGuide": False,
        "lessonCount": 0,
        "course_topic": slug,
        "model_provider": "bedrock",
    }


def load_search_fields(s3_client, bucket_name, project_folder):
    """Lightweight title/description for searching every project (skips book/lesson checks)."""
    slug = _folder_slug(project_folder)
    title = ""
    description = ""
    course_topic = ""
    created = extract_date_from_folder(project_folder) or ""

    try:
        response = s3_client.get_object(
            Bucket=bucket_name, Key=f"{project_folder}/metadata.json"
        )
        metadata = json.loads(response["Body"].read().decode("utf-8"))
        title = str(metadata.get("title") or "").strip()
        description = str(metadata.get("description") or "").strip()
        course_topic = str(metadata.get("course_topic") or "").strip()
        if not created and metadata.get("created"):
            created = str(metadata["created"])[:10]
    except Exception:
        pass

    if _title_is_generic(title, project_folder) or not description:
        outline = load_outline_fields(s3_client, bucket_name, project_folder)
        if _title_is_generic(title, project_folder) and outline.get("title"):
            title = outline["title"]
        if not description and outline.get("description"):
            description = outline["description"]
        if not course_topic and outline.get("course_topic"):
            course_topic = outline["course_topic"]

    if not title:
        title = slug

    return {
        "folder": project_folder,
        "title": title,
        "description": description,
        "course_topic": course_topic or slug,
        "created": created,
    }


def build_project_row(s3_client, bucket_name, project_folder):
    """
    Build one project descriptor. Does NOT download Generated_Course_Book_data.json
    (too large for list endpoints).
    """
    metadata = load_project_metadata(s3_client, bucket_name, project_folder)
    has_book, has_lab_guide = check_for_book(s3_client, bucket_name, project_folder)

    course_title = metadata.get("title")
    description = metadata.get("description") or ""
    course_topic = metadata.get("course_topic") or ""
    if _title_is_generic(course_title, project_folder) or not description:
        outline = load_outline_fields(s3_client, bucket_name, project_folder)
        if _title_is_generic(course_title, project_folder) and outline.get("title"):
            course_title = outline["title"]
        if (not description or description.startswith("Course project")) and outline.get(
            "description"
        ):
            description = outline["description"]
        if not course_topic and outline.get("course_topic"):
            course_topic = outline["course_topic"]
    if not course_title:
        course_title = _folder_slug(project_folder)

    creation_date = get_project_creation_date(s3_client, bucket_name, project_folder, metadata)

    return {
        "folder": project_folder,
        "title": course_title,
        "description": description,
        "created": creation_date,
        "hasBook": has_book,
        "hasLabGuide": has_lab_guide,
        "lessonCount": metadata.get("lessonCount", 0),
        "course_topic": course_topic or _folder_slug(project_folder),
        "model_provider": metadata.get("model_provider", "bedrock"),
    }


def extract_date_from_folder(folder_name):
    """Extract date from folder name if it starts with YYMMDD."""
    match = re.match(r"^(\d{2})(\d{2})(\d{2})", folder_name)
    if match:
        year, month, day = match.groups()
        return f"20{year}-{month}-{day}"
    return None


def get_project_creation_date(s3_client, bucket_name, project_folder, metadata=None):
    """Get exact creation date from folder prefix, metadata, or S3 object timestamps."""
    folder_date = extract_date_from_folder(project_folder)
    if folder_date:
        return folder_date
    if metadata and metadata.get("created"):
        created_val = str(metadata["created"])
        if len(created_val) >= 10:
            return created_val[:10]
    try:
        res = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f"{project_folder}/", MaxKeys=5)
        contents = res.get("Contents", [])
        if contents:
            dates = [obj["LastModified"] for obj in contents]
            return min(dates).strftime("%Y-%m-%d")
    except Exception:
        pass
    return ""


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

    # Lab guide files are named dynamically (e.g. {title}_LabGuide_data.json)
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=f"{project_folder}/book/",
            Delimiter="/"
        )
        for obj in response.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1].lower()
            if filename.endswith(".json") and ("lab_guide" in filename or "labguide" in filename):
                has_lab_guide = True
                break
    except Exception as e:
        print(f"Error checking lab guide for {project_folder}: {e}")

    return has_book, has_lab_guide


def load_outline_fields(s3_client, bucket_name, project_folder):
    """Extract course title/description from outline.yaml if available."""
    empty = {"title": None, "description": None, "course_topic": None}
    try:
        outline_prefix = f"{project_folder}/outline/"
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=outline_prefix,
            MaxKeys=10,
        )

        for obj in response.get("Contents", []):
            key = obj["Key"]
            if not (key.endswith(".yaml") or key.endswith(".yml")):
                continue
            file_response = s3_client.get_object(Bucket=bucket_name, Key=key)
            outline_content = file_response["Body"].read().decode("utf-8")

            title = None
            description = None
            try:
                import yaml

                outline_data = yaml.safe_load(outline_content)
                course = (outline_data or {}).get("course") if isinstance(outline_data, dict) else None
                if isinstance(course, dict):
                    title = course.get("title")
                    description = course.get("description")
            except Exception:
                pass

            if not title:
                match = re.search(
                    r'course:\s*\n\s*title:\s*["\']?([^"\'\n]+)["\']?',
                    outline_content,
                )
                if match:
                    title = match.group(1).strip()

            if not description:
                match = re.search(
                    r'(?m)^\s*description:\s*["\']?([^"\'\n]+)',
                    outline_content,
                )
                if match:
                    description = match.group(1).strip()

            if isinstance(description, str):
                description = " ".join(description.split())

            return {
                "title": str(title).strip() if title else None,
                "description": description or None,
                "course_topic": str(title).strip() if title else None,
            }

        return empty
    except Exception as e:
        print(f"Error loading outline for {project_folder}: {e}")
        return empty


def get_course_title_from_outline(s3_client, bucket_name, project_folder):
    """Extract course title from outline.yaml if available."""
    return load_outline_fields(s3_client, bucket_name, project_folder).get("title")
