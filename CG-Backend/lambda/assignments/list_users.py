import boto3
import json
import os

cognito_client = boto3.client('cognito-idp')
USER_POOL_ID = os.environ.get('USER_POOL_ID', 'us-east-1_B7QVYyDGp')

def lambda_handler(event, context):
    """
    List users from Cognito User Pool.
    Optionally filter by group.
    
    Query params:
    - group: Filter by Cognito group (e.g., 'Estudiantes')
    - limit: Max users to return (default 60)
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        query_params = event.get('queryStringParameters') or {}
        group_name = query_params.get('group')
        limit = int(query_params.get('limit', 60))
        
        if group_name:
            # List users in a specific group
            response = cognito_client.list_users_in_group(
                UserPoolId=USER_POOL_ID,
                GroupName=group_name,
                Limit=min(limit, 60)
            )
        else:
            # List all users
            response = cognito_client.list_users(
                UserPoolId=USER_POOL_ID,
                Limit=min(limit, 60)
            )
        
        users = []
        for user in response.get('Users', []):
            user_info = {
                'username': user['Username'],
                'status': user['UserStatus'],
                'enabled': user['Enabled'],
                'created': user['UserCreateDate'].isoformat() if user.get('UserCreateDate') else None
            }
            
            # Extract attributes
            for attr in user.get('Attributes', []):
                if attr['Name'] == 'email':
                    user_info['email'] = attr['Value']
                elif attr['Name'] == 'name':
                    user_info['name'] = attr['Value']
            
            users.append(user_info)
        
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'users': users,
                'count': len(users)
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
