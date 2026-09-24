#!/usr/bin/env python3
"""Compare available Claude models"""
import boto3
import json
import time

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

MODELS = [
    ("Sonnet 4.5 (current)", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    ("Haiku 4.5", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    ("Haiku 3.5", "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
]

prompt = "Create a simple bullet list with 3 items about Python."

for name, model_id in MODELS:
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Model: {model_id}")
    print(f"{'='*60}")
    
    try:
        start = time.time()
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        output = result['content'][0]['text']
        usage = result['usage']
        elapsed = time.time() - start
        
        print(f"✅ SUCCESS ({elapsed:.2f}s)")
        print(f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out")
        print(f"Response:\n{output[:200]}...")
        
    except Exception as e:
        error_str = str(e)
        if "AccessDenied" in error_str:
            print(f"❌ NOT ENABLED - Need AWS Marketplace subscription")
        else:
            print(f"❌ FAILED: {error_str[:100]}")
