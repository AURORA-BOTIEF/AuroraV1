import boto3
import json
import os
from datetime import datetime

def inspect_projects():
    bucket_name = os.getenv('COURSE_BUCKET', 'crewai-course-artifacts')
    s3 = boto3.client('s3')
    
    print(f"Scanning bucket: {bucket_name}")
    
    response = s3.list_objects_v2(Bucket=bucket_name, Delimiter='/')
    
    if 'CommonPrefixes' not in response:
        print("No projects found.")
        return

    print(f"Found {len(response['CommonPrefixes'])} folders. Checking first 10...")
    
    for prefix_obj in response['CommonPrefixes'][:10]:
        folder = prefix_obj['Prefix'].rstrip('/')
        if folder in ['PPT_Templates', 'logo', 'uploads', 'images', 'book'] or folder.startswith('.'):
            continue
            
        print(f"\nProject: {folder}")
        
        # Check metadata.json
        metadata_key = f"{folder}/metadata.json"
        try:
            # Get object with metadata to see LastModified
            obj = s3.get_object(Bucket=bucket_name, Key=metadata_key)
            last_modified = obj['LastModified']
            content = json.loads(obj['Body'].read().decode('utf-8'))
            created = content.get('created', 'MISSING')
            
            print(f"  metadata.json exists")
            print(f"  'created' field: {created}")
            print(f"  LastModified: {last_modified}")
        except Exception as e:
            print(f"  metadata.json error: {e}")
            
            # Check for any file to get a date
            try:
                list_resp = s3.list_objects_v2(Bucket=bucket_name, Prefix=f"{folder}/", MaxKeys=1)
                if 'Contents' in list_resp:
                    print(f"  Fallback file LastModified: {list_resp['Contents'][0]['LastModified']}")
                else:
                    print("  Empty folder")
            except:
                pass

if __name__ == "__main__":
    inspect_projects()
