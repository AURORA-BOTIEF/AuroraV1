#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- CRITICAL: ABSOLUTE FIRST THING - FILESYSTEM WORKAROUND ---
# This MUST be the very first code executed before ANY other imports

import os
import sys
import json
import re
import yaml
try:
    import boto3
except Exception:
    boto3 = None
import time
import random
import uuid
from datetime import datetime

# Override the home directory immediately
original_home = os.environ.get('HOME', '/tmp')
os.environ['HOME'] = '/tmp'

# Set all possible environment variables that might cause filesystem writes
os.environ['CREWAI_STORAGE_DIR'] = '/tmp/.crewai'
os.environ['CREW_CACHE_DIR'] = '/tmp/.crewai_cache'
os.environ['TRANSFORMERS_CACHE'] = '/tmp/.transformers'
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        return None
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

"""
Delay importing heavy CrewAI and langchain-related packages until runtime.
This reduces Lambda init time and avoids doing large imports during container startup.
The original top-level monkey-patch logic is preserved but executed lazily.
"""

# Placeholders for heavy dependencies; will be populated by _lazy_load_heavy_dependencies()
Agent = None
Task = None
Crew = None
Process = None
LLM = None
BaseTool = None
DuckDuckGoSearchRun = None

# If heavy libs are not available at module import time, provide a minimal BaseTool fallback
# so classes that subclass BaseTool can be defined without raising TypeError during import.
if BaseTool is None:
    class _BaseToolFallback:
        """Minimal fallback for BaseTool used during import-time when langchain/crewai
        are not installed. This class is intentionally simple and will raise if the
        tool is actually executed at runtime without the heavy deps loaded.
        """

        name: str = "BaseToolFallback"
        description: str = "Fallback BaseTool used until real BaseTool is loaded"

        def __init__(self, *args, **kwargs):
            # No-op initializer
            pass

        def _run(self, *args, **kwargs):
            raise RuntimeError("BaseTool is not available in this environment. Call _lazy_load_heavy_dependencies() first.")

    BaseTool = _BaseToolFallback

# --- COMPREHENSIVE MONKEY-PATCH FOR AWS LAMBDA ---
def _lazy_load_heavy_dependencies():
    """Import heavy CrewAI/langchain dependencies and apply necessary monkey patches.

    This function is safe to call multiple times; it will no-op if imports already loaded.
    """
    global Agent, Task, Crew, Process, LLM, BaseTool, DuckDuckGoSearchRun

    if Agent is not None:
        return

    try:
        # Import heavy libraries at runtime
        from crewai import Agent as _Agent, Task as _Task, Crew as _Crew, Process as _Process, LLM as _LLM
        from crewai.tools import BaseTool as _BaseTool
        try:
            from langchain_community.tools import DuckDuckGoSearchRun as _Duck
        except Exception:
            _Duck = None

        Agent, Task, Crew, Process, LLM, BaseTool, DuckDuckGoSearchRun = _Agent, _Task, _Crew, _Process, _LLM, _BaseTool, _Duck

    except Exception as e:
        # Re-raise as ImportError-like to be handled by caller
        print(f"Warning: failed to import heavy dependencies: {e}")
        raise

    # Apply monkey patches after imports are available
    try:
        import crewai.utilities.paths as _paths

        def patched_db_storage_path():
            return "/tmp/.crewai"

        _paths.db_storage_path = patched_db_storage_path
    except Exception:
        pass

    try:
        from crewai.memory.storage import kickoff_task_outputs_storage as _kickoff

        class NoOpStorage:
            """A dummy storage class that does nothing."""

            def save(self, *args, **kwargs):
                pass

            def load(self, *args, **kwargs):
                return None

            def reset(self, *args, **kwargs):
                pass

        _kickoff.KickoffTaskOutputsSQLiteStorage = NoOpStorage
    except Exception:
        pass

    try:
        import crewai.rag.chromadb.constants as _chromac
        _chromac.DEFAULT_STORAGE_PATH = "/tmp/.chromadb"
    except Exception:
        pass

    try:
        # If CrewAI tries to access user home directory, redirect to /tmp
        import os.path as _op

        def safe_expanduser(path):
            if path.startswith('~'):
                return path.replace('~', '/tmp')
            return path

        # Monkey patch os.path.expanduser for this module only
        _op.expanduser = safe_expanduser
    except Exception:
        pass

# --- Rate Limiting Utilities ---
class RateLimiter:
    """Smart rate limiter to handle Bedrock API limits with proactive delays."""
    
    def __init__(self, base_delay=5.0, max_delay=90.0, exponential_base=2.0, proactive_delay=4.0):
        self.base_delay = base_delay  # Increased for Lambda environment
        self.max_delay = max_delay    # Increased for Lambda environment  
        self.exponential_base = exponential_base
        self.consecutive_errors = 0
        self.last_request_time = 0
        self.proactive_delay = proactive_delay  # Increased to 4 seconds for Lambda
        self.request_times = []
    
    def wait_if_needed(self):
        """Wait based on current rate limiting state with proactive delays."""
        current_time = time.time()
        
        # PROACTIVE DELAY: Always wait minimum time between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.proactive_delay:
            wait_time = self.proactive_delay - time_since_last
            print(f"Proactive rate limiting: waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
        
        # REACTIVE DELAY: Additional delay if we have consecutive errors
        if self.consecutive_errors > 0:
            delay = min(
                self.base_delay * (self.exponential_base ** self.consecutive_errors),
                self.max_delay
            )
            # Add some jitter to avoid thundering herd
            delay += random.uniform(0, delay * 0.1)
            print(f"Error recovery delay: {delay:.1f} seconds (errors: {self.consecutive_errors})")
            time.sleep(delay)
        
        # RATE LIMIT PREVENTION: Check request frequency
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < 60]  # Keep last minute
        
        if len(self.request_times) >= 15:  # Conservative limit: 15 requests per minute
            extra_delay = 60 - (now - min(self.request_times))
            if extra_delay > 0:
                print(f"Rate limit prevention: waiting {extra_delay:.1f} seconds")
                time.sleep(extra_delay)
        
        self.request_times.append(now)
        self.last_request_time = time.time()
    
    def record_success(self):
        """Record a successful API call."""
        self.consecutive_errors = 0
    
    def record_error(self, is_rate_limit=True):
        """Record an API error."""
        if is_rate_limit:
            self.consecutive_errors += 1
            print(f"Rate limit hit. Consecutive errors: {self.consecutive_errors}")
        return self.consecutive_errors < 15  # Increased tolerance from 5 to 15

