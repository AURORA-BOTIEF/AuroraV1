#!/usr/bin/env python3
"""
visual_tag_normalizer.py

Scan lesson markdown files under a project prefix for visual tags like
  [VISUAL: Mockup de interface de SOC Copilot ...]
and attempt to map each descriptive tag to a canonical prompt/image id (based on prompt files in `prompts/`).

It produces a report of suggested replacements and can optionally apply the replacements back to S3 with --apply.

Usage:
  python3 visual_tag_normalizer.py --bucket BUCKET --prefix 251018-JS-06/ [--profile myaws] [--apply]

This script is conservative: it won't alter lesson files unless --apply is provided.
"""
import argparse
import boto3
import botocore
import json
import re
import difflib
from collections import defaultdict

VISUAL_TAG_RE = re.compile(r"\[VISUAL:\s*(.*?)\]")


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
        try:
            return body.decode('utf-8')
        except UnicodeDecodeError:
            return body.decode('latin-1')
    except botocore.exceptions.ClientError as e:
        print(f"Error fetching {key}: {e}")
        return None


def put_s3_text(s3_client, bucket, key, text):
    s3_client.put_object(Bucket=bucket, Key=key, Body=text.encode('utf-8'))


def copy_s3_object(s3_client, bucket, src_key, dest_key):
    # simple S3 copy
    copy_source = {'Bucket': bucket, 'Key': src_key}
    s3_client.copy_object(CopySource=copy_source, Bucket=bucket, Key=dest_key)


def normalize_id_from_key(key):
    name = key.rstrip('/').split('/')[-1]
    if '.' in name:
        return name.rsplit('.', 1)[0]
    return name


def build_prompt_index(s3_client, bucket, prompts_keys):
    index = {}
    searchable = {}
    for k in prompts_keys:
        pid = normalize_id_from_key(k)
        text = get_s3_text(s3_client, bucket, k)
        content = ''
        try:
            j = json.loads(text) if text else {}
            # gather common textual fields
            field_texts = []
            for f in ('title', 'description', 'prompt', 'caption'):
                v = j.get(f)
                if isinstance(v, str):
                    field_texts.append(v)
            # fallback: raw JSON string
            field_texts.append(json.dumps(j, ensure_ascii=False))
            content = ' \n '.join(field_texts)
        except Exception:
            content = text or ''
        index[pid] = k
        searchable[pid] = content
    return index, searchable


def find_best_match(desc, searchable):
    # Try exact substring (case-insensitive)
    desc_norm = desc.strip().lower()
    for pid, text in searchable.items():
        if desc_norm in (text or '').lower():
            return pid, 1.0
    # Otherwise use difflib sequence matcher on the joined searchable strings
    best = (None, 0.0)
    for pid, text in searchable.items():
        if not text:
            continue
        ratio = difflib.SequenceMatcher(None, desc_norm, text.lower()).ratio()
        if ratio > best[1]:
            best = (pid, ratio)
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--profile', required=False)
    parser.add_argument('--region', required=False, default=None)
    parser.add_argument('--apply', action='store_true', help='Apply replacements to S3 lessons')
    parser.add_argument('--min-score', type=float, default=0.45, help='Minimum fuzzy match score to accept')
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

    prompts = [k for k in keys if k.startswith(prefix + 'prompts/') and k.lower().endswith('.json')]
    lessons = [k for k in keys if k.startswith(prefix + 'lessons/') and k.lower().endswith('.md')]

    print(f"Found {len(prompts)} prompts and {len(lessons)} lessons")

    prompt_index, searchable = build_prompt_index(s3_client, args.bucket, prompts)

    suggestions = defaultdict(list)
    total_tags = 0
    unresolved = []

    for lk in lessons:
        text = get_s3_text(s3_client, args.bucket, lk)
        if text is None:
            continue
        tags = VISUAL_TAG_RE.findall(text)
        if not tags:
            continue
        for tag in tags:
            total_tags += 1
            desc = tag.strip()
            # if desc already looks like an id (e.g., 01-01-0001), skip
            if re.match(r'^[0-9]{2}-[0-9]{2}-[0-9]{4}$', desc):
                continue
            pid, score = find_best_match(desc, searchable)
            if pid is None:
                suggestions[lk].append((desc, None, 0.0))
                unresolved.append((lk, desc))
            else:
                suggestions[lk].append((desc, pid, score))

    # Print summary
    print('\nVisual tag normalization suggestions:')
    print(f'Total descriptive visual tags scanned: {total_tags}')
    applied = 0
    for lk, items in suggestions.items():
        print('\nLesson:', lk)
        for desc, pid, score in items:
            if pid is None:
                print(f"  - '{desc}' => NO MATCH")
            else:
                print(f"  - '{desc}' => {pid} (score={score:.2f})")

    # Optionally apply replacements for confident matches
    if args.apply:
        print('\nApplying replacements to S3 lessons (conservative by score)')
        for lk, items in suggestions.items():
            text = get_s3_text(s3_client, args.bucket, lk)
            new_text = text
            changed = False
            for desc, pid, score in items:
                if pid and score >= args.min_score:
                    # replace first occurrence of the exact desc inside VISUAL tag
                    pattern = re.escape(f"[VISUAL: {desc}]")
                    # replacement uses canonical id
                    repl = f"[VISUAL: {pid}]"
                    new_text, n = re.subn(pattern, repl, new_text, count=0)
                    if n > 0:
                        changed = True
                        print(f"Replaced {n} occurrences in {lk}: '{desc}' -> {pid} (score={score:.2f})")
            if changed:
                # backup original to prefix/lessons-backup/
                backup_prefix = prefix + 'lessons-backup/'
                # ensure the backup key mirrors lesson filename
                lesson_name = lk.split('/')[-1]
                backup_key = backup_prefix + lesson_name + '.orig'
                try:
                    copy_s3_object(s3_client, args.bucket, lk, backup_key)
                    print(f"Backed up {lk} -> {backup_key}")
                except Exception as e:
                    print(f"Failed to back up {lk}: {e}")
                # write modified lesson
                put_s3_text(s3_client, args.bucket, lk, new_text)
                applied += 1
        print(f"Applied replacements to {applied} lesson files")

    if unresolved:
        print('\nUnresolved tags (no candidate found):')
        for lk, desc in unresolved:
            print(f"  - {lk}: '{desc}'")

    print('\nDone')


if __name__ == '__main__':
    main()
