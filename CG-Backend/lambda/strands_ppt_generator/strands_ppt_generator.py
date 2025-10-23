"""
PowerPoint Presentation Generator - Strands Agent
==================================================
Generates engaging PowerPoint presentations from theory book content using Strands Agents.
Uses existing images from the book to avoid regenerating visuals.

Expected event parameters:
    - course_bucket: S3 bucket name
    - project_folder: Project folder path
    - book_version_key: S3 key to specific book version JSON (optional, defaults to latest)
    - model_provider: 'bedrock' or 'openai'
    - slides_per_lesson: Number of slides per lesson (default: 5-7)
    - presentation_style: 'professional' | 'educational' | 'modern' (default: 'professional')
"""

import os
import json
import boto3
import re
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from botocore.config import Config

# Configure boto3 with extended timeouts
boto_config = Config(
    read_timeout=600,
    connect_timeout=60,
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

# AWS Clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=boto_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-5"


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"⚠️ Error retrieving secret {secret_name}: {e}")
        raise


def configure_bedrock_model(model_id: str = DEFAULT_BEDROCK_MODEL):
    """Configure Bedrock model for Strands Agent."""
    try:
        from strands.models import BedrockModel
        
        model = BedrockModel(
            model_id=model_id,
            client=bedrock_client
        )
        print(f"✅ Configured Bedrock model: {model_id}")
        return model
    except Exception as e:
        print(f"❌ Failed to configure Bedrock model: {e}")
        raise


def configure_openai_model(model_id: str = DEFAULT_OPENAI_MODEL) -> Any:
    """Configure OpenAI model for Strands Agent."""
    try:
        from strands.models.openai import OpenAIModel
        
        # Get API key from Secrets Manager
        secret_data = get_secret('aurora/openai-api-key')
        api_key = secret_data.get('api_key')
        
        if not api_key:
            raise ValueError("OpenAI API key not found in secrets")
        
        model = OpenAIModel(
            client_args={"api_key": api_key},
            model_id=model_id,
            streaming=False
        )
        print(f"✅ Configured OpenAI model: {model_id}")
        return model
    except Exception as e:
        print(f"❌ Failed to configure OpenAI model: {e}")
        raise


def load_book_from_s3(bucket: str, book_key: str) -> Dict:
    """Load book JSON from S3."""
    try:
        print(f"📖 Loading book from s3://{bucket}/{book_key}")
        print(f"   Bucket: '{bucket}'")
        print(f"   Key: '{book_key}'")
        
        # Check if the object exists first
        try:
            s3_client.head_object(Bucket=bucket, Key=book_key)
            print(f"✅ Object exists, proceeding with download")
        except Exception as head_err:
            print(f"❌ Object does not exist or no access: {head_err}")
            # Try listing objects in the folder to help debug
            try:
                folder = '/'.join(book_key.split('/')[:-1])
                print(f"🔍 Listing objects in folder: {folder}/")
                list_response = s3_client.list_objects_v2(Bucket=bucket, Prefix=folder + '/', MaxKeys=10)
                if 'Contents' in list_response:
                    print(f"   Found {len(list_response['Contents'])} objects:")
                    for obj in list_response['Contents']:
                        print(f"   - {obj['Key']}")
                else:
                    print(f"   No objects found in folder")
            except Exception as list_err:
                print(f"❌ Could not list folder contents: {list_err}")
            raise head_err
        
        response = s3_client.get_object(Bucket=bucket, Key=book_key)
        book_data = json.loads(response['Body'].read().decode('utf-8'))
        print(f"✅ Loaded book with {len(book_data.get('lessons', []))} lessons")
        return book_data
    except Exception as e:
        print(f"❌ Failed to load book: {e}")
        print(f"   Error type: {type(e).__name__}")
        raise


def extract_images_from_content(content: str) -> List[Dict[str, str]]:
    """Extract image references from lesson content."""
    images = []

    # Match markdown image syntax: ![alt](url)
    img_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
    matches = re.findall(img_pattern, content)

    print(f"🔍 Found {len(matches)} image matches in content")

    for alt_text, img_url in matches:
        print(f"📷 Processing image: {alt_text} -> {img_url}")
        images.append({
            'alt_text': alt_text,
            'url': img_url,
            'type': 'diagram' if 'diagram' in alt_text.lower() else 'image'
        })

    # Also look for VISUAL tags which are common in our books
    visual_pattern = r'\[VISUAL([^\]]*)\]'
    visual_matches = re.findall(visual_pattern, content)

    print(f"🔍 Found {len(visual_matches)} VISUAL tags in content")

    for visual_desc in visual_matches:
        visual_desc = visual_desc.strip()
        if visual_desc:
            print(f"📷 Processing VISUAL: {visual_desc}")
            images.append({
                'alt_text': visual_desc,
                'url': '',  # Will be filled by image mapping logic
                'type': 'diagram' if 'diagram' in visual_desc.lower() else 'image'
            })

    return images


