#!/usr/bin/env python3
import os
import json
import boto3
import google.generativeai as genai
from botocore.exceptions import ClientError

def get_secret(secret_name: str, region_name: str = "us-east-1"):
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

def test_gemini():
    print("Retrieving Google API key from Secrets Manager...")
    try:
        secret = get_secret("aurora/google-api-key")
        api_key = secret.get('api_key')
        if not api_key:
            print("Error: api_key key not found in secret.")
            return
        print("API Key retrieved successfully.")
    except Exception as e:
        print(f"Error retrieving secret: {e}")
        return

    # Configure Gemini SDK
    genai.configure(api_key=api_key)
    
    # List models to see if gemini-3.5-flash is available
    print("\nListing available models...")
    try:
        models = genai.list_models()
        found_35 = False
        for model in models:
            print(f" - {model.name} ({model.display_name})")
            if "gemini-3.5-flash" in model.name:
                found_35 = True
        
        if found_35:
            print("\n✅ Found gemini-3.5-flash model in the listed models.")
        else:
            print("\n⚠️ gemini-3.5-flash was NOT found in listed models, but we will try direct invocation.")
    except Exception as e:
        print(f"Error listing models: {e}")
    
    # Attempt invocation of various Gemini 3.5 models
    for model_name in ['gemini-3.5-flash', 'gemini-3.5-flash-thinking', 'gemini-3.5-pro', 'gemini-3.5-pro-thinking']:
        print(f"\nAttempting to call '{model_name}'...")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Explain the difference between a list and a tuple in Python in one short sentence.")
            print(f"✅ Success! Response:")
            print(response.text)
        except Exception as e:
            print(f"❌ Failed to call '{model_name}': {e}")

if __name__ == "__main__":
    test_gemini()