class RateLimitedLLM:
    """Wrapper around LLM that enforces rate limiting for Lambda environment."""
    
    def __init__(self, llm, rate_limiter):
        self.llm = llm
        self.rate_limiter = rate_limiter
        
    def __getattr__(self, name):
        """Delegate all attribute access to the wrapped LLM."""
        return getattr(self.llm, name)
    
    def call(self, messages, **kwargs):
        """Rate-limited LLM call with automatic retry logic."""
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting before each call
                self.rate_limiter.wait_if_needed()
                
                # Make the actual LLM call
                result = self.llm.call(messages, **kwargs)
                
                # Record success and return result
                self.rate_limiter.record_success()
                return result
                
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = "rate limit" in error_msg or "too many requests" in error_msg
                
                if self.rate_limiter.record_error(is_rate_limit):
                    print(f"Rate limit error on attempt {attempt + 1}: {e}")
                    continue
                else:
                    print(f"Too many consecutive rate limit errors. Aborting after {max_retries} attempts.")
                    raise e
                    
        raise Exception(f"Failed after {max_retries} attempts due to rate limiting")

# Global rate limiter instance
rate_limiter = RateLimiter()

# --- Custom Tools ---
def create_search_tool():
    """Factory that returns a BaseTool-compatible search tool instance.

    This ensures the returned instance is an instance of the real CrewAI
    `BaseTool` class after heavy dependencies are lazy-loaded. If the heavy
    dependencies are not available, a fallback tool instance is returned that
    raises at runtime when invoked.
    """
    # Ensure heavy deps are loaded if possible
    try:
        _lazy_load_heavy_dependencies()
    except Exception:
        # If lazy load fails, fall through to fallback behavior
        pass

    try:
        # Dynamically create a subclass of the currently-available BaseTool
        class _SearchTool(BaseTool):
            name: str = "DuckDuckGo Search"
            description: str = "A tool that can be used to search the web with DuckDuckGo."

            def _run(self, search_query: str) -> str:
                if DuckDuckGoSearchRun is None:
                    raise RuntimeError("DuckDuckGoSearchRun tool not available")
                return DuckDuckGoSearchRun().run(search_query)

        return _SearchTool()
    except Exception:
        # Fallback: return an instance of whatever BaseTool is (likely the fallback)
        class _FallbackTool(BaseTool):
            def _run(self, *args, **kwargs):
                raise RuntimeError("Search tool unavailable in this environment")

        return _FallbackTool()

# --- Agents ---
def create_agents(llm, course_duration_hours=40, performance_mode='balanced'):
    search_tool = create_search_tool()
    
    # Calculate target content depth based on course duration
    if course_duration_hours <= 20:
        content_depth = "intermediate"
        target_words = 2000
        detail_level = "detailed"
    elif course_duration_hours <= 40:
        content_depth = "advanced"
        target_words = 3000
        detail_level = "comprehensive"
    else:
        content_depth = "expert"
        target_words = 4000
        detail_level = "exhaustive"
    
    # PERFORMANCE OPTIMIZATION: Choose agent strategy based on performance mode
    if performance_mode == 'fast':
        # Single streamlined agent for maximum speed
        agents = create_streamlined_agents(llm, content_depth, target_words, search_tool)
        return agents, target_words
    else:
        # Traditional 3-agent approach for quality
        agents = create_traditional_agents(llm, content_depth, target_words, detail_level, search_tool, course_duration_hours)
        return agents, target_words

def create_streamlined_agents(llm, content_depth, target_words, search_tool):
    """Optimized single-agent approach for speed."""
    
    content_generator = Agent(
        role='Expert Content Generator and Researcher',
        goal=f'Research and write comprehensive, university-level lessons in a single efficient step, targeting {target_words}+ words per lesson. Include theoretical foundations, practical applications, real-world examples, troubleshooting scenarios, and hands-on exercises. CRITICAL: Strategically insert multiple visual placeholder tags [VISUAL: description] throughout the content to support the visual planning pipeline.',
        backstory=f"""You are an expert technical author and researcher with expertise in creating {content_depth}-level educational content efficiently. You combine research and writing capabilities to generate comprehensive lessons in a streamlined process. 
        
        EFFICIENCY EXPERTISE: You work quickly without sacrificing quality, conducting focused research and immediately incorporating findings into well-structured content. You understand the importance of speed in content generation while maintaining educational value.
        
        VISUAL INTEGRATION EXPERTISE: You excel at identifying optimal placement for visual aids and consistently embed [VISUAL: description] tags throughout your content. You understand that these tags are essential for the downstream visual planning pipeline that will generate appropriate diagrams, flowcharts, and educational images. You include 3-5 visual tags per major section, ensuring comprehensive visual support for learning.""",
        verbose=True,
        allow_delegation=False,
        tools=[search_tool],
        llm=llm
    )
    
    return [content_generator]

