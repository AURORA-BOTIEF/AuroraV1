#!/usr/bin/env python3
"""
Strands Visual Optimizer (Agent 2)
Intelligently fixes oversized slides and optimizes visual layout using Claude Haiku 4.5.
This runs AFTER HTML generation as an independent post-processing step.
"""
import json
import logging
import os
import re
import boto3
from typing import Dict, List, Any
from bs4 import BeautifulSoup

# Logging
logger = logging.getLogger("aurora.visual_optimizer")
logger.setLevel(logging.INFO)

# AWS Clients
s3_client = boto3.client('s3', region_name='us-east-1')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

# Model Configuration
DEFAULT_MODEL = "us.anthropic.claude-haiku-4.5-20251001-v1:0"

# PPT Dimension Constants - MUST MATCH actual HTML rendering
# Browser slide is 720px height with FIXED layout
MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 460  # Slide with subtitle
MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520    # Slide without subtitle
BULLET_HEIGHT = 50       # CRITICAL: 20pt font × 1.4 line-height + 8px padding + 4px margin = 50px (MATCHES CSS EXACTLY)
LINE_HEIGHT = 30         # Line wrapping height
HEADING_HEIGHT = 65      # 20pt font + spacing
IMAGE_HEIGHT = 550       # CRITICAL: Matches CSS max-height (550px as per infographic_generator.py CSS)
SPACING_BETWEEN_BLOCKS = 20  # Vertical spacing between blocks
CHARS_PER_LINE = 90      # Characters per line for wrapping calculation


