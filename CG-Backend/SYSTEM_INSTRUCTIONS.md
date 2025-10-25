# Aurora Course Generator - System Instructions

## Critical System Knowledge & Best Practices

**Last Updated:** October 24, 2025  
**Purpose:** Prevent recurring issues and maintain system consistency

---

## 🚨 MANDATORY DEPLOYMENT RULES

### Rule #1: ALWAYS Use the Deployment Script
```bash
cd /home/juan/AuroraV1/CG-Backend
./deploy-with-dependencies.sh
```

**NEVER** run `sam deploy` directly without first running `sam build`. The deployment script:
- Rebuilds all Lambda functions with dependencies (pyyaml, etc.)
- Prevents "module not found" errors in production
- Updates all 4 critical functions: StarterApi, StrandsLabPlanner, BatchExpander, LabBatchExpander

**Why:** Lambda functions lose their dependencies if you deploy template changes without rebuilding the code packages.

---

## 📋 Visual Tags System - CRITICAL FORMAT RULES

### Content Generation (strands_content_gen.py)

**LLM MUST generate visual tags in EXACTLY this format:**

```markdown
[VISUAL: description]
```

**Format Requirements:**
- ✅ `VISUAL` in capital letters
- ✅ Single space after colon
- ✅ No period at end of description
- ✅ No quotes, parentheses, or special characters in description
- ✅ 5-15 words (concise but specific)
- ✅ Place on its own line for best results

**Valid Examples:**
```markdown
[VISUAL: Diagram showing the MVC architecture flow]
[VISUAL: Screenshot of the IDE debugger panel]
[VISUAL: Flowchart of the authentication process]
[VISUAL: Table comparing synchronous vs asynchronous operations]
```

**Invalid Examples (DO NOT USE):**
```markdown
[VISUAL: "Diagram showing MVC"]  ❌ Has quotes
[VISUAL: (Architecture diagram)]  ❌ Has parentheses
[VISUAL: Diagram showing... etc.]  ❌ Has ellipsis
[visual: diagram]                  ❌ Lowercase
[VISUAL:diagram]                   ❌ No space after colon
[VISUAL: Very long description that exceeds 15 words and becomes too verbose]  ❌ Too long
```

### Visual Tags Workflow (Theory Content)

```
1. Content Generator (strands_content_gen.py)
   └─> Creates: [VISUAL: description] in lesson markdown
   
2. Visual Planner (strands_visual_planner.py)
   ├─> Extracts visual tags using: r'\[VISUAL:\s*(.*?)\]'
   ├─> Creates prompt JSON files: 01-01-0001.json
   └─> Preserves ORIGINAL description from lesson
   
3. Image Generator (images_gen.py)
   └─> Creates PNG files: 01-01-0001.png
   
4. Book Builder (book_builder.py)
   ├─> Reads prompt JSON files to get original descriptions
   ├─> Maps: [VISUAL: description] → image URL
   └─> Replaces tags with: ![description](https://.../{project}/images/01-01-0001.png)
```

**CRITICAL:** The description in the lesson markdown MUST match EXACTLY the description in the prompt JSON, or the mapping will fail and visual tags won't be replaced.

---

## 🔄 Step Functions Context Preservation

### Critical Pattern: Pass States with Parameters REPLACE Context

```yaml
# ❌ WRONG - Context is lost
SomePassState:
  Type: Pass
  Parameters:
    new_field.$: $.some_value
  Next: NextState
# Result: Only new_field exists, everything else is gone!

# ✅ CORRECT - Context is preserved
SomePassState:
  Type: Pass
  Parameters:
    new_field.$: $.some_value
    existing_field1.$: $.existing_field1
    existing_field2.$: $.existing_field2
    # ... preserve ALL fields you need downstream
  Next: NextState
```

**Key Points:**
- Pass states with `Parameters` **replace** the entire state machine context
- Always explicitly preserve fields you need in downstream states
- Common fields to preserve: `project_folder`, `course_bucket`, `outline_s3_key`, `book_result`, `master_plan_key`

