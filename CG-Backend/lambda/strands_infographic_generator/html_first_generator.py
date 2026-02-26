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
import html as html_module
import unicodedata
from urllib.parse import quote
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger("aurora.infographic_generator")


def highlight_code_with_pygments(code: str, language: str) -> str:
    """
    Apply syntax highlighting to code using Pygments.
    Returns HTML with inline styles matching VS Code's Tomorrow Night theme.
    Falls back to escaped plain text if Pygments fails.
    """
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, TextLexer
        from pygments.formatters import HtmlFormatter
        
        # Map common language names to Pygments lexer names
        language_map = {
            'js': 'javascript',
            'ts': 'typescript',
            'py': 'python',
            'rb': 'ruby',
            'sh': 'bash',
            'shell': 'bash',
            'yml': 'yaml',
            'dockerfile': 'docker',
            'tf': 'terraform',
            'hcl': 'terraform',
        }
        
        lang = language_map.get(language.lower(), language.lower())
        
        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except Exception:
            lexer = TextLexer()
        
        # Use inline styles for compatibility (no external CSS needed)
        # Colors match prism-tomorrow.css / VS Code Dark+ theme
        formatter = HtmlFormatter(
            nowrap=True,
            noclasses=True,
            style='monokai'  # Close to Tomorrow Night / VS Code dark
        )
        
        highlighted = highlight(code, lexer, formatter)
        return f'<pre><code>{highlighted}</code></pre>'
        
    except ImportError:
        logger.warning("Pygments not available, falling back to plain text")
        escaped = html_module.escape(code)
        return f'<pre><code>{escaped}</code></pre>'
    except Exception as e:
        logger.error(f"Pygments error: {e}, falling back to plain text")
        escaped = html_module.escape(code)
        return f'<pre><code>{escaped}</code></pre>'


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


def extract_code_from_content(content: str) -> List[Dict]:
    """
    Extract code blocks from lesson content.
    Returns list of dicts with 'language', 'code', and optional 'title' for each code block.
    
    Supports markdown fenced code blocks:
    ```python
    def hello():
        print("Hello!")
    ```
    """
    code_blocks = []
    
    # Pattern to match fenced code blocks with optional language
    pattern = r'```(\w+)?\s*\n(.*?)```'
    
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        language = match.group(1) or 'text'
        code = match.group(2).rstrip()
        
        # Try to find a title in the preceding lines
        start_pos = match.start()
        preceding_content = content[:start_pos].split('\n')[-3:]
        
        title = None
        for line in reversed(preceding_content):
            line = line.strip()
            if line.startswith('##'):
                title = line.lstrip('#').strip()
                break
            if line.startswith('**') and line.endswith('**'):
                title = line.strip('*').strip()
                break
        
        # Skip very short code snippets (not worth a slide)
        if len(code.strip()) < 20:
            continue
            
        code_blocks.append({
            'language': language.lower(),
            'code': code,
            'title': title,
            'lines': len(code.split('\n'))
        })
    
    logger.info(f"📝 Extracted {len(code_blocks)} code blocks from content")
    
    return code_blocks


