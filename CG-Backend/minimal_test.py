def lambda_handler(event, context):
    print("Minimal test Lambda invoked")
    print(f"Event: {event}")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-content-sha256",
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        },
        "body": '{"message": "success", "test": true}'
    }