---

## 📚 Book Types & Data Structures

### Theory Books (Lessons)
```json
{
  "title": "Course Title",
  "modules": [
    {
      "title": "Module 1",
      "lessons": [
        {
          "title": "Lesson Title",
          "filename": "module-1-lesson-1-title.md",
          "content": "# Lesson 1\n\n![desc](url)\n\nText...",
          "word_count": 1090,
          "module_number": 1,
          "lesson_number": 1
        }
      ]
    }
  ]
}
```

**Key Field:** `modules[].lessons[]` with `content` field containing full markdown

### Lab Guides (Labs)
```json
{
  "title": "Lab Guide",
  "modules": [
    {
      "title": "Module 1",
      "labs": [
        {
          "lab_number": 1,
          "title": "Lab Title",
          "filename": "lab-01-00-01-title.md",
          "content": "# Lab 01-00-01\n\nInstructions...",
          "duration": "60 minutos",
          "complexity": "fácil",
          "bloom_level": "Apply",
          "word_count": 1634
        }
      ]
    }
  ]
}
```

**Key Field:** `modules[].labs[]` with `content` field containing full markdown

### Frontend Compatibility (BookEditor.jsx)

```javascript
// MUST handle both structures:
const items = module.lessons || module.labs;
if (items && Array.isArray(items)) {
  items.forEach((item, itemIdx) => {
    // item.content must exist for display
    // item.filename must exist for identification
  });
}
```

---

## 🎯 Load Book API - Book Type Selection

### Backend (load_book.py)
```python
# Accept bookType query parameter
book_type = query_params.get('bookType') or 'theory'  # 'theory' or 'lab'

# Filter files based on book_type
if book_type == 'lab':
    # Include only files with 'Lab_Guide' or 'LabGuide' in name
    if 'Lab_Guide' in key or 'LabGuide' in key:
        json_files.append((key, last_modified))
else:
    # Exclude files with 'Lab_Guide' or 'LabGuide' in name
    if 'Lab_Guide' not in key and 'LabGuide' not in key:
        json_files.append((key, last_modified))
```

### Frontend (BookEditor.jsx)
```javascript
// Pass bookType in API call
const response = await fetch(
  `${API_BASE}/load-book/${projectFolder}?bookType=${bookType}`,
  { method: 'GET', headers: { 'Content-Type': 'application/json' } }
);
```

### Project List (BookBuilderPage.jsx)
```jsx
// Separate buttons for each book type
<button onClick={() => openBookEditor(project, 'theory')}>
  📚 Libro Teoría
</button>
{project.hasLabGuide && (
  <button onClick={() => openBookEditor(project, 'lab')}>
    🧪 Guía de Labs
  </button>
)}
```

---

## 🗂️ S3 Folder Structure

```
s3://crewai-course-artifacts/{project}/
├── book/
│   ├── Generated_Course_Book_complete.md      (theory markdown)
│   ├── Generated_Course_Book_data.json        (theory JSON with content)
│   ├── Lab_Guide_LabGuide_complete.md         (lab markdown)
│   └── Lab_Guide_LabGuide_data.json           (lab JSON with content)
├── lessons/
│   ├── module-1-lesson-1-title.md             (individual lesson files)
│   └── ...
├── labguide/
│   ├── lab-01-00-01-title.md                  (individual lab files)
│   ├── lab-master-plan.json                   (lab planning metadata)
│   └── ...
├── images/
│   ├── 01-01-0001.png                         (generated images)
│   └── ...
├── prompts/
│   ├── 01-01-0001.json                        (visual prompts)
│   └── ...
└── outline.yaml                                (course structure)
```

**Naming Conventions:**
- Theory book: Always starts with `Generated_Course_Book`
- Lab guide: Always contains `Lab_Guide` or `LabGuide`
- Images: Format `{module}-{lesson}-{index}.png` (e.g., `01-01-0001.png`)
- Prompts: Same ID as image (e.g., `01-01-0001.json`)

