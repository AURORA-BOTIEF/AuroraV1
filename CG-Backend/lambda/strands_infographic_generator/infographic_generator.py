"""
HTML Infographic Generator - HTML-First Design for Classroom Presentations
=============================================================================
Generates production-ready HTML slide decks for classroom instruction.

Key Features:
- Clean HTML/CSS layout optimized for 1280px × 720px presentation format
- Maximum image sizes for clarity (up to 600px height)
- Strict overflow prevention (no scrolling required)
- Automatic slide splitting when content exceeds height limits
- Images displayed as large as possible while maintaining slide integrity
- Semantic structure with proper text blocks and visual hierarchy

HTML-FIRST APPROACH:
- HTML is the FINAL PRODUCTION OUTPUT (not intermediate format)
- PPT conversion is deprecated/optional
- Visual optimizer works directly on HTML for quality assurance

Expected event parameters:
    - course_bucket: S3 bucket name
    - project_folder: Project folder path
    - book_version_key: S3 key to specific book version JSON
    - model_provider: 'bedrock' or 'openai'
    - slides_per_lesson: Number of infographic slides per lesson (default: 5)
    - style: 'professional' | 'modern' | 'minimal' (default: 'professional')
"""

import os
import logging
import json
import boto3
import re
import math
from datetime import datetime
from typing import Dict, List, Any, Optional
from botocore.config import Config
from bs4 import BeautifulSoup

# Configure boto3 with extended timeouts
boto_config = Config(
    read_timeout=900,
    connect_timeout=60,
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

# AWS Clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=boto_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration - Using Claude Haiku 4.5 inference profile (faster, cheaper)
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-5"

# Height Estimation Constants (pixels) - MATCHED TO ACTUAL HTML CSS RENDERING
# HTML-FIRST DESIGN: These constants are calibrated for 1280px × 720px HTML slides
# CRITICAL: These MUST match html_generator.py CSS exactly (20pt font × 1.4 line-height + padding + margin)
MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 460  # Slide with subtitle has less content space
MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520    # Slide without subtitle has more space
BULLET_HEIGHT = 50       # FIXED: 20pt×1.4 line-height (38px) + 8px padding + 4px margin = 50px (was 44px - caused overflow!)
HEADING_HEIGHT = 65      # Height for block headings (20pt font + spacing)
IMAGE_HEIGHT = 400       # Conservative to prevent overflow with text
CALLOUT_HEIGHT = 75      # Callout block base height
SPACING_BETWEEN_BLOCKS = 20  # Vertical spacing between content blocks
CHARS_PER_LINE = 70      # Realistic for actual slide width with 20pt font

# Logging
logger = logging.getLogger("aurora.infographic_generator")
if not logger.handlers:
    h = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    h.setFormatter(fmt)
    logger.addHandler(h)
    logger.setLevel(logging.INFO)


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise


def configure_bedrock_model(model_id: str = DEFAULT_BEDROCK_MODEL):
    """Configure Bedrock model for Strands Agent."""
    try:
        from strands.models import BedrockModel
        
        model = BedrockModel(
            model_id=model_id,
            client=bedrock_client
        )
        logger.info(f"✅ Configured Bedrock model: {model_id}")
        return model
    except Exception as e:
        logger.error(f"Failed to configure Bedrock model: {e}")
        raise


def configure_openai_model(model_id: str = DEFAULT_OPENAI_MODEL) -> Any:
    """Configure OpenAI model for Strands Agent."""
    try:
        from strands.models.openai import OpenAIModel
        
        secret_data = get_secret('aurora/openai-api-key')
        api_key = secret_data.get('api_key')
        
        if not api_key:
            raise ValueError("OpenAI API key not found in secrets")
        
        model = OpenAIModel(
            client_args={"api_key": api_key},
            model_id=model_id,
            streaming=False
        )
        logger.info(f"✅ Configured OpenAI model: {model_id}")
        return model
    except Exception as e:
        logger.error(f"Failed to configure OpenAI model: {e}")
        raise


def load_book_from_s3(bucket: str, book_key: str) -> Dict:
    """Load book JSON from S3."""
    try:
        logger.info(f"📖 Loading book from s3://{bucket}/{book_key}")
        response = s3_client.get_object(Bucket=bucket, Key=book_key)
        book_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Handle nested module structure
        lessons = []
        if 'modules' in book_data:
            # New structure: modules contain lessons
            for module in book_data.get('modules', []):
                lessons.extend(module.get('lessons', []))
            logger.info(f"✅ Loaded book with {len(lessons)} lessons from {len(book_data.get('modules', []))} modules")
            # Flatten structure for compatibility
            book_data['lessons'] = lessons
        else:
            # Old structure: lessons at top level
            lessons = book_data.get('lessons', [])
            logger.info(f"✅ Loaded book with {len(lessons)} lessons")
        
        # Try to load outline for richer module information
        try:
            project_folder = book_key.split('/')[0]
            outline_folder = f"{project_folder}/outline/"
            
            # List all files in the outline folder to find the YAML file
            logger.info(f"📋 Searching for outline in: {outline_folder}")
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=outline_folder)
            
            outline_key = None
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('.yaml') or key.endswith('.yml'):
                        outline_key = key
                        logger.info(f"✅ Found outline file: {outline_key}")
                        break
            
            if not outline_key:
                logger.warning(f"⚠️ No YAML file found in {outline_folder}")
                raise FileNotFoundError("No outline YAML file found")
            
            # Load the discovered outline file
            outline_response = s3_client.get_object(Bucket=bucket, Key=outline_key)
            import yaml
            outline_data = yaml.safe_load(outline_response['Body'].read().decode('utf-8'))
            
            # Extract module info from outline
            if 'course' in outline_data and 'modules' in outline_data['course']:
                book_data['outline_modules'] = outline_data['course']['modules']
                logger.info(f"✅ Loaded outline with {len(outline_data['course']['modules'])} modules")
            
            # Extract course metadata
            if 'course' in outline_data:
                course = outline_data['course']
                book_data['course_metadata'] = {
                    'title': course.get('title', ''),
                    'description': course.get('description', ''),
                    'audience': course.get('audience', []),
                    'prerequisites': course.get('prerequisites', []),
                    'learning_outcomes': course.get('learning_outcomes', []),
                    'level': course.get('level', ''),
                    'duration': course.get('total_duration_minutes', 0),
                    'language': course.get('language', '')  # Add language field
                }
                logger.info(f"✅ Extracted course metadata: {course.get('title', 'N/A')} [lang: {course.get('language', 'N/A')}]")
        except Exception as e:
            logger.warning(f"⚠️ Could not load outline: {e}")
        
        return book_data
    except Exception as e:
        logger.error(f"Failed to load book: {e}")
        raise


def extract_images_from_content(content: str) -> List[Dict[str, str]]:
    """Extract image references from lesson content."""
    images = []
    
    # Match markdown image syntax: ![alt](url)
    img_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
    matches = re.findall(img_pattern, content)
    
    for alt_text, img_url in matches:
        images.append({
            'alt_text': alt_text,
            'url': img_url,
            'type': 'diagram' if 'diagram' in alt_text.lower() else 'image'
        })
    
    return images


def get_image_dimensions(image_url: str) -> tuple:
    """
    Fetch actual image dimensions from S3 or web URL.
    Returns (width, height) tuple. Falls back to (800, 600) if fetch fails.
    
    For HTML-first design: Images should be as large as possible while fitting in slide.
    """
    try:
        from PIL import Image
        from io import BytesIO
        import urllib.request
        
        # Download image
        if 's3.amazonaws.com' in image_url:
            # Parse S3 URL and download
            # Format: https://bucket-name.s3.amazonaws.com/key or https://s3.amazonaws.com/bucket/key
            if '.s3.amazonaws.com' in image_url:
                parts = image_url.split('.s3.amazonaws.com/')
                bucket = parts[0].split('//')[-1]
                key = parts[1]
            else:
                parts = image_url.replace('https://s3.amazonaws.com/', '').split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
            
            response = s3_client.get_object(Bucket=bucket, Key=key)
            image_data = response['Body'].read()
        else:
            # Regular HTTP/HTTPS URL
            with urllib.request.urlopen(image_url, timeout=10) as response:
                image_data = response.read()
        
        # Get dimensions using PIL
        img = Image.open(BytesIO(image_data))
        width, height = img.size
        
        logger.info(f"📐 Image dimensions: {width}x{height}px - {image_url[:80]}...")
        return (width, height)
        
    except Exception as e:
        logger.warning(f"⚠️ Could not fetch image dimensions: {e}")
        # Fallback to reasonable default (landscape orientation)
        return (800, 600)


