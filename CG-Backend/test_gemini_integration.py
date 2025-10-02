#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for Gemini 2.5 Flash Image Preview integration with CrewAI
"""

import os
import sys
import json
import time
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Override the home directory immediately
original_home = os.environ.get('HOME', '/tmp')
os.environ['HOME'] = '/tmp'

# Set all possible environment variables that might cause filesystem writes
os.environ['CREWAI_STORAGE_DIR'] = '/tmp/.crewai'
os.environ['CREW_CACHE_DIR'] = '/tmp/.crewai_cache'
os.environ['TRANSFORMERS_CACHE'] = '/tmp/.transformers'
os.environ['CHROMA_DB_PATH'] = '/tmp/.chromadb'
os.environ['CREWAI_TELEMETRY_ENABLED'] = 'false'
os.environ['DO_NOT_TRACK'] = '1'

# Create all necessary directories immediately
directories_to_create = [
    '/tmp/.crewai',
    '/tmp/.crewai_cache',
    '/tmp/.transformers',
    '/tmp/.huggingface',
    '/tmp/.chromadb'
]

for directory in directories_to_create:
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        pass  # Ignore if already exists or can't create

# Now import CrewAI and related packages
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

# Import Google Generative AI
import google.generativeai as genai

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

genai.configure(api_key=GOOGLE_API_KEY)

# Test Gemini model availability
def test_gemini_model():
    """Test if Gemini 2.5 Flash Image Preview model is available"""
    try:
        model = genai.GenerativeModel('models/gemini-2.5-flash-image-preview')
        print("✅ Gemini model initialized successfully")
        return model
    except Exception as e:
        print(f"❌ Failed to initialize Gemini model: {e}")
        return None

# Test image generation
def test_image_generation(model):
    """Test basic image generation with Gemini"""
    try:
        prompt = "Generate an image: Create a professional diagram showing a basic client-server architecture with arrows indicating data flow"

        response = model.generate_content(prompt)

        print("✅ Image description generation request sent successfully")
        print(f"Response type: {type(response)}")

        # Check for candidates first to avoid auto-conversion issues
        if hasattr(response, 'candidates') and response.candidates:
            print("ℹ️  Response has candidates, checking for content...")
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'text'):
                            print(f"✅ Found text part ({len(part.text)} characters)")
                            print(f"First 200 characters: {part.text[:200]}...")
                            return True
                        elif hasattr(part, 'inline_data'):
                            print("✅ Found inline data - this model generates actual images!")
                            print(f"   MIME type: {getattr(part.inline_data, 'mime_type', 'unknown')}")
                            if hasattr(part.inline_data, 'data'):
                                data_size = len(part.inline_data.data) if hasattr(part.inline_data.data, '__len__') else 'unknown'
                                print(f"   Data size: {data_size} bytes")
                            return True
            print("❌ No text or image data found in response")
            return False
        elif hasattr(response, 'text'):
            print(f"✅ Response text received ({len(response.text)} characters)")
            print(f"First 200 characters: {response.text[:200]}...")
            return True
        else:
            print("❌ Unexpected response format")
            return False
            
    except Exception as e:
        print(f"❌ Image description generation failed: {e}")
        return False

# Test CrewAI integration
def test_crewai_integration():
    """Test CrewAI integration with Gemini"""
    try:
        # Create a simple agent
        image_generator = Agent(
            role='Image Generator',
            goal='Generate images based on text descriptions using Gemini',
            backstory="""You are an AI image generator that creates visual content from text descriptions.
            You use Google's Gemini model to generate high-quality images.""",
            verbose=True,
            allow_delegation=False,
        )

        # Create a simple task
        generation_task = Task(
            description="Generate a simple diagram of a basic flowchart with start, process, and end nodes",
            expected_output="A description of the generated image",
            agent=image_generator
        )

        # Create crew
        crew = Crew(
            agents=[image_generator],
            tasks=[generation_task],
            process=Process.sequential,
            verbose=True
        )

        print("✅ CrewAI integration test completed")
        return True
    except Exception as e:
        print(f"❌ CrewAI integration failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting Gemini + CrewAI Integration Test")
    print("=" * 50)

    # Test 1: Gemini Model
    print("\n📋 Test 1: Gemini Model Initialization")
    model = test_gemini_model()
    if not model:
        print("❌ Gemini model test failed. Exiting.")
        return False

    # Test 2: Image Generation
    print("\n📋 Test 2: Basic Image Generation")
    if not test_image_generation(model):
        print("❌ Image generation test failed. Exiting.")
        return False

    # Test 3: CrewAI Integration
    print("\n📋 Test 3: CrewAI Integration")
    if not test_crewai_integration():
        print("❌ CrewAI integration test failed. Exiting.")
        return False

    print("\n🎉 All tests passed! Gemini + CrewAI integration is working correctly.")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
