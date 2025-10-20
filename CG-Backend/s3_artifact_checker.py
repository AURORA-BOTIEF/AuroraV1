#!/usr/bin/env python3
"""
s3_artifact_checker.py

List S3 objects under a project prefix, count prompts/images/lessons,
download lesson markdowns and scan for visual tags like "[VISUAL: 01-01-0001]",
and compare the sets to report missing images/prompts and orphans.

Usage:
  python3 s3_artifact_checker.py --bucket crewai-course-artifacts --prefix 251018-JS-06/ [--profile myaws]

The script requires boto3. It will use the default AWS credentials/profile unless --profile is provided.
"""
import argparse
import boto3
import botocore
import re
import json
from urllib.parse import unquote_plus


VISUAL_TAG_RE = re.compile(r"\[VISUAL:\s*([^\]\s]+)\]")


def list_s3_objects(s3_client, bucket, prefix):
    paginator = s3_client.get_paginator('list_objects_v2')
    kwargs = {'Bucket': bucket, 'Prefix': prefix}
    keys = []
    for page in paginator.paginate(**kwargs):
        for obj in page.get('Contents', []):
            keys.append(obj['Key'])
    return keys


def get_s3_text(s3_client, bucket, key):
    try:
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        body = resp['Body'].read()
        # try utf-8 decode, fall back to latin-1
        try:
            return body.decode('utf-8')
        except UnicodeDecodeError:
            return body.decode('latin-1')
    except botocore.exceptions.ClientError as e:
        print(f"Error fetching {key}: {e}")
        return None


def normalize_id_from_key(key):
    # return filename without extension
    name = key.rstrip('/').split('/')[-1]
    if '.' in name:
        return name.rsplit('.', 1)[0]
    return name


def extract_visual_ids_from_text(text):
    ids = set()
    for m in VISUAL_TAG_RE.findall(text or ""):
        # strip any surrounding punctuation and possible extension
        id_raw = m.strip()
        if '.' in id_raw:
            id_raw = id_raw.rsplit('.', 1)[0]
        ids.add(id_raw)
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--prefix', required=True, help='Project prefix (e.g. 251018-JS-06/)')
    parser.add_argument('--profile', required=False, help='AWS CLI profile name (optional)')
    parser.add_argument('--region', required=False, default=None, help='AWS region (optional)')
    parser.add_argument('--output', required=False, help='Write JSON report to this file')
    args = parser.parse_args()

    session_kwargs = {}
    if args.profile:
        session_kwargs['profile_name'] = args.profile
    session = boto3.Session(**session_kwargs)
    s3_client = session.client('s3', region_name=args.region)

    prefix = args.prefix
    if not prefix.endswith('/'):
        prefix = prefix + '/'

    print(f"Listing objects in s3://{args.bucket}/{prefix} ...")
    keys = list_s3_objects(s3_client, args.bucket, prefix)
    print(f"Found {len(keys)} total objects under prefix")

    prompts = [k for k in keys if k.startswith(prefix + 'prompts/') and k.lower().endswith('.json')]
    images = [k for k in keys if k.startswith(prefix + 'images/') and (k.lower().endswith('.png') or k.lower().endswith('.jpg') or k.lower().endswith('.jpeg') or k.lower().endswith('.webp'))]
    lessons = [k for k in keys if k.startswith(prefix + 'lessons/') and k.lower().endswith('.md')]

    print(f"Prompts: {len(prompts)} files")
    print(f"Images: {len(images)} files")
    print(f"Lessons: {len(lessons)} files")

    prompt_ids = set(normalize_id_from_key(k) for k in prompts)
    image_ids = set(normalize_id_from_key(k) for k in images)

    visuals_in_lessons = set()
    lesson_visual_map = {}
    for lk in lessons:
        text = get_s3_text(s3_client, args.bucket, lk)
        if text is None:
            continue
        ids = extract_visual_ids_from_text(text)
        lesson_visual_map[lk] = sorted(list(ids))
        visuals_in_lessons.update(ids)

    report = {
        'bucket': args.bucket,
        'prefix': prefix,
        'counts': {
            'total_objects': len(keys),
            'prompts': len(prompts),
            'images': len(images),
            'lessons': len(lessons),
            'visual_tags_found_in_lessons': len(visuals_in_lessons),
        },
        'summary': {},
        'lesson_visual_map': lesson_visual_map,
    }

    report['summary']['visual_ids_in_lessons'] = sorted(list(visuals_in_lessons))
    report['summary']['prompt_ids'] = sorted(list(prompt_ids))
    report['summary']['image_ids'] = sorted(list(image_ids))

    missing_images_for_visuals = sorted(list(visuals_in_lessons - image_ids))
    missing_prompts_for_visuals = sorted(list(visuals_in_lessons - prompt_ids))
    orphan_prompts = sorted(list(prompt_ids - visuals_in_lessons))
    orphan_images = sorted(list(image_ids - visuals_in_lessons))

    report['mismatches'] = {
        'missing_images_for_visuals': missing_images_for_visuals,
        'missing_prompts_for_visuals': missing_prompts_for_visuals,
        'orphan_prompts': orphan_prompts,
        'orphan_images': orphan_images,
    }

    print('\n--- Comparison Summary ---')
    print(f"Unique visual tags found in lessons: {len(visuals_in_lessons)}")
    print(f"Unique prompt ids: {len(prompt_ids)}")
    print(f"Unique image ids: {len(image_ids)}")
    print('')
    print(f"Visual tags without corresponding image files: {len(missing_images_for_visuals)}")
    if missing_images_for_visuals:
        print('Examples (up to 50):')
        for v in missing_images_for_visuals[:50]:
            print('  -', v)

    print(f"Visual tags without corresponding prompt files: {len(missing_prompts_for_visuals)}")
    if missing_prompts_for_visuals:
        print('Examples (up to 50):')
        for v in missing_prompts_for_visuals[:50]:
            print('  -', v)

    print(f"Orphan prompt files (not referenced by any lesson): {len(orphan_prompts)}")
    print(f"Orphan image files (not referenced by any lesson): {len(orphan_images)}")

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\nWrote JSON report to {args.output}")
        except Exception as e:
            print(f"Failed to write report to {args.output}: {e}")

    # Also return exit status indicating whether any missing items exist
    problems = len(missing_images_for_visuals) + len(missing_prompts_for_visuals)
    if problems > 0:
        print('\nResult: Issues found. See report above.')
        exit(2)
    else:
        print('\nResult: No missing prompts/images for visual tags found.')
        exit(0)


if __name__ == '__main__':
    main()
