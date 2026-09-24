"""
Server-side overflow detection for HTML slides.

This module adds data-overflow markers to slides BEFORE Visual Optimizer runs,
eliminating the need for browser execution to detect overflow.

The JavaScript in the HTML does the same thing client-side for visual feedback,
but we need server-side markers for the Visual Optimizer to work.
"""

from bs4 import BeautifulSoup
import logging

logger = logging.getLogger()


def estimate_slide_height(slide_soup) -> int:
    """
    Estimate rendered height of a slide's content.
    
    This is a Python approximation of browser rendering.
    While not 100% accurate, it's close enough to identify obvious overflows.
    """
    # Constants matching CSS/JS (from infographic_generator.py)
    BULLET_HEIGHT = 44
    HEADING_HEIGHT = 65
    IMAGE_HEIGHT = 550  # CSS max-height
    SPACING = 20
    LINE_HEIGHT = 30
    CHARS_PER_LINE = 90
    
    total_height = 0
    
    # Find content area (skip title/subtitle which are in separate positioning)
    content_elements = slide_soup.find_all(['ul', 'img', 'div'], class_=['bullets', 'image-container', 'callout', 'image-with-text'])
    
    for idx, elem in enumerate(content_elements):
        if idx > 0:
            total_height += SPACING
        
        # Bullet lists
        if 'bullets' in elem.get('class', []):
            # Check for heading
            heading = elem.find_previous_sibling(class_='block-heading')
            if heading:
                total_height += HEADING_HEIGHT
            
            # Count bullets
            bullets = elem.find_all('li')
            for bullet in bullets:
                text_len = len(bullet.get_text(strip=True))
                lines = max(1, (text_len // CHARS_PER_LINE) + 1)
                total_height += BULLET_HEIGHT * lines
        
        # Images
        elif 'image-container' in elem.get('class', []) or elem.name == 'img':
            total_height += IMAGE_HEIGHT
            # Check for caption
            caption = elem.find(class_='image-caption')
            if caption:
                total_height += 30
        
        # Image-with-text (two-column layout)
        elif 'image-with-text' in elem.get('class', []):
            # In two-column layout, height is max of text column and image
            # For simplicity, estimate as IMAGE_HEIGHT + some text
            total_height += IMAGE_HEIGHT
        
        # Callouts
        elif 'callout' in elem.get('class', []):
            text_len = len(elem.get_text(strip=True))
            lines = max(1, (text_len // CHARS_PER_LINE) + 1)
            total_height += 75 + (lines - 1) * LINE_HEIGHT
    
    return total_height


def mark_overflow_slides(html_content: str) -> str:
    """
    Parse HTML and add data-overflow markers to slides that exceed height limits.
    
    Returns modified HTML with overflow markers added.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    slides = soup.find_all('div', class_='slide')
    
    overflow_count = 0
    SLIDE_HEIGHT = 720  # Fixed slide height
    MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 460
    MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520
    
    logger.info(f"🔍 Marking overflow slides (server-side detection)")
    
    for idx, slide in enumerate(slides):
        # Skip title slides
        classes = slide.get('class', [])
        if 'course-title' in classes or 'module-title' in classes or 'lesson-title' in classes:
            continue
        
        # Check for subtitle
        subtitle = slide.find('h2', class_='slide-subtitle')
        has_subtitle = subtitle is not None and subtitle.get_text(strip=True)
        max_height = MAX_CONTENT_HEIGHT_WITH_SUBTITLE if has_subtitle else MAX_CONTENT_HEIGHT_NO_SUBTITLE
        
        # Estimate content height
        estimated_height = estimate_slide_height(slide)
        
        # Mark if overflow detected
        if estimated_height > max_height:
            overflow_amount = estimated_height - max_height
            slide['data-overflow'] = 'true'
            slide['data-overflow-amount'] = str(overflow_amount)
            slide['data-estimated-height'] = str(estimated_height)
            slide['data-max-height'] = str(max_height)
            overflow_count += 1
            
            title_elem = slide.find('h1', class_='slide-title')
            title = title_elem.get_text(strip=True) if title_elem else f"Slide {idx + 1}"
            logger.warning(f"⚠️  Overflow detected: Slide {idx + 1} '{title}' - {estimated_height}px > {max_height}px (excess: {overflow_amount}px)")
    
    logger.info(f"📊 Server-side overflow detection: {overflow_count} slides marked with data-overflow='true'")
    
    return str(soup)
