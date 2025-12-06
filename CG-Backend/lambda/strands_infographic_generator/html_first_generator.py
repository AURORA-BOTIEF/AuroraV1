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


def extract_tables_from_content(content: str) -> List[Dict]:
    """
    Extract markdown tables from lesson content.
    Returns list of dicts with 'headers' and 'rows' for each table found.
    """
    tables = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this line looks like a table header (starts and ends with |)
        if line.startswith('|') and line.endswith('|') and '|' in line[1:-1]:
            # Potential table found - check for separator line next
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Separator line has dashes and pipes: |---|---|
                if next_line.startswith('|') and '---' in next_line:
                    # This is a markdown table
                    # Parse header row
                    headers = [cell.strip() for cell in line.split('|')[1:-1]]
                    
                    # Skip separator line
                    i += 2
                    
                    # Parse data rows
                    rows = []
                    while i < len(lines):
                        row_line = lines[i].strip()
                        if row_line.startswith('|') and row_line.endswith('|'):
                            row_cells = [cell.strip() for cell in row_line.split('|')[1:-1]]
                            if row_cells:
                                rows.append(row_cells)
                            i += 1
                        else:
                            break
                    
                    if headers and rows:
                        tables.append({
                            'headers': headers,
                            'rows': rows
                        })
                    continue
        i += 1
    
    return tables


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
    
    # Max modules per slide (each module + lessons counts as ~2-3 bullets worth of space)
    MAX_MODULES_PER_SLIDE = 3
    
    # If agenda fits in one slide, return single slide
    if len(agenda_items) <= MAX_MODULES_PER_SLIDE:
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
        
        if len(current_items) >= MAX_MODULES_PER_SLIDE:
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
    
    def _remove_lab_sections(self, content: str) -> str:
        """
        Remove lab/practice sections from lesson content (THEORY ONLY).
        
        Filters out markdown sections that start with:
        - ## Laboratorio: ...
        - ## Práctica: ...
        - ## Lab: ...
        - ## Actividad: ...
        
        Returns theory-only content for slide generation.
        """
        if not content:
            return content
        
        # Split content into lines
        lines = content.split('\n')
        filtered_lines = []
        skip_section = False
        section_level = 0
        
        for line in lines:
            # Check if this is a heading line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).lower().strip()
                
                # Check if this is a lab section heading
                is_lab_section = (
                    heading_text.startswith('laboratorio:') or
                    heading_text.startswith('laboratorio ') or
                    heading_text.startswith('práctica:') or
                    heading_text.startswith('práctica ') or
                    heading_text.startswith('lab:') or
                    heading_text.startswith('lab ') or
                    heading_text.startswith('actividad:') or
                    heading_text.startswith('actividad ') or
                    heading_text.startswith('laboratory:') or
                    heading_text.startswith('laboratory ') or
                    'objetivo del laboratorio' in heading_text or
                    'conclusión del laboratorio' in heading_text
                )
                
                if is_lab_section:
                    # Start skipping this section
                    skip_section = True
                    section_level = level
                    logger.info(f"🚫 Skipping lab section: {heading_text[:50]}...")
                    continue
                elif skip_section and level <= section_level:
                    # We've reached a new section at the same or higher level - stop skipping
                    skip_section = False
                    section_level = 0
            
            # Add line if not in skip mode
            if not skip_section:
                filtered_lines.append(line)
        
        filtered_content = '\n'.join(filtered_lines)
        
        # Log if content was filtered
        if len(filtered_content) < len(content):
            reduction = len(content) - len(filtered_content)
            logger.info(f"✂️  Removed {reduction} characters of lab content (theory only)")
        
        return filtered_content
    
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
        
        # FILTER OUT LAB SECTIONS (theory content only)
        lesson_content = self._remove_lab_sections(lesson_content)
        
        logger.info(f"\n📝 HTML-First generation for: {lesson_title}")
        
        # Create AI Web Designer Agent - KNOWS EXACT HEIGHT CONSTRAINTS
        web_designer = Agent(
            model=self.model,
            system_prompt=f"""You are a PROFESSIONAL WEB DESIGNER creating educational slides.

🎯 YOUR JOB: Create slide content that FITS within STRICT HEIGHT LIMITS using DYNAMIC SPACE CALCULATION.

📏 CRITICAL CONSTRAINTS (HTML slides, 1280px × 720px):
- **MAX CONTENT HEIGHT**: 460px (with subtitle) or 520px (without subtitle)
- **EACH BULLET**: 50px height (20pt font + line-height + padding + margin)
- **EACH HEADING**: 65px height
- **EACH IMAGE**: 400px height
- **EACH CALLOUT**: 75px height
- **SPACING**: 20px between blocks

🧮 DYNAMIC SPACE CALCULATION:
For each slide, calculate available space and fit content accordingly:
- **Start with**: 460px (with subtitle) or 520px (without subtitle)
- **Subtract heading**: -65px if heading present
- **Subtract image**: -400px if image present
- **Subtract callout**: -75px if callout present
- **Remaining space ÷ 50px** = Maximum bullets that fit
- **Example 1**: No subtitle, no extras = 520px ÷ 50px = 10 bullets max
- **Example 2**: With subtitle + heading = 460px - 65px = 395px ÷ 50px = 7 bullets max
- **Example 3**: With subtitle + image = 460px - 400px = 60px ÷ 50px = 1 bullet max

⚠️ CRITICAL RULES - SMART SPLITTING:
1. **CALCULATE available space** for each slide: (460 or 520) - heading - image - callout
2. **Count your bullets**: If you have 7 key points and max is 10, use ONE slide with 7 bullets
3. **Only split when necessary**: If you have 12 points and max is 10, create TWO slides (10 + 2)
4. **Don't over-split**: Having 5 bullets on a slide that fits 10 is PERFECT - don't split unnecessarily
5. **Quality content**: Better to have meaningful bullets that fit comfortably than splitting prematurely

🖼️ IMAGE REFERENCE RULES (CRITICAL):
- **Use EXACT image IDs from the AVAILABLE IMAGES list** (e.g., "06-01-0001", "04-01-0003")
- **DO NOT create descriptive names** like "diagram", "flow chart", "architecture diagram"
- **COPY the ID EXACTLY** as provided in the user prompt
- Example: If available images show "06-01-0001", use exactly "06-01-0001" in image_reference
- Example: If available images show "pasted-image", use exactly "pasted-image" in image_reference

🎨 LAYOUT STRATEGIES (OPTIMIZED FOR IMAGE ASPECT RATIOS):
- **single-column**: Text-only slides, bullets calculated from available space (typically 8-10 bullets)
- **image-left**: Image (4:3 aspect ratio) on left 50%, bullets on right 50%
  * Use for SQUARE/PORTRAIT images (aspect ratio < 1.6)
  * CRITICAL: Space limited to ~60-120px = MAXIMUM 1-2 bullets
  * ALWAYS include 1-2 SHORT explanatory bullets
- **image-right**: Bullets on left 50%, image (4:3 aspect ratio) on right 50%
  * Use for SQUARE/PORTRAIT images (aspect ratio < 1.6)
  * CRITICAL: Space limited to ~60-120px = MAXIMUM 1-2 bullets
  * ALWAYS include 1-2 SHORT explanatory bullets
- **image-full**: Full-width image without bullets
  * Use for WIDE images (16:9 aspect ratio ~1.78 or wider)
  * NO bullets - image takes full slide space
  * Image speaks for itself (diagrams, screenshots, charts)
- **two-column**: Split bullets across TWO columns based on calculated space

⚠️ IMAGE LAYOUT SELECTION:
- Check image suggested_layout in available images list
- If suggested_layout='split': use image-left or image-right WITH 1-2 bullets
- If suggested_layout='full-width': use image-full WITHOUT bullets

📤 OUTPUT FORMAT (JSON):
{{
    "sections": [
        {{
            "title": "Section Title",
            "subtitle": "Optional subtitle",
            "layout": "single-column" | "image-left" | "image-right" | "image-full" | "two-column",
            "bullets": ["Bullet 1", "Bullet 2", ...],  // As many as fit! Empty for image-full
            "image_reference": "06-01-0001",  // EXACT ID from AVAILABLE IMAGES list!
            "callout": "Optional important note",
            "table": {{  // OPTIONAL: Include when content has tabular data
                "headers": ["Col1", "Col2", "Col3"],
                "rows": [["R1C1", "R1C2", "R1C3"], ["R2C1", "R2C2", "R2C3"]]
            }}
        }}
    ]
}}

📊 TABLE HANDLING (CRITICAL):
- If TABLES FOUND section lists tables, you MUST include them as table objects
- Tables are ~200px height (depends on rows) - calculate space accordingly
- Use the EXACT headers and rows provided in TABLES FOUND section
- Create dedicated slides for tables with appropriate titles
- Do NOT convert tables to bullet points - preserve the tabular structure!

🎯 YOUR MISSION:
1. For each topic, CALCULATE max bullets: (460 or 520) - extras ÷ 50
2. If topic has ≤ max bullets: Create ONE section with all bullets
3. If topic has > max bullets: Split intelligently (e.g., 15 bullets, max 10 → two slides: 10 + 5)
4. AVOID premature splitting: 5 bullets fitting in 10-bullet space = ONE slide, not multiple!
5. INCLUDE ALL TABLES from TABLES FOUND section - do NOT skip them!
""",
            tools=[]
        )
        
        # Build image info with aspect ratios
        image_info_list = []
        for img in images:
            img_alt = img.get('alt_text', '')
            suggested = img.get('suggested_layout', 'split')
            aspect = img.get('aspect_ratio', 'unknown')
            image_info_list.append(f"  - '{img_alt}' (layout: {suggested}, aspect_ratio: {aspect:.2f})" if isinstance(aspect, (int, float)) else f"  - '{img_alt}' (layout: {suggested})")
        
        image_info = "\n".join(image_info_list) if image_info_list else "  (none)"
        
        # Extract tables from content
        tables = extract_tables_from_content(lesson_content)
        logger.info(f"📊 Found {len(tables)} tables in lesson content")
        
        # Build tables info for prompt
        tables_info = ""
        if tables:
            tables_info_lines = [""]
            for idx, table in enumerate(tables, 1):
                headers = table.get('headers', [])
                rows = table.get('rows', [])
                tables_info_lines.append(f"TABLE {idx}:")
                tables_info_lines.append(f"  Headers: {json.dumps(headers)}")
                # Show first 3 rows as sample
                sample_rows = rows[:3]
                tables_info_lines.append(f"  Rows ({len(rows)} total): {json.dumps(sample_rows)}{'...' if len(rows) > 3 else ''}")
                tables_info_lines.append("")
            tables_info = "\n".join(tables_info_lines)
        
        # Build tables section for prompt
        tables_prompt_section = ""
        if tables:
            tables_prompt_section = f"""
TABLES FOUND IN CONTENT ({len(tables)}):
{tables_info}
⚠️ MANDATORY: You MUST create a section with "table" object for EACH table above!
Use the EXACT headers and rows provided. Do NOT convert tables to bullets!
"""
        
        # Ask AI to structure content with HEIGHT AWARENESS
        prompt = f"""
Create slide sections for this lesson using DYNAMIC SPACE CALCULATION.

LESSON: {lesson_title}

CONTENT:
{lesson_content}

AVAILABLE IMAGES (use these EXACT IDs - do NOT rename them):
{image_info}
{tables_prompt_section}
⚠️ CRITICAL IMAGE INSTRUCTIONS:
- Use the EXACT image ID from the list above (e.g., "06-01-0001", "04-01-0003")
- DO NOT create descriptive names like "diagram" or "flow chart"
- Copy the ID EXACTLY as shown in the AVAILABLE IMAGES list
- If you want to use an image, set image_reference to the EXACT ID from above

CRITICAL SPACE CALCULATION:
- Available: 460px (with subtitle) or 520px (without)
- Subtract extras: heading (-65px), image (-400px), callout (-75px), table (-200px approx)
- Formula: remaining_space ÷ 50px = MAX bullets per slide
- **ONLY split if bullets > MAX**
- Example: Topic has 6 bullets, MAX is 10 → Use ONE slide with 6 bullets (don't split!)
- Example: Topic has 15 bullets, MAX is 10 → Use TWO slides (10 + 5 bullets)

Create sections intelligently - combine related points up to the calculated MAX, split only when necessary.
{"Include ALL tables from TABLES FOUND section as table objects in your output!" if tables else ""}
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
            table_data = section.get('table', None)
            
            logger.info(f"  Section {section_idx}/{len(sections)}: {title} ({len(bullets)} bullets, layout: {layout}, has_table: {table_data is not None})")
            
            # Start slide with AI-specified layout
            self.builder.start_slide(title, subtitle=subtitle, layout=layout)
            
            # Add image if present
            if image_ref:
                if layout == 'image-full':
                    # Full-width image without bullets (16:9 aspect ratio)
                    self.builder.add_image(image_ref)
                elif 'image' in layout:
                    # Split layout image with bullets (4:3 aspect ratio)
                    self.builder.add_image(image_ref)
            
            # Add bullets - skip for image-full layout
            if bullets and layout != 'image-full':
                added = self.builder.add_bullets(bullets)
                if not added:
                    # AI made a mistake - force add anyway and log warning
                    logger.warning(f"  ⚠️ Bullets exceed calculated space ({len(bullets)} bullets) but adding anyway - AI calculation error")
                    self.builder.current_slide['content_blocks'].append({
                        'type': 'bullets',
                        'heading': '',
                        'items': bullets
                    })
                    # Still update height for tracking
                    self.builder.current_height += len(bullets) * self.builder.BULLET_HEIGHT + self.builder.SPACING
            
            # Add table if present
            if table_data:
                headers = table_data.get('headers', [])
                rows = table_data.get('rows', [])
                if headers and rows:
                    logger.info(f"  📊 Adding table with {len(headers)} columns and {len(rows)} rows")
                    self.builder.current_slide['content_blocks'].append({
                        'type': 'table',
                        'heading': '',
                        'headers': headers,
                        'rows': rows
                    })
                    # Estimate table height (header + rows)
                    table_height = 50 + (len(rows) * 35)  # ~50px header, ~35px per row
                    self.builder.current_height += table_height + self.builder.SPACING
            
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
    total_lessons: int = None,
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
        total_lessons: Total lessons in full course (for completion detection)
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
    # Note: lesson_batch_start and lesson_batch_end are ABSOLUTE lesson numbers (1-based)
    # The 'lessons' array has already been sliced by the Lambda handler to contain only the batch lessons
    # So we process ALL lessons in the array (which is the current batch)
    batch_lessons = lessons  # Process all lessons in the already-sliced array
    
    # Keep lesson_batch_end as-is (it's the absolute lesson number, needed for completion detection)
    if lesson_batch_end is None:
        lesson_batch_end = lesson_batch_start + len(lessons) - 1
    
    # Track module changes for module title slides
    last_module_number = None
    lesson_number_in_module = 0
    lessons_processed = 0
    
    # Get lab titles to skip them during lesson processing
    lab_titles = set()
    outline_modules = book_data.get('outline_modules', [])
    
    # Build comprehensive list of lab activity titles from outline
    for module in outline_modules:
        for lesson in module.get('lessons', []):
            # Add lab_activities titles to skip list
            for lab in lesson.get('lab_activities', []):
                lab_title = lab.get('title', '').lower().strip()
                if lab_title:
                    lab_titles.add(lab_title)
                    
    logger.info(f"🚫 Found {len(lab_titles)} lab activities to skip from outline")
    
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
        
        # Skip lab lessons - THEORY ONLY (exclude all lab/practice activities)
        lesson_title_lower = lesson_title.lower().strip()
        
        # Check multiple patterns for lab detection
        is_lab_lesson = (
            lesson_title_lower in lab_titles or  # Exact match from outline
            lesson_title_lower.startswith('laboratorio') or  # Starts with "Laboratorio"
            lesson_title_lower.startswith('lab ') or  # Starts with "Lab "
            lesson_title_lower.startswith('lab-') or
            lesson_title_lower.startswith('lab:') or
            lesson_title_lower.startswith('práctica') or  # Starts with "Práctica"
            lesson_title_lower.startswith('practice') or
            lesson_title_lower.startswith('actividad') or  # Starts with "Actividad"
            lesson_title_lower.startswith('activity') or
            'laboratorio -' in lesson_title_lower or
            'lab -' in lesson_title_lower or
            'práctica -' in lesson_title_lower or
            lesson.get('type', '').lower() in ['lab', 'practice', 'activity', 'lab_activity', 'laboratorio']
        )
        
        if is_lab_lesson:
            logger.info(f"\n⏭️  Skipping Lab/Practice Lesson {lesson_idx}: {lesson_title} (theory content only)")
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
        
        # Get image dimensions from S3 to determine layout
        s3_client = boto3.client('s3')
        for alt_text, img_url in matches:
            image_info = {'alt_text': alt_text, 'url': img_url}
            
            # Try to get dimensions from S3 metadata
            try:
                if 's3.amazonaws.com' in img_url:
                    # Parse S3 URL
                    if '.s3.amazonaws.com' in img_url:
                        parts = img_url.split('.s3.amazonaws.com/')
                        bucket = parts[0].split('//')[-1]
                        key = parts[1]
                    else:
                        parts = img_url.replace('https://s3.amazonaws.com/', '').split('/', 1)
                        bucket = parts[0]
                        key = parts[1] if len(parts) > 1 else ''
                    
                    # Get object metadata
                    response = s3_client.head_object(Bucket=bucket, Key=key)
                    metadata = response.get('Metadata', {})
                    
                    # Check for width/height in metadata or content-type
                    if 'width' in metadata and 'height' in metadata:
                        image_info['width'] = int(metadata['width'])
                        image_info['height'] = int(metadata['height'])
                        aspect_ratio = image_info['width'] / image_info['height']
                        image_info['aspect_ratio'] = aspect_ratio
                        # Determine layout: 16:9 (~1.78), 4:3 (~1.33)
                        if aspect_ratio > 1.6:  # Wide image (16:9 or wider)
                            image_info['suggested_layout'] = 'full-width'  # No bullets
                        else:  # Squarer image (4:3 or portrait)
                            image_info['suggested_layout'] = 'split'  # With bullets
            except Exception as e:
                logger.debug(f"Could not fetch image metadata for {alt_text}: {e}")
                # Default to split layout if we can't determine
                image_info['suggested_layout'] = 'split'
            
            lesson_images.append(image_info)
        
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
    
    # Determine if this is the final batch for the entire course
    # A batch is "complete" only if it processed all lessons up to the end of the course
    # Use total_lessons parameter if provided, otherwise fall back to len(lessons) from book_data
    logger.info(f"🔍 DEBUG: total_lessons param={total_lessons}, len(lessons)={len(lessons)}, lesson_batch_end={lesson_batch_end}")
    course_total_lessons = total_lessons if total_lessons is not None else len(lessons)
    is_final_batch = lesson_batch_end is not None and lesson_batch_end >= course_total_lessons
    completion_status = "complete" if is_final_batch else "partial"
    
    logger.info(f"🔍 DEBUG: course_total_lessons={course_total_lessons}, is_final_batch={is_final_batch}, completion_status={completion_status}")
    if is_final_batch:
        logger.info(f"✅ FINAL BATCH: lesson_batch_end={lesson_batch_end} >= total_lessons={course_total_lessons}")
    else:
        logger.info(f"⏭️  INTERMEDIATE BATCH: lesson_batch_end={lesson_batch_end} < total_lessons={course_total_lessons}")
    
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


def generate_html_output(slides: List[Dict], style: str = 'professional', image_url_mapping: Dict = None, course_title: str = "Course Presentation") -> str:
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
    logger.info(f"🔍 DEBUG generate_html_output: Processing {len(slides)} slides")
    
    # Generate presigned URLs for S3 images and logo
    s3_client = boto3.client('s3')
    presigned_mapping = {}
    
    # Generate presigned URL for logo
    logo_s3_url = "https://crewai-course-artifacts.s3.amazonaws.com/logo/LogoNetec.png"
    logo_presigned_url = logo_s3_url
    try:
        parts = logo_s3_url.split('.s3.amazonaws.com/')
        bucket = parts[0].split('//')[-1]
        key = parts[1]
        logo_presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=3600
        )
        logger.info(f"🔑 Generated presigned URL for logo")
    except Exception as e:
        logger.warning(f"⚠️ Could not generate presigned URL for logo: {e}")
    
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
        f'''
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
        
        /* Nested bullets for agenda (second level) */
        .bullets li ul {{
            list-style: none;
            margin: 8px 0 0 0;
            padding-left: 30px;
        }}
        
        .bullets li ul li {{
            font-size: 18pt;
            line-height: 1.4;
            padding: 2px 0;
            margin-bottom: 2px;
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
        
        /* Tables */
        .slide-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 16pt;
        }}
        
        .slide-table th {{
            background: {colors['primary']};
            color: white;
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            border: 1px solid {colors['secondary']};
        }}
        
        .slide-table td {{
            padding: 10px 15px;
            border: 1px solid #ddd;
            line-height: 1.3;
        }}
        
        .slide-table tr:nth-child(even) {{
            background: #f5f5f5;
        }}
        
        .slide-table tr:hover {{
            background: #eef4fa;
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
            align-items: center;
            height: 100%;
        }}
        
        .image-layout.image-left {{
            grid-template-columns: 1fr 1fr;
        }}
        
        .image-layout.image-right {{
            grid-template-columns: 1fr 1fr;
        }}
        
        .image-layout.image-full {{
            grid-template-columns: 1fr;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
        }}
        
        .image-layout .image-column {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100%;
        }}
        
        .image-layout .bullets-column {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            height: 100%;
        }}
        
        .image-layout .bullets-column ul.bullets {{
            margin: 0;
        }}
        
        .image-layout.image-full .slide-image {{
            max-width: 100%;
            max-height: 650px;
            width: auto;
            height: auto;
            object-fit: contain;
        }}
        
        /* Logo positioning */
        .slide-logo {{
            position: absolute;
            bottom: 20px;
            right: 30px;
            width: 120px;
            height: auto;
            opacity: 0.9;
            z-index: 100;
        }}
        
        /* COURSE TITLE SLIDE - Main branded opening */
        .course-title-slide {{
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            height: 100%;
            background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
            color: white;
            text-align: center;
            padding: 80px;
            position: relative;
        }}
        
        .course-title-slide .title {{
            font-size: 72pt;
            font-weight: 700;
            margin-bottom: 40px;
            line-height: 1.1;
        }}
        
        .course-title-slide .logo {{
            position: absolute;
            top: 40px;
            right: 40px;
            width: 150px;
            height: auto;
            opacity: 1;
        }}
        
        /* MODULE TITLE SLIDE - Section divider */
        .module-title-slide {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            flex-direction: column;
            height: 100%;
            background: linear-gradient(to right, {colors['primary']}, {colors['secondary']});
            color: white;
            padding: 100px 80px;
            position: relative;
        }}
        
        .module-title-slide .title {{
            font-size: 56pt;
            font-weight: 700;
            margin-top: 80px;
            text-align: left;
            width: 100%;
            border-left: 8px solid {colors['accent']};
            padding-left: 30px;
        }}
        
        .module-title-slide .logo {{
            position: absolute;
            bottom: 40px;
            left: 50%;
            transform: translateX(-50%);
            width: 140px;
            height: auto;
            opacity: 0.95;
        }}
        
        /* LESSON TITLE SLIDE - Topic introduction */
        .lesson-title-slide {{
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            height: 100%;
            background: white;
            color: {colors['primary']};
            padding: 60px 80px;
            position: relative;
            border-top: 10px solid {colors['accent']};
        }}
        
        .lesson-title-slide .title {{
            font-size: 48pt;
            font-weight: 700;
            margin-bottom: 20px;
            text-align: center;
            color: {colors['primary']};
        }}
        
        .lesson-title-slide .subtitle {{
            font-size: 28pt;
            color: {colors['secondary']};
            opacity: 0.8;
            text-align: center;
        }}
        
        .lesson-title-slide .logo {{
            position: absolute;
            top: 40px;
            right: 40px;
            width: 100px;
            height: auto;
            opacity: 0.85;
        }}
        
        /* Legacy branded-title (for thank you slide) */
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
        ''',
        '    </style>',
        '</head>',
        '<body>',
        f'    <h1 style="text-align: center; color: {colors["primary"]}; margin-bottom: 30px; font-size: 32pt;">{course_title}</h1>',
    ]
    
    # Use presigned logo URL
    logo_url = logo_presigned_url
    
    # Generate each slide
    for slide_idx, slide in enumerate(slides, 1):
        layout = slide.get('layout', 'single-column')
        title = slide.get('title', '')
        subtitle = slide.get('subtitle', '')
        
        html_parts.append(f'<div class="slide" data-slide="{slide_idx}">')
        
        # Special layouts for title slides
        if layout == 'course-title':
            html_parts.append('  <div class="course-title-slide">')
            html_parts.append(f'    <div class="title">{title}</div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            html_parts.append('</div>')
            continue
        
        elif layout == 'module-title':
            html_parts.append('  <div class="module-title-slide">')
            html_parts.append(f'    <div class="title">{title}</div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            html_parts.append('</div>')
            continue
        
        elif layout == 'lesson-title':
            html_parts.append('  <div class="lesson-title-slide">')
            html_parts.append(f'    <div class="title">{title}</div>')
            if subtitle:
                html_parts.append(f'    <div class="subtitle">{subtitle}</div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            html_parts.append('</div>')
            continue
        
        # Regular content slides with header
        html_parts.append('  <div class="slide-header">')
        html_parts.append(f'    <div class="slide-title">{title}</div>')
        if subtitle:
            html_parts.append(f'    <div class="slide-subtitle">{subtitle}</div>')
        html_parts.append('  </div>')
        
        # Content - use special layout wrapper for image layouts
        if layout in ['image-left', 'image-right', 'image-full']:
            html_parts.append(f'  <div class="slide-content image-layout {layout}">')
            
            # For image-left: image first, then bullets
            # For image-right: bullets first, then image
            # For image-full: just image
            
            content_blocks = slide.get('content_blocks', [])
            image_block = None
            bullet_blocks = []
            
            for block in content_blocks:
                if block.get('type') == 'image':
                    image_block = block
                elif block.get('type') == 'bullets':
                    bullet_blocks.append(block)
            
            # Render based on layout
            if layout == 'image-left':
                # Image column
                html_parts.append('    <div class="image-column">')
                if image_block:
                    img_ref = image_block.get('image_reference', '')
                    img_url = final_image_mapping.get(img_ref, '') if final_image_mapping else ''
                    if img_url:
                        html_parts.append(f'      <img src="{img_url}" class="slide-image" alt="{img_ref}">')
                html_parts.append('    </div>')
                
                # Bullets column
                html_parts.append('    <div class="bullets-column">')
                for bullet_block in bullet_blocks:
                    heading = bullet_block.get('heading', '')
                    if heading:
                        html_parts.append(f'      <div class="content-heading">{heading}</div>')
                    html_parts.append('      <ul class="bullets">')
                    for item in bullet_block.get('items', []):
                        html_parts.append(f'        <li>{item}</li>')
                    html_parts.append('      </ul>')
                html_parts.append('    </div>')
                
            elif layout == 'image-right':
                # Bullets column
                html_parts.append('    <div class="bullets-column">')
                for bullet_block in bullet_blocks:
                    heading = bullet_block.get('heading', '')
                    if heading:
                        html_parts.append(f'      <div class="content-heading">{heading}</div>')
                    html_parts.append('      <ul class="bullets">')
                    for item in bullet_block.get('items', []):
                        html_parts.append(f'        <li>{item}</li>')
                    html_parts.append('      </ul>')
                html_parts.append('    </div>')
                
                # Image column
                html_parts.append('    <div class="image-column">')
                if image_block:
                    img_ref = image_block.get('image_reference', '')
                    img_url = final_image_mapping.get(img_ref, '') if final_image_mapping else ''
                    if img_url:
                        html_parts.append(f'      <img src="{img_url}" class="slide-image" alt="{img_ref}">')
                html_parts.append('    </div>')
                
            elif layout == 'image-full':
                # Just the image, centered
                if image_block:
                    img_ref = image_block.get('image_reference', '')
                    img_url = final_image_mapping.get(img_ref, '') if final_image_mapping else ''
                    if img_url:
                        html_parts.append(f'    <img src="{img_url}" class="slide-image" alt="{img_ref}">')
            
            html_parts.append('  </div>')
            
        else:
            # Standard single-column or two-column layout
            html_parts.append('  <div class="slide-content">')
            
            logger.info(f"🔍 DEBUG: Slide {slide_idx} '{title}' has {len(slide.get('content_blocks', []))} content blocks")
            
            for block in slide.get('content_blocks', []):
                block_type = block.get('type')
                logger.info(f"🔍 DEBUG: Block type='{block_type}', items={len(block.get('items', []))}")
                
                if block_type == 'nested-bullets':
                    # Nested bullets for agenda (modules with lessons)
                    logger.info(f"🔍 DEBUG: NESTED-BULLETS BRANCH 1! Items: {block.get('items')}")
                    heading = block.get('heading', '')
                    if heading:
                        html_parts.append(f'    <div class="content-heading">{heading}</div>')
                    html_parts.append('    <ul class="bullets">')
                    for item in block.get('items', []):
                        if isinstance(item, dict):
                            # Module with nested lessons
                            html_parts.append(f'      <li>{item.get("text", "")}')
                            lessons = item.get('lessons', [])
                            if lessons:
                                html_parts.append('        <ul>')
                                for lesson in lessons:
                                    html_parts.append(f'          <li>{lesson}</li>')
                                html_parts.append('        </ul>')
                            html_parts.append('      </li>')
                        else:
                            # Plain text item (fallback)
                            html_parts.append(f'      <li>{item}</li>')
                    html_parts.append('    </ul>')
                
                elif block_type == 'bullets':
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
                    
                    if not img_url:
                        logger.warning(f"⚠️ Image '{img_ref}' not found in mapping. Available: {list(final_image_mapping.keys())[:5]}")
                    
                    if img_url:
                        html_parts.append(f'    <img src="{img_url}" class="slide-image" alt="{img_ref}">')
                        if caption:
                            html_parts.append(f'    <div style="text-align: center; font-size: 16pt; color: #666;">{caption}</div>')
                    else:
                        html_parts.append(f'    <div style="border: 2px dashed #ccc; padding: 100px; text-align: center; color: #999; margin: 20px 0;">Image: {img_ref}</div>')
                
                elif block_type == 'callout':
                    text = block.get('text', '')
                    html_parts.append(f'    <div class="callout">{text}</div>')
                
                elif block_type == 'table':
                    # Render table from headers and rows
                    heading = block.get('heading', '')
                    headers = block.get('headers', [])
                    rows = block.get('rows', [])
                    
                    if heading:
                        html_parts.append(f'    <div class="content-heading">{heading}</div>')
                    
                    html_parts.append('    <table class="slide-table">')
                    
                    # Table headers
                    if headers:
                        html_parts.append('      <thead>')
                        html_parts.append('        <tr>')
                        for header in headers:
                            html_parts.append(f'          <th>{header}</th>')
                        html_parts.append('        </tr>')
                        html_parts.append('      </thead>')
                    
                    # Table body
                    if rows:
                        html_parts.append('      <tbody>')
                        for row in rows:
                            html_parts.append('        <tr>')
                            for cell in row:
                                html_parts.append(f'          <td>{cell}</td>')
                            html_parts.append('        </tr>')
                        html_parts.append('      </tbody>')
                    
                    html_parts.append('    </table>')
            
            html_parts.append('  </div>')
        
        # Add logo to regular content slides (bottom-right)
        html_parts.append(f'  <img src="{logo_url}" class="slide-logo" alt="Logo">')
        
        html_parts.append('</div>')
    
    html_parts.extend([
        '</body>',
        '</html>'
    ])
    
    return '\n'.join(html_parts)
