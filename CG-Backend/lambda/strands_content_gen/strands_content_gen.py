"""
Strands Agents Content Generator
Replaces CrewAI-based content_gen.py with Strands Agents framework.

This Lambda generates course lesson content using Strands Agents multi-agent workflow.
NO DOCKER required - deploys as standard Python Lambda with Layer.

Migration from CrewAI to Strands Agents - Phase 2
Updated: 2025-10-08 - Added outline.yaml support
"""

import os
import sys
import json
import re
import yaml
import boto3
import time
import random
from datetime import datetime
from typing import Dict, Any, List, Optional
from strands import Agent, tool
from strands.models import BedrockModel

# Try to import OpenAIModel dynamically
try:
    from strands.models.openai import OpenAIModel
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAIModel = None
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI model not available in this environment")

# ============================================================================
# CONFIGURATION
# ============================================================================

# Model configuration - respects model_provider parameter
# Bedrock: Claude 3.7 Sonnet (your selected model)
# OpenAI: GPT-5 (your selected model - keeping as requested)
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-5"
DEFAULT_REGION = "us-east-1"

# ============================================================================
# CUSTOM TOOLS FOR S3 OPERATIONS
# ============================================================================

@tool
def read_s3_file(bucket: str, key: str) -> str:
    """
    Read a file from S3 and return its contents as a string.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        File contents as string
    """
    try:
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        print(f"✅ Successfully read {key} from S3")
        return content
    except Exception as e:
        print(f"❌ Error reading {key} from S3: {e}")
        raise


@tool
def write_s3_file(bucket: str, key: str, content: str) -> str:
    """
    Write content to an S3 file.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        content: Content to write
        
    Returns:
        Success message with S3 key
    """
    try:
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='text/markdown'
        )
        print(f"✅ Successfully wrote {key} to S3")
        return f"Successfully saved to s3://{bucket}/{key}"
    except Exception as e:
        print(f"❌ Error writing {key} to S3: {e}")
        raise


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def sanitize_filename(name: str) -> str:
    """Sanitize a string to be used as a valid filename."""
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")


def format_lesson_filename(module_number: int, lesson_index: int, lesson_title: str) -> str:
    """Format lesson filename as module-XX-lesson-YY.md"""
    module_str = f"{module_number:02d}"
    lesson_str = f"{lesson_index + 1:02d}"
    sanitized_title = sanitize_filename(lesson_title).lower().replace("_", "-")
    return f"module-{module_str}-lesson-{lesson_str}.md"


def load_outline_from_yaml(yaml_path: str) -> Dict[str, Any]:
    """Load and parse course outline from YAML file."""
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    return {
        'course_metadata': data.get('course_metadata', {}),
        'modules': data.get('modules', [])
    }


