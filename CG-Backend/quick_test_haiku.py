#!/usr/bin/env python3
"""Quick test of Haiku 4.5"""
import boto3
import json
import time

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

print(f"Testing: {model_id}")
start = time.time()

try:
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": "Say OK"}]
        })
    )
    
    result = json.loads(response['body'].read())
    output = result['content'][0]['text']
    usage = result['usage']
    
    elapsed = time.time() - start
    print(f"✅ SUCCESS: {output.strip()} ({elapsed:.2f}s)")
    print(f"   Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out")
    
except Exception as e:
    import traceback
    print(f"❌ FAILED: {e}")
    traceback.print_exc()