def lambda_handler(event, context):
    """
    Main Lambda handler for Visual Optimizer (Agent 2).
    """
    try:
        logger.info("🔧 Strands Visual Optimizer (Agent 2) started")
        
        # Extract inputs
        html_s3_key = event.get('html_s3_key')
        bucket = event.get('bucket', 'crewai-course-artifacts')
        course_id = event.get('course_id')
        
        if not html_s3_key:
            raise ValueError("Missing required parameter: html_s3_key")
        
        logger.info(f"📥 Loading HTML from s3://{bucket}/{html_s3_key}")
        
        # Download HTML
        response = s3_client.get_object(Bucket=bucket, Key=html_s3_key)
        html_content = response['Body'].read().decode('utf-8')
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find oversized slides
        oversized_slides = find_oversized_slides(soup)
        
        if not oversized_slides:
            logger.info("✅ No oversized slides found - HTML is already optimal")
            return {
                'statusCode': 200,
                'optimized_html_key': html_s3_key,  # No changes needed
                'fixes_applied': 0,
                'slides_optimized': []
            }
        
        logger.info(f"🔍 Found {len(oversized_slides)} oversized slides")
        
        # Optimize each overflow slide using AI with throttling protection
        import time as time_module
        
        slides_optimized = []
        MAX_SLIDES_TO_FIX = 15  # Reduced from 30: Each slide ~25-40s with throttling = 6-10 minutes for 15 slides (safe for 10min Lambda timeout)
        slides_to_fix = oversized_slides[:MAX_SLIDES_TO_FIX]
        
        if len(oversized_slides) > MAX_SLIDES_TO_FIX:
            logger.warning(f"⚠️  Found {len(oversized_slides)} overflow slides, but limiting to {MAX_SLIDES_TO_FIX} to prevent timeout")
            logger.warning(f"   Remaining {len(oversized_slides) - MAX_SLIDES_TO_FIX} slides will not be optimized this run")
            logger.warning(f"   💡 TIP: Run state machine multiple times to fix all overflow slides incrementally")
        
        for idx, slide_info in enumerate(slides_to_fix, 1):
            slide_title = slide_info['title']
            bullet_count = slide_info['bullets']
            image_count = slide_info['images']
            
            logger.info(f"🔧 Optimizing slide {idx}/{len(slides_to_fix)}: {slide_title} ({bullet_count} bullets, {image_count} images)")
            
            # FAST PATH: Use algorithmic split for simple text-only slides (no AI needed!)
            # This is 100x faster - no Bedrock API calls, no throttling, instant results
            if image_count == 0 and bullet_count >= 4:
                logger.info(f"   ⚡ Using FAST algorithmic split (text-only slide)")
                optimized_html = split_slide_algorithmically(
                    slide_info['html'],
                    bullet_count,
                    slide_info['max_height']
                )
            else:
                # SLOW PATH: Use AI for complex slides with images
                logger.info(f"   🤖 Using AI optimization (slide has {image_count} images)")
                
                # Add delay to prevent Bedrock throttling
                if idx > 1:
                    delay = min(2.0 * (idx // 5), 5.0)
                    logger.info(f"   ⏱️  Waiting {delay:.1f}s to avoid throttling...")
                    time_module.sleep(delay)
                
                optimized_html = optimize_slide_with_ai(
                    slide_info['html'],
                    bullet_count,
                    image_count,
                    slide_info['max_height']
                )
            
            if not optimized_html:
                logger.warning(f"⚠️ Optimization returned None for {slide_title} - skipping")
                continue
            
            if optimized_html:
                # Replace in soup
                slide_element = soup.find('div', {'data-slide-id': slide_info['slide_id']})
                if not slide_element:
                    logger.error(f"❌ Could not find slide with ID {slide_info['slide_id']} in HTML! Skipping optimization.")
                    continue
                
                if slide_element:
                    # Parse the new HTML fragment
                    new_content_soup = BeautifulSoup(optimized_html, 'html.parser')
                    
                    # The AI might return multiple <div>s. We need to insert them all.
                    # We replace the original slide with the first new one, then insert the rest after it.
                    new_slides = new_content_soup.find_all('div', class_='slide')
                    
                    if new_slides:
                        # Replace original with first new slide
                        slide_element.replace_with(new_slides[0])
                        
                        # Insert remaining slides after the first one
                        current_node = new_slides[0]
                        for i in range(1, len(new_slides)):
                            current_node.insert_after(new_slides[i])
                            current_node = new_slides[i]
                            
                        slides_optimized.append(slide_title)
                        logger.info(f"✅ Optimized: {slide_title} -> Split into {len(new_slides)} slides")
                    else:
                        logger.warning(f"⚠️ AI returned HTML but no 'slide' divs found for {slide_title}")

        # Save optimized HTML
        optimized_html_content = str(soup)
        optimized_key = html_s3_key.replace('.html', '_optimized.html')
        
        s3_client.put_object(
            Bucket=bucket,
            Key=optimized_key,
            Body=optimized_html_content.encode('utf-8'),
            ContentType='text/html'
        )
        
        logger.info(f"💾 Saved optimized HTML to s3://{bucket}/{optimized_key}")
        logger.info(f"🎉 Visual Optimizer completed: {len(slides_optimized)} slides fixed")
        
        return {
            'statusCode': 200,
            'optimized_html_key': optimized_key,
            'fixes_applied': len(slides_optimized),
            'slides_optimized': slides_optimized
        }
        
    except Exception as e:
        logger.error(f"❌ Visual Optimizer failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }


def find_oversized_slides(soup: BeautifulSoup) -> List[Dict]:
    """
    Detect overflow slides using ACCURATE height calculation.
    
    Uses the same logic as browser JavaScript but with Python approximation.
    More accurate than old heuristics (bullets > 10) but still an estimation.
    
    For production: Could use headless browser (Playwright/Selenium) for 100% accuracy,
    but this Python estimation is close enough for most cases.
    """
    overflow_slides = []
    slides = soup.find_all('div', class_='slide')
    
    logger.info(f"🔍 Analyzing {len(slides)} slides for overflow using height calculation")
    
    # Constants matching CSS (from infographic_generator.py)
    SLIDE_HEIGHT = 720
    MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 460
    MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520
    BULLET_HEIGHT = 44
    IMAGE_HEIGHT = 450  # Actual CSS max-height from infographic_generator.py
    HEADING_HEIGHT = 65
    CALLOUT_HEIGHT = 75
    SPACING = 20
    
    # Track stats
    total_slides = 0
    title_slides = 0
    overflow_detected = 0
    
    for idx, slide in enumerate(slides):
        # CRITICAL FIX: Add slide-id to HTML so we can find it later for replacement
        slide_id = slide.get('data-slide-id', f'slide-{idx}')
        if 'data-slide-id' not in slide.attrs:
            slide['data-slide-id'] = slide_id  # Add ID to HTML if missing
        
        title_elem = slide.find('h1', class_='slide-title')
        title = title_elem.get_text(strip=True) if title_elem else f"Slide {idx + 1}"
        
        # Skip title slides (they don't overflow)
        classes = slide.get('class', [])
        if 'course-title' in classes or 'module-title' in classes or 'lesson-title' in classes:
            title_slides += 1
            continue
        
        total_slides += 1
        
        # Calculate content height (same logic as JavaScript scrollHeight check)
        subtitle_elem = slide.find('h2', class_='slide-subtitle')
        has_subtitle = subtitle_elem is not None and subtitle_elem.get_text(strip=True)
        max_height = MAX_CONTENT_HEIGHT_WITH_SUBTITLE if has_subtitle else MAX_CONTENT_HEIGHT_NO_SUBTITLE
        
        # Estimate content height
        content_height = 0
        content_blocks = slide.find_all(['ul', 'div'], class_=['bullets', 'image-container', 'callout', 'image-with-text'])
        
        for block_idx, block in enumerate(content_blocks):
            if block_idx > 0:
                content_height += SPACING
            
            # Bullet lists
            if 'bullets' in block.get('class', []):
                bullets = block.find_all('li')
                # Each bullet: base height + wrapping for long text
                for bullet in bullets:
                    text_len = len(bullet.get_text(strip=True))
                    lines = max(1, (text_len // 90) + 1)  # 90 chars per line
                    content_height += BULLET_HEIGHT * lines
            
            # Images
            elif 'image-container' in block.get('class', []) or 'image-with-text' in block.get('class', []):
                content_height += IMAGE_HEIGHT
                caption = block.find(class_='image-caption')
                if caption:
                    content_height += 30
            
            # Callouts
            elif 'callout' in block.get('class', []):
                text_len = len(block.get_text(strip=True))
                lines = max(1, (text_len // 90) + 1)
                content_height += CALLOUT_HEIGHT + (lines - 1) * 30
        
        # Check for overflow (with 10% tolerance to avoid false positives)
        overflow_threshold = max_height * 1.10  # 10% tolerance
        
        if content_height > overflow_threshold:
            overflow_detected += 1
            overflow_amount = content_height - max_height
            
            # Gather metrics
            bullets = len(slide.find_all('li'))
            images = len(slide.find_all('img'))
            paragraphs = len(slide.find_all('p'))
            headings = len(slide.find_all(['h3', 'h4']))
            
            overflow_slides.append({
                'slide_id': slide_id,
                'title': title,
                'has_subtitle': has_subtitle,
                'bullets': bullets,
                'images': images,
                'paragraphs': paragraphs,
                'headings': headings,
                'overflow_amount': str(int(overflow_amount)),
                'max_height': max_height,
                'estimated_height': int(content_height),
                'html': str(slide)
            })
            logger.warning(f"⚠️  OVERFLOW DETECTED on slide {idx + 1} '{title}': {int(content_height)}px > {max_height}px (excess: {int(overflow_amount)}px, bullets={bullets}, images={images})")
    
    logger.info(f"📊 Overflow Detection Summary:")
    logger.info(f"   Total slides: {len(slides)}")
    logger.info(f"   Title slides (skipped): {title_slides}")
    logger.info(f"   Content slides: {total_slides}")
    logger.info(f"   Overflow detected: {overflow_detected} slides")
    logger.info(f"🎯 Found {overflow_detected} overflow slides using height calculation (with 10% tolerance)")
    
    return overflow_slides


# Removed estimate_content_height - now using AI-based density analysis instead of pixel estimation


def split_slide_algorithmically(slide_html: str, bullet_count: int, max_height: int) -> str:
    """
    Fast algorithmic slide splitting - NO AI needed!
    
    Simple strategy:
    1. Parse the slide HTML
    2. Split bullet lists in half
    3. Create 2 slides with proper continuation numbering
    4. Return updated HTML
    
    This is 100x faster than AI and works perfectly for simple overflow.
    """
    from bs4 import BeautifulSoup
    import re
    
    try:
        soup = BeautifulSoup(slide_html, 'html.parser')
        slide = soup.find('div', class_='slide')
        
        if not slide:
            logger.error("Could not find slide div in HTML")
            return None
        
        # Get slide title
        title_elem = slide.find('h1', class_='slide-title')
        title = title_elem.get_text(strip=True) if title_elem else "Slide"
        
        # Check if title already has continuation number
        cont_match = re.search(r'\(cont\.\s*(\d+)\)', title, re.IGNORECASE)
        if cont_match:
            # Extract base title and current number
            base_title = re.sub(r'\s*\(cont\.?\s*\d*\)', '', title, flags=re.IGNORECASE).strip()
            current_num = int(cont_match.group(1))
            next_num = current_num + 1
        else:
            # First split - add (cont. 1)
            base_title = title
            next_num = 1
        
        # Find all bullet lists
        bullet_lists = slide.find_all('ul', class_='bullets')
        
        if not bullet_lists:
            logger.warning(f"No bullet lists found in slide - cannot split")
            return None
        
        # Simple strategy: Split first bullet list in half
        first_list = bullet_lists[0]
        bullets = first_list.find_all('li', recursive=False)
        
        if len(bullets) < 4:
            logger.warning(f"Only {len(bullets)} bullets - splitting may not help")
            # For very few bullets, just return original (AI might handle better)
            return None
        
        mid_point = len(bullets) // 2
        
        # Create first slide (original with first half of bullets)
        first_slide = soup.new_tag('div', **{'class': 'slide'})
        
        # Copy title
        first_title = soup.new_tag('h1', **{'class': 'slide-title'})
        first_title.string = title  # Keep original title
        first_slide.append(first_title)
        
        # Copy subtitle if exists
        subtitle_elem = slide.find('h2', class_='slide-subtitle')
        if subtitle_elem:
            first_subtitle = soup.new_tag('h2', **{'class': 'slide-subtitle'})
            first_subtitle.string = subtitle_elem.get_text(strip=True)
            first_slide.append(first_subtitle)
        
        # Create content div
        first_content = soup.new_tag('div', **{'class': 'slide-content'})
        
        # Add first half of bullets
        first_ul = soup.new_tag('ul', **{'class': 'bullets'})
        for bullet in bullets[:mid_point]:
            first_ul.append(bullet.__copy__())
        first_content.append(first_ul)
        first_slide.append(first_content)
        
        # Create second slide (continuation with second half)
        second_slide = soup.new_tag('div', **{'class': 'slide'})
        
        # Continuation title
        second_title = soup.new_tag('h1', **{'class': 'slide-title'})
        second_title.string = f"{base_title} (cont. {next_num})"
        second_slide.append(second_title)
        
        # No subtitle on continuation
        
        # Create content div
        second_content = soup.new_tag('div', **{'class': 'slide-content'})
        
        # Add second half of bullets
        second_ul = soup.new_tag('ul', **{'class': 'bullets'})
        for bullet in bullets[mid_point:]:
            second_ul.append(bullet.__copy__())
        second_content.append(second_ul)
        second_slide.append(second_content)
        
        # Combine both slides
        result_html = str(first_slide) + "\n" + str(second_slide)
        
        logger.info(f"✂️  Algorithmically split slide into 2 parts ({mid_point} + {len(bullets) - mid_point} bullets)")
        return result_html
        
    except Exception as e:
        logger.error(f"Algorithmic split failed: {e}", exc_info=True)
        return None


def optimize_slide_with_ai(slide_html: str, bullet_count: int, image_count: int, max_height: int) -> str:
    """
    Use Claude Haiku 4.5 to intelligently restructure dense slides.
    Returns optimized HTML or None if optimization fails.
    
    Uses density metrics (bullets, images) instead of pixel estimation for reliability.
    """
    # Determine density level
    if bullet_count > 10 or (bullet_count > 7 and image_count > 0):
        density_level = "VERY HIGH"
    elif bullet_count > 7 or image_count > 1:
        density_level = "HIGH"
    else:
        density_level = "MODERATE"
    
    prompt = f"""You are a visual content optimizer for PowerPoint slides. 
The following slide is TOO DENSE and will likely overflow in the final presentation.
You must fix this by splitting it intelligently while preserving ALL content.

**Current slide HTML:**
```html
{slide_html}
```

**Density Metrics:**
- Bullet points: {bullet_count}
- Images: {image_count}
- Density level: {density_level}
- Maximum allowed content height: {max_height}px

**Your Goal:**
Create optimized slide(s) that fit within {max_height}px while preserving ALL content with maximum detail.

**CRITICAL RULES - Content Preservation:**
1. **Target 450-480px per slide** (nearly full capacity - don't waste space!)
2. **ONLY split if overflow > 100px** (significant overflow requiring action)
3. **Preserve 6-8 bullets per slide** when possible (detailed content is good!)
4. **NEVER create sparse slides** with only 1-3 bullets
5. **Keep images WITH their descriptive bullets** - don't separate them

**Optimization Strategies (in priority order):**

**Strategy 1: Minor Overflow (< 100px)** - Try to fit without splitting:
   - Convert single-column to two-column layout (splits bullets side-by-side)
   - Reduce excessive whitespace or redundant headings
   - Only use this if overflow is small

**Strategy 2: Significant Overflow (> 100px)** - Smart split required:
   - **Split at logical boundaries** (between content blocks, not mid-list)
   - **Fill each slide to 450-480px** (target nearly full capacity)
   - **Numbering Logic:**
     * If title is "Topic", split into "Topic", "Topic (cont. 1)", "Topic (cont. 2)"
     * If title is ALREADY "Topic (cont. X)", continue numbering: "Topic (cont. X+1)", "Topic (cont. X+2)"
     * DO NOT repeat "cont." twice (e.g., "Topic (cont. 1) (cont. 2)" is WRONG)
   - **Content Distribution:**
     * First slide: Fill with 6-8 bullets (450-480px target)
     * Second slide: Remaining content with 6-8 bullets (450-480px target)
     * Only create 3rd slide if truly needed (avoid over-splitting)

**Strategy 3: Image Slides** - Special handling:
   - Keep image + its descriptive bullets together on same slide
   - If overflow, move ENTIRE image block to continuation slide
   - Never split bullets from their related image

**HTML Structure Rules:**
- Each item in your JSON array must be a full `<div class="slide" ...>...</div>` element
- Preserve ALL classes (e.g., `slide-title`, `slide-subtitle`, `content-block`)
- Do NOT remove ANY content - all text/images must be preserved
- Maintain proper HTML syntax and structure

**Return Format:**
Return ONLY a JSON array of objects. No markdown code blocks, no explanation text.
[
  {{
    "title": "Slide Title",
    "html": "<div class='slide' data-slide-id='...'> ... content ... </div>"
  }},
  {{
    "title": "Slide Title (cont. 1)",
    "html": "<div class='slide' data-slide-id='...'> ... content ... </div>"
  }}
]
"""

    import time as time_module
    
    # Retry logic for throttling
    max_retries = 5
    base_delay = 2.0
    
    try:
        for attempt in range(max_retries):
            try:
                response = bedrock_client.converse(
                    modelId=os.environ.get('BEDROCK_MODEL_ID', DEFAULT_MODEL),
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": 6000, "temperature": 0.2}
                )
                break  # Success - exit retry loop
            except Exception as e:
                if 'ThrottlingException' in str(e) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                    logger.warning(f"⚠️  Bedrock throttling (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                    time_module.sleep(delay)
                    continue
                else:
                    # Not throttling or max retries reached
                    raise
        
        response_text = response['output']['message']['content'][0]['text'].strip()
        
        # Extract JSON from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if not json_match:
            logger.error("AI response doesn't contain valid JSON array")
            # Fallback: try to find just the array if it's wrapped in text
            start = response_text.find('[')
            end = response_text.rfind(']')
            if start != -1 and end != -1:
                json_str = response_text[start:end+1]
            else:
                return None
        else:
            json_str = json_match.group(0)
            
        slides = json.loads(json_str)
        
        if not isinstance(slides, list) or len(slides) == 0:
            logger.error("AI returned empty or invalid slide array")
            return None
        
        # Join all optimized slides HTML to replace the original oversized slide
        full_html = "\n".join([s['html'] for s in slides])
        return full_html
        
    except Exception as e:
        logger.error(f"AI optimization failed: {e}", exc_info=True)
        return None
