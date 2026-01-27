"""
HTML to PPT Converter with Style Mapping
Converts HTML infographic slides to PowerPoint while preserving visual design.
Includes logo and image support.
"""

import io
import logging
import re
import requests
from bs4 import BeautifulSoup
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# DESIGN CONSTANTS (matching HTML CSS)
# =============================================================================

COLORS = {
    'header_dark': RGBColor(0x00, 0x33, 0x66),
    'header_light': RGBColor(0x46, 0x82, 0xB4),
    'bullet_marker': RGBColor(0xFF, 0xC0, 0x00),
    'code_bg': RGBColor(0x1E, 0x1E, 0x1E),
    'code_text': RGBColor(0xD4, 0xD4, 0xD4),
    'text_dark': RGBColor(0x00, 0x33, 0x66),
    'white': RGBColor(0xFF, 0xFF, 0xFF),
    'callout_bg': RGBColor(0xFF, 0xC0, 0x00),
}

FONTS = {
    'title': 'Segoe UI',
    'body': 'Segoe UI', 
    'code': 'Consolas',
}

# Slide dimensions (16:9)
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# Layout measurements
HEADER_HEIGHT = Inches(1.2)
CONTENT_TOP = Inches(1.4)
CONTENT_LEFT = Inches(0.5)
CONTENT_WIDTH = Inches(12.333)
CONTENT_HEIGHT = Inches(5.5)

# Logo settings
LOGO_WIDTH = Inches(1.5)
LOGO_HEIGHT = Inches(0.6)
LOGO_RIGHT_MARGIN = Inches(0.3)
LOGO_BOTTOM_MARGIN = Inches(0.3)


def convert_html_to_pptx(html_content: str, s3_client=None, course_bucket: str = None) -> bytes:
    """
    Convert HTML infographic slides to PowerPoint.
    """
    logger.info("Starting HTML to PPT conversion with style mapping...")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    slides_html = soup.find_all('div', class_='slide')
    
    logger.info(f"Found {len(slides_html)} slides in HTML")
    
    logo_bytes = download_logo(s3_client, course_bucket)
    
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    
    blank_layout = prs.slide_layouts[6]
    
    # Store references for image downloads
    ctx = {'s3_client': s3_client, 'bucket': course_bucket}
    
    for idx, slide_html in enumerate(slides_html):
        logger.info(f"Processing slide {idx + 1}/{len(slides_html)}")
        
        if slide_html.find(class_='course-title-slide'):
            create_course_title_slide(prs, blank_layout, slide_html, logo_bytes)
        elif slide_html.find(class_='module-title-slide'):
            create_module_title_slide(prs, blank_layout, slide_html, logo_bytes)
        elif slide_html.find(class_='lesson-title-slide'):
            create_lesson_title_slide(prs, blank_layout, slide_html, logo_bytes)
        else:
            create_content_slide(prs, blank_layout, slide_html, logo_bytes, ctx)
    
    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    
    logger.info(f"✅ Created PowerPoint with {len(slides_html)} slides")
    return output.read()


def download_logo(s3_client, course_bucket: str) -> bytes:
    """Download logo from S3."""
    if not s3_client or not course_bucket:
        logger.warning("No S3 client or bucket provided, skipping logo")
        return None
    
    try:
        logo_key = "logo/LogoNetec.png"
        logger.info(f"Downloading logo from s3://{course_bucket}/{logo_key}")
        response = s3_client.get_object(Bucket=course_bucket, Key=logo_key)
        return response['Body'].read()
    except Exception as e:
        logger.warning(f"Could not download logo: {e}")
        return None


def add_logo(slide, logo_bytes):
    """Add logo to bottom-right corner of slide."""
    if not logo_bytes:
        return
    
    try:
        logo_stream = io.BytesIO(logo_bytes)
        left = SLIDE_WIDTH - LOGO_WIDTH - LOGO_RIGHT_MARGIN
        top = SLIDE_HEIGHT - LOGO_HEIGHT - LOGO_BOTTOM_MARGIN
        slide.shapes.add_picture(logo_stream, left, top, LOGO_WIDTH, LOGO_HEIGHT)
    except Exception as e:
        logger.warning(f"Could not add logo: {e}")


