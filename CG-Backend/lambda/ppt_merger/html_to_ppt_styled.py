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
    'primary': RGBColor(0x00, 0x33, 0x66),
    'secondary': RGBColor(0x46, 0x82, 0xB4),
    'text_black': RGBColor(0x33, 0x33, 0x33),
}

FONTS = {
    'title': 'Neue Haas Grotesk Text Pro',
    'body': 'Neue Haas Grotesk Text Pro', 
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

# =============================================================================
# SUPPLEMENTARY DATA HELPERS (for backward-compatible enrichment)
# =============================================================================

def _extract_objectives_from_md(content: str) -> list:
    """Extract learning objectives bullet items from lesson markdown."""
    if not content:
        return []
    pattern = re.compile(
        r'^#{2,3}\s*(?:Objetivos[^\n]*|Learning\s+Objectives[^\n]*)\n+'
        r'(?:[^\n]*\n)*?'
        r'((?:\s*-\s+.+\n?)+)',
        re.MULTILINE | re.IGNORECASE,
    )
    m = pattern.search(content)
    if not m:
        return []
    items = []
    for line in m.group(1).strip().split('\n'):
        line = line.strip()
        if line.startswith('- '):
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', line[2:].strip())
            items.append(text)
    return items[:6]


def _extract_intro_from_md(content: str) -> str:
    """Extract the first paragraph of ## Introducción / ## Introduction."""
    if not content:
        return ''
    pattern = re.compile(
        r'^#{2,3}\s*(?:Introducción|Introduction)[^\n]*\n+(.+?)(?:\n\n|\n##|\Z)',
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(content)
    if not m:
        return ''
    para = m.group(1).strip().split('\n\n')[0].replace('\n', ' ').strip()
    return para[:300] + '...' if len(para) > 300 else para


def _build_supplementary_lookup(book_data: dict) -> dict:
    """Build a lookup dict keyed by module number with title, objectives, lessons.
    Used to enrich old HTML that lacks new classes."""
    supp = {}
    if not book_data:
        return supp

    outline_modules = book_data.get('outline_modules', [])
    book_modules = book_data.get('book_modules', [])

    for idx, om in enumerate(outline_modules):
        mod_num = idx + 1
        supp[mod_num] = {
            'title': om.get('title', ''),
            'objectives': [],
            'lessons': [],
        }

    for idx, bm in enumerate(book_modules):
        mod_num = bm.get('module_number', idx + 1)
        if mod_num not in supp:
            supp[mod_num] = {'title': bm.get('module_title', ''), 'objectives': [], 'lessons': []}

        # Extract objectives from the first "Introducción" lesson
        for lesson in bm.get('lessons', []):
            lesson_title = lesson.get('title', '')
            content = lesson.get('content', '')
            supp[mod_num]['lessons'].append({
                'title': lesson_title,
                'content': content,
            })
            if lesson_title.lower().strip() in ('introducción', 'introduction') and not supp[mod_num]['objectives']:
                supp[mod_num]['objectives'] = _extract_objectives_from_md(content)

        # Update title from book if outline didn't provide it
        if not supp[mod_num]['title']:
            supp[mod_num]['title'] = bm.get('module_title', f'Capítulo {mod_num}')

    return supp


def convert_html_to_pptx(html_content: str, s3_client=None, course_bucket: str = None, book_data: dict = None) -> bytes:
    """
    Convert HTML infographic slides to PowerPoint.
    book_data: optional dict with 'outline_modules' and 'book_modules' for
               enriching module-title / lesson-title slides from S3 data.
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

    # Build supplementary lookup for backward-compatible enrichment
    supp = _build_supplementary_lookup(book_data) if book_data else {}
    current_module_num = 0  # tracks which module we're in (parsed from text)
    lesson_counter_in_module = 0  # counts lesson-title slides within current module
    seen_module_nums = set()  # track first-occurrence module-title slides

    for idx, slide_html in enumerate(slides_html):
        logger.info(f"Processing slide {idx + 1}/{len(slides_html)}")
        
        slide = None
        if slide_html.find(class_='intro-cover-slide'):
            slide = create_intro_cover_slide(prs, blank_layout, slide_html, logo_bytes, ctx)
        elif slide_html.find(class_='intro-legal-slide'):
            slide = create_intro_legal_slide(prs, blank_layout, slide_html, logo_bytes, ctx)
        elif slide_html.find(class_='intro-agenda-slide'):
            slide = create_intro_agenda_slide(prs, blank_layout, slide_html, logo_bytes)
        elif slide_html.find(class_='intro-content-slide'):
            slide = create_intro_content_slide(prs, blank_layout, slide_html, logo_bytes, ctx)
        elif slide_html.find(class_='course-title-slide'):
            slide = create_course_title_slide(prs, blank_layout, slide_html, logo_bytes)
        elif slide_html.find(class_='module-title-slide'):
            # Parse module number from text instead of using sequential counter
            _mt = slide_html.find(class_='module-title-chapter') or slide_html.find(class_='title')
            _mt_text = _mt.get_text(strip=True) if _mt else ''
            _mn = re.search(r'(\d+)', _mt_text)
            if _mn:
                current_module_num = int(_mn.group(1))
            else:
                current_module_num += 1
            # Only reset lesson counter on FIRST occurrence of a module number
            # Old HTML may have duplicate module-title slides (start + before summary)
            if current_module_num not in seen_module_nums:
                lesson_counter_in_module = 0
                seen_module_nums.add(current_module_num)
            slide = create_module_title_slide(prs, blank_layout, slide_html, logo_bytes,
                                              supp=supp, module_num=current_module_num)
        elif slide_html.find(class_='lesson-title-slide'):
            lesson_counter_in_module += 1
            slide = create_lesson_title_slide(prs, blank_layout, slide_html, logo_bytes,
                                              supp=supp, module_num=current_module_num,
                                              lesson_num=lesson_counter_in_module)
        elif slide_html.find(class_='module-end-logo-slide'):
            slide = create_module_end_logo_slide(prs, blank_layout, slide_html, logo_bytes)
        else:
            slide = create_content_slide(prs, blank_layout, slide_html, logo_bytes, ctx)
            
        # Add instructor notes if present
        if slide:
            notes_div = slide_html.find(class_='notes')
            if notes_div:
                notes_text = notes_div.get_text(strip=True)
                if notes_text:
                    try:
                        slide.notes_slide.notes_text_frame.text = notes_text
                        logger.info(f"   📝 Added instructor notes ({len(notes_text)} chars)")
                    except Exception as e:
                        logger.warning(f"   ⚠️ Could not add notes: {e}")
    
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
            top = ctx.get('content_top', CONTENT_TOP)
            width = Inches(5)
            height = Inches(4)
        else:
            left = Inches(7)
            top = ctx.get('content_top', CONTENT_TOP)
            width = Inches(5)
            height = Inches(4)
        
        slide.shapes.add_picture(img_stream, left, top, width, height)
        logger.info(f"✅ Added image at {position}")
    except Exception as e:
        logger.warning(f"Could not add image: {e}")


def download_image_bytes(img_url: str, ctx: dict) -> bytes:
    """Download an image from S3-backed URL or HTTP URL."""
    if not img_url:
        return None

    # Prefer S3 direct read when possible (works for presigned and S3 URLs)
    img_bytes = download_image_from_s3(ctx.get('s3_client'), ctx.get('bucket'), img_url)
    if img_bytes:
        return img_bytes

    try:
        response = requests.get(img_url, timeout=15)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.warning(f"Could not download image over HTTP: {e}")

    return None


def add_logo_bottom_left(slide, logo_bytes):
    """Add Netec logo at bottom-left (intro style)."""
    if not logo_bytes:
        return

    try:
        logo_stream = io.BytesIO(logo_bytes)
        slide.shapes.add_picture(
            logo_stream,
            Inches(0.22),
            Inches(6.58),
            width=Inches(1.95),
            height=Inches(0.73)
        )
    except Exception as e:
        logger.warning(f"Could not add bottom-left logo: {e}")


def _safe_add_picture(slide, image_bytes: bytes, left, top, width=None, height=None) -> bool:
    """Safely add image to slide, returning False instead of raising on unsupported formats."""
    if not image_bytes:
        return False
    try:
        stream = io.BytesIO(image_bytes)
        if width is not None and height is not None:
            slide.shapes.add_picture(stream, left, top, width=width, height=height)
        elif width is not None:
            slide.shapes.add_picture(stream, left, top, width=width)
        elif height is not None:
            slide.shapes.add_picture(stream, left, top, height=height)
        else:
            slide.shapes.add_picture(stream, left, top)
        return True
    except Exception as e:
        logger.warning(f"Could not place image on slide: {e}")
        return False


def add_intro_accent_bar(slide):
    """Add the yellow accent line in a consistent position for all intro slides."""
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.53), Inches(0.46), Inches(0.82), Inches(0.08))
    accent.fill.solid()
    accent.fill.fore_color.rgb = COLORS['bullet_marker']
    accent.line.fill.background()


def _add_agenda_item_paragraph(text_frame, item_text: str):
    """Add one agenda row with yellow bullet, bold chapter prefix, and normal remainder."""
    raw = (item_text or '').strip()
    if not raw:
        return

    match = re.match(r'^\s*((?:Cap[ií]tulo|Chapter|Module)\s+\d+\s*:)\s*(.*)$', raw, flags=re.IGNORECASE)

    para = text_frame.paragraphs[0] if not text_frame.paragraphs[0].text and len(text_frame.paragraphs) == 1 else text_frame.add_paragraph()
    para.level = 0
    para.space_after = Pt(7)

    bullet_run = para.add_run()
    bullet_run.text = "• "
    bullet_run.font.size = Pt(20)
    bullet_run.font.bold = True
    bullet_run.font.name = FONTS['body']
    bullet_run.font.color.rgb = COLORS['bullet_marker']

    if match:
        prefix = match.group(1).strip()
        rest = match.group(2).strip()

        prefix_run = para.add_run()
        prefix_run.text = prefix + (" " if rest else "")
        prefix_run.font.size = Pt(22)
        prefix_run.font.bold = True
        prefix_run.font.name = FONTS['body']
        prefix_run.font.color.rgb = RGBColor(20, 20, 20)

        if rest:
            rest_run = para.add_run()
            rest_run.text = rest
            rest_run.font.size = Pt(22)
            rest_run.font.bold = False
            rest_run.font.name = FONTS['body']
            rest_run.font.color.rgb = RGBColor(20, 20, 20)
    else:
        full_run = para.add_run()
        full_run.text = raw
        full_run.font.size = Pt(22)
        full_run.font.bold = False
        full_run.font.name = FONTS['body']
        full_run.font.color.rgb = RGBColor(20, 20, 20)


def create_intro_cover_slide(prs, layout, slide_html, logo_bytes, ctx):
    """Corporate cover: left title panel, right hero image, countries strip and contact text."""
    slide = prs.slides.add_slide(layout)

    # Background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(245, 245, 245)

    # Left panel – same colour as background so no visible seam
    left_panel = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(6.3), Inches(7.5))
    left_panel.fill.solid()
    left_panel.fill.fore_color.rgb = RGBColor(245, 245, 245)
    left_panel.line.fill.background()

    # Accent bar (fixed position across intro slides)
    add_intro_accent_bar(slide)

    # Title
    title_elem = slide_html.find(class_='intro-cover-title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Curso"
    title_box = slide.shapes.add_textbox(Inches(0.58), Inches(2.05), Inches(5.75), Inches(3.2))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.name = FONTS['title']
    p.font.color.rgb = RGBColor(0, 60, 120)
    p.alignment = PP_ALIGN.LEFT

    # Right hero image
    hero = slide_html.find('img', class_='intro-cover-main-image')
    hero_bytes = download_image_bytes(hero.get('src') if hero else '', ctx)
    _safe_add_picture(slide, hero_bytes, Inches(6.02), Inches(0.9), width=Inches(6.93), height=Inches(5.75))

    # Countries strip
    countries = slide_html.find('img', class_='intro-cover-countries')
    countries_bytes = download_image_bytes(countries.get('src') if countries else '', ctx)
    _safe_add_picture(slide, countries_bytes, Inches(9.2), Inches(6.53), width=Inches(3.5), height=Inches(0.55))

    # Contact text
    contact = slide_html.find(class_='intro-cover-contact')
    contact_text = contact.get_text(strip=True) if contact else "www.netec.com | servicio@netec.com"
    if contact_text:
        t = slide.shapes.add_textbox(Inches(8.3), Inches(7.0), Inches(4.95), Inches(0.28))
        p = t.text_frame.paragraphs[0]
        p.text = contact_text
        p.font.size = Pt(12)
        p.font.color.rgb = RGBColor(30, 30, 30)
        p.font.name = FONTS['body']
        p.alignment = PP_ALIGN.RIGHT

    add_logo_bottom_left(slide, logo_bytes)
    return slide


def create_intro_legal_slide(prs, layout, slide_html, logo_bytes, ctx):
    """Corporate legal slide with left icon and right legal paragraphs."""
    slide = prs.slides.add_slide(layout)

    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(239, 239, 239)

    icon = slide_html.find('img', class_='intro-legal-icon')
    icon_bytes = download_image_bytes(icon.get('src') if icon else '', ctx)
    _safe_add_picture(slide, icon_bytes, Inches(0.9), Inches(1.8), width=Inches(3.2), height=Inches(3.9))

    # Accent bar + title
    add_intro_accent_bar(slide)

    title_elem = slide_html.find(class_='intro-content-title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Propiedad intelectual"
    title_box = slide.shapes.add_textbox(Inches(5.85), Inches(1.0), Inches(6.7), Inches(1.3))
    p = title_box.text_frame.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.name = FONTS['title']
    p.font.color.rgb = RGBColor(0, 0, 0)

    # Divider
    divider = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(5.85), Inches(2.35), Inches(6.95), Inches(0.02))
    divider.fill.solid()
    divider.fill.fore_color.rgb = RGBColor(195, 195, 195)
    divider.line.fill.background()

    paragraphs = [p.get_text(strip=True) for p in slide_html.select('.intro-paragraphs p') if p.get_text(strip=True)]
    text_box = slide.shapes.add_textbox(Inches(5.85), Inches(2.45), Inches(6.9), Inches(4.7))
    tf = text_box.text_frame
    tf.word_wrap = True
    for i, txt in enumerate(paragraphs):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = txt
        para.font.size = Pt(18)
        para.font.name = FONTS['body']
        para.font.color.rgb = RGBColor(25, 25, 25)
        para.space_after = Pt(8)

    add_logo_bottom_left(slide, logo_bytes)
    return slide


def create_intro_content_slide(prs, layout, slide_html, logo_bytes, ctx):
    """Corporate content intro slide: left text/list and right asset image."""
    slide = prs.slides.add_slide(layout)

    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(239, 239, 239)

    # Accent bar
    add_intro_accent_bar(slide)

    title_elem = slide_html.find(class_='intro-content-title')
    title_text = title_elem.get_text(strip=True) if title_elem else ""
    subtitle_elem = slide_html.find(class_='intro-subtitle')
    subtitle_text = subtitle_elem.get_text(strip=True) if subtitle_elem else ""

    title_box = slide.shapes.add_textbox(Inches(0.83), Inches(1.0), Inches(6.2), Inches(1.2))
    p = title_box.text_frame.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.name = FONTS['title']
    p.font.color.rgb = RGBColor(0, 0, 0)

    current_top = Inches(2.2)
    if subtitle_text:
        sub_box = slide.shapes.add_textbox(Inches(0.83), current_top, Inches(6.2), Inches(0.7))
        sp = sub_box.text_frame.paragraphs[0]
        sp.text = subtitle_text
        sp.font.size = Pt(22)
        sp.font.name = FONTS['body']
        sp.font.color.rgb = RGBColor(20, 20, 20)
        current_top = Inches(2.9)

    # Divider
    divider = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.83), current_top, Inches(6.6), Inches(0.02))
    divider.fill.solid()
    divider.fill.fore_color.rgb = RGBColor(195, 195, 195)
    divider.line.fill.background()
    current_top = current_top + Inches(0.12)

    list_items = [li.get_text(strip=True) for li in slide_html.select('ul.intro-list li') if li.get_text(strip=True)]
    text_box = slide.shapes.add_textbox(Inches(0.9), current_top, Inches(6.35), Inches(4.4))
    tf = text_box.text_frame
    tf.word_wrap = True
    tf.clear()
    for txt in list_items:
        para = tf.paragraphs[0] if not tf.paragraphs[0].text and len(tf.paragraphs) == 1 else tf.add_paragraph()
        para.level = 0

        bullet_run = para.add_run()
        bullet_run.text = "• "
        bullet_run.font.size = Pt(22)
        bullet_run.font.bold = True
        bullet_run.font.name = FONTS['body']
        bullet_run.font.color.rgb = COLORS['bullet_marker']

        text_run = para.add_run()
        text_run.text = txt
        text_run.font.size = Pt(21)
        text_run.font.bold = False
        text_run.font.name = FONTS['body']
        text_run.font.color.rgb = RGBColor(20, 20, 20)

        para.space_after = Pt(6)

    asset = slide_html.find('img', class_='intro-right-asset')
    asset_bytes = download_image_bytes(asset.get('src') if asset else '', ctx)
    _safe_add_picture(slide, asset_bytes, Inches(7.6), Inches(1.0), width=Inches(5.2), height=Inches(5.5))

    add_logo_bottom_left(slide, logo_bytes)
    return slide


def create_intro_agenda_slide(prs, layout, slide_html, logo_bytes):
    """Corporate agenda/temario slide with large chapter list and max readability."""
    slide = prs.slides.add_slide(layout)

    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(239, 239, 239)

    add_intro_accent_bar(slide)

    # Soft horizontal separator
    sep = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(1.82), Inches(13.333), Inches(0.03))
    sep.fill.solid()
    sep.fill.fore_color.rgb = RGBColor(220, 220, 220)
    sep.line.fill.background()

    title_elem = slide_html.find(class_='intro-content-title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Temario"
    title_box = slide.shapes.add_textbox(Inches(1.0), Inches(0.66), Inches(6.5), Inches(0.95))
    p = title_box.text_frame.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.name = FONTS['title']
    p.font.color.rgb = RGBColor(0, 0, 0)

    agenda_items = [li.get_text(strip=True) for li in slide_html.select('ul.intro-agenda-list li') if li.get_text(strip=True)]
    list_box = slide.shapes.add_textbox(Inches(1.08), Inches(2.34), Inches(11.0), Inches(3.95))
    tf = list_box.text_frame
    tf.word_wrap = True
    tf.clear()
    for txt in agenda_items:
        _add_agenda_item_paragraph(tf, txt)

    add_logo_bottom_left(slide, logo_bytes)
    return slide


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
    return slide


def create_module_title_slide(prs, layout, slide_html, logo_bytes, supp=None, module_num=1):
    """Module title: white bg, yellow accent bar, chapter number left, objectives right."""
    slide = prs.slides.add_slide(layout)

    # White/light background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(239, 239, 239)

    # Yellow accent bar (top-left)
    accent = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.53), Inches(0.55), Inches(0.82), Inches(0.08)
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = COLORS['bullet_marker']
    accent.line.fill.background()

    # Parse chapter label and name from the title element
    title_elem = slide_html.find(class_='module-title-chapter')
    chapter_label = title_elem.get_text(strip=True) if title_elem else ""
    name_elem = slide_html.find(class_='module-title-name')
    chapter_name = name_elem.get_text(strip=True) if name_elem else ""

    # Objectives from new HTML classes
    obj_heading_elem = slide_html.find(class_='module-title-obj-heading')
    obj_list_elem = slide_html.find(class_='module-title-obj-list')
    obj_items = []
    if obj_list_elem:
        obj_items = [li.get_text(strip=True) for li in obj_list_elem.find_all('li') if li.get_text(strip=True)]

    # --- Backward-compatible fallback: use supplementary book data ---
    if not chapter_label:
        old_title = slide_html.find(class_='title')
        full = old_title.get_text(strip=True) if old_title else ""

        m = re.match(r'^((?:Cap[ií]tulo|M[oó]dulo|Module|Chapter)\s+\d+)\s*:\s*(.+)$', full, re.IGNORECASE)
        if m:
            chapter_label = m.group(1).strip()
            chapter_name = m.group(2).strip()
        else:
            # Title is just "Capítulo N" without name – enrich from supp
            chapter_label = full or f"Capítulo {module_num}"
            chapter_name = ""
            if supp and module_num in supp:
                mod_info = supp[module_num]
                # Parse name from the full outline title "Módulo N: Name"
                om = re.match(r'^(?:M[oó]dulo|Cap[ií]tulo|Module|Chapter)\s+\d+\s*:\s*(.+)$',
                              mod_info.get('title', ''), re.IGNORECASE)
                if om:
                    chapter_name = om.group(1).strip()
                elif mod_info.get('title') and mod_info['title'] != chapter_label:
                    chapter_name = mod_info['title']

    if not obj_items and supp and module_num in supp:
        obj_items = supp[module_num].get('objectives', [])

    # Chapter label (large, black)
    lbl_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.1), Inches(5.5), Inches(2.0))
    tf = lbl_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = chapter_label
    p.font.size = Pt(50)
    p.font.bold = True
    p.font.name = FONTS['title']
    p.font.color.rgb = RGBColor(17, 17, 17)
    p.alignment = PP_ALIGN.LEFT

    # Divider line
    divider = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(3.2), Inches(5.5), Inches(0.02)
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = RGBColor(199, 199, 199)
    divider.line.fill.background()

    # Chapter name (red, below divider)
    if chapter_name:
        name_box = slide.shapes.add_textbox(Inches(0.6), Inches(3.4), Inches(5.5), Inches(2.0))
        tf = name_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = chapter_name
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.name = FONTS['title']
        p.font.color.rgb = RGBColor(178, 34, 34)
        p.alignment = PP_ALIGN.LEFT

    # Objectives on right side (already extracted above, including supp fallback)
    obj_heading = "Objetivos:"
    if obj_heading_elem:
        obj_heading = obj_heading_elem.get_text(strip=True)

    if obj_items:
        obj_heading = obj_heading_elem.get_text(strip=True) if obj_heading_elem else "Objetivos:"
        # Heading
        h_box = slide.shapes.add_textbox(Inches(6.8), Inches(1.1), Inches(6.0), Inches(0.6))
        hp = h_box.text_frame.paragraphs[0]
        hp.text = obj_heading
        hp.font.size = Pt(26)
        hp.font.bold = True
        hp.font.name = FONTS['title']
        hp.font.color.rgb = RGBColor(17, 17, 17)

        # Objective items
        obj_box = slide.shapes.add_textbox(Inches(6.8), Inches(1.8), Inches(6.0), Inches(4.5))
        tf = obj_box.text_frame
        tf.word_wrap = True
        tf.clear()
        for i, item in enumerate(obj_items):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            bullet_run = para.add_run()
            bullet_run.text = "• "
            bullet_run.font.size = Pt(18)
            bullet_run.font.bold = True
            bullet_run.font.name = FONTS['body']
            bullet_run.font.color.rgb = COLORS['bullet_marker']

            text_run = para.add_run()
            text_run.text = item
            text_run.font.size = Pt(18)
            text_run.font.bold = False
            text_run.font.name = FONTS['body']
            text_run.font.color.rgb = RGBColor(34, 34, 34)
            para.space_after = Pt(6)

    add_logo_bottom_left(slide, logo_bytes)
    return slide


def create_lesson_title_slide(prs, layout, slide_html, logo_bytes, supp=None, module_num=1, lesson_num=1):
    """Lesson title: light bg, yellow bar at TOP, numbered title, divider, intro text."""
    slide = prs.slides.add_slide(layout)

    # Light background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(239, 239, 239)

    title_elem = slide_html.find(class_='title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Untitled"

    # Check if title already has numbering like "1.2 Name" or "1.1: Name"
    has_numbering = bool(re.match(r'^\d+\.\d+[:\s]', title_text))

    # Don't number module-intro or summary lessons
    title_lower = title_text.lower().strip()
    is_bookend = title_lower in ('introducción', 'introduction',
                                  'resumen del capítulo', 'chapter summary',
                                  'resumen', 'summary')

    # If old format without numbering, prepend "module.lesson" prefix
    if not has_numbering and not is_bookend and module_num > 0:
        title_text = f"{module_num}.{lesson_num} {title_text}"
    
    # Yellow bar at TOP
    yellow_bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        SLIDE_WIDTH, Inches(0.12)
    )
    yellow_bar.fill.solid()
    yellow_bar.fill.fore_color.rgb = COLORS['bullet_marker']
    yellow_bar.line.fill.background()
    
    # Title (centered, dark blue)
    title_box = slide.shapes.add_textbox(
        Inches(0.5), Inches(1.8), Inches(12.333), Inches(1.8)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(42)
    p.font.bold = True
    p.font.color.rgb = COLORS['text_dark']
    p.font.name = FONTS['title']
    p.alignment = PP_ALIGN.CENTER

    # Introduction text (from new HTML classes)
    intro_items = [li.get_text(strip=True) for li in slide_html.select('.lesson-intro-text p') if li.get_text(strip=True)]

    # Backward-compatible fallback: extract intro from book data via title matching
    if not intro_items and not is_bookend and supp and module_num in supp:
        supp_lessons = supp[module_num].get('lessons', [])
        matched_lesson = None

        # Try 1: match by "X.Y" number prefix in the title
        _num_m = re.match(r'(\d+\.\d+)', title_text)
        if _num_m:
            target_num = _num_m.group(1)
            for _sl in supp_lessons:
                if target_num + ':' in _sl['title'] or target_num + ' ' in _sl['title'] or _sl['title'].startswith(target_num):
                    matched_lesson = _sl
                    break

        # Try 2: fuzzy match on stripped title text
        if not matched_lesson:
            clean_title = re.sub(r'^\d+\.\d+[:\s]+', '', title_text).strip().lower()
            if clean_title:
                for _sl in supp_lessons:
                    clean_supp = re.sub(r'^\d+\.\d+[:\s]+', '', _sl['title']).strip().lower()
                    if clean_title == clean_supp or clean_title in clean_supp or clean_supp in clean_title:
                        matched_lesson = _sl
                        break

        if matched_lesson:
            intro_text = _extract_intro_from_md(matched_lesson.get('content', ''))
            if intro_text:
                intro_items = [intro_text]

    if intro_items:
        # Divider
        divider = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(2), Inches(3.7),
            Inches(9.333), Inches(0.02)
        )
        divider.fill.solid()
        divider.fill.fore_color.rgb = RGBColor(199, 199, 199)
        divider.line.fill.background()

        intro_box = slide.shapes.add_textbox(
            Inches(1.5), Inches(3.9), Inches(10.333), Inches(2.8)
        )
        tf = intro_box.text_frame
        tf.word_wrap = True
        for i, text in enumerate(intro_items):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = text
            para.font.size = Pt(20)
            para.font.name = FONTS['body']
            para.font.color.rgb = RGBColor(51, 51, 51)
            para.alignment = PP_ALIGN.CENTER
            para.space_after = Pt(6)

    add_logo_bottom_left(slide, logo_bytes)
    return slide


def create_module_end_logo_slide(prs, layout, slide_html, logo_bytes):
    """Module end slide: White background, large centered logo."""
    slide = prs.slides.add_slide(layout)
    
    # White background
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = COLORS['white']
    
    add_logo_middle_center(slide, logo_bytes)
    return slide


def create_content_slide(prs, layout, slide_html, logo_bytes, ctx):
    """Create a content slide with header, bullets, and optional image."""
    slide = prs.slides.add_slide(layout)

    # White background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = COLORS['white']
    
    title_elem = slide_html.find(class_='slide-title')
    title_text = title_elem.get_text(strip=True) if title_elem else "Untitled"
    
    subtitle_elem = slide_html.find(class_='slide-subtitle')
    subtitle_text = subtitle_elem.get_text(strip=True) if subtitle_elem else ""
    
    header_height = add_header_bar(slide, title_text, subtitle_text)
    
    content_top_pos = header_height + Inches(0.2) # Start content below header
    
    content_elem = slide_html.find(class_='slide-content')
    if not content_elem:
        add_logo_bottom_left(slide, logo_bytes)
        return slide
    
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
        
        # Pass content_top to image function
        ctx['content_top'] = content_top_pos
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
    heading_elem = content_elem.find(class_='content-heading')
    bullets_elem = content_elem.find('ul', class_='bullets')
    code_elem = content_elem.find(class_='code-block')
    callout_elem = content_elem.find(class_='callout')
    
    current_top = content_top_pos
    
    if heading_elem:
        current_top = add_content_heading(slide, heading_elem, current_top, bullet_left, bullet_width)

    if bullets_elem:
        current_top = add_bullets(slide, bullets_elem, current_top, bullet_left, bullet_width)
    
    if code_elem:
        add_code_block(slide, code_elem, current_top)
    
    if callout_elem:
        add_callout(slide, callout_elem)
    
    add_logo_bottom_left(slide, logo_bytes)
    return slide


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


def add_header_bar(slide, title_text, subtitle_text=""):
    """
    Add a header region with yellow accent bar on left, dark title, and
    a thin divider line.  Matches the corporate template (no gradient).
    """
    # Determine heights
    is_long_title = len(title_text) > 50
    has_subtitle = bool(subtitle_text)
    base_h = 1.0
    if has_subtitle:
        base_h = 1.5
    if is_long_title:
        base_h = max(base_h, 1.4)

    bar_height = Inches(base_h)

    # Yellow accent bar on left
    accent_bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.4), Inches(0.22),
        Inches(0.08), Inches(base_h - 0.14)
    )
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = COLORS['bullet_marker']
    accent_bar.line.fill.background()

    # Title text (dark blue)
    title_top = Inches(0.18)
    title_height = Inches(0.9) if not is_long_title else Inches(1.2)

    title_box = slide.shapes.add_textbox(
        Inches(0.65), title_top, Inches(12), title_height
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(30)
    p.font.bold = True
    p.font.color.rgb = COLORS['primary']
    p.font.name = FONTS['title']

    # Subtitle (secondary colour)
    if subtitle_text:
        subtitle_top = Inches(0.9) if not is_long_title else Inches(1.1)
        subtitle_box = slide.shapes.add_textbox(
            Inches(0.65), subtitle_top, Inches(12), Inches(0.5)
        )
        tf_sub = subtitle_box.text_frame
        p_sub = tf_sub.paragraphs[0]
        p_sub.text = subtitle_text
        p_sub.font.size = Pt(20)
        p_sub.font.color.rgb = COLORS['secondary']
        p_sub.font.name = FONTS['body']

    # Divider line under header
    divider = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.4), bar_height,
        Inches(12.533), Inches(0.02)
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = RGBColor(208, 208, 208)
    divider.line.fill.background()

    return bar_height



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
        
        # Split Bullet Symbol (Yellow) and Text (Black)
        run_symbol = p.add_run()
        run_symbol.text = "▸ "
        run_symbol.font.size = Pt(20)
        run_symbol.font.name = FONTS['body']
        run_symbol.font.color.rgb = COLORS['bullet_marker'] # Yellow Accent
        
        run_text = p.add_run()
        run_text.text = text
        run_text.font.size = Pt(20)
        run_text.font.name = FONTS['body']
        run_text.font.color.rgb = COLORS['text_black'] # Black Text
        
        p.space_before = Pt(8)
        p.space_after = Pt(4)
        
        nested_ul = li.find('ul')
        if nested_ul:
            for nested_li in nested_ul.find_all('li', recursive=False):
                nested_text = nested_li.get_text(strip=True)
                if nested_text:
                    np = tf.add_paragraph()
                    run_symbol_nested = np.add_run()
                    run_symbol_nested.text = "    ○ "
                    run_symbol_nested.font.size = Pt(18)
                    run_symbol_nested.font.name = FONTS['body']
                    run_symbol_nested.font.color.rgb = COLORS['bullet_marker']

                    run_text_nested = np.add_run()
                    run_text_nested.text = nested_text
                    run_text_nested.font.size = Pt(18)
                    run_text_nested.font.name = FONTS['body']
                    run_text_nested.font.color.rgb = COLORS['text_black']
                    np.space_before = Pt(4)
    
    return top + Inches(len(items) * 0.5)


def add_code_block(slide, code_elem, top):
    """Add a dark-themed code block."""
    code_content = code_elem.find('pre')
    if not code_content:
        code_content = code_elem.find(class_='code-content')
    
    code_text = code_content.get_text() if code_content else ""
    
    # Calculate dynamic height based on number of lines
    lines = code_text.strip().split('\n')[:20]  # Allow up to 20 lines
    num_lines = len(lines)
    
    # Approx 0.25 inches per line, min 1.5", max 4.5"
    line_height = 0.25
    padding = 0.6  # Top + bottom padding
    calculated_height = (num_lines * line_height) + padding
    box_height = max(1.5, min(4.5, calculated_height))
    
    code_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        CONTENT_LEFT, top,
        CONTENT_WIDTH, Inches(box_height)
    )
    code_box.fill.solid()
    code_box.fill.fore_color.rgb = COLORS['code_bg']
    code_box.line.fill.background()
    
    text_box = slide.shapes.add_textbox(
        CONTENT_LEFT + Inches(0.2), top + Inches(0.2),
        CONTENT_WIDTH - Inches(0.4), Inches(box_height - 0.4)
    )
    tf = text_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    
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


def add_content_heading(slide, heading_elem, top, left=None, width=None):
    """Add a bold styled heading (e.g. 'Descripción')."""
    if left is None:
        left = CONTENT_LEFT
    if width is None:
        width = CONTENT_WIDTH
        
    text = heading_elem.get_text(strip=True)
    if not text:
        return top
        
    # Text box for heading
    text_box = slide.shapes.add_textbox(left, top, width, Inches(0.5))
    tf = text_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.name = FONTS['title']
    p.font.color.rgb = COLORS['primary'] # Use primary blue for headings
    
    return top + Inches(0.6) # Return new top position


def add_logo_middle_center(slide, logo_bytes):
    """Add logo centered both vertically and horizontally."""
    if not logo_bytes:
        return
    
    try:
        logo_stream = io.BytesIO(logo_bytes)
        logo_w = Inches(3) # Larger logo for module end
        logo_h = Inches(1.2)
        
        left = (SLIDE_WIDTH - logo_w) / 2
        top = (SLIDE_HEIGHT - logo_h) / 2
        
        slide.shapes.add_picture(logo_stream, left, top, logo_w, logo_h)
    except Exception as e:
        logger.warning(f"Could not add centered logo: {e}")

