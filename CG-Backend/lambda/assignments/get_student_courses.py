import boto3
import json
import os
import urllib.parse
import yaml
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
TABLE_NAME = os.environ.get('ASSIGNMENTS_TABLE', 'CourseAssignments')
BUCKET_NAME = os.environ.get('COURSE_BUCKET', 'crewai-course-artifacts')

def lambda_handler(event, context):
    """
    Get courses assigned to a specific student.
    Returns course details along with assignment info.
    
    Path param: userId (URL encoded email)
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        path_params = event.get('pathParameters') or {}
        user_id = path_params.get('userId')
        
        if not user_id:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'userId is required'})
            }
        
        # URL decode the userId
        user_id = urllib.parse.unquote(user_id)
        
        table = dynamodb.Table(TABLE_NAME)
        
        # Get all assignments for this user
        response = table.query(
            KeyConditionExpression=Key('userId').eq(user_id)
        )
        assignments = response.get('Items', [])
        
        # Enrich with course details from S3
        courses = []
        for assignment in assignments:
            course_id = assignment['courseId']
            course_info = get_course_info(course_id)
            courses.append({
                'courseId': course_id,
                'assignedAt': assignment.get('assignedAt'),
                'assignedBy': assignment.get('assignedBy'),
                **course_info
            })
        
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'userId': user_id,
                'courses': courses,
                'count': len(courses)
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def get_course_info(project_folder):
    """Get course info from S3, including title and description from outline."""
    try:
        title = project_folder
        description = ''
        has_book = False
        has_lab_guide = False
        
        # Try to get title and description from outline.yaml
        outline_data = get_outline_data(project_folder)
        if outline_data:
            # Handle nested 'course' key structure
            course_data = outline_data.get('course', outline_data)
            title = course_data.get('title') or course_data.get('course_title') or outline_data.get('course_title') or outline_data.get('title') or project_folder
            description = course_data.get('description') or course_data.get('course_description') or outline_data.get('course_description') or outline_data.get('description') or ''
        
        # Check for book
        try:
            s3_client.head_object(
                Bucket=BUCKET_NAME,
                Key=f"{project_folder}/book/Generated_Course_Book_data.json"
            )
            has_book = True
        except:
            pass
        
        # Check for lab guide
        try:
            s3_client.head_object(
                Bucket=BUCKET_NAME,
                Key=f"{project_folder}/book/Generated_Lab_Guide_data.json"
            )
            has_lab_guide = True
        except:
            pass
        
        # Fallback: try to get title from book metadata if outline didn't have it
        if title == project_folder and has_book:
            try:
                book_response = s3_client.get_object(
                    Bucket=BUCKET_NAME,
                    Key=f"{project_folder}/book/Generated_Course_Book_data.json"
                )
                book_data = json.loads(book_response['Body'].read().decode('utf-8'))
                if 'course_metadata' in book_data and 'title' in book_data['course_metadata']:
                    title = book_data['course_metadata']['title']
            except:
                pass
        
        return {
            'title': title,
            'description': description,
            'hasBook': has_book,
            'hasLabGuide': has_lab_guide
        }
        
    except Exception as e:
        print(f"Error getting course info for {project_folder}: {e}")
        return {
            'title': project_folder,
            'description': '',
            'hasBook': False,
            'hasLabGuide': False
        }


def get_outline_data(project_folder):
    """Get outline data from outline.yaml in the project's outline folder."""
    try:
        # List files in the outline folder
        outline_prefix = f"{project_folder}/outline/"
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=outline_prefix,
            MaxKeys=10
        )
        
        if 'Contents' not in response:
            return None
        
        # Look for outline.yaml or similar files
        outline_files = []
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('.yaml') or key.endswith('.yml'):
                outline_files.append(key)
        
        if not outline_files:
            return None
        
        # Get the first yaml file
        outline_key = outline_files[0]
        outline_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=outline_key
        )
        outline_content = outline_response['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_content)
        
        return outline_data
        
    except Exception as e:
        print(f"Error getting outline for {project_folder}: {e}")
        return None


def cors_headers():
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,GET,POST,PUT,DELETE'
    }
