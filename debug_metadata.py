import boto3
import yaml
import os
import json

# Configuration matching the failing course
BUCKET = "crewai-course-artifacts"
PROJECT_FOLDER = "251215-Herramientas-IA-Copilot"

session = boto3.Session(profile_name='Netec')
s3 = session.client('s3')

def debug_outline():
    print(f"--- Debugging Outline Search in {BUCKET}/{PROJECT_FOLDER} ---")
    
    # Strategy 1: outline/ subdirectory
    prefix1 = f"{PROJECT_FOLDER}/outline/"
    print(f"1. Listing Prefix: {prefix1}")
    resp1 = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix1)
    
    found_key = None
    if 'Contents' in resp1:
        for obj in resp1['Contents']:
            print(f"   - Found: {obj['Key']}")
            if obj['Key'].lower().endswith(('.yaml', '.yml')):
                found_key = obj['Key']
                print(f"   -> MATCH (Strategy 1): {found_key}")
                break
    else:
        print("   - No objects found.")

    # Strategy 2: Root fallback
    if not found_key:
        prefix2 = f"{PROJECT_FOLDER}/"
        print(f"2. Listing Prefix (Fallback): {prefix2}")
        resp2 = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix2)
        if 'Contents' in resp2:
            for obj in resp2['Contents']:
                # Filter to avoid deep recursion if possible, but list_objects lists everything recursively by default
                if obj['Key'].lower().endswith(('.yaml', '.yml')) and 'outline' not in obj['Key']:
                     print(f"   - Found potential root yaml: {obj['Key']}")
                     found_key = obj['Key']
                     print(f"   -> MATCH (Strategy 2): {found_key}")
                     break

    if found_key:
        print(f"--- Parsing {found_key} ---")
        obj = s3.get_object(Bucket=BUCKET, Key=found_key)
        content = obj['Body'].read()
        print(f"Raw Content (first 200 chars):\n{content[:200]}")
        
        try:
            data = yaml.safe_load(content)
            print("YAML Parsed Successfully.")
            print("Keys found:", list(data.keys()))
            
            title = data.get('course_title', data.get('title', data.get('name', 'DEFAULT')))
            print(f"EXTRACTED TITLE: '{title}'")
            
            if title == 'DEFAULT':
                print("FAILURE: Could not find course_title, title, or name.")
        except Exception as e:
            print(f"YAML Parse Error: {e}")
    else:
        print("FAILURE: No outline file found in either location.")

if __name__ == "__main__":
    debug_outline()
