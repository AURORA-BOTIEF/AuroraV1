#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for Google Imagen 4.0 Ultra image generation
Uses Vertex AI API (not the generativeai library)

Requirements:
    pip install google-cloud-aiplatform
    
Setup:
    1. Set up Google Cloud credentials (GOOGLE_APPLICATION_CREDENTIALS or gcloud auth)
    2. Enable Vertex AI API in your Google Cloud project
    3. Set environment variables:
       - GCP_PROJECT_ID: Your Google Cloud project ID
       - GCP_LOCATION: Region (e.g., 'us-central1')
"""

import os
import json
import base64
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import Vertex AI
try:
    from google.cloud import aiplatform
    from vertexai.preview.vision_models import ImageGenerationModel
    print("✅ Vertex AI libraries imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Vertex AI libraries: {e}")
    print("Install with: pip install google-cloud-aiplatform")
    aiplatform = None
    ImageGenerationModel = None

# Configuration
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
GCP_LOCATION = os.getenv('GCP_LOCATION', 'us-central1')  # Default to us-central1
GCP_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')


def initialize_vertex_ai():
    """Initialize Vertex AI with project and location."""
    if not GCP_PROJECT_ID:
        print("❌ GCP_PROJECT_ID environment variable not set")
        return False
    
    # Set credentials path if provided
    if GCP_CREDENTIALS and os.path.exists(GCP_CREDENTIALS):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GCP_CREDENTIALS
        print(f"✅ Using service account: {GCP_CREDENTIALS}")
    
    try:
        aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        print(f"✅ Initialized Vertex AI")
        print(f"   Project: {GCP_PROJECT_ID}")
        print(f"   Location: {GCP_LOCATION}")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Vertex AI: {e}")
        return False


def test_imagen_4_generation(prompt_text, prompt_id, save_to_file=True):
    """
    Test Imagen 4.0 Ultra image generation.
    
    Args:
        prompt_text: Description/prompt for image generation
        prompt_id: Unique identifier for the prompt
        save_to_file: Whether to save generated image to local file
        
    Returns:
        bool: Success status
    """
    print(f"\n{'='*70}")
    print(f"Testing Imagen 4.0 Ultra for prompt: {prompt_id}")
    print(f"{'='*70}")
    print(f"Prompt: {prompt_text[:150]}{'...' if len(prompt_text) > 150 else ''}\n")
    
    try:
        # Load the Imagen 4.0 model
        print("📦 Loading Imagen 4.0 Ultra model...")
        model = ImageGenerationModel.from_pretrained("imagen-4.0-ultra-generate-001")
        print("✅ Model loaded successfully")
        
        # Generate image
        print("🎨 Generating image...")
        print(f"   This may take 10-30 seconds...\n")
        
        # Generate with Imagen 4.0
        # Note: Imagen uses different parameters than Gemini
        images = model.generate_images(
            prompt=prompt_text,
            number_of_images=1,
            aspect_ratio="1:1",  # Options: "1:1", "9:16", "16:9", "4:3", "3:4"
            safety_filter_level="block_some",  # Options: "block_most", "block_some", "block_few"
            person_generation="allow_adult",  # Options: "dont_allow", "allow_adult", "allow_all"
        )
        
        if not images:
            print("❌ No images generated")
            return False
        
        # Get the first image
        image = images[0]
        print(f"✅ Image generated successfully!")
        
        # Access image data
        image_bytes = image._image_bytes
        print(f"   Image size: {len(image_bytes)} bytes")
        
        # Verify it's a valid image using PIL
        try:
            pil_image = Image.open(BytesIO(image_bytes))
            print(f"   Image dimensions: {pil_image.size}")
            print(f"   Image mode: {pil_image.mode}")
            print(f"   Image format: {pil_image.format}")
            
            # Save to file if requested
            if save_to_file:
                output_filename = f"test_imagen_output_{prompt_id}.png"
                pil_image.save(output_filename, format='PNG')
                print(f"   💾 Saved to: {output_filename}")
            
            # Display image info
            if hasattr(image, 'generation_parameters'):
                print(f"\n📊 Generation parameters:")
                print(f"   {image.generation_parameters}")
            
            return True
            
        except Exception as pil_error:
            print(f"❌ Failed to process image with PIL: {pil_error}")
            return False
        
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_imagen_4_with_parameters():
    """Test Imagen 4.0 with various parameter combinations."""
    print("\n" + "="*70)
    print("Testing Imagen 4.0 Ultra with different parameters")
    print("="*70 + "\n")
    
    test_prompt = "Modern professional diagram showing cloud architecture with containers, load balancers, and databases. Clean, technical illustration style."
    
    # Test different aspect ratios
    aspect_ratios = ["1:1", "16:9", "9:16"]
    
    for i, aspect_ratio in enumerate(aspect_ratios, 1):
        print(f"\n--- Test {i}: Aspect ratio {aspect_ratio} ---")
        try:
            model = ImageGenerationModel.from_pretrained("imagen-4.0-ultra-generate-001")
            
            images = model.generate_images(
                prompt=test_prompt,
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                safety_filter_level="block_some",
                person_generation="allow_adult",
            )
            
            if images and len(images) > 0:
                image = images[0]
                pil_image = Image.open(BytesIO(image._image_bytes))
                print(f"✅ Success! Generated {pil_image.size} image")
                
                # Save with aspect ratio in filename
                filename = f"test_imagen_aspect_{aspect_ratio.replace(':', 'x')}.png"
                pil_image.save(filename, format='PNG')
                print(f"   Saved to: {filename}")
            else:
                print(f"❌ No images generated")
                
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Small delay between requests
        import time
        time.sleep(2)


def test_sample_prompts():
    """Test Imagen 4.0 with sample technical diagram prompts."""
    print("\n" + "="*70)
    print("Testing Imagen 4.0 Ultra with sample prompts")
    print("="*70 + "\n")
    
    test_prompts = [
        {
            "id": "test-001",
            "description": "Clean technical diagram showing Kubernetes architecture: master node with API server, scheduler, and controller manager; worker nodes with kubelet and pods. Use blue and white color scheme, minimal style."
        },
        {
            "id": "test-002",
            "description": "Network topology diagram showing a router connected to multiple switches and endpoints. Professional, technical illustration with labeled components and connection lines."
        },
        {
            "id": "test-003",
            "description": "Flowchart diagram showing CI/CD pipeline: code commit, build, test, deploy stages. Modern, clean design with icons and arrows."
        }
    ]
    
    successful = 0
    total = len(test_prompts)
    
    for prompt in test_prompts:
        result = test_imagen_4_generation(
            prompt['description'], 
            prompt['id'],
            save_to_file=True
        )
        if result:
            successful += 1
        
        # Delay between requests
        print("\n⏳ Waiting 5 seconds before next request...")
        import time
        time.sleep(5)
    
    print(f"\n{'='*70}")
    print(f"Results: {successful}/{total} prompts successful ({successful/total*100:.1f}%)")
    print(f"{'='*70}\n")


def compare_prompting_styles():
    """Test different prompt styles to see what works best."""
    print("\n" + "="*70)
    print("Testing different prompting styles for Imagen 4.0")
    print("="*70 + "\n")
    
    base_concept = "Kubernetes deployment architecture"
    
    prompt_styles = [
        {
            "style": "Simple",
            "prompt": base_concept
        },
        {
            "style": "Detailed Technical",
            "prompt": f"Technical diagram of {base_concept} showing deployment controller, replica sets, and pods with connections and labels. Professional technical illustration style."
        },
        {
            "style": "Art Style Specified",
            "prompt": f"{base_concept} as a clean, modern infographic. Flat design, blue color palette, minimalist style with clear labels and icons."
        },
        {
            "style": "Detailed + Constraints",
            "prompt": f"Create a professional technical diagram illustrating {base_concept}. Include: deployment object, replica set, multiple pods. Use clean lines, consistent spacing, label all components. Style: technical documentation illustration, high contrast, easy to read."
        }
    ]
    
    for i, test in enumerate(prompt_styles, 1):
        print(f"\n--- Style {i}: {test['style']} ---")
        print(f"Prompt: {test['prompt'][:100]}...\n")
        
        try:
            model = ImageGenerationModel.from_pretrained("imagen-4.0-ultra-generate-001")
            
            images = model.generate_images(
                prompt=test['prompt'],
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="block_some",
            )
            
            if images and len(images) > 0:
                image = images[0]
                pil_image = Image.open(BytesIO(image._image_bytes))
                print(f"✅ Success! Generated {pil_image.size} image")
                
                filename = f"test_style_{i}_{test['style'].replace(' ', '_').lower()}.png"
                pil_image.save(filename, format='PNG')
                print(f"   Saved to: {filename}")
            else:
                print(f"❌ No images generated")
                
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        # Delay between requests
        import time
        time.sleep(3)


def main():
    """Main test function."""
    print("\n" + "="*70)
    print("Imagen 4.0 Ultra Test Script")
    print("="*70)
    
    # Check if libraries are available
    if not aiplatform or not ImageGenerationModel:
        print("\n❌ Vertex AI libraries not available")
        print("Install with: pip install google-cloud-aiplatform")
        return
    
    # Initialize Vertex AI
    if not initialize_vertex_ai():
        print("\n❌ Failed to initialize Vertex AI")
        print("\nRequired setup:")
        print("1. Set GCP_PROJECT_ID environment variable")
        print("2. Set GCP_LOCATION environment variable (optional, defaults to us-central1)")
        print("3. Authenticate with: gcloud auth application-default login")
        print("4. Enable Vertex AI API in your Google Cloud project")
        return
    
    # Run tests
    print("\n" + "="*70)
    print("Select test to run:")
    print("="*70)
    print("1. Single prompt test")
    print("2. Test different aspect ratios")
    print("3. Test sample technical prompts")
    print("4. Compare prompting styles")
    print("5. Run all tests")
    print("="*70)
    
    choice = input("\nEnter choice (1-5) or 'q' to quit: ").strip()
    
    if choice == '1':
        prompt = input("\nEnter prompt: ").strip()
        if prompt:
            test_imagen_4_generation(prompt, "custom-001", save_to_file=True)
    elif choice == '2':
        test_imagen_4_with_parameters()
    elif choice == '3':
        test_sample_prompts()
    elif choice == '4':
        compare_prompting_styles()
    elif choice == '5':
        test_imagen_4_with_parameters()
        test_sample_prompts()
        compare_prompting_styles()
    elif choice.lower() == 'q':
        print("\nExiting...")
    else:
        print("\n❌ Invalid choice")


if __name__ == '__main__':
    main()