def add_logo_centered(slide, logo_bytes):
    """Add logo centered at bottom of slide (for title slides)."""
    if not logo_bytes:
        return
    
    try:
        logo_stream = io.BytesIO(logo_bytes)
        logo_w = Inches(2)  # Larger logo for title slides
        logo_h = Inches(0.8)
        left = (SLIDE_WIDTH - logo_w) / 2
        top = SLIDE_HEIGHT - logo_h - Inches(0.5)
        slide.shapes.add_picture(logo_stream, left, top, logo_w, logo_h)
    except Exception as e:
        logger.warning(f"Could not add centered logo: {e}")


def extract_s3_key_from_url(url: str) -> str:
    """Extract S3 key from presigned URL or direct S3 URL."""
    try:
        # URL format: https://bucket.s3.amazonaws.com/folder/images/file.png?...
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        # Get path after bucket name
        path = unquote(parsed.path)
        if path.startswith('/'):
            path = path[1:]
        return path
    except Exception as e:
        logger.warning(f"Could not extract S3 key: {e}")
        return None


def download_image_from_s3(s3_client, bucket: str, image_url: str) -> bytes:
    """Download image from S3 using the S3 client (avoids expired presigned URLs)."""
    if not s3_client or not bucket:
        return None
    
    s3_key = extract_s3_key_from_url(image_url)
    if not s3_key:
        return None
    
    try:
        logger.info(f"Downloading image from S3: {s3_key}")
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        return response['Body'].read()
    except Exception as e:
        logger.warning(f"Could not download image from S3: {e}")
        return None


def add_content_image(slide, img_url: str, position: str, ctx: dict):
    """Add content image to slide."""
    img_bytes = download_image_from_s3(ctx.get('s3_client'), ctx.get('bucket'), img_url)
    if not img_bytes:
        logger.warning(f"Could not download image: {img_url[:60]}...")
        return
    
    try:
        img_stream = io.BytesIO(img_bytes)
        
        if position == 'left':
            left = CONTENT_LEFT
            top = CONTENT_TOP
            width = Inches(5)
            height = Inches(4)
        else:
            left = Inches(7)
            top = CONTENT_TOP
            width = Inches(5)
            height = Inches(4)
        
        slide.shapes.add_picture(img_stream, left, top, width, height)
        logger.info(f"✅ Added image at {position}")
    except Exception as e:
        logger.warning(f"Could not add image: {e}")