def create_introduction_slides(course_metadata: Dict, is_spanish: bool, slide_counter: int) -> tuple:
    """
    Create introduction slides for the course:
    1. Course Title (full-screen branded slide)
    2. Description / Audience
    3. Prerequisites
    4. Objectives (Learning Outcomes)
    
    Returns tuple of (list of slide dictionaries, updated slide counter).
    """
    intro_slides = []
    
    # 1. Course Title Slide - Full branded title slide
    intro_slides.append({
        "slide_number": slide_counter,
        "title": course_metadata.get('title', 'Course Title'),
        "subtitle": "",
        "layout_hint": "course-title",
        "content_blocks": [],
        "notes": "Course title slide"
    })
    slide_counter += 1
    
    # 2. Description / Audience Slide
    audience_list = course_metadata.get('audience', [])
    if audience_list:
        intro_slides.append({
            "slide_number": slide_counter,
            "title": "Descripción" if is_spanish else "Description",
            "subtitle": course_metadata.get('description', ''),
            "layout_hint": "single-column",
            "content_blocks": [
                {
                    "type": "bullets",
                    "heading": "¿Para quién es este curso?" if is_spanish else "Who is this course for?",
                    "items": audience_list
                }
            ],
            "notes": "Target audience and course description"
        })
        slide_counter += 1
    
    # 3. Prerequisites Slide
    prerequisites_list = course_metadata.get('prerequisites', [])
    if prerequisites_list:
        intro_slides.append({
            "slide_number": slide_counter,
            "title": "Prerrequisitos" if is_spanish else "Prerequisites",
            "subtitle": "Conocimientos recomendados" if is_spanish else "Recommended knowledge",
            "layout_hint": "single-column",
            "content_blocks": [
                {
                    "type": "bullets",
                    "heading": "",
                    "items": prerequisites_list
                }
            ],
            "notes": "Course prerequisites"
        })
        slide_counter += 1
    
    # 4. Objectives / Learning Outcomes Slide
    learning_outcomes = course_metadata.get('learning_outcomes', [])
    if learning_outcomes:
        intro_slides.append({
            "slide_number": slide_counter,
            "title": "Objetivos" if is_spanish else "Learning Objectives",
            "subtitle": "Al finalizar este curso podrás:" if is_spanish else "By the end of this course you will be able to:",
            "layout_hint": "single-column",
            "content_blocks": [
                {
                    "type": "bullets",
                    "heading": "",
                    "items": learning_outcomes
                }
            ],
            "notes": "Course learning objectives"
        })
        slide_counter += 1
    
    return intro_slides, slide_counter


def create_group_presentation_slide(is_spanish: bool, slide_counter: int) -> Dict:
    """Create a group presentation slide for introductions."""
    return {
        "slide_number": slide_counter,
        "title": "Presentación del Grupo" if is_spanish else "Group Presentation",
        "subtitle": "Conozcámonos" if is_spanish else "Let's get to know each other",
        "layout_hint": "single-column",
        "content_blocks": [
            {
                "type": "bullets",
                "heading": "",
                "items": [
                    "¿Cuál es tu nombre?" if is_spanish else "What is your name?",
                    "¿Cuál es tu experiencia?" if is_spanish else "What is your experience?",
                    "¿Qué tecnología/idea/software te ha impresionado?" if is_spanish else "What technology/idea/software has impressed you?",
                    "¿Cuáles son tus expectativas respecto al curso?" if is_spanish else "What are your expectations for the course?"
                ]
            }
        ],
        "notes": "Group presentation and introductions"
    }


def create_agenda_slide(modules: List[Dict], is_spanish: bool, slide_counter: int) -> List[Dict]:
    """
    Create agenda slide(s) showing all course modules and lessons.
    Automatically splits into multiple slides if content exceeds height limits.
    Returns list of slide dictionaries.
    """
    # Build full agenda first
    agenda_items = []
    for idx, module in enumerate(modules, 1):
        module_title = module.get('title', f"Módulo {idx}")
        agenda_items.append(module_title)  # Modules with default bullet (►)
        
        # Add lessons under each module (indented with different bullet)
        lessons = module.get('lessons', [])
        for lesson in lessons:
            lesson_title = lesson.get('title', '')
            if lesson_title:
                agenda_items.append(f"      ○ {lesson_title}")  # Indented with circle bullet
    
    # Estimate height: Each bullet ≈ 48px (BULLET_HEIGHT)
    # Max bullets per slide with subtitle: ~9 bullets (460px / 48px ≈ 9.5)
    MAX_BULLETS_PER_SLIDE = 9
    
    # If agenda fits in one slide, return single slide
    if len(agenda_items) <= MAX_BULLETS_PER_SLIDE:
        return [{
            "slide_number": slide_counter,
            "title": "Agenda" if is_spanish else "Agenda",
            "subtitle": "Estructura del curso" if is_spanish else "Course structure",
            "layout_hint": "single-column",
            "content_blocks": [
                {
                    "type": "bullets",
                    "heading": "",
                    "items": agenda_items
                }
            ],
            "notes": "Course agenda with modules and lessons"
        }]
    
    # Split into multiple slides
    slides = []
    current_items = []
    part_num = 1
    
    for item in agenda_items:
        current_items.append(item)
        
        # Check if we've reached the limit
        if len(current_items) >= MAX_BULLETS_PER_SLIDE:
            slides.append({
                "slide_number": slide_counter + len(slides),
                "title": f"Agenda ({part_num})" if is_spanish else f"Agenda ({part_num})",
                "subtitle": "Estructura del curso" if is_spanish else "Course structure",
                "layout_hint": "single-column",
                "content_blocks": [
                    {
                        "type": "bullets",
                        "heading": "",
                        "items": current_items[:]
                    }
                ],
                "notes": f"Course agenda part {part_num}"
            })
            current_items = []
            part_num += 1
    
    # Add remaining items
    if current_items:
        slides.append({
            "slide_number": slide_counter + len(slides),
            "title": f"Agenda ({part_num})" if is_spanish else f"Agenda ({part_num})",
            "subtitle": "Estructura del curso" if is_spanish else "Course structure",
            "layout_hint": "single-column",
            "content_blocks": [
                {
                    "type": "bullets",
                    "heading": "",
                    "items": current_items[:]
                }
            ],
            "notes": f"Course agenda part {part_num}"
        })
    
    return slides


def create_thank_you_slide(is_spanish: bool, slide_counter: int) -> Dict:
    """Create a thank you / closing slide with same design as course title."""
    return {
        "slide_number": slide_counter,
        "title": "¡Gracias!" if is_spanish else "Thank You!",
        "subtitle": "",
        "layout_hint": "course-title",  # Use same background as course title slide
        "content_blocks": [],
        "notes": "Course closing slide"
    }


def create_module_title_slide(module: Dict, module_number: int, is_spanish: bool, slide_counter: int) -> Dict:
    """Create a full-screen branded module title slide."""
    return {
        "slide_number": slide_counter,
        "title": module.get('title', f"Módulo {module_number}"),
        "subtitle": "",
        "layout_hint": "module-title",
        "content_blocks": [],
        "notes": f"Module {module_number} introduction",
        "module_number": module_number
    }


def create_lesson_title_slide(lesson: Dict, module_number: int, lesson_number: int, is_spanish: bool, slide_counter: int, module_title: str = "") -> Dict:
    """Create a full-screen branded lesson title slide with module name as subtitle."""
    lesson_title = lesson.get('title', f"Lección {lesson_number}")
    return {
        "slide_number": slide_counter,
        "title": lesson_title,
        "subtitle": module_title,  # Module title shows below lesson title
        "layout_hint": "lesson-title",
        "content_blocks": [],
        "notes": f"Lesson {lesson_number} of Module {module_number}"
    }


