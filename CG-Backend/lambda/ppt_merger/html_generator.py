from typing import Dict
import logging
import re
import boto3

logger = logging.getLogger(__name__)
s3_client = boto3.client('s3')

def calculate_content_height_px(content_blocks) -> tuple:
    """
    Estimate content height in pixels (at 96 DPI).
    Used to detect overflow before rendering to HTML.
    
    HTML slide dimensions:
    - Slide: 1280px width × 720px height (at 96 DPI = 13.333" × 7.5")
    - Available for content: ~550px (conservative estimate after title + subtitle + margins)
    - Content margins: 76px left/right = effective width ~1128px
    
    IMPORTANT: This uses CONSERVATIVE (higher) estimates to prevent overflow
    in the final PPT. Better to split too early than too late!
    """
    estimated_height = 0
    block_breakdown = []
    
    # Standard slide components (more conservative estimates)
    estimated_height += 45  # Title (32pt) - Increased buffer
    estimated_height += 30  # Subtitle area - Increased buffer
    estimated_height += 20  # Spacing margins - Increased buffer
    
    # Estimate content blocks height with REALISTIC multipliers
    for idx, block in enumerate(content_blocks):
        block_type = block.get('type', 'text')
        block_height = 0
        block_info = {'index': idx, 'type': block_type, 'height': 0, 'details': ''}
        
        if block_type == 'heading':
            text = block.get('heading', '')
            # Realistic: 18pt heading (approx 24px) + padding
            block_height = 30  # Increased from 24
            block_height += 10  # Increased from 6
            block_info['height'] = block_height
            block_info['details'] = f"heading: '{text[:50]}...'" if len(text) > 50 else f"heading: '{text}'"
        
        elif block_type == 'bullets':
            items = block.get('items', [])
            item_count = len([i for i in items if str(i).strip()])
            # Realistic: 16pt bullets (approx 21px) + padding
            block_height = item_count * 24  # Increased from 20
            block_height += 8  # Increased from 6
            block_info['height'] = block_height
            block_info['details'] = f"bullets: {item_count} items"
        
        elif block_type == 'text':
            text = block.get('text', '')
            # Realistic wrapping
            lines = max(1, len(text) // 90)  # Fewer chars per line (conservative wrapping)
            block_height = lines * 24  # Increased from 20
            block_height += 8  # Increased from 6
            block_info['height'] = block_height
            block_info['details'] = f"text: {len(text)} chars ({lines} lines)"
        
        elif block_type == 'callout':
            text = block.get('text', '')
            lines = max(1, len(text) // 80)
            block_height = lines * 24 + 20  # Increased
            block_height += 10  # Increased
            block_info['height'] = block_height
            block_info['details'] = f"callout: {len(text)} chars ({lines} lines)"
        
        elif block_type == 'image':
            block_height = 360  # Increased from 350 for safety buffer
            block_height += 15
            block_info['height'] = block_height
            block_info['details'] = "image placeholder"
        
        estimated_height += block_height
        block_breakdown.append(block_info)
    
    return estimated_height, block_breakdown


def should_split_slide(content_blocks) -> bool:
    """
    Determine if content should be split across multiple slides.
    Threshold: 600px available (Conservative - Slide is 720px)
    """
    estimated_height, block_breakdown = calculate_content_height_px(content_blocks)
    threshold = 600  # Reduced from 660 to 600 to FORCE splitting earlier
    
    if estimated_height > threshold:
        overflow_px = estimated_height - threshold
        logger.warning(
            f"⚠️  OVERFLOW DETECTED IN HTML GENERATION"
        )
        logger.warning(
            f"   Total content height: {estimated_height}px"
        )
        logger.warning(
            f"   Available space: {threshold}px"
        )
        logger.warning(
            f"   Overflow: {overflow_px}px ({overflow_px/96:.2f}\")"
        )
        logger.warning(f"   Block breakdown ({len(block_breakdown)} blocks):")
        for block_info in block_breakdown:
            logger.warning(
                f"      Block {block_info['index']}: {block_info['type']:10s} - "
                f"{block_info['height']:3d}px - {block_info['details']}"
            )
        return True
    
    logger.debug(
        f"✅ Content fits: {estimated_height}px / {threshold}px ({len(content_blocks)} blocks)"
    )
    return False


def split_content_blocks(content_blocks) -> tuple:
    """
    Split content blocks into two groups if overflow detected.
    Implements RECURSIVE SPLITTING: keeps splitting until content fits.
    Returns: (blocks_for_slide1, blocks_for_slide2)
    """
    estimated_height, block_breakdown = calculate_content_height_px(content_blocks)
    threshold = 500
    
    if estimated_height <= threshold:
        logger.debug("No split needed - content fits")
        return (content_blocks, [])  # No split needed
    
    # If only 1 block and it's still too large, we can't split it further
    if len(content_blocks) == 1:
        logger.warning(
            f"⚠️  Single block exceeds threshold ({estimated_height}px > {threshold}px) "
            f"but cannot be split further. Will render as-is and may overflow in PPT."
        )
        return (content_blocks, [])
    
    # Split strategy: Keep first portion on slide 1, remainder on slide 2
    # Use aggressive split (1/3 vs 2/3) instead of 1/2 to be safe
    mid_point = max(1, len(content_blocks) // 3)  # Take first 1/3
    slide1_blocks = content_blocks[:mid_point]
    slide2_blocks = content_blocks[mid_point:]
    
    slide1_height, slide1_breakdown = calculate_content_height_px(slide1_blocks)
    slide2_height, slide2_breakdown = calculate_content_height_px(slide2_blocks)
    
    logger.warning(
        f"✂️  SPLITTING SLIDE: {len(content_blocks)} blocks into 2 slides"
    )
    logger.warning(
        f"   Slide 1: {len(slide1_blocks)} blocks, {slide1_height}px "
        f"({slide1_height/96:.2f}\", fit: {slide1_height <= threshold})"
    )
    logger.warning(
        f"   Slide 2: {len(slide2_blocks)} blocks, {slide2_height}px "
        f"({slide2_height/96:.2f}\", fit: {slide2_height <= threshold})"
    )
    
    logger.warning("   Slide 1 blocks:")
    for block_info in slide1_breakdown:
        logger.warning(
            f"      Block {block_info['index']}: {block_info['type']:10s} - "
            f"{block_info['height']:3d}px - {block_info['details']}"
        )
    
    logger.warning("   Slide 2 blocks:")
    for block_info in slide2_breakdown:
        logger.warning(
            f"      Block {block_info['index']}: {block_info['type']:10s} - "
            f"{block_info['height']:3d}px - {block_info['details']}"
        )
    
    # If slide2 still overflows, mark it for recursive split
    if slide2_height > threshold:
        logger.warning(
            f"   ⚠️  Slide 2 still overflows - will be recursively split"
        )
    
    return (slide1_blocks, slide2_blocks)


def render_slide_with_recursive_split(slide, content_blocks, layout, text_reduction_class, 
                                       html_content, overflow_slides, image_url_mapping=None, part_num=1):
    """
    Render slides, splitting if needed (NON-RECURSIVE version).
    Returns: updated html_content
    """
    if image_url_mapping is None:
        image_url_mapping = {}

    # Attach original indices to blocks for context preservation during splits
    for idx, block in enumerate(content_blocks):
        if '_original_index' not in block:
            block['_original_index'] = idx

    # Check if this chunk needs splitting
    if should_split_slide(content_blocks):
        overflow_slides.append(slide.get('slide_number', '?'))
        
        # Keep splitting until we have pieces that fit
        pieces = [content_blocks]
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while len(pieces) > 0 and iteration < max_iterations:
            iteration += 1
            new_pieces = []
            
            for piece in pieces:
                if should_split_slide(piece):
                    # Split this piece
                    part1, part2 = split_content_blocks(piece)
                    new_pieces.append(part1)
                    if part2:
                        new_pieces.append(part2)
                else:
                    # This piece fits, render it
                    # Clean title of existing continuation markers to avoid duplication
                    base_title = slide.get("title", "")
                    # Robust title cleaning to prevent "(cont. 2)(cont. 2)" artifacts
                    base_title = re.sub(r'\s*\(cont\.?\s*\d*\)', '', base_title, flags=re.IGNORECASE)
                    base_title = re.sub(r'\s*\(Part\s*\d+\)', '', base_title, flags=re.IGNORECASE)
                    
                    part_suffix = f" (Part {part_num})" if part_num > 1 else ""
                    html_content += f'<div class="slide{text_reduction_class}" data-slide="{slide.get("slide_number")}{part_suffix}">\n'
                    html_content += f'  <h1 class="slide-title" contenteditable="true">{base_title}{part_suffix}</h1>\n'
                    
                    if slide.get('subtitle') and part_num == 1:
                        html_content += f'  <p class="slide-subtitle" contenteditable="true">{slide["subtitle"]}</p>\n'
                    
                    if layout == 'two-column' and len(piece) >= 2:
                        html_content += '  <div class="two-column">\n'
                        for idx, block in enumerate(piece[:2]):
                            # Use original index from metadata (preserved during splits)
                            original_idx = block.get('_original_index', idx)
                            html_content += '    <div>\n'
                            html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=original_idx)
                            html_content += '    </div>\n'
                        html_content += '  </div>\n'
                        for idx, block in enumerate(piece[2:], start=2):
                            # Use original index from metadata
                            original_idx = block.get('_original_index', idx)
                            html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=original_idx)
                    elif layout in ['image-left', 'image-right'] and len(piece) == 2:
                        # Image + text slide: render in two-column layout
                        html_content += '  <div class="image-with-text">\n'
                        for idx, block in enumerate(piece):
                            original_idx = block.get('_original_index', idx)
                            block_type = block.get('type')
                            if block_type == 'bullets':
                                html_content += '    <div class="text-column">\n'
                                html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=original_idx)
                                html_content += '    </div>\n'
                            elif block_type == 'image':
                                html_content += '    <div class="image-column">\n'
                                html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=original_idx)
                                html_content += '    </div>\n'
                            else:
                                html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=original_idx)
                        html_content += '  </div>\n'
                    else:
                        for idx, block in enumerate(piece):
                            # Use original index from metadata
                            original_idx = block.get('_original_index', idx)
                            html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=original_idx)
                    
                    html_content += '</div>\n\n'
                    part_num += 1
            
            pieces = new_pieces
        
        return html_content
    else:
        # Content fits - render it
        html_content += f'<div class="slide{text_reduction_class}" data-slide="{slide.get("slide_number")}">\n'
        html_content += f'  <h1 class="slide-title" contenteditable="true">{slide.get("title", "")}</h1>\n'
        
        if slide.get('subtitle'):
            html_content += f'  <p class="slide-subtitle" contenteditable="true">{slide["subtitle"]}</p>\n'
        
        if layout == 'two-column' and len(content_blocks) >= 2:
            html_content += '  <div class="two-column">\n'
            for idx, block in enumerate(content_blocks[:2]):
                html_content += '    <div>\n'
                html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx)
                html_content += '    </div>\n'
            html_content += '  </div>\n'
            for idx, block in enumerate(content_blocks[2:], start=2):
                html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx)
        elif layout in ['image-left', 'image-right'] and len(content_blocks) == 2:
            # Image + text slide: render in two-column layout
            html_content += '  <div class="image-with-text">\n'
            for idx, block in enumerate(content_blocks):
                block_type = block.get('type')
                if block_type == 'bullets':
                    html_content += '    <div class="text-column">\n'
                    html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx)
                    html_content += '    </div>\n'
                elif block_type == 'image':
                    html_content += '    <div class="image-column">\n'
                    html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx)
                    html_content += '    </div>\n'
                else:
                    html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx)
            html_content += '  </div>\n'
        else:
            for idx, block in enumerate(content_blocks):
                html_content += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx)
        
        html_content += '</div>\n\n'
        return html_content