def load_outline_from_s3(s3_client, bucket: str, key: str) -> Dict[str, Any]:
    """Load and parse course outline from S3."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    data = yaml.safe_load(content)

    return {
        'course_metadata': data.get('course_metadata', {}),
        'modules': data.get('modules', [])
    }


def generate_project_folder(course_topic: str, s3_client, bucket: str) -> str:
    """Generate project folder name: YYMMDD-course-topic"""
    date_str = datetime.now().strftime("%y%m%d")
    sanitized_topic = sanitize_filename(course_topic).lower().replace("_", "-")

    # Find existing projects to determine next ID
    prefix = f"{date_str}-{sanitized_topic}-"

    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter='/'
        )

        existing_ids = []
        if 'CommonPrefixes' in response:
            for obj in response['CommonPrefixes']:
                folder_name = obj['Prefix'].rstrip('/')
                if folder_name.startswith(prefix):
                    try:
                        suffix = folder_name[len(prefix):]
                        if suffix.isdigit() and len(suffix) == 2:
                            existing_ids.append(int(suffix))
                    except:
                        continue

        next_id = 1 if not existing_ids else max(existing_ids) + 1
        id_suffix = f"{next_id:02d}"

        return f"{prefix}{id_suffix}"

    except Exception as e:
        print(f"Warning: Could not check existing projects: {e}")
        fallback_suffix = f"{int(time.time()) % 100:02d}"
        return f"{prefix}{fallback_suffix}"


def configure_openai_model() -> Any:
    """
    Configure OpenAI model with enhanced error handling and fallback options.

    Returns:
        Configured OpenAIModel instance

    Raises:
        ValueError: If OpenAI cannot be configured
    """
    if not OPENAI_AVAILABLE or OpenAIModel is None:
        raise ValueError("OpenAI model provider requested but OpenAIModel is not available")

    # Get OpenAI API key
    openai_key = None
    try:
        # Try to get OpenAI API key from Secrets Manager
        openai_secret = get_secret("aurora/openai-api-key")
        openai_key = openai_secret.get('api_key')
        print("Retrieved OpenAI API key from Secrets Manager")
    except Exception as e:
        print(f"Failed to retrieve OpenAI API key from Secrets Manager: {e}")
        # Fallback to environment variable
        openai_key = os.getenv('OPENAI_API_KEY')
        print("Using OpenAI API key from environment variable")

    if not openai_key:
        raise ValueError("OPENAI_API_KEY not found in Secrets Manager or environment variable")

    # Try different configurations to avoid organization verification issues
    configurations = [
        # Try with streaming explicitly disabled
        {"streaming": False},
        # Try without streaming parameter (let library decide)
        {},
        # Try with different model if available
        {"model_id": "gpt-4o", "streaming": False},
        {"model_id": "gpt-4o-mini", "streaming": False},
    ]

    last_error = None
    for i, config in enumerate(configurations):
        try:
            model_kwargs = {
                "client_args": {"api_key": openai_key},
                "model_id": config.get("model_id", DEFAULT_OPENAI_MODEL)
            }

            if "streaming" in config:
                model_kwargs["streaming"] = config["streaming"]

            model = OpenAIModel(**model_kwargs)

            streaming_status = "disabled" if config.get("streaming") is False else "default"
            model_name = config.get("model_id", DEFAULT_OPENAI_MODEL)
            print(f"✅ OpenAI model configured successfully: {model_name} (streaming: {streaming_status})")

            return model

        except Exception as e:
            error_msg = str(e)
            last_error = e
            print(f"⚠️  OpenAI configuration attempt {i+1} failed: {error_msg}")

            # Check for specific organization verification error
            if "organization" in error_msg.lower() and "verified" in error_msg.lower():
                raise ValueError(
                    "OpenAI organization verification required. Please verify your organization at: "
                    "https://platform.openai.com/settings/organization/general. "
                    "This may take up to 15 minutes to propagate."
                ) from e

    # If all configurations failed, raise the last error
    raise ValueError(f"Failed to initialize OpenAI model after {len(configurations)} attempts: {str(last_error)}") from last_error


# ============================================================================
# STRANDS AGENTS - CONTENT GENERATION WORKFLOW
# ============================================================================

def create_content_agents(model, target_words: int = 1500) -> Dict[str, Agent]:
    """
    Create Strands Agents for content generation workflow.
    
    Mimics the CrewAI workflow with three sequential agents:
    1. Researcher - Gathers information about the topic
    2. Writer - Creates structured lesson content
    3. Reviewer - Refines and adds visual placeholders
    
    Args:
        model: Model instance (BedrockModel or OpenAIModel)
        target_words: Target word count for lessons
        
    Returns:
        Dictionary of agents
    """
    
    # Agent 1: Content Researcher
    researcher = Agent(
        model=model,
        system_prompt=f"""You are a Technical Research Specialist.

Research topics and provide structured notes covering:
- Key concepts and definitions
- Technical specifications
- Best practices
- Real-world examples
- Common issues

Output format:
## Key Concepts
## Technical Details  
## Best Practices
## Real-World Examples
## Common Issues