class HTMLSlideBuilder:
    """Builds HTML slides with real-time overflow detection."""
    
    # CSS constants - ACTUAL rendering values
    SLIDE_WIDTH = 1280
    SLIDE_HEIGHT = 720
    HEADER_HEIGHT = 120  # Title + subtitle area
    FOOTER_HEIGHT = 40
    MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 500
    MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520
    
    # Element heights (from actual CSS)
    BULLET_HEIGHT = 50  # 20pt × 1.4 line-height + padding
    HEADING_HEIGHT = 65
    IMAGE_HEIGHT = 400
    CALLOUT_HEIGHT = 75
    TABLE_ROW_HEIGHT = 45  # Header ~45px, Data ~35px
    TABLE_MARGIN = 40
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
        
    def add_table(self, headers: List[str], rows: List[List[str]], notes: str = "") -> bool:
        """Add a table to current slide."""
        if not self.current_slide:
            return False
            
        # Calculate height: margin + header + (rows * row height) + optional notes
        height = self.TABLE_MARGIN + self.TABLE_ROW_HEIGHT + (len(rows) * self.TABLE_ROW_HEIGHT)
        if notes:
            height += 40
            
        if not self.can_add_content(height):
            return False
            
        self.current_slide['content_blocks'].append({
            'type': 'table',
            'headers': headers,
            'rows': rows,
            'notes': notes
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
    
    # 1. Course Title Slide
    intro_slides.append({
        "slide_number": slide_counter,
        "title": course_metadata.get('title', 'Course Title'),
        "subtitle": "",
        "layout": "intro-cover",
        "content_blocks": [],
        "notes": "Course title slide"
    })
    slide_counter += 1
    
    # 2. Copyright Slide - IMMEDIATELY after course title
    intro_slides.append(create_copyright_slide(True, slide_counter))  # Always Spanish for Netec
    slide_counter += 1
    
    # 3. Description Slide
    description_text = (course_metadata.get('description') or '').strip()
    if description_text:
        intro_slides.append({
            "slide_number": slide_counter,
            "title": "Descripción del curso" if is_spanish else "Course Description",
            "subtitle": "",
            "layout": "intro-description",
            "content_blocks": [
                {
                    "type": "bullets",
                    "heading": "",
                    "items": [description_text]
                }
            ],
            "notes": "Course description"
        })
        slide_counter += 1

    # 4. Objectives Slide
    learning_outcomes = course_metadata.get('learning_outcomes', [])
    if learning_outcomes:
        intro_slides.append({
            "slide_number": slide_counter,
            "title": "Objetivos del curso" if is_spanish else "Course Objectives",
            "subtitle": "Al finalizar el curso, serás capaz de:" if is_spanish else "By the end of this course, you will be able to:",
            "layout": "intro-objectives",
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
    
    # 5. Prerequisites Slide
    prerequisites_list = course_metadata.get('prerequisites', [])
    if prerequisites_list:
        intro_slides.append({
            "slide_number": slide_counter,
            "title": "Prerrequisitos" if is_spanish else "Prerequisites",
            "subtitle": "",
            "layout": "intro-prerequisites",
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
    
    # 6. Audience Slide (new)
    audience_list = course_metadata.get('audience', [])
    if audience_list:
        intro_slides.append({
            "slide_number": slide_counter,
            "title": "Audiencia" if is_spanish else "Audience",
            "subtitle": "",
            "layout": "intro-audience",
            "content_blocks": [
                {
                    "type": "bullets",
                    "heading": "",
                    "items": audience_list
                }
            ],
            "notes": "Target audience"
        })
        slide_counter += 1
    
    return intro_slides, slide_counter


def create_group_presentation_slide(is_spanish: bool, slide_counter: int) -> Dict:
    """Create a group presentation slide for introductions."""
    return {
        "slide_number": slide_counter,
        "title": "Presentación del Grupo" if is_spanish else "Group Presentation",
        "subtitle": "",
        "layout": "intro-group-presentation",
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


def create_copyright_slide(is_spanish: bool, slide_counter: int) -> Dict:
    """Create the intellectual property/copyright slide."""
    title = "Propiedad Intelectual"
    text_content = [
        "Material didáctico preparado por la empresa Global K, S.A. de C.V. Registrado en Derechos de Autor.",
        "Todos los contenidos de este Sitio (incluyendo, pero no limitado a: texto, logotipos, contenido, fotografías, audio, botones, nombres comerciales y videos) están sujetos a derechos de propiedad por las leyes de Derechos de Autor de la empresa Global K, S.A. de C.V.",
        "Queda prohibido copiar, reproducir, distribuir, publicar, transmitir, difundir, o en cualquier modo explotar cualquier parte de este documento sin la autorización previa por escrito de Global K, S.A. de C.V. o de los titulares correspondientes."
    ]
    
    return {
        "slide_number": slide_counter,
        "title": title,
        "subtitle": "",
        "layout": "intro-intellectual-property",
        "content_blocks": [
            {
                "type": "bullets",
                "heading": "",
                "items": text_content
            }
        ],
        "notes": "Legal copyright notice"
    }


def create_agenda_slide(modules: List[Dict], is_spanish: bool, slide_counter: int) -> List[Dict]:
    """
    Create simplified agenda slide(s) showing ONLY course modules (no lessons).
    Automatically splits into multiple slides based on TOTAL ITEM COUNT (not just module count)
    to prevent content overflow.
    Returns list of slide dictionaries.
    """
    # 1. Extract only module titles
    agenda_items = []
    for idx, module in enumerate(modules, 1):
        module_title = str(module.get('title', '') or '').strip()
        if not module_title:
            module_title = f"{'Capítulo' if is_spanish else 'Module'} {idx}"

        if is_spanish:
            cleaned_title = re.sub(
                r'^\s*(?:cap[ií]tulo|modulo|m[oó]dulo)\s*\d+\s*[:\-–—]?\s*',
                '',
                module_title,
                flags=re.IGNORECASE
            ).strip()
            if not cleaned_title:
                cleaned_title = module_title
            agenda_items.append(f"Capítulo {idx}: {cleaned_title}")
        else:
            cleaned_title = re.sub(
                r'^\s*(?:module|chapter)\s*\d+\s*[:\-–—]?\s*',
                '',
                module_title,
                flags=re.IGNORECASE
            ).strip()
            if not cleaned_title:
                cleaned_title = module_title
            agenda_items.append(f"Module {idx}: {cleaned_title}")
    
    # 2. Simple splitting logic

    # (Removed lesson processing)
        
    MAX_MODULES_PER_SLIDE = 5
    
    slides = []
    current_items = []
    part_num = 1
    
    for item in agenda_items:
        current_items.append(item)
        if len(current_items) >= MAX_MODULES_PER_SLIDE:
             slides.append({
                "slide_number": slide_counter + len(slides),
                "title": (f"Temario ({part_num})" if len(agenda_items) > MAX_MODULES_PER_SLIDE else "Temario") if is_spanish else (f"Agenda ({part_num})" if len(agenda_items) > MAX_MODULES_PER_SLIDE else "Agenda"),
                "subtitle": "Estructura del curso" if is_spanish else "Course structure",
                "layout": "intro-agenda",
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
    
    if current_items:
        slides.append({
            "slide_number": slide_counter + len(slides),
            "title": (f"Temario ({part_num})" if len(agenda_items) > MAX_MODULES_PER_SLIDE and part_num > 1 else "Temario") if is_spanish else (f"Agenda ({part_num})" if len(agenda_items) > MAX_MODULES_PER_SLIDE and part_num > 1 else "Agenda"),
            "subtitle": "Estructura del curso" if is_spanish else "Course structure",
            "layout": "intro-agenda",
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


def _extract_markdown_section(content: str, heading_keywords: List[str]) -> str:
    """Extract markdown section body for first matching heading, including nested subsections."""
    if not content:
        return ""

    lines = content.splitlines()
    start_idx = None
    start_level = None

    for i, line in enumerate(lines):
        match = re.match(r'^\s{0,3}(#{2,6})\s*(.+?)\s*$', line)
        if not match:
            continue
        heading_level = len(match.group(1))
        heading = match.group(2).strip().lower().rstrip(':')
        if any(keyword in heading for keyword in heading_keywords):
            start_idx = i + 1
            start_level = heading_level
            break

    if start_idx is None:
        return ""

    end_idx = len(lines)
    for j in range(start_idx, len(lines)):
        m = re.match(r'^\s{0,3}(#{2,6})\s+', lines[j])
        if m:
            level = len(m.group(1))
            # Stop only when we hit a heading at same or higher hierarchy level
            if start_level is not None and level <= start_level:
                end_idx = j
                break

    return "\n".join(lines[start_idx:end_idx]).strip()


def _section_to_bullets(section_text: str) -> List[str]:
    """Convert markdown section body to bullet-like items."""
    if not section_text:
        return []

    bullets = []
    paragraph_buffer = []

    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r'[-_]{3,}', line):
            continue
        if line.startswith('```'):
            continue

        list_match = re.match(r'^(?:[-*+]\s+|\d+[\.)]\s+)(.+)$', line)
        if list_match:
            item = list_match.group(1).strip()
            item = re.sub(r'\s+', ' ', item)
            if item:
                bullets.append(item)
            continue

        cleaned = re.sub(r'^[>#\s]+', '', line)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if cleaned:
            paragraph_buffer.append(cleaned)

    if not bullets and paragraph_buffer:
        paragraph = " ".join(paragraph_buffer)
        sentences = [s.strip() for s in re.split(r'(?<=[\.!?])\s+', paragraph) if s.strip()]
        bullets.extend(sentences[:8])

    # Remove duplicates preserving order
    unique = []
    seen = set()
    for b in bullets:
        normalized = b.lower()
        if normalized not in seen:
            unique.append(b)
            seen.add(normalized)

    return unique


def _extract_instruction_lines(section_text: str) -> List[str]:
    """Extract explicit instruction list items (numbered/bulleted) for procedural sections."""
    if not section_text:
        return []

    items = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line or re.fullmatch(r'[-_]{3,}', line):
            continue
        if line.startswith('```'):
            continue

        m = re.match(r'^(?:\d+[\.)]|[-*+])\s+(.+)$', line)
        if not m:
            continue

        item = re.sub(r'\s+', ' ', m.group(1).strip())
        if len(item) < 3:
            continue
        items.append(item)

    # De-duplicate preserving order
    deduped = []
    seen = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            deduped.append(item)
            seen.add(key)

    return deduped


def _extract_procedure_headings(section_text: str) -> List[str]:
    """Extract higher-level procedure headings (e.g., Paso 1, Paso 2) to avoid over-fragmented slides."""
    if not section_text:
        return []

    headings = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = re.match(r'^\s{0,3}#{3,6}\s*(.+?)\s*$', line)
        if not m:
            continue

        heading = re.sub(r'\s+', ' ', m.group(1).strip().rstrip(':'))
        if not heading:
            continue

        # Skip non-procedural subsections commonly embedded in guides
        if re.search(r'(resultado|salida\s+esperada|checklist|verificaci[oó]n|evidencia|validaci[oó]n)', heading, re.IGNORECASE):
            continue

        headings.append(heading)

    deduped = []
    seen = set()
    for item in headings:
        key = item.lower()
        if key not in seen:
            deduped.append(item)
            seen.add(key)

    return deduped


def _chunk_items(items: List[str], chunk_size: int) -> List[List[str]]:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)] if items else []


def _format_duration(duration_minutes: Optional[int], is_spanish: bool) -> str:
    if duration_minutes is None:
        return ""

    if duration_minutes < 60:
        return f"{duration_minutes} minutos" if is_spanish else f"{duration_minutes} minutes"

    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    if is_spanish:
        if minutes == 0:
            return f"{hours} hora{'s' if hours != 1 else ''}"
        return f"{hours} h {minutes} min"

    if minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours}h {minutes}m"


def _extract_duration_minutes(lab_data: Dict, content: str) -> Optional[int]:
    """Extract duration in minutes from structured fields or markdown text."""
    structured_duration = lab_data.get('duration_minutes')
    if isinstance(structured_duration, (int, float)):
        return int(structured_duration)

    if isinstance(structured_duration, str) and structured_duration.strip().isdigit():
        return int(structured_duration.strip())

    patterns = [
        r'(?:duraci[oó]n(?:\s+estimada)?|tiempo(?:\s+estimado)?|estimated\s+time|duration)\s*[:\-]?\s*(\d{1,3})\s*(?:min|mins|minuto|minutos|minutes?)',
        r'(?:duraci[oó]n(?:\s+estimada)?|tiempo(?:\s+estimado)?|estimated\s+time|duration)\s*[:\-]?\s*(\d{1,2})\s*(?:hora|horas|hour|hours)(?:\s*(\d{1,2})\s*(?:min|minutos|minutes?))?'
    ]

    for idx, pattern in enumerate(patterns):
        match = re.search(pattern, content, re.IGNORECASE)
        if not match:
            continue
        if idx == 0:
            return int(match.group(1))
        hours = int(match.group(1))
        extra_minutes = int(match.group(2)) if match.group(2) else 0
        return hours * 60 + extra_minutes

    return None


def extract_references_from_lesson_content(content: str) -> List[str]:
    """Extract bibliography/reference items from a lesson markdown body."""
    references_section = _extract_markdown_section(
        content,
        ['bibliografía', 'bibliografia', 'bibliography', 'referencias', 'references']
    )
    return _section_to_bullets(references_section)


def create_lab_intro_slide(lab_data: Dict, is_spanish: bool, slide_counter: int) -> Dict:
    """Create a slide introducing a lab activity."""
    lab_title = lab_data.get('title', 'Actividad')
    
    # Extract description and objectives if available, otherwise generic text
    description = lab_data.get('description', '')
    objectives = lab_data.get('objectives', [])
    if isinstance(objectives, str):
        objectives = [objectives]
        
    items = []
    if description:
        items.append(description)
    if objectives:
        if is_spanish:
             items.append("Objetivos:")
        else:
             items.append("Objectives:")
        items.extend(objectives)
        
    if not items:
        # Fallback if no details
        items = ["Realizar la práctica descrita en el manual de laboratorio."] if is_spanish else ["Perform the lab activity described in the lab manual."]

    # Generate detailed notes for the instructor
    notes_text = f"Lab Activity: {lab_title}\n\nDescription:\n{description}\n\n"
    if objectives:
        notes_text += "Objectives:\n" + "\n".join(f"- {obj}" for obj in objectives)
        
    return {
        "slide_number": slide_counter,
        "title": lab_title,
        "subtitle": "Actividad Práctica" if is_spanish else "Lab Activity",
        "layout": "single-column",
        "content_blocks": [
            {
                "type": "bullets",
                "heading": "Descripción" if is_spanish else "Description",
                "items": items
            }
        ],
        "notes": notes_text
    }


def create_lab_result_slide(lab_data: Dict, is_spanish: bool, slide_counter: int) -> Dict:
    """Create 'Resultado esperado' slide for a lab."""
    lab_title = lab_data.get('title', 'Actividad')
    
    return {
        "slide_number": slide_counter,
        "title": "Resultado Esperado" if is_spanish else "Expected Result",
        "subtitle": lab_title,
        "layout": "image-center", # Placeholder preference, though usually text
        "content_blocks": [
             {
                "type": "bullets",
                "heading": "",
                "items": ["(Captura de pantalla o descripción del resultado final esperado de la práctica)"]
            }
        ],
        "notes": f"Expected result for {lab_title}"
    }


def create_references_slide(module_data: Dict, is_spanish: bool, slide_counter: int) -> Dict:
    """Create 'Referencias Bibliográficas' slide for a module."""
    # Try to get references from module data, or generic placeholder
    references = module_data.get('references', [])
    if not references:
        references = ["Documentación oficial de Google Cloud"]  # Generic default
        
    return {
        "slide_number": slide_counter,
        "title": "Referencias Bibliográficas" if is_spanish else "Bibliographic References",
        "subtitle": module_data.get('title', ''),
        "layout": "single-column",
        "content_blocks": [
            {
                "type": "bullets",
                "heading": "",
                "items": references
            }
        ],
        "notes": "Module references"
    }


def create_logo_slide(slide_counter: int) -> Dict:
    """Create a branded slide with just the logo (replaces intermediate Gracias)."""
    return {
        "slide_number": slide_counter,
        "title": "",
        "subtitle": "",
        "layout": "logo-only", 
        "content_blocks": [],
        "notes": "Netec brand slide"
    }


def create_module_end_logo_slide(slide_counter: int) -> Dict:
    """Create a module-end slide with Netec logo centered (no blue frame, white background)."""
    return {
        "slide_number": slide_counter,
        "title": "",
        "subtitle": "",
        "layout": "module-end-logo",  # Special layout: white bg, centered logo, no header frame
        "content_blocks": [],
        "notes": "Module end - Netec logo centered"
    }


def create_thank_you_slide(is_spanish: bool, slide_counter: int) -> Dict:
    """Create a thank you / closing slide with Gracias asset."""
    return {
        "slide_number": slide_counter,
        "title": "¡Gracias!" if is_spanish else "Thank You!",
        "subtitle": "¿Dudas o comentarios?" if is_spanish else "Questions or comments?",
        "layout": "gracias",
        "content_blocks": [],
        "notes": "Course closing slide"
    }


# ── Chapter summary, Glossary, Lab-intro helpers ────────────────────────────

# Noise items that are AI section headings, not real objectives/topics
_NOISE_HEADINGS = {
    'visión general del concepto', 'detalles técnicos', 'aplicación práctica',
    'puntos clave', 'próximos pasos', 'recursos adicionales',
    'información general', 'temas principales del capítulo',
    'lecciones incluidas',
}


def _extract_resumen_items(content: str) -> List[str]:
    """Extract summary items from 'Resumen del Capítulo' lesson content."""
    if not content:
        return []
    pattern = re.compile(
        r'###\s*(?:Temas\s+m[áa]s\s+importantes\s+cubiertos|Key\s+Topics\s+Covered)[^\n]*\n+'
        r'((?:\s*-\s+.+\n?)+)',
        re.MULTILINE | re.IGNORECASE
    )
    m = pattern.search(content)
    if not m:
        return []
    items = []
    for line in m.group(1).strip().split('\n'):
        line = line.strip()
        if line.startswith('- '):
            text = line[2:].strip()
            if text.lower() in _NOISE_HEADINGS:
                continue
            items.append(text)
    return items[:10]


def _parse_glossary_items(glossary_md: str) -> List[Dict]:
    """Parse glossary markdown into list of {'term': str, 'definition': str} dicts."""
    items = []
    if not glossary_md:
        return items
    seen_terms = set()
    _skip_terms = {'próximos pasos', 'recursos adicionales', 'puntos clave',
                   'describir', 'explicar', 'comparar', 'aplicación práctica',
                   'detalles técnicos', 'visión general del concepto'}
    for line in glossary_md.strip().split('\n'):
        line = line.strip()
        if line.startswith('- **'):
            m = re.match(r'^-\s+\*\*([^*]+)\*\*:\s*(.+)$', line)
            if m:
                term = m.group(1).strip()
                definition = m.group(2).strip()
                term_lower = term.lower().replace('¿', '').replace('?', '').strip()
                if term_lower in _skip_terms:
                    continue
                if term.startswith('¿') or term.endswith('?'):
                    continue
                if term_lower in seen_terms:
                    continue
                seen_terms.add(term_lower)
                # Clean definition
                definition = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', definition)
                definition = re.sub(r'#{2,}\s*', '', definition)
                definition = re.sub(r'\*\*([^*]+)\*\*', r'\1', definition)
                definition = re.sub(r'^[–—-]+\s*', '', definition).strip()
                for prefix in [term, term.split(':')[0].strip()]:
                    if definition.lower().startswith(prefix.lower()):
                        definition = definition[len(prefix):].lstrip(' :,.-–—').strip()
                if definition.lower().replace('¿', '').replace('?', '') == term_lower:
                    definition = ''
                if 'concepto clave abordado' in definition.lower():
                    definition = ''
                if 'objetivos de aprendizaje' in definition.lower():
                    definition = ''
                if len(definition) > 120:
                    definition = definition[:117] + '...'
                items.append({'term': term, 'definition': definition})
    return items


def _is_lesson_summary_slide(slide: Dict) -> bool:
    """Check if a slide is a per-lesson summary that should be suppressed."""
    title = slide.get('title', '').lower()
    return (
        title.startswith('resumen:') or
        title.startswith('resumen -') or
        ('resumen' in title and ('puntos clave' in title or 'key points' in title)) or
        title == 'resumen' or
        title == 'puntos clave'
    )


def create_chapter_summary_slide(module_number: int, summary_items: List[str],
                                  module_title: str, is_spanish: bool,
                                  slide_counter: int) -> Dict:
    """Create a chapter summary slide with Resumen_Capitulo.png asset."""
    return {
        "slide_number": slide_counter,
        "title": "Resumen del capítulo" if is_spanish else "Chapter Summary",
        "subtitle": module_title,
        "layout": "chapter-summary",
        "content_blocks": [{
            "type": "bullets",
            "heading": "",
            "items": summary_items
        }],
        "notes": f"Chapter {module_number} summary",
        "module_number": module_number
    }


def create_glossary_slides(glossary_items: List[Dict], is_spanish: bool, slide_counter: int) -> List[Dict]:
    """Create glossary slide(s) with terms from the book."""
    slides = []
    # Chunk: max 10 items per slide
    chunk_size = 10
    chunks = [glossary_items[i:i + chunk_size] for i in range(0, len(glossary_items), chunk_size)]
    for idx, chunk in enumerate(chunks):
        slides.append({
            "slide_number": slide_counter + idx,
            "title": "Glosario" if is_spanish else "Glossary",
            "subtitle": f"({idx + 1}/{len(chunks)})" if len(chunks) > 1 else "",
            "layout": "glossary",
            "content_blocks": [{
                "type": "glossary",
                "items": chunk
            }],
            "notes": "Course glossary"
        })
    return slides


def create_module_title_slide(module: Dict, module_number: int, is_spanish: bool, slide_counter: int) -> Dict:
    """Create a full-screen branded module title slide."""
    return {
        "slide_number": slide_counter,
        "title": module.get('title', f"{'Capítulo' if is_spanish else 'Module'} {module_number}"),
        "subtitle": "",
        "layout": "module-title",
        "content_blocks": [],
        "notes": f"Module {module_number} introduction",
        "module_number": module_number
    }


def _extract_objectives_from_content(content: str) -> List[str]:
    """Extract learning objectives from lesson markdown content.
    
    Looks for sections like '## Objetivos de Aprendizaje' / '### Objetivos del capítulo'
    and pulls the bullet list items from it.
    """
    if not content:
        return []
    
    # Match the objectives section header (## or ###)
    pattern = re.compile(
        r'^#{2,3}\s*(?:Objetivos\s+(?:de\s+Aprendizaje|del\s+[Cc]ap[ií]tulo)|Learning\s+Objectives|Objetivos)[^\n]*\n+'
        r'(?:[^\n]*\n)*?'  # optional preamble line like "Al finalizar..."
        r'((?:\s*-\s+.+\n?)+)',
        re.MULTILINE | re.IGNORECASE
    )
    match = pattern.search(content)
    if not match:
        return []
    
    bullet_block = match.group(1)
    objectives = []
    for line in bullet_block.strip().split('\n'):
        line = line.strip()
        if line.startswith('- '):
            # Strip bold markers for cleaner slide text
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', line[2:].strip())
            # Skip glossary-style definitions (term with parens + colon)
            if re.match(r'^[A-Za-z\u00C1-\u00FF]+[^:]{0,40}\)\s*:', text):
                continue
            if text.lower().strip() in _NOISE_HEADINGS:
                continue
            objectives.append(text)
    
    return objectives[:6]  # Cap at 6 to fit on slide


def _extract_introduction_from_content(content: str) -> str:
    """Extract the first paragraph of the '## Introducción' / '## Introduction' section."""
    if not content:
        return ''
    
    pattern = re.compile(
        r'^#{2,3}\s*(?:Introducción|Introduction)[^\n]*\n+'
        r'(.+?)(?:\n\n|\n#{2,3}|\Z)',
        re.MULTILINE | re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(content)
    if not match:
        return ''
    
    # Take just the first paragraph (first block of non-empty lines)
    raw = match.group(1).strip()
    first_para = raw.split('\n\n')[0].replace('\n', ' ').strip()
    # Cap at 300 chars for slide readability
    if len(first_para) > 300:
        first_para = first_para[:297] + '...'
    return first_para


def create_lesson_title_slide(lesson: Dict, module_number: int, lesson_number: int, is_spanish: bool, slide_counter: int, module_title: str = "") -> Dict:
    """Create a branded lesson title slide with introduction text."""
    lesson_title = lesson.get('title', f"Lección {lesson_number}")
    
    # Extract introduction from lesson content for the slide body
    intro_text = _extract_introduction_from_content(lesson.get('content', ''))
    
    # Use the title as-is from the book (it already contains numbering like "1.1: ...")
    display_title = lesson_title
    
    content_blocks = []
    if intro_text:
        content_blocks.append({
            "type": "bullets",
            "heading": "Introducción" if is_spanish else "Introduction",
            "items": [intro_text]
        })
    
    return {
        "slide_number": slide_counter,
        "title": display_title,
        "subtitle": module_title,
        "layout": "lesson-title",
        "content_blocks": content_blocks,
        "notes": f"Lesson {lesson_number} of Module {module_number}"
    }


def create_module_title_slide_from_lesson(lesson: Dict, module_number: int, is_spanish: bool, slide_counter: int) -> Dict:
    """
    Create module title slide using lesson data (no outline dependency).
    Extracts module title from lesson's module_title field if present,
    otherwise uses a generic "Capítulo N" title.
    Extracts learning objectives from the first lesson's content.
    """
    # Try to get module title from lesson metadata
    module_title = lesson.get('module_title', '')
    if not module_title:
        module_title = f"{'Capítulo' if is_spanish else 'Module'} {module_number}"
    
    # Extract objectives from first lesson of the module
    objectives = _extract_objectives_from_content(lesson.get('content', ''))
    content_blocks = []
    if objectives:
        content_blocks.append({
            "type": "bullets",
            "heading": "Objetivos:" if is_spanish else "Objectives:",
            "items": objectives
        })
    
    return {
        "slide_number": slide_counter,
        "title": module_title,
        "subtitle": "",
        "layout": "module-title",
        "content_blocks": content_blocks,
        "notes": f"Module {module_number} introduction",
        "module_number": module_number
    }


def create_lab_slides_from_content(lesson: Dict, is_spanish: bool, slide_counter: int) -> List[Dict]:
    """
    Create rich, multi-slide lab activity deck from lab guide content.
    Includes: duration, objectives, description, steps, expected results.
    """
    slides = []
    lesson_title = lesson.get('title', 'Lab Activity')
    content = lesson.get('lab_guide') or lesson.get('content', '')

    duration_minutes = _extract_duration_minutes(lesson, content)
    duration_text = _format_duration(duration_minutes, is_spanish) if duration_minutes is not None else ""

    description_text = _extract_markdown_section(
        content,
        ['descripción general', 'descripción', 'description', 'general description', 'overview']
    )
    objective_text = _extract_markdown_section(content, ['objetivos', 'objetivo', 'learning objectives', 'objective'])
    steps_text = _extract_markdown_section(content, ['pasos', 'procedimiento', 'instrucciones', 'steps', 'procedure', 'instructions'])
    expected_text = _extract_markdown_section(
        content,
        [
            'resultado esperado', 'resultados esperados',
            'expected result', 'expected results',
            'salida esperada', 'entregables',
            'criterios de éxito', 'criterios de exito',
            'success criteria', 'verification', 'verificación', 'verificacion'
        ]
    )

    description_items = _section_to_bullets(description_text)
    objectives_items = _section_to_bullets(objective_text)
    steps_items = _extract_procedure_headings(steps_text)
    if not steps_items:
        steps_items = _extract_instruction_lines(steps_text)
    if not steps_items:
        steps_items = _section_to_bullets(steps_text)
    expected_items = _section_to_bullets(expected_text)

    if not description_items:
        fallback_description = lesson.get('description', '')
        if fallback_description:
            description_items = [fallback_description]

    if not objectives_items:
        raw_objectives = lesson.get('objectives', [])
        if isinstance(raw_objectives, str):
            objectives_items = [raw_objectives]
        elif isinstance(raw_objectives, list):
            objectives_items = [str(item).strip() for item in raw_objectives if str(item).strip()]

    if not expected_items:
        raw_expected = lesson.get('expected_results') or lesson.get('expected_result')
        if isinstance(raw_expected, str) and raw_expected.strip():
            expected_items = [raw_expected.strip()]
        elif isinstance(raw_expected, list):
            expected_items = [str(item).strip() for item in raw_expected if str(item).strip()]

    current_slide = slide_counter

    # Slide 1: Lab Intro (title + objective only, with Reloj.png asset)
    intro_objective = ''
    if objectives_items:
        intro_objective = objectives_items[0]
    elif description_items:
        intro_objective = description_items[0]
    else:
        intro_objective = ("Completar la actividad práctica siguiendo la guía del laboratorio."
                           if is_spanish else "Complete the lab activity following the lab guide.")

    intro_blocks = []
    if intro_objective:
        intro_blocks.append({
            "type": "bullets",
            "heading": "Objetivo" if is_spanish else "Objective",
            "items": [intro_objective]
        })
    if duration_text:
        intro_blocks.append({
            "type": "bullets",
            "heading": "",
            "items": [f"{'Tiempo estimado' if is_spanish else 'Estimated time'}: {duration_text}"]
        })

    slides.append({
        "slide_number": current_slide,
        "title": lesson_title,
        "subtitle": "Actividad Práctica" if is_spanish else "Lab Activity",
        "layout": "lab-intro",
        "content_blocks": intro_blocks,
        "notes": f"Lab intro for {lesson_title}"
    })
    current_slide += 1

    # Slide 2: Planteamiento / Description (regular text-only slide)
    overview_items = []
    overview_items.extend(description_items[:5])
    if not overview_items:
        overview_items = [
            "Revisar la guía de laboratorio y preparar el entorno." if is_spanish
            else "Review the lab guide and prepare the environment."
        ]

    slides.append({
        "slide_number": current_slide,
        "title": f"Planteamiento – {lesson_title}" if is_spanish else f"Overview – {lesson_title}",
        "subtitle": "",
        "layout": "text-only",
        "content_blocks": [{
            "type": "bullets",
            "heading": "Descripción General" if is_spanish else "General Description",
            "items": overview_items
        }],
        "notes": f"Lab overview for {lesson_title}"
    })
    current_slide += 1

    # Objectives slides
    if objectives_items:
        objective_chunks = _chunk_items(objectives_items, 6)
        for idx, chunk in enumerate(objective_chunks, 1):
            slides.append({
                "slide_number": current_slide,
                "title": (
                    f"Objetivos ({idx}/{len(objective_chunks)})" if len(objective_chunks) > 1 else "Objetivos"
                ) if is_spanish else (
                    f"Objectives ({idx}/{len(objective_chunks)})" if len(objective_chunks) > 1 else "Objectives"
                ),
                "subtitle": lesson_title,
                "layout": "text-only",
                "content_blocks": [{"type": "bullets", "heading": "", "items": chunk}],
                "notes": f"Lab objectives for {lesson_title}"
            })
            current_slide += 1

    # Steps slides (required)
    if steps_items:
        step_chunks = _chunk_items(steps_items, 5)
        for idx, chunk in enumerate(step_chunks, 1):
            slides.append({
                "slide_number": current_slide,
                "title": (
                    f"Pasos de la Práctica ({idx}/{len(step_chunks)})" if len(step_chunks) > 1 else "Pasos de la Práctica"
                ) if is_spanish else (
                    f"Lab Steps ({idx}/{len(step_chunks)})" if len(step_chunks) > 1 else "Lab Steps"
                ),
                "subtitle": lesson_title,
                "layout": "text-only",
                "content_blocks": [{"type": "bullets", "heading": "", "items": chunk}],
                "notes": f"Lab procedure steps for {lesson_title}"
            })
            current_slide += 1

    # Expected results slides
    if expected_items:
        expected_chunks = _chunk_items(expected_items, 6)
        for idx, chunk in enumerate(expected_chunks, 1):
            slides.append({
                "slide_number": current_slide,
                "title": (
                    f"Resultados Esperados ({idx}/{len(expected_chunks)})" if len(expected_chunks) > 1 else "Resultados Esperados"
                ) if is_spanish else (
                    f"Expected Results ({idx}/{len(expected_chunks)})" if len(expected_chunks) > 1 else "Expected Results"
                ),
                "subtitle": lesson_title,
                "layout": "text-only",
                "content_blocks": [{"type": "bullets", "heading": "", "items": chunk}],
                "notes": f"Expected outcomes for {lesson_title}"
            })
            current_slide += 1

    if not steps_items and not expected_items:
        slides.append({
            "slide_number": current_slide,
            "title": "Resultado Esperado" if is_spanish else "Expected Result",
            "subtitle": lesson_title,
            "layout": "text-only",
            "content_blocks": [{
                "type": "bullets",
                "heading": "",
                "items": [
                    "Completar correctamente la actividad siguiendo la guía del laboratorio."
                    if is_spanish else
                    "Successfully complete the activity following the lab guide."
                ]
            }],
            "notes": f"Fallback expected result for {lesson_title}"
        })

    return slides


def create_references_slides(module_title: str, references: List[str], is_spanish: bool, slide_counter: int) -> List[Dict]:
    """Create one or more reference slides using bibliography extracted from theory book lessons."""
    cleaned_references = [ref.strip() for ref in references if isinstance(ref, str) and ref.strip()]

    # Remove duplicates preserving order
    deduped = []
    seen = set()
    for ref in cleaned_references:
        key = ref.lower()
        if key not in seen:
            deduped.append(ref)
            seen.add(key)

    if not deduped:
        deduped = [
            "Documentación oficial del curso" if is_spanish else "Official course documentation"
        ]

    chunks = _chunk_items(deduped, 6)
    slides = []

    for idx, chunk in enumerate(chunks, 1):
        title = "Referencias Bibliográficas" if is_spanish else "Bibliographic References"
        if len(chunks) > 1:
            title = f"{title} ({idx}/{len(chunks)})"

        slides.append({
            "slide_number": slide_counter + idx - 1,
            "title": title,
            "subtitle": module_title,
            "layout": "single-column",
            "content_blocks": [{
                "type": "bullets",
                "heading": "",
                "items": chunk
            }],
            "notes": "Module references from theory book bibliography"
        })

    return slides


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize('NFKD', value)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r'[^a-z0-9\s\-]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _extract_first_heading(content: str) -> str:
    if not content:
        return ""
    for line in content.splitlines():
        match = re.match(r'^\s{0,3}#\s+(.+?)\s*$', line)
        if match:
            return match.group(1).strip()
    return ""


def load_lab_guides_from_s3(course_bucket: str, project_folder: str) -> List[Dict]:
    """Load generated lab guide markdown files from S3 for richer lab slides."""
    if not course_bucket or not project_folder:
        return []

    s3 = boto3.client('s3')
    prefix = f"{project_folder}/labguide/"
    guides = []

    try:
        response = s3.list_objects_v2(Bucket=course_bucket, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj.get('Key', '')
            if not key.endswith('.md'):
                continue

            try:
                content_obj = s3.get_object(Bucket=course_bucket, Key=key)
                content = content_obj['Body'].read().decode('utf-8')
            except Exception as e:
                logger.warning(f"⚠️ Could not load lab guide {key}: {e}")
                continue

            module_number = None
            module_match = re.search(r'lab-(\d{2})-', key)
            if module_match:
                try:
                    module_number = int(module_match.group(1))
                except ValueError:
                    module_number = None

            title = _extract_first_heading(content)
            if not title:
                title = key.split('/')[-1].replace('.md', '').replace('-', ' ')

            guides.append({
                'key': key,
                'title': title,
                'normalized_title': _normalize_text(title),
                'module_number': module_number,
                'duration_minutes': _extract_duration_minutes({}, content),
                'content': content
            })

        logger.info(f"🧪 Loaded {len(guides)} lab guide(s) from s3://{course_bucket}/{prefix}")
    except Exception as e:
        logger.warning(f"⚠️ Could not list/load lab guides at {prefix}: {e}")

    return guides


def select_best_lab_guide(
    activity_title: str,
    module_number: Optional[int],
    lab_guides: List[Dict],
    used_guide_keys: set
) -> Optional[Dict]:
    """Find best lab guide match by module and title similarity."""
    if not lab_guides:
        return None

    target = _normalize_text(activity_title)
    target_tokens = set(target.split())

    best = None
    best_score = -1

    for guide in lab_guides:
        score = 0
        guide_key = guide.get('key')

        if guide_key in used_guide_keys:
            score -= 2

        if module_number is not None and guide.get('module_number') == module_number:
            score += 4

        guide_title = guide.get('normalized_title', '')
        if target and guide_title:
            if target in guide_title or guide_title in target:
                score += 5

            guide_tokens = set(guide_title.split())
            overlap = len(target_tokens.intersection(guide_tokens))
            score += overlap

        if score > best_score:
            best_score = score
            best = guide

    return best


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


class LayoutDefinitions:
    """
    Defines strict, rigid layouts with hard pixel limits.
    These are the ONLY allowable slide structures.
    """
    
    # Canvas dimensions
    WIDTH = 1280
    HEIGHT = 720
    
    # Safe zones
    HEADER_HEIGHT = 120
    FOOTER_HEIGHT = 40
    SIDE_PADDING = 50
    
    # Layouts - REDUCED LIMITS to avoid logo overlap (footer needs 80px clearance)
    # NOTE: Image layouts have FEWER bullets (4) because text area is narrower AND long bullets wrap
    LAYOUTS = {
        "text_only": {
            "description": "Title + Bullet points only (full width)",
            "containers": [
                {"type": "text", "width": 1160, "height": 440, "max_bullets": 7}
            ]
        },
        "image_left": {
            "description": "Image on left, text on right (use for visual concepts)",
            "containers": [
                {"type": "image", "width": 550, "height": 420},
                {"type": "text", "width": 520, "height": 420, "max_bullets": 4}
            ]
        },
        "image_right": {
            "description": "Text on left, image on right (use for visual concepts)",
            "containers": [
                {"type": "text", "width": 520, "height": 420, "max_bullets": 4},
                {"type": "image", "width": 550, "height": 420}
            ]
        },
        "text_and_code": {
            "description": "Brief explanation (2 bullets) + code snippet (use when context needed)",
            "containers": [
                {"type": "text", "width": 1160, "height": 100, "max_bullets": 2},
                {"type": "code", "width": 1160, "height": 320, "max_lines": 12}
            ]
        },
        "code_only": {
            "description": "FULL-HEIGHT code block - PREFERRED for code (maximizes lines!)",
            "containers": [
                {"type": "code", "width": 1160, "height": 440, "max_lines": 17}
            ]
        },
        "table": {
            "description": "Tabular data presentation",
            "containers": [
                {"type": "table", "width": 1160, "height": 420, "max_rows": 10}
            ]
        }
    }

    @classmethod
    def get_system_prompt_info(cls) -> str:
        """Returns layout info formatted for the System Prompt."""
        info = "📐 STRICT LAYOUT TEMPLATES (YOU MUST CHOOSE ONE):\n\n"
        info += "🔤 TEXT LAYOUTS:\n"
        info += f"- **text_only**: Full-width bullets (max {cls.LAYOUTS['text_only']['containers'][0]['max_bullets']} bullets)\n"
        info += f"- **image_left/image_right**: Image + bullets side-by-side (max {cls.LAYOUTS['image_left']['containers'][1]['max_bullets']} bullets - VERY LIMITED SPACE!)\n"
        
        info += "\n💻 CODE LAYOUTS (choose based on context needs):\n"
        info += f"- **code_only**: FULL-HEIGHT code - {cls.LAYOUTS['code_only']['containers'][0]['max_lines']} lines max - USE THIS WHEN CODE IS SELF-EXPLANATORY!\n"
        info += f"- **text_and_code**: Brief intro + code - {cls.LAYOUTS['text_and_code']['containers'][0]['max_bullets']} bullets + {cls.LAYOUTS['text_and_code']['containers'][1]['max_lines']} lines - USE ONLY WHEN CONTEXT IS ESSENTIAL!\n"
        
        info += "\n📊 DATA LAYOUTS:\n"
        info += f"- **table**: Data tables - {cls.LAYOUTS['table']['containers'][0]['max_rows']} rows max - USE THIS FOR TABULAR DATA!\n"
        
        info += "\n⚡ CRITICAL RULES:\n"
        info += "1. For CODE: Prefer 'code_only' to maximize lines shown. ALWAYS specify language.\n"
        info += f"2. For IMAGE layouts: Only {cls.LAYOUTS['image_left']['containers'][1]['max_bullets']} SHORT bullets! Keep text VERY concise!\n"
        info += "3. ALWAYS respect max_bullets/max_lines/max_rows - content WILL BE CUT if exceeded!\n"
        info += "4. Each bullet should be ONE SHORT sentence - avoid multi-line bullets!\n"
        info += "5. Summarize content into concise, high-value bullet points. Extract key concepts but keep it complete for instructors.\n"
        info += "6. YOU MUST INCLUDE ALL TABLES from the source using the 'table' layout.\n"
        return info


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
    


    def _repair_json(self, json_str: str) -> str:
        """
        Attempt to repair common JSON syntax errors from LLMs.
        - Fixes trailing commas
        - Fixes missing commas between items
        """
        import re
        
        # 1. Remove trailing commas before closing brackets/braces
        json_str = re.sub(r',\s*]', ']', json_str)
        json_str = re.sub(r',\s*}', '}', json_str)
        
        # 2. Add missing commas between string list items
        # Matches: "string" [newline] "string"
        # Lookbehind matches end quote, lookahead matches start quote next line
        json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
        
        # 3. Add missing commas between objects in list
        # Matches: } [newline] {
        json_str = re.sub(r'}\s*\n\s*{', '},\n{', json_str)
        
        return json_str

    def generate_from_lesson(self, lesson: Dict, lesson_idx: int, images: List[Dict]) -> List[Dict]:
        """
        Generate slides for a lesson using STRICT TEMPLATE SYSTEM + VALIDATION LOOP.
        """
        from strands import Agent
        
        lesson_title = lesson.get('title', f'Lesson {lesson_idx}')
        lesson_content = lesson.get('content', '')
        
        # FILTER OUT LAB SECTIONS (theory content only)
        lesson_content = self._remove_lab_sections(lesson_content)
        
        logger.info(f"\n📝 Strict-Template Generation for: {lesson_title}")
        
        
        # 1. Define the Creator Agent
        layout_info = LayoutDefinitions.get_system_prompt_info()
        
        system_prompt = f"""You are a STRICT TEMPLATE WEB DESIGNER creating educational slides.
TARGET: Create HTML slides by filling pre-defined templates with SMART CONTENT DISTRIBUTION.

{layout_info}

🛑 CRITICAL RULES:

1. **SMART CONTENT DISTRIBUTION** (MOST IMPORTANT!):
   - When content exceeds slide limits, SPLIT into MULTIPLE SLIDES with BALANCED content
   - Example: 10 bullets for text_only (max 7) → Create 2 slides with 5 bullets EACH, NOT 7+3!
   - Example: 8 bullets for image_left (max 4) → Create 2 slides with 4 bullets EACH
   - Each split slide should have SIMILAR amount of content - AVOID lopsided Part 1/Part 2 slides
   - Use titles like "Topic (Part 1 of 2)", "Topic (Part 2 of 2)" to show relationship

2. **IMAGE LAYOUT RULES** (VERY STRICT LIMITS!):
   - image_left/image_right: MAX 4 SHORT BULLETS - text area is NARROW (520px)
   - KEEP EACH BULLET TO ONE SHORT SENTENCE - avoid long explanations
   - If bullets are long, use FEWER bullets or SPLIT into more slides
   - NEVER exceed 4 bullets - ALWAYS split if more content exists

3. **BULLET FORMAT RULES** (CRITICAL FOR FITTING - ENFORCED BY VALIDATOR!):
   - MAXIMUM 100 characters per bullet - bullets exceeding this WILL BE TRUNCATED!
   - Each bullet must be ONE SHORT sentence (under 80 characters ideal)
   - Use concise technical terminology instead of long explanations
   - For image layouts: even shorter bullets (under 50 characters ideal)
   - Long multi-line bullets WILL BE CUT with "..." - keep them brief!

4. **CODE LAYOUT RULES** (MAXIMIZE CODE SPACE!):
   - PREFER "code_only" for code blocks - uses FULL slide (17 lines max)
   - Use "text_and_code" ONLY when brief context is ESSENTIAL (2 bullets + 12 lines)
   - Very large code (>17 lines) → SPLIT into multiple "code_only" slides
   - CODE BLOCKS SHOULD USE ALL AVAILABLE SPACE - don't leave empty space!

⚠️ JSON SYNTAX RULES (STRICT):
   - NO trailing commas in lists or objects
   - All strings must be double-quoted
   - Escape quotes inside strings (e.g. \\"text\\")
   - NO comments in JSON
   - Ensure all braces {{}} and brackets [] are matched

OUTPUT JSON FORMAT:
{{
    "slides": [
        {{
            "layout": "text_only",  // Must match one of the layout keys
            "title": "Slide Title",
            "content": {{
                "bullets": ["Point 1", "Point 2"],
                "code": {{ "language": "python", "code": "print('hi')" }}, // Only for code layouts
                "image_id": "01-01-001", // Only for image layouts
                "table": {{ // Only for table layouts
                    "headers": ["Col 1", "Col 2"],
                    "rows": [["Val 1", "Val 2"]]
                }}
            }},
            "notes": "COPY AND PASTE the exact source text paragraphs from the provided content that correspond to this slide's bullets. Do not summarize or rewrite. This text will be used as the instructor's script."
        }}
    ]
}}
"""
        
        web_designer = Agent(
            model=self.model,
            system_prompt=system_prompt,
            tools=[]
        )

        # 2. Optimization Loop (The "Second Agent")
        final_slides = []
        
        # Initial draft generation
        try:
            image_context = ""
            if images:
                image_context = "\\n\\nAVAILABLE IMAGES (YOU MUST INCLUDE ALL OF THESE USING IMAGE LAYOUTS):\\n"
                for i, img in enumerate(images):
                    image_context += f"- ID: {img.get('alt_text', f'image_{i}')}\\n"
                    
            response = web_designer(f"Create slides for this content:\\n\\n{lesson_content}{image_context}")
            
            # Extract text from Strands Agent response object
            response_text = ""
            if hasattr(response, 'message'):
                msg = response.message
                if hasattr(msg, 'content'):
                    content = msg.content
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and 'text' in block:
                                response_text += block['text']
                            elif hasattr(block, 'text'):
                                response_text += str(block.text)
                            else:
                                response_text += str(block)
                    elif isinstance(content, str):
                        response_text = content
                    else:
                        response_text = str(content)
                elif isinstance(msg, dict) and 'content' in msg:
                    content = msg['content']
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and 'text' in block:
                                response_text += block['text']
                            else:
                                response_text += str(block)
                    else:
                        response_text = str(content)
                else:
                    response_text = str(msg)
            elif hasattr(response, 'output'):
                response_text = str(response.output)
            elif hasattr(response, 'text'):
                response_text = str(response.text)
            else:
                response_text = str(response)
            
            response_text = response_text.strip()
            logger.info(f"📄 AI Response (first 500 chars): {response_text[:500]}...")
            
            # ROBUST markdown fence stripping - handle various formats
            import re
            response_text = re.sub(r'^```\w*\s*\n?', '', response_text, flags=re.MULTILINE)
            response_text = re.sub(r'\n?```\s*$', '', response_text, flags=re.MULTILINE)
            response_text = response_text.strip()
            
            # Parse JSON from response
            start_idx = response_text.find('{')
            if start_idx == -1:
                logger.error(f"No JSON found in AI response: {response_text[:200]}")
                return []
            
            import json
            try:
                parsed_response, _ = json.JSONDecoder().raw_decode(response_text[start_idx:])
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ JSON Parse Error: {e}. Attempting repair...")
                repaired_json = self._repair_json(response_text[start_idx:])
                try:
                    parsed_response, _ = json.JSONDecoder().raw_decode(repaired_json)
                    logger.info("✅ JSON Repair successful")
                except json.JSONDecodeError as e2:
                    logger.error(f"❌ JSON Repair failed: {e2}")
                    return []

            draft_slides = parsed_response.get('slides', [])
            logger.info(f"📊 Parsed {len(draft_slides)} draft slides")
            
        except Exception as e:
            logger.error(f"AI Generation failed: {e}")
            return []

        # Validation & Refinement Loop
        for slide in draft_slides:
            validated_slide = self.validate_and_refine_slide(slide, web_designer)
            if validated_slide:
                # TRANSFORMATION STEP: Convert to system-compatible format
                transformed_slide = self._transform_to_system_format(validated_slide)
                final_slides.append(transformed_slide)

        return final_slides

    def _transform_to_system_format(self, slide: Dict) -> Dict:
        """
        Transforms AI Layout JSON -> internal 'content_blocks' format.
        Maps underscore_layouts to dash-layouts used by CSS.
        """
        layout_map = {
            "text_only": "text-only",
            "image_left": "image-left",
            "image_right": "image-right", 
            "text_and_code": "text-code",
            "code_only": "code-full",
            "table": "table"
        }
        
        raw_layout = slide.get('layout', 'text_only')
        target_layout = layout_map.get(raw_layout, 'single-column')
        
        content = slide.get('content', {})
        content_blocks = []
        
        # 1. Image (if applicable)
        if 'image_id' in content and content['image_id']:
            content_blocks.append({
                "type": "image",
                "image_reference": content['image_id']
            })
            
        # 2. Bullets (Always present)
        if 'bullets' in content and content['bullets']:
            content_blocks.append({
                "type": "bullets",
                "items": content['bullets']
            })
            
        # 3. Code (if applicable)
        if 'code' in content and content['code']:
            content_blocks.append({
                "type": "code",
                "language": content['code'].get('language', 'text'),
                "code": content['code'].get('code', '')
            })
            
        # 4. Table (if applicable)
        if 'table' in content and content['table']:
            content_blocks.append({
                "type": "table",
                "headers": content['table'].get('headers', []),
                "rows": content['table'].get('rows', []),
                "notes": content['table'].get('notes', '')
            })
            
        return {
            "title": slide.get('title', 'Slide'),
            "subtitle": slide.get('subtitle', ''),
            "layout": target_layout,
            "content_blocks": content_blocks,
            "notes": slide.get('notes', '')
        }

    def validate_and_refine_slide(self, slide: Dict, agent) -> Optional[Dict]:
        """
        Validates content against rigid limits. If failing, re-prompts AI to fix.
        """
        layout_key = slide.get('layout')
        if layout_key not in LayoutDefinitions.LAYOUTS:
            logger.warning(f"Invalid layout '{layout_key}', defaulting to text_only")
            layout_key = 'text_only'
            slide['layout'] = 'text_only'

        layout_spec = LayoutDefinitions.LAYOUTS[layout_key]
        
        # Check constraints
        violations = []
        
        # Check text length
        content = slide.get('content', {})
        
        # ROBUST CONTENT NORMALIZATION
        # Handle various malformed structures from LLM
        if isinstance(content, list):
             if not content:
                 content = {}
             elif isinstance(content[0], dict):
                 content = content[0]
             elif isinstance(content[0], str):
                 # Assume list of strings is the bullet list
                 content = {'bullets': content}
             else:
                 content = {}
        elif isinstance(content, str):
            # content is just a string, treat as one bullet or description
            content = {'bullets': [content]}
        
        # Ensure dict at this point
        if not isinstance(content, dict):
            content = {}

        # Ensure 'bullets' exists
        bullets = content.get('bullets', [])
        # If bullets is explicitly None (found in some logs)
        if bullets is None:
            bullets = []
        
        # Update slide content with normalized version to ensure downstream renderers work
        slide['content'] = content

        for container in layout_spec['containers']:
            if container['type'] == 'text':
                if len(bullets) > container['max_bullets']:
                    violations.append(f"Too many bullets: {len(bullets)} > {container['max_bullets']}")
                
                # NEW: Check individual bullet length to prevent text overflow
                # At 16pt font, ~100 chars fits on 2 lines in the content area
                MAX_BULLET_CHARS = 100
                for i, bullet in enumerate(bullets):
                    if len(bullet) > MAX_BULLET_CHARS:
                        violations.append(f"Bullet {i+1} too long: {len(bullet)} > {MAX_BULLET_CHARS} chars")
            
            if container['type'] == 'code':
                code_obj = content.get('code', {})
                if isinstance(code_obj, list):
                     code_obj = code_obj[0] if code_obj else {}
                code = code_obj.get('code', '')
                lines = len(code.split('\n'))
                if lines > container['max_lines']:
                    violations.append(f"Code too long: {lines} lines > {container['max_lines']} lines")
                    
            if container['type'] == 'table':
                table_obj = content.get('table', {})
                rows = table_obj.get('rows', [])
                if len(rows) > container['max_rows']:
                    violations.append(f"Table too many rows: {len(rows)} > {container['max_rows']}")

        if not violations:
            return slide
        
        # For code-only violations, skip AI refinement and go straight to truncation
        # This saves significant time since code truncation is deterministic
        code_only_violation = len(violations) == 1 and 'Code too long' in violations[0]
        if code_only_violation:
            logger.warning(f"⚠️ Slide '{slide.get('title')}' has code overflow - using fast truncation (skipping AI)")
            self._force_truncate(slide, layout_spec)
            return slide
            
        # Refinement Loop (Max 1 retry for non-code issues to save time)
        logger.warning(f"⚠️ Slide '{slide.get('title')}' failed validation: {violations}. Attempting refinement...")
        
        for attempt in range(1):  # Reduced from 2 to 1 to save time
            refinement_prompt = f"""
            CRITICAL LAYOUT VIOLATION in slide '{slide.get('title')}':
            {', '.join(violations)}
            
            Based on layout '{layout_key}', you MUST condense the content to fit.
            - Remove less important bullets.
            - Summarize text.
            - Truncate code if necessary.
            
            Return ONLY the corrected JSON for this single slide. NO markdown fences, NO explanation text.
            """
            
            try:
                # Ask agent to fix
                fixed_response = agent(refinement_prompt)
                
                # Extract text from response (same as main generation)
                response_text = ""
                if hasattr(fixed_response, 'message'):
                    msg = fixed_response.message
                    if hasattr(msg, 'content'):
                        content = msg.content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and 'text' in block:
                                    response_text += block['text']
                                else:
                                    response_text += str(block)
                        else:
                            response_text = str(content)
                    else:
                        response_text = str(msg)
                else:
                    response_text = str(fixed_response)
                
                response_text = response_text.strip()
                
                # ROBUST markdown fence stripping - handle various formats
                import re
                # Remove ```json or ``` at start (with optional language tag)
                response_text = re.sub(r'^```\w*\s*\n?', '', response_text, flags=re.MULTILINE)
                # Remove ``` at end
                response_text = re.sub(r'\n?```\s*$', '', response_text, flags=re.MULTILINE)
                response_text = response_text.strip()
                
                # Parse JSON
                start_idx = response_text.find('{')
                if start_idx != -1:
                    import json
                    parsed, _ = json.JSONDecoder().raw_decode(response_text[start_idx:])
                    fixed_slide = parsed.get('slides', [parsed])[0] if 'slides' in parsed else parsed
                    
                    # Accept fix if structure is valid
                    if fixed_slide and 'content' in fixed_slide:
                        logger.info(f"✅ Slide fixed on attempt {attempt+1}")
                        return fixed_slide
            except Exception as e:
                logger.error(f"Refinement failed: {e}")
        
        # If still failing, force truncate (Last Resort)
        logger.error(f"❌ Refinement failed for '{slide.get('title')}', performing hard truncation.")
        self._force_truncate(slide, layout_spec)
        return slide

    def _force_truncate(self, slide: Dict, layout_spec: Dict):
        """Hard truncates content to fit limits (both bullet count and bullet length)."""
        MAX_BULLET_CHARS = 100  # Must match validation constant
        
        for container in layout_spec['containers']:
             if container['type'] == 'text':
                 bullets = slide.get('content', {}).get('bullets', [])
                 # First truncate by count
                 bullets = bullets[:container['max_bullets']]
                 # Then truncate individual bullets that are too long
                 truncated_bullets = []
                 for bullet in bullets:
                     if len(bullet) > MAX_BULLET_CHARS:
                         truncated_bullets.append(bullet[:MAX_BULLET_CHARS - 3] + "...")
                     else:
                         truncated_bullets.append(bullet)
                 slide['content']['bullets'] = truncated_bullets
             if container['type'] == 'code':
                 code_obj = slide.get('content', {}).get('code', {})
                 code = code_obj.get('code', '')
                 lines = code.split('\n')
                 slide['content']['code']['code'] = '\n'.join(lines[:container['max_lines']]) + "\n# ... (truncated)"
             if container['type'] == 'table':
                 table_obj = slide.get('content', {}).get('table', {})
                 rows = table_obj.get('rows', [])
                 slide['content']['table']['rows'] = rows[:container['max_rows']]



def generate_complete_course(
    book_data: Dict,
    model,
    slides_per_lesson: int = 5,
    style: str = 'professional',
    is_first_batch: bool = True,
    lesson_batch_start: int = 1,
    lesson_batch_end: int = None,
    total_lessons: int = None,
    max_processing_time: int = 840,
    course_bucket: Optional[str] = None,
    project_folder: Optional[str] = None
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
    lab_guides = load_lab_guides_from_s3(course_bucket, project_folder)
    used_lab_guide_keys = set()
    processed_lab_activity_titles = set()

    # ── Helper: emit module-end slides (references, chapter summary, logo) ──
    def _emit_module_end_slides(mod_num, mod_title, sc):
        """Add end-of-module slides and return updated slide_counter."""
        logger.info(f"📚 Adding End-of-Module slides for Module {mod_num}")
        refs = module_references_by_number.get(mod_num, [])
        title_ref = mod_title or f"{'Capítulo' if is_spanish else 'Module'} {mod_num}"

        if 'outline_modules' in book_data:
            outline_modules = book_data.get('outline_modules', [])
            if mod_num <= len(outline_modules):
                m_info = outline_modules[mod_num - 1]
                title_ref = m_info.get('title', title_ref)

                for activity in m_info.get('lab_activities', []):
                    a_title = activity.get('title', 'Lab Activity')
                    norm_a = _normalize_text(a_title)
                    if norm_a in processed_lab_activity_titles:
                        continue
                    best_g = select_best_lab_guide(
                        activity_title=a_title, module_number=mod_num,
                        lab_guides=lab_guides, used_guide_keys=used_lab_guide_keys
                    )
                    lab_data = {
                        'title': a_title,
                        'description': activity.get('description', ''),
                        'objectives': activity.get('objectives', []),
                        'duration_minutes': activity.get('duration_minutes'),
                    }
                    if best_g:
                        lab_data['lab_guide'] = best_g.get('content', '')
                        if lab_data.get('duration_minutes') is None:
                            lab_data['duration_minutes'] = best_g.get('duration_minutes')
                        used_lab_guide_keys.add(best_g.get('key'))
                        logger.info(f"🧪 Using lab guide for activity '{a_title}': {best_g.get('key')}")
                    lab_act_slides = create_lab_slides_from_content(lab_data, is_spanish, sc)
                    for ls in lab_act_slides:
                        ls['module_number'] = mod_num
                        all_slides.append(ls)
                    sc += len(lab_act_slides)
                    processed_lab_activity_titles.add(norm_a)
                    logger.info(f"✅ Added {len(lab_act_slides)} lab activity slide(s) for: {a_title}")

                if not refs:
                    refs = m_info.get('references', [])
            else:
                if not refs:
                    refs = []

        ref_slides = create_references_slides(
            module_title=title_ref, references=refs,
            is_spanish=is_spanish, slide_counter=sc
        )
        all_slides.extend(ref_slides)
        sc += len(ref_slides)

        r_items = _resumen_items_by_module.get(mod_num, [])
        if r_items:
            summary_slide = create_chapter_summary_slide(
                mod_num, r_items, title_ref, is_spanish, sc
            )
            all_slides.append(summary_slide)
            sc += 1
            logger.info(f"📋 Added chapter summary slide for Module {mod_num}")

        all_slides.append(create_module_end_logo_slide(sc))
        sc += 1
        return sc

    # Add introduction slides ONLY for first batch
    if is_first_batch:
        course_metadata = book_data.get('course_metadata', {})
        if course_metadata:
            logger.info(f"📋 Adding introduction slides (first batch)")
            intro_slides, slide_counter = create_introduction_slides(course_metadata, is_spanish, slide_counter)
            all_slides.extend(intro_slides)
            logger.info(f"✅ Added {len(intro_slides)} introduction slides (includes copyright)")
        
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

    # Build a set of modules that were already processed in PREVIOUS batches
    # to avoid creating duplicate module-title slides across batch boundaries
    _already_titled_modules = set()
    if lesson_batch_start > 1:
        # Check which modules had lessons in earlier batches
        for mod in book_data.get('modules', []):
            mod_num = mod.get('module_number', 0)
            for li, _les in enumerate(mod.get('lessons', [])):
                # Global lesson index (1-based)
                global_idx = sum(len(m.get('lessons',[])) for m in book_data.get('modules',[]) if m.get('module_number',0) < mod_num) + li + 1
                if global_idx < lesson_batch_start:
                    _already_titled_modules.add(mod_num)

    # Bookend lesson titles to skip (Introducción, Resumen del Capítulo)
    _bookend_titles = {'introducción', 'introduction', 'resumen del capítulo',
                       'chapter summary', 'resumen', 'summary'}
    _resumen_titles = {'resumen del capítulo', 'chapter summary', 'resumen', 'summary'}
    _resumen_items_by_module = {}  # module_num -> list of summary items
    lessons_processed = 0
    module_references_by_number = {}
    
    # REMOVED: lab_titles set no longer needed - labs are detected by lesson type field

    
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
        
        # BOOK-DRIVEN MODULE DETECTION: Use module_number change, not title matching
        # When module_number changes, we've entered a new module
        if current_module_number != last_module_number:
            logger.info(f"📚 Module change detected: {last_module_number} -> {current_module_number}")

            # Enrich the lesson dict with module_title from outline if not already set
            if not lesson.get('module_title') and 'outline_modules' in book_data:
                outline_modules = book_data.get('outline_modules', [])
                if current_module_number <= len(outline_modules):
                    mod_info = outline_modules[current_module_number - 1]
                    lesson['module_title'] = mod_info.get('title', '')

            # Only create module-title if NOT already created in a previous batch
            if current_module_number not in _already_titled_modules:
                module_slide = create_module_title_slide_from_lesson(lesson, current_module_number, is_spanish, slide_counter)
                all_slides.append(module_slide)
                slide_counter += 1
                _already_titled_modules.add(current_module_number)
            else:
                logger.info(f"   ⏭️ Skipping duplicate module-title for module {current_module_number} (already created in previous batch)")

            last_module_number = current_module_number
            lesson_number_in_module = 0
        
        # Get module title for lesson subtitle (from lesson metadata or generate)
        current_module_title = lesson.get('module_title', f"{'Capítulo' if is_spanish else 'Module'} {current_module_number}")

        # Collect bibliography/references from lesson content to build module-level references slides
        lesson_references = extract_references_from_lesson_content(lesson.get('content', ''))
        if lesson_references:
            module_references_by_number.setdefault(current_module_number, []).extend(lesson_references)
        
        # Always get module title for lesson subtitle (without adding the slide again)
        # Check if we didn't just get it above
        if not current_module_title and 'outline_modules' in book_data:
            outline_modules = book_data.get('outline_modules', [])
            if current_module_number <= len(outline_modules):
                module_info = outline_modules[current_module_number - 1]
                current_module_title = module_info.get('title', '')

        # SKIP BOOKEND LESSONS (Introducción, Resumen del Capítulo)
        # Their content was already used for the module-title slide (objectives)
        # but they should NOT produce their own slides
        if lesson_title.lower().strip() in _bookend_titles:
            # Capture Resumen content for chapter summary slide
            if lesson_title.lower().strip() in _resumen_titles:
                resumen_items = _extract_resumen_items(lesson.get('content', ''))
                if resumen_items:
                    _resumen_items_by_module[current_module_number] = resumen_items
                    logger.info(f"   📋 Captured {len(resumen_items)} summary items for Module {current_module_number}")
            logger.info(f"   ⏭️ Skipping bookend lesson: {lesson_title}")
            lessons_processed += 1

            # Module-end check: bookends can be the last lesson of a module/batch
            _bk_is_last = lesson_idx >= len(batch_lessons) + lesson_batch_start - 1
            _bk_next_mod = None
            if not _bk_is_last and lesson_idx - lesson_batch_start + 1 < len(batch_lessons):
                _bk_next = batch_lessons[lesson_idx - lesson_batch_start + 1]
                _bk_next_mod = _bk_next.get('module_number', 1)
            if _bk_is_last or (_bk_next_mod is not None and _bk_next_mod != current_module_number):
                slide_counter = _emit_module_end_slides(
                    current_module_number, current_module_title, slide_counter)
            continue

        # BOOK-DRIVEN LAB DETECTION: Check lesson type field instead of title matching
        lesson_type = lesson.get('type', 'lesson').lower()
        lesson_title_lower = lesson_title.lower().strip()
        lesson_content_lower = lesson.get('content', '').lower()
        has_lab_markers = (
            '## laboratorio' in lesson_content_lower or
            '## práctica' in lesson_content_lower or
            '## practica' in lesson_content_lower or
            '## lab activity' in lesson_content_lower or
            '## laboratory' in lesson_content_lower or
            'guía de laboratorio' in lesson_content_lower or
            'guia de laboratorio' in lesson_content_lower
        )
        
        # Detect lab lessons by type field OR title patterns
        is_lab_lesson = (
            lesson_type in ['lab', 'practice', 'activity', 'lab_activity', 'laboratorio', 'práctica'] or
            lesson_title_lower.startswith('laboratorio') or
            lesson_title_lower.startswith('lab ') or
            lesson_title_lower.startswith('lab:') or
            lesson_title_lower.startswith('práctica') or
            lesson_title_lower.startswith('actividad') or
            has_lab_markers
        )
        
        # Increment lesson number within module
        lesson_number_in_module += 1
        
        if is_lab_lesson:
            # PROCESS LABS INLINE - Generate lab intro and result slides
            logger.info(f"\n🧪 Processing Lab Lesson {lesson_idx}: {lesson_title}")
            best_guide = select_best_lab_guide(
                activity_title=lesson_title,
                module_number=current_module_number,
                lab_guides=lab_guides,
                used_guide_keys=used_lab_guide_keys
            )

            if best_guide:
                lesson['lab_guide'] = best_guide.get('content', '')
                if lesson.get('duration_minutes') is None and best_guide.get('duration_minutes') is not None:
                    lesson['duration_minutes'] = best_guide.get('duration_minutes')
                used_lab_guide_keys.add(best_guide.get('key'))
                logger.info(f"   📄 Matched lab guide: {best_guide.get('key')}")

            lab_slides = create_lab_slides_from_content(lesson, is_spanish, slide_counter)
            for lab_slide in lab_slides:
                lab_slide['lesson_number'] = lesson_idx
                lab_slide['lesson_title'] = lesson_title
                lab_slide['module_number'] = current_module_number
                all_slides.append(lab_slide)
                slide_counter += 1
            processed_lab_activity_titles.add(_normalize_text(lesson_title))
            logger.info(f"✅ Added {len(lab_slides)} lab slides for: {lesson_title}")
            lessons_processed += 1
            continue  # Skip normal lesson processing for labs
        
        # Add lesson title slide (for theory lessons)
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
        
        # Suppress per-lesson summary/Resumen slides (chapter summary added separately)
        lesson_slides = [s for s in lesson_slides if not _is_lesson_summary_slide(s)]
        
        # Update slide numbers
        for slide in lesson_slides:
            slide['slide_number'] = slide_counter
            slide['lesson_number'] = lesson_idx
            slide['lesson_title'] = lesson_title
            slide['module_number'] = current_module_number
            all_slides.append(slide)
            slide_counter += 1
        
        # REMOVED: Old outline-based module-end logic
        # Module-end slides will be added when module_number changes (detected in next iteration)
        # or at the very end of processing
        
        # REMOVED: Per-lesson logo slides
        # Only module-end logo slides will be kept
        
        lessons_processed += 1
        logger.info(f"✅ Completed lesson {lesson_idx} - Total slides: {len(all_slides)}")
        
        # Check if NEXT lesson will be a different module (or this is the last lesson)
        # If so, add module-end slides for the current module
        is_last_lesson = lesson_idx >= len(batch_lessons) + lesson_batch_start - 1
        next_lesson_module = None
        if not is_last_lesson and lesson_idx - lesson_batch_start + 1 < len(batch_lessons):
            next_lesson = batch_lessons[lesson_idx - lesson_batch_start + 1]
            next_lesson_module = next_lesson.get('module_number', 1)
        
        if is_last_lesson or (next_lesson_module is not None and next_lesson_module != current_module_number):
            slide_counter = _emit_module_end_slides(
                current_module_number, current_module_title, slide_counter)

    
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
        
        # Add Glossary slide(s) before closing
        glossary_md = book_data.get('metadata', {}).get('course_glossary', '')
        if not glossary_md:
            # Try from special_sections
            for ss in book_data.get('special_sections', []):
                if isinstance(ss, dict) and 'glosario' in (ss.get('title', '') or '').lower():
                    glossary_md = ss.get('content', '')
                    break
        glossary_items = _parse_glossary_items(glossary_md)
        if glossary_items:
            glos_slides = create_glossary_slides(glossary_items, is_spanish, slide_counter)
            all_slides.extend(glos_slides)
            slide_counter += len(glos_slides)
            logger.info(f"📖 Added {len(glos_slides)} glossary slide(s) with {len(glossary_items)} terms")
        
        # Add Final Thank You slide (Gracias)
        final_thank_you = create_thank_you_slide(is_spanish, slide_counter)
        all_slides.append(final_thank_you)
        slide_counter += 1
        logger.info(f"🏁 Added Final Thank You slide")
    else:
        logger.info(f"⏭️  INTERMEDIATE BATCH: lesson_batch_end={lesson_batch_end} < total_lessons={course_total_lessons}")
    
    # Post-process: Fix image-only slides by adding contextual bullets
    try:
        from infographic_generator import fix_image_only_slides
        original_count = len(all_slides)
        all_slides = fix_image_only_slides(all_slides, is_spanish)
        logger.info(f"🖼️ Post-processed {original_count} slides with fix_image_only_slides")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import fix_image_only_slides: {e}")
    except Exception as e:
        logger.warning(f"⚠️ fix_image_only_slides failed: {e}")
    
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

    # Corporate intro assets (logo/Assets)
    corporate_asset_files = {
        'cover': 'Portada.jpg',
        'countries': 'Paises.png',
        'intellectual': 'Propiedad_Intelectual.png',
        'description': 'Descripcion_Curso.jpg',
        'objectives': 'Objetivos.jpg',
        'prerequisites': 'Prerrequisitos.png',
        'audience': 'Audiencia.png',
        'group': 'Presentacion.png'
    }

    def _asset_url_from_s3(*filenames: str) -> str:
        safe_filenames = [f for f in filenames if f]
        if not safe_filenames:
            return ''

        for filename in safe_filenames:
            asset_key = f"logo/Assets/{filename}"
            try:
                # Validate existence first so we can fallback across filename variants
                s3_client.head_object(Bucket='crewai-course-artifacts', Key=asset_key)
                return s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': 'crewai-course-artifacts', 'Key': asset_key},
                    ExpiresIn=3600
                )
            except Exception:
                continue

        # Last-resort direct URL for first candidate
        first = safe_filenames[0]
        return f"https://crewai-course-artifacts.s3.amazonaws.com/logo/Assets/{quote(first)}"

    corporate_assets = {
        'cover': _asset_url_from_s3(corporate_asset_files['cover']),
        'countries': _asset_url_from_s3(corporate_asset_files['countries']),
        'intellectual': _asset_url_from_s3('Propiedad_Intelectual.png', 'Propiedad_Intelectual.svg'),
        'description': _asset_url_from_s3(corporate_asset_files['description']),
        'objectives': _asset_url_from_s3(corporate_asset_files['objectives']),
        'prerequisites': _asset_url_from_s3(corporate_asset_files['prerequisites']),
        'audience': _asset_url_from_s3(corporate_asset_files['audience']),
        # Support both names, prefer non-accented as requested
        'group': _asset_url_from_s3('Presentacion.png', 'Presentación.png')
    }
    
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
            font-family: 'Neue Haas Grotesk Text Pro', 'Helvetica Neue', Arial, sans-serif;
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
            /* Note: overflow visible to allow modal popup */
        }}
        
        /* Slide header - corporate template: yellow accent bar on left, no gradient */
        .slide-header {{
            padding: 30px 50px 20px 70px;
            background: transparent;
            color: {colors['primary']};
            min-height: 90px;
            position: relative;
            z-index: 10;
            border-bottom: 2px solid #d0d0d0;
        }}

        .slide-header::before {{
            content: '';
            position: absolute;
            left: 42px;
            top: 22px;
            bottom: 22px;
            width: 8px;
            background: {colors['accent']};
            border-radius: 2px;
        }}
        
        .slide-title {{
            font-size: 30pt;
            font-weight: 700;
            margin-bottom: 6px;
            line-height: 1.2;
            color: {colors['primary']};
        }}
        
        .slide-subtitle {{
            font-size: 20pt;
            opacity: 0.8;
            line-height: 1.3;
            color: {colors['secondary']};
        }}
        
        /* Content area */
        .slide-content {{
            padding: 20px 50px 40px 50px;
            max-height: 560px; /* 720 - 90 header - 30 footer - 40 padding */
            overflow: hidden;
            position: relative;
        }}
        
        .slide-content.with-subtitle {{
            max-height: 540px;
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
            color: {colors['accent']};
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
            margin: 20px 0 60px 0; /* Extra bottom margin for logo clearance */
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
        
        /* Code blocks - dark theme for professional appearance */
        .code-block {{
            background: #1e1e1e;
            border-radius: 8px;
            margin: 10px 0 20px 0;
            overflow: hidden;
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'Consolas', monospace;
            position: relative;
            /* Height controlled by layout - no max-height here */
        }}
        
        /* Code block in text-code layout (with bullets above) */
        .layout-text-code .code-block {{
            max-height: 320px; /* Reduced to leave space for logo */
            overflow: hidden;
        }}
        
        /* Code block in code-full layout (standalone) */
        .layout-code-full .code-block,
        .slide-content:not(.layout-text-code) .code-block {{
            max-height: 440px; /* Reduced to leave space for logo */
            overflow: hidden;
        }}
        
        .code-block-header {{
            background: #2d2d2d;
            padding: 8px 16px;
            font-size: 12pt;
            color: #9cdcfe;
            font-weight: 500;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .code-block-language {{
            background: {colors['accent']};
            color: {colors['primary']};
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10pt;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .code-zoom-btn {{
            background: #f5a623;
            border: none;
            color: #1e1e1e;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12pt;
            font-weight: 600;
            transition: background 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            position: relative;
            z-index: 200;
            pointer-events: auto;
            text-decoration: none;
        }}
        
        .code-zoom-btn:hover {{
            background: #4d4d4d;
        }}
        
        .code-content {{
            padding: 12px 16px;
            overflow-x: auto;
            overflow-y: auto;
            /* Height inherited from parent .code-block minus header (~45px) */
        }}
        
        /* Code content heights based on layout - reduced to avoid logo overlap */
        .layout-text-code .code-content {{
            max-height: 280px; /* Reduced from 300 */
        }}
        
        .layout-code-full .code-content,
        .slide-content:not(.layout-text-code) .code-content {{
            max-height: 400px; /* Reduced from 420 */
        }}
        
        .code-content pre {{
            margin: 0;
            padding: 0;
            background: transparent;
        }}
        
        .code-content code {{
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'Consolas', monospace;
            font-size: 13pt;
            line-height: 1.5;
            white-space: pre;
            display: block;
            color: #f8f8f2; /* Light text for dark background - prevents invisible black text */
        }}
        
        /* Pygments uses inline styles, but we ensure base text color */
        .code-content code span {{
            font-family: inherit;
        }}
        
        /* Override any black text from Pygments to ensure visibility */
        .code-content code span[style*="color: #000"],
        .code-content code span[style*="color:#000"],
        .code-content code span[style*="color: black"],
        .code-content code span[style*="color:black"] {{
            color: #f8f8f2 !important;
        }}
        
        /* Code fullscreen modal - MAX Z-INDEX for iframe visibility */
        .code-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            z-index: 2147483647; /* Max z-index to break out of iframe stacking */
            justify-content: center;
            align-items: center;
            padding: 40px;
        }}
        
        .code-modal.active {{
            display: flex;
        }}
        
        .code-modal-content {{
            background: #1e1e1e;
            border-radius: 12px;
            max-width: 95%;
            max-height: 90%;
            overflow: auto;
            position: relative;
        }}
        
        .code-modal-header {{
            background: #2d2d2d;
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 1;
        }}
        
        .code-modal-close {{
            background: #e74c3c;
            border: none;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14pt;
            font-weight: 600;
        }}
        
        .code-modal-close:hover {{
            background: #c0392b;
        }}
        
        .code-modal-body {{
            padding: 20px 30px;
        }}
        
        .code-modal-body pre {{
            margin: 0;
        }}
        
        .code-modal-body code {{
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'Consolas', monospace;
            font-size: 16pt;
            line-height: 1.6;
            color: #f8f8f2;
        }}
        
        /* Images */
        .slide-image {{
            max-width: 100%;
            max-height: 450px; /* Expanded to fill available space */
            display: block;
            margin: 10px auto;
            object-fit: contain;
        }}
        
        .image-caption {{
            text-align: center;
            font-size: 16pt;
            color: #666;
            margin-top: 10px;
            font-style: italic;
        }}
        
        /* ============================================
           STRICT PREDEFINED LAYOUTS (Validated by AI)
           CRITICAL: All containers must have overflow:hidden
           to prevent content from overlapping the logo!
           ============================================ */
           
        /* L1: Text Only (1160x480) - reduced to avoid logo overlap */
        .layout-text-only .bullets {{
            max-width: 1160px;
            max-height: 440px; /* Reduced from 480 to leave space for logo */
            overflow: hidden;
        }}

        /* L2: Image Left (Img: 550x420, Text: 520x420) - reduced heights */
        .image-layout.image-left .image-column {{
            width: 550px;
            max-height: 420px; /* Reduced from 460 */
        }}
        .image-layout.image-left .slide-image {{
            max-height: 400px; /* Reduced from 460 */
            width: auto;
            max-width: 100%;
        }}
        .image-layout.image-left .bullets-column {{
            width: 520px;
            max-height: 420px; /* Reduced from 460 */
            overflow: hidden; /* CRITICAL: Clip overflowing content */
        }}
        
        /* L3: Image Right (Text: 520x420, Img: 550x420) - reduced heights */
        .image-layout.image-right .bullets-column {{
            width: 520px;
            max-height: 420px; /* Reduced from 460 */
            overflow: hidden; /* CRITICAL: Clip overflowing content */
        }}
        .image-layout.image-right .image-column {{
            width: 550px;
            max-height: 420px; /* Reduced from 460 */
        }}
        .image-layout.image-right .slide-image {{
            max-height: 400px; /* Reduced from 460 */
            width: auto;
            max-width: 100%;
        }}

        /* L4: Text + Code (Text: 1160x100, Code: 1160x340) */
        .layout-text-code .bullets {{
            max-height: 100px; /* Reduced from 120 */
            overflow: hidden;
            margin-bottom: 15px;
        }}
        .layout-text-code .code-block {{
            max-height: 320px; /* Reduced from 340 to leave space for logo */
            overflow: hidden;
        }}
        .layout-text-code .code-content {{
            max-height: 280px; /* Reduced from 300 */
            overflow: auto;
        }}
        
        /* L5: Code Only (Code: 1160x440) - reduced to avoid logo overlap */
        .layout-code-full .code-block {{
            max-height: 440px; /* Reduced from 480 */
            overflow: hidden;
        }}
        .layout-code-full .code-content {{
            max-height: 400px; /* Reduced from 440 */
            overflow: auto;
        }}
        
        /* General Utils */
        .slide-content {{
            /* Ensure we use flex/grid where appropriate if needed, 
               but for now relying on existing layout logic + these strict constraints. */
            position: relative;
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
            max-height: 480px; /* Optimized for 520px content area */
            width: auto;
            height: auto;
            object-fit: contain;
        }}
        
        /* ============================================
           LAYOUT-SPECIFIC CONTAINER SIZES
           These match the layouts.py specifications
           ============================================ */
        
        /* TEXT-ONLY Layout: Full width for bullets */
        .layout-text-only {{
            height: 520px;
            overflow: hidden;
        }}
        
        /* TEXT-CODE Layout: Bullets above, code below */
        .layout-text-code {{
            display: flex;
            flex-direction: column;
            height: 520px;
        }}
        
        .layout-text-code .text-area {{
            height: 140px;
            overflow: hidden;
        }}
        
        .layout-text-code .code-area {{
            height: 360px;
            overflow: hidden;
        }}
        
        /* CODE-FULL Layout: Large code block */
        .layout-code-full {{
            height: 520px;
        }}
        
        .layout-code-full .code-area {{
            height: 460px;
            overflow: hidden;
        }}
        
        .layout-code-full .caption-area {{
            height: 60px;
            overflow: hidden;
        }}
        
        /* IMAGE-CODE Layout: Side by side */
        .layout-image-code {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            height: 520px;
        }}
        
        .layout-image-code .image-area,
        .layout-image-code .code-area {{
            height: 520px;
            overflow: hidden;
        }}
        
        /* TABLE Layout */
        .layout-table {{
            height: 520px;
        }}
        
        .layout-table .table-area {{
            height: 440px;
            overflow: auto;
        }}
        
        .layout-table .notes-area {{
            height: 80px;
            overflow: hidden;
        }}
        
        /* Logo positioning */
        .slide-logo {{
            position: absolute;
            bottom: 10px;
            left: 22px;
            width: 150px;
            height: auto;
            opacity: 0.9;
            z-index: 500;
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
        
        /* MODULE TITLE SLIDE - Section divider (corporate template) */
        .module-title-slide {{
            height: 100%;
            background: #efefef;
            padding: 50px 60px 40px 60px;
            position: relative;
            display: grid;
            grid-template-columns: 48% 52%;
            gap: 40px;
        }}

        .module-title-left {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding-top: 0;
        }}

        .module-title-accent {{
            width: 80px;
            height: 8px;
            background: {colors['accent']};
            position: absolute;
            top: 45px;
            left: 50px;
        }}

        .module-title-chapter {{
            font-size: 54pt;
            font-weight: 800;
            color: #111;
            line-height: 1.1;
            margin-bottom: 18px;
        }}

        .module-title-divider {{
            height: 2px;
            background: #c7c7c7;
            width: 100%;
            margin: 12px 0 18px;
        }}

        .module-title-name {{
            font-size: 26pt;
            font-weight: 700;
            color: {colors['primary']};
            line-height: 1.2;
        }}

        .module-title-right {{
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            padding-top: 30px;
            padding-right: 40px;
        }}

        .module-title-obj-heading {{
            font-size: 22pt;
            font-weight: 700;
            color: #111;
            margin-bottom: 14px;
            text-align: left;
        }}

        .module-title-obj-list {{
            list-style: none;
            padding-left: 0;
            margin: 0;
        }}

        .module-title-obj-list li {{
            position: relative;
            padding-left: 34px;
            font-size: 16pt;
            color: #222;
            line-height: 1.35;
            margin: 10px 0;
        }}

        .module-title-obj-list li::before {{
            content: '•';
            position: absolute;
            left: 0;
            top: 0;
            color: {colors['accent']};
            font-size: 22px;
            line-height: 1.1;
        }}

        .module-title-slide .logo {{
            position: absolute;
            bottom: 10px;
            left: 22px;
            width: 190px;
            height: auto;
            opacity: 1;
        }}

        /* CHAPTER SUMMARY SLIDE */
        .chapter-summary-slide {{
            height: 100%;
            background: #ffffff;
            padding: 50px 60px 40px 60px;
            position: relative;
            display: grid;
            grid-template-columns: 55% 45%;
            gap: 30px;
        }}
        .chapter-summary-slide::before {{
            /* Gray divider near bottom */
            content: '';
            display: block;
            width: 100%;
            height: 2px;
            background: #c7c7c7;
            position: absolute;
            bottom: 90px;
            left: 0;
        }}
        .chapter-summary-slide::after {{
            /* Yellow accent bar at bottom */
            content: '';
            display: block;
            width: 35%;
            height: 8px;
            background: {colors['accent']};
            position: absolute;
            bottom: 82px;
            left: 60px;
        }}
        .chapter-summary-left {{
            padding-top: 10px;
        }}
        .chapter-summary-title {{
            font-size: 36pt;
            font-weight: 800;
            color: #222;
            margin-bottom: 16px;
        }}
        .chapter-summary-heading {{
            font-size: 18pt;
            font-weight: 600;
            color: #555;
            margin-bottom: 18px;
        }}
        .chapter-summary-list {{
            list-style: none;
            padding-left: 0;
            margin: 0;
        }}
        .chapter-summary-list li {{
            position: relative;
            padding-left: 30px;
            font-size: 17pt;
            color: #222;
            line-height: 1.35;
            margin: 8px 0;
        }}
        .chapter-summary-list li::before {{
            content: '•';
            position: absolute;
            left: 0;
            color: #222;
            font-size: 22px;
        }}
        .chapter-summary-right {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .chapter-summary-right img {{
            max-width: 90%;
            max-height: 80%;
            object-fit: contain;
        }}
        .chapter-summary-slide .logo {{
            position: absolute;
            bottom: 10px;
            left: 22px;
            width: 150px;
            height: auto;
        }}

        /* LAB INTRO SLIDE — corporate template (white bg, dashed title box) */
        .lab-intro-slide {{
            height: 100%;
            background: #ffffff;
            padding: 40px 60px;
            position: relative;
        }}
        .lab-intro-title-box {{
            border: 2px dashed #aaa;
            border-radius: 6px;
            padding: 28px 40px 22px;
            text-align: center;
            margin-bottom: 8px;
        }}
        .lab-intro-title {{
            font-size: 36pt;
            font-weight: 800;
            color: #111;
            line-height: 1.2;
        }}
        .lab-intro-accent {{
            width: 200px;
            height: 8px;
            background: {colors['accent']};
            margin: 10px 0 0 0;
        }}
        .lab-intro-divider {{
            width: 100%;
            height: 2px;
            background: #c7c7c7;
            margin: 0 0 22px 0;
        }}
        .lab-intro-section-heading {{
            font-size: 18pt;
            font-weight: 700;
            color: #222;
            margin-bottom: 6px;
        }}
        .lab-intro-section-body {{
            font-size: 16pt;
            color: #333;
            line-height: 1.4;
            border-left: 3px solid #ccc;
            padding-left: 14px;
            margin-bottom: 18px;
        }}
        .lab-intro-bottom {{
            position: absolute;
            bottom: 30px;
            right: 60px;
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .lab-intro-bottom img {{
            width: 80px;
            height: 80px;
            object-fit: contain;
        }}
        .lab-intro-duration-box {{
            text-align: left;
        }}
        .lab-intro-duration-label {{
            font-size: 16pt;
            font-weight: 700;
            color: #111;
        }}
        .lab-intro-duration-value {{
            font-size: 15pt;
            color: #333;
        }}
        .lab-intro-slide .logo {{
            position: absolute;
            bottom: 10px;
            left: 22px;
            width: 150px;
            height: auto;
        }}

        /* GLOSSARY SLIDE */
        .glossary-slide {{
            height: 100%;
            background: #efefef;
            padding: 40px 60px;
            position: relative;
        }}
        .glossary-slide::before {{
            content: '';
            display: block;
            width: 100%;
            height: 10px;
            background: {colors['accent']};
            position: absolute;
            top: 0;
            left: 0;
        }}
        .glossary-title {{
            font-size: 36pt;
            font-weight: 800;
            color: {colors['primary']};
            margin-bottom: 24px;
            padding-top: 10px;
        }}
        .glossary-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px 40px;
        }}
        .glossary-item {{
            display: flex;
            align-items: baseline;
            gap: 8px;
            font-size: 15pt;
            line-height: 1.3;
        }}
        .glossary-term {{
            font-weight: 700;
            color: {colors['primary']};
            white-space: nowrap;
        }}
        .glossary-def {{
            color: #444;
        }}
        .glossary-slide .logo {{
            position: absolute;
            bottom: 10px;
            left: 22px;
            width: 150px;
            height: auto;
        }}

        /* GRACIAS (CLOSING) SLIDE */
        .gracias-slide {{
            height: 100%;
            background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            text-align: center;
        }}
        .gracias-image {{
            max-width: 280px;
            max-height: 280px;
            margin-bottom: 30px;
        }}
        .gracias-title {{
            font-size: 56pt;
            font-weight: 800;
            color: white;
            margin-bottom: 20px;
        }}
        .gracias-subtitle {{
            font-size: 28pt;
            color: {colors['accent']};
            font-weight: 600;
        }}
        .gracias-slide .logo {{
            position: absolute;
            bottom: 20px;
            right: 30px;
            width: 150px;
            height: auto;
            opacity: 0.9;
        }}
        
        /* LESSON TITLE SLIDE - Topic introduction (corporate template) */
        .lesson-title-slide {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            flex-direction: column;
            height: 100%;
            background: #efefef;
            color: {colors['primary']};
            padding: 0 80px 40px 80px;
            position: relative;
        }}

        .lesson-title-slide::before {{
            content: '';
            display: block;
            width: 100%;
            height: 10px;
            background: {colors['accent']};
            position: absolute;
            top: 0;
            left: 0;
        }}

        .lesson-title-slide .title {{
            font-size: 42pt;
            font-weight: 700;
            margin-top: 80px;
            margin-bottom: 24px;
            text-align: center;
            color: #111;
            line-height: 1.15;
        }}

        .lesson-intro-divider {{
            width: 70%;
            height: 2px;
            background: #c7c7c7;
            margin: 0 auto 20px auto;
        }}

        .lesson-intro-heading {{
            font-size: 20pt;
            font-weight: 400;
            color: #333;
            margin-bottom: 12px;
        }}

        .lesson-intro-heading::before {{
            content: '•';
            margin-right: 12px;
            font-size: 22pt;
        }}

        .lesson-intro-text {{
            max-width: 900px;
            text-align: left;
            padding: 0 60px;
        }}

        .lesson-intro-text p {{
            font-size: 18pt;
            color: #444;
            line-height: 1.45;
            margin-bottom: 10px;
            text-indent: 20px;
        }}

        .lesson-title-slide .logo {{
            position: absolute;
            bottom: 10px;
            left: 22px;
            width: 190px;
            height: auto;
            opacity: 1;
        }}
        
        /* MODULE-END LOGO SLIDE - White background, centered logo, no frame */
        .module-end-logo-slide {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            background: white;
            padding: 0;
            position: relative;
        }}
        
        .module-end-logo-slide .centered-logo {{
            width: 300px;
            height: auto;
            opacity: 1;
        }}

        /* ============================================
           CORPORATE INTRODUCTION LAYOUTS
           ============================================ */
        .intro-cover-slide {{
            height: 100%;
            display: grid;
            grid-template-columns: 46% 54%;
            background: #efefef;
            position: relative;
        }}

        .intro-cover-left {{
            padding: 48px 46px 44px 60px;
            position: relative;
            overflow: visible;
            z-index: 2;
        }}

        .intro-cover-left::after {{
            content: '';
            position: absolute;
            top: -10%;
            right: -32%;
            width: 80%;
            height: 130%;
            background: rgba(255, 255, 255, 0.6);
            border-radius: 50%;
            border: 2px solid rgba(0, 0, 0, 0.04);
        }}

        .intro-global-accent {{
            position: absolute;
            left: 52px;
            top: 44px;
            width: 80px;
            height: 8px;
            background: {colors['accent']};
            z-index: 10;
        }}

        .intro-accent-bar {{
            width: 80px;
            height: 8px;
            background: {colors['accent']};
            margin-bottom: 24px;
        }}

        .intro-cover-title {{
            margin-top: 128px;
            font-size: 52pt;
            line-height: 1.06;
            font-weight: 800;
            color: {colors['primary']};
            position: relative;
            z-index: 2;
            max-width: 100%;
        }}

        .intro-cover-right {{
            padding: 56px 50px 34px 20px;
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            justify-content: flex-start;
            gap: 14px;
            z-index: 4;
        }}

        .intro-cover-main-image {{
            width: 100%;
            max-width: 640px;
            height: 565px;
            object-fit: cover;
            border: none;
        }}

        .intro-cover-countries {{
            width: 320px;
            height: auto;
            object-fit: contain;
            position: absolute;
            right: 50px;
            bottom: 32px;
            margin-top: 0;
        }}

        .intro-cover-contact {{
            position: absolute;
            right: 50px;
            bottom: 0;
            width: auto;
            text-align: right;
            font-size: 18pt;
            color: #1a1a1a;
            line-height: 1.1;
            white-space: nowrap;
            z-index: 9;
        }}

        .intro-logo-bottom-left {{
            position: absolute;
            bottom: 8px;
            left: 22px;
            width: 190px;
            height: auto;
            z-index: 10;
        }}

        .intro-content-slide {{
            height: 100%;
            background: #efefef;
            padding: 90px 48px 40px 50px;
            position: relative;
            display: grid;
            grid-template-columns: 56% 44%;
            gap: 26px;
        }}

        .intro-content-slide.group-style {{
            grid-template-columns: 52% 48%;
        }}

        .intro-main-col {{
            display: flex;
            flex-direction: column;
        }}

        .intro-content-title {{
            font-size: 46pt;
            line-height: 1.04;
            font-weight: 800;
            color: #000;
            margin-bottom: 12px;
        }}

        .intro-subtitle {{
            font-size: 24pt;
            color: #111;
            margin-bottom: 10px;
            line-height: 1.2;
        }}

        .intro-divider {{
            height: 2px;
            background: #c7c7c7;
            margin: 8px 0 16px;
        }}

        .intro-list {{
            margin: 0;
            padding-left: 0;
            list-style: none;
            max-height: 430px;
            overflow: hidden;
        }}

        .intro-list li {{
            position: relative;
            padding-left: 34px;
            font-size: 21pt;
            color: #111;
            line-height: 1.3;
            margin: 8px 0;
        }}

        .intro-list li::before {{
            content: '•';
            position: absolute;
            left: 0;
            top: 0;
            color: {colors['accent']};
            font-size: 28px;
            line-height: 1.1;
        }}

        .intro-paragraphs {{
            display: flex;
            flex-direction: column;
            gap: 16px;
            max-height: 430px;
            overflow: hidden;
        }}

        .intro-paragraphs p {{
            font-size: 21pt;
            color: #111;
            line-height: 1.28;
        }}

        .intro-right-asset {{
            width: 100%;
            max-width: 560px;
            height: 520px;
            object-fit: cover;
            justify-self: end;
        }}

        .intro-legal-slide {{
            height: 100%;
            background: #efefef;
            padding: 90px 40px 36px 42px;
            display: grid;
            grid-template-columns: 38% 62%;
            gap: 24px;
            position: relative;
        }}

        .intro-legal-icon {{
            width: 100%;
            max-width: 360px;
            max-height: 500px;
            object-fit: contain;
            align-self: center;
            justify-self: center;
        }}

        .intro-agenda-slide {{
            height: 100%;
            background: #efefef;
            position: relative;
            padding: 90px 0 0;
        }}

        .intro-agenda-wave {{
            position: absolute;
            left: 0;
            right: 0;
            top: 168px;
            height: 26px;
            background: linear-gradient(to bottom, rgba(255,255,255,0.45), rgba(220,220,220,0.25));
            border-bottom: 1px solid rgba(0,0,0,0.08);
        }}

        .intro-agenda-content {{
            position: relative;
            z-index: 2;
            padding: 18px 90px 0 102px;
        }}

        .intro-agenda-content .intro-content-title {{
            margin-bottom: 26px;
        }}

        .intro-agenda-list {{
            list-style: none;
            padding-left: 0;
            max-height: 430px;
            overflow: hidden;
        }}

        .intro-agenda-list li {{
            position: relative;
            padding-left: 34px;
            font-size: 34px;
            line-height: 1.18;
            margin: 14px 0;
            font-weight: 400;
            color: #111;
        }}

        .intro-agenda-list li::before {{
            content: '•';
            position: absolute;
            left: 0;
            top: 0;
            color: {colors['accent']};
            font-size: 30px;
            line-height: 1.12;
        }}

        .agenda-chapter-prefix {{
            font-weight: 800;
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
        '''    <script>
        // Code block zoom functionality - inline for maximum compatibility
        function openCodeModal(codeId) {
            console.log('openCodeModal called with:', codeId);
            
            var codeBlock = document.getElementById(codeId);
            var modal = document.getElementById('codeModal');
            var modalBody = document.getElementById('codeModalBody');
            var modalLang = document.getElementById('codeModalLang');
            
            if (!codeBlock) {
                console.error('Code block not found: ' + codeId);
                return;
            }
            if (!modal) {
                console.error('Modal not found');
                return;
            }
            
            var codeContent = codeBlock.querySelector('.code-content');
            var langBadge = codeBlock.querySelector('.code-block-language');
            
            if (codeContent && modalBody) {
                modalBody.innerHTML = codeContent.innerHTML;
            }
            if (langBadge && modalLang) {
                modalLang.textContent = langBadge.textContent;
            }
            
            modal.classList.add('active');
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            console.log('Modal opened successfully');
        }
        
        function closeCodeModal() {
            var modal = document.getElementById('codeModal');
            if (modal) {
                modal.classList.remove('active');
                modal.style.display = 'none';
                document.body.style.overflow = '';
            }
        }
        
        // Make functions globally available
        window.openCodeModal = openCodeModal;
        window.closeCodeModal = closeCodeModal;
        
        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeCodeModal();
            }
        });
        
        // Close on click outside modal content
        document.addEventListener('click', function(e) {
            var modal = document.getElementById('codeModal');
            if (e.target === modal) {
                closeCodeModal();
            }
        });
        </script>''',
        '</head>',
        '<body>',
        '''    <!-- Code fullscreen modal -->
    <div id="codeModal" class="code-modal">
        <div class="code-modal-content">
            <div class="code-modal-header">
                <span id="codeModalLang" class="code-block-language">CODE</span>
                <button class="code-modal-close" onclick="closeCodeModal()">✕ Close</button>
            </div>
            <div id="codeModalBody" class="code-modal-body"></div>
        </div>
    </div>''',
        f'    <h1 style="text-align: center; color: {colors["primary"]}; margin-bottom: 30px; font-size: 32pt;">{course_title}</h1>',
    ]
    
    # Use presigned logo URL
    logo_url = logo_presigned_url
    
    def _format_intro_agenda_item(item_text: str) -> str:
        raw = str(item_text or '').strip()
        if not raw:
            return ''

        chapter_match = re.match(r'^\s*((?:Cap[ií]tulo|Chapter|Module)\s+\d+\s*:)\s*(.*)$', raw, flags=re.IGNORECASE)
        if not chapter_match:
            return html_module.escape(raw)

        prefix = html_module.escape(chapter_match.group(1).strip())
        remainder = html_module.escape(chapter_match.group(2).strip())
        return f'<span class="agenda-chapter-prefix">{prefix}</span> {remainder}'

    # Generate each slide
    for slide_idx, slide in enumerate(slides, 1):
        layout = slide.get('layout') or slide.get('layout_hint', 'single-column')
        title = slide.get('title', '')
        subtitle = slide.get('subtitle', '')
        notes = slide.get('notes', '')
        
        html_parts.append(f'<div class="slide" data-slide="{slide_idx}">')
        
        # Special layouts for title slides
        if layout == 'intro-cover':
            html_parts.append('  <div class="intro-cover-slide">')
            html_parts.append('    <div class="intro-global-accent"></div>')
            html_parts.append('    <div class="intro-cover-left">')
            html_parts.append(f'      <div class="intro-cover-title">{title}</div>')
            html_parts.append(f'      <img src="{logo_url}" class="intro-logo-bottom-left" alt="Netec Logo">')
            html_parts.append('    </div>')
            html_parts.append('    <div class="intro-cover-right">')
            html_parts.append(f'      <img src="{corporate_assets["cover"]}" class="intro-cover-main-image" alt="Portada">')
            html_parts.append(f'      <img src="{corporate_assets["countries"]}" class="intro-cover-countries" alt="Países">')
            html_parts.append('      <div class="intro-cover-contact">www.netec.com | servicio@netec.com</div>')
            html_parts.append('    </div>')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout == 'intro-intellectual-property':
            legal_items = []
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'bullets':
                    legal_items.extend(block.get('items', []))

            html_parts.append('  <div class="intro-legal-slide">')
            html_parts.append('    <div class="intro-global-accent"></div>')
            html_parts.append(f'    <img src="{corporate_assets["intellectual"]}" class="intro-legal-icon" alt="Propiedad Intelectual">')
            html_parts.append('    <div class="intro-main-col">')
            html_parts.append(f'      <div class="intro-content-title">{title}</div>')
            html_parts.append('      <div class="intro-divider"></div>')
            html_parts.append('      <div class="intro-paragraphs">')
            for item in legal_items:
                html_parts.append(f'        <p>{item}</p>')
            html_parts.append('      </div>')
            html_parts.append('    </div>')
            html_parts.append(f'    <img src="{logo_url}" class="intro-logo-bottom-left" alt="Netec Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout in ['intro-description', 'intro-objectives', 'intro-prerequisites', 'intro-audience', 'intro-group-presentation']:
            intro_items = []
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'bullets':
                    intro_items.extend(block.get('items', []))

            asset_by_layout = {
                'intro-description': corporate_assets['description'],
                'intro-objectives': corporate_assets['objectives'],
                'intro-prerequisites': corporate_assets['prerequisites'],
                'intro-audience': corporate_assets['audience'],
                'intro-group-presentation': corporate_assets['group']
            }

            extra_class = ' group-style' if layout == 'intro-group-presentation' else ''
            list_class = 'intro-list red-bullets' if layout == 'intro-objectives' else 'intro-list'

            html_parts.append(f'  <div class="intro-content-slide{extra_class}">')
            html_parts.append('    <div class="intro-global-accent"></div>')
            html_parts.append('    <div class="intro-main-col">')
            html_parts.append(f'      <div class="intro-content-title">{title}</div>')
            if subtitle:
                html_parts.append(f'      <div class="intro-subtitle">{subtitle}</div>')
            html_parts.append('      <div class="intro-divider"></div>')
            html_parts.append(f'      <ul class="{list_class}">')
            for item in intro_items:
                html_parts.append(f'        <li>{item}</li>')
            html_parts.append('      </ul>')
            html_parts.append('    </div>')
            html_parts.append(f'    <img src="{asset_by_layout[layout]}" class="intro-right-asset" alt="{title}">')
            html_parts.append(f'    <img src="{logo_url}" class="intro-logo-bottom-left" alt="Netec Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout == 'intro-agenda':
            agenda_items = []
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'bullets':
                    agenda_items.extend(block.get('items', []))

            html_parts.append('  <div class="intro-agenda-slide">')
            html_parts.append('    <div class="intro-global-accent"></div>')
            html_parts.append('    <div class="intro-agenda-wave"></div>')
            html_parts.append('    <div class="intro-agenda-content">')
            html_parts.append(f'      <div class="intro-content-title">{title}</div>')
            html_parts.append('      <ul class="intro-list intro-agenda-list">')
            for item in agenda_items:
                html_parts.append(f'        <li>{_format_intro_agenda_item(item)}</li>')
            html_parts.append('      </ul>')
            html_parts.append('    </div>')
            html_parts.append(f'    <img src="{logo_url}" class="intro-logo-bottom-left" alt="Netec Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout == 'chapter-summary':
            # Chapter summary slide with Resumen_Capitulo.png
            summary_items = []
            summary_heading = ""
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'bullets':
                    summary_heading = block.get('heading', '')
                    summary_items.extend(block.get('items', []))
            resumen_img_url = _asset_url_from_s3('Resumen_Capitulo.png')
            html_parts.append('  <div class="chapter-summary-slide">')
            html_parts.append('    <div class="chapter-summary-left">')
            html_parts.append(f'      <div class="chapter-summary-title">{title}</div>')
            if summary_heading:
                html_parts.append(f'      <div class="chapter-summary-heading">{summary_heading}</div>')
            if summary_items:
                html_parts.append('      <ul class="chapter-summary-list">')
                for item in summary_items:
                    html_parts.append(f'        <li>{item}</li>')
                html_parts.append('      </ul>')
            html_parts.append('    </div>')
            html_parts.append('    <div class="chapter-summary-right">')
            html_parts.append(f'      <img src="{resumen_img_url}" alt="Resumen">')
            html_parts.append('    </div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout == 'lab-intro':
            # Lab intro slide — corporate template (white bg, dashed title box)
            lab_objective = ""
            lab_duration = ""
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'bullets':
                    items = block.get('items', [])
                    heading = block.get('heading', '').lower()
                    if 'objetivo' in heading or 'objective' in heading:
                        lab_objective = items[0] if items else ""
                    elif items and not lab_objective:
                        text = items[0]
                        if 'tiempo' in text.lower() or 'estimated' in text.lower():
                            lab_duration = text
                        else:
                            lab_objective = text
            reloj_img_url = _asset_url_from_s3('Reloj.png')
            is_es = 'actividad' in (subtitle or '').lower() or 'práctica' in (subtitle or '').lower()
            obj_label = 'Objetivo:' if is_es else 'Objective:'
            dur_label = 'Tiempo para esta actividad:' if is_es else 'Time for this activity:'
            html_parts.append('  <div class="lab-intro-slide">')
            html_parts.append('    <div class="lab-intro-title-box">')
            html_parts.append(f'      <div class="lab-intro-title">{title}</div>')
            html_parts.append('    </div>')
            html_parts.append('    <div class="lab-intro-accent"></div>')
            html_parts.append('    <div class="lab-intro-divider"></div>')
            if lab_objective:
                html_parts.append(f'    <div class="lab-intro-section-heading">{obj_label}</div>')
                html_parts.append(f'    <div class="lab-intro-section-body">{lab_objective}</div>')
            html_parts.append('    <div class="lab-intro-bottom">')
            html_parts.append(f'      <img src="{reloj_img_url}" alt="Reloj">')
            if lab_duration:
                # Extract just the time value from "Tiempo estimado: 30 minutos"
                dur_val = lab_duration
                if ':' in dur_val:
                    dur_val = dur_val.split(':', 1)[1].strip()
                html_parts.append('      <div class="lab-intro-duration-box">')
                html_parts.append(f'        <div class="lab-intro-duration-label">{dur_label}</div>')
                html_parts.append(f'        <div class="lab-intro-duration-value">{dur_val}</div>')
                html_parts.append('      </div>')
            html_parts.append('    </div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout == 'glossary':
            # Glossary slide with term-definition grid
            glossary_items = []
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'glossary':
                    glossary_items.extend(block.get('items', []))
            html_parts.append('  <div class="glossary-slide">')
            html_parts.append(f'    <div class="glossary-title">{title}</div>')
            html_parts.append('    <div class="glossary-grid">')
            for item in glossary_items:
                term = item.get('term', '') if isinstance(item, dict) else str(item)
                definition = item.get('definition', '') if isinstance(item, dict) else ''
                html_parts.append('      <div class="glossary-item">')
                html_parts.append(f'        <span class="glossary-term">{term}</span>')
                if definition:
                    html_parts.append(f'        <span class="glossary-def">– {definition}</span>')
                html_parts.append('      </div>')
            html_parts.append('    </div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout == 'gracias':
            # Gracias closing slide with Gracias.png
            gracias_img_url = _asset_url_from_s3('Gracias.png')
            html_parts.append('  <div class="gracias-slide">')
            html_parts.append(f'    <img src="{gracias_img_url}" class="gracias-image" alt="Gracias">')
            html_parts.append(f'    <div class="gracias-title">{title}</div>')
            if subtitle:
                html_parts.append(f'    <div class="gracias-subtitle">{subtitle}</div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue

        elif layout == 'course-title':
            html_parts.append('  <div class="course-title-slide">')
            html_parts.append(f'    <div class="title">{title}</div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue
        
        elif layout == 'module-title':
            # Parse module number from slide data or title
            mod_num = slide.get('module_number', '')
            # Detect language from title pattern
            is_es = bool(re.search(r'(?:M[oó]dulo|Cap[ií]tulo)', title, re.IGNORECASE))
            # Try to split "Módulo 1: Nombre" into chapter label + name
            mod_match = re.match(r'^(?:M[oó]dulo|Cap[ií]tulo|Module|Chapter)\s+(\d+)\s*:\s*(.+)$', title, re.IGNORECASE)
            if mod_match:
                chapter_label = f"{'Capítulo' if is_es else 'Chapter'} {mod_match.group(1)}"
                chapter_name = mod_match.group(2).strip()
            else:
                chapter_label = f"{'Capítulo' if is_es else 'Chapter'} {mod_num}" if mod_num else title
                chapter_name = title if mod_num else ''
            
            # Extract objectives from content_blocks
            obj_items = []
            obj_heading = "Objetivos:" if is_es else "Objectives:"
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'bullets':
                    if block.get('heading'):
                        obj_heading = block['heading']
                    obj_items.extend(block.get('items', []))
            
            html_parts.append('  <div class="module-title-slide">')
            html_parts.append('    <div class="module-title-left">')
            html_parts.append('      <div class="module-title-accent"></div>')
            html_parts.append(f'      <div class="module-title-chapter">{chapter_label}</div>')
            html_parts.append('      <div class="module-title-divider"></div>')
            html_parts.append(f'      <div class="module-title-name">{chapter_name}</div>')
            html_parts.append('    </div>')
            html_parts.append('    <div class="module-title-right">')
            if obj_items:
                html_parts.append(f'      <div class="module-title-obj-heading">{obj_heading}</div>')
                html_parts.append('      <ul class="module-title-obj-list">')
                for item in obj_items:
                    html_parts.append(f'        <li>{item}</li>')
                html_parts.append('      </ul>')
            html_parts.append('    </div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue
        
        elif layout == 'lesson-title':
            # Extract introduction text from content_blocks if available
            intro_items = []
            for block in slide.get('content_blocks', []):
                if block.get('type') == 'bullets':
                    intro_items.extend(block.get('items', []))
            
            # Extract heading and items for lesson-title intro
            intro_heading = ''
            for block in slide.get('content_blocks', []):
                if block.get('heading'):
                    intro_heading = block['heading']
                    break

            html_parts.append('  <div class="lesson-title-slide">')
            html_parts.append(f'    <div class="title">{title}</div>')
            if intro_items or intro_heading:
                html_parts.append('    <div class="lesson-intro-divider"></div>')
                if intro_heading:
                    html_parts.append(f'    <div class="lesson-intro-heading">{intro_heading}</div>')
                if intro_items:
                    html_parts.append('    <div class="lesson-intro-text">')
                    for item in intro_items:
                        html_parts.append(f'      <p>{item}</p>')
                    html_parts.append('    </div>')
            html_parts.append(f'    <img src="{logo_url}" class="logo" alt="Logo">')
            html_parts.append('  </div>')
            if notes:
                html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
            html_parts.append('</div>')
            continue
        
        elif layout == 'module-end-logo':
            # Special module-end slide: white background, large centered logo, no frame
            html_parts.append('  <div class="module-end-logo-slide">')
            html_parts.append(f'    <img src="{logo_url}" class="centered-logo" alt="Netec Logo">')
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
            html_parts.append(f'  <div class="slide-content layout-{layout}">')
            
            logger.info(f"🔍 DEBUG: Slide {slide_idx} '{title}' has {len(slide.get('content_blocks', []))} content blocks")
            
            for block_idx, block in enumerate(slide.get('content_blocks', []), 1):
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
                
                elif block_type == 'code':
                    # Render code block with Pygments syntax highlighting (VS Code-like)
                    heading = block.get('heading', '')
                    language = block.get('language', 'text').lower()
                    code = block.get('code', '')
                    
                    # Generate unique ID for zoom functionality
                    code_block_id = f'code-{slide_idx}-{block_idx}'
                    
                    # Use Pygments for syntax highlighting
                    highlighted_code = highlight_code_with_pygments(code, language)
                    
                    if heading:
                        html_parts.append(f'    <div class="content-heading">{heading}</div>')
                    
                    html_parts.append(f'    <div class="code-block" id="{code_block_id}">')
                    
                    # Add header with language badge and zoom button
                    html_parts.append(f'      <div class="code-block-header">')
                    if language and language != 'text':
                        html_parts.append(f'        <span class="code-block-language">{language}</span>')
                    else:
                        html_parts.append(f'        <span class="code-block-language">CODE</span>')
                    html_parts.append(f'        <button type="button" class="code-zoom-btn" onclick="openCodeModal(\'{code_block_id}\'); return false;">🔍 Zoom</button>')
                    html_parts.append(f'      </div>')
                    
                    html_parts.append('      <div class="code-content">')
                    html_parts.append(f'        {highlighted_code}')
                    html_parts.append('      </div>')
                    html_parts.append('    </div>')
            
            html_parts.append('  </div>')
        
        # Add logo to regular content slides (bottom-right)
        html_parts.append(f'  <img src="{logo_url}" class="slide-logo" alt="Logo">')
        
        if notes:
            html_parts.append(f'  <div class="notes" style="display:none">{notes}</div>')
        html_parts.append('</div>')
    
    html_parts.extend([
        '</body>',
        '</html>'
    ])
    
    return '\n'.join(html_parts)
