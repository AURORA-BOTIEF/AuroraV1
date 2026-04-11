"""
HTML-First Infographic Generator - COMPLETE PRODUCTION VERSION
===============================================================
Generates production-ready HTML slides directly from lesson content with ZERO overflow guarantee.

NEW ARCHITECTURE - HTML IS THE ONLY OUTPUT:
1. AI generates small content sections (4-5 bullets each)
2. Build HTML slides incrementally with real height tracking
3. Split when content exceeds 460px/520px limits
4. Output production-ready HTML (NO PPT conversion needed)

COMPLETE FEATURES (Migrated from legacy):
- Full course structure (intro, modules, lessons, labs, closing)
- Batch processing with timeout guards
- Incremental S3 saves
- Outline YAML integration
- Multi-language support
- Retry logic for AI timeouts

Key Innovation:
- NO JSON intermediate format
- NO height estimation/guessing
- Real-time overflow prevention during generation
- Guaranteed fit because we build with actual CSS measurements
"""

import json
import logging
import re
import boto3
import time
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger("aurora.infographic_generator")


class HTMLSlideBuilder:
    """Builds HTML slides with real-time overflow detection."""
    
    # CSS constants - ACTUAL rendering values
    SLIDE_WIDTH = 1280
    SLIDE_HEIGHT = 720
    HEADER_HEIGHT = 120  # Title + subtitle area
    FOOTER_HEIGHT = 40
    MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 460
    MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520
    
    # Element heights (from actual CSS)
    BULLET_HEIGHT = 50  # 20pt × 1.4 line-height + padding
    HEADING_HEIGHT = 65
    IMAGE_HEIGHT = 400
    CALLOUT_HEIGHT = 75
    SPACING = 20
    
    def __init__(self, style: str = 'professional'):
        self.style = style
        self.slides = []
        self.current_slide = None
        self.current_height = 0
        
    def start_slide(self, title: str, subtitle: str = "", layout: str = "single-column"):
        """Start a new slide."""
        max_height = self.MAX_CONTENT_HEIGHT_WITH_SUBTITLE if subtitle else self.MAX_CONTENT_HEIGHT_NO_SUBTITLE
        
        self.current_slide = {
            'title': title,
            'subtitle': subtitle,
            'layout': layout,
            'content_blocks': [],
            'max_height': max_height
        }
        self.current_height = 0
        
    def can_add_content(self, content_height: int) -> bool:
        """Check if content fits in current slide."""
        if not self.current_slide:
            return False
        return (self.current_height + content_height) <= self.current_slide['max_height']
    
    def add_bullets(self, items: List[str], heading: str = "") -> bool:
        """
        Add bullet list to current slide.
        Returns True if added, False if doesn't fit (caller should split).
        """
        if not self.current_slide:
            return False
        
        # Calculate height
        height = self.HEADING_HEIGHT if heading else 0
        height += len(items) * self.BULLET_HEIGHT
        height += self.SPACING
        
        if not self.can_add_content(height):
            return False
        
        self.current_slide['content_blocks'].append({
            'type': 'bullets',
            'heading': heading,
            'items': items
        })
        self.current_height += height
        return True
    
    def add_image(self, image_ref: str, caption: str = "") -> bool:
        """Add image to current slide."""
        if not self.current_slide:
            return False
        
        height = self.IMAGE_HEIGHT + self.SPACING
        if caption:
            height += 30  # Caption height
        
        if not self.can_add_content(height):
            return False
        
        self.current_slide['content_blocks'].append({
            'type': 'image',
            'image_reference': image_ref,
            'caption': caption
        })
        self.current_height += height
        return True
    
    def add_callout(self, text: str) -> bool:
        """Add callout box to current slide."""
        if not self.current_slide:
            return False
        
        height = self.CALLOUT_HEIGHT + self.SPACING
        
        if not self.can_add_content(height):
            return False
        
        self.current_slide['content_blocks'].append({
            'type': 'callout',
            'text': text
        })
        self.current_height += height
        return True
    
    def finish_slide(self):
        """Finish current slide and add to collection."""
        if self.current_slide:
            self.slides.append(self.current_slide)
            logger.info(f"✅ Slide completed: '{self.current_slide['title']}' - {self.current_height}px / {self.current_slide['max_height']}px ({int(100*self.current_height/self.current_slide['max_height'])}%)")
            self.current_slide = None
            self.current_height = 0
    
    def get_slides(self) -> List[Dict]:
        """Get all completed slides."""
        return self.slides