---

## 🐛 Common Issues & Solutions

### Issue 1: "Module 'yaml' not found" in Lambda
**Cause:** Deployed template without rebuilding Lambda code  
**Solution:** Always use `./deploy-with-dependencies.sh`

### Issue 2: Visual tags not replaced in theory book
**Cause:** Prompt files not created or description mismatch  
**Check:**
1. Verify prompts folder has JSON files: `aws s3 ls s3://bucket/{project}/prompts/`
2. Check visual tag format in lessons matches prompts
3. Verify book_builder ran after images were generated

**Manual Fix:**
```python
# Rebuild theory book JSON with image references
python3 << 'SCRIPT'
import boto3, json, re
s3 = boto3.client('s3')
# Load book JSON
response = s3.get_object(Bucket='bucket', Key='{project}/book/Generated_Course_Book_data.json')
book = json.loads(response['Body'].read())
# Replace visual tags with images (see repair script)
SCRIPT
```

### Issue 3: Lab guide shows for theory book (or vice versa)
**Cause:** `load_book.py` returns most recent `_data.json` without filtering by type  
**Solution:** Pass `?bookType=theory` or `?bookType=lab` in API call

### Issue 4: Step Functions execution fails with "JSONPath not found"
**Cause:** Context lost in Pass state with Parameters  
**Solution:** Explicitly preserve all needed fields in Pass state Parameters

### Issue 5: Blank page when viewing book
**Cause:** JSON missing `content` field (only has metadata)  
**Solution:** 
- Theory books: Ensure book_builder includes lesson content
- Lab guides: Ensure LabGuideBuilder includes lab content

---

## 📊 Verification Checklist (After Course Generation)

### ✅ Theory Book Verification
```bash
# 1. Check lesson files exist
aws s3 ls s3://crewai-course-artifacts/{project}/lessons/

# 2. Check visual tags in lessons
aws s3 cp s3://.../lessons/module-1-lesson-1-*.md - | grep -c "\[VISUAL:"

# 3. Check prompt files created
aws s3 ls s3://crewai-course-artifacts/{project}/prompts/ | wc -l

# 4. Check images generated
aws s3 ls s3://crewai-course-artifacts/{project}/images/ | wc -l

# 5. Check theory book JSON has images (not visual tags)
aws s3 cp s3://.../book/Generated_Course_Book_data.json - | jq '.modules[0].lessons[0].content' | grep "!\["
```

### ✅ Lab Guide Verification
```bash
# 1. Check lab files exist
aws s3 ls s3://crewai-course-artifacts/{project}/labguide/

# 2. Check lab guide JSON has content field
aws s3 cp s3://.../book/Lab_Guide_LabGuide_data.json - | jq '.modules[0].labs[0] | has("content")'

# 3. Verify content is not empty
aws s3 cp s3://.../book/Lab_Guide_LabGuide_data.json - | jq '.modules[0].labs[0].content' | wc -c
```

---

## 🔧 Emergency Repair Procedures

### Repair 1: Fix Theory Book with Missing Images
```bash
cd /home/juan/AuroraV1/CG-Backend
python3 << 'PYSCRIPT'
import boto3, json, re
s3 = boto3.client('s3')
project = 'YYMMDD-Course-XX'
bucket = 'crewai-course-artifacts'

# Get images list
images = sorted([obj['Key'].split('/')[-1] 
    for obj in s3.list_objects_v2(Bucket=bucket, Prefix=f'{project}/images/').get('Contents', [])])

# Load book
response = s3.get_object(Bucket=bucket, Key=f'{project}/book/Generated_Course_Book_data.json')
book = json.loads(response['Body'].read())

# Replace visual tags
counter = 1
for module in book.get('modules', []):
    for lesson in module.get('lessons', []):
        content = lesson.get('content', '')
        tags = re.findall(r'\[VISUAL:\s*(.*?)\]', content)
        for tag_desc in tags:
            if counter <= len(images):
                img = images[counter - 1]
                url = f"https://{bucket}.s3.amazonaws.com/{project}/images/{img}"
                old = f"[VISUAL: {tag_desc}]"
                new = f"![{tag_desc}]({url})"
                content = content.replace(old, new, 1)
                counter += 1
        lesson['content'] = content

# Save
s3.put_object(Bucket=bucket, Key=f'{project}/book/Generated_Course_Book_data.json',
    Body=json.dumps(book, ensure_ascii=False, indent=2), ContentType='application/json')
print(f"✅ Fixed {counter-1} visual tags")
PYSCRIPT
```

