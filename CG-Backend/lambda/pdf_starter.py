import json
import boto3
import os
import datetime
import uuid
import logging
import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sf_client = boto3.client('stepfunctions')

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Enable CORS
    if event.get('httpMethod') == 'OPTIONS':
        return cors_response(200, '')

    try:
        raw_body = event.get('body')
        
        # Handle Base64 encoding from API Gateway
        if event.get('isBase64Encoded', False) and raw_body:
            raw_body = base64.b64decode(raw_body).decode('utf-8')

        if isinstance(raw_body, str) and raw_body.strip():
             body = json.loads(raw_body)
        elif isinstance(raw_body, dict):
             body = raw_body # Already parsed (integration type dependent)
        else:
             body = {}

        action = body.get('action', 'start')
        
        if action == 'start':
            return handle_start(body)
        elif action == 'check':
            return handle_check(body)
        else:
            return cors_response(400, {'error': f"Unknown action: {action}"})

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return cors_response(500, {'error': str(e)})

def handle_start(body):
    state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
    if not state_machine_arn:
        return cors_response(500, {'error': 'STATE_MACHINE_ARN not configured'})

    s3_key = body.get('s3Key')
    if not s3_key:
        return cors_response(400, {'error': 'Missing s3Key'})
    
    # Validation: Ensure it's a JSON file
    if not s3_key.endswith('.json'):
         return cors_response(400, {'error': 's3Key must be a .json file'})

    execution_name = f"pdf-job-{uuid.uuid4()}"
    input_payload = {
        "s3Key": s3_key,
        "action": "generate",
        # Pass through other potential params
        "course_bucket": body.get('course_bucket', os.environ.get('COURSE_BUCKET')),
        "project_folder": body.get('project_folder')
    }
    
    response = sf_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(input_payload)
    )
    
    return cors_response(200, {
        'message': 'PDF generation started',
        'executionArn': response['executionArn'],
        'startDate': str(datetime.datetime.now())
    })

def handle_check(body):
    execution_arn = body.get('executionArn')
    if not execution_arn:
        # Fallback for old frontend that might send jobId (though we are updating frontend)
        return cors_response(400, {'error': 'Missing executionArn'})

    response = sf_client.describe_execution(executionArn=execution_arn)
    status = response['status']
    
    result = {
        'status': status  # RUNNING, SUCCEEDED, FAILED, TIMED_OUT, ABORTED
    }
    
    if status == 'SUCCEEDED':
        output = json.loads(response.get('output', '{}'))
        # The output from the last state (BookToPdfFunction) should contain the downloadUrl
        # State Machine ResultPath is $.pdf_generation_result
        # So the output of the execution is actually the output of the last state... 
        # Wait, usually output is the whole JSON if we don't filter.
        # Let's assume BookToPdfFunction returns { ... downloadUrl ... }
        # And if SF ends there, that is the output.
        result['output'] = output
        if 'downloadUrl' in output:
             result['downloadUrl'] = output['downloadUrl']
        elif 'pdf_generation_result' in output:
             # If ResultPath was used and preserved structure
             payload = output['pdf_generation_result'].get('Payload', {})
             result['downloadUrl'] = payload.get('downloadUrl')
             result['s3Key'] = payload.get('s3Key')

    return cors_response(200, result)

def cors_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization'
        },
        'body': json.dumps(body)
    }
