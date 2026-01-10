import boto3
import json
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('ASSIGNMENTS_TABLE', 'CourseAssignments')

def lambda_handler(event, context):
    """
    List all assignments. Supports filtering by courseId or userId.
    
    Query params:
    - courseId: Filter assignments by course
    - userId: Filter assignments by user
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        query_params = event.get('queryStringParameters') or {}
        course_id = query_params.get('courseId')
        user_id = query_params.get('userId')
        
        table = dynamodb.Table(TABLE_NAME)
        
        if user_id:
            # Query by userId (partition key)
            response = table.query(
                KeyConditionExpression=Key('userId').eq(user_id)
            )
            items = response.get('Items', [])
            
        elif course_id:
            # Query by courseId using GSI
            response = table.query(
                IndexName='CourseIndex',
                KeyConditionExpression=Key('courseId').eq(course_id)
            )
            items = response.get('Items', [])
            
        else:
            # Scan all (use with caution in production)
            response = table.scan(Limit=1000)
            items = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'assignments': items,
                'count': len(items)
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