### Repair 2: Fix Lab Guide with Missing Content
```bash
# Rebuild lab guide JSON from markdown files
python3 << 'PYSCRIPT'
import boto3, json
s3 = boto3.client('s3')
project = 'YYMMDD-Course-XX'
bucket = 'crewai-course-artifacts'

# Load existing JSON
response = s3.get_object(Bucket=bucket, Key=f'{project}/book/Lab_Guide_LabGuide_data.json')
book = json.loads(response['Body'].read())

# Get lab files
labs = sorted([obj['Key'] for obj in s3.list_objects_v2(Bucket=bucket, 
    Prefix=f'{project}/labguide/').get('Contents', []) if obj['Key'].endswith('.md')])

# Update each lab with content
for idx, lab_key in enumerate(labs):
    if idx < len(book['modules'][0]['labs']):
        response = s3.get_object(Bucket=bucket, Key=lab_key)
        content = response['Body'].read().decode('utf-8')
        book['modules'][0]['labs'][idx]['content'] = content
        book['modules'][0]['labs'][idx]['filename'] = lab_key.split('/')[-1]

# Save
s3.put_object(Bucket=bucket, Key=f'{project}/book/Lab_Guide_LabGuide_data.json',
    Body=json.dumps(book, ensure_ascii=False, indent=2), ContentType='application/json')
print(f"✅ Updated {len(labs)} labs with content")
PYSCRIPT
```

---

## 📝 Development Workflow Best Practices

### Before Making Changes
1. ✅ Read this instructions file
2. ✅ Check existing code patterns
3. ✅ Test changes locally if possible
4. ✅ Use deployment script for Lambda updates

### After Making Changes
1. ✅ Deploy with `./deploy-with-dependencies.sh`
2. ✅ Test end-to-end with small course
3. ✅ Verify visual tags workflow
4. ✅ Check both theory and lab guide display
5. ✅ Update this file if new patterns emerge

### When Debugging
1. ✅ Check CloudWatch logs for each Lambda
2. ✅ Verify S3 folder structure
3. ✅ Test Step Functions execution in AWS Console
4. ✅ Use AWS CLI to inspect S3 objects directly

---

## 🤖 AI Agent Instructions

If you are an AI assistant working on this codebase:

1. **ALWAYS** use `./deploy-with-dependencies.sh` for deployments
2. **NEVER** modify visual tag format without updating all components
3. **ALWAYS** preserve Step Functions context in Pass states
4. **VERIFY** S3 folder structure matches documentation
5. **TEST** both theory and lab guide paths after changes
6. **UPDATE** this file when discovering new patterns or issues
7. **REFERENCE** this file before making changes to core components

### Key Files to Understand
- `template.yaml` - Step Functions state machine definition
- `lambda/strands_content_gen/strands_content_gen.py` - Content generation with visual tags
- `lambda/strands_visual_planner/strands_visual_planner.py` - Visual tag extraction & prompt creation
- `lambda/images_gen.py` - Image generation from prompts
- `lambda/book_builder.py` - Book assembly with visual tag replacement
- `src/components/BookEditor.jsx` - Frontend book display
- `src/components/BookBuilderPage.jsx` - Project list with book type selection

---

## 📞 Support & Maintenance

**Repository:** github.com/AURORA-BOTIEF/AuroraV1  
**Branch:** testing  
**AWS Region:** us-east-1  
**S3 Bucket:** crewai-course-artifacts