def create_course_title_slide(prs, layout, slide_html, logo_bytes):
    """Course title: Full gradient, centered title, centered logo at bottom."""
    slide = prs.slides.add_slide(layout)
    
    title_elem = slide_html.find(class_='title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Untitled"
    
    add_gradient_background(slide)
    
    # Title (centered)
    title_box = slide.shapes.add_textbox(
        Inches(0.5), Inches(3), Inches(12.333), Inches(1.5)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.color.rgb = COLORS['white']
    p.font.name = FONTS['title']
    p.alignment = PP_ALIGN.CENTER
    
    add_logo_centered(slide, logo_bytes)


def create_module_title_slide(prs, layout, slide_html, logo_bytes):
    """Module title: Gradient background, yellow bar on LEFT, centered logo."""
    slide = prs.slides.add_slide(layout)
    
    title_elem = slide_html.find(class_='title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Untitled"
    
    add_gradient_background(slide)
    
    # Yellow accent bar on left side
    yellow_bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        Inches(0.15), SLIDE_HEIGHT
    )
    yellow_bar.fill.solid()
    yellow_bar.fill.fore_color.rgb = COLORS['bullet_marker']
    yellow_bar.line.fill.background()
    
    # Title (left-aligned with padding from yellow bar)
    title_box = slide.shapes.add_textbox(
        Inches(0.5), Inches(2.5), Inches(12), Inches(2)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.color.rgb = COLORS['white']
    p.font.name = FONTS['title']
    p.alignment = PP_ALIGN.CENTER
    
    add_logo_centered(slide, logo_bytes)


def create_lesson_title_slide(prs, layout, slide_html, logo_bytes):
    """Lesson title: WHITE background, yellow bar at TOP, logo top-right, dark text."""
    slide = prs.slides.add_slide(layout)
    
    title_elem = slide_html.find(class_='title')
    subtitle_elem = slide_html.find(class_='subtitle')
    
    title_text = title_elem.get_text(strip=True) if title_elem else "Untitled"
    subtitle_text = subtitle_elem.get_text(strip=True) if subtitle_elem else ""
    
    # Yellow bar at TOP (border-top style from CSS)
    yellow_bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        SLIDE_WIDTH, Inches(0.12)
    )
    yellow_bar.fill.solid()
    yellow_bar.fill.fore_color.rgb = COLORS['bullet_marker']
    yellow_bar.line.fill.background()
    
    # Logo at top-right
    if logo_bytes:
        try:
            logo_stream = io.BytesIO(logo_bytes)
            slide.shapes.add_picture(
                logo_stream, 
                SLIDE_WIDTH - Inches(1.8), 
                Inches(0.3), 
                Inches(1.5), 
                Inches(0.6)
            )
        except Exception as e:
            logger.warning(f"Could not add top-right logo: {e}")
    
    # Title (centered, dark blue)
    title_box = slide.shapes.add_textbox(
        Inches(0.5), Inches(2.5), Inches(12.333), Inches(1.5)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = COLORS['text_dark']  # Dark blue text
    p.font.name = FONTS['title']
    p.alignment = PP_ALIGN.CENTER
    
    # Subtitle (light blue)
    if subtitle_text:
        subtitle_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(4), Inches(12.333), Inches(1)
        )
        tf = subtitle_box.text_frame
        p = tf.paragraphs[0]
        p.text = subtitle_text
        p.font.size = Pt(24)
        p.font.color.rgb = COLORS['header_light']  # Light blue
        p.font.name = FONTS['body']
        p.alignment = PP_ALIGN.CENTER


def create_content_slide(prs, layout, slide_html, logo_bytes, ctx):
    """Create a content slide with header, bullets, and optional image."""
    slide = prs.slides.add_slide(layout)
    
    title_elem = slide_html.find(class_='slide-title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Untitled"
    
    add_header_bar(slide, title_text)
    
    content_elem = slide_html.find(class_='slide-content')
    if not content_elem:
        add_logo(slide, logo_bytes)
        return
    
    # Check for image layout
    has_image = 'image-left' in content_elem.get('class', []) or 'image-right' in content_elem.get('class', [])
    image_position = 'left' if 'image-left' in content_elem.get('class', []) else 'right'
    
    # Find image in image-column or directly in content
    image_column = content_elem.find(class_='image-column')
    if image_column:
        img_elem = image_column.find('img', class_='slide-image')
    else:
        img_elem = content_elem.find('img', class_='slide-image')
    
    if not img_elem:
        img_elem = slide_html.find('img', class_='slide-image')
    
    if img_elem and img_elem.get('src'):
        img_url = img_elem.get('src')
        logger.info(f"Found slide image: {img_url[:80]}...")
        add_content_image(slide, img_url, image_position, ctx)
        
        # Adjust bullet area based on image position
        if image_position == 'left':
            bullet_left = Inches(6)
            bullet_width = Inches(6.5)
        else:
            bullet_left = CONTENT_LEFT
            bullet_width = Inches(6)
    else:
        bullet_left = CONTENT_LEFT
        bullet_width = CONTENT_WIDTH
    
    # Content
    bullets_elem = content_elem.find('ul', class_='bullets')
    code_elem = content_elem.find(class_='code-block')
    callout_elem = content_elem.find(class_='callout')
    
    current_top = CONTENT_TOP
    
    if bullets_elem:
        current_top = add_bullets(slide, bullets_elem, current_top, bullet_left, bullet_width)
    
    if code_elem:
        add_code_block(slide, code_elem, current_top)
    
    if callout_elem:
        add_callout(slide, callout_elem)
    
    add_logo(slide, logo_bytes)


def add_gradient_background(slide):
    """Add a full-slide gradient background."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        SLIDE_WIDTH, SLIDE_HEIGHT
    )
    shape.line.fill.background()
    
    fill = shape.fill
    fill.gradient()
    fill.gradient_angle = 135
    fill.gradient_stops[0].color.rgb = COLORS['header_dark']
    fill.gradient_stops[1].color.rgb = COLORS['header_light']


def add_header_bar(slide, title_text):
    """Add a gradient header bar with title."""
    header = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        SLIDE_WIDTH, HEADER_HEIGHT
    )
    header.line.fill.background()
    
    fill = header.fill
    fill.gradient()
    fill.gradient_angle = 135
    fill.gradient_stops[0].color.rgb = COLORS['header_dark']
    fill.gradient_stops[1].color.rgb = COLORS['header_light']
    
    title_box = slide.shapes.add_textbox(
        Inches(0.5), Inches(0.3), Inches(12), Inches(0.8)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = COLORS['white']
    p.font.name = FONTS['title']


def add_bullets(slide, bullets_elem, top, left=None, width=None):
    """Add bullet list with styled markers."""
    if left is None:
        left = CONTENT_LEFT
    if width is None:
        width = CONTENT_WIDTH
        
    items = bullets_elem.find_all('li', recursive=False)
    
    if not items:
        return top
    
    text_box = slide.shapes.add_textbox(left, top, width, CONTENT_HEIGHT)
    tf = text_box.text_frame
    tf.word_wrap = True
    
    for i, li in enumerate(items):
        text = ""
        for child in li.children:
            if isinstance(child, str):
                text += child.strip()
            elif child.name != 'ul':
                text += child.get_text(strip=True)
        
        if not text:
            continue
            
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        
        p.text = f"▸ {text}"
        p.font.size = Pt(20)
        p.font.name = FONTS['body']
        p.font.color.rgb = COLORS['text_dark']
        p.space_before = Pt(8)
        p.space_after = Pt(4)
        
        nested_ul = li.find('ul')
        if nested_ul:
            for nested_li in nested_ul.find_all('li', recursive=False):
                nested_text = nested_li.get_text(strip=True)
                if nested_text:
                    np = tf.add_paragraph()
                    np.text = f"    ○ {nested_text}"
                    np.font.size = Pt(18)
                    np.font.name = FONTS['body']
                    np.font.color.rgb = COLORS['text_dark']
                    np.space_before = Pt(4)
    
    return top + Inches(len(items) * 0.5)


def add_code_block(slide, code_elem, top):
    """Add a dark-themed code block."""
    code_content = code_elem.find('pre')
    if not code_content:
        code_content = code_elem.find(class_='code-content')
    
    code_text = code_content.get_text() if code_content else ""
    
    code_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        CONTENT_LEFT, top,
        CONTENT_WIDTH, Inches(3)
    )
    code_box.fill.solid()
    code_box.fill.fore_color.rgb = COLORS['code_bg']
    code_box.line.fill.background()
    
    text_box = slide.shapes.add_textbox(
        CONTENT_LEFT + Inches(0.2), top + Inches(0.3),
        CONTENT_WIDTH - Inches(0.4), Inches(2.6)
    )
    tf = text_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    
    lines = code_text.strip().split('\n')[:15]
    p.text = '\n'.join(lines)
    p.font.size = Pt(12)
    p.font.name = FONTS['code']
    p.font.color.rgb = COLORS['code_text']


def add_callout(slide, callout_elem):
    """Add a yellow callout box."""
    text = callout_elem.get_text(strip=True)
    
    callout = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        CONTENT_LEFT, Inches(5.5),
        CONTENT_WIDTH, Inches(1)
    )
    callout.fill.solid()
    callout.fill.fore_color.rgb = COLORS['callout_bg']
    callout.line.fill.background()
    
    tf = callout.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.name = FONTS['body']
    p.font.color.rgb = COLORS['text_dark']
    p.alignment = PP_ALIGN.CENTER