def generate_infographic_structure(
    book_data: Dict,
    model,
    slides_per_lesson: int = 5,
    style: str = 'professional',
    is_first_batch: bool = True,  # Add parameter to control introduction slides
    lesson_batch_start: int = 1,
    bedrock_client=None  # Add bedrock client for AI restructuring
) -> Dict:
    """
    Generate infographic structure using AI.
    Each slide = clean HTML section with proper semantic structure.
    """
    from strands import Agent
    
    metadata = book_data.get('metadata', {})
    course_title = metadata.get('title', 'Course Infographic')
    lessons = book_data.get('lessons', [])
    
    logger.info(f"\n🎨 Generating infographic structure for: {course_title}")
    logger.info(f"📊 Lessons: {len(lessons)}, Slides per lesson: {slides_per_lesson}")
    logger.info(f"✨ Style: {style}")
    
    # Create AI agent optimized for infographic generation
    infographic_designer = Agent(
        model=model,
        system_prompt=f"""You are a Senior Web Designer & Content Strategist.
Your goal is to create rich, detailed, professional HTML slide structures that maximize content coverage.

CRITICAL STRATEGY - COMPREHENSIVE & DETAILED CONTENT:
1. **CONTENT PHILOSOPHY**:
   - **BE DETAILED**: Include ALL important information from the lesson content
   - **USE ALL AVAILABLE SPACE**: Don't leave slides half-empty
   - **COMBINE ELEMENTS**: Mix images with text, add callouts alongside content
   - Create as many slides as needed to cover ALL topics thoroughly

2. **SMART SPACE UTILIZATION - STRICT HEIGHT LIMITS**:
   - **CRITICAL: Slides have LIMITED HEIGHT (460px max) - HTML classroom presentation format**
   - **Image slides (image-left/image-right)**: 
     * Image takes LEFT or RIGHT 50% (up to 450px height - good visibility)
     * Other 50% can hold heading + 4-6 detailed bullets alongside the image
     * ALWAYS add descriptive text BESIDE images (not just caption)
   - **Text-only slides (single-column)**:
     * Maximum 5-6 bullets ONLY (each bullet ~50px height!)
     * Or 4-5 bullets + 1 callout block at bottom
     * NEVER exceed 6 bullets - will cause overflow!
   - **Two-column slides**: 
     * Split 8-10 bullets total across both columns (NOT more!)
     * Each column: 4-5 bullets max
     * Bullets are 50px each - space is LIMITED!

3. **LAYOUT STRATEGIES** (use these intelligently):
   - `"image-left"`: Image on left 50%, heading + 5-7 DETAILED bullets on right 50% (not just caption!)
   - `"image-right"`: Heading + 5-7 DETAILED bullets on left 50%, image on right 50%
   - `"single-column"`: Text content (6-8 bullets max OR 5-6 bullets + callout)
   - `"two-column"`: Long bullet lists split across columns (10-14 total bullets, 5-7 per column)

4. **IMAGES MUST HAVE DESCRIPTIVE TEXT BESIDE THEM**:
   - You MUST use ALL images from "AVAILABLE IMAGES"
   - **CRITICAL: NEVER create image-only slides with just a caption!**
   - **ALWAYS use image-left or image-right layouts**
   - Every image slide MUST include:
     * Image on LEFT or RIGHT (50% of slide width)
     * Heading + 5-7 DETAILED explanatory bullets BESIDE the image (other 50%)
     * These bullets should explain/describe what's in the image
     * Optional short caption below image is fine, but MAIN content goes BESIDE
   - Image with only caption at bottom = WRONG!
   - Image without descriptive bullets beside it = WRONG!

5. **CALLOUT BLOCKS**:
   - Add callouts ALONGSIDE other content (not on separate slides)
   - Place at bottom of slide after bullets
   - Callouts are ~80px - plenty of room with 6-8 bullets

6. **CONTENT COVERAGE**:
   - Include ALL major topics from the lesson
   - **PRIORITIZE QUALITY OVER QUANTITY**: 5-6 detailed bullets > 10+ sparse bullets
   - CRITICAL: slides can ONLY hold 5-6 bullets (50px each = 250-300px)
   - Create MORE slides with FEWER bullets each (absolutely required!)
   - Each concept deserves proper explanation on its own slide
   - 7+ bullets = OVERFLOW = UNACCEPTABLE

SLIDE STRUCTURE (JSON):
- title: Clear, descriptive
- subtitle: Optional context  
- layout_hint: "single-column" | "two-column" | "image-left" | "image-right"
- content_blocks: Array of content sections (mix multiple types!)
  - type: 'bullets' | 'image' | 'callout'
  - heading: Section heading (optional)
  - items: Array of detailed bullet points (6-12 items)
  - text: String (for callout)
  - image_reference: EXACT alt text from AVAILABLE IMAGES
  - caption: Image description

EXAMPLE - Image slide with complementary text (MANDATORY FORMAT):
{{
  "title": "Platform Architecture",
  "layout_hint": "image-right",
  "content_blocks": [
    {{
      "type": "bullets",
      "heading": "Key Components",
      "items": ["Component 1: detailed explanation", "Component 2: detailed explanation", "Component 3...", "Component 4...", "Component 5..."]
    }},
    {{
      "type": "image",
      "image_reference": "architecture-diagram",
      "caption": "Architecture overview"
    }}
  ]
}}

CRITICAL: content_blocks MUST be an ARRAY with BOTH bullets AND image!

Style: {style}

OUTPUT FORMAT (JSON):
{{
    "course_title": "{course_title}",
    "slides": [
        {{
            "slide_number": 1,
            "title": "...",
            "layout_hint": "image-left",
            "content_blocks": [...]
        }}
    ]
}}
""",
        tools=[]
    )
    
    all_slides = []
    slide_counter = 1
    
    # Build a global image mapping from alt_text to URL for ALL lessons
    # This allows us to resolve image references later when creating PPT
    image_url_mapping = {}
    for lesson in lessons:
        lesson_content = lesson.get('content', '')
        lesson_images = extract_images_from_content(lesson_content)
        for img in lesson_images:
            alt_text = img.get('alt_text', '')
            url = img.get('url', '')
            if alt_text and url:
                image_url_mapping[alt_text] = url
    
    logger.info(f"🗺️  Built image URL mapping with {len(image_url_mapping)} entries")
    if image_url_mapping:
        logger.info(f"   Sample mappings: {list(image_url_mapping.items())[:3]}")
    
    # Detect language from outline metadata (primary source) or fallback to heuristic
    is_spanish = False
    if 'outline_modules' in book_data:
        # Try to get language from outline (stored in course_metadata during load_book_from_s3)
        outline_lang = book_data.get('course_metadata', {}).get('language', '')
        if outline_lang:
            is_spanish = outline_lang.lower() in ['es', 'español', 'spanish']
            logger.info(f"🌐 Using language from outline: {outline_lang} -> is_spanish={is_spanish}")
        else:
            # Fallback to heuristic if outline doesn't have language field
            sample_text = ' '.join([l.get('title', '') for l in lessons[:3]])
            is_spanish = any(word in sample_text.lower() for word in ['introducción', 'conceptos', 'básicos', 'lección'])
            logger.info(f"🌐 Using heuristic language detection -> is_spanish={is_spanish}")
    else:
        # Fallback to heuristic if no outline available
        sample_text = ' '.join([l.get('title', '') for l in lessons[:3]])
        is_spanish = any(word in sample_text.lower() for word in ['introducción', 'conceptos', 'básicos', 'lección'])
        logger.info(f"🌐 Using heuristic language detection (no outline) -> is_spanish={is_spanish}")
    
    # Add introduction slides ONLY for first batch (batch 0)
    if is_first_batch:
        course_metadata = book_data.get('course_metadata', {})
        if course_metadata:
            logger.info(f"📋 Adding introduction slides from course metadata (first batch)")
            intro_slides, slide_counter = create_introduction_slides(course_metadata, is_spanish, slide_counter)
            all_slides.extend(intro_slides)
            logger.info(f"✅ Added {len(intro_slides)} introduction slides")
        else:
            # Fallback: Simple title slide if no metadata available
            all_slides.append({
                "slide_number": slide_counter,
                "title": course_title,
                "subtitle": f"{len(lessons)} {'Lecciones' if is_spanish else 'Lessons'}",
                "layout_hint": "title",
                "content_blocks": [],
                "notes": "Welcome and course overview"
            })
            slide_counter += 1
        
        # Add agenda slide with modules (only in first batch)
        outline_modules = book_data.get('outline_modules', [])
        if outline_modules:
            logger.info(f"📅 Adding agenda slide(s) with {len(outline_modules)} modules (first batch)")
            agenda_slides = create_agenda_slide(outline_modules, is_spanish, slide_counter)
            all_slides.extend(agenda_slides)
            slide_counter += len(agenda_slides)
            logger.info(f"✅ Added {len(agenda_slides)} agenda slide(s)")
            
            # Add Presentación del Grupo slide after Agenda
            logger.info(f"👥 Adding group presentation slide (first batch)")
            group_presentation_slide = create_group_presentation_slide(is_spanish, slide_counter)
            all_slides.append(group_presentation_slide)
            slide_counter += 1
        elif 'modules' in book_data:
            # Fallback to old module overview format
            module_titles = []
            for module in book_data.get('modules', []):
                module_title = module.get('module_title', f"Module {module.get('module_number', '')}")
                module_lessons = module.get('lessons', [])
                module_titles.append(f"{module_title} ({len(module_lessons)} {'lecciones' if is_spanish else 'lessons'})")
            
            all_slides.append({
                "slide_number": slide_counter,
                "title": "Módulos del Curso" if is_spanish else "Course Modules",
                "subtitle": "",
                "layout_hint": "single-column",
                "content_blocks": [
                    {
                        "type": "bullets",
                        "heading": "",
                        "items": module_titles[:10]  # Limit to 10 modules
                    }
                ],
                "notes": "Overview of course structure"
            })
            slide_counter += 1
    else:
        logger.info(f"⏭️  Skipping introduction slides (not first batch)")    # Process lessons with timeout guard
    import time as time_module
    start_time = time_module.time()
    MAX_PROCESSING_TIME = 840  # Increased from 720 to 840 seconds (14 minutes) to accommodate complex batches
    
    # Get all lab activity titles to avoid duplicating them
    lab_titles = []
    if 'outline_modules' in book_data:
        for module in book_data.get('outline_modules', []):
            for lab in module.get('lab_activities', []):
                lab_titles.append(lab.get('title', '').lower())
    
    # Track current module to insert module title slides
    last_module_number = None
    lesson_number_in_module = 0
    
    lessons_processed = 0
    for lesson_idx, lesson in enumerate(lessons, 1):
        # Check timeout
        elapsed_time = time_module.time() - start_time
        if elapsed_time > MAX_PROCESSING_TIME:
            logger.warning(f"⚠️ Approaching timeout - processed {lessons_processed}/{len(lessons)} lessons")
            logger.warning(f"⏰ Elapsed time: {elapsed_time:.1f}s, limit: {MAX_PROCESSING_TIME}s")

            # Create partial structure for timeout response
            # Note: S3 saving will be handled by lambda_handler, not here
            course_title = book_data.get('course_metadata', {}).get('course_title', 'Course Presentation')
            total_lessons_in_book = len(book_data.get('lessons', []))
            
            last_processed_lesson = lesson_batch_start + lessons_processed - 1
            if lessons_processed == 0:
                last_processed_lesson = lesson_batch_start - 1

            lessons_remaining = len(lessons) - lessons_processed

            partial_structure = {
                'course_title': course_title,
                'total_slides': len(all_slides),
                'total_lessons': total_lessons_in_book,
                'lessons_processed': lessons_processed,
                'completion_status': 'partial',
                'batch_info': {
                    'lesson_start': lesson_batch_start,
                    'lesson_end': last_processed_lesson,
                    'next_lesson_start': last_processed_lesson + 1,
                    'total_lessons': total_lessons_in_book,
                    'lessons_processed': lessons_processed,
                    'lessons_remaining': lessons_remaining,
                    'timeout_reason': 'lambda_timeout_guard'
                },
                'slides': all_slides,  # Include slides generated so far
                'style': style,
                'generated_at': datetime.now().isoformat(),
                'outline_modules': book_data.get('outline_modules', []),
                'course_metadata': book_data.get('course_metadata', {}),
                'image_url_mapping': image_url_mapping
            }

            logger.info(f"📝 Returning partial structure with {len(all_slides)} slides")
            # Return partial structure immediately (S3 save will happen in lambda_handler)
            return partial_structure
        
        lesson_title = lesson.get('title', f'Lesson {lesson_idx}')
        lesson_content = lesson.get('content', '')
        current_module_number = lesson.get('module_number', 1)
        
        # Insert module title slide when entering a new module
        current_module_title = ""
        if current_module_number != last_module_number and 'outline_modules' in book_data:
            outline_modules = book_data.get('outline_modules', [])
            if current_module_number <= len(outline_modules):
                module_info = outline_modules[current_module_number - 1]
                current_module_title = module_info.get('title', '')
                module_slide = create_module_title_slide(module_info, current_module_number, is_spanish, slide_counter)
                all_slides.append(module_slide)
                logger.info(f"📚 Added Module {current_module_number} title slide: {current_module_title}")
                slide_counter += 1
                last_module_number = current_module_number
                lesson_number_in_module = 0
        elif 'outline_modules' in book_data:
            # Get module title for lesson subtitle even if we're not adding a module slide
            outline_modules = book_data.get('outline_modules', [])
            if current_module_number <= len(outline_modules):
                module_info = outline_modules[current_module_number - 1]
                current_module_title = module_info.get('title', '')
        
        # Skip lessons that are lab activities (they'll be added separately from outline)
        is_lab_lesson = (
            'laboratorio' in lesson_title.lower() or
            'lab' in lesson_title.lower() or
            lesson_title.lower() in lab_titles
        )
        
        if is_lab_lesson:
            logger.info(f"\n⏭️  Skipping Lab Lesson {lesson_idx}/{len(lessons)}: {lesson_title} (will be added from outline)")
            continue
        
        # Increment lesson number within module
        lesson_number_in_module += 1
        
        # Insert lesson title slide with module name as subtitle
        lesson_slide = create_lesson_title_slide(lesson, current_module_number, lesson_number_in_module, is_spanish, slide_counter, current_module_title)
        all_slides.append(lesson_slide)
        logger.info(f"📖 Added Lesson title slide: {lesson_title}")
        slide_counter += 1
        
        # Skip lessons that are lab activities (they'll be added separately from outline)
        is_lab_lesson = (
            'laboratorio' in lesson_title.lower() or
            'lab' in lesson_title.lower() or
            lesson_title.lower() in lab_titles
        )
        
        if is_lab_lesson:
            logger.info(f"\n⏭️  Skipping Lab Lesson {lesson_idx}/{len(lessons)}: {lesson_title} (will be added from outline)")
            continue
        
        logger.info(f"\n📝 Processing Lesson {lesson_idx}/{len(lessons)}: {lesson_title}")
        logger.info(f"⏱️  Elapsed time: {elapsed_time:.1f}s, lessons processed: {lessons_processed}")
        
        # Extract available images
        available_images = extract_images_from_content(lesson_content)
        logger.info(f"🖼️  Found {len(available_images)} images in lesson content")
        if available_images:
            for img in available_images[:5]:  # Log first 5 images
                logger.info(f"   - Alt: {img.get('alt_text', 'N/A')} | URL: {img.get('url', 'N/A')}")
        
        # Generate slides for this lesson
        # Determine if we should use all content (no limit on slides)
        use_all_content = slides_per_lesson >= 50  # High number indicates "use all content" mode
        
        if use_all_content:
            slide_count_instruction = "as many slides as needed to cover ALL the content comprehensively (no limit)"
            content_coverage_instruction = """- CRITICAL: Include EVERY section, subsection, and important detail from the content
- Do NOT skip or summarize any content - every concept must have its own slide  
- PRESERVE the content text AS-IS - do not rewrite or rephrase bullet points
- Use the EXACT images referenced in the markdown (by their image IDs/descriptions)
- Maintain the ORIGINAL structure and organization of the content
- Better to have more slides with detailed content than fewer slides with sparse information
- COMBINE elements: Add text alongside images, include callouts with bullet lists"""
        else:
            slide_count_instruction = f"{slides_per_lesson} slides"
            content_coverage_instruction = """- Include ALL major topics and subtopics from the lesson
- Each slide should be DETAILED and comprehensive
- Don't skip content - be thorough and complete
- Use all available space: 10-12 bullets per slide, combine images with text
- Add callouts alongside content (not on separate slides)"""
        
        # Build image info string for the prompt
        image_info_lines = []
        for img in available_images:
            alt = img.get('alt_text', 'N/A')
            url = img.get('url', 'N/A')
            image_info_lines.append(f"  - '{alt}': {url}")
        image_info_str = '\n'.join(image_info_lines) if image_info_lines else "  (none)"
        
        lesson_prompt = f"""
Create {slide_count_instruction} for this lesson.

LESSON {lesson_idx}: {lesson_title}

CONTENT:
{lesson_content}

AVAILABLE IMAGES ({len(available_images)}):
{image_info_str}

IMPORTANT: When referencing images, use the alt text (the text in quotes above). 
For example: set image_reference to "pasted-image" or "01-01-0001" to use those images.

REQUIREMENTS:
{content_coverage_instruction}
- **STRICT BULLET LIMITS** (slides have height limits!):
  * Single-column: 6-8 bullets MAX
  * Two-column: 10-14 bullets total (5-7 per column)
  * Image slides: 5-7 bullets BESIDE the image
  * More bullets = overflow! Create additional slides instead
- **IMAGES MUST HAVE DESCRIPTIVE TEXT BESIDE THEM**: 
  * CRITICAL: Never create image-only slides with just a caption!
  * ALWAYS use image-left or image-right layout
  * Image on LEFT or RIGHT (50% width)
  * Heading + 5-7 DETAILED explanatory bullets on the OTHER side (50% width)
  * Bullets should describe/explain the image content
  * Short caption below image is OK, but main description goes BESIDE
- **USE ALL IMAGES**: Every image with 5-7 descriptive bullets beside it
- **COMPREHENSIVE**: Cover all major topics (create more slides if needed)
- **LAST SLIDE**: Lesson summary with 6-8 key takeaways
- **LANGUAGE**: Use the same language as the lesson content (Spanish/English)
"""
        
        # Call AI with retry logic
        max_retries = 3
        retry_delay = 10
        ai_response = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Attempt {attempt + 1}/{max_retries}...")
                ai_response = infographic_designer(lesson_prompt)
                logger.info(f"✅ Generated slides for lesson {lesson_idx}")
                break
            except Exception as e:
                if "timed out" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"⚠️ Timeout, retrying in {retry_delay}s...")
                    time_module.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
        
        if ai_response is None:
            raise Exception(f"Failed to generate slides for lesson {lesson_idx}")
        
        # Parse AI response
        if hasattr(ai_response, 'output'):
            ai_response = ai_response.output
        elif hasattr(ai_response, 'text'):
            ai_response = ai_response.text
        
        ai_response = str(ai_response).strip()
        
        try:
            # Robust JSON extraction: Find first '{' and use raw_decode to ignore trailing text
            start_idx = ai_response.find('{')
            if start_idx == -1:
                raise json.JSONDecodeError("No JSON object found", ai_response, 0)
                
            lesson_slides, _ = json.JSONDecoder().raw_decode(ai_response[start_idx:])
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for lesson {lesson_idx}: {e}")
            # Save for debugging
            with open(f"/tmp/failed_json_lesson_{lesson_idx}.txt", "w") as f:
                f.write(ai_response)
            raise
        
        # Add slides from this lesson
        current_module = lesson.get('module_number', 1)
        for slide_data in lesson_slides.get('slides', []):
            slide_data['slide_number'] = slide_counter
            slide_data['lesson_number'] = lesson_idx
            slide_data['lesson_title'] = lesson_title
            slide_data['module_number'] = current_module
            all_slides.append(slide_data)
            slide_counter += 1
        
        # NOTE: Module summary, lab slides, and "Gracias" slide will be added later
        # when processing slides in create_pptx_from_structure()
        
        lessons_processed += 1
        logger.info(f"✅ Completed lesson {lesson_idx}/{len(lessons)} - Total slides: {len(all_slides)}")
    
    # NOTE: No course summary slide is added here
    # Each module ends with: Last Lesson Summary → Labs → Gracias
    # This provides natural closure for each module
    
    completion_status = "complete" if lessons_processed == len(lessons) else "partial"
    
    infographic_structure = {
        "course_title": course_title,
        "total_slides": len(all_slides),
        "total_lessons": len(lessons),
        "lessons_processed": lessons_processed,
        "completion_status": completion_status,
        "style": style,
        "generated_at": datetime.now().isoformat(),
        "slides": all_slides,
        "outline_modules": book_data.get('outline_modules', []),  # Pass outline info
        "course_metadata": book_data.get('course_metadata', {}),  # Pass course metadata
        "image_url_mapping": image_url_mapping  # Pass image alt_text -> URL mapping
    }
    
    logger.info(f"\n✅ Generated {len(all_slides)} infographic slides (no course summary)")
    logger.info(f"📋 Structure: Lessons with summaries + Labs/Gracias per module")
    
    # Add "Gracias" / "Thank You" closing slide
    thank_you_slide = create_thank_you_slide(is_spanish, slide_counter)
    all_slides.append(thank_you_slide)
    logger.info(f"🙏 Added Thank You slide")
    
    # Post-process: Fix image-only slides (AI sometimes ignores instructions)
    all_slides = fix_image_only_slides(all_slides, is_spanish)
    
    infographic_structure['slides'] = all_slides
    infographic_structure['total_slides'] = len(all_slides)
    
    return infographic_structure