**Last Major Changes:**
- Oct 24, 2025: Fixed visual tag format specification
- Oct 24, 2025: Added book type selection (theory vs lab)
- Oct 24, 2025: Fixed context preservation in Step Functions
- Oct 24, 2025: PowerPoint Generator - Optimized 16:9 layout, image sizing, and S3 image retrieval

---

## 🎤 PowerPoint Generator - Layout & Image Optimization

### StrandsPPTGenerator Lambda Function

**Purpose:** Generate professional PowerPoint presentations from book content using AI-powered slide design with proper 16:9 layout and image integration.

### Critical Layout Specifications (16:9 Format)

**Slide Dimensions:**
```python
prs.slide_width = Inches(13.333)   # 16:9 aspect ratio
prs.slide_height = Inches(7.5)
```

**Two-Column Layout (with images):**
```python
# Text column: 60% of usable space
content_left = Inches(0.8)        # Left margin
content_width = Inches(7.5)       # Text width
content_top = Inches(1.8)         # Below title
content_height = Inches(5.2)      # Vertical space

# Image column: 30% of slide width
image_left = Inches(8.8)          # Right side
image_top = Inches(2.2)           # Aligned with content
image_width = Inches(4.0)         # Max width constraint
image_height = Inches(4.5)        # Max height constraint
```

**Full-Width Layout (no images):**
```python
content_left = Inches(1.5)        # More centered
content_width = Inches(10.5)      # Wider but balanced
```

### Image Retrieval from S3

**VISUAL Tag Processing:**
```markdown
Lesson content: [VISUAL: description]
↓
Extract: url: None (not '' empty string)
↓
S3 search with multiple path patterns:
1. {project}/images/ ✅ (primary - flat folder)
2. {project}/lessons/lesson_X/images/ (fallback)
3. {project}/lesson_X/images/ (fallback)
4. {project}/images/lesson_X/ (fallback)
↓
Filter by lesson number: 01-XX-XXXX.png for lesson 1
↓
Assign unique image per slide using img_idx
```

**S3 Image Naming Convention:**
```
{project}/images/01-01-0001.png  → Lesson 1, first image
{project}/images/01-02-0002.png  → Lesson 1, second image
{project}/images/02-01-0001.png  → Lesson 2, first image
```

**Image Selection Logic:**
```python
# Format lesson number as 2 digits
lesson_num_str = f"{lesson_idx:02d}"  # "01", "02", etc.

# Find images matching pattern: XX-YY-ZZZZ.png
for s3_obj in s3_objects:
    filename = key.split('/')[-1]
    if filename.startswith(f"{lesson_num_str}-"):
        matching_images.append(key)

# Cycle through matching images using img_idx
selected_key = matching_images[img_idx % len(matching_images)]
```

### Text Optimization for Visual Balance

**Font Sizing:**
```python
# With images (prevent text overflow)
p.font.size = Pt(16)              # Smaller for better fit
p.space_before = Pt(8)            # Tighter spacing
p.space_after = Pt(6)

# Without images (full width)
p.font.size = Pt(18)              # Standard size
p.space_before = Pt(12)           # Normal spacing
p.space_after = Pt(8)
```

**Bullet Limiting:**
```python
max_bullets = 7 if has_image else 8
bullets_to_show = bullets[:max_bullets]
# Prevents text overwhelming and ensures visual balance
```

### Image Sizing & Aspect Ratio

**Automatic Sizing (python-pptx):**
```python
# Add image with width constraint
pic = slide.shapes.add_picture(img_data, image_left, image_top, width=image_width)

# Check if height exceeds limit after width constraint
if pic.height > image_height:
    # Recalculate to fit height instead
    aspect_ratio = pic.width / pic.height
    pic.height = image_height
    pic.width = int(image_height * aspect_ratio)
    
    # Re-center horizontally if narrower
    if pic.width < image_width:
        pic.left = image_left + (image_width - pic.width) // 2
```

### AI Slide Generation Best Practices

