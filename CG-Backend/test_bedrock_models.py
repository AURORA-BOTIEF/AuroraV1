#!/usr/bin/env python3
"""
Test script to check Bedrock model access and compare different Claude models.
"""
import boto3
import json
import time
from botocore.exceptions import ClientError

# Initialize Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Models to test
MODELS_TO_TEST = [
    # Claude 4.5 models
    ("Sonnet 4.5 (inference profile)", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    ("Haiku 4.5 (inference profile)", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    
    # Claude 3.5 models (older but proven to work)
    ("Sonnet 3.5 v2 (direct)", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
    ("Haiku 3.5 (direct)", "anthropic.claude-3-5-haiku-20241022-v1:0"),
    ("Sonnet 3.5 v2 (inference profile)", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
    ("Haiku 3.5 (inference profile)", "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
]

def test_model(model_name, model_id):
    """Test if a model is accessible and measure response time."""
    print(f"\n{'='*70}")
    print(f"Testing: {model_name}")
    print(f"Model ID: {model_id}")
    print(f"{'='*70}")
    
    try:
        start_time = time.time()
        
        # Use converse_stream like Strands does
        response = bedrock.converse_stream(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Say 'OK' in one word"}]
                }
            ],
            inferenceConfig={
                "maxTokens": 10,
                "temperature": 0.1
            }
        )
        
        # Consume the stream
        output_text = ""
        input_tokens = 0
        output_tokens = 0
        
        for event in response['stream']:
            if 'contentBlockDelta' in event:
                delta = event['contentBlockDelta']['delta']
                if 'text' in delta:
                    output_text += delta['text']
            elif 'metadata' in event:
                usage = event['metadata'].get('usage', {})
                input_tokens = usage.get('inputTokens', 0)
                output_tokens = usage.get('outputTokens', 0)
        
        elapsed = time.time() - start_time
        
        print(f"✅ SUCCESS")
        print(f"   Response: {output_text.strip()}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Tokens: {input_tokens} in / {output_tokens} out")
        
        return True, elapsed
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        print(f"❌ FAILED")
        print(f"   Error: {error_code}")
        print(f"   Message: {error_msg}")
        
        return False, None
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR")
        print(f"   {type(e).__name__}: {str(e)}")
        return False, None

def main():
    print("\n" + "="*70)
    print("BEDROCK MODEL ACCESS TEST")
    print("="*70)
    
    results = []
    
    for model_name, model_id in MODELS_TO_TEST:
        success, elapsed = test_model(model_name, model_id)
        results.append({
            'name': model_name,
            'model_id': model_id,
            'success': success,
            'time': elapsed
        })
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    working_models = [r for r in results if r['success']]
    failed_models = [r for r in results if not r['success']]
    
    if working_models:
        print(f"\n✅ Working models ({len(working_models)}):")
        # Sort by speed
        working_models.sort(key=lambda x: x['time'] if x['time'] else float('inf'))
        for i, r in enumerate(working_models, 1):
            print(f"   {i}. {r['name']}")
            print(f"      Model ID: {r['model_id']}")
            print(f"      Response time: {r['time']:.2f}s")
    
    if failed_models:
        print(f"\n❌ Failed models ({len(failed_models)}):")
        for r in failed_models:
            print(f"   - {r['name']}")
            print(f"     Model ID: {r['model_id']}")
    
    # Recommendation
    if working_models:
        fastest = working_models[0]
        print(f"\n💡 RECOMMENDATION:")
        print(f"   Use: {fastest['name']}")
        print(f"   Model ID: {fastest['model_id']}")
        print(f"   Fastest response: {fastest['time']:.2f}s")

if __name__ == "__main__":
    main()
