#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- CRITICAL: ABSOLUTE FIRST THING - FILESYSTEM WORKAROUND ---
# This MUST be the very first code executed before ANY other imports

# Aggressively force user/home/temp paths to /tmp and monkeypatch common path helpers
import os as _os
import sys as _sys
try:
    # Set safe environment vars early
    _os.environ.setdefault('HOME', '/tmp')
    _os.environ.setdefault('USERPROFILE', '/tmp')
    _os.environ.setdefault('TMPDIR', '/tmp')
    _os.environ.setdefault('XDG_CACHE_HOME', '/tmp/.cache')
    _os.environ.setdefault('XDG_CONFIG_HOME', '/tmp/.config')

    # Monkeypatch os.path.expanduser to avoid resolving to read-only home
    import os.path as _opath

    def _safe_expanduser(path):
        try:
            if isinstance(path, str) and path.startswith('~'):
                return path.replace('~', _os.environ.get('HOME', '/tmp'), 1)
        except Exception:
            pass
        return path

    _opath.expanduser = _safe_expanduser

    # Monkeypatch pathlib.Path.home to return /tmp
    try:
        import pathlib as _pathlib
        _pathlib.Path.home = classmethod(lambda cls: _pathlib.Path(_os.environ.get('HOME', '/tmp')))
    except Exception:
        pass
except Exception:
    # Best-effort only; don't fail import-time
    pass

import os
import sys
import json
import re
import yaml
import boto3
import time
import random
import uuid
import hashlib
from datetime import datetime

# Override the home directory immediately
original_home = os.environ.get('HOME', '/tmp')
os.environ['HOME'] = '/tmp'

# Set all possible environment variables that might cause filesystem writes
os.environ['CREWAI_STORAGE_DIR'] = '/tmp/.crewai'
os.environ['CREW_CACHE_DIR'] = '/tmp/.crewai_cache'
os.environ['TRANSFORMERS_CACHE'] = '/tmp/.transformers'
from dotenv import load_dotenv
os.environ['CHROMA_DB_PATH'] = '/tmp/.chromadb'
os.environ['CREWAI_TELEMETRY_ENABLED'] = 'false'
os.environ['DO_NOT_TRACK'] = '1'
os.environ['ANTHROPIC_LOG'] = 'error'

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

# Load environment variables
load_dotenv()

# Now import CrewAI and related packages
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool

# --- COMPREHENSIVE MONKEY-PATCH FOR AWS LAMBDA ---
# Patch CrewAI's path utilities after import
try:
    import crewai.utilities.paths

    # Override the db_storage_path function to always use /tmp
    def patched_db_storage_path():
        return "/tmp/.crewai"

    crewai.utilities.paths.db_storage_path = patched_db_storage_path
except ImportError:
    pass

# Patch storage classes
try:
    from crewai.memory.storage import kickoff_task_outputs_storage

    class NoOpStorage:
        """A dummy storage class that does nothing."""
        def save(self, *args, **kwargs):
            pass

        def load(self, *args, **kwargs):
            return None

        def reset(self, *args, **kwargs):
            pass

    # Overwrite the original class with our dummy class
    kickoff_task_outputs_storage.KickoffTaskOutputsSQLiteStorage = NoOpStorage
except ImportError:
    pass

# Patch ChromaDB configuration if it exists
try:
    from crewai.rag.chromadb.constants import DEFAULT_STORAGE_PATH
    # Override constant
    import crewai.rag.chromadb.constants
    crewai.rag.chromadb.constants.DEFAULT_STORAGE_PATH = "/tmp/.chromadb"
except ImportError:
    pass

# Additional comprehensive patching
try:
    # Patch any other potential path-related issues
    import crewai

    # Patch the Crew class to disable memory
    original_crew_init = Crew.__init__

    def patched_crew_init(self, *args, **kwargs):
        # Force memory to False
        kwargs['memory'] = False
        return original_crew_init(self, *args, **kwargs)

    Crew.__init__ = patched_crew_init
except ImportError:
    pass

