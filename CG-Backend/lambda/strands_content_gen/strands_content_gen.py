"""
Content Generation - Single Call Version
Generates entire module in ONE LLM call for maximum efficiency.

Performance:
- Old: 7 calls, 10+ minutes
- New: 1 call, 1-2 minutes (85% faster)
"""

import os
import json
import yaml
import boto3
from botocore.config import Config
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure boto3 with extended timeouts for long-running LLM calls
boto_config = Config(
    read_timeout=600,  # 10 minutes read timeout
    connect_timeout=60,  # 1 minute connection timeout
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

# AWS Clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=boto_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-5"
DEFAULT_REGION = "us-east-1"


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        raise


def format_lesson_filename(module_num: int, lesson_index: int, lesson_title: str) -> str:
    """Format lesson filename."""
    safe_title = lesson_title.lower()
    safe_title = ''.join(c if c.isalnum() or c.isspace() else '' for c in safe_title)
    safe_title = '-'.join(safe_title.split())
    return f"module-{module_num}-lesson-{lesson_index + 1}-{safe_title}.md"


def calculate_target_words(lesson_data: dict, module_info: dict) -> int:
    """Calculate target word count for a lesson."""
    lesson_duration = lesson_data.get('duration_minutes', module_info.get('duration_minutes', 45))
    lesson_bloom = lesson_data.get('bloom_level', module_info.get('bloom_level', 'Understand'))
    
    # Handle compound bloom levels
    if '/' in lesson_bloom:
        bloom_parts = [b.strip() for b in lesson_bloom.split('/')]
        bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
        lesson_bloom = max(bloom_parts, key=lambda x: bloom_order.index(x) if x in bloom_order else 0)
    
    # Bloom multipliers
    bloom_multipliers = {
        'Remember': 1.0,
        'Understand': 1.1,
        'Apply': 1.2,
        'Analyze': 1.3,
        'Evaluate': 1.4,
        'Create': 1.5
    }
    
    bloom_mult = bloom_multipliers.get(lesson_bloom, 1.1)
    
    # Base calculation: 15 words per minute (concise content that teacher expands)
    base_words = lesson_duration * 15
    base_words = int(base_words * bloom_mult)
    
    # Add for topics and labs
    topics_count = len(lesson_data.get('topics', []))
    labs_count = len(lesson_data.get('lab_activities', []))
    
    total_words = base_words + (topics_count * 80) + (labs_count * 120)
    
    # Bounds
    return max(500, min(3000, total_words))


def build_course_context(course_data: dict) -> str:
    """Build complete course outline context."""
    course_title = course_data.get('title', 'Course')
    modules = course_data.get('modules', [])
    
    context_lines = [
        "════════════════════════════════════════════════════════════════════════",
        "COMPLETE COURSE OUTLINE - MUST REFERENCE THIS EXACT STRUCTURE",
        "════════════════════════════════════════════════════════════════════════",
        f"Course: {course_title}",
        ""
    ]
    
    for mod_idx, module in enumerate(modules, 1):
        mod_title = module.get('title', f'Module {mod_idx}')
        context_lines.append(f"\nModule {mod_idx}: {mod_title}")
        
        lessons = module.get('lessons', [])
        for les_idx, lesson in enumerate(lessons, 1):
            les_title = lesson.get('title', f'Lesson {les_idx}')
            context_lines.append(f"  {mod_idx}.{les_idx} {les_title}")
    
    context_lines.extend([
        "",
        "════════════════════════════════════════════════════════════════════════"
    ])
    
    return "\n".join(context_lines)


def generate_module_single_call(
    module_number: int,
    module_data: dict,
    course_data: dict,
    model_provider: str = "bedrock",
    openai_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate complete module content in a SINGLE LLM call.
    
    This is 85% faster than the multi-call approach (1-2 min vs 10+ min).
    
    Args:
        module_number: Module number (1-based)
        module_data: Module information from outline
        course_data: Full course data for context
        model_provider: "bedrock" or "openai"
        openai_api_key: OpenAI API key (if using OpenAI)
    
    Returns:
        List of generated lessons with metadata
    """
    
    print(f"\n{'='*70}")
    print(f"🚀 SINGLE-CALL GENERATION - Module {module_number}")
    print(f"{'='*70}")
    
    # Extract module info
    module_title = module_data.get('title', f'Module {module_number}')
    module_summary = module_data.get('summary', '')
    module_duration = module_data.get('duration_minutes', 0)
    module_bloom = module_data.get('bloom_level', 'Understand')
    lessons = module_data.get('lessons', [])
    
    total_lessons = len(lessons)
    print(f"📚 Module: {module_title}")
    print(f"📖 Lessons to generate: {total_lessons}")
    print(f"⏱️  Duration: {module_duration} minutes")
    print(f"🎯 Bloom level: {module_bloom}")
    
    # Build course context
    course_context_str = build_course_context(course_data)
    
    # Build lesson specifications
    lesson_specs = []
    total_target_words = 0
    
    # Extract language from course_data
    course_language = course_data.get('language', 'en').lower()
    language_names = {
        'en': 'English',
        'es': 'Spanish (Español)',
        'fr': 'French (Français)',
        'de': 'German (Deutsch)',
        'pt': 'Portuguese (Português)',
        'it': 'Italian (Italiano)'
    }
    target_language = language_names.get(course_language, 'English')
    
    print(f"🌐 Target Language: {target_language} ({course_language})")
    
    for idx, lesson in enumerate(lessons, 1):
        lesson_title = lesson.get('title', f'Lesson {idx}')
        lesson_duration = lesson.get('duration_minutes', 0)
        lesson_bloom = lesson.get('bloom_level', module_bloom)
        topics = lesson.get('topics', [])
        labs = lesson.get('lab_activities', [])
        
        target_words = calculate_target_words(lesson, module_data)
        total_target_words += target_words
        
        # Format topics
        topics_list = []
        for topic in topics:
            if isinstance(topic, dict):
                topic_title = topic.get('title', 'Unnamed topic')
                topic_duration = topic.get('duration_minutes', 0)
                topic_bloom = topic.get('bloom_level', 'Understand')
                topics_list.append(f"    - {topic_title} [{topic_duration} min, {topic_bloom}]")
            else:
                topics_list.append(f"    - {topic}")
        
        # Format labs
        labs_list = []
        for lab in labs:
            if isinstance(lab, dict):
                lab_title = lab.get('title', 'Unnamed lab')
                lab_duration = lab.get('duration_minutes', 0)
                labs_list.append(f"    - {lab_title} [{lab_duration} min]")
            else:
                labs_list.append(f"    - {lab}")
        
        lesson_spec = f"""
## LESSON {idx}: {lesson_title}
Duration: {lesson_duration} minutes
Bloom Level: {lesson_bloom}
Target Words: {target_words}+

TOPICS (EXACTLY {len(topics)} - NO EXTRAS):
{chr(10).join(topics_list) if topics_list else '    - General overview'}

LAB ACTIVITIES (Reference only - brief descriptions):
{chr(10).join(labs_list) if labs_list else '    - No lab activities'}
"""
        lesson_specs.append(lesson_spec)
    
    lessons_structure = "\n".join(lesson_specs)
    
    print(f"📝 Total target words: {total_target_words}")
    print(f"🤖 Using model: {model_provider}")
    
    # Build comprehensive prompt
    comprehensive_prompt = f"""
Generate COMPLETE educational content for Module {module_number}: {module_title}

═══════════════════════════════════════════════════════════════════════════════════
🎨 VISUAL TAG REQUIREMENTS (MANDATORY) 🎨
═══════════════════════════════════════════════════════════════════════════════════

When you need to include a visual element, use [VISUAL: detailed description] tags.
IMPORTANT: The description must be at least 80 characters with specific details.

✅ FOLLOW THESE PATTERNS - Study these examples carefully:

Example 1 - Architecture Diagram (147 characters):
[VISUAL: Three-layer architecture diagram with blue boxes: top layer shows 'Docker CLI' with terminal icon, middle layer has 'Docker Daemon' with gear icon, bottom layer displays 'containerd' and 'runc' boxes side by side, connected by downward arrows between each layer]

Example 2 - Comparison Table (135 characters):
[VISUAL: Side-by-side comparison table with two columns labeled 'Virtual Machine' and 'Container', showing rows for Size (GB vs MB), Startup (minutes vs seconds), Isolation (hardware vs process), with green checkmarks and red X marks]

Example 3 - Process Flowchart (162 characters):
[VISUAL: Horizontal flowchart with 5 rounded rectangles connected by right-pointing arrows: 'Write Dockerfile' (pencil icon) → 'docker build' (hammer icon) → 'Image Created' (box icon) → 'docker run' (play icon) → 'Container Running' (green circle)]

EVERY visual tag MUST include:
✓ Minimum 80 characters (count them before writing!)
✓ Specific component names and labels  
✓ Layout description (layered, side-by-side, horizontal, vertical, etc.)
✓ Relationships between elements (arrows, connections, lines)
✓ Visual attributes (colors, icons, shapes when relevant)

═══════════════════════════════════════════════════════════════════════════════════
📋 REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════════

1️⃣ CONTENT LENGTH: Target ~{total_target_words} words TOTAL across all {total_lessons} lessons
   - Approximately {total_target_words // total_lessons} words per lesson
   - Be thorough with examples, code snippets, and real-world scenarios

2️⃣ COMPLETENESS: Generate ALL {total_lessons} lessons in full
   - Each lesson must be complete with all sections
   - Do not stop mid-lesson or skip content

3️⃣ VISUAL TAGS: Include 3-5 descriptive [VISUAL: ...] tags per lesson
   - Remember: 80+ characters describing components, layout, and relationships
   - (Details in system instructions)

═══════════════════════════════════════════════════════════════════════════════════

{course_context_str}

════════════════════════════════════════════════════════════════════════
LANGUAGE REQUIREMENT
════════════════════════════════════════════════════════════════════════
**GENERATE ALL CONTENT IN: {target_language}**

- All headings, explanations, examples, and text must be in {target_language}
- Use proper {target_language} terminology and idioms
- Code comments should also be in {target_language} where appropriate
- Maintain technical accuracy while using natural {target_language} expression

════════════════════════════════════════════════════════════════════════
MODULE OVERVIEW
════════════════════════════════════════════════════════════════════════
Title: {module_title}
Summary: {module_summary}
Duration: {module_duration} minutes
Bloom Level: {module_bloom}
Number of Lessons: {total_lessons}

════════════════════════════════════════════════════════════════════════
LESSON SPECIFICATIONS
════════════════════════════════════════════════════════════════════════
{lessons_structure}

════════════════════════════════════════════════════════════════════════
CRITICAL REQUIREMENTS
════════════════════════════════════════════════════════════════════════

[x] Generate ALL {total_lessons} lessons in THIS response
[x] Each lesson must cover ONLY the topics listed (no extras)
[x] Target total: ~{total_target_words} words across all lessons
[x] NO "Practical Context" section - integrate practical aspects into Theoretical Foundations
[x] Lab activities: ONLY list labs from outline (1-2 sentences each)
[x] NO detailed lab procedures or step-by-step guides
[x] NO invented or additional labs not in the outline

CONTENT REQUIREMENTS:
[x] Generate ALL {total_lessons} lessons in THIS response
[x] Each lesson must cover ONLY the topics listed (no extras)
[x] Target total: ~{total_target_words} words across all lessons
[x] NO "Practical Context" section - integrate practical aspects into Theoretical Foundations
[x] Lab activities: ONLY list labs from outline (1-2 sentences each)
[x] NO detailed lab procedures or step-by-step guides
[x] NO invented or additional labs not in the outline
[x] Include 3-5 descriptive [VISUAL: ...] tags per lesson (80+ characters each)
[x] Maintain consistent terminology across all lessons
[x] Each lesson should flow naturally to the next
[x] Use Markdown formatting with clear headings
[x] Include practical examples and code snippets where appropriate

════════════════════════════════════════════════════════════════════════
LESSON STRUCTURE (for each lesson)
════════════════════════════════════════════════════════════════════════

1. INTRODUCTION (5% of content)
   - Context and learning objectives
   - Connection to previous lesson (if not Lesson 1)

2. THEORETICAL FOUNDATIONS (85% of content)
   - Cover ONLY the topics listed for this lesson
   - Clear explanations with examples and real-world context
   - Tool comparisons and selection criteria where relevant
   - Include descriptive [VISUAL: ...] tags for major concepts
   - If topic is "roadmap": Show COMPLETE course structure from outline above

3. LAB ACTIVITIES OVERVIEW (5% of content)
   - ONLY list lab titles with 1-2 sentence descriptions
   - Format: "In the lab guide, you will [brief action]..."
   - NO detailed procedures or step-by-step instructions
   - NO mention of labs not listed in the outline

4. SUMMARY (5% of content)
   - Recap key concepts covered
   - Bridge to next lesson (if not last)

✅ EXCELLENT (130+ chars, fully describes image):
[VISUAL: Layered architecture diagram showing three horizontal layers: top layer labeled 'Application Containers' with boxes for nginx, redis, and postgres; middle layer labeled 'Container Runtime (Docker/containerd)' with dotted line separator; bottom layer labeled 'Linux Kernel' showing namespace and cgroups boxes. Arrows pointing down from apps through runtime to kernel.]

✅ EXCELLENT (140+ chars, complete visualization):
[VISUAL: Side-by-side comparison table with 5 rows and 3 columns. Column headers: 'Minikube', 'kind', 'Managed K8s (EKS/GKE)'. Rows show: Setup Time (quick/instant/varies), Resource Usage (medium/low/high), Production Ready (no/no/yes), Ideal For (learning/testing/production), Cost (free/free/paid). Each cell uses green checkmark or red X icons.]

✅ EXCELLENT (120+ chars, shows flow and components):
[VISUAL: Flowchart diagram with 6 connected boxes showing kubectl command flow: 1) User types 'kubectl get pods' (terminal icon), 2) kubectl CLI sends HTTPS request (arrow with lock), 3) API Server validates auth (shield icon), 4) API Server queries etcd (database cylinder), 5) etcd returns pod data (arrow back), 6) kubectl displays table output (terminal with table). All connected by numbered arrows showing sequence.]