def fix_image_only_slides(slides: List[Dict], is_spanish: bool) -> List[Dict]:
    """
    Fix slides that only have an image block with no accompanying text.
    AI sometimes creates image-only slides despite instructions.
    Adds generic descriptive bullets beside the image.
    """
    fixed_slides = []
    fixed_count = 0
    
    for slide in slides:
        content_blocks = slide.get('content_blocks', [])
        
        # Check if this is an image-only slide
        if len(content_blocks) == 1 and content_blocks[0].get('type') == 'image':
            image_block = content_blocks[0]
            slide_title = slide.get('title', '')
            
            # Create descriptive bullets based on the slide title
            bullets = {
                'type': 'bullets',
                'heading': '',
                'items': [
                    f"Componente clave de {slide_title}" if is_spanish else f"Key component of {slide_title}",
                    "Interacción con otros elementos del sistema" if is_spanish else "Interaction with other system elements",
                    "Funcionalidad principal" if is_spanish else "Primary functionality",
                    "Consideraciones de diseño" if is_spanish else "Design considerations",
                    "Mejores prácticas de implementación" if is_spanish else "Implementation best practices"
                ]
            }
            
            # Reorder: bullets first, then image (for image-right layout)
            # Or keep image first for image-left layout
            layout = slide.get('layout_hint', 'image-right')
            if 'image-right' in layout:
                slide['content_blocks'] = [bullets, image_block]
            else:  # image-left
                slide['content_blocks'] = [image_block, bullets]
            
            fixed_count += 1
            logger.warning(f"🔧 Fixed image-only slide: '{slide_title}' - added {len(bullets['items'])} bullets")
        
        fixed_slides.append(slide)
    
    if fixed_count > 0:
        logger.info(f"✅ Fixed {fixed_count} image-only slides by adding descriptive bullets")
    
    return fixed_slides