def create_slides_from_content(
    lesson_title: str,
    lesson_content: str,
    available_images: List[Dict],
    slides_per_lesson: int,
    lesson_idx: int
) -> List[Dict]:
    """
    Create slides by extracting structured content from markdown.
    This is faster and more reliable than AI generation.
    """
    slides = []
    
    # Helper to clean markdown from text
    def clean_markdown(text):
        text = re.sub(r'^#+\\s*', '', text)  # Remove leading #
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)  # Italic
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # Links
        text = re.sub(r'^[-*]\s+', '', text)  # List markers
        text = text.replace('`', '')
        return text.strip()

    # 1. Extract sections and headers from markdown
    lines = lesson_content.split('\n')
    sections = []
    current_section = None
    current_content = []
    for line in lines:
        line = line.strip()
        if line.startswith('##'):
            if current_section and current_content:
                sections.append({
                    'title': clean_markdown(current_section),
                    'content': current_content
                })
            current_section = line.replace('##', '').strip()
            current_content = []
        elif line and not line.startswith('#') and current_section:
            clean_line = clean_markdown(line)
            if len(clean_line) > 0 and not clean_line.startswith('!'):
                # Split long paragraphs into bullets
                if len(clean_line) > 120:
                    bullets = [b.strip() for b in re.split(r'[.\n]', clean_line) if len(b.strip()) > 0]
                    current_content.extend(bullets)
                else:
                    current_content.append(clean_line)
    if current_section and current_content:
        sections.append({
            'title': clean_markdown(current_section),
            'content': current_content
        })
    # Fallback: if no sections, use the whole lesson as one section, split paragraphs into bullets
    if not sections and lesson_content:
        # Remove all markdown image lines
        content_lines = [l for l in lines if l and not l.strip().startswith('![')]
        # Join lines to form paragraphs, then split into sentences
        full_text = ' '.join([clean_markdown(l) for l in content_lines if not l.strip().startswith('#')])
        # Split into bullets by period, semicolon, or newline
        bullets = [b.strip() for b in re.split(r'[.;\n]', full_text) if len(b.strip()) > 0]
        # Group bullets into chunks for slides
        chunk_size = max(4, min(7, slides_per_lesson))
        for i in range(0, len(bullets), chunk_size):
            chunk = bullets[i:i+chunk_size]
            sections.append({'title': clean_markdown(lesson_title), 'content': chunk})

    # 2. Title slide for the lesson (skip if no content)
    if sections:
        slides.append({
            "title": clean_markdown(lesson_title),
            "bullets": [f"Lesson {lesson_idx}", "Key concepts and practical applications", "Hands-on examples and best practices"],
            "slide_type": "content"
        })

    slides_to_create = slides_per_lesson - 2  # Reserve 1 for title, 1 for summary
    if slides_to_create < 1:
        slides_to_create = 1
    slides_created = 0
    image_idx = 0
    for section in sections[:slides_to_create]:
        bullets = [b for b in section['content'] if b][:6]
        if not bullets and image_idx >= len(available_images):
            continue  # Skip blank slides
        slide = {
            "title": clean_markdown(section['title']),
            "bullets": bullets,
            "slide_type": "content"
        }
        if image_idx < len(available_images):
            slide['image_reference'] = f"USE_IMAGE: {available_images[image_idx]['alt_text']}"
            slide['image_url'] = available_images[image_idx]['url']
            image_idx += 1
        slides.append(slide)
        slides_created += 1
        if slides_created < slides_to_create and image_idx < len(available_images):
            img = available_images[image_idx]
            slides.append({
                "title": clean_markdown(section['title']) + " - Visual",
                "image_reference": f"USE_IMAGE: {img['alt_text']}",
                "image_url": img['url'],
                "bullets": [img['alt_text']],
                "slide_type": "image"
            })
            slides_created += 1
            image_idx += 1
    # 3. Summary slide
    summary_points = []
    for section in sections[:5]:
        if section['content']:
            summary_points.append(f"{clean_markdown(section['title'])}: {section['content'][0][:80]}...")
    if summary_points:
        slides.append({
            "title": f"{clean_markdown(lesson_title)} - Summary",
            "bullets": summary_points[:5],
            "slide_type": "summary"
        })
    return slides


