import boto3
import json
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('ASSIGNMENTS_TABLE', 'CourseAssignments')

def lambda_handler(event, context):
    """
    Assign a course to one or more users.
    
    Body:
    {
        "courseId": "project-folder-name",
        "userIds": ["user1@email.com", "user2@email.com"],
        "assignedBy": "assigner@email.com"
    }
    
    OR for single user:
    {
        "userId": "user@email.com",
        "courseIds": ["course1", "course2"],
        "assignedBy": "assigner@email.com"
    }
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        table = dynamodb.Table(TABLE_NAME)
        assigned_by = body.get('assignedBy', 'system')
        timestamp = datetime.utcnow().isoformat()
        
        assignments_created = []
        
        # Mode 1: Assign one course to multiple users
        if 'courseId' in body and 'userIds' in body:
            course_id = body['courseId']
            user_ids = body['userIds']
            
            for user_id in user_ids:
                item = {
                    'userId': user_id,
                    'courseId': course_id,
                    'assignedBy': assigned_by,
                    'assignedAt': timestamp
                }
                table.put_item(Item=item)
                assignments_created.append(item)
        
        # Mode 2: Assign multiple courses to one user
        elif 'userId' in body and 'courseIds' in body:
            user_id = body['userId']
            course_ids = body['courseIds']
            
            for course_id in course_ids:
                item = {
                    'userId': user_id,
                    'courseId': course_id,
                    'assignedBy': assigned_by,
                    'assignedAt': timestamp
                }
                table.put_item(Item=item)
                assignments_created.append(item)
        
        else:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Invalid request. Provide courseId+userIds or userId+courseIds'})
            }
        
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'message': f'Created {len(assignments_created)} assignments',
                'assignments': assignments_created
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def cors_headers():
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,GET,POST,PUT,DELETE'
    }