# --- Rate Limiting Classes ---
class RateLimiter:
    """Advanced rate limiter with exponential backoff and proactive delays."""

    def __init__(self, base_delay=1.0, max_delay=60.0, exponential_base=2.0, proactive_delay=0.5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.proactive_delay = proactive_delay
        self.last_call_time = 0
        self.consecutive_failures = 0
        self.total_calls = 0

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        current_time = time.time()

        # Always enforce minimum delay between calls
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < self.proactive_delay:
            sleep_time = self.proactive_delay - time_since_last_call
            print(f"Rate limiter: Sleeping {sleep_time:.2f}s (proactive delay)")
            time.sleep(sleep_time)

        # Exponential backoff for failures
        if self.consecutive_failures > 0:
            backoff_delay = min(self.base_delay * (self.exponential_base ** self.consecutive_failures), self.max_delay)
            print(f"Rate limiter: Sleeping {backoff_delay:.2f}s (exponential backoff)")
            time.sleep(backoff_delay)

        self.last_call_time = time.time()
        self.total_calls += 1

    def record_success(self):
        """Record a successful API call."""
        self.consecutive_failures = 0

    def record_failure(self):
        """Record a failed API call."""
        self.consecutive_failures += 1

class RateLimitedLLM:
    """Wrapper for LLM that enforces rate limiting."""

    def __init__(self, base_llm, rate_limiter):
        self.base_llm = base_llm
        self.rate_limiter = rate_limiter

    def __getattr__(self, name):
        """Delegate all other attributes to the base LLM."""
        return getattr(self.base_llm, name)

    def call(self, *args, **kwargs):
        """Make a rate-limited call to the LLM."""
        self.rate_limiter.wait_if_needed()
        try:
            result = self.base_llm.call(*args, **kwargs)
            self.rate_limiter.record_success()
            return result
        except Exception as e:
            self.rate_limiter.record_failure()
            raise e

# --- Helper Functions ---
def create_unique_filename(description, prefix="visual"):
    """Creates a unique, short, and sanitized filename using a hash."""
    hash_object = hashlib.sha1(description.encode())
    short_hash = hash_object.hexdigest()[:10]
    return f"{prefix}_{short_hash}.png"


def load_course_outline_from_yaml(yaml_path):
    """Load and parse the course outline from YAML file."""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        course_data = yaml.safe_load(f)

    # Support both top-level 'modules' and 'course' -> 'modules'
    course_info = course_data.get('course', {})
    course_metadata = {
        'title': course_info.get('title', 'Technical Course'),
        'description': course_info.get('description', ''),
        'language': course_info.get('language', 'en'),
        'level': course_info.get('level', 'intermediate'),
        'audience': course_info.get('audience', []),
        'prerequisites': course_info.get('prerequisites', []),
        'total_duration_minutes': course_info.get('total_duration_minutes', 1200),
        'learning_outcomes': course_info.get('learning_outcomes', [])
    }

    modules_src = course_data.get('modules')
    if not modules_src:
        modules_src = course_info.get('modules', [])

    parsed_modules = []
    for idx, m in enumerate(modules_src, start=1):
        title = m.get('title') or m.get('name') or f"Module {idx}"
        module_info = {
            'title': title,
            'summary': m.get('summary', ''),
            'duration_minutes': m.get('duration_minutes', 0),
            'percent_theory': m.get('percent_theory', 50),
            'percent_practice': m.get('percent_practice', 50),
            'bloom_level': m.get('bloom_level', 'Understand'),
            'module_number': idx
        }

        lessons = []
        for lesson_idx, lesson in enumerate(m.get('lessons', []) or []):
            if isinstance(lesson, dict):
                lesson_title = lesson.get('title') or f'Lesson {lesson_idx + 1}'
                lesson_info = {
                    'title': lesson_title,
                    'duration_minutes': lesson.get('duration_minutes', 0),
                    'bloom_level': lesson.get('bloom_level', 'Understand'),
                    'lesson_number': lesson_idx + 1,
                    'topics': lesson.get('topics', []),
                    'lab_activities': lesson.get('lab_activities', [])
                }
                lessons.append(lesson_info)
            else:
                lessons.append({
                    'title': str(lesson),
                    'duration_minutes': 0,
                    'bloom_level': 'Understand',
                    'lesson_number': lesson_idx + 1,
                    'topics': [],
                    'lab_activities': []
                })

        parsed_modules.append({
            'module_info': module_info,
            'lessons': lessons
        })

    return {
        'course_metadata': course_metadata,
        'modules': parsed_modules
    }


def execute_crew_with_rate_limiting(crew):
    """Execute a CrewAI crew with rate limiting."""
    try:
        result = crew.kickoff()
        return result
    except Exception as e:
        print(f"Error executing crew: {e}")
        raise e

# --- Main Lambda Handler ---
def lambda_handler(event, context):
    """
    Lambda handler for generating visual plans from content.

    Expected event format:
    {
        "course_bucket": "bucket-name",
        "module_to_generate": 1,  # Optional, defaults to 1. Use 0 for all modules
        "model_provider": "bedrock",  # Optional, "bedrock" or "openai"
        "performance_mode": "balanced",  # Optional
        "content_source": "local"  # Optional, "local" or "s3"
    }
    """
    try:
        print("--- Starting Visual Planning Lambda ---")
        print(f"Event: {json.dumps(event, indent=2)}")

        # --- DEBUG: Print environment variables FIRST to diagnose SAM env-vars issue ---
        print("--- DEBUG: Environment Variables ---")
        env_vars = dict(os.environ)
        for key in sorted(env_vars.keys()):
            if 'KEY' in key or 'SECRET' in key or 'TOKEN' in key or 'PASS' in key:
                val = env_vars[key]
                if len(val) > 20:
                    print(f"{key}={val[:10]}...{val[-10:]}")
                else:
                    print(f"{key}={val}")
            else:
                print(f"{key}={env_vars[key]}")
        print("--- END DEBUG ---")

        # --- Configure LLM Provider (Bedrock or OpenAI) ---
        model_provider = event.get('model_provider', 'bedrock').lower()
        performance_mode = event.get('performance_mode', 'balanced')

        print(f"Model provider: {model_provider}")
        print(f"Performance mode: {performance_mode}")

        # Initialize region for all providers
        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        if model_provider == 'openai':
            # --- Configure OpenAI ---
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
            
            print(f"OPENAI_API_KEY found: {openai_key is not None}")
            if openai_key:
                if len(openai_key) > 20:
                    print(f"OPENAI_API_KEY value: {openai_key[:10]}...{openai_key[-10:]}")
                else:
                    print(f"OPENAI_API_KEY value: {openai_key}")
            
            if not openai_key:
                raise ValueError("OPENAI_API_KEY not found in Secrets Manager or environment variable")
            
            # Use GPT-5 model (now available as of September 2025)
            model_name = "gpt-5"
            model_arn = f"openai/{model_name}"
            
            print(f"Using OpenAI model: {model_name}")
            print(f"Model ARN: {model_arn}")

        else:  # Default to Bedrock
            # --- Configure Bedrock ---
            try:
                # Try to get Bedrock API key from Secrets Manager
                bedrock_secret = get_secret("aurora/bedrock-api-key")
                bedrock_key = bedrock_secret.get('api_key')
                print("Retrieved Bedrock API key from Secrets Manager")
            except Exception as e:
                print(f"Failed to retrieve Bedrock API key from Secrets Manager: {e}")
                # Fallback to environment variable
                bedrock_key = os.getenv('BEDROCK_API_KEY')
                print("Using Bedrock API key from environment variable")
            
            print(f"BEDROCK_API_KEY found: {bedrock_key is not None}")
            if bedrock_key:
                if len(bedrock_key) > 20:
                    print(f"BEDROCK_API_KEY value: {bedrock_key[:10]}...{bedrock_key[-10:]}")
                else:
                    print(f"BEDROCK_API_KEY value: {bedrock_key}")
            
            if not bedrock_key:
                raise ValueError("BEDROCK_API_KEY not found in Secrets Manager or environment variable")

            # PERFORMANCE OPTIMIZATION: Choose model based on performance mode
            if performance_mode == 'ultra_fast':
                # Claude 3.7 Sonnet - Best balance of speed and quality
                model_arn = f"bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
                model_name = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
            elif performance_mode == 'maximum_quality':
                # Claude 3.7 Sonnet - Proven high-quality output with excellent performance
                model_arn = f"bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
                model_name = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
            elif performance_mode == 'fast':
                # Claude 3.7 Sonnet - Consistent quality across all performance modes
                model_arn = f"bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
                model_name = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
            else:  # balanced (default)
                # Claude 3.7 Sonnet - Latest high-quality model with excellent reasoning
                model_arn = f"bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
                model_name = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

            print(f"Using region: {region}")
            print(f"Using Bedrock model: {model_name}")
            print(f"Model ARN: {model_arn}")

        # --- Initialize Global Rate Limiter for Lambda Environment ---
        rate_limiter = RateLimiter(
            base_delay=5.0,      # Aggressive base delay for Lambda
            max_delay=90.0,      # Higher max delay
            exponential_base=2.5, # Faster exponential backoff
            proactive_delay=4.0   # Minimum 4 seconds between any API calls
        )

        # Create base LLM and wrap it with rate limiting
        base_llm = LLM(model=model_arn)
        llm = RateLimitedLLM(base_llm, rate_limiter)

        # Get configuration from event
        course_bucket = event.get('course_bucket')
        module_to_generate = event.get('module_to_generate', 1)
        content_source = event.get('content_source', 'local')
        project_folder = event.get('project_folder')  # Extract project folder from event
        request_id = context.get('aws_request_id') if isinstance(context, dict) else getattr(context, 'aws_request_id', 'unknown')

        print("--- Configuration ---")
        print(f"Bucket: {course_bucket}")
        print(f"Module to generate: {module_to_generate}")
        print(f"Content source: {content_source}")
        print(f"Project folder: {project_folder}")
        print(f"Request ID: {request_id}")

        # Initialize S3 client if needed
        s3_client = None
        if content_source == 's3' or course_bucket:
            s3_client = boto3.client('s3', region_name=region)
            if not course_bucket:
                course_bucket = os.environ.get('OUTPUT_S3_BUCKET')
                if not course_bucket:
                    raise ValueError("course_bucket must be provided when using S3")

        # Load course outline
        possible_paths = [
            os.path.join(os.getcwd(), 'outline.yaml'),
            '/var/task/outline.yaml',
            '/tmp/outline.yaml',
            'outline.yaml'
        ]

        local_yaml_path = None
        for path in possible_paths:
            print(f"Checking for outline at: {path}")
            if os.path.exists(path):
                local_yaml_path = path
                break

        if not local_yaml_path:
            raise Exception("No local outline.yaml found")

        print(f"--- Loading course outline from local YAML: {local_yaml_path} ---")
        outline_data = load_course_outline_from_yaml(local_yaml_path)
        course_metadata = outline_data['course_metadata']
        parsed_modules = outline_data['modules']

        # --- Support explicit lesson_key override (process a single S3 lesson directly) ---
        lesson_key = event.get('lesson_key')
        s3_lesson_overrides = {}
        if lesson_key and s3_client and course_bucket:
            try:
                # Try to read the exact lesson from S3 and map it to its module/lesson numbers
                print(f"--- DEBUG: lesson_key provided, attempting direct S3 fetch: {lesson_key} ---")
                s3_resp = s3_client.get_object(Bucket=course_bucket, Key=lesson_key)
                lesson_text = s3_resp['Body'].read().decode('utf-8')
                filename = lesson_key.split('/')[-1]
                mm = re.match(r'^(?P<mod>\d{2})-(?P<les>\d{2})-(?P<rest>.+)\.md$', filename)
                if mm:
                    mod_num = int(mm.group('mod'))
                    les_num = int(mm.group('les'))
                    s3_lesson_overrides[(mod_num, les_num)] = {
                        'lesson_content': lesson_text,
                        'content_file': lesson_key,
                        'project_folder': lesson_key.split('/')[0]
                    }
                    # Force the loop to focus on this module
                    module_to_generate = mod_num
                    print(f"--- DEBUG: lesson_key maps to module {mod_num} lesson {les_num}; override installed ---")
                else:
                    print(f"--- DEBUG: lesson_key filename did not match expected pattern: {filename} ---")
            except Exception as e:
                print(f"--- DEBUG: unable to fetch lesson_key from S3: {e} ---")

        # Create visual classifier agent
        visual_classifier = Agent(
            role='Visual Asset Classifier',
            goal='Read a list of visual descriptions and classify each as either "artistic_image" or "diagram". Your final output must be a clean JSON object representing this classification.',
            backstory="""You are a logical AI that analyzes requests for visuals. You classify a request as a "diagram" if it describes a flowchart, a layered model, or a sequence. You classify a request as an "artistic_image" if it describes a scene, a metaphor, or a concept. You always return your work as a clean JSON object.""",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )

        # Create prompts directory (for S3 path organization)
        prompts_dir = '/tmp/prompts'
        os.makedirs(prompts_dir, exist_ok=True)

        generated_prompts = []
        visual_tag_regex = re.compile(r'\[VISUAL:\s*(.*?)\]')

        if module_to_generate == 0:
            print("--- Starting Visual Planning for ALL modules ---")
        else:
            print(f"--- Starting Visual Planning for Module {module_to_generate} ---")

        for module_data in parsed_modules:
            module_info = module_data['module_info']
            module_title = module_info['title']
            lessons = module_data['lessons']

            # Extract module number
            module_number = module_info['module_number']

            # Skip if not the target module (unless generating all)
            if module_to_generate != 0 and module_number != module_to_generate:
                continue

            print(f"--- Processing Module {module_number}: {module_title} ---")

            if not lessons:
                print("--- No lessons found for this module ---")
                continue

            # Process each lesson
            for lesson_data in lessons:
                lesson_title = lesson_data['title']
                lesson_number = lesson_data['lesson_number']

                print(f"  -- Processing Lesson {lesson_number}: {lesson_title} --")

                # Initialize variables for this lesson
                content_file = None
                lesson_content = None
                # If an explicit S3 lesson override was provided, use it directly
                if s3_lesson_overrides and (module_number, lesson_number) in s3_lesson_overrides:
                    override = s3_lesson_overrides[(module_number, lesson_number)]
                    lesson_content = override.get('lesson_content')
                    content_file = override.get('content_file')
                    # Ensure project_folder is taken from the override so prompts are saved under the correct prefix
                    project_folder = override.get('project_folder', project_folder)
                    print(f"    -- Using lesson_key override for module {module_number} lesson {lesson_number}: {content_file} --")
                    # Proceed to processing visual tags for this lesson
                else:
                    if content_source == 'local':
                        # Look for content in the out directory (where content_gen saves)
                        # content_gen names files like AA-BB-<lesson_title>-<model>.md (e.g. 03-01-Intro-bedrock.md)
                        out_dir = os.path.join(os.getcwd(), 'out')
                        if os.path.exists(out_dir):
                            for root, dirs, files in os.walk(out_dir):
                                for filename in files:
                                    if not filename.endswith('.md'):
                                        continue
                                    # Match the AA-BB-... pattern used by content_gen
                                    m = re.match(r'^(?P<mod>\d{2})-(?P<les>\d{2})-(?P<rest>.+)\.md$', filename)
                                    if not m:
                                        continue
                                    try:
                                        mod_num = int(m.group('mod'))
                                        les_num = int(m.group('les'))
                                    except Exception:
                                        continue
                                    if mod_num == module_number and les_num == lesson_number:
                                        content_file = os.path.join(root, filename)
                                        break
                                if content_file:
                                    break

                        if content_file and os.path.exists(content_file):
                            print(f"  -- Reading content from local file: {content_file} --")
                            with open(content_file, 'r', encoding='utf-8') as f:
                                lesson_content = f.read()
                        else:
                            print(f"  -- Local content file not found for lesson {lesson_number}, trying S3 --")
                            content_source = 's3'  # Fallback to S3
                
                if content_source == 's3' and s3_client and course_bucket:
                    print(f"  -- DEBUG: S3 section reached, content_source={content_source}, s3_client={s3_client is not None}, course_bucket={course_bucket} --")
                    # Try to find content in S3
                    try:
                        # If project_folder is provided, restrict to that prefix and do NOT fall back
                        # to other project folders. This ensures we only read files for the requested
                        # project and prevents accidental processing of other projects' prompts.
                        search_prefix = f"{project_folder}/" if project_folder else ""
                        response = s3_client.list_objects_v2(Bucket=course_bucket, Prefix=search_prefix)

                        if 'Contents' not in response or not response['Contents']:
                            print(f"  -- No objects found under search prefix '{search_prefix}' in S3 bucket --")
                        else:
                            print(f"  -- Found {len(response['Contents'])} objects under prefix '{search_prefix}' in S3 bucket --")
                            print(f"  -- DEBUG: About to start checking objects under prefix '{search_prefix}' --")

                            found = False
                            for obj in response['Contents']:
                                key = obj['Key']
                                # Only consider lesson markdown files under a lessons/ path
                                if '/lessons/' not in key or not key.endswith('.md'):
                                    print(f"    -- Skipping non-lesson key: {key} --")
                                    continue

                                filename = key.split('/')[-1]
                                m = re.match(r'^(?P<mod>\d{2})-(?P<les>\d{2})-(?P<rest>.+)\.md$', filename)
                                if not m:
                                    continue
                                try:
                                    mod_num = int(m.group('mod'))
                                    les_num = int(m.group('les'))
                                except Exception:
                                    continue

                                if mod_num == module_number and les_num == lesson_number:
                                    print(f"  -- MATCH FOUND: {key} --")
                                    try:
                                        print(f"  -- Reading content from S3: {key} --")
                                        s3_response = s3_client.get_object(Bucket=course_bucket, Key=key)
                                        lesson_content = s3_response['Body'].read().decode('utf-8')
                                        content_file = key
                                        found = True
                                        break
                                    except Exception as e:
                                        print(f"  -- Error getting S3 object {key}: {e} --")

                            if not found and project_folder:
                                print(f"  -- No matching lesson found in specified project folder '{project_folder}'; skipping (no global fallback) --")
                            elif not found and not project_folder:
                                # No project folder specified: optional global fallback (rare)
                                print("  -- No match found in bucket prefix and no project_folder specified; attempting global search --")
                                full_resp = s3_client.list_objects_v2(Bucket=course_bucket, Prefix="")
                                if 'Contents' in full_resp and full_resp['Contents']:
                                    for obj in full_resp['Contents']:
                                        key = obj['Key']
                                        # Only consider markdown lesson files
                                        if '/lessons/' not in key or not key.endswith('.md'):
                                            continue
                                        filename = key.split('/')[-1]
                                        m = re.match(r'^(?P<mod>\d{2})-(?P<les>\d{2})-(?P<rest>.+)\.md$', filename)
                                        if not m:
                                            continue
                                        try:
                                            mod_num = int(m.group('mod'))
                                            les_num = int(m.group('les'))
                                        except Exception:
                                            continue
                                        if mod_num == module_number and les_num == lesson_number:
                                            try:
                                                s3_response = s3_client.get_object(Bucket=course_bucket, Key=key)
                                                lesson_content = s3_response['Body'].read().decode('utf-8')
                                                content_file = key
                                                found = True
                                                break
                                            except Exception as e:
                                                print(f"  -- Error getting S3 object {key}: {e} --")
                    except Exception as e:
                        print(f"  -- Error reading from S3: {e} --")
                
                if not lesson_content:
                    print(f"  -- Content not found for lesson {lesson_number} in either local or S3 --")
                    continue

                # Extract project folder from the content file path for S3 organization
                if content_file and '/' in content_file:
                    # Extract project folder from S3 key (e.g., "250905-kubernetes-for-devops-engineers-01" from the key)
                    parts = content_file.split('/')
                    if len(parts) >= 2:
                        project_folder = parts[0]  # First part is the project folder

                # Extract visual tags
                descriptions = visual_tag_regex.findall(lesson_content)

                if not descriptions:
                    print(f"  -- No visual tags found in lesson {lesson_number} --")
                    continue

                print(f"  -- Found {len(descriptions)} visual tags --")

                # Prepare visual plans for classification
                visual_plans_to_classify = []
                for idx, desc in enumerate(descriptions, start=1):
                    visual_plans_to_classify.append({
                        "id": idx,
                        "description": desc,
                        "filename": create_unique_filename(desc),
                        "module": module_number,
                        "lesson": lesson_number
                    })

                # Create classification task
                classification_task = Task(
                    description=f"""For each object in the following list, add a 'type' key. The value should be 'artistic_image' or 'diagram' based on the 'description'.

    JSON List:
    {json.dumps(visual_plans_to_classify, indent=2)}

    Classify each visual description as either:
    - "diagram": for flowcharts, layered models, sequences, technical diagrams
    - "artistic_image": for scenes, metaphors, concepts, illustrations""",
                    expected_output="A single, clean JSON object with a key 'visuals', containing the original list of objects, now with the 'type' key added to each one.",
                    agent=visual_classifier
                )

                # Execute classification
                classification_crew = Crew(
                    agents=[visual_classifier],
                    tasks=[classification_task],
                    process=Process.sequential,
                    verbose=False
                )

                result = execute_crew_with_rate_limiting(classification_crew)
                result_json_string = str(result)

                try:
                    # Clean and parse the result
                    cleaned_json_string = re.sub(r'^```json\s*|\s*```$', '', result_json_string.strip(), flags=re.MULTILINE)
                    classification_result = json.loads(cleaned_json_string)

                    # Generate individual prompt files
                    prompt_number = 1
                    for visual in classification_result.get('visuals', []):
                        # Create prompt structure
                        prompt_data = {
                            "id": f"{module_number:02d}-{lesson_number:02d}-{prompt_number:04d}",
                            "module": module_number,
                            "lesson": lesson_number,
                            "prompt_number": prompt_number,
                            "visual_type": visual.get('type', 'diagram'),
                            "description": visual.get('description', ''),
                            "filename": visual.get('filename', ''),
                            "lesson_title": lesson_title,
                            "module_title": module_title,
                            "generated_at": datetime.now().isoformat(),
                            "model_provider": model_provider,
                            "request_id": request_id
                        }

                        # Create filename with short name
                        short_name = visual.get('description', '')[:30].replace(' ', '_').replace(':', '').replace('[', '').replace(']', '').lower()
                        if not short_name:
                            short_name = f"visual_{prompt_number}"

                        filename = f"{module_number:02d}-{lesson_number:02d}-{prompt_number:04d}-{short_name}.json"
                    
                        # Save to S3 in the prompts folder
                        if project_folder and s3_client and course_bucket:
                            s3_key = f"{project_folder}/prompts/{filename}"
                            s3_client.put_object(
                                Bucket=course_bucket,
                                Key=s3_key,
                                Body=json.dumps(prompt_data, indent=2),
                                ContentType='application/json'
                            )
                            filepath = f"s3://{course_bucket}/{s3_key}"
                            print(f"    -- Saved prompt to S3: {s3_key} --")
                        else:
                            # Fallback to local saving
                            filepath = os.path.join(prompts_dir, filename)
                            with open(filepath, 'w', encoding='utf-8') as f:
                                json.dump(prompt_data, f, indent=2)
                            print(f"    -- Saved prompt locally: {filename} --")

                        generated_prompts.append({
                            "id": prompt_data["id"],
                            "filename": filename,
                            "filepath": filepath,
                            "visual_type": prompt_data["visual_type"],
                            "description": prompt_data["description"]
                        })
                        prompt_number += 1

                except Exception as e:
                    print(f"  -- FAILED to process visual plan for lesson {lesson_number}. Error: {e} --")
                    continue

        # Return success response
        response = {
            "statusCode": 200,
            "message": f"Successfully generated {len(generated_prompts)} visual prompts",
            "request_id": request_id,
            "module_processed": module_to_generate,
            "content_source": content_source,
            "generated_prompts": generated_prompts,
            "bucket": course_bucket if s3_client else None,
            "project_folder": project_folder,
            "prompts_s3_prefix": f"{project_folder}/prompts/" if project_folder else None,
            "statistics": {
                "total_prompts": len(generated_prompts),
                "prompts_directory": prompts_dir,
                "saved_to_s3": bool(project_folder and s3_client and course_bucket)
            }
        }

        print("--- Visual Planning Complete ---")
        print(f"Generated prompts: {len(generated_prompts)}")

        return response

    except Exception as e:
        error_msg = f"Error in visual planning: {str(e)}"
        print(f"ERROR: {error_msg}")
        request_id = context.get('aws_request_id') if isinstance(context, dict) else getattr(context, 'aws_request_id', 'unknown')
        return {
            "statusCode": 500,
            "error": error_msg,
            "request_id": request_id
        }


def get_secret(secret_name, region_name="us-east-1"):
    """Retrieve a secret from AWS Secrets Manager."""
    import boto3
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


if __name__ == '__main__':
    # CLI entrypoint for testing
    print("Visual Planner Lambda Function")
    print("Use SAM CLI to test: sam local invoke VisualPlanner -e test-event.json")
