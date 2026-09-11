"""
HTML Patcher for Infographic Updates
=====================================
Patches existing HTML with updated slide content instead of regenerating everything.
This is more efficient and preserves URL signatures.
"""

import re
from typing import Dict, List
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger()


def patch_html_content(existing_html: str, updated_slides: List[Dict], image_mapping: Dict = None) -> str:
    """
    Patch existing HTML with updated slide content.
    
    Args:
        existing_html: Original HTML content
        updated_slides: List of updated slide dictionaries
        image_mapping: Optional mapping of image URLs (not used in current implementation)
    
    Returns:
        Updated HTML string
    """
    try:
        soup = BeautifulSoup(existing_html, 'html.parser')
        
        # Find all slide divs
        slide_divs = soup.find_all('div', class_='slide', attrs={'data-slide': True})
        
        # Create mapping of slide number to div
        slide_map = {}
        for div in slide_divs:
            slide_num = int(div.get('data-slide'))
            slide_map[slide_num] = div
        
        # Only update slides that have content_blocks (i.e., were actually edited in the frontend)
        for slide in updated_slides:
            slide_num = slide.get('slide_number')
            
            # Skip if slide doesn't exist in HTML
            if slide_num not in slide_map:
                logger.warning(f"Slide {slide_num} not found in existing HTML, skipping")
                continue
            
            # CRITICAL: Only patch if this slide has content_blocks
            # The frontend only sends content_blocks for slides that were actually edited
            if 'content_blocks' not in slide or not slide.get('content_blocks'):
                logger.info(f"Skipping slide {slide_num} - no content_blocks (not edited)")
                continue
            
            try:
                patch_slide_div(slide_map[slide_num], slide)
                logger.info(f"Successfully patched slide {slide_num}")
            except Exception as e:
                logger.error(f"Error patching slide {slide_num}: {e}")
                # Continue with other slides even if one fails
                continue
        
        return str(soup)
        
    except Exception as e:
        logger.error(f"Error in patch_html_content: {e}")
        raise


def patch_slide_div(slide_div, slide_data: Dict):
    """
    Update a single slide div with new content.
    
    Args:
        slide_div: BeautifulSoup div element for the slide
        slide_data: Dictionary with updated slide data
    """
    slide_type = slide_data.get('type')
    
    # Don't patch special slide types (covers, titles, etc.)
    if slide_type in ['cover', 'module-title', 'lesson-title', 'thank-you']:
        logger.info(f"Skipping special slide type: {slide_type}")
        return
    
    # Get content blocks
    content_blocks = slide_data.get('content_blocks', [])
    if not content_blocks:
        logger.warning(f"No content blocks for slide {slide_data.get('slide_number')}")
        return
    
    # Update title if present and changed
    title = slide_data.get('title')
    if title:
        title_div = slide_div.find('div', class_='slide-title')
        if title_div and title_div.string != title:
            title_div.string = title
    
    # Update subtitle if present and changed
    subtitle = slide_data.get('subtitle')
    if subtitle:
        subtitle_div = slide_div.find('div', class_='slide-subtitle')
        if subtitle_div and subtitle_div.string != subtitle:
            subtitle_div.string = subtitle
    
    # Find and update content area
    content_div = slide_div.find('div', class_='slide-content')
    if not content_div:
        logger.warning(f"No content div found for slide {slide_data.get('slide_number')}")
        return
    
    # Clear existing content and rebuild
    content_div.clear()
    
    # Recreate content from blocks
    for block in content_blocks:
        block_type = block.get('type')
        
        if block_type == 'nested-bullets':
            # CRITICAL FIX: Handle nested bullets properly
            patch_nested_bullets(content_div, block)
        elif block_type == 'bullets':
            patch_bullets(content_div, block)
        elif block_type == 'callout':
            patch_callout(content_div, block)
        else:
            logger.warning(f"Unknown block type: {block_type}")


def patch_nested_bullets(content_div, block: Dict):
    """
    Patch nested bullets content block (used for Agenda slide).
    
    Args:
        content_div: BeautifulSoup div to append to
        block: Content block dictionary with nested items
    """
    from bs4 import Tag
    
    heading = block.get('heading', '')
    if heading:
        heading_div = Tag(name='div')
        heading_div['class'] = 'content-heading'
        heading_div.string = heading
        content_div.append(heading_div)
    
    ul = Tag(name='ul')
    ul['class'] = 'bullets'
    
    items = block.get('items', [])
    for item in items:
        li = Tag(name='li')
        
        # CRITICAL FIX: Check if item is a dict (module with lessons) or string
        if isinstance(item, dict):
            # Module with nested lessons
            module_text = item.get('text', '')
            li.append(module_text)
            
            lessons = item.get('lessons', [])
            if lessons:
                nested_ul = Tag(name='ul')
                for lesson in lessons:
                    lesson_li = Tag(name='li')
                    # Ensure lesson is treated as string
                    lesson_text = lesson if isinstance(lesson, str) else str(lesson)
                    lesson_li.string = lesson_text
                    nested_ul.append(lesson_li)
                li.append(nested_ul)
        else:
            # Plain text item - convert to string if needed
            item_text = item if isinstance(item, str) else str(item)
            li.string = item_text
        
        ul.append(li)
    
    content_div.append(ul)


def patch_bullets(content_div, block: Dict):
    """
    Patch regular bullets content block.
    
    Args:
        content_div: BeautifulSoup div to append to
        block: Content block dictionary
    """
    from bs4 import Tag
    
    heading = block.get('heading', '')
    if heading:
        heading_div = Tag(name='div')
        heading_div['class'] = 'content-heading'
        heading_div.string = heading
        content_div.append(heading_div)
    
    ul = Tag(name='ul')
    ul['class'] = 'bullets'
    
    items = block.get('items', [])
    for item in items:
        li = Tag(name='li')
        # Ensure item is string
        item_text = item if isinstance(item, str) else str(item)
        li.string = item_text
        ul.append(li)
    
    content_div.append(ul)


def patch_callout(content_div, block: Dict):
    """
    Patch callout content block.
    
    Args:
        content_div: BeautifulSoup div to append to
        block: Content block dictionary
    """
    from bs4 import Tag
    
    callout_div = Tag(name='div')
    callout_div['class'] = 'callout'
    text = block.get('text', '')
    callout_div.string = text
    content_div.append(callout_div)