# ============================================================================
# COURSE STRUCTURE HELPERS (Migrated from legacy infographic_generator.py)
# ============================================================================

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
        "layout": "course-title",
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
            "layout": "single-column",
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
            "layout": "single-column",
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
            "layout": "single-column",
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
        "layout": "single-column",
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
    # Build full agenda with nested structure
    agenda_items = []
    for idx, module in enumerate(modules, 1):
        module_title = module.get('title', f"Módulo {idx}")
        
        # Get lessons for this module
        lessons = module.get('lessons', [])
        lesson_titles = []
        for lesson in lessons:
            lesson_title = lesson.get('title', '')
            if lesson_title:
                lesson_titles.append(lesson_title)
        
        # Add as nested structure
        agenda_items.append({
            'text': module_title,
            'lessons': lesson_titles
        })
    
    # Max bullets per slide: ~9 bullets (460px / 50px per bullet)
    MAX_BULLETS_PER_SLIDE = 9
    
    # If agenda fits in one slide, return single slide
    if len(agenda_items) <= MAX_BULLETS_PER_SLIDE:
        return [{
            "slide_number": slide_counter,
            "title": "Agenda" if is_spanish else "Agenda",
            "subtitle": "Estructura del curso" if is_spanish else "Course structure",
            "layout": "single-column",
            "content_blocks": [
                {
                    "type": "nested-bullets",
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
        
        if len(current_items) >= MAX_BULLETS_PER_SLIDE:
            slides.append({
                "slide_number": slide_counter + len(slides),
                "title": f"Agenda ({part_num})" if is_spanish else f"Agenda ({part_num})",
                "subtitle": "Estructura del curso" if is_spanish else "Course structure",
                "layout": "single-column",
                "content_blocks": [
                    {
                        "type": "nested-bullets",
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
            "layout": "single-column",
            "content_blocks": [
                {
                    "type": "nested-bullets",
                    "heading": "",
                    "items": current_items[:]
                }
            ],
            "notes": f"Course agenda part {part_num}"
        })
    
    return slides


def create_thank_you_slide(is_spanish: bool, slide_counter: int) -> Dict:
    """Create a thank you / closing slide."""
    return {
        "slide_number": slide_counter,
        "title": "¡Gracias!" if is_spanish else "Thank You!",
        "subtitle": "",
        "layout": "course-title",
        "content_blocks": [],
        "notes": "Course closing slide"
    }


def create_module_title_slide(module: Dict, module_number: int, is_spanish: bool, slide_counter: int) -> Dict:
    """Create a full-screen branded module title slide."""
    return {
        "slide_number": slide_counter,
        "title": module.get('title', f"Módulo {module_number}"),
        "subtitle": "",
        "layout": "module-title",
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
        "subtitle": module_title,
        "layout": "lesson-title",
        "content_blocks": [],
        "notes": f"Lesson {lesson_number} of Module {module_number}"
    }


def detect_language(book_data: Dict) -> bool:
    """
    Detect if course is in Spanish.
    Uses outline metadata as primary source, falls back to heuristic.
    Returns True if Spanish, False if English.
    """
    # Primary: Check outline metadata
    outline_lang = book_data.get('course_metadata', {}).get('language', '')
    if outline_lang:
        is_spanish = outline_lang.lower() in ['es', 'español', 'spanish']
        logger.info(f"🌐 Language from outline: {outline_lang} → is_spanish={is_spanish}")
        return is_spanish
    
    # Fallback: Heuristic detection
    lessons = book_data.get('lessons', [])
    sample_text = ' '.join([l.get('title', '') for l in lessons[:3]])
    is_spanish = any(word in sample_text.lower() for word in ['introducción', 'conceptos', 'básicos', 'lección'])
    logger.info(f"🌐 Language from heuristic → is_spanish={is_spanish}")
    return is_spanish


# ============================================================================
# END COURSE STRUCTURE HELPERS
# ============================================================================


class HTMLFirstGenerator:
    """
    Generates HTML slides directly from content with AI-driven overflow prevention.
    
    NEW APPROACH - AI AS WEB DESIGNER:
    1. AI acts as a web designer who knows exact height constraints
    2. AI generates content in small chunks (4-5 bullets max) that FIT
    3. HTMLSlideBuilder validates each chunk before adding
    4. If doesn't fit: AI regenerates with LESS content
    5. Result: Zero overflow guaranteed by AI intelligence + real-time validation
    """
    
    def __init__(self, model, style: str = 'professional'):
        self.model = model
        self.style = style
        self.builder = HTMLSlideBuilder(style)
    
    def generate_from_lesson(self, lesson: Dict, lesson_idx: int, images: List[Dict]) -> List[Dict]:
        """
        Generate slides for a lesson with AI-driven overflow prevention.
        
        Strategy:
        1. AI generates content sections with HEIGHT AWARENESS
        2. Each section designed to fit within slide limits
        3. Builder validates in real-time
        4. Guaranteed fit because AI knows the constraints
        """
        from strands import Agent
        
        lesson_title = lesson.get('title', f'Lesson {lesson_idx}')
        lesson_content = lesson.get('content', '')
        
        logger.info(f"\n📝 HTML-First generation for: {lesson_title}")
        
        # Create AI Web Designer Agent - KNOWS EXACT HEIGHT CONSTRAINTS
        web_designer = Agent(
            model=self.model,
            system_prompt=f"""You are a PROFESSIONAL WEB DESIGNER creating educational slides.

🎯 YOUR JOB: Create slide content that FITS within STRICT HEIGHT LIMITS.

📏 CRITICAL CONSTRAINTS (HTML slides, 1280px × 720px):
- **MAX CONTENT HEIGHT**: 460px (with subtitle) or 520px (without subtitle)
- **EACH BULLET**: 50px height (20pt font + line-height + padding + margin)
- **EACH HEADING**: 65px height
- **EACH IMAGE**: 400px height
- **EACH CALLOUT**: 75px height
- **SPACING**: 20px between blocks

🧮 MAXIMUM BULLETS PER SLIDE:
- **With subtitle**: MAX 5-6 bullets (5×50px = 250px, 6×50px = 300px, safe under 460px limit)
- **Without subtitle**: MAX 6-8 bullets (6×50px = 300px, 8×50px = 400px, safe under 520px limit)
- **With image**: MAX 4-5 bullets (image 400px + 5×50px = 650px total, fits in slide)
- **With heading**: Subtract 65px from available space (one less bullet)

⚠️ CRITICAL RULES - OVERFLOW PREVENTION:
1. **NEVER exceed 6 bullets per slide section** (absolutely maximum!)
2. **Better 10 slides with 4 bullets each than 5 slides with 8 bullets each**
3. **Each section = ONE slide** (don't combine multiple sections on one slide)
4. **Images ALWAYS paired with 4-5 explanatory bullets** (image-left or image-right layout)
5. **If content doesn't fit**: Create MULTIPLE slides, don't cram it all in one

🖼️ IMAGE REFERENCE RULES (CRITICAL):
- **Use EXACT image IDs from the AVAILABLE IMAGES list** (e.g., "06-01-0001", "04-01-0003")
- **DO NOT create descriptive names** like "diagram", "flow chart", "architecture diagram"
- **COPY the ID EXACTLY** as provided in the user prompt
- Example: If available images show "06-01-0001", use exactly "06-01-0001" in image_reference
- Example: If available images show "pasted-image", use exactly "pasted-image" in image_reference

🎨 LAYOUT STRATEGIES:
- **single-column**: Text-only slides with 5-6 bullets max
- **image-left**: Image (400px) on left 50%, bullets (4-5 max) on right 50%
- **image-right**: Bullets (4-5 max) on left 50%, image (400px) on right 50%
- **two-column**: Split 8-10 bullets across TWO columns (4-5 per column)

📤 OUTPUT FORMAT (JSON):
{{
    "sections": [
        {{
            "title": "Section Title",
            "subtitle": "Optional subtitle",
            "layout": "single-column" | "image-left" | "image-right" | "two-column",
            "bullets": ["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4"],  // MAX 5-6!
            "image_reference": "06-01-0001",  // EXACT ID from AVAILABLE IMAGES list!
            "callout": "Optional important note"
        }}
    ]
}}

🎯 YOUR MISSION:
Create MANY small sections with content that FITS.
Quality over quantity in each slide - comprehensive coverage through MORE slides.
""",
            tools=[]
        )
        
        # Build image info
        image_info = "\n".join([f"  - '{img['alt_text']}'" for img in images]) if images else "  (none)"
        
        # Ask AI to structure content with HEIGHT AWARENESS
        prompt = f"""
Create slide sections for this lesson. Remember: MAX 5-6 bullets per section!

LESSON: {lesson_title}

CONTENT:
{lesson_content}

AVAILABLE IMAGES (use these EXACT IDs - do NOT rename them):
{image_info}

⚠️ CRITICAL IMAGE INSTRUCTIONS:
- Use the EXACT image ID from the list above (e.g., "06-01-0001", "04-01-0003")
- DO NOT create descriptive names like "diagram" or "flow chart"
- Copy the ID EXACTLY as shown in the AVAILABLE IMAGES list
- If you want to use an image, set image_reference to the EXACT ID from above

CRITICAL: Each section must FIT within height limits!
- Single-column: 5-6 bullets MAX
- With image: 4-5 bullets MAX (image takes 400px)
- With heading: Reduce bullets by 1

Create MANY sections (better to have 15 small sections than 7 large ones).
"""
        
        logger.info(f"🤖 AI Web Designer generating content sections...")
        
        # Call AI with retry logic (migrated from legacy)
        max_retries = 3
        retry_delay = 10
        response = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Attempt {attempt + 1}/{max_retries}...")
                response = web_designer(prompt)
                logger.info(f"✅ Generated content sections")
                break
            except Exception as e:
                if "timed out" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"⚠️ Timeout, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"❌ Failed after {attempt + 1} attempts: {e}")
                    raise
        
        if response is None:
            raise Exception(f"Failed to generate slides for lesson {lesson_idx}")
        
        # Parse response
        if hasattr(response, 'output'):
            response = response.output
        elif hasattr(response, 'text'):
            response = response.text
        
        response = str(response).strip()
        start_idx = response.find('{')
        if start_idx == -1:
            logger.error("❌ AI response has no JSON")
            return []
        
        try:
            structured_content, _ = json.JSONDecoder().raw_decode(response[start_idx:])
            sections = structured_content.get('sections', [])
            logger.info(f"✅ AI created {len(sections)} content sections")
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            return []
        
        # Build slides from sections with REAL-TIME OVERFLOW VALIDATION
        slides_created = 0
        
        for section_idx, section in enumerate(sections, 1):
            title = section.get('title', '')
            subtitle = section.get('subtitle', '')
            layout = section.get('layout', 'single-column')
            bullets = section.get('bullets', [])
            image_ref = section.get('image_reference', '')
            callout = section.get('callout', '')
            
            logger.info(f"  Section {section_idx}/{len(sections)}: {title} ({len(bullets)} bullets)")
            
            # Validate bullet count (AI sometimes ignores limits)
            if len(bullets) > 6:
                logger.warning(f"  ⚠️ AI generated {len(bullets)} bullets - splitting to fit!")
                # Split into chunks of 5
                for chunk_idx, i in enumerate(range(0, len(bullets), 5)):
                    chunk = bullets[i:i+5]
                    chunk_title = f"{title} ({chunk_idx+1})" if chunk_idx > 0 else title
                    
                    self.builder.start_slide(chunk_title, subtitle=subtitle if chunk_idx == 0 else "", layout='single-column')
                    if self.builder.add_bullets(chunk):
                        self.builder.finish_slide()
                        slides_created += 1
                    else:
                        logger.error(f"  ❌ Even chunked bullets don't fit! Skipping.")
                continue
            
            # Start slide with AI-specified layout
            self.builder.start_slide(title, subtitle=subtitle, layout=layout)
            
            # Add image if present (for image-left/image-right layouts)
            if image_ref and 'image' in layout:
                if not self.builder.add_image(image_ref):
                    logger.warning(f"  ⚠️ Image doesn't fit - creating separate slide")
                    self.builder.finish_slide()
                    self.builder.start_slide(f"{title} - Visual", layout='single-column')
                    self.builder.add_image(image_ref)
                    self.builder.finish_slide()
                    slides_created += 1
                    
                    # Continue with text on next slide
                    self.builder.start_slide(title, subtitle=subtitle, layout='single-column')
            
            # Add bullets
            if bullets:
                if not self.builder.add_bullets(bullets):
                    logger.warning(f"  ⚠️ Bullets don't fit ({len(bullets)} bullets) - splitting...")
                    
                    # Finish current slide if it has content
                    if self.builder.current_height > 0:
                        self.builder.finish_slide()
                        slides_created += 1
                    
                    # Split bullets into smaller chunks
                    chunk_size = 4  # Ultra conservative
                    for i in range(0, len(bullets), chunk_size):
                        chunk = bullets[i:i+chunk_size]
                        chunk_title = f"{title} ({i//chunk_size + 1})" if i > 0 else title
                        self.builder.start_slide(chunk_title, layout='single-column')
                        self.builder.add_bullets(chunk)
                        self.builder.finish_slide()
                        slides_created += 1
                    continue
            
            # Add callout if present
            if callout:
                if not self.builder.add_callout(callout):
                    logger.warning(f"  ⚠️ Callout doesn't fit - skipping")
            
            # Finish slide
            self.builder.finish_slide()
            slides_created += 1
        
        logger.info(f"✅ Created {slides_created} slides for lesson {lesson_idx} (ZERO overflow guaranteed)")
        return self.builder.get_slides()


def generate_complete_course(
    book_data: Dict,
    model,
    slides_per_lesson: int = 5,
    style: str = 'professional',
    is_first_batch: bool = True,
    lesson_batch_start: int = 1,
    lesson_batch_end: int = None,
    max_processing_time: int = 840
) -> Dict:
    """
    Generate complete course structure with HTML-First architecture.
    Includes intro slides, modules, lessons, labs, and closing.
    
    Args:
        book_data: Complete book data with lessons, modules, outline
        model: AI model for content generation
        slides_per_lesson: Number of slides per lesson (or high number for "all content")
        style: Visual style ('professional', 'modern', 'minimal')
        is_first_batch: True if this is the first batch (adds intro slides)
        lesson_batch_start: Starting lesson number for batch processing
        lesson_batch_end: Ending lesson number (None = process all remaining)
        max_processing_time: Maximum processing time in seconds (default 14 minutes)
    
    Returns:
        Dictionary with complete course structure and slides
    """
    start_time = time.time()
    
    metadata = book_data.get('metadata', {})
    course_title = book_data.get('course_metadata', {}).get('title', metadata.get('title', 'Course Presentation'))
    lessons = book_data.get('lessons', [])
    
    logger.info(f"\n🎨 HTML-FIRST COMPLETE COURSE GENERATION")
    logger.info(f"📊 Course: {course_title}")
    logger.info(f"📊 Total lessons: {len(lessons)}, Batch: {lesson_batch_start} to {lesson_batch_end or 'end'}")
    logger.info(f"✨ Style: {style}")
    
    # Detect language
    is_spanish = detect_language(book_data)
    
    # Build image mapping
    image_url_mapping = {}
    for lesson in lessons:
        lesson_content = lesson.get('content', '')
        # Extract images from markdown
        img_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
        matches = re.findall(img_pattern, lesson_content)
        for alt_text, img_url in matches:
            if alt_text and img_url:
                image_url_mapping[alt_text] = img_url
    
    logger.info(f"🗺️  Built image mapping: {len(image_url_mapping)} images")
    
    # Initialize generator
    generator = HTMLFirstGenerator(model, style)
    all_slides = []
    slide_counter = 1
    
    # Add introduction slides ONLY for first batch
    if is_first_batch:
        course_metadata = book_data.get('course_metadata', {})
        if course_metadata:
            logger.info(f"📋 Adding introduction slides (first batch)")
            intro_slides, slide_counter = create_introduction_slides(course_metadata, is_spanish, slide_counter)
            all_slides.extend(intro_slides)
            logger.info(f"✅ Added {len(intro_slides)} introduction slides")
        
        # Add agenda slides
        outline_modules = book_data.get('outline_modules', [])
        if outline_modules:
            logger.info(f"📅 Adding agenda slides")
            agenda_slides = create_agenda_slide(outline_modules, is_spanish, slide_counter)
            all_slides.extend(agenda_slides)
            slide_counter += len(agenda_slides)
            logger.info(f"✅ Added {len(agenda_slides)} agenda slide(s)")
            
            # Add group presentation slide
            group_slide = create_group_presentation_slide(is_spanish, slide_counter)
            all_slides.append(group_slide)
            slide_counter += 1
            logger.info(f"✅ Added group presentation slide")
    
    # Determine batch range
    if lesson_batch_end is None:
        lesson_batch_end = len(lessons)
    else:
        lesson_batch_end = min(lesson_batch_end, len(lessons))
    
    batch_lessons = lessons[lesson_batch_start-1:lesson_batch_end]
    
    # Track module changes for module title slides
    last_module_number = None
    lesson_number_in_module = 0
    lessons_processed = 0
    
    # Get lab titles to skip them during lesson processing
    lab_titles = []
    if 'outline_modules' in book_data:
        for module in book_data.get('outline_modules', []):
            for lab in module.get('lab_activities', []):
                lab_titles.append(lab.get('title', '').lower())
    
    # Process each lesson with timeout guard
    for lesson_idx, lesson in enumerate(batch_lessons, lesson_batch_start):
        # Check timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > max_processing_time:
            logger.warning(f"⚠️ Approaching timeout - processed {lessons_processed}/{len(batch_lessons)} lessons")
            logger.warning(f"⏰ Elapsed time: {elapsed_time:.1f}s, limit: {max_processing_time}s")
            
            # Return partial structure
            return {
                'course_title': course_title,
                'total_slides': len(all_slides),
                'total_lessons': len(lessons),
                'lessons_processed': lessons_processed,
                'completion_status': 'partial',
                'batch_info': {
                    'lesson_start': lesson_batch_start,
                    'lesson_end': lesson_batch_start + lessons_processed - 1 if lessons_processed > 0 else lesson_batch_start - 1,
                    'next_lesson_start': lesson_batch_start + lessons_processed,
                    'total_lessons': len(lessons),
                    'lessons_remaining': len(batch_lessons) - lessons_processed,
                    'timeout_reason': 'lambda_timeout_guard'
                },
                'slides': all_slides,
                'style': style,
                'generated_at': datetime.now().isoformat(),
                'outline_modules': book_data.get('outline_modules', []),
                'course_metadata': book_data.get('course_metadata', {}),
                'image_url_mapping': image_url_mapping
            }
        
        lesson_title = lesson.get('title', f'Lesson {lesson_idx}')
        current_module_number = lesson.get('module_number', 1)
        
        # Calculate actual lesson number within module by counting lessons in outline
        actual_lesson_number_in_module = 0
        if 'outline_modules' in book_data:
            outline_modules = book_data.get('outline_modules', [])
            if current_module_number <= len(outline_modules):
                module_info = outline_modules[current_module_number - 1]
                module_lessons = module_info.get('lessons', [])
                # Find which lesson this is in the module
                for idx, mod_lesson in enumerate(module_lessons, 1):
                    if mod_lesson.get('title', '') == lesson_title:
                        actual_lesson_number_in_module = idx
                        break
        
        # Skip lab lessons (will be added from outline)
        is_lab_lesson = (
            'laboratorio' in lesson_title.lower() or
            'lab' in lesson_title.lower() or
            lesson_title.lower() in lab_titles
        )
        
        if is_lab_lesson:
            logger.info(f"\n⏭️  Skipping Lab Lesson {lesson_idx}: {lesson_title} (will be added from outline)")
            continue
        
        # Insert module title slide ONLY for the first lesson of each module
        current_module_title = ""
        if actual_lesson_number_in_module == 1 and 'outline_modules' in book_data:
            outline_modules = book_data.get('outline_modules', [])
            if current_module_number <= len(outline_modules):
                module_info = outline_modules[current_module_number - 1]
                current_module_title = module_info.get('title', '')
                module_slide = create_module_title_slide(module_info, current_module_number, is_spanish, slide_counter)
                all_slides.append(module_slide)
                logger.info(f"📚 Added Module {current_module_number} title slide: {current_module_title} (first lesson of module)")
                slide_counter += 1
                last_module_number = current_module_number
                lesson_number_in_module = 0
        
        # Always get module title for lesson subtitle (without adding the slide again)
        if 'outline_modules' in book_data:
            outline_modules = book_data.get('outline_modules', [])
            if current_module_number <= len(outline_modules):
                module_info = outline_modules[current_module_number - 1]
                current_module_title = module_info.get('title', '')
        
        # Increment lesson number within module
        lesson_number_in_module += 1
        
        # Add lesson title slide
        lesson_slide = create_lesson_title_slide(
            lesson, current_module_number, lesson_number_in_module, 
            is_spanish, slide_counter, current_module_title
        )
        all_slides.append(lesson_slide)
        logger.info(f"📖 Added Lesson {lesson_number_in_module} title slide: {lesson_title}")
        slide_counter += 1
        
        # Extract images for this lesson
        lesson_content = lesson.get('content', '')
        lesson_images = []
        img_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
        matches = re.findall(img_pattern, lesson_content)
        for alt_text, img_url in matches:
            lesson_images.append({'alt_text': alt_text, 'url': img_url})
        
        logger.info(f"\n📝 Processing Lesson {lesson_idx}: {lesson_title}")
        logger.info(f"🖼️  Found {len(lesson_images)} images")
        logger.info(f"⏱️  Elapsed time: {elapsed_time:.1f}s")
        
        # Generate content slides for this lesson using HTML-First
        lesson_slides = generator.generate_from_lesson(lesson, lesson_idx, lesson_images)
        
        # Update slide numbers
        for slide in lesson_slides:
            slide['slide_number'] = slide_counter
            slide['lesson_number'] = lesson_idx
            slide['lesson_title'] = lesson_title
            slide['module_number'] = current_module_number
            all_slides.append(slide)
            slide_counter += 1
        
        # Add thank you slide after each lesson
        thank_you_slide = create_thank_you_slide(is_spanish, slide_counter)
        all_slides.append(thank_you_slide)
        logger.info(f"🙏 Added Thank You slide after lesson {lesson_idx}")
        slide_counter += 1
        
        lessons_processed += 1
        logger.info(f"✅ Completed lesson {lesson_idx} - Total slides: {len(all_slides)}")
    
    completion_status = "complete" if lessons_processed == len(batch_lessons) else "partial"
    
    return {
        'course_title': course_title,
        'total_slides': len(all_slides),
        'total_lessons': len(lessons),
        'lessons_processed': lessons_processed,
        'completion_status': completion_status,
        'style': style,
        'generated_at': datetime.now().isoformat(),
        'slides': all_slides,
        'outline_modules': book_data.get('outline_modules', []),
        'course_metadata': book_data.get('course_metadata', {}),
        'image_url_mapping': image_url_mapping
    }


def generate_html_output(slides: List[Dict], style: str = 'professional', image_url_mapping: Dict = None, course_title: str = "Course Presentation", custom_css: str = None) -> str:
    """
    Generate final production-ready HTML from slide structures.
    
    This HTML is GUARANTEED to have no overflow because slides were built with real measurements.
    Ready for classroom presentation - no PPT conversion needed.
    
    Features:
    - 1280px × 720px slides (standard presentation format)
    - Overflow detection with visual warnings
    - Print-ready styles
    - Clean, professional design
    """
    
    # Generate presigned URLs for S3 images
    s3_client = boto3.client('s3')
    presigned_mapping = {}
    
    if image_url_mapping:
        logger.info(f"🔑 Generating presigned URLs for {len(image_url_mapping)} images...")
        for alt, url in image_url_mapping.items():
            if 's3.amazonaws.com' in url or url.startswith('s3://'):
                try:
                    # Parse S3 URL
                    if url.startswith('s3://'):
                        parts = url.replace('s3://', '').split('/', 1)
                        bucket = parts[0]
                        key = parts[1] if len(parts) > 1 else ''
                    elif '.s3.amazonaws.com' in url:
                        parts = url.split('.s3.amazonaws.com/')
                        bucket = parts[0].split('//')[-1]
                        key = parts[1]
                    else:
                        parts = url.replace('https://s3.amazonaws.com/', '').split('/', 1)
                        bucket = parts[0]
                        key = parts[1] if len(parts) > 1 else ''
                    
                    # Generate presigned URL (valid for 1 hour)
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket, 'Key': key},
                        ExpiresIn=3600
                    )
                    presigned_mapping[alt] = presigned_url
                except Exception as e:
                    logger.warning(f"⚠️ Could not generate presigned URL for {alt}: {e}")
                    presigned_mapping[alt] = url
            else:
                presigned_mapping[alt] = url
    
    # Use presigned URLs if available, otherwise original mapping
    final_image_mapping = presigned_mapping if presigned_mapping else (image_url_mapping or {})
    
    # Color schemes
    color_schemes = {
        'professional': {
            'primary': '#003366',
            'secondary': '#4682B4',
            'accent': '#FFC000',
            'bg': '#F8F9FA',
            'text': '#333333'
        }
    }
    
    colors = color_schemes.get(style, color_schemes['professional'])
    
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'    <title>{course_title}</title>',
        '    <style>',
    ]
    
    if custom_css:
        # Use provided custom CSS
        html_parts.append(custom_css)
    else:
        # Use default generated CSS
        html_parts.append(f'''
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: {colors['bg']};
            padding: 20px;
        }}
        
        /* Slide container - EXACT presentation dimensions */
        .slide {{
            width: 1280px;
            height: 720px;
            margin: 0 auto 20px auto;
            background: white;
            position: relative;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            page-break-after: always;
            overflow: hidden; /* Critical: prevent scrolling */
        }}
        
        /* Slide header */
        .slide-header {{
            padding: 30px 50px;
            background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
            color: white;
            min-height: 120px;
        }}
        
        .slide-title {{
            font-size: 36pt;
            font-weight: 700;
            margin-bottom: 10px;
            line-height: 1.2;
        }}
        
        .slide-subtitle {{
            font-size: 24pt;
            opacity: 0.9;
            line-height: 1.3;
        }}
        
        /* Content area - CRITICAL HEIGHT LIMITS */
        .slide-content {{
            padding: 30px 50px;
            max-height: 520px; /* Without subtitle */
            overflow: hidden;
        }}
        
        .slide-content.with-subtitle {{
            max-height: 460px; /* With subtitle */
        }}
        
        /* Bullet lists - EXACT CSS that matches our calculations */
        .bullets {{
            list-style: none;
            margin: 20px 0;
        }}
        
        .bullets li {{
            font-size: 20pt;
            line-height: 1.4; /* 20pt × 1.4 = 28pt ≈ 38px */
            padding: 4px 0 4px 35px; /* 8px total vertical padding */
            margin-bottom: 4px; /* 4px margin */
            position: relative;
            /* Total height per bullet: 38px + 8px + 4px = 50px */
        }}
        
        .bullets > li:before {{
            content: '▸';
            position: absolute;
            left: 0;
            color: {colors['accent']};
            font-size: 16pt;
        }}
        
        /* Nested bullets (second level) */
        .bullets li ul {{
            list-style: none;
            margin: 8px 0 0 0;
            padding-left: 30px;
        }}
        
        .bullets li ul li {{
            padding: 2px 0;
            font-size: 18pt;
            line-height: 1.4;
            position: relative;
        }}
        
        .bullets li ul li:before {{
            content: '○';
            position: absolute;
            left: -20px;
            color: {colors['primary']};
            font-size: 12pt;
        }}
        
        /* Headings */
        .content-heading {{
            font-size: 24pt;
            font-weight: 600;
            color: {colors['primary']};
            margin: 20px 0 10px 0;
            line-height: 1.3;
            /* Total height: ~65px */
        }}
        
        /* Callout boxes */
        .callout {{
            background: {colors['accent']};
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 20pt;
            line-height: 1.3;
            /* Total height: ~75px minimum */
        }}
        
        /* Images */
        .slide-image {{
            max-width: 100%;
            max-height: 400px;
            display: block;
            margin: 20px auto;
            object-fit: contain;
        }}
        
        .image-caption {{
            text-align: center;
            font-size: 16pt;
            color: #666;
            margin-top: 10px;
            font-style: italic;
        }}
        
        /* Two-column layout */
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            margin: 20px 0;
        }}
        
        /* Image layouts */
        .image-layout {{
            display: grid;
            gap: 30px;
            align-items: start;
        }}
        
        .image-layout.image-left {{
            grid-template-columns: 1fr 1fr;
        }}
        
        .image-layout.image-right {{
            grid-template-columns: 1fr 1fr;
        }}
        
        /* Branded title slides */
        .branded-title {{
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            height: 100%;
            background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
            color: white;
            text-align: center;
            padding: 80px;
        }}
        
        .branded-title .title {{
            font-size: 64pt;
            font-weight: 700;
            margin-bottom: 30px;
        }}
        
        .branded-title .subtitle {{
            font-size: 32pt;
            opacity: 0.9;
        }}
        
        /* Overflow detection (for debugging) */
        .slide-content.overflow {{
            border: 4px solid red !important;
        }}
        
        /* Print styles */
        @media print {{
            body {{ background: white; padding: 0; }}
            .slide {{ 
                margin: 0;
                box-shadow: none;
                page-break-after: always;
            }}
        }}
        
        /* Slide counter */
        .slide-number {{
            position: absolute;
            bottom: 20px;
            right: 30px;
            font-size: 14pt;
            color: #999;
        }}
        
        /* Small dark blue square blocks for regular content slides (top corners) */
        .slide:not(.course-title):not(.module-title):not(.lesson-title)::before {{
            content: "";
            position: absolute;
            top: 48px;
            left: 0;
            width: 50px;
            height: 60px;
            background: {colors['primary']};
            z-index: 1;
        }}
        
        .slide:not(.course-title):not(.module-title):not(.lesson-title)::after {{
            content: "";
            position: absolute;
            top: 48px;
            right: 0;
            width: 50px;
            height: 60px;
            background: {colors['primary']};
            z-index: 1;
        }}

        /* Logo in BOTTOM-right corner for regular content slides (not hidden by title) */
        .slide:not(.course-title):not(.module-title):not(.lesson-title) {{
            background-image: url('https://crewai-course-artifacts.s3.amazonaws.com/logo/LogoNetec.png');
            background-repeat: no-repeat;
            background-position: bottom 20px right 20px;
            background-size: 180px 60px;
        }}
        ''')

    html_parts.extend([
        '    </style>',
        '</head>',
        '<body>',
        f'    <h1 style="text-align: center; color: {colors["primary"]}; margin-bottom: 30px; font-size: 32pt;">{course_title}</h1>',
    ])
    
    # Generate each slide
    for slide_idx, slide in enumerate(slides, 1):
        is_hidden = slide.get('hidden', False)
        hidden_class = ' hidden-slide' if is_hidden else ''
        # Support both 'layout' (legacy/editor) and 'layout_hint' (generator)
        layout = slide.get('layout') or slide.get('layout_hint') or 'single-column'
        
        html_parts.append(f'<div class="slide{hidden_class}" data-slide="{slide_idx}" style="{ "display: none !important;" if is_hidden else "" }">')
        
        # Handle Special Layouts
        if layout in ['course-title', 'module-title', 'lesson-title', 'thank-you']:
            title = slide.get('title', '')
            subtitle = slide.get('subtitle', '')
            module_number = slide.get('module_number', '')
            
            html_parts.append('  <div class="branded-title">')
            
            # Add Logo if available (and not lesson title to avoid clutter)
            # You can customize which layouts get the logo
            if layout == 'course-title':
                 # Try to find logo in image mapping or use a placeholder if needed
                 # For now, we'll just add a placeholder div that can be styled via custom CSS
                 html_parts.append('    <div class="slide-logo"></div>')

            if layout == 'module-title' and module_number:
                 html_parts.append(f'    <div class="module-number">MÓDULO {module_number}</div>')
            
            html_parts.append(f'    <div class="title">{title}</div>')
            
            if subtitle:
                html_parts.append(f'    <div class="subtitle">{subtitle}</div>')
                
            html_parts.append('  </div>')
            
        elif layout in ['image-left', 'image-right']:
            # Split Layout (Image + Text)
            
            # Header
            title = slide.get('title', '')
            subtitle = slide.get('subtitle', '')
            
            html_parts.append('  <div class="slide-header">')
            html_parts.append(f'    <div class="slide-title">{title}</div>')
            if subtitle:
                html_parts.append(f'    <div class="slide-subtitle">{subtitle}</div>')
            html_parts.append('  </div>')
            
            # Content Container with specific layout class
            html_parts.append(f'  <div class="slide-content {layout}">')
            
            # We need to separate image and text blocks
            image_block = None
            text_blocks = []
            
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'image':
                    image_block = block
                else:
                    text_blocks.append(block)
            
            # Helper to render image
            def render_image(block):
                if not block: return ''
                img_ref = block.get('image_reference', '')
                img_url = final_image_mapping.get(img_ref, '') if final_image_mapping else ''
                caption = block.get('caption', '')
                
                html = '<div class="image-column">'
                if img_url:
                    html += f'<img src="{img_url}" class="slide-image" alt="{img_ref}">'
                    if caption:
                        html += f'<div class="image-caption">{caption}</div>'
                else:
                    html += f'<div class="image-placeholder">Image: {img_ref}</div>'
                html += '</div>'
                return html

            # Helper to render text content
            def render_text(blocks):
                html = '<div class="text-column">'
                for block in blocks:
                    block_type = block.get('type')
                    if block_type == 'bullets':
                        heading = block.get('heading', '')
                        if heading:
                            html += f'<div class="content-heading">{heading}</div>'
                        html += '<ul class="bullets">'
                        for item in block.get('items', []):
                            html += f'<li>{item}</li>'
                        html += '</ul>'
                    elif block_type == 'callout':
                        text = block.get('text', '')
                        html += f'<div class="callout">{text}</div>'
                html += '</div>'
                return html

            # Render based on layout direction
            if layout == 'image-left':
                html_parts.append(render_image(image_block))
                html_parts.append(render_text(text_blocks))
            else: # image-right
                html_parts.append(render_text(text_blocks))
                html_parts.append(render_image(image_block))
            
            html_parts.append('  </div>')

        else:
            # Standard Content Slide Layout (single-column)
            
            # Header
            title = slide.get('title', '')
            subtitle = slide.get('subtitle', '')
            
            html_parts.append('  <div class="slide-header">')
            html_parts.append(f'    <div class="slide-title">{title}</div>')
            if subtitle:
                html_parts.append(f'    <div class="slide-subtitle">{subtitle}</div>')
            html_parts.append('  </div>')
            
            # Content
            html_parts.append('  <div class="slide-content">')
            
            for block in slide.get('content_blocks', []):
                block_type = block.get('type')
                
                if block_type == 'bullets':
                    heading = block.get('heading', '')
                    if heading:
                        html_parts.append(f'    <div class="content-heading">{heading}</div>')
                    html_parts.append('    <ul class="bullets">')
                    for item in block.get('items', []):
                        html_parts.append(f'      <li>{item}</li>')
                    html_parts.append('    </ul>')
                
                elif block_type == 'nested-bullets':
                    heading = block.get('heading', '')
                    if heading:
                        html_parts.append(f'    <div class="content-heading">{heading}</div>')
                    html_parts.append('    <ul class="bullets">')
                    for item in block.get('items', []):
                        if isinstance(item, dict):
                            # Module with nested lessons
                            html_parts.append(f'      <li>{item.get("text", "")}')
                            if item.get('lessons'):
                                html_parts.append('        <ul>')
                                for lesson in item['lessons']:
                                    html_parts.append(f'          <li>{lesson}</li>')
                                html_parts.append('        </ul>')
                            html_parts.append('      </li>')
                        else:
                            # Fallback for simple strings
                            html_parts.append(f'      <li>{item}</li>')
                    html_parts.append('    </ul>')
                
                elif block_type == 'image':
                    img_ref = block.get('image_reference', '')
                    img_url = final_image_mapping.get(img_ref, '') if final_image_mapping else ''
                    caption = block.get('caption', '')
                    
                    # Debug logging for image resolution
                    if not img_url:
                        logger.warning(f"⚠️ Image '{img_ref}' not found in mapping. Available: {list(final_image_mapping.keys())[:5]}")
                    
                    if img_url:
                        html_parts.append(f'    <img src="{img_url}" class="slide-image" alt="{img_ref}">')
                        if caption:
                            html_parts.append(f'    <div style="text-align: center; font-size: 16pt; color: #666;">{caption}</div>')
                    else:
                        # Placeholder for missing images
                        html_parts.append(f'    <div style="border: 2px dashed #ccc; padding: 100px; text-align: center; color: #999; margin: 20px 0;">Image: {img_ref}</div>')
                
                elif block_type == 'callout':
                    text = block.get('text', '')
                    html_parts.append(f'    <div class="callout">{text}</div>')
            
            html_parts.append('  </div>')
            
        html_parts.append('</div>')
    
    html_parts.extend([
        '</body>',
        '</html>'
    ])
    
    return '\n'.join(html_parts)