Remember: Write your visual tags following the EXCELLENT examples pattern above.
Every tag must be at least 80 characters with complete details about components, layout, and relationships.

════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════════════════════════════════════

MANDATORY MARKDOWN STRUCTURE (use EXACTLY this heading hierarchy):

# Lesson Title (H1 - only for lesson title)

## Introduction (H2 - for main sections)
Content here...

## Theoretical Foundations (H2)

### Topic 1: Name (H3 - for topics/subtopics)
Content with **bold** for key terms and *italic* for emphasis.

[VISUAL: Detailed 80+ character description here...]

Code examples:
```yaml
apiVersion: v1
kind: Pod
```

### Topic 2: Name (H3)
Content...

## Lab Activities (H2)

### Lab 1: Title (H3)
Brief description...

## Summary (H2)
Content...

---

CRITICAL MARKDOWN RULES (enforced for both Bedrock and GPT-5):
- H1 (#): ONLY for lesson title at the very top
- H2 (##): For main sections (Introduction, Theoretical Foundations, Lab Activities, Summary)
- H3 (###): For topics within sections and individual labs
- NO H4 or deeper - keep it simple
- Use **bold** for key terms and concepts
- Use *italic* for emphasis only
- Use code blocks with language tags: ```yaml, ```bash, ```python
- Lists: use "- " for unordered, "1. " for ordered
- Blank line before and after headings
- Blank line before and after code blocks
- Blank line before and after visual tags

Use this EXACT format:

---LESSON-1-START---
# Lesson 1: [Title]

## Introduction

[Context, learning objectives, connection to previous lesson]

## Theoretical Foundations

### [Topic 1 Title from Outline]

[Detailed explanation with examples]

[VISUAL: Detailed 120+ character description with components, layout, relationships, labels, colors, and flow direction clearly specified...]

[More content with **key terms** in bold]

### [Topic 2 Title from Outline]

[Detailed explanation]

[VISUAL: Another detailed 120+ character description...]

## Lab Activities

### Lab 1: [Lab Title from Outline]

In the lab guide, you will [brief 1-2 sentence description].

### Lab 2: [Lab Title from Outline]

In the lab guide, you will [brief 1-2 sentence description].

## Summary

[Recap of key concepts and bridge to next lesson]

---LESSON-1-END---

---LESSON-2-START---
# Lesson 2: [Title]

[Full lesson content here with all sections]

---LESSON-2-END---

---LESSON-3-START---
# Lesson 3: [Title]

[Full lesson content here with all sections]

---LESSON-3-END---

════════════════════════════════════════════════════════════════════════
VALIDATION CHECKLIST (Complete before finishing)
════════════════════════════════════════════════════════════════════════

Before submitting, verify:
[ ] All {total_lessons} lessons generated
[ ] Each lesson has ONLY the specified topics (no extras)
[ ] Lab activities section lists ONLY labs from the outline (no invented labs)
[ ] NO "Practical Context" section (integrate context into Theoretical Foundations)
[ ] Visual tags present (3-5 per lesson minimum, 80+ characters each)
[ ] Markdown formatting clean
[ ] Word count appropriate (~{total_target_words} total)
[ ] Course roadmap (if applicable) matches outline EXACTLY
[ ] Consistent terminology throughout
[ ] Natural flow between lessons

════════════════════════════════════════════════════════════════════════
FINAL REMINDERS
════════════════════════════════════════════════════════════════════════

✅ Generate ALL {total_lessons} lessons completely (no partial lessons)
✅ Target ~{total_target_words} words total (~{total_target_words // total_lessons} per lesson)
✅ Include 3-5 descriptive [VISUAL: ...] tags per lesson (80+ chars - see system instructions)
✅ Use H1/H2/H3 hierarchy exactly as specified
✅ NO invented labs - only labs from outline
✅ Be thorough and detailed, not overly concise

Now generate the complete module content.
"""
    
    print(f"\n🔄 Calling {model_provider.upper()} API...")
    start_time = datetime.now()
    
    # Call appropriate model
    if model_provider.lower() == "openai":
        full_content = call_openai(comprehensive_prompt, openai_api_key)
    else:
        full_content = call_bedrock(comprehensive_prompt)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"✅ Generation complete in {elapsed:.1f} seconds!")
    
    # Parse lessons from response
    print(f"\n📋 Parsing {total_lessons} lessons from response...")
    parsed_lessons = parse_lessons_from_response(
        full_content,
        lessons,
        module_number,
        module_data
    )
    
    # Summary
    total_words = sum(l['word_count'] for l in parsed_lessons)
    print(f"\n{'='*70}")
    print(f"✅ MODULE GENERATION COMPLETE")
    print(f"{'='*70}")
    print(f"📚 Module: {module_title}")
    print(f"📖 Lessons Generated: {len(parsed_lessons)}")
    print(f"📊 Total Words: {total_words} (target: {total_target_words})")
    print(f"⏱️  Generation Time: {elapsed:.1f} seconds")
    print(f"{'='*70}\n")
    
    return parsed_lessons


def call_bedrock(prompt: str, model_id: str = DEFAULT_BEDROCK_MODEL) -> str:
    """Call AWS Bedrock with Converse API."""
    try:
        # System message with visual tag requirements
        system_message = [
            {
                "text": """You are an expert educational content creator. Follow these CRITICAL rules:

🚨 VISUAL TAG REQUIREMENT (NON-NEGOTIABLE):
Every [VISUAL: ...] tag you write MUST be 80+ characters and describe:
- WHAT components are shown (e.g., "Docker CLI", "containerd", "nginx container")
- HOW they are arranged (e.g., "layered vertically", "connected in a flow", "side-by-side comparison")
- WHAT relationships exist (e.g., "connected by arrows", "bidirectional communication", "hierarchical structure")
- Any colors, labels, icons, or visual indicators

STUDY THESE CORRECT EXAMPLES (minimum 80 characters each):

Example 1 - Architecture (147 chars):
[VISUAL: Three-layer architecture diagram with blue boxes: top layer shows 'Docker CLI' with terminal icon, middle layer has 'Docker Daemon' with gear icon, bottom layer displays 'containerd' and 'runc' boxes side by side, connected by downward arrows between each layer]

Example 2 - Comparison (135 chars):
[VISUAL: Side-by-side comparison table with two columns labeled 'Virtual Machine' and 'Container', showing rows for Size (GB vs MB), Startup (minutes vs seconds), Isolation (hardware vs process), with green checkmarks and red X marks]

Example 3 - Flowchart (145 chars):
[VISUAL: Horizontal flowchart with 5 rounded rectangles connected by arrows: 'Code Push' (purple) → 'Build Image' (blue) → 'Push to Registry' (green) → 'Pull Image' (orange) → 'Run Container' (red)]

Write all your visual tags following these patterns. Minimum 80 characters, maximum detail.
Before writing each tag, ask: "Could someone draw this from my description alone?" If no, add more details."""
            }
        ]
        
        response = bedrock_client.converse(
            modelId=model_id,
            system=system_message,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            inferenceConfig={
                "maxTokens": 30000,  # Increased from 16000 to allow longer responses (3 lessons)
                # Note: temperature removed - Claude Sonnet 4.5 uses default (1.0) only
            }
        )
        
        return response['output']['message']['content'][0]['text']
    
    except Exception as e:
        print(f"❌ Bedrock API error: {e}")
        raise


def call_openai(prompt: str, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> str:
    """Call OpenAI API with SYSTEM message for visual tag requirements."""
    import openai
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # GPT-5 specific parameters:
        # - Uses max_completion_tokens instead of max_tokens
        # - Only supports default temperature (1.0), cannot be customized
        # Note: GPT-5 reasoning modes (Auto/Instant/Thinking/Pro) are controlled client-side,
        # not via API parameters. Users must select "Thinking" mode in their UI.
        
        # CRITICAL: Put visual tag requirements in SYSTEM message so GPT-5 processes them FIRST
        system_message = """You are an expert educational content creator. Follow these CRITICAL rules:

🚨 VISUAL TAG REQUIREMENT (NON-NEGOTIABLE):
Every [VISUAL: ...] tag you write MUST be 80+ characters and describe:
- WHAT components are shown (e.g., "API Server", "etcd", "Scheduler")
- HOW they are arranged (e.g., "layered", "connected in a hub", "side-by-side")
- WHAT relationships exist (e.g., "connected by arrows labeled 'gRPC'", "bidirectional communication")
- Any colors, labels, or visual indicators

STUDY THESE CORRECT EXAMPLES (minimum 80 characters each):

Example 1 - Architecture (147 chars):
[VISUAL: Kubernetes control plane architecture with API Server (central blue box), Scheduler (green box above), Controller Manager (orange box left), etcd (cyan cylinder right), all connected to API Server with bidirectional arrows labeled with protocol names]

Example 2 - Comparison (125 chars):
[VISUAL: Three-column comparison table with headers 'Minikube', 'kind', 'EKS', showing rows for Setup, Cost, Scale, Production-Ready, each cell with green checkmarks or red X marks]

Example 3 - Process Flow (138 chars):
[VISUAL: Vertical flowchart with 6 numbered steps: 1) kubectl command (terminal), 2) API validation (shield), 3) etcd query (database), 4) scheduler decision (gears), 5) kubelet execution (node), 6) container running (green box)]

Write all your visual tags following these patterns. Minimum 80 characters with complete component and layout details.
Before writing each tag, ask: "Could someone draw this from my description alone?" If no, add more specifics."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=30000  # Increased from 16000 to allow longer, more detailed responses
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        raise


def parse_lessons_from_response(
    full_content: str,
    lessons_outline: List[dict],
    module_number: int,
    module_data: dict
) -> List[Dict[str, Any]]:
    """
    Parse individual lessons from the single LLM response.
    
    Expects lessons to be separated by markers like:
    ---LESSON-1-START---
    [content]
    ---LESSON-1-END---
    """
    
    parsed_lessons = []
    
    # Try to split by lesson markers
    lesson_parts = []
    
    for idx in range(1, len(lessons_outline) + 1):
        start_marker = f"---LESSON-{idx}-START---"
        end_marker = f"---LESSON-{idx}-END---"
        
        if start_marker in full_content and end_marker in full_content:
            start_pos = full_content.find(start_marker) + len(start_marker)
            end_pos = full_content.find(end_marker)
            lesson_content = full_content[start_pos:end_pos].strip()
            lesson_parts.append(lesson_content)
        else:
            print(f"⚠️  Warning: Could not find markers for Lesson {idx}, trying fallback...")
            # Fallback: try to split by heading
            # This is more fragile but better than failing
            lesson_parts.append("")
    
    # If markers didn't work, try splitting by headings
    if not all(lesson_parts):
        print("⚠️  Using fallback parsing (splitting by headings)...")
        lesson_parts = split_by_headings(full_content, len(lessons_outline))
    
    # Build lesson objects
    for idx, (lesson_outline, lesson_content) in enumerate(zip(lessons_outline, lesson_parts), 1):
        lesson_title = lesson_outline.get('title', f'Lesson {idx}')
        topics = lesson_outline.get('topics', [])
        labs = lesson_outline.get('lab_activities', [])
        target_words = calculate_target_words(lesson_outline, module_data)
        
        word_count = len(lesson_content.split())
        
        parsed_lessons.append({
            'lesson_number': idx,
            'lesson_title': lesson_title,
            'lesson_content': lesson_content,
            'filename': format_lesson_filename(module_number, idx - 1, lesson_title),
            'word_count': word_count,
            'target_words': target_words,
            'topics_count': len(topics),
            'labs_count': len(labs)
        })
        
        print(f"  ✅ Lesson {idx}: {lesson_title} ({word_count} words)")
    
    return parsed_lessons


def split_by_headings(content: str, expected_lessons: int) -> List[str]:
    """
    Fallback parser: Split content by lesson headings.
    Looks for patterns like "# Lesson 1:" or "## Lesson 1:"
    """
    import re
    
    # Find all lesson headings
    pattern = r'^#{1,2}\s*Lesson\s+\d+[:\s]'
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    
    if len(matches) < expected_lessons:
        print(f"⚠️  Warning: Found {len(matches)} lesson headings, expected {expected_lessons}")
    
    lesson_parts = []
    
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        lesson_content = content[start:end].strip()
        lesson_parts.append(lesson_content)
    
    # Pad with empty strings if needed
    while len(lesson_parts) < expected_lessons:
        lesson_parts.append(f"# Lesson {len(lesson_parts) + 1}\n\n[Content generation failed]")
    
    return lesson_parts[:expected_lessons]


def lambda_handler(event, context):
    """
    AWS Lambda handler - main entry point.
    
    This is a drop-in replacement for the original handler.
    """
    
    try:
        print("=" * 70)
        print("CONTENT GENERATION LAMBDA - MULTI-MODULE SUPPORT")
        print("=" * 70)
        
        # Debug: Print full event to see what we're receiving
        print(f"\n📥 Received event:")
        print(json.dumps(event, indent=2, default=str))
        
        # Extract parameters from event
        course_topic = event.get('course_topic', 'Custom Course')
        
        # Support both old (single module) and new (multiple modules) formats
        modules_to_generate = event.get('modules_to_generate')
        if modules_to_generate is None:
            # Fallback to old single-module parameters
            module_to_generate = event.get('module_number') or event.get('module_to_generate', 1)
            modules_to_generate = [int(module_to_generate)]
        elif not isinstance(modules_to_generate, list):
            # Handle case where it's a single value
            modules_to_generate = [int(modules_to_generate)]
        
        model_provider = event.get('model_provider', 'bedrock').lower()
        
        # S3 configuration
        outline_s3_key = event.get('outline_s3_key')
        course_bucket = event.get('course_bucket')
        project_folder = event.get('project_folder')
        
        if not all([outline_s3_key, course_bucket, project_folder]):
            raise ValueError("Missing required S3 parameters")
        
        print(f"Course: {course_topic}")
        print(f"Modules to generate: {modules_to_generate}")
        print(f"Model: {model_provider}")
        print(f"Outline: s3://{course_bucket}/{outline_s3_key}")
        
        # Load outline from S3
        print(f"\n📥 Loading outline from S3...")
        outline_obj = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
        outline_content = outline_obj['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_content)
        
        # Support both 'course' and 'course_metadata' keys for backward compatibility
        course_info = outline_data.get('course', outline_data.get('course_metadata', {}))
        modules = outline_data.get('modules', [])
        
        # Validate modules
        for module_num in modules_to_generate:
            if module_num > len(modules) or module_num < 1:
                raise ValueError(f"Module {module_num} not found (outline has {len(modules)} modules)")
        
        # Get OpenAI key if needed (do this once for all modules)
        openai_api_key = None
        if model_provider == 'openai':
            try:
                secret = get_secret("aurora/openai-api-key")
                openai_api_key = secret.get('api_key')
            except Exception as e:
                print(f"⚠️  Could not get OpenAI key: {e}")
                openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # GENERATE CONTENT FOR ALL MODULES
        all_lessons = []
        all_lesson_keys = []
        total_word_count = 0
        
        for module_num in modules_to_generate:
            print(f"\n{'='*70}")
            print(f"📚 GENERATING MODULE {module_num}/{len(modules)}")
            print(f"{'='*70}")
            
            module_data = modules[module_num - 1]
            
            # Generate module content (SINGLE CALL per module!)
            generated_lessons = generate_module_single_call(
                module_number=module_num,
                module_data=module_data,
                course_data=course_info,
                model_provider=model_provider,
                openai_api_key=openai_api_key
            )
            
            # Save lessons to S3
            print(f"\n💾 Saving {len(generated_lessons)} lessons to S3...")
            
            for lesson in generated_lessons:
                lesson_key = f"{project_folder}/lessons/{lesson['filename']}"
                
                s3_client.put_object(
                    Bucket=course_bucket,
                    Key=lesson_key,
                    Body=lesson['lesson_content'].encode('utf-8'),
                    ContentType='text/markdown'
                )
                
                print(f"  ✅ Saved: {lesson_key}")
                all_lesson_keys.append(lesson_key)
                total_word_count += lesson['word_count']
            
            all_lessons.extend(generated_lessons)
        
        # Return success response (compatible with Step Functions state machine)
        print(f"\n{'='*70}")
        print(f"✅ COMPLETE: Generated {len(all_lessons)} lessons across {len(modules_to_generate)} module(s)")
        print(f"📊 Total words: {total_word_count:,}")
        print(f"{'='*70}")
        
        return {
            'statusCode': 200,
            'message': f'Generated {len(modules_to_generate)} module(s) successfully',
            # Step Functions compatibility
            'lesson_keys': all_lesson_keys,  # Required by state machine
            'bucket': course_bucket,
            'project_folder': project_folder,
            'modules_generated': modules_to_generate,
            'total_lessons': len(all_lessons),
            'total_words': total_word_count,
            'model_provider': model_provider,
            # Additional info
            'lessons': [
                {
                    'lesson_number': l['lesson_number'],
                    'lesson_title': l['lesson_title'],
                    'filename': l['filename'],
                    'word_count': l['word_count'],
                    's3_key': f"{project_folder}/lessons/{l['filename']}"
                }
                for l in all_lessons
            ]
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'error': str(e),
            'errorType': type(e).__name__
        }