**Prompt Requirements:**
```python
slides_per_lesson = 6  # Target slides per lesson
presentation_style = 'professional'  # or 'educational', 'modern'

# AI MUST generate:
- Compelling, descriptive titles (not generic)
- 3-7 bullet points per slide (concise, impactful)
- NEVER create empty bullet lists
- Image references: "USE_IMAGE: description"
- Each content slide MUST have bullets array with 3+ points
```

**Slide Type Distribution:**
- Title slides: Course intro, lesson intros
- Content slides: Main concepts (60% of slides)
- Image slides: Full-screen visuals (20%)
- Summary slides: Key takeaways (20%)

### Common Issues & Solutions

#### Issue 1: Images Overwhelming Slides
**Symptoms:** Large image covering most of slide, text cramped  
**Cause:** Image dimensions too large (old values: 5" width, 8" left position)  
**Solution:** Reduced to 4.0" width max, 4.5" height max, positioned at 8.8" left

#### Issue 2: Text Overlapping and Overwhelming
**Symptoms:** Too many bullets, text running off slide  
**Cause:** No bullet limiting, font too large with images  
**Solution:** 
- Max 7 bullets with images, 8 without
- Reduced font to 16pt with images
- Tighter spacing (8pt/6pt vs 12pt/8pt)
- Wider text column (7.5" vs 6.5")

#### Issue 3: Unused White Space on Right
**Symptoms:** Content hugging left side, empty right side  
**Cause:** Content width too narrow (was 6.5")  
**Solution:** Increased to 7.5" for better space utilization (60% of usable width)

#### Issue 4: No Images Appearing
**Symptoms:** Slides have no images despite VISUAL tags  
**Cause:** VISUAL tags had `url: ''` instead of `url: None`  
**Solution:** 
- Changed extract to use `url: None`
- Added S3 search with multiple path patterns
- Filter by lesson number (01-XX-XXXX.png pattern)

#### Issue 5: Same Image on Multiple Slides
**Symptoms:** Image repetition across different slides  
**Cause:** S3 fallback assigning same image to all  
**Solution:** Track used images with `used_image_indices` set, cycle through lesson-specific images

#### Issue 6: Content Not Centered (4:3 in 16:9)
**Symptoms:** Content positioned like 4:3 pasted into 16:9  
**Cause:** Content at 0.5" from edge (too close)  
**Solution:** 
- With images: 0.8" left margin (better padding)
- Without images: 1.5" left margin (centered appearance)

### Verification Checklist

**After PPT Generation:**
```bash
# 1. Check CloudWatch logs for image retrieval
aws logs tail /aws/lambda/StrandsPPTGenerator --since 5m | grep "Retrieved image"

# 2. Verify S3 image search found images
aws logs tail /aws/lambda/StrandsPPTGenerator --since 5m | grep "Found matching image"

# 3. Check final image insertion
aws logs tail /aws/lambda/StrandsPPTGenerator --since 5m | grep "Inserted image"

# 4. Verify image dimensions logged
aws logs tail /aws/lambda/StrandsPPTGenerator --since 5m | grep "inches"
```

**Visual Inspection:**
- ✅ Images sized appropriately (not overwhelming)
- ✅ Text readable and not cramped
- ✅ Content centered properly for 16:9
- ✅ Balanced use of horizontal space
- ✅ Different images on different slides
- ✅ No blank slides

### Lambda Configuration

```yaml
StrandsPPTGenerator:
  Runtime: python3.12
  Handler: strands_ppt_generator.lambda_handler
  MemorySize: 1024
  Timeout: 900  # 15 minutes for large presentations
  Layers:
    - !Ref StrandsAgentsLayer
    - !Ref PPTLayer  # Contains python-pptx, requests
  Environment:
    STRANDS_API_KEY: !Ref StrandsAPIKey
```

**Dependencies (PPTLayer):**
- python-pptx (PowerPoint generation)
- requests (HTTP fallback for images)
- boto3 (S3 access - included in Lambda runtime)

---

**Remember:** When in doubt, refer to this file first!