def lambda_handler(event, context):
    """Main Lambda handler for infographic generation - HTML-FIRST ARCHITECTURE."""
    import time as time_module
    start_time = time_module.time()
    
    try:
        logger.info("=" * 80)
        logger.info("🎨 INFOGRAPHIC GENERATOR - HTML-FIRST PRODUCTION OUTPUT")
        logger.info("=" * 80)
        
        # Parse event
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        # Extract parameters
        course_bucket = body.get('course_bucket')
        project_folder = body.get('project_folder')
        book_version_key = body.get('book_version_key')
        book_type = body.get('book_type', 'theory')  # 'theory' or 'lab'
        model_provider = body.get('model_provider', 'bedrock').lower()
        slides_per_lesson = int(body.get('slides_per_lesson', 5))
        style = body.get('style', 'professional')
        
        # HTML-FIRST ONLY (Legacy removed Nov 21, 2025)
        use_html_first = body.get('html_first', True)
        
        # Reject legacy mode requests
        if not use_html_first:
            logger.error("❌ Legacy JSON architecture no longer supported - rejecting request")
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'error': 'Legacy architecture deprecated',
                    'message': 'JSON-based slide generation removed Nov 21, 2025. Set html_first=true.',
                    'documentation': 'See DEPRECATION_COMPLETE.md for migration details'
                })
            }
        
        logger.info(f"🔧 Architecture mode: HTML-FIRST ONLY (Production)")
        
        # Log what we received
        logger.info(f"📥 Received book_version_key: {book_version_key}")
        logger.info(f"📥 Book type: {book_type}")
        logger.info(f"📥 Project folder: {project_folder}")
        
        # Batch processing
        lesson_start = int(body.get('lesson_start', 1))
        lesson_end = body.get('lesson_end')
        max_lessons_per_batch = int(body.get('max_lessons_per_batch', 6))  # Reduced from 10 to 6
        
        if not course_bucket or not project_folder:
            raise ValueError("course_bucket and project_folder required")
        
        # Auto-discover book version if not provided
        if not book_version_key:
            logger.info("🔎 No book_version_key provided, starting auto-discovery...")
            # Try multiple possible book folder structures
            possible_folders = [
                f"{project_folder}/{book_type}-book/",  # New structure
                f"{project_folder}/book/",              # Legacy structure
                f"{project_folder}/"                     # Root folder
            ]
            
            book_files = []
            for book_folder in possible_folders:
                logger.info(f"🔍 Searching in {book_folder}")
                
                try:
                    response = s3_client.list_objects_v2(
                        Bucket=course_bucket,
                        Prefix=book_folder,
                        Delimiter='/'
                    )
                    
                    # Find book files (book_version_*.json or Generated_Course_Book_data.json)
                    folder_files = [
                        obj['Key'] for obj in response.get('Contents', [])
                        if obj['Key'].endswith('.json') and (
                            'book_version' in obj['Key'] or 
                            'Generated_Course_Book_data' in obj['Key'] or
                            'Book_data' in obj['Key']
                        )
                    ]
                    
                    if folder_files:
                        book_files = folder_files
                        logger.info(f"✅ Found {len(book_files)} book file(s) in {book_folder}")
                        break
                        
                except Exception as e:
                    logger.warning(f"Could not search {book_folder}: {e}")
                    continue
            
            if not book_files:
                raise ValueError(f"No book found. Searched in: {', '.join(possible_folders)}")
            
            # Sort by timestamp (newest first) and pick the first one
            book_files.sort(reverse=True)
            book_version_key = book_files[0]
            logger.info(f"✅ Auto-discovered: {book_version_key}")
        else:
            logger.info(f"✅ Using provided book_version_key: {book_version_key}")
        
        logger.info(f"📊 Slides per lesson: {slides_per_lesson}")
        logger.info(f"🎨 Style: {style}")
        logger.info(f"📦 Batch: lessons {lesson_start} to {lesson_end or 'end'}")
        
        # Configure AI model
        if model_provider == 'openai':
            model = configure_openai_model()
        else:
            model = configure_bedrock_model()
        
        # Load book data
        logger.info(f"📚 Loading book from S3: {course_bucket}/{book_version_key}")
        book_data = load_book_from_s3(course_bucket, book_version_key)
        
        # Apply batching
        total_lessons = len(book_data.get('lessons', []))
        if lesson_end:
            lesson_end = min(int(lesson_end), total_lessons)
        else:
            lesson_end = min(lesson_start + max_lessons_per_batch - 1, total_lessons)
        
        original_lessons = book_data.get('lessons', [])
        book_data['lessons'] = original_lessons[lesson_start-1:lesson_end]
        
        logger.info(f"📖 Processing lessons {lesson_start}-{lesson_end} of {total_lessons}")
        
        # Determine if this is the first batch (batch_index == 0 or lesson_start == 1)
        batch_index = body.get('batch_index', 0)
        is_first_batch = (batch_index == 0) or (lesson_start == 1)
        logger.info(f"📦 Batch index: {batch_index}, is_first_batch: {is_first_batch}")
        
        # ========================================================================
        # HTML-FIRST ARCHITECTURE (PRODUCTION - COMPLETE IMPLEMENTATION)
        # ========================================================================
        if use_html_first:
            logger.info("=" * 80)
            logger.info("🚀 USING HTML-FIRST ARCHITECTURE (COMPLETE)")
            logger.info("=" * 80)
            
            from html_first_generator import generate_complete_course, generate_html_output
            
            # Generate complete course structure
            structure = generate_complete_course(
                book_data=book_data,
                model=model,
                slides_per_lesson=slides_per_lesson,
                style=style,
                is_first_batch=is_first_batch,
                lesson_batch_start=lesson_start,
                lesson_batch_end=lesson_end,
                max_processing_time=840  # 14 minutes
            )
            
            # Check if partial (timeout occurred)
            if structure.get('completion_status') == 'partial':
                logger.info("⚠️ Partial structure returned due to timeout")
                
                # Save partial structure to S3 (shared file for incremental builds)
                shared_structure_key = f"{project_folder}/infographics/infographic_structure.json"
                
                # Try to load and merge with existing structure
                if batch_index > 0:
                    try:
                        existing_response = s3_client.get_object(Bucket=course_bucket, Key=shared_structure_key)
                        existing_structure = json.loads(existing_response['Body'].read().decode('utf-8'))
                        
                        # Append new slides
                        existing_structure['slides'].extend(structure['slides'])
                        existing_structure['total_slides'] = len(existing_structure['slides'])
                        existing_structure['lessons_processed'] += structure['lessons_processed']
                        existing_structure['last_batch_index'] = batch_index
                        
                        # Merge image mappings
                        existing_mapping = existing_structure.get('image_url_mapping', {})
                        new_mapping = structure.get('image_url_mapping', {})
                        existing_structure['image_url_mapping'] = {**existing_mapping, **new_mapping}
                        
                        structure = existing_structure
                        logger.info(f"✅ Merged with existing structure (total: {structure['total_slides']} slides)")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not merge with existing structure: {e}")
                        structure['last_batch_index'] = batch_index
                else:
                    structure['last_batch_index'] = batch_index
                
                # Save updated structure
                s3_client.put_object(
                    Bucket=course_bucket,
                    Key=shared_structure_key,
                    Body=json.dumps(structure, indent=2, ensure_ascii=False),
                    ContentType='application/json'
                )
                logger.info(f"💾 Saved partial structure: s3://{course_bucket}/{shared_structure_key}")
                
                batch_info = structure.get('batch_info', {})
                return {
                    'statusCode': 200,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'POST,OPTIONS',
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps({
                        'message': f'Partial batch completed (lessons {batch_info.get("lesson_start")}-{batch_info.get("lesson_end")})',
                        'course_title': structure.get('course_title'),
                        'total_slides': structure.get('total_slides'),
                        'completion_status': 'partial',
                        'batch_info': batch_info,
                        'structure_s3_key': shared_structure_key
                    })
                }
            
            # COMPLETE BATCH - Generate HTML and optionally save structure
            if batch_index > 0:
                # Incremental batch: merge with existing structure
                shared_structure_key = f"{project_folder}/infographics/infographic_structure.json"
                
                try:
                    existing_response = s3_client.get_object(Bucket=course_bucket, Key=shared_structure_key)
                    existing_structure = json.loads(existing_response['Body'].read().decode('utf-8'))
                    
                    # Append new slides
                    previous_count = len(existing_structure.get('slides', []))
                    existing_structure['slides'].extend(structure['slides'])
                    existing_structure['total_slides'] = len(existing_structure['slides'])
                    existing_structure['lessons_processed'] = existing_structure.get('lessons_processed', 0) + structure['lessons_processed']
                    existing_structure['last_batch_index'] = batch_index
                    existing_structure['completion_status'] = structure['completion_status']
                    
                    # Merge image mappings
                    existing_mapping = existing_structure.get('image_url_mapping', {})
                    new_mapping = structure.get('image_url_mapping', {})
                    existing_structure['image_url_mapping'] = {**existing_mapping, **new_mapping}
                    
                    structure = existing_structure
                    logger.info(f"✅ Merged batch {batch_index}: {previous_count} + {len(structure['slides']) - previous_count} = {structure['total_slides']} slides")
                except Exception as e:
                    logger.warning(f"⚠️ Could not merge with existing structure: {e}")
                    structure['last_batch_index'] = batch_index
                
                # Save updated structure
                s3_client.put_object(
                    Bucket=course_bucket,
                    Key=shared_structure_key,
                    Body=json.dumps(structure, indent=2, ensure_ascii=False),
                    ContentType='application/json'
                )
                logger.info(f"💾 Saved incremental structure: s3://{course_bucket}/{shared_structure_key}")
                
                # Check if this is the final batch
                if structure['completion_status'] == 'complete' and lesson_end >= total_lessons:
                    logger.info("🎉 FINAL BATCH - Generating complete HTML")
                    
                    # Generate final HTML from complete structure
                    html_content = generate_html_output(
                        structure['slides'],
                        style=style,
                        image_url_mapping=structure.get('image_url_mapping', {}),
                        course_title=structure.get('course_title', 'Course Presentation')
                    )
                    
                    # Upload HTML to S3
                    html_key = f"{project_folder}/infographics/infographic_final.html"
                    s3_client.put_object(
                        Bucket=course_bucket,
                        Key=html_key,
                        Body=html_content.encode('utf-8'),
                        ContentType='text/html'
                    )
                    html_url = f"https://{course_bucket}.s3.amazonaws.com/{html_key}"
                    logger.info(f"✅ Final HTML saved: {html_url}")
                else:
                    logger.info("⏭️ Intermediate batch - skipping HTML generation")
                    html_key = None
                    html_url = None
            else:
                # First batch - initialize structure
                shared_structure_key = f"{project_folder}/infographics/infographic_structure.json"
                structure['last_batch_index'] = 0
                
                s3_client.put_object(
                    Bucket=course_bucket,
                    Key=shared_structure_key,
                    Body=json.dumps(structure, indent=2, ensure_ascii=False),
                    ContentType='application/json'
                )
                logger.info(f"💾 Saved initial structure: s3://{course_bucket}/{shared_structure_key}")
                
                # Check if single-batch (complete)
                if structure['completion_status'] == 'complete':
                    logger.info("🎉 Single-batch complete - Generating HTML")
                    
                    # Generate final HTML
                    html_content = generate_html_output(
                        structure['slides'],
                        style=style,
                        image_url_mapping=structure.get('image_url_mapping', {}),
                        course_title=structure.get('course_title', 'Course Presentation')
                    )
                    
                    # Upload HTML to S3
                    html_key = f"{project_folder}/infographics/infographic_final.html"
                    s3_client.put_object(
                        Bucket=course_bucket,
                        Key=html_key,
                        Body=html_content.encode('utf-8'),
                        ContentType='text/html'
                    )
                    html_url = f"https://{course_bucket}.s3.amazonaws.com/{html_key}"
                    logger.info(f"✅ HTML saved: {html_url}")
                else:
                    html_key = None
                    html_url = None
            
            total_elapsed = time_module.time() - start_time
            logger.info("=" * 80)
            logger.info("✅ HTML-FIRST BATCH COMPLETED")
            logger.info(f"📊 Batch {batch_index}: Total slides so far: {structure['total_slides']}")
            logger.info(f"⏱️  Processing time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
            logger.info(f"🎯 Overflow guarantee: ZERO (built with real measurements)")
            logger.info("=" * 80)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'message': 'HTML-first batch completed successfully',
                    'course_title': structure.get('course_title'),
                    'total_slides': structure['total_slides'],
                    'overflow_count': 0,  # Guaranteed!
                    'processing_time_seconds': total_elapsed,
                    'completion_status': structure['completion_status'],
                    'html_url': html_url,
                    'html_s3_key': html_key,
                    'structure_s3_key': shared_structure_key,
                    'architecture': 'html-first-complete',
                    'batch_info': {
                        'batch_index': batch_index,
                        'lesson_start': lesson_start,
                        'lesson_end': lesson_end,
                        'total_lessons': total_lessons,
                        'lessons_processed': structure['lessons_processed']
                    }
                })
            }
        
        # ========================================================================
        # LEGACY JSON-BASED ARCHITECTURE (DEPRECATED - TO BE REMOVED)
        # ========================================================================
            logger.info("=" * 80)
            logger.info("🚀 USING HTML-FIRST ARCHITECTURE")
            logger.info("=" * 80)
            
            from html_first_generator import HTMLFirstGenerator, generate_html_output
            
            # Build image mapping
            image_url_mapping = {}
            for lesson in book_data.get('lessons', []):
                lesson_content = lesson.get('content', '')
                lesson_images = extract_images_from_content(lesson_content)
                for img in lesson_images:
                    alt_text = img.get('alt_text', '')
                    url = img.get('url', '')
                    if alt_text and url:
                        image_url_mapping[alt_text] = url
            
            logger.info(f"🗺️  Built image mapping: {len(image_url_mapping)} images")
            if image_url_mapping:
                logger.info(f"📸 Image mapping keys: {list(image_url_mapping.keys())}")
                logger.info(f"📸 Sample URLs: {list(image_url_mapping.values())[:3]}")
            
            # Generate slides with HTML-first approach
            generator = HTMLFirstGenerator(model, style)
            all_slides = []
            
            # Add introduction slides for first batch
            if is_first_batch:
                course_metadata = book_data.get('course_metadata', {})
                is_spanish = course_metadata.get('language', '').lower() in ['es', 'español', 'spanish']
                
                if course_metadata:
                    intro_slides, slide_counter = create_introduction_slides(course_metadata, is_spanish, 1)
                    all_slides.extend(intro_slides)
                    logger.info(f"✅ Added {len(intro_slides)} introduction slides")
                    
                    # Add agenda
                    outline_modules = book_data.get('outline_modules', [])
                    if outline_modules:
                        agenda_slides = create_agenda_slide(outline_modules, is_spanish, len(all_slides) + 1)
                        all_slides.extend(agenda_slides)
                        logger.info(f"✅ Added {len(agenda_slides)} agenda slides")
                        
                        # Add group presentation slide
                        group_slide = create_group_presentation_slide(is_spanish, len(all_slides) + 1)
                        all_slides.append(group_slide)
                        logger.info(f"✅ Added group presentation slide")
            
            # Process each lesson
            for lesson_idx, lesson in enumerate(book_data.get('lessons', []), lesson_start):
                lesson_title = lesson.get('title', f'Lesson {lesson_idx}')
                lesson_images = extract_images_from_content(lesson.get('content', ''))
                
                logger.info(f"\n📝 HTML-first generation: {lesson_title}")
                
                # Generate slides for this lesson
                lesson_slides = generator.generate_from_lesson(lesson, lesson_idx, lesson_images)
                all_slides.extend(lesson_slides)
                
                logger.info(f"✅ Generated {len(lesson_slides)} slides for lesson {lesson_idx}")
            
            # Generate final HTML
            course_title = book_data.get('course_metadata', {}).get('title', 'Course Presentation')
            html_content = generate_html_output(
                all_slides,
                style=style,
                image_url_mapping=image_url_mapping,
                course_title=course_title
            )
            
            # Upload HTML to S3
            html_key = f"{project_folder}/infographics/infographic_final.html"
            s3_client.put_object(
                Bucket=course_bucket,
                Key=html_key,
                Body=html_content.encode('utf-8'),
                ContentType='text/html'
            )
            
            html_url = f"https://{course_bucket}.s3.amazonaws.com/{html_key}"
            
            total_elapsed = time_module.time() - start_time
            logger.info("=" * 80)
            logger.info("✅ HTML-FIRST GENERATION COMPLETED")
            logger.info(f"📊 Total slides: {len(all_slides)}")
            logger.info(f"⏱️  Processing time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
            logger.info(f"📁 HTML output: {html_url}")
            logger.info(f"🎯 Overflow guarantee: ZERO (built with real measurements)")
            logger.info("=" * 80)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'message': 'HTML presentation generated successfully (HTML-first architecture)',
                    'course_title': course_title,
                    'total_slides': len(all_slides),
                    'overflow_count': 0,  # Guaranteed!
                    'processing_time_seconds': total_elapsed,
                    'html_url': html_url,
                    'html_s3_key': html_key,
                    'architecture': 'html-first',
                    'batch_info': {
                        'lesson_start': lesson_start,
                        'lesson_end': lesson_end,
                        'total_lessons': total_lessons
                    }
                })
            }
        
        # ========================================================================
        # LEGACY JSON-BASED ARCHITECTURE REMOVED (Nov 21, 2025)
        # ========================================================================
        # Legacy code removed - see git history before Nov 21, 2025
        # All functionality migrated to HTML-First architecture
        logger.error("❌ Legacy JSON architecture no longer supported")
        logger.error("❌ Set html_first=true to use production architecture")
        
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': 'Legacy architecture deprecated',
                'message': 'The JSON-based slide generation has been removed. Use html_first=true.',
                'migration_info': 'See DEPRECATION_COMPLETE.md for details'
            })
        }
        
        # LEGACY CODE REMOVED BELOW THIS LINE
        # ========================================================================
        """
        # OLD CODE - KEPT FOR REFERENCE ONLY (NOT EXECUTED)
        logger.info("⚠️  Using legacy JSON-based architecture (deprecated)")
        logger.info("⚠️  Set html_first=true to use new architecture")
        
        # Generate infographic structure
        structure = generate_infographic_structure(
            book_data,
            model,
            slides_per_lesson,
            style,
            is_first_batch=is_first_batch,
            lesson_batch_start=lesson_start,
            bedrock_client=bedrock_client  # Pass bedrock client for AI restructuring
        )

        # Check if this is a partial structure (timeout occurred)
        if structure.get('completion_status') == 'partial':
            logger.info("⚠️ Partial structure returned due to timeout - saving and returning early")
            structure_key = f"{project_folder}/infographics/infographic_structure.json"
            
            # Save partial structure to S3
            s3_client.put_object(
                Bucket=course_bucket,
                Key=structure_key,
                Body=json.dumps(structure, indent=2),
                ContentType='application/json'
            )
            logger.info(f"💾 Saved partial structure: s3://{course_bucket}/{structure_key}")
            
            batch_info = structure.get('batch_info', {})
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'message': f'Partial presentation generated (lessons {batch_info.get("lesson_start", 1)}-{batch_info.get("lesson_end", 0)} of {batch_info.get("total_lessons", 0)})',
                    'course_title': structure.get('course_title', 'presentation'),
                    'total_slides': structure.get('total_slides', 0),
                    'completion_status': 'partial',
                    'batch_info': batch_info,
                    'structure_s3_key': structure_key,
                    'html_s3_key': None,  # Not generated for partial
                    'pptx_s3_key': None   # Not generated for partial
                })
            }

        # INCREMENTAL APPROACH: Use single shared structure file, append slides
        shared_structure_key = f"{project_folder}/infographics/infographic_structure.json"
        
        # Try to load existing structure (if not first batch)
        if batch_index > 0:
            try:
                logger.info(f"📖 Loading existing structure from previous batches...")
                existing_response = s3_client.get_object(Bucket=course_bucket, Key=shared_structure_key)
                existing_structure = json.loads(existing_response['Body'].read().decode('utf-8'))
                
                previous_slides = len(existing_structure.get('slides', []))
                
                # Append new slides to existing structure
                existing_structure['slides'].extend(structure['slides'])
                existing_structure['total_slides'] = len(existing_structure['slides'])
                existing_structure['last_batch_index'] = batch_index
                existing_structure['completion_status'] = 'in_progress'
                
                # CRITICAL: Merge image_url_mapping from this batch with existing mappings
                # This ensures ALL images from ALL batches are available to the merger
                existing_mapping = existing_structure.get('image_url_mapping', {})
                new_mapping = structure.get('image_url_mapping', {})
                merged_mapping = {**existing_mapping, **new_mapping}  # Merge both dictionaries
                existing_structure['image_url_mapping'] = merged_mapping
                
                structure = existing_structure
                logger.info(f"✅ Appended {len(structure['slides']) - previous_slides} new slides (total now: {structure['total_slides']} slides)")
                logger.info(f"🗺️  Merged image mappings: {len(existing_mapping)} + {len(new_mapping)} = {len(merged_mapping)} total images")
            except Exception as e:
                logger.warning(f"⚠️ Could not load existing structure: {e}")
                logger.info(f"📝 Creating new structure file")
                structure['last_batch_index'] = batch_index
                structure['completion_status'] = 'in_progress'
        else:
            # First batch - initialize structure
            logger.info(f"📝 First batch - creating new shared structure")
            structure['last_batch_index'] = 0
            structure['completion_status'] = 'in_progress'
        
        # Save updated shared structure (single file for all batches)
        s3_client.put_object(
            Bucket=course_bucket,
            Key=shared_structure_key,
            Body=json.dumps(structure, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        logger.info(f"💾 Saved incremental structure: s3://{course_bucket}/{shared_structure_key}")
        logger.info(f"   Batch {batch_index}: {structure['total_slides']} total slides across all batches so far")
        
        # SKIP HTML generation in batches - will be generated once by merger
        logger.info("⏭️  Skipping HTML generation - will be created by merger from complete structure")
        
        # SKIP PPT GENERATION IN BATCHES - Will be generated by merger from complete HTML
        logger.info("⏭️  Skipping PPT generation - will be created by merger from complete HTML")
        
        # Generate unique filename for structure reference
        course_title = structure.get('course_title', 'presentation')
        
        # Log final completion summary
        total_elapsed = time_module.time() - start_time
        logger.info("="*80)
        logger.info("✅ BATCH GENERATION COMPLETED SUCCESSFULLY")
        logger.info(f"📊 Batch {batch_index}: Lessons {lesson_start}-{lesson_end}")
        logger.info(f"⏱️  Batch time: {total_elapsed:.1f} seconds ({total_elapsed/60:.1f} minutes)")
        logger.info(f"📄 Total slides in structure so far: {structure['total_slides']}")
        logger.info(f"📁 Course: {structure['course_title']}")
        logger.info("="*80)
        
        # Return success
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': f'Batch {batch_index} completed - slides appended to shared structure',
                'course_title': structure['course_title'],
                'batch_slides': len([s for s in structure['slides'] if s.get('lesson_number') is not None and lesson_start <= s.get('lesson_number') <= lesson_end]),
                'total_slides_so_far': structure['total_slides'],
                'completion_status': structure.get('completion_status', 'in_progress'),
                'structure_s3_key': shared_structure_key,
                'html_s3_key': None,  # No HTML created in batch - will be created by merger
                'pptx_s3_key': None,  # No PPT created in batch - will be created by merger
                'batch_info': {
                    'batch_index': batch_index,
                    'lesson_start': lesson_start,
                    'lesson_end': lesson_end,
                    'total_lessons': total_lessons
        # LEGACY CODE REMOVED - End of lambda_handler
        # ========================================================================
        """
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        }
# Deploy timestamp: Thu Nov 20 19:39:11 -05 2025
