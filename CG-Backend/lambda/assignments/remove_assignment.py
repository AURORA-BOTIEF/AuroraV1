import boto3
import json
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('ASSIGNMENTS_TABLE', 'CourseAssignments')

def lambda_handler(event, context):
    """
    Remove a course assignment.
    
    Body:
    {
        "userId": "user@email.com",
        "courseId": "project-folder-name"
    }
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        body = json.loads(event.get('body', '{}'))
        user_id = body.get('userId')
        course_id = body.get('courseId')
        
        if not user_id or not course_id:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'userId and courseId are required'})
            }
        
        table = dynamodb.Table(TABLE_NAME)
        
        # Delete the assignment
        table.delete_item(
            Key={
                'userId': user_id,
                'courseId': course_id
            }
        )
        
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'message': 'Assignment removed successfully',
                'userId': user_id,
                'courseId': course_id
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