def generate_html_from_structure(structure: Dict) -> str:
    """
    Convert infographic structure to clean HTML.
    Each slide = semantic HTML section.
    """
    style = structure.get('style', 'professional')
    image_url_mapping = structure.get('image_url_mapping', {})
    
    # Generate presigned URLs for all images to avoid 403 errors in browser
    # This is critical because the browser cannot access private S3 buckets directly
    logger.info(f"🔑 Generating presigned URLs for {len(image_url_mapping)} images...")
    presigned_mapping = {}
    
    for alt, url in image_url_mapping.items():
        try:
            # Check if it's an S3 URL
            if 's3.amazonaws.com' in url:
                # Extract bucket and key
                bucket_name = None
                key = None
                
                if 'https://s3.amazonaws.com/' in url:
                    parts = url.split('https://s3.amazonaws.com/')
                    if len(parts) > 1:
                        path_parts = parts[1].split('/', 1)
                        if len(path_parts) == 2:
                            bucket_name = path_parts[0]
                            key = path_parts[1]
                else:
                    # Assume bucket.s3.amazonaws.com
                    import re
                    match = re.search(r'https://([^.]+)\.s3\.amazonaws\.com/(.+)', url)
                    if match:
                        bucket_name = match.group(1)
                        key = match.group(2)
                
                if bucket_name and key:
                    # Generate presigned URL (valid for 7 days)
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': key},
                        ExpiresIn=604800  # 7 days
                    )
                    presigned_mapping[alt] = presigned_url
                else:
                    presigned_mapping[alt] = url
            else:
                presigned_mapping[alt] = url
        except Exception as e:
            logger.warning(f"⚠️ Failed to presign URL for {alt}: {e}")
            presigned_mapping[alt] = url
            
    # Use presigned mapping for rendering
    image_url_mapping = presigned_mapping
    
    # Color schemes
    color_schemes = {
        'professional': {
            'primary': '#003366',
            'secondary': '#4682B4',
            'accent': '#FFC000',
            'bg': '#F8F9FA',
            'text': '#333333'
        },
        'modern': {
            'primary': '#212121',
            'secondary': '#607D8B',
            'accent': '#009688',
            'bg': '#FAFAFA',
            'text': '#212121'
        },
        'minimal': {
            'primary': '#000000',
            'secondary': '#757575',
            'accent': '#E0E0E0',
            'bg': '#FFFFFF',
            'text': '#212121'
        }
    }
    
    colors = color_schemes.get(style, color_schemes['professional'])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{structure.get('course_title', 'Course Infographic')}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: {colors['text']};
            background: {colors['bg']};
            line-height: 1.6;
        }}
        
        /* Toolbar for editing controls */
        .toolbar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #2c3e50;
            padding: 15px 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .toolbar-title {{
            color: white;
            font-size: 18px;
            font-weight: 600;
        }}
        
        .toolbar-buttons {{
            display: flex;
            gap: 10px;
        }}
        
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }}
        
        .btn-primary {{
            background: {colors['accent']};
            color: #333;
        }}
        
        .btn-primary:hover {{
            background: {colors['primary']};
            color: white;
        }}
        
        .btn-secondary {{
            background: #34495e;
            color: white;
        }}
        
        .btn-secondary:hover {{
            background: #2c3e50;
        }}
        
        .btn-success {{
            background: #27ae60;
            color: white;
        }}
        
        .btn-success:hover {{
            background: #229954;
        }}
        
        /* Content area with top margin for toolbar */
        .content {{
            margin-top: 80px;
        }}
        
        .slide {{
            width: 1280px;
            height: 720px;  /* FIXED HEIGHT - matches PPT exactly (13.333" x 7.5" at 96 DPI) */
            margin: 20px auto;
            background: white;
            padding: 0;  /* Remove padding, use margins on content instead */
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            page-break-after: always;
            position: relative;
            overflow: hidden;  /* Hide overflow - content should be split beforehand */
        }}
        
        /* Small dark blue square blocks for regular content slides (top corners) */
        .slide:not(.course-title):not(.module-title):not(.lesson-title)::before {{
            content: "";
            position: absolute;
            top: 48px;  /* Align with title text position */
            left: 0;
            width: 50px;  /* Small square block */
            height: 60px;  /* Short rectangular block in corner */
            background: {colors['primary']};  /* Dark blue #003c78 */
            z-index: 1;
        }}
        
        .slide:not(.course-title):not(.module-title):not(.lesson-title)::after {{
            content: "";
            position: absolute;
            top: 48px;  /* Align with title text position */
            right: 0;
            width: 50px;  /* Small square block */
            height: 60px;  /* Short rectangular block in corner */
            background: {colors['primary']};  /* Dark blue #003c78 */
            z-index: 1;
        }}
        
        /* Branded Title Slides - Netec Professional Design */
        
        /* Course Title - Full background image (Netec_Portada_1.png) */
        .slide.course-title {{
            background: url('https://crewai-course-artifacts.s3.amazonaws.com/PPT_Templates/Netec_Portada_1.png') no-repeat center center;
            background-size: cover;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        
        /* Module Title - White background with lateral image */
        .slide.module-title {{
            background: #ffffff;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            position: relative;
        }}
        
        /* Lateral decorative image for module (right side) */
        .slide.module-title::after {{
            content: "";
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            width: 41.67%; /* 5.333" of 13.333" = 40% of slide width */
            background: url('https://crewai-course-artifacts.s3.amazonaws.com/PPT_Templates/Netec_Lateral_1.png') no-repeat right center;
            background-size: cover;
            z-index: 0;
        }}
        
        /* Lesson Title - White background with lateral image (same as module) */
        .slide.lesson-title {{
            background: #ffffff;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            position: relative;
        }}
        
        /* Lateral decorative image for lesson (right side) */
        .slide.lesson-title::after {{
            content: "";
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            width: 41.67%; /* Match module width */
            background: url('https://crewai-course-artifacts.s3.amazonaws.com/PPT_Templates/Netec_Lateral_1.png') no-repeat right center;
            background-size: cover;
            z-index: 0;
        }}
        
        .slide.course-title::before,
        .slide.module-title::before,
        .slide.lesson-title::before {{
            border: none; /* Remove safe area border for title slides */
        }}
        
        /* Logo in top-left corner for module and lesson slides */
        .slide.module-title .title-content::before,
        .slide.lesson-title .title-content::before {{
            content: "";
            position: absolute;
            top: 40px;
            left: 40px;
            width: 180px;
            height: 60px;
            background: url('https://crewai-course-artifacts.s3.amazonaws.com/logo/LogoNetec.png') no-repeat left center;
            background-size: contain;
            z-index: 2;
        }}
        
        .title-content {{
            text-align: left;
            padding: 60px 60px;
            max-width: 58%; /* 7.75" of 13.333" - Leave space for lateral image */
            position: relative;
            z-index: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-start; /* Align to top */
        }}
        
        /* Course title - centered styling */
        .slide.course-title .title-content {{
            text-align: center;
            max-width: 1000px;
            padding: 40px 100px;
        }}
        
        /* Course Title - Largest, white text */
        .slide.course-title .main-title {{
            font-size: 60pt;
            font-weight: 700;
            color: #ffffff;
            margin: 0;
            padding: 0;
            line-height: 1.2;
            text-shadow: 2px 2px 8px rgba(0,0,0,0.3);
        }}
        
        /* Module Title - Dark blue, left-aligned */
        .slide.module-title .main-title {{
            font-size: 48pt;
            font-weight: 700;
            color: #003c78; /* Dark blue */
            margin: 80px 0 0 0; /* Space for logo above */
            padding: 0;
            line-height: 1.3; /* Increased from 1.2 for better multi-line spacing */
            word-wrap: break-word;
            overflow-wrap: break-word;
            max-height: none; /* Dynamic height - no maximum */
            min-height: auto; /* Auto height based on content */
        }}
        
        /* Lesson Title - Dark blue, left-aligned */
        .slide.lesson-title .main-title {{
            font-size: 42pt;
            font-weight: 700;
            color: #003c78; /* Dark blue */
            margin: 80px 0 0 0; /* Space for logo above */
            padding: 0;
            line-height: 1.3; /* Increased from 1.2 for better multi-line spacing */
            word-wrap: break-word;
            overflow-wrap: break-word;
            max-height: none; /* Dynamic height - no maximum */
            min-height: auto; /* Auto height based on content */
        }}
        
        /* Module subtitle below lesson title (cyan) - Dynamic margin to prevent overlap */
        .main-subtitle {{
            font-size: 28pt;
            color: #00bceb; /* Cyan */
            margin: 20px 0 0 0; /* Increased from 15px to give more breathing room */
            font-weight: 400;
            line-height: 1.3;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        
        /* Remove decorative elements - we use images now */
        .slide.course-title .title-content::before,
        .slide.module-title .title-content::after,
        .slide.lesson-title .title-content::after {{
            display: none;
        }}
        
        /* Overflow indicator for debugging */
        .slide.overflow-warning {{
            border: 3px solid red;
        }}
        
        .slide.overflow-warning::after {{
            content: "⚠️ CONTENT OVERFLOW - SPLIT NEEDED";
            position: absolute;
            top: 0;
            right: 0;
            background: red;
            color: white;
            padding: 5px 10px;
            font-size: 12px;
            font-weight: bold;
            z-index: 1000;
        }}
        
        /* Logo in BOTTOM-right corner for regular content slides (not hidden by title) */
        .slide:not(.course-title):not(.module-title):not(.lesson-title) {{
            background-image: url('https://crewai-course-artifacts.s3.amazonaws.com/logo/LogoNetec.png');
            background-repeat: no-repeat;
            background-position: bottom 20px right 20px;  /* Bottom-right corner with margin */
            background-size: 180px 60px;  /* Logo size */
        }}
        
        /* Editable elements styling */
        [contenteditable="true"] {{
            outline: none;
            transition: background 0.3s;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: normal; /* Ensure text wraps instead of overflow */
        }}
        
        [contenteditable="true"]:hover {{
            background: rgba(255, 255, 0, 0.1);
            cursor: text;
        }}
        
        [contenteditable="true"]:focus {{
            background: rgba(255, 255, 0, 0.2);
            padding: 5px;
            margin: -5px;
            border-radius: 3px;
        }}
        
        .slide-title {{
            font-size: 32pt;
            font-weight: bold;
            color: {colors['primary']};
            margin: 25px 76px 10px 76px;  /* Reduced top margin from 48px */
            position: relative;
            z-index: 1;
            line-height: 1.3;  /* Increased from default for better multi-line spacing */
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: normal;
            min-height: auto;  /* Dynamic height based on content */
        }}
        
        .slide-subtitle {{
            font-size: 20pt;
            color: {colors['secondary']};
            margin: 5px 76px 20px 76px;  /* Reduced from 15px top, 30px bottom */
            position: relative;
            z-index: 1;
            line-height: 1.3;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        
        .slide-content {{
            margin: 0 76px;  /* Standard 0.8" side margins */
            overflow: visible;
            position: relative;
            z-index: 1;
        }}
        
        .content-block {{
            margin: 0 76px 15px 76px;  /* Reduced bottom margin from 25px */
        }}
        
        .block-heading {{
            font-size: 24pt;
            font-weight: 600;
            color: {colors['primary']};
            margin-top: 15px;  /* Reduced from 25px */
            margin-bottom: 10px;  /* Reduced from 15px */
        }}
        
        .bullets {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        
        .bullets li {{
            font-size: 20pt;
            line-height: 1.4;
            padding: 4px 0 4px 35px;  /* Reduced padding from 8px */
            position: relative;
            margin-bottom: 4px;  /* Reduced from 6px */
        }}
        
        .bullets li:before {{
            content: "▸";
            color: {colors['accent']};
            font-size: 24pt;
            position: absolute;
            left: 0;
            font-weight: bold;
        }}
        
        /* Second-level bullets (indented, different symbol) */
        .bullets li.level-2 {{
            font-size: 18pt;
            padding-left: 60px;  /* More indentation */
            margin-bottom: 4px;
        }}
        
        .bullets li.level-2:before {{
            content: "▪";  /* Square bullet */
            color: {colors['secondary']};
            font-size: 20pt;
            left: 35px;  /* Indented from parent */
        }}
        
        /* Compact text mode - for slides with text_reduction flag */
        .slide.compact-text .block-heading {{
            font-size: 16pt;  /* Reduced from 18pt */
            margin-bottom: 6px;  /* Reduced from 8px */
        }}
        
        .slide.compact-text .bullets li {{
            font-size: 13pt;  /* Reduced from 16pt */
            line-height: 1.15;  /* Reduced from 1.25 */
            padding: 2px 0 2px 25px;  /* Tighter padding */
            margin-bottom: 2px;  /* Reduced from 3px */
        }}
        
        .slide.compact-text .bullets li:before {{
            font-size: 14pt;  /* Reduced from 18pt */
        }}
        
        .slide.compact-text .bullets li.level-2 {{
            font-size: 12pt;  /* Reduced from 18pt */
            padding-left: 45px;
        }}
        
        .image-container {{
            text-align: center;
            margin: 20px 0;
        }}
        
        .image-container img {{
            max-width: 100%;
            max-height: 600px;
            object-fit: contain;
        }}
        
        .image-caption {{
            font-size: 18px;
            color: {colors['secondary']};
            margin-top: 10px;
            font-style: italic;
            display: none; /* Caption hidden - maximizing image space */
        }}
        
        .callout {{
            background: {colors['accent']}20;
            border-left: 4px solid {colors['accent']};
            padding: 20px;
            font-size: 22px;
        }}
        
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
        }}
        
        .image-with-text {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            align-items: start;
        }}
        
        .image-with-text .text-column {{
            font-size: 20px;
            line-height: 1.6;
        }}
        
        .image-with-text .image-column {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        @media print {{
            .toolbar {{
                display: none;
            }}
            
            .content {{
                margin-top: 0;
            }}
            
            .slide {{
                page-break-after: always;
                margin: 0;
                box-shadow: none;
                width: 100%;
                height: auto;
            }}
            
            [contenteditable="true"]:hover,
            [contenteditable="true"]:focus {{
                background: transparent !important;
                padding: 0 !important;
                margin: 0 !important;
            }}
        }}
    </style>
</head>
<body>
    <!-- Editing Toolbar -->
    <div class="toolbar">
        <div class="toolbar-title">
            📊 {structure.get('course_title', 'Course Infographic')} - Editable Version
        </div>
        <div class="toolbar-buttons">
            <button class="btn btn-secondary" onclick="toggleEditMode()">
                <span id="edit-btn-text">🔒 Lock Editing</span>
            </button>
            <button class="btn btn-success" onclick="saveChanges()">
                💾 Save Changes
            </button>
            <button class="btn btn-primary" onclick="downloadPDF()">
                📄 Download PDF
            </button>
        </div>
    </div>
    
    <div class="content">
"""
    
    # Generate slides with editable content
    slides_to_process = list(structure.get('slides', []))
    overflow_slides = []
    split_slides_count = 0
    
    idx = 0
    while idx < len(slides_to_process):
        slide = slides_to_process[idx]
        layout = slide.get('layout_hint', 'single-column')
        content_blocks = slide.get('content_blocks', [])
        
        # Special handling for branded title slides
        if layout in ['course-title', 'module-title', 'lesson-title']:
            html += f'<div class="slide {layout}" data-slide="{slide.get("slide_number")}">\n'
            html += f'  <div class="title-content">\n'
            html += f'    <h1 class="main-title" contenteditable="true">{slide.get("title", "")}</h1>\n'
            if slide.get('subtitle'):
                html += f'    <p class="main-subtitle" contenteditable="true">{slide["subtitle"]}</p>\n'
            html += f'  </div>\n'
            html += '</div>\n\n'
            idx += 1
            continue
        
        # IMPORTANT: Don't skip title-only slides or special slides like Agenda
        # Agenda slides might have minimal content blocks but are still needed
        slide_title = slide.get('title', '').lower()
        is_agenda_slide = 'agenda' in slide_title
        
        # Skip completely empty slides UNLESS they are special slides (like Agenda)
        if not content_blocks or len(content_blocks) == 0:
            if not is_agenda_slide:
                idx += 1
                continue  # Skip this slide entirely
        else:
            # Check if all content blocks would be filtered out (all empty)
            has_any_content = False
            for idx_check, block in enumerate(content_blocks):
                block_html = generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx_check)
                if block_html.strip():  # If any block generates non-empty HTML
                    has_any_content = True
                    break
            
            if not has_any_content and not is_agenda_slide:
                idx += 1
                continue  # Skip slides where all content blocks are empty (unless Agenda)
        
        # ========== NEW: Detect and handle overflow with RECURSIVE splitting ==========
        text_reduction_class = ' compact-text' if slide.get('text_reduction', False) else ''
        
        # Special handling: Don't split Agenda slides, render them as-is despite overflow
        # Agenda slides need to show all items together for context
        if is_agenda_slide:
            logger.info(f"📋 Rendering Agenda slide without splitting (all items together)")
            html += f'<div class="slide{text_reduction_class}" data-slide="{slide.get("slide_number")}">\n'
            html += f'  <h1 class="slide-title" contenteditable="true">{slide.get("title", "")}</h1>\n'
            if slide.get('subtitle'):
                html += f'  <p class="slide-subtitle" contenteditable="true">{slide["subtitle"]}</p>\n'
            for idx_block, block in enumerate(content_blocks):
                html += generate_content_block_html(block, image_url_mapping, all_blocks=content_blocks, block_index=idx_block)
            html += '</div>\n\n'
            # Note: Agenda overflow will be flagged by client-side JS, but we accept it
        else:
            # Use recursive function to handle splitting for non-Agenda slides
            html = render_slide_with_recursive_split(
                slide, content_blocks, layout, text_reduction_class,
                html, overflow_slides, image_url_mapping, part_num=1
            )
            split_slides_count += 1
        
        idx += 1
    
    # Log summary
    if overflow_slides:
        logger.warning(
            f"✂️  SPLIT {split_slides_count} overflowing slides in HTML generation. "
            f"Slide numbers: {overflow_slides}"
        )
        logger.warning(
            f"   Slide count increased: {len(slides_to_process)} → "
            f"{len(slides_to_process) + split_slides_count} (added {split_slides_count} split slides)"
        )
    else:
        logger.info(
            f"✅ HTML generation complete: All {len(slides_to_process)} slides fit within dimensions"
        )
    
    html += """
    </div> <!-- End content -->
    
    <script>
        let editingEnabled = true;
        
        // Check for content overflow on load
        window.addEventListener('load', () => {
            checkContentOverflow();
            const saved = localStorage.getItem('infographic_autosave');
            if (saved && confirm('📝 Found auto-saved changes. Restore them?')) {
                document.querySelector('.content').innerHTML = saved;
                checkContentOverflow();
            }
        });
        
        // Detect slides with content overflow
        function checkContentOverflow() {
            const slides = document.querySelectorAll('.slide');
            let overflowCount = 0;
            
            slides.forEach((slide, index) => {
                const slideHeight = 720; // Fixed height in pixels
                const contentHeight = slide.scrollHeight;
                
                if (contentHeight > slideHeight) {
                    slide.classList.add('overflow-warning');
                    overflowCount++;
                    console.warn(`⚠️ Slide ${index + 1} overflow: ${contentHeight}px > ${slideHeight}px`);
                } else {
                    slide.classList.remove('overflow-warning');
                }
            });
            
            if (overflowCount > 0) {
                console.warn(`⚠️ WARNING: ${overflowCount} slide(s) have content overflow!`);
                alert(`⚠️ WARNING: ${overflowCount} slide(s) have content that exceeds the PPT dimensions.\\n\\nThese slides are marked with a red border. The content may be cut off in PowerPoint.\\n\\nConsider regenerating with better content distribution.`);
            } else {
                console.log('✅ All slides fit within PPT dimensions');
            }
        }
        
        // Toggle edit mode
        function toggleEditMode() {
            editingEnabled = !editingEnabled;
            const editables = document.querySelectorAll('[contenteditable]');
            const btnText = document.getElementById('edit-btn-text');
            
            editables.forEach(el => {
                el.contentEditable = editingEnabled;
            });
            
            if (editingEnabled) {
                btnText.textContent = '🔒 Lock Editing';
            } else {
                btnText.textContent = '🔓 Enable Editing';
            }
        }
        
        // Save changes (downloads edited HTML)
        function saveChanges() {
            checkContentOverflow(); // Check before saving
            const html = document.documentElement.outerHTML;
            const blob = new Blob([html], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'infographic_edited.html';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            alert('✅ Changes saved! The edited HTML file has been downloaded.');
        }
        
        // Download as PDF
        function downloadPDF() {
            alert('📄 PDF Download Instructions:\\n\\n1. Press Ctrl+P (Windows/Linux) or Cmd+P (Mac)\\n2. Select "Save as PDF" as the destination\\n3. Click Save\\n\\nThe PDF will preserve all your edits and formatting!');
            window.print();
        }
        
        // Auto-save to localStorage every 30 seconds
        setInterval(() => {
            if (editingEnabled) {
                const content = document.querySelector('.content').innerHTML;
                localStorage.setItem('infographic_autosave', content);
                console.log('✅ Auto-saved at', new Date().toLocaleTimeString());
            }
        }, 30000);
        
        // Warn before leaving if there are unsaved changes
        let initialContent = document.querySelector('.content').innerHTML;
        window.addEventListener('beforeunload', (e) => {
            const currentContent = document.querySelector('.content').innerHTML;
            if (currentContent !== initialContent && editingEnabled) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            }
        });
    </script>
</body>
</html>
"""
    
    return html


def generate_content_block_html(block: Dict, image_url_mapping: Dict = None, all_blocks: list = None, block_index: int = -1) -> str:
    """Generate HTML for a content block with editable content.
    Returns empty string if block is empty (no meaningful content).
    
    Args:
        block: The current content block to render
        image_url_mapping: Mapping of image references to URLs
        all_blocks: All content blocks in the slide (for context)
        block_index: Index of current block in all_blocks
    """
    if image_url_mapping is None:
        image_url_mapping = {}
    if all_blocks is None:
        all_blocks = []

    block_type = block.get('type', 'text')
    heading = block.get('heading') or ''
    heading = str(heading).strip()
    
    # Validate content exists - skip empty blocks
    has_content = False
    
    if block_type == 'bullets':
        items = block.get('items', [])
        has_content = bool(items and any(str(item).strip() for item in items))
    elif block_type == 'callout':
        text = block.get('text') or ''
        text = str(text).strip()
        has_content = bool(text)
    elif block_type == 'text':
        text = block.get('text') or ''
        text = str(text).strip()
        has_content = bool(text)
    elif block_type == 'image':
        has_content = bool(block.get('image_reference'))  # Image always has content
    
    # Skip if no heading AND no content
    if not heading and not has_content:
        return ''
    
    # Skip if heading exists but content is explicitly empty (heading-only blocks without substance)
    if heading and not has_content and block_type in ['text', 'callout']:
        return ''  # Don't render heading-only blocks with empty text/callout
    
    html = '<div class="content-block">\n'
    
    if heading:
        html += f'  <h2 class="block-heading" contenteditable="true">{heading}</h2>\n'
    
    if block_type == 'bullets' and has_content:
        html += '  <ul class="bullets">\n'
        for item in block.get('items', []):
            if str(item).strip():  # Only add non-empty bullets
                item_str = str(item)
                # Detect second-level bullets by indentation (4+ leading spaces)
                leading_spaces = len(item_str) - len(item_str.lstrip())
                is_second_level = leading_spaces >= 4
                
                if is_second_level:
                    # Remove leading spaces and any bullet symbols (○, •, -, etc)
                    clean_item = item_str.strip()
                    # Remove common bullet symbols from start
                    for symbol in ['○', '●', '•', '-', '*']:
                        if clean_item.startswith(symbol):
                            clean_item = clean_item[1:].strip()
                            break
                    html += f'    <li class="level-2" contenteditable="true">{clean_item}</li>\n'
                else:
                    html += f'    <li contenteditable="true">{item_str}</li>\n'
        html += '  </ul>\n'
    
    elif block_type == 'image':
        # Resolve image URL first
        image_ref = block.get('image_reference', '')
        image_url = image_url_mapping.get(image_ref, '')
        
        # If not in mapping but looks like a URL, use it directly
        if not image_url and image_ref.startswith('http'):
            image_url = image_ref
            
        # Fuzzy lookup: Try case-insensitive match if exact match failed
        if not image_url and image_ref:
            # Helper to normalize strings (remove non-alphanumeric)
            def normalize(s):
                return re.sub(r'[^a-z0-9]', '', str(s).lower())
            
            ref_norm = normalize(image_ref)
            
            # 1. Try case-insensitive match
            for key, url in image_url_mapping.items():
                if key.lower().strip() == image_ref.lower().strip():
                    image_url = url
                    break
            
            # 2. Try normalized match
            if not image_url:
                for key, url in image_url_mapping.items():
                    if normalize(key) == ref_norm:
                        image_url = url
                        break

            # 3. Try partial match (if image_ref is part of the key or vice versa)
            if not image_url:
                for key, url in image_url_mapping.items():
                    key_norm = normalize(key)
                    # Check if one contains the other (ignoring case)
                    if image_ref.lower() in key.lower() or key.lower() in image_ref.lower():
                        # Only accept if significant overlap (e.g. > 5 chars) to avoid false positives
                        if len(image_ref) > 5 and len(key) > 5:
                            image_url = url
                            break
                    # Check normalized containment
                    elif ref_norm and key_norm and (ref_norm in key_norm or key_norm in ref_norm):
                         if len(ref_norm) > 5 and len(key_norm) > 5:
                            image_url = url
                            break
            
        if image_url:
            # Simply render image in container - NO TWO-COLUMN LOGIC HERE
            # The structure should already have bullets+image ordered correctly
            html += '  <div class="image-container">\n'
            html += f'    <img src="{image_url}" alt="{block.get("caption", "")}">\n'
            if block.get('caption'):
                html += f'    <div class="image-caption">{block.get("caption")}</div>\n'
            html += '  </div>\n'
        else:
            # Fallback to placeholder
            html += '  <div class="image-container">\n'
            logger.warning(f"⚠️ Image not found for reference: '{image_ref}'. Available keys: {list(image_url_mapping.keys())[:5]}...")
            
            # Try to find a similar image from the same module/lesson
            fallback_url = None
            if image_ref and '-' in str(image_ref):
                # Extract module/lesson prefix (e.g., "01-02" from "01-02-0001")
                parts = str(image_ref).split('-')
                if len(parts) >= 2:
                    prefix = f"{parts[0]}-{parts[1]}"
                    # Find first image with same prefix
                    for key, url in image_url_mapping.items():
                        if key.startswith(prefix):
                            fallback_url = url
                            logger.info(f"✅ Using fallback image: {key} for missing {image_ref}")
                            break
            
            if fallback_url:
                html += f'    <img src="{fallback_url}" alt="Related content">\n'
                html += f'    <div class="image-caption" style="color:#f39c12;">⚠️ Using related image (original not found: {image_ref})</div>\n'
            else:
                html += f'    <div class="image-placeholder" style="background:#f0f0f0;height:300px;display:flex;align-items:center;justify-content:center;">\n'
                html += f'      <span style="color:#999;">Image not found: {image_ref}</span>\n'
                html += '    </div>\n'
            html += '  </div>\n'
    
    elif block_type == 'callout':
        text = block.get('text') or ''
        html += f'  <div class="callout" contenteditable="true">{text}</div>\n'
    
    elif block_type == 'text':
        text = block.get('text') or ''
        html += f'  <p style="font-size:24px;line-height:1.6;" contenteditable="true">{text}</p>\n'
    
    html += '</div>\n'
    return html