Keep research focused and concise for {target_words} word content.
""",
        tools=[],  # No tools needed for this agent
    )
    
    # Agent 2: Lesson Writer
    writer = Agent(
        model=model,
        system_prompt=f"""You are an Expert Technical Author.

Write comprehensive lesson content with:
- Target: {target_words} words
- Academic yet accessible style
- Clear sections and structure
- Theoretical foundations + practical examples
- Hands-on exercises
- [VISUAL: description] tags for 3-5 diagrams

Standard Structure:
## Introduction
## Theoretical Foundations  
## Practical Implementation
## Real-World Applications
## Hands-On Exercises
## Summary
""",
        tools=[],
    )
    
    # Agent 3: Content Reviewer & Visual Planner
    reviewer = Agent(
        model=model,
        system_prompt="""You are a Content Quality Reviewer.

Review and enhance lesson content:
1. Check completeness and accuracy
2. Ensure proper structure and flow
3. Add 3-5 [VISUAL: description] tags for diagrams
4. Ensure consistent formatting

Output the complete, polished lesson in Markdown format.
""",
        tools=[],
    )
    
    return {
        'researcher': researcher,
        'writer': writer,
        'reviewer': reviewer
    }


def generate_lesson_content(
    agents: Dict[str, Agent],
    lesson_title: str,
    lesson_topics: List[str],
    course_topic: str,
    target_words: int = 1500
) -> str:
    """
    Generate lesson content using multi-agent workflow.
    
    Workflow:
    1. Researcher gathers information
    2. Writer creates structured content
    3. Reviewer refines and adds visuals
    
    Args:
        agents: Dictionary of Strands Agents
        lesson_title: Title of the lesson
        lesson_topics: List of topics to cover
        course_topic: Overall course topic
        target_words: Target word count
        
    Returns:
        Complete lesson content in Markdown
    """
    
    print(f"\n{'='*60}")
    print(f"Generating: {lesson_title}")
    print(f"{'='*60}")
    
    # Step 1: Research
    print("\n[Step 1/3] 🔍 Researching topic...")
    topics_str = "\n- ".join(lesson_topics) if lesson_topics else "General overview"
    
    research_prompt = f"""Research the following lesson topic for a course on {course_topic}:

Lesson: {lesson_title}

Topics to cover:
- {topics_str}

Provide comprehensive research notes covering:
1. Key concepts and definitions
2. Technical specifications
3. Best practices
4. Real-world examples
5. Common issues and troubleshooting

Make your research thorough enough to support {target_words}+ words of content.
"""
    
    research_notes = agents['researcher'](research_prompt)
    print(f"✅ Research complete ({len(str(research_notes).split())} words of notes)")
    
    # Step 2: Write
    print("\n[Step 2/3] ✍️  Writing lesson content...")
    
    # Summarize research notes to reduce token usage
    summary_prompt = f"""Summarize the key points from these research notes for lesson '{lesson_title}':

{research_notes}

Provide a concise summary (max 300 words) covering:
- Main concepts and definitions
- Key technical details
- Best practices
- Important examples

Focus on the most relevant information for creating educational content.
"""
    
    research_summary = agents['researcher'](summary_prompt)
    print(f"✅ Research summarized ({len(str(research_summary).split())} words)")
    
    writing_prompt = f"""Write a comprehensive lesson on '{lesson_title}' for a course about {course_topic}.

SUMMARY OF RESEARCH:
{research_summary}

REQUIREMENTS:
- Target: {target_words} words
- Include: Introduction, Theory, Practice, Examples, Exercises, Summary
- Add 3-5 [VISUAL: description] tags for diagrams
- Academic but accessible style

Structure:
1. Introduction with objectives
2. Theoretical Foundations  
3. Practical Implementation
4. Real-World Applications
5. Hands-On Exercises
6. Summary

