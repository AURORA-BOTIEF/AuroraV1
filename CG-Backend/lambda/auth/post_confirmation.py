import boto3
import os

def lambda_handler(event, context):
    """
    Post-confirmation trigger to add new users to the 'Estudiantes' group.
    """
    print(f"Received event: {event}")
    
    try:
        user_pool_id = event['userPoolId']
        username = event['userName']
        
        # Initialize Cognito Identity Provider client
        client = boto3.client('cognito-idp')
        
        # Add user to 'Estudiantes' group
        group_name = 'Estudiantes'
        
        print(f"Adding user {username} to group {group_name} in pool {user_pool_id}")
        
        client.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=username,
            GroupName=group_name
        )
        
        print(f"Successfully added user {username} to {group_name}")
        
        return event
        
    except Exception as e:
        print(f"Error adding user to group: {str(e)}")
        # Return event anyway to not block sign-up flow, but log error
        return event