def create_traditional_agents(llm, content_depth, target_words, detail_level, search_tool, course_duration_hours=40):
    """Traditional 3-agent approach for maximum quality."""
    
    lesson_planner = Agent(
        role='Master Curriculum Designer',
        goal=f'For a given lesson topic, create an exhaustive, multi-level bulleted plan for a {course_duration_hours}-hour course. This plan must break down every concept into its fundamental sub-topics, advanced concepts, practical applications, and assessment points.',
        backstory=f"""You are a world-class curriculum designer with 20+ years of experience creating {content_depth} professional training programs. You excel at designing {course_duration_hours}-hour courses that provide {detail_level} coverage of technical topics. You understand that longer courses require deeper theoretical foundations, more practical exercises, and comprehensive assessment strategies.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )

    content_researcher = Agent(
        role='Senior Technical Research Specialist',
        goal=f'For a given list of technical topics, perform comprehensive web searches to gather detailed information, technical specifications, best practices, real-world examples, and industry insights. Synthesize this into rich, {content_depth}-level research notes suitable for a {course_duration_hours}-hour course.',
        backstory=f"""You are a master researcher with deep expertise in technical documentation and industry best practices. You dive deep to find the most accurate, current, and comprehensive information for {content_depth}-level training programs. You understand that {course_duration_hours}-hour courses require extensive supporting material, case studies, and practical examples.""",
        verbose=True,
        allow_delegation=False,
        tools=[search_tool],
        llm=llm
    )

    lesson_writer = Agent(
        role='Expert Technical Author and Instructional Designer',
        goal=f'Write comprehensive, university-level lessons based on research notes, targeting {target_words}+ words per lesson for a {course_duration_hours}-hour course. Include theoretical foundations, practical applications, real-world examples, troubleshooting scenarios, and hands-on exercises. CRITICAL: Strategically insert multiple visual placeholder tags [VISUAL: description] throughout the content to support the visual planning pipeline.',
        backstory=f"""You are an expert technical author and instructional designer with expertise in creating {content_depth}-level educational content. You write engaging, detailed content that balances theoretical depth with practical application. For {course_duration_hours}-hour courses, you ensure each lesson provides thorough coverage including:
        - Theoretical foundations and principles
        - Step-by-step practical procedures
        - Real-world case studies and examples
        - Common troubleshooting scenarios
        - Best practices and industry standards
        - Hands-on exercises and labs
        - Assessment checkpoints
        
        VISUAL INTEGRATION EXPERTISE: You excel at identifying optimal placement for visual aids and consistently embed [VISUAL: description] tags throughout your content. You understand that these tags are essential for the downstream visual planning pipeline that will generate appropriate diagrams, flowcharts, and educational images. You include 3-5 visual tags per major section, ensuring comprehensive visual support for learning.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    return [lesson_planner, content_researcher, lesson_writer]

def execute_crew_with_rate_limiting(crew, max_retries=3):
    """Execute a crew with automatic rate limiting and retry logic."""
    global rate_limiter
    
    for attempt in range(max_retries):
        try:
            print(f"Executing crew (attempt {attempt + 1}/{max_retries})...")
            rate_limiter.wait_if_needed()
            
            result = crew.kickoff()
            rate_limiter.record_success()
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = 'rate limit' in error_str or 'too many requests' in error_str
            
            if is_rate_limit:
                print(f"Rate limit error on attempt {attempt + 1}: {e}")
                if rate_limiter.record_error(is_rate_limit=True):
                    if attempt < max_retries - 1:
                        delay = rate_limiter.base_delay * (2 ** attempt) + random.uniform(5, 15)
                        print(f"Waiting {delay:.1f} seconds before retry...")
                        time.sleep(delay)
                        continue
                else:
                    raise Exception("Too many consecutive rate limit errors. Giving up.")
            else:
                print(f"Non-rate-limit error: {e}")
                rate_limiter.record_error(is_rate_limit=False)
                raise e
    
    raise Exception(f"Failed to execute crew after {max_retries} attempts")

# --- Utility Functions ---
def sanitize_filename(name):
    """Sanitizes a string to be used as a valid filename."""
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")

def generate_project_folder_name(course_topic: str, s3_client, bucket_name: str) -> str:
    """Generate a structured project folder name: YYMMDD-<course_title>-XY"""
    # Get current date in YYMMDD format
    date_str = datetime.now().strftime("%y%m%d")
    
    # Sanitize course topic for folder name
    sanitized_topic = sanitize_filename(course_topic).lower().replace("_", "-")
    
    # Find existing projects for today to determine next ID
    prefix = f"{date_str}-{sanitized_topic}-"
    
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix,
            Delimiter='/'
        )
        
        existing_ids = []
        if 'CommonPrefixes' in response:
            for obj in response['CommonPrefixes']:
                folder_name = obj['Prefix'].rstrip('/')
                # Extract the XY suffix
                if folder_name.startswith(prefix):
                    try:
                        suffix = folder_name[len(prefix):]
                        if suffix.isdigit() and len(suffix) == 2:
                            existing_ids.append(int(suffix))
                    except:
                        continue
        
        # Determine next available ID
        next_id = 1
        if existing_ids:
            next_id = max(existing_ids) + 1
        
        # Format as two digits
        id_suffix = f"{next_id:02d}"
        
        return f"{prefix}{id_suffix}"
        
    except Exception as e:
        print(f"Warning: Could not check existing projects, using default: {e}")
        # Fallback to timestamp-based suffix
        fallback_suffix = f"{int(time.time()) % 100:02d}"
        return f"{prefix}{fallback_suffix}"

def format_lesson_filename(module_number: int, lesson_index: int, lesson_title: str, model_provider: str = "bedrock") -> str:
    """Format lesson filename as AA-BB-<lesson_title>-<model>.md"""
    module_str = f"{module_number:02d}"
    lesson_str = f"{lesson_index + 1:02d}"  # lesson_index is 0-based, but we want 1-based numbering
    sanitized_title = sanitize_filename(lesson_title)
    model_suffix = "bedrock" if model_provider.lower() in ["bedrock", "claude"] else "openai"
    return f"{module_str}-{lesson_str}-{sanitized_title}-{model_suffix}.md"

