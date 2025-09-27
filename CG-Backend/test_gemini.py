#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for Gemini image generation without AWS dependencies
"""

import os
import json
import base64
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Google Generative AI
import google.generativeai as genai

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

genai.configure(api_key=GOOGLE_API_KEY)

def test_gemini_image_generation(prompt_text, prompt_id, model_name='models/gemini-2.5-flash-image-preview'):
    """Test Gemini image generation for a single prompt"""
    print(f"--- Testing Gemini for prompt: {prompt_id} ---")
    print(f"Prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}")

    try:
        # Initialize Gemini model
        model = genai.GenerativeModel(model_name)

        # Generate image using Gemini
        enhanced_prompt = f"Generate an image: {prompt_text}"
        print(f"Sending to Gemini: {enhanced_prompt[:100]}{'...' if len(enhanced_prompt) > 100 else ''}")

        response = model.generate_content(enhanced_prompt)
        print(f"Gemini response type: {type(response)}")

        # Process the response
        if response and hasattr(response, 'candidates'):
            print(f"Found {len(response.candidates)} candidates")
            for candidate_idx, candidate in enumerate(response.candidates):
                print(f"Checking candidate {candidate_idx}")
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    print(f"Found {len(candidate.content.parts)} parts")
                    for part_idx, part in enumerate(candidate.content.parts):
                        print(f"Checking part {part_idx}, type: {type(part)}")

                        # Check for text parts first
                        if hasattr(part, 'text'):
                            text_content = part.text
                            print(f"Found text part: {text_content[:200]}...")

                            # Check if this is an error message
                            if any(keyword in text_content.lower() for keyword in ['cannot', 'unable', 'error', 'sorry']):
                                print(f"Gemini returned error: {text_content[:100]}...")
                                return False
                            continue

                        if hasattr(part, 'inline_data'):
                            print(f"Found inline_data in part {part_idx}")
                            image_data = part.inline_data
                            image_bytes = image_data.data
                            mime_type = image_data.mime_type

                            print(f"Image data type: {type(image_bytes)}, size: {len(image_bytes) if hasattr(image_bytes, '__len__') else 'unknown'}")
                            print(f"MIME type: {mime_type}")

                            # Check if we have image data
                            if not image_bytes or len(image_bytes) == 0:
                                print(f"Empty image data for {prompt_id}")
                                return False

                            # Try to detect if this is text
                            try:
                                text_check = image_bytes.decode('utf-8', errors='ignore')
                                if len(text_check) > 0 and not text_check.startswith('\x89PNG') and not text_check.startswith('\xff\xd8'):
                                    print(f"Image data appears to be text: {text_check[:200]}...")
                                    return False
                            except:
                                pass

                            # Decode base64 if needed
                            if isinstance(image_bytes, str):
                                print("Decoding base64 image data")
                                image_bytes = base64.b64decode(image_bytes)

                            # Try to create PIL Image
                            print("Creating PIL Image")
                            try:
                                image = Image.open(BytesIO(image_bytes))
                                print(f"Success! Image size: {image.size}, mode: {image.mode}, format: {image.format}")
                                return True
                            except Exception as pil_error:
                                print(f"PIL Error: {pil_error}")

                                # Inspect the bytes
                                first_bytes = image_bytes[:20] if len(image_bytes) > 20 else image_bytes
                                print(f"First 20 bytes: {first_bytes}")

                                # Try different formats
                                if image_bytes.startswith(b'\xff\xd8\xff'):
                                    print("Detected JPEG signature")
                                elif image_bytes.startswith(b'\x89PNG'):
                                    print("Detected PNG signature")
                                elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:20]:
                                    print("Detected WebP signature")
                                else:
                                    print("Unknown format signature")

                                return False
                    else:
                        print("No inline_data found")
                        return False
                else:
                    print("Candidate has no valid content")
                    return False
            else:
                print("No candidates with image data found")
                return False
        else:
            print(f"Unexpected response format: {type(response)}")
            if hasattr(response, 'text'):
                print(f"Response text: {response.text}")
            return False

    except Exception as e:
        print(f"Error testing prompt {prompt_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_specific_prompting_for_2_5():
    """Test specific prompting strategies for gemini-2.5-flash-image-preview"""
    test_prompt = "Kubernetes Deployments hierarchy diagram showing relationship between Deployments, ReplicaSets, and Pods"
    
    print("Testing specific prompting for gemini-2.5-flash-image-preview:")
    print("=" * 60)
    
    # Try different prompt strategies
    prompt_strategies = [
        f"Generate an image: {test_prompt}",
        f"Create a visual diagram image of: {test_prompt}. Return only the image, no text.",
        f"Draw a diagram: {test_prompt}. Output format: image only.",
        f"Generate visual content for: {test_prompt}. Format: PNG image.",
        f"Create an illustration: {test_prompt}. Return as image data."
    ]
    
    for i, prompt in enumerate(prompt_strategies, 1):
        print(f"\n--- Strategy {i}: {prompt[:50]}... ---")
        try:
            model = genai.GenerativeModel('models/gemini-2.5-flash-image-preview')
            response = model.generate_content(prompt)
            
            if response and hasattr(response, 'candidates'):
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data'):
                                print(f"✅ SUCCESS! Strategy {i} returned image data!")
                                return True
                            elif hasattr(part, 'text'):
                                print(f"📝 Strategy {i} returned text: {part.text[:100]}...")
        except Exception as e:
            print(f"❌ Strategy {i} failed: {e}")
        
        # Wait between requests
        import time
        time.sleep(5)
    
    return False

def test_different_models():
    """Test different Gemini models for image generation"""
    models_to_test = [
        'models/gemini-2.5-flash-image-preview',
        'models/gemini-1.5-pro',
        'models/gemini-1.5-flash',
        'models/gemini-pro-vision'
    ]
    
    test_prompt = "Generate a simple diagram of a Kubernetes pod"
    
    for model_name in models_to_test:
        print(f"\n--- Testing model: {model_name} ---")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(test_prompt)
            
            if response and hasattr(response, 'candidates'):
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data'):
                                print(f"✅ {model_name} returned image data!")
                                return model_name
                            elif hasattr(part, 'text'):
                                print(f"📝 {model_name} returned text: {part.text[:100]}...")
        except Exception as e:
            print(f"❌ {model_name} failed: {e}")
    
    return None

def test_first_five_prompts():
    """Test with just the first 5 prompts from the logs with longer delays"""
    test_prompts = [
        {
            "id": "03-01-0001",
            "description": "Kubernetes Deployments hierarchy diagram showing relationship between Deployments, ReplicaSets, and Pods"
        },
        {
            "id": "03-01-0002", 
            "description": "Deployment architecture diagram showing Controller, ReplicaSets, and Pods"
        },
        {
            "id": "03-01-0003",
            "description": "Annotated Deployment YAML showing the relationship between different sections"
        },
        {
            "id": "03-01-0004",
            "description": "Timeline diagram showing Recreate deployment pattern with downtime"
        },
        {
            "id": "03-01-0005",
            "description": "Timeline diagram showing Rolling Update deployment pattern with no downtime"
        }
    ]
    
    print("Testing with first 5 prompts and longer delays")
    print("=" * 50)
    
    successful = 0
    total = len(test_prompts)
    
    for i, prompt in enumerate(test_prompts):
        print(f"\n--- Testing prompt {i+1}/{total} ---")
        result = test_gemini_image_generation(prompt['description'], prompt['id'])
        if result:
            successful += 1
        
        # Add longer delay between requests (except for the last one)
        if i < total - 1:
            print("⏱️  Waiting 10 seconds before next request...")
            import time
            time.sleep(10)
    
    print(f"\nResults: {successful}/{total} prompts successful ({successful/total*100:.1f}%)")

def test_improved_gemini_generation(prompt_text, prompt_id):
    """Test Gemini with improved prompting strategies"""
    print(f"--- Testing improved prompting for: {prompt_id} ---")
    print(f"Original prompt: {prompt_text[:100]}{'...' if len(prompt_text) > 100 else ''}")

    try:
        # Initialize Gemini model
        model = genai.GenerativeModel('models/gemini-2.5-flash-image-preview')

        # Try multiple prompt styles
        prompt_styles = [
            f"Generate a visual diagram image showing: {prompt_text}. Create a clear, professional diagram with labels and visual elements.",
            f"Create an illustration of: {prompt_text}. Make it a graphical diagram with colors and clear labels.",
            f"Draw a diagram for: {prompt_text}. Use visual elements and make it easy to understand."
        ]
        
        for i, prompt_style in enumerate(prompt_styles):
            print(f"🤖 Trying prompt style {i+1}: {prompt_style[:50]}...")
            try:
                response = model.generate_content(prompt_style)
                print(f"📡 Response received")
                
                # Check if we got image data
                if response and hasattr(response, 'candidates'):
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data'):
                                    print(f"🖼️  SUCCESS! Found image data with prompt style {i+1}")
                                    return True
                                elif hasattr(part, 'text'):
                                    print(f"📝 Got text response: {part.text[:100]}...")
            except Exception as e:
                print(f"❌ Error with style {i+1}: {e}")
                continue
        
        print(f"❌ All prompt styles failed for {prompt_id}")
        return False
        
    except Exception as e:
        print(f"Error testing improved prompting for {prompt_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_improved_prompting():
    """Test with improved prompting strategies"""
    test_prompts = [
        {
            "id": "03-01-0001",
            "description": "Kubernetes Deployments hierarchy diagram showing relationship between Deployments, ReplicaSets, and Pods"
        },
        {
            "id": "03-01-0002", 
            "description": "Deployment architecture diagram showing Controller, ReplicaSets, and Pods"
        }
    ]
    
    print("Testing with improved prompting strategies")
    print("=" * 50)
    
    successful = 0
    total = len(test_prompts)
    
    for prompt in test_prompts:
        result = test_improved_gemini_generation(prompt['description'], prompt['id'])
        if result:
            successful += 1
        print()
    
    print(f"Results: {successful}/{total} prompts successful ({successful/total*100:.1f}%)")

def main():
    """Main test function - test specific prompting for gemini-2.5"""
    print("Testing specific prompting strategies for gemini-2.5-flash-image-preview...")
    success = test_specific_prompting_for_2_5()
    
    if success:
        print("\n🎉 Found a working prompt strategy!")
        print("The model can generate images with the right prompting.")
    else:
        print("\n❌ No prompt strategies worked with gemini-2.5-flash-image-preview.")
        print("The model may have changed or have limitations.")

if __name__ == '__main__':
    main()