def generate_presentation_structure(
    book_data: Dict,
    model,
    slides_per_lesson: int = 6,
    presentation_style: str = 'professional'
) -> Dict:
    """
    Use Strands Agent to generate PowerPoint presentation structure from book content.
    Creates engaging, professional slides optimized for course delivery.
    """
    from strands import Agent

    # Extract course metadata
    metadata = book_data.get('metadata', {})
    course_title = metadata.get('title', 'Course Presentation')
    lessons = book_data.get('lessons', [])

    print(f"\n🎨 Generating AI-powered presentation structure for: {course_title}")
    print(f"📊 Lessons to convert: {len(lessons)}")
    print(f"🎯 Slides per lesson: {slides_per_lesson}")
    print(f"✨ Style: {presentation_style}")

    # Check if book has modules instead of lessons
    if len(lessons) == 0 and 'modules' in book_data:
        print("⚠️ Book uses 'modules' structure, converting to lessons...")
        modules = book_data.get('modules', [])
        for module in modules:
            if 'lessons' in module and isinstance(module['lessons'], list):
                lessons.extend(module['lessons'])
        print(f"✅ Extracted {len(lessons)} lessons from {len(modules)} modules")

    if len(lessons) == 0:
        raise ValueError("No lessons found in book data. Cannot generate presentation.")

    # Build comprehensive course context
    course_context = f"""
COURSE: {course_title}
TOTAL LESSONS: {len(lessons)}
PRESENTATION STYLE: {presentation_style}
SLIDES PER LESSON: {slides_per_lesson}

LESSON TITLES:
"""
    for i, lesson in enumerate(lessons, 1):
        course_context += f"{i}. {lesson.get('title', f'Lesson {i}')}\n"

    # Create AI-powered PPT Designer Agent
    ppt_designer = Agent(
        model=model,
        system_prompt=f"""You are a senior instructional designer and PowerPoint expert specializing in creating engaging, professional presentations for corporate training and educational courses.

Style: {presentation_style}
- Professional: Clean, corporate design with blue color scheme, structured layouts, business-focused
- Educational: Student-friendly, colorful, emphasizes examples and practice exercises, interactive elements
- Modern: Minimalist, high-impact visuals, brief text, dynamic layouts, contemporary design

COURSE CONTEXT:
{course_context}

EXPERTISE REQUIREMENTS:
1. Each slide MUST have:
    - A compelling, descriptive title (not generic like "Introduction" or "Overview")
    - 3-7 bullet points maximum (concise, action-oriented, impactful)
    - Clear indication if existing image should be used

2. Advanced Slide Types to Use:
    - Title Slide: Course introduction with compelling hook and value proposition
    - Learning Objectives Slide: Specific, measurable outcomes with business impact
    - Content Slide: Main concepts with practical applications and real-world examples
    - Image Slide: Full-screen diagram/visual with detailed caption and learning context
    - Process Slide: Step-by-step workflows with clear progression
    - Comparison Slide: Side-by-side concepts, before/after scenarios, pros/cons
    - Case Study Slide: Real-world applications with outcomes
    - Interactive Slide: Discussion questions, exercises, reflection points
    - Summary Slide: Key takeaways, action items, and next steps

3. Strategic Image Usage:
    - ALWAYS reference existing images from the lesson when available
    - Specify which image to use: "USE_IMAGE: [exact alt_text or description]"
    - Don't request new images - use what exists in the book
    - Place images strategically to enhance learning and retention
    - Use images to break up text-heavy sections

4. Professional Course Delivery Elements:
    - Include specific learning objectives for each lesson (measurable outcomes)
    - Add estimated timing for each section
    - Include discussion questions and interaction points
    - Add practical exercises and hands-on activities
    - Create reflection points and knowledge checks
    - Include real-world applications and case studies
    - Add summary slides with key takeaways and action items
    - Include next steps and homework assignments

5. Content Adaptation for Maximum Engagement:
    - Convert complex paragraphs into clear, memorable bullet points
    - Extract key terminology for emphasis and discussion
    - Identify practical examples that resonate with the audience
    - Create "what this means for you" connections
    - Build concepts progressively with clear learning progression
    - Use storytelling techniques to maintain interest
    - Include surprises and "aha" moments

6. Contextual Understanding and Flow:
    - Maintain cohesion between slides within a lesson
    - Create smooth transitions between lessons
    - Build upon concepts progressively
    - Reference previous lessons when relevant
    - Create anticipation for upcoming content
    - End each lesson with clear next steps

OUTPUT FORMAT: Return a JSON structure with this exact format:
{{
    "presentation_title": "{course_title}",
    "total_slides": 45,
    "slides": [
        {{
            "slide_number": 1,
            "slide_type": "title",
            "title": "{course_title}",
            "subtitle": "Professional Training Program",
            "notes": "Welcome participants and set expectations"
        }},
        {{
            "slide_number": 2,
            "slide_type": "content",
            "title": "What You'll Achieve Today",
            "bullets": [
                "Master practical skills for immediate application",
                "Understand real-world scenarios and challenges",
                "Develop strategies for long-term success"
            ],
            "image_reference": "USE_IMAGE: Course overview diagram",
            "notes": "Connect objectives to participant goals"
        }},
        {{
            "slide_number": 3,
            "slide_type": "image",
            "title": "System Architecture Deep Dive",
            "image_reference": "USE_IMAGE: Complete system architecture",
            "caption": "Understanding the components and their critical interactions",
            "notes": "Walk through each component and explain relationships"
        }}
    ]
}}
""",
        tools=[]
    )

    # Process lessons with AI agent for professional slide creation
    all_slides = []
    slide_counter = 1

    # Add title slide
    all_slides.append({
        "slide_number": slide_counter,
        "slide_type": "title",
        "title": course_title,
        "subtitle": f"Professional Training • {len(lessons)} Lessons",
        "notes": "Welcome and course overview"
    })
    slide_counter += 1

    # Process each lesson with AI for professional slide design
    for lesson_idx, lesson in enumerate(lessons, 1):
        lesson_title = lesson.get('title', f'Lesson {lesson_idx}')
        lesson_content = lesson.get('content', '')

        print(f"\n📝 Processing Lesson {lesson_idx}/{len(lessons)}: {lesson_title}")

        # Extract images available in this lesson
        available_images = extract_images_from_content(lesson_content)
        print(f"🖼️  Found {len(available_images)} images in this lesson")

        # Use AI agent to create professional slides for this lesson
        lesson_prompt = f"""
Create professional PowerPoint slides for this lesson:

LESSON {lesson_idx}: {lesson_title}

CONTENT:
{lesson_content}

Available images: {len(available_images)} images found
Image descriptions: {[img['alt_text'] for img in available_images]}

Create {slides_per_lesson} engaging slides that are optimized for course delivery.
Include learning objectives, key concepts, practical examples, and discussion points.

Focus on:
- Creating contextually connected slides with smooth flow
- Using specific, compelling titles for each slide
- Including practical, real-world examples
- Adding discussion questions and interaction points
- Leveraging available images strategically
- Building concepts progressively within the lesson
"""

        try:
            # Get AI-generated slide structure for this lesson
            # Use Strands Agent to generate slides
            if hasattr(ppt_designer, 'generate'):
                ai_response = ppt_designer.generate(lesson_prompt)
            elif hasattr(ppt_designer, 'invoke'):
                ai_response = ppt_designer.invoke(lesson_prompt)
            elif hasattr(ppt_designer, 'call'):
                ai_response = ppt_designer.call(lesson_prompt)
            else:
                # Fallback to direct model call
                messages = [{"role": "user", "content": lesson_prompt}]
                if hasattr(ppt_designer, 'model'):
                    ai_response = ppt_designer.model.generate(messages)
                else:
                    # Use the agent as a callable
                    ai_response = ppt_designer(messages)

            # Ensure we have a string response
            if not isinstance(ai_response, str):
                ai_response = str(ai_response)

            lesson_slides_data = json.loads(ai_response)

            print(f"✅ AI generated {len(lesson_slides_data.get('slides', []))} slides for lesson {lesson_idx}")

            # Process and enhance the AI-generated slides
            for slide_data in lesson_slides_data.get('slides', []):
                slide_data['slide_number'] = slide_counter
                slide_data['lesson_number'] = lesson_idx
                slide_data['lesson_title'] = lesson_title

                # Ensure image references use available images
                if 'image_reference' in slide_data and available_images:
                    # Map AI image references to actual available images
                    img_ref = slide_data['image_reference']
                    if 'USE_IMAGE:' in img_ref:
                        requested_img = img_ref.split('USE_IMAGE:')[1].strip()
                        print(f"🔗 Mapping AI image request: '{requested_img}' to available images")

                        # Find best matching available image
                        best_match = available_images[0]  # Default to first image
                        best_score = 0

                        for img in available_images:
                            # Calculate similarity score
                            score = 0
                            if requested_img.lower() in img['alt_text'].lower():
                                score += 10
                            if requested_img.lower() == img['alt_text'].lower():
                                score += 20
                            if any(word in img['alt_text'].lower() for word in requested_img.lower().split()):
                                score += 5

                            if score > best_score:
                                best_score = score
                                best_match = img

                        print(f"✅ Mapped to: {best_match['alt_text']} (score: {best_score})")
                        slide_data['image_url'] = best_match['url']
                        slide_data['image_reference'] = f"USE_IMAGE: {best_match['alt_text']}"

                # If no image URL but we have available images, try to find actual image files in S3
                if 'image_url' not in slide_data or not slide_data['image_url']:
                    if available_images:
                        # Try to find the actual image file in S3
                        try:
                            images_prefix = f"{project_folder}/images/"
                            list_response = s3_client.list_objects_v2(
                                Bucket=course_bucket,
                                Prefix=images_prefix,
                                MaxKeys=50
                            )

                            if 'Contents' in list_response and list_response['Contents']:
                                # Find the first PNG image
                                for obj in list_response['Contents']:
                                    if obj['Key'].endswith('.png'):
                                        image_url = f"https://{course_bucket}.s3.amazonaws.com/{obj['Key']}"
                                        slide_data['image_url'] = image_url
                                        slide_data['image_reference'] = f"USE_IMAGE: {available_images[0]['alt_text'] if available_images else 'Image'}"
                                        print(f"🔗 Found S3 image: {image_url}")
                                        break
                        except Exception as e:
                            print(f"⚠️ Could not list S3 images: {e}")

                all_slides.append(slide_data)
                slide_counter += 1

        except Exception as e:
            print(f"⚠️ AI generation failed for lesson {lesson_idx}, using fallback: {e}")
            # Fallback to content extraction if AI fails
            lesson_slides = create_slides_from_content(
                lesson_title=lesson_title,
                lesson_content=lesson_content,
                available_images=available_images,
                slides_per_lesson=slides_per_lesson,
                lesson_idx=lesson_idx
            )

            for slide in lesson_slides:
                slide['slide_number'] = slide_counter
                slide['lesson_number'] = lesson_idx
                slide['lesson_title'] = lesson_title
                all_slides.append(slide)
                slide_counter += 1

        print(f"📈 Total slides so far: {len(all_slides)}")

    # Add final summary slide
    all_slides.append({
        "slide_number": slide_counter,
        "slide_type": "summary",
        "title": "Course Summary & Next Steps",
        "bullets": [
            f"Completed {len(lessons)} comprehensive lessons",
            "Developed practical skills for immediate application",
            "Ready to apply knowledge in professional scenarios",
            "Continue learning with advanced topics and certifications"
        ],
        "notes": "Thank participants and discuss next steps and resources"
    })

    presentation_structure = {
        "presentation_title": course_title,
        "total_slides": len(all_slides),
        "total_lessons": len(lessons),
        "style": presentation_style,
        "generated_at": datetime.now().isoformat(),
        "slides": all_slides
    }

    print(f"\n✅ AI-powered presentation structure complete: {len(all_slides)} slides")
    return presentation_structure