def parse_markdown_to_json_structure(markdown_text):
    """Parses a markdown course outline and converts it into a JSON-like Python dictionary structure."""
    modules = []
    current_module = None
    parsing_lessons = False
    parsing_objectives = False

    module_header_regex = re.compile(r"^\s*##\s*Module\s+(\d+)[:\-\s]+(.*)", re.IGNORECASE)
    any_subheader_regex = re.compile(r"^\s*###\s+(.*)", re.IGNORECASE)
    lesson_item_regex = re.compile(r"^\s*\d+\.\s+(.*)")
    objective_item_regex = re.compile(r"^\s*-\s+(.*)")

    for line in markdown_text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue

        module_match = module_header_regex.match(line_stripped)
        if module_match:
            if current_module:
                modules.append(current_module)
            
            module_number = module_match.group(1)
            module_title = module_match.group(2).strip()
            current_module = {
                "module_title": f"Module {module_number}: {module_title}",
                "learning_objectives": [],
                "lessons": []
            }
            parsing_lessons = False
            parsing_objectives = False
            continue

        if current_module:
            subheader_match = any_subheader_regex.match(line_stripped)
            if subheader_match:
                header_text = subheader_match.group(1).lower()
                parsing_lessons = 'lessons' in header_text
                parsing_objectives = 'objectives' in header_text
                continue

            # For our outline format, bullet points under modules are lessons
            if line_stripped.startswith('-') and not line_stripped.lower().startswith('- **'):
                lesson_text = line_stripped[1:].strip()
                if lesson_text and not lesson_text.lower().startswith('**'):
                    current_module['lessons'].append(lesson_text)
            
            # Also check for numbered lessons
            lesson_match = lesson_item_regex.match(line_stripped)
            if lesson_match:
                current_module['lessons'].append(lesson_match.group(1).strip())
            
            # Check for objectives
            if parsing_objectives:
                objective_match = objective_item_regex.match(line_stripped)
                if objective_match:
                    current_module['learning_objectives'].append(objective_match.group(1).strip())

    if current_module:
        modules.append(current_module)

    return {"modules": modules}

def get_course_outline_from_s3(s3_client, bucket_name: str, outline_s3_key: str = None) -> str:
    """Download the most recent course outline from S3, or a specific outline if outline_s3_key is provided."""
    try:
        if outline_s3_key:
            # Use the specific outline key provided
            print(f"--- Using specific outline file: {outline_s3_key} ---")
            response = s3_client.get_object(Bucket=bucket_name, Key=outline_s3_key)
            return response['Body'].read().decode('utf-8')
        else:
            # Fallback to searching for the most recent file in outlines/ prefix
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix='outlines/'
            )
            
            if 'Contents' not in response:
                raise Exception("No outline files found in S3 bucket")
            
            # Get the most recent file
            outline_files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
            latest_outline_key = outline_files[0]['Key']
            
            print(f"--- Using outline file: {latest_outline_key} ---")
            
            # Download the file
            response = s3_client.get_object(Bucket=bucket_name, Key=latest_outline_key)
            return response['Body'].read().decode('utf-8')
        
    except Exception as e:
        raise Exception(f"Failed to get course outline from S3: {str(e)}")


def load_course_outline_from_yaml(path: str):
    """Load the structured YAML outline and convert to the simple modules/lessons list used by the generator."""
    p = os.path.abspath(path)
    if not os.path.exists(p):
        raise FileNotFoundError(p)

    with open(p, 'r', encoding='utf-8') as fh:
        doc = yaml.safe_load(fh)

    # Extract course-level metadata
    course_info = doc.get('course', {})
    course_metadata = {
        'title': course_info.get('title', 'Kubernetes Course'),
        'description': course_info.get('description', ''),
        'language': course_info.get('language', 'en'),
        'level': course_info.get('level', 'intermediate'),
        'audience': course_info.get('audience', []),
        'prerequisites': course_info.get('prerequisites', []),
        'total_duration_minutes': course_info.get('total_duration_minutes', 1200),
        'learning_outcomes': course_info.get('learning_outcomes', [])
    }

    # Support both top-level 'modules' and 'course' -> 'modules'
    modules_src = doc.get('modules')
    if not modules_src:
        modules_src = course_info.get('modules', [])

    parsed = []
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

        parsed.append({
            'module_info': module_info,
            'lessons': lessons
        })

    return {
        'course_metadata': course_metadata,
        'modules': parsed
    }

def upload_lesson_to_s3(s3_client, bucket_name: str, lesson_content: str, module_number: int, lesson_index: int, lesson_title: str, project_folder: str, model_provider: str = "bedrock") -> str:
    """Upload a lesson file to S3 with structured folder organization."""
    try:
        # Create the structured filename
        lesson_filename = format_lesson_filename(module_number, lesson_index, lesson_title, model_provider)
        
        # Create the S3 key with project folder structure
        s3_key = f"{project_folder}/lessons/{lesson_filename}"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=lesson_content.encode('utf-8'),
            ContentType='text/markdown'
        )
        
        return s3_key
        
    except Exception as e:
        raise Exception(f"Failed to upload lesson to S3: {str(e)}")


def save_local_lesson(module_number: int, lesson_index: int, lesson_title: str, content: str, project_folder: str = None, model_provider: str = "bedrock") -> str:
    """Save lesson markdown to local out directory with structured organization."""
    # Decide where to write files:
    # - Prefer /var/task when it exists and is writable (this is the case for SAM local invoke
    #   because SAM mounts the project into /var/task).
    # - If /var/task exists but is NOT writable (deployed Lambda images are typically read-only),
    #   fall back to /tmp which is writable in Lambda.
    # - Otherwise (regular local runs), use the current working directory.
    if os.path.exists('/var/task') and os.access('/var/task', os.W_OK):
        base_dir = '/var/task'
    elif os.path.exists('/var/task') and not os.access('/var/task', os.W_OK):
        # Running inside a deployed Lambda image where /var/task is read-only
        base_dir = '/tmp'
    else:
        base_dir = os.getcwd()
    
    if project_folder:
        # Use the same structure as S3
        out_base = os.path.join(base_dir, 'out', project_folder, 'lessons')
    else:
        # Fallback to old structure for local-only mode
        out_base = os.path.join(base_dir, 'out', 'lessons', 'local')
    
    # Create the structured filename
    lesson_filename = format_lesson_filename(module_number, lesson_index, lesson_title, model_provider)
    
    os.makedirs(out_base, exist_ok=True)
    dest_path = os.path.join(out_base, lesson_filename)
    
    with open(dest_path, 'w', encoding='utf-8') as fh:
        fh.write(content)
    return dest_path