Write the complete lesson now.
"""
    
    draft_content = agents['writer'](writing_prompt)
    print(f"✅ Draft complete ({len(str(draft_content).split())} words)")
    
    # Step 3: Review and enhance
    print("\n[Step 3/3] 🔍 Reviewing and enhancing...")
    
    review_prompt = f"""Review and enhance this lesson draft:

{draft_content}

Tasks:
1. Check completeness and accuracy
2. Ensure proper structure  
3. Add 3-5 [VISUAL: description] tags for key diagrams
4. Ensure consistent Markdown formatting

Output the complete, polished lesson.
"""
    
    final_content = agents['reviewer'](review_prompt)
    final_word_count = len(str(final_content).split())
    
    print(f"✅ Review complete")
    print(f"📊 Final word count: {final_word_count} words")
    print(f"{'='*60}\n")
    
    return str(final_content)


def calculate_target_words(lesson_data, module_info):
    """
    Calculate target words for a lesson based on duration and complexity.
    
    Formula:
    - Base words per minute: 120 (conservative reading speed for technical content)
    - Bloom level multiplier: Remember=1.0, Understand=1.1, Apply=1.2, Analyze=1.3, Evaluate=1.4, Create=1.5
    - Topic complexity: additional 100 words per topic
    - Minimum: 600 words, Maximum: 1800 words (reduced to prevent token limits)
    
    Args:
        lesson_data: Lesson data from outline
        module_info: Module information
        
    Returns:
        int: Calculated target words
    """
    
    # Extract lesson duration (default to module duration if not specified)
    lesson_duration = lesson_data.get('duration_minutes', module_info.get('duration_minutes', 45))
    
    # Extract bloom level (default to module level)
    lesson_bloom = lesson_data.get('bloom_level', module_info.get('bloom_level', 'Understand'))
    
    # Count topics
    topics = lesson_data.get('topics', [])
    if topics and isinstance(topics[0], dict):
        topic_count = len(topics)
    elif topics and isinstance(topics[0], str):
        topic_count = len(topics)
    else:
        topic_count = 1  # Minimum 1 topic
    
    # Base calculation: 120 words per minute (conservative for technical content)
    base_words = lesson_duration * 120
    
    # Bloom level multipliers (reduced to prevent excessive token usage)
    bloom_multipliers = {
        'Remember': 1.0,
        'Understand': 1.1,
        'Apply': 1.2,
        'Analyze': 1.3,
        'Evaluate': 1.4,
        'Create': 1.5
    }
    
    bloom_multiplier = bloom_multipliers.get(lesson_bloom, 1.1)  # Default to Understand
    
    # Topic complexity bonus (reduced)
    topic_bonus = topic_count * 100
    
    # Calculate final target
    calculated_words = int((base_words * bloom_multiplier) + topic_bonus)
    
    # Apply bounds (reduced maximum to prevent token limits)
    target_words = max(600, min(1800, calculated_words))
    
    print(f"📊 Target words calculation:")
    print(f"   Duration: {lesson_duration} minutes")
    print(f"   Bloom level: {lesson_bloom} (multiplier: {bloom_multiplier})")
    print(f"   Topics: {topic_count}")
    print(f"   Base words: {base_words}")
    print(f"   Topic bonus: {topic_bonus}")
    print(f"   Calculated: {calculated_words} → Bounded: {target_words}")
    
    return target_words


# ============================================================================
# LAMBDA HANDLER
# ============================================================================

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for Strands Agents content generation.
    
    Expected event format:
    {
        "course_topic": "Kubernetes for DevOps",
        "course_duration_hours": 20,
        "module_to_generate": 2,
        "lesson_to_generate": 1,
        "target_words": 3000,
        "outline_s3_key": "project/outline.yaml",
        "course_bucket": "crewai-course-artifacts",
        "project_folder": "251006-kubernetes-course"
    }
    
    Returns:
    {
        "statusCode": 200,
        "message": "Lesson generated successfully",
        "lesson_key": "project/lessons/module-02-lesson-01.md",
        "project_folder": "project-folder",
        "bucket": "bucket-name"
    }
    """
    
    try:
        print("="*70)
        print("🚀 STRANDS AGENTS CONTENT GENERATOR")
        print("="*70)
        print(f"\n📥 Event: {json.dumps(event, indent=2)}\n")
        
        # Extract parameters
        course_topic = event.get('course_topic', 'Technical Course')
        course_duration_hours = event.get('course_duration_hours', 20)
        module_to_generate = event.get('module_to_generate', 1)
        lesson_to_generate = event.get('lesson_to_generate', 1)
        outline_s3_key = event.get('outline_s3_key')
        course_bucket = event.get('course_bucket', 'crewai-course-artifacts')  # Default bucket
        project_folder = event.get('project_folder')
        
        # Model provider configuration (your original design)
        model_provider = event.get('model_provider', 'bedrock').lower()
        performance_mode = event.get('performance_mode', 'balanced')
        region = os.getenv('AWS_DEFAULT_REGION', DEFAULT_REGION)

        # Configuration for error handling and fallbacks
        # For OpenAI, disable fallback by default to ensure GPT-5 works or fails cleanly
        allow_openai_fallback = event.get('allow_openai_fallback', model_provider != 'openai')
        disable_openai_on_org_error = os.getenv('DISABLE_OPENAI_ON_ORG_ERROR', 'true').lower() == 'true'

        print(f"🤖 Model Provider: {model_provider}")
        print(f"⚡ Performance Mode: {performance_mode}")
        print(f"🔄 OpenAI Fallback Allowed: {allow_openai_fallback}")

        # Configure model based on provider with enhanced error handling
        model = None
        actual_provider = model_provider

        if model_provider == 'openai':
            try:
                model = configure_openai_model()
                print(f"🔵 Using OpenAI: {DEFAULT_OPENAI_MODEL}")
            except ValueError as e:
                error_msg = str(e).lower()
                if "organization" in error_msg and "verified" in error_msg:
                    print(f"⚠️  OpenAI organization verification required: {str(e)}")

                    if disable_openai_on_org_error:
                        print("🔄 Auto-fallback to Bedrock due to organization verification requirement")
                        if allow_openai_fallback:
                            model = BedrockModel(model_id=DEFAULT_BEDROCK_MODEL)
                            actual_provider = 'bedrock'
                            print(f"🟠 Fallback successful: Using Bedrock: {DEFAULT_BEDROCK_MODEL}")
                        else:
                            raise ValueError(
                                "OpenAI organization verification required and fallback disabled. "
                                "Please verify your organization at: "
                                "https://platform.openai.com/settings/organization/general "
                                "or enable allow_openai_fallback=true"
                            ) from e
                    else:
                        raise  # Re-raise if auto-fallback is disabled
                else:
                    # Other OpenAI errors - try fallback if allowed
                    print(f"⚠️  OpenAI configuration error: {str(e)}")
                    if allow_openai_fallback:
                        print("🔄 Fallback to Bedrock due to OpenAI error")
                        model = BedrockModel(model_id=DEFAULT_BEDROCK_MODEL)
                        actual_provider = 'bedrock'
                        print(f"� Fallback successful: Using Bedrock: {DEFAULT_BEDROCK_MODEL}")
                    else:
                        raise
            except Exception as e:
                print(f"❌ OpenAI initialization failed: {str(e)}")
                if allow_openai_fallback:
                    print("🔄 Fallback to Bedrock due to unexpected OpenAI error")
                    model = BedrockModel(model_id=DEFAULT_BEDROCK_MODEL)
                    actual_provider = 'bedrock'
                    print(f"🟠 Fallback successful: Using Bedrock: {DEFAULT_BEDROCK_MODEL}")
                else:
                    raise ValueError(f"OpenAI initialization failed and fallback disabled: {str(e)}") from e

        else:  # bedrock (default)
            model = BedrockModel(model_id=DEFAULT_BEDROCK_MODEL)
            print(f"🟠 Using Bedrock: {DEFAULT_BEDROCK_MODEL}")

        # Ensure we have a valid model
        if model is None:
            raise ValueError("No valid model could be configured. Check your model provider settings.")
        
        print(f"📚 Course: {course_topic}")
        print(f"📦 Module: {module_to_generate}, Lesson: {lesson_to_generate}")
        print(f" Region: {region}")
        
        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=region)
        
        # Load outline
        if outline_s3_key and course_bucket:
            print(f"\n📥 Loading outline from S3: {outline_s3_key}")
            outline_data = load_outline_from_s3(s3_client, course_bucket, outline_s3_key)
        else:
            print("\n📥 Loading outline from local file")
            yaml_path = os.path.join(os.getcwd(), 'outline.yaml')
            if not os.path.exists(yaml_path):
                yaml_path = '/var/task/outline.yaml'
            outline_data = load_outline_from_yaml(yaml_path)
        
        # Extract lesson details
        modules = outline_data['modules']
        
        if module_to_generate > len(modules):
            raise ValueError(f"Module {module_to_generate} not found in outline")
        
        module_data = modules[module_to_generate - 1]
        
        # Handle both CrewAI format (with module_info) and simple frontend format
        if 'module_info' in module_data:
            module_info = module_data['module_info']
        else:
            # Create module_info from simple format
            module_info = {
                'title': module_data.get('module_title', f"Module {module_to_generate}"),
                'module_number': module_data.get('module_number', module_to_generate),
                'summary': module_data.get('module_description', 'Module overview'),
                'duration_minutes': module_data.get('estimated_duration_minutes', 60),
                'percent_theory': 50,
                'percent_practice': 50,
                'bloom_level': 'Understand'
            }
            print(f"⚠️  Using simplified module_info (frontend format detected)")
        
        lessons = module_data['lessons']
        
        if lesson_to_generate > len(lessons):
            raise ValueError(f"Lesson {lesson_to_generate} not found in module {module_to_generate}")
        
        lesson_data = lessons[lesson_to_generate - 1]
        
        # Handle both formats for lesson title
        lesson_title = lesson_data.get('title') or lesson_data.get('lesson_title', 'Untitled Lesson')
        
        # Handle both formats for topics
        topics = lesson_data.get('topics', [])
        if topics and isinstance(topics[0], dict):
            # CrewAI format: [{"title": "..."}]
            lesson_topics = [t['title'] for t in topics]
        elif topics and isinstance(topics[0], str):
            # Simple format: ["...", "..."]
            lesson_topics = topics
        else:
            lesson_topics = []
        
        print(f"\n📖 Generating lesson: {lesson_title}")
        print(f"📝 Topics: {', '.join(lesson_topics) if lesson_topics else 'General overview'}")
        
        # Calculate target words based on lesson complexity and duration
        target_words = calculate_target_words(lesson_data, module_info)
        print(f"🎯 Target words: {target_words}")
        
        # Generate project folder if not provided
        if not project_folder and course_bucket:
            project_folder = generate_project_folder(course_topic, s3_client, course_bucket)
            print(f"📁 Project folder: {project_folder}")
        
        # Generate project folder if not provided
        if not project_folder and course_bucket:
            project_folder = generate_project_folder(course_topic, s3_client, course_bucket)
            print(f"📁 Project folder: {project_folder}")
        
        # Create agents
        print(f"\n🤖 Creating Strands Agents...")
        agents = create_content_agents(model, target_words)
        print(f"✅ Agents ready: researcher, writer, reviewer")
        
        # Generate content
        print(f"\n🎬 Starting content generation workflow...")
        start_time = time.time()

        try:
            lesson_content = generate_lesson_content(
                agents=agents,
                lesson_title=lesson_title,
                lesson_topics=lesson_topics,
                course_topic=course_topic,
                target_words=target_words
            )
        except Exception as content_error:
            error_msg = str(content_error).lower()

            # Check if this is an OpenAI streaming/organization error and we can fallback
            if (actual_provider == 'openai' and
                allow_openai_fallback and
                ("organization" in error_msg and "verified" in error_msg or
                 "stream" in error_msg and "unsupported" in error_msg)):

                print(f"⚠️  OpenAI streaming failed during content generation: {str(content_error)}")
                print("🔄 Attempting fallback to Bedrock for content generation...")

                # Create Bedrock agents for fallback
                try:
                    bedrock_model = BedrockModel(model_id=DEFAULT_BEDROCK_MODEL)
                    bedrock_agents = create_content_agents(bedrock_model, target_words)
                    actual_provider = 'bedrock'

                    print(f"🟠 Fallback successful: Using Bedrock: {DEFAULT_BEDROCK_MODEL}")

                    # Retry content generation with Bedrock
                    lesson_content = generate_lesson_content(
                        agents=bedrock_agents,
                        lesson_title=lesson_title,
                        lesson_topics=lesson_topics,
                        course_topic=course_topic,
                        target_words=target_words
                    )

                    print("✅ Content generation succeeded with Bedrock fallback")

                except Exception as bedrock_error:
                    print(f"❌ Bedrock fallback also failed: {str(bedrock_error)}")
                    raise ValueError(
                        f"Content generation failed with both OpenAI and Bedrock. "
                        f"OpenAI error: {str(content_error)}. Bedrock error: {str(bedrock_error)}"
                    ) from bedrock_error
            else:
                # Re-raise the original error if fallback is not applicable
                raise content_error

        elapsed = time.time() - start_time
        print(f"\n⏱️  Generation completed in {elapsed:.1f} seconds")
        
        # Save to S3
        lesson_filename = format_lesson_filename(module_to_generate, lesson_to_generate - 1, lesson_title)
        lesson_key = f"{project_folder}/lessons/{lesson_filename}"
        
        print(f"\n💾 Saving to S3: {lesson_key}")
        
        s3_client.put_object(
            Bucket=course_bucket,
            Key=lesson_key,
            Body=lesson_content.encode('utf-8'),
            ContentType='text/markdown'
        )
        
        print(f"✅ Lesson saved successfully")
        
        # Prepare response
        response = {
            "statusCode": 200,
            "message": "Lesson generated successfully",
            "lesson_key": lesson_key,
            "project_folder": project_folder,
            "bucket": course_bucket,
            "module_number": module_to_generate,
            "lesson_number": lesson_to_generate,
            "lesson_title": lesson_title,
            "word_count": len(lesson_content.split()),
            "target_words": target_words,
            "generation_time_seconds": round(elapsed, 2),
            "model_provider": actual_provider,  # Include actual provider used (may differ from requested due to fallback)
            "requested_provider": model_provider  # Include originally requested provider
        }
        
        print(f"\n✅ SUCCESS")
        print(f"📊 Response: {json.dumps(response, indent=2)}")
        print("="*70)
        
        return response
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Raise exception instead of returning error to trigger Step Functions retry
        raise e


def get_secret(secret_name, region_name="us-east-1"):
    """Retrieve a secret from AWS Secrets Manager."""
    from botocore.exceptions import ClientError

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)


# ============================================================================
# LOCAL TESTING
# ============================================================================

if __name__ == '__main__':
    # Test event
    test_event = {
        "course_topic": "Kubernetes for DevOps",
        "course_duration_hours": 20,
        "module_to_generate": 1,
        "lesson_to_generate": 1,
        "target_words": 2000,
        "course_bucket": "crewai-course-artifacts",
        "project_folder": "test-project"
    }
    
    class MockContext:
        aws_request_id = 'local-test'
    
    result = lambda_handler(test_event, MockContext())
    print(f"\n\nTest Result: {json.dumps(result, indent=2)}")
