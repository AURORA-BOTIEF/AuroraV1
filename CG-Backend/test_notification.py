import boto3
import json
import sys

def test_notification():
    client = boto3.client('lambda')
    
    payload = {
        "project_folder": "Test-Project-Verification",
        "user_email": "juan.ossa@netec.com", # Sending to the verified email to test
        "input": {
            "some_data": "test"
        }
    }
    
    print(f"Invoking StrandsNotification with payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = client.invoke(
            FunctionName='StrandsNotification',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        response_payload = json.loads(response['Payload'].read())
        print(f"Response: {json.dumps(response_payload, indent=2)}")
        
        if response.get('FunctionError'):
            print("❌ Lambda execution failed!")
            sys.exit(1)
            
        if response_payload.get('statusCode') == 200:
            print("✅ Notification sent successfully!")
        else:
            print("⚠️  Notification might have failed (check logs)")
            
    except Exception as e:
        print(f"❌ Error invoking Lambda: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_notification()