# --- Main Lambda Handler ---
def lambda_handler(event, context):
    """
    Lambda handler for generating module content.
    
    Expected event format:
    {
        "course_bucket": "bucket-name",
        "module_to_generate": 1,  # Optional, defaults to 1. Use 0 for all modules
        "course_topic": "Advanced Python Programming",  # Optional, will try to get from outline
        "course_duration_hours": 40,  # Optional, defaults to 40 hours. Affects content depth
        "max_lessons_per_execution": 3  # Optional, defaults to 3 to avoid timeouts
    }
    """
    try:
        print(f"--- Starting Module Content Generation Lambda ---")
        print(f"Event: {json.dumps(event, indent=2)}")
        
        # --- DEBUG: Print environment variables FIRST to diagnose SAM env-vars issue ---
        print(f"--- DEBUG: Environment Variables ---")
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
        print(f"--- END DEBUG ---")
        
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
            
            # Use GPT-5 model (now available as of August 2025)
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
            
            # Note: Bedrock uses IAM authentication, so API key is not required
            # We keep the check for backward compatibility but don't fail if not found
            
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
        
        # Lazy-load heavy dependencies (CrewAI, langchain, etc.) to reduce cold-start time
            try:
                _lazy_load_heavy_dependencies()
            except Exception as e:
                # If heavy deps are not available (local dry-run), continue but fail later if used
                print(f"Warning: heavy dependencies failed to load: {e}")

        # --- Initialize Global Rate Limiter for Lambda Environment ---
        # Use more aggressive (smaller) delays to speed up single-lesson Lambda runs.
        # This is safe because we force a single-agent, single-lesson execution, so
        # the number of LLM calls will be limited.
        rate_limiter = RateLimiter(
            base_delay=1.0,      # shorter base delay to reduce idle time
            max_delay=30.0,      # smaller max delay for retries
            exponential_base=2.0,
            proactive_delay=1.0   # minimum 1 second between API calls
        )

        # Create base LLM and wrap it with rate limiting. If LLM class isn't available
        # (for local dry-run), leave llm as None and only use it when heavy deps are present.
        try:
            base_llm = LLM(model=model_arn)
            llm = RateLimitedLLM(base_llm, rate_limiter)
        except Exception as e:
            print(f"Warning: could not initialize LLM: {e}")
            llm = None

    # Agents and target_words will be created after configuration is read

        # Get configuration from event (course_bucket resolved later if S3 enabled)
        course_bucket = None
        module_to_generate = event.get('module_to_generate', 1)
        course_topic = event.get('course_topic', 'Technical Course')
        course_duration_hours = event.get('course_duration_hours', 40)
        # Enforce single-lesson per Lambda execution to fit reliably within Lambda timeouts.
        # Even if the caller asks for more, we override here to keep executions short.
        max_lessons_per_execution = 1
        request_id = getattr(context, 'aws_request_id', 'unknown') if context else 'unknown'

        # Force single-agent (streamlined) mode in Lambda to reduce API calls and runtime
        performance_mode = 'fast'

        print(f"--- Configuration ---")
        print(f"Bucket: {course_bucket}")
        print(f"Module to generate: {module_to_generate}")
        print(f"Course topic: {course_topic}")
        print(f"Course duration: {course_duration_hours} hours")
        print(f"Max lessons per execution: {max_lessons_per_execution}")
        print(f"Performance mode: {performance_mode}")
        print(f"Request ID: {request_id}")

        # Initialize S3 client (optional)
        s3_client = None
        if os.getenv('USE_S3_OUTLINES', 'false').lower() in ('1', 'true', 'yes') or event.get('use_s3') or event.get('content_source') == 's3':
            s3_client = boto3.client('s3', region_name=region)

        # Prefer local YAML outline when present - check multiple paths
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

        if local_yaml_path:
            print(f"--- Loading course outline from local YAML: {local_yaml_path} ---")
            outline_data = load_course_outline_from_yaml(local_yaml_path)
            course_metadata = outline_data['course_metadata']
            parsed_modules = outline_data['modules']

            # Update course_topic from outline if not provided
            if not course_topic:
                course_topic = course_metadata['title']
        else:
            if not s3_client:
                raise Exception("No local outline.yaml found and S3 outlines not enabled (set USE_S3_OUTLINES or event['use_s3']=True)")

            # Resolve course_bucket for S3 use
            course_bucket = event.get('course_bucket') or os.environ.get('OUTPUT_S3_BUCKET')
            if not course_bucket:
                raise ValueError("course_bucket must be provided in event or OUTPUT_S3_BUCKET environment variable when S3 is enabled")

            # Get course outline from S3
            print(f"--- Retrieving course outline from S3 ---")
            outline_s3_key = event.get('outline_s3_key')
            outline_content = get_course_outline_from_s3(s3_client, course_bucket, outline_s3_key)
            # Parse the YAML outline
            print(f"--- Parsing course outline ---")
            course_data = yaml.safe_load(outline_content)

            # Support both top-level 'modules' and 'course' -> 'modules'
            course_info = course_data.get('course', {})
            course_metadata = {
                'title': course_info.get('title', 'Kubernetes Course'),
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

            # Update course_topic from outline if not provided
            if not course_topic:
                course_topic = course_metadata['title']

        # If the caller provided a project_folder explicitly, honor it (useful for testing)
        project_folder = event.get('project_folder') or None

        # If S3 client is enabled and course_bucket not yet set, resolve from event/env
        if s3_client and not course_bucket:
            course_bucket = event.get('course_bucket') or os.environ.get('OUTPUT_S3_BUCKET')
            if not course_bucket:
                raise ValueError("course_bucket must be provided in event or OUTPUT_S3_OUTLINE environment variable when S3 is enabled")

        if s3_client:
            print(f"S3 enabled. Using bucket: {course_bucket}")
        else:
            print("S3 not enabled; outputs will be saved locally only")

        if not parsed_modules:
            raise Exception("Could not parse any modules from the outline")

        print(f"--- Found {len(parsed_modules)} modules in outline ---")

        # Generate project folder name for S3 organization if caller didn't provide one
        if not project_folder:
            project_folder = None
            if s3_client and course_bucket:
                project_folder = generate_project_folder_name(course_topic, s3_client, course_bucket)
                print(f"--- Project folder: {project_folder} ---")
        else:
            print(f"--- Using caller-provided project_folder: {project_folder} ---")

        # Create agents with LLM and course duration. We force the 'fast' path so
        # a single streamlined agent is used (minimizes API calls and runtime).
        agents, target_words = create_agents(llm, course_duration_hours, 'fast')

        # Process modules
        generated_lessons = []

        if module_to_generate == 0:
            print(f"--- Starting Content Generation for ALL modules ---")
        else:
            print(f"--- Starting Content Generation for Module {module_to_generate} ---")
        
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
            print(f"  -- Module Summary: {module_info['summary']} --")
            print(f"  -- Duration: {module_info['duration_minutes']} minutes ({module_info['percent_theory']}% theory, {module_info['percent_practice']}% practice) --")
            print(f"  -- Bloom Level: {module_info['bloom_level']} --")
            
            if not lessons:
                print(f"--- No lessons found for this module ---")
                continue

            # Minimal: if caller requested a specific lesson in this module, select it (1-based lesson_number)
            requested_lesson = event.get('lesson_to_generate')
            if requested_lesson is not None:
                try:
                    rl = int(requested_lesson)
                    # Treat 0 or negative as 'no filter' (generate all lessons)
                    if rl <= 0:
                        print(f"--- lesson_to_generate={rl} interpreted as 'all lessons' for module {module_number} ---")
                    else:
                        matched = [l for l in lessons if l.get('lesson_number') == rl]
                        if matched:
                            print(f"--- Selecting requested lesson {rl} in module {module_number} ---")
                            lessons = matched
                        else:
                            print(f"--- Requested lesson {rl} not found in module {module_number}; no lessons will be generated for this module. ---")
                            lessons = []
                except Exception:
                    print(f"--- Invalid lesson_to_generate value: {requested_lesson}; ignoring. ---")
            
            # Process each lesson (with limit to avoid timeouts)
            lessons_processed = 0
            for lesson_data in lessons:
                if lessons_processed >= max_lessons_per_execution:
                    print(f"  -- Reached maximum lessons per execution ({max_lessons_per_execution}). Stopping. --")
                    break
                
                lesson_title = lesson_data['title']
                lesson_topics = lesson_data.get('topics', [])
                lesson_labs = lesson_data.get('lab_activities', [])
                lesson_bloom = lesson_data.get('bloom_level', 'Understand')
                lesson_duration = lesson_data.get('duration_minutes', 0)
                
                # Calculate dynamic word count based on lesson duration
                # Base word count per minute: 50-75 words for comprehensive content
                base_words_per_minute = 60
                calculated_target_words = max(lesson_duration * base_words_per_minute, target_words)
                
                # Adjust for bloom level complexity
                bloom_multiplier = {
                    'Remember': 0.8,
                    'Understand': 1.0,
                    'Apply': 1.2,
                    'Analyze': 1.4,
                    'Evaluate': 1.5,
                    'Create': 1.6
                }.get(lesson_bloom, 1.0)
                
                final_target_words = int(calculated_target_words * bloom_multiplier)
                
                print(f"    -- Calculated target words: {final_target_words} (Duration: {lesson_duration}min × {base_words_per_minute}wpm × {bloom_multiplier} bloom multiplier) --")
                
                # Create tasks based on agent strategy - Force single-agent in Lambda
                if performance_mode in ['fast', 'ultra_fast'] or len(agents) == 1:
                    # Streamlined single-agent approach for Lambda efficiency
                    content_generator = agents[0]
                    
                    # Build detailed topic and lab information for the agent
                    topics_text = ""
                    if lesson_topics:
                        topics_text = "\n".join([f"- {topic['title']} (Duration: {topic['duration_minutes']} min, Bloom Level: {topic['bloom_level']})" for topic in lesson_topics])
                    
                    labs_text = ""
                    if lesson_labs:
                        labs_text = "\n".join([f"- {lab['title']} (Duration: {lab['duration_minutes']} min, Bloom Level: {lab['bloom_level']})" for lab in lesson_labs])
                    
                    single_task = Task(
                        description=f"""MANDATORY FORMATTING REQUIREMENTS - FOLLOW THESE EXACTLY:

1. EXPLICITLY DISPLAY bloom levels in EVERY section header using this format:
   "## 1. Topic Name [Bloom: Understand]"
   "## 2. Lab Activity [Bloom: Apply]"

2. MARK ANY CONTENT BEYOND THE OUTLINE AS OPTIONAL using this format:
   "## Optional: Best Practices [Bonus Content]"
   "## Optional: Troubleshooting [Bonus Content]"

3. ONLY include content from these REQUIRED sections:
   {topics_text}
   {labs_text}

Research and write a comprehensive lesson on '{lesson_title}' for module '{module_title}' in a {course_duration_hours}-hour course about '{course_topic}'. 

MODULE CONTEXT:
- Module Summary: {module_info['summary']}
- Module Duration: {module_info['duration_minutes']} minutes
- Theory/Practice Balance: {module_info['percent_theory']}% theory, {module_info['percent_practice']}% practice
- Target Bloom Level: {module_info['bloom_level']}

LESSON DETAILS:
- Lesson Duration: {lesson_duration} minutes
- Lesson Bloom Level: {lesson_bloom}
- Target Word Count: {final_target_words}+ words (calculated for {lesson_duration}min duration)

CONTENT REQUIREMENTS:
1) Cover ALL topics listed above with appropriate depth for their bloom levels
2) Include ALL lab activities as hands-on exercises with step-by-step instructions
3) Generate content that fills EXACTLY {lesson_duration} minutes of teaching time - aim for comprehensive coverage
4) Align content with {lesson_bloom} bloom taxonomy level:
   - Remember: Focus on basic facts, definitions, and recognition
   - Understand: Explain concepts, provide examples, ensure comprehension
   - Apply: Include practical exercises, real-world scenarios, hands-on application
   - Analyze: Break down complex concepts, compare/contrast, identify patterns
   - Evaluate: Include assessment, critique, judgment-based activities
   - Create: Encourage synthesis, design, original work, and innovation
5) Step-by-step procedures for each lab activity (timed for {lesson_duration} minutes total)
6) Real-world examples and troubleshooting scenarios appropriate for {lesson_bloom} level
7) Best practices aligned with course level ({course_metadata['level']})
8) Assessment checkpoints for each major topic

CRITICAL REQUIREMENT: Insert visual placeholder tags [VISUAL: description] strategically throughout the content where visual aids would enhance learning. Include tags for:
- Architecture diagrams (e.g., [VISUAL: Kubernetes control plane architecture diagram])
- Process flowcharts (e.g., [VISUAL: Authentication flow diagram])
- Conceptual illustrations (e.g., [VISUAL: Security layers pyramid diagram])
- Real-world scenarios (e.g., [VISUAL: Developer configuring security policies])
- Technical schematics (e.g., [VISUAL: Network topology with security zones])

These tags are essential for the visual planning pipeline and must be included.""",
                        expected_output=f"Complete lesson in markdown format with {final_target_words}+ words, covering ALL required topics and lab activities from the outline. Content must fill {lesson_duration} minutes of teaching time with comprehensive coverage appropriate for {lesson_bloom} bloom level. Include MULTIPLE strategically-placed visual placeholder tags [VISUAL: description]. MANDATORY: EXPLICITLY show bloom levels in section headers using [Bloom: Level] format and MARK additional content beyond outline as OPTIONAL with [Bonus Content] format. The content must align with the {lesson_bloom} bloom level and {course_metadata['level']} course level. Professional-level depth appropriate for a {course_duration_hours}-hour course.",
                        agent=content_generator
                    )
                    
                    lesson_crew = Crew(
                        agents=[content_generator],
                        tasks=[single_task],
                        process=Process.sequential,
                        verbose=False,
                        max_iter=1,  # Limit iterations to reduce API calls
                        memory=False  # Disable memory to reduce complexity
                    )
                    
                else:
                    # Traditional 3-agent approach
                    lesson_planner, content_researcher, lesson_writer = agents[0], agents[1], agents[2]
                    
                    lesson_plan_task = Task(
                        description=f"Create a comprehensive lesson plan for the topic: '{lesson_title}'. This lesson is part of the module '{module_title}' in a {course_duration_hours}-hour course about '{course_topic}'. The lesson should provide {target_words}+ words of content with theoretical depth, practical applications, and hands-on exercises appropriate for professional-level training.",
                        expected_output=f"A highly detailed, multi-level, bullet-pointed list of sections, sub-topics, practical exercises, and specific research points for the lesson. Include assessment criteria and learning objectives suitable for a {course_duration_hours}-hour professional course.",
                        agent=lesson_planner
                    )

                    research_task = Task(
                        description=f"Research each point in the lesson plan for '{lesson_title}'. Focus on current best practices, real-world implementations, troubleshooting scenarios, and industry standards. Gather comprehensive information suitable for {course_duration_hours}-hour professional training.",
                        expected_output=f"Rich and detailed research notes covering all topics in the lesson plan, including current industry practices, technical specifications, best practices, common pitfalls, and real-world examples suitable for {course_duration_hours}-hour course depth.",
                        agent=content_researcher,
                        context=[lesson_plan_task]
                    )

                    writing_task = Task(
                        description=f"""MANDATORY FORMATTING REQUIREMENTS - FOLLOW THESE EXACTLY:

1. EXPLICITLY DISPLAY bloom levels in EVERY section header using this format:
   "## 1. Topic Name [Bloom: Understand]"
   "## 2. Lab Activity [Bloom: Apply]"

2. MARK ANY CONTENT BEYOND THE OUTLINE AS OPTIONAL using this format:
   "## Optional: Best Practices [Bonus Content]"
   "## Optional: Troubleshooting [Bonus Content]"

Write a comprehensive lesson on '{lesson_title}' based on the research notes. Target {final_target_words}+ words. Include: 1) Theoretical foundations, 2) Step-by-step procedures, 3) Real-world examples, 4) Troubleshooting scenarios, 5) Best practices, 6) Hands-on exercises, 7) Assessment checkpoints. 

CRITICAL REQUIREMENT: Insert visual placeholder tags [VISUAL: description] strategically throughout the content where visual aids would enhance learning. Include tags for:
- Architecture diagrams (e.g., [VISUAL: Kubernetes control plane architecture diagram])
- Process flowcharts (e.g., [VISUAL: Authentication flow diagram])
- Conceptual illustrations (e.g., [VISUAL: Security layers pyramid diagram])
- Real-world scenarios (e.g., [VISUAL: Developer configuring security policies])
- Technical schematics (e.g., [VISUAL: Network topology with security zones])

These tags are essential for the visual planning pipeline and must be included. This is for a {course_duration_hours}-hour professional course.""",
                        expected_output=f"Complete lesson in markdown format with {final_target_words}+ words, including comprehensive coverage of theoretical and practical aspects, and MULTIPLE strategically-placed visual placeholder tags [VISUAL: description]. The content must include at least 3-5 visual tags per major section to support the visual planning pipeline. MANDATORY: EXPLICITLY show bloom levels in section headers using [Bloom: Level] format and MARK additional content beyond outline as OPTIONAL with [Bonus Content] format.",
                        agent=lesson_writer,
                        context=[research_task]
                    )

                    # Execute the lesson generation with rate limiting
                    lesson_crew = Crew(
                        agents=[lesson_planner, content_researcher, lesson_writer],
                        tasks=[lesson_plan_task, research_task, writing_task],
                        process=Process.sequential,
                        verbose=False,
                        max_iter=1,  # Limit iterations to reduce API calls
                        memory=False  # Disable memory to reduce complexity
                    )
                
                # Execute the lesson generation with rate limiting
                lesson_result = execute_crew_with_rate_limiting(lesson_crew)
                lesson_content = str(lesson_result)

                # Save lesson locally with new structure
                out_path = save_local_lesson(module_number, lesson_data['lesson_number'] - 1, lesson_title, lesson_content, project_folder, model_provider)

                s3_key = None
                if s3_client and course_bucket and project_folder:
                    try:
                        s3_key = upload_lesson_to_s3(
                            s3_client,
                            course_bucket,
                            lesson_content,
                            module_number,
                            lesson_data['lesson_number'] - 1,
                            lesson_title,
                            project_folder,
                            model_provider
                        )
                    except Exception as e:
                        print(f"  -- WARNING: failed uploading lesson to S3: {e}")

                # Create structured filename for response
                lesson_filename = format_lesson_filename(module_number, lesson_data['lesson_number'] - 1, lesson_title, model_provider)

                generated_lessons.append({
                    "module_title": module_title,
                    "lesson_title": lesson_title,
                    "lesson_filename": lesson_filename,
                    "local_path": out_path,
                    "s3_key": s3_key,
                    "word_count": len(lesson_content.split()),
                    "target_words": final_target_words,
                    "project_folder": project_folder,
                    "topics_covered": len(lesson_topics),
                    "labs_included": len(lesson_labs),
                    "lesson_bloom_level": lesson_bloom,
                    "lesson_duration_minutes": lesson_duration
                })
                
                lessons_processed += 1
                print(f"  -- Lesson '{lesson_filename}' saved locally: {out_path} (Words: {len(lesson_content.split())}) --")
        
        # Return success response
        total_words = sum(lesson.get('word_count', 0) for lesson in generated_lessons)
        avg_words = total_words / len(generated_lessons) if generated_lessons else 0
        
        # Determine a representative lesson_key (first uploaded lesson S3 key) if any
        first_lesson_key = None
        for g in generated_lessons:
            if g.get('s3_key'):
                first_lesson_key = g.get('s3_key')
                break

        response = {
            "statusCode": 200,
            "message": f"Successfully generated {len(generated_lessons)} lessons",
            "request_id": request_id,
            "module_processed": module_to_generate,
            "course_duration_hours": course_duration_hours,
            "course_topic": course_topic,
            "project_folder": project_folder,
            "generated_lessons": generated_lessons,
            "bucket": course_bucket if s3_client else None,
            # For StepFunctions wiring: expose the primary lesson S3 key (if any) and the course bucket
            "lesson_key": first_lesson_key,
            "course_bucket": course_bucket if s3_client else None,
            "content_statistics": {
                "total_words": total_words,
                "average_words_per_lesson": round(avg_words, 0),
                "target_words_per_lesson": target_words,
                "lessons_generated": len(generated_lessons)
            }
        }
        
        print(f"--- Module Content Generation Complete ---")
        print(f"Generated lessons: {len(generated_lessons)}")
        
        return response
        
    except Exception as e:
        error_msg = f"Error in module content generation: {str(e)}"
        print(f"ERROR: {error_msg}")
        request_id = getattr(context, 'aws_request_id', 'unknown') if context else 'unknown'
        return {
            "statusCode": 500,
            "error": error_msg,
            "request_id": request_id
        }


if __name__ == '__main__':
    # CLI entrypoint: support dry-run listing
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print("Usage: python content_gen.py list")
        sys.exit(0)

    cmd = args[0]
    yaml_path = os.path.join(os.getcwd(), 'outline.yaml')

    if cmd == 'list':
        try:
            outline_data = load_course_outline_from_yaml(yaml_path)
            course_metadata = outline_data['course_metadata']
            modules = outline_data['modules']
            
            print(f"Course: {course_metadata['title']}")
            print(f"Level: {course_metadata['level']}")
            print(f"Total Duration: {course_metadata['total_duration_minutes']} minutes")
            print(f"Found {len(modules)} modules in {yaml_path}")
            print()
            
            for module_data in modules:
                module_info = module_data['module_info']
                lessons = module_data['lessons']
                
                print(f"Module {module_info['module_number']}: {module_info['title']}")
                print(f"  Summary: {module_info['summary']}")
                print(f"  Duration: {module_info['duration_minutes']} min ({module_info['percent_theory']}% theory, {module_info['percent_practice']}% practice)")
                print(f"  Bloom Level: {module_info['bloom_level']}")
                print(f"  Lessons: {len(lessons)}")
                
                for lesson_data in lessons:
                    print(f"    {lesson_data['lesson_number']}. {lesson_data['title']}")
                    print(f"       Duration: {lesson_data['duration_minutes']} min, Bloom: {lesson_data['bloom_level']}")
                    
                    # Calculate expected word count for CLI display
                    base_words_per_minute = 60
                    calculated_words = lesson_data['duration_minutes'] * base_words_per_minute
                    bloom_multiplier = {
                        'Remember': 0.8,
                        'Understand': 1.0,
                        'Apply': 1.2,
                        'Analyze': 1.4,
                        'Evaluate': 1.5,
                        'Create': 1.6
                    }.get(lesson_data['bloom_level'], 1.0)
                    expected_words = int(calculated_words * bloom_multiplier)
                    
                    print(f"       Expected Words: ~{expected_words} (based on duration and bloom level)")
                    
                    if lesson_data.get('topics'):
                        print(f"       Topics: {len(lesson_data['topics'])}")
                        for topic in lesson_data['topics']:
                            print(f"         - {topic['title']} ({topic['duration_minutes']} min, {topic['bloom_level']})")
                    
                    if lesson_data.get('lab_activities'):
                        print(f"       Lab Activities: {len(lesson_data['lab_activities'])}")
                        for lab in lesson_data['lab_activities']:
                            print(f"         - {lab['title']} ({lab['duration_minutes']} min, {lab['bloom_level']})")
                
                print()
        except Exception as e:
            print(f"ERROR loading YAML outline: {e}")
            sys.exit(2)

    else:
        print("Unknown command. Use 'list' to show course structure")
        sys.exit(2)


def _dry_run_event():
    """Return a minimal event that exercises lambda_handler without calling external LLMs.
    This sets USE_S3_OUTLINES to false and points to a local small outline.yaml that's already
    in the repo for tests."""
    return {
        "module_to_generate": 0,
        "course_topic": "Test Course",
        "course_duration_hours": 1,
        "max_lessons_per_execution": 0,  # Avoid generating heavy content
        "model_provider": "openai",
        "performance_mode": "fast",
        "use_s3": False
    }


def run_dry():
    """Run a lightweight invocation of lambda_handler for local testing."""
    class Ctx:
        aws_request_id = 'local-test'

    ev = _dry_run_event()
    print('Running dry invocation...')
    res = lambda_handler(ev, Ctx())
    print('Dry run result keys:', list(res.keys()) if isinstance(res, dict) else type(res))
    return res


# --- Utility function to retrieve secrets from AWS Secrets Manager ---
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