def generate_pptx_file(presentation_structure: Dict, book_data: Dict) -> bytes:
    """
    Generate actual PPTX file from the presentation structure.
    Uses python-pptx library.
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        from pptx.dml.color import RGBColor
        import io
        import requests
        from urllib.parse import urlparse
        
        print("🎨 Creating PowerPoint file...")
        
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        
        # Define slide layouts
        title_slide_layout = prs.slide_layouts[0]  # Title Slide
        content_slide_layout = prs.slide_layouts[1]  # Title and Content
        blank_slide_layout = prs.slide_layouts[6]  # Blank
        
        style = presentation_structure.get('style', 'professional')
        
        # Color schemes by style
        color_schemes = {
            'professional': {
                'primary': RGBColor(0, 51, 102),  # Dark Blue
                'secondary': RGBColor(68, 114, 196),  # Medium Blue
                'accent': RGBColor(255, 192, 0)  # Gold
            },
            'educational': {
                'primary': RGBColor(46, 139, 87),  # Sea Green
                'secondary': RGBColor(70, 130, 180),  # Steel Blue
                'accent': RGBColor(255, 140, 0)  # Dark Orange
            },
            'modern': {
                'primary': RGBColor(33, 33, 33),  # Dark Gray
                'secondary': RGBColor(96, 125, 139),  # Blue Gray
                'accent': RGBColor(0, 150, 136)  # Teal
            }
        }
        
        colors = color_schemes.get(style, color_schemes['professional'])
        
        # Process each slide
        for slide_data in presentation_structure.get('slides', []):
            slide_type = slide_data.get('slide_type', 'content')
            slide_title = slide_data.get('title', '')

            if slide_type == 'title':
                slide = prs.slides.add_slide(title_slide_layout)
                title_shape = slide.shapes.title
                subtitle = slide.placeholders[1]
                title_shape.text = slide_title
                subtitle.text = slide_data.get('subtitle', '')
                title_shape.text_frame.paragraphs[0].font.size = Pt(44)
                title_shape.text_frame.paragraphs[0].font.bold = True
                title_shape.text_frame.paragraphs[0].font.color.rgb = colors['primary']
            elif slide_type == 'content':
                slide = prs.slides.add_slide(content_slide_layout)
                title_shape = slide.shapes.title
                title_shape.text = slide_title
                title_shape.text_frame.paragraphs[0].font.size = Pt(32)
                title_shape.text_frame.paragraphs[0].font.bold = True
                title_shape.text_frame.paragraphs[0].font.color.rgb = colors['primary']
                body = slide.placeholders[1]
                text_frame = body.text_frame
                text_frame.clear()
                for bullet in slide_data.get('bullets', []):
                    p = text_frame.add_paragraph()
                    p.text = bullet
                    p.level = 0
                    p.font.size = Pt(18)
                    p.space_before = Pt(12)
                # Add image if referenced
                image_url = slide_data.get('image_url')
                if image_url:
                    try:
                        img_data = None
                        if image_url.startswith('http'):
                            # Try to get image with timeout and error handling
                            try:
                                img_resp = requests.get(image_url, timeout=10)
                                if img_resp.status_code == 200:
                                    img_data = io.BytesIO(img_resp.content)
                                    print(f"✅ Downloaded image: {image_url}")
                                else:
                                    print(f"⚠️ Image not accessible (HTTP {img_resp.status_code}): {image_url}")
                            except requests.exceptions.RequestException as e:
                                print(f"⚠️ Network error downloading image: {e}")
                                # Try alternative: if it's an S3 URL, try to get from S3 directly
                                if 's3.amazonaws.com' in image_url:
                                    try:
                                        # Extract bucket and key from S3 URL
                                        url_parts = image_url.split('/')
                                        bucket_idx = url_parts.index('s3.amazonaws.com') + 1
                                        if bucket_idx < len(url_parts):
                                            bucket = url_parts[bucket_idx]
                                            key = '/'.join(url_parts[bucket_idx + 1:])
                                            print(f"🔄 Trying direct S3 access: {bucket}/{key}")

                                            # Use S3 client to get the object
                                            s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                                            img_data = io.BytesIO(s3_response['Body'].read())
                                            print(f"✅ Retrieved image from S3: {bucket}/{key}")
                                    except Exception as s3_error:
                                        print(f"❌ S3 access failed: {s3_error}")

                        if img_data:
                            left = Inches(6.5)
                            top = Inches(1.5)
                            width = Inches(3)
                            slide.shapes.add_picture(img_data, left, top, width=width)
                            print(f"✅ Inserted image into slide")
                        else:
                            print(f"⚠️ Could not access image, skipping: {image_url}")
                            # Add placeholder text instead
                            txBox = slide.shapes.add_textbox(Inches(6.5), Inches(1.5), Inches(3), Inches(2))
                            tf = txBox.text_frame
                            tf.text = "[Image not available]"
                            tf.paragraphs[0].font.size = Pt(12)
                            tf.paragraphs[0].font.italic = True
                    except Exception as e:
                        print(f"⚠️ Error inserting image: {e}")
            elif slide_type == 'image':
                slide = prs.slides.add_slide(blank_slide_layout)
                txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.8))
                tf = txBox.text_frame
                p = tf.paragraphs[0]
                p.text = slide_data.get('title', '')
                p.font.size = Pt(32)
                p.font.bold = True
                p.font.color.rgb = colors['primary']
                # Add image
                image_url = slide_data.get('image_url')
                if image_url:
                    try:
                        img_data = None
                        if image_url.startswith('http'):
                            # Try to get image with timeout and error handling
                            try:
                                img_resp = requests.get(image_url, timeout=10)
                                if img_resp.status_code == 200:
                                    img_data = io.BytesIO(img_resp.content)
                                    print(f"✅ Downloaded image: {image_url}")
                                else:
                                    print(f"⚠️ Image not accessible (HTTP {img_resp.status_code}): {image_url}")
                            except requests.exceptions.RequestException as e:
                                print(f"⚠️ Network error downloading image: {e}")
                                # Try alternative: if it's an S3 URL, try to get from S3 directly
                                if 's3.amazonaws.com' in image_url:
                                    try:
                                        # Extract bucket and key from S3 URL
                                        url_parts = image_url.split('/')
                                        bucket_idx = url_parts.index('s3.amazonaws.com') + 1
                                        if bucket_idx < len(url_parts):
                                            bucket = url_parts[bucket_idx]
                                            key = '/'.join(url_parts[bucket_idx + 1:])
                                            print(f"🔄 Trying direct S3 access: {bucket}/{key}")

                                            # Use S3 client to get the object
                                            s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                                            img_data = io.BytesIO(s3_response['Body'].read())
                                            print(f"✅ Retrieved image from S3: {bucket}/{key}")
                                    except Exception as s3_error:
                                        print(f"❌ S3 access failed: {s3_error}")

                        if img_data:
                            left = Inches(2)
                            top = Inches(1.2)
                            width = Inches(6)
                            slide.shapes.add_picture(img_data, left, top, width=width)
                            print(f"✅ Inserted image into slide")
                        else:
                            print(f"⚠️ Could not access image, skipping: {image_url}")
                            # Add placeholder text instead
                            txBox = slide.shapes.add_textbox(Inches(2), Inches(1.2), Inches(6), Inches(2))
                            tf = txBox.text_frame
                            tf.text = "[Image not available]"
                            tf.paragraphs[0].font.size = Pt(16)
                            tf.paragraphs[0].font.italic = True
                    except Exception as e:
                        print(f"⚠️ Error inserting image: {e}")
                # Add caption
                caption = slide_data.get('caption', '')
                if caption:
                    txBox2 = slide.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(9), Inches(0.8))
                    tf2 = txBox2.text_frame
                    p2 = tf2.paragraphs[0]
                    p2.text = caption
                    p2.font.size = Pt(14)
                    p2.font.italic = True
            elif slide_type == 'summary':
                slide = prs.slides.add_slide(content_slide_layout)
                title_shape = slide.shapes.title
                title_shape.text = slide_title or 'Summary'
                body = slide.placeholders[1]
                text_frame = body.text_frame
                text_frame.clear()
                for bullet in slide_data.get('bullets', []):
                    p = text_frame.add_paragraph()
                    p.text = bullet
                    p.level = 0
                    p.font.size = Pt(20)
                    p.font.bold = True
                    p.space_before = Pt(12)
        
        # Save to bytes
        pptx_buffer = io.BytesIO()
        prs.save(pptx_buffer)
        pptx_buffer.seek(0)
        
        print(f"✅ PowerPoint file created: {len(presentation_structure.get('slides', []))} slides")
        return pptx_buffer.getvalue()
        
    except ImportError as e:
        print(f"❌ Missing python-pptx library: {e}")
        print("💡 Install with: pip install python-pptx")
        raise
    except Exception as e:
        print(f"❌ Error creating PPTX file: {e}")
        raise


def lambda_handler(event, context):
    """
    Main Lambda handler for PPT generation.
    """
    try:
        print("=" * 80)
        print("🎯 STRANDS PPT GENERATOR")
        print("=" * 80)
        print(f"📥 Event: {json.dumps(event, indent=2)}")
        
        # Parse event - handle API Gateway body format
        if 'body' in event:
            # API Gateway POST request - body is a JSON string
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            # Direct Lambda invocation
            body = event
        
        print(f"📦 Parsed body: {json.dumps(body, indent=2)}")
        
        # Extract parameters
        course_bucket = body.get('course_bucket')
        project_folder = body.get('project_folder')
        book_version_key = body.get('book_version_key')
        model_provider = body.get('model_provider', 'bedrock').lower()
        slides_per_lesson = int(body.get('slides_per_lesson', 6))
        presentation_style = body.get('presentation_style', 'professional')
        
        if not course_bucket or not project_folder:
            raise ValueError("course_bucket and project_folder are required")
        
        # Auto-discover book file if no version specified (same logic as load_book.py)
        if not book_version_key:
            print(f"\n🔍 Auto-discovering book file in {project_folder}/book/")
            book_prefix = f"{project_folder}/book/"
            response = s3_client.list_objects_v2(
                Bucket=course_bucket,
                Prefix=book_prefix,
                MaxKeys=50
            )
            
            if 'Contents' in response:
                # Look for files ending with _data.json
                json_files = []
                for obj in response['Contents']:
                    key = obj['Key']
                    last_modified = obj.get('LastModified')
                    if key.endswith('_data.json'):
                        json_files.append((key, last_modified))
                
                if json_files:
                    # Sort by last modified (most recent first)
                    json_files.sort(key=lambda x: x[1], reverse=True)
                    book_version_key = json_files[0][0]
                    print(f"✅ Auto-discovered book file: {book_version_key}")
                else:
                    raise ValueError(f"No book files (*_data.json) found in {book_prefix}")
            else:
                raise ValueError(f"No files found in {book_prefix}")
        
        print(f"\n📚 Book version: {book_version_key}")
        print(f"🤖 Model provider: {model_provider}")
        print(f"📊 Slides per lesson: {slides_per_lesson}")
        print(f"🎨 Style: {presentation_style}")
        
        # Configure AI model
        if model_provider == 'openai':
            model = configure_openai_model()
        else:
            model = configure_bedrock_model()
        
        # Load book data
        book_data = load_book_from_s3(course_bucket, book_version_key)
        
        # Generate presentation structure
        presentation_structure = generate_presentation_structure(
            book_data,
            model,
            slides_per_lesson,
            presentation_style
        )
        
        # Save presentation structure as JSON
        structure_key = f"{project_folder}/presentations/presentation_structure.json"
        s3_client.put_object(
            Bucket=course_bucket,
            Key=structure_key,
            Body=json.dumps(presentation_structure, indent=2),
            ContentType='application/json'
        )
        print(f"💾 Saved structure: s3://{course_bucket}/{structure_key}")
        
        # Generate PPTX file
        try:
            print("🎨 Starting PPTX file generation...")
            print(f"📊 Presentation structure has {len(presentation_structure.get('slides', []))} slides")
            
            pptx_bytes = generate_pptx_file(presentation_structure, book_data)
            
            print(f"✅ PPTX file generated: {len(pptx_bytes)} bytes")
            
            # Save PPTX to S3 in the presentations folder
            pptx_title = presentation_structure.get('presentation_title', 'presentation')
            # Sanitize only the filename, not the folder path
            sanitized_filename = pptx_title.replace(' ', '_').replace('/', '-').replace(':', '-').replace('\\', '-')
            pptx_key = f"{project_folder}/presentations/{sanitized_filename}.pptx"
            
            print(f"📁 Saving to: {pptx_key}")
            
            s3_client.put_object(
                Bucket=course_bucket,
                Key=pptx_key,
                Body=pptx_bytes,
                ContentType='application/vnd.openxmlformats-officedocument.presentationml.presentation'
            )
            print(f"💾 Saved PPTX: s3://{course_bucket}/{pptx_key}")
            
        except Exception as e:
            error_details = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'error_args': str(e.args) if hasattr(e, 'args') else None
            }
            print(f"⚠️ PPTX generation failed (structure still saved)")
            print(f"Error details: {json.dumps(error_details, indent=2)}")
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            pptx_key = None
        
        # Return success response with CORS headers
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'Presentation generated successfully',
                'presentation_title': presentation_structure['presentation_title'],
                'total_slides': presentation_structure['total_slides'],
                'structure_s3_key': structure_key,
                'pptx_s3_key': pptx_key,
                'generated_at': presentation_structure['generated_at']
            })
        }
        
    except Exception as e:
        error_msg = f"Error generating presentation: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': error_msg,
                'traceback': traceback.format_exc()
            })
        }
