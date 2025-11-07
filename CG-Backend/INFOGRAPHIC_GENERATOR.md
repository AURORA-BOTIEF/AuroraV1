# 🎨 HTML Infographic Generator - Migration Complete

## ✅ What Changed

### Old System (REMOVED):
- ❌ `StrandsPPTGenerator` - python-pptx with layout issues
- ❌ Complex overlap detection (200+ lines, didn't work)
- ❌ Overwhelming content, persistent overlaps
- ❌ Timeout issues even after fixes

### New System (ACTIVE):
- ✅ `StrandsInfographicGenerator` - HTML to editable PPT
- ✅ Clean semantic HTML with proper structure
- ✅ CSS prevents overlaps by design
- ✅ Professional layouts (professional/modern/minimal styles)
- ✅ Each concept = one slide with proper hierarchy
- ✅ Exports to **editable PowerPoint** (text boxes preserved!)

---

## 🚀 API Endpoint

**New Endpoint:**
```
POST https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod/generate-infographic
```

**Old Endpoint (REMOVED):**
```
POST /generate-ppt  ❌ NO LONGER EXISTS
```

---

## 📦 Request Format

```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "projects/your-course",
  "book_version_key": "projects/your-course/theory-book/book_version_20241104.json",
  "model_provider": "bedrock",
  "slides_per_lesson": 5,
  "style": "professional",
  "lesson_start": 1,
  "lesson_end": 10,
  "max_lessons_per_batch": 10
}
```

### Parameters:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `course_bucket` | string | ✅ Yes | - | S3 bucket name |
| `project_folder` | string | ✅ Yes | - | Project folder path in S3 |
| `book_version_key` | string | ✅ Yes | - | S3 key to book JSON |
| `model_provider` | string | No | `bedrock` | `bedrock` or `openai` |
| `slides_per_lesson` | number | No | `5` | Number of slides per lesson |
| `style` | string | No | `professional` | `professional`, `modern`, or `minimal` |
| `lesson_start` | number | No | `1` | First lesson to process |
| `lesson_end` | number | No | auto | Last lesson (auto = all remaining) |
| `max_lessons_per_batch` | number | No | `10` | Max lessons per batch |

### Styles:

1. **professional** (default)
   - Clean, corporate look
   - Blues and grays
   - Structured layouts
   - Best for: Corporate training, certifications

2. **modern**
   - Bold colors
   - Minimal text
   - High-impact visuals
   - Best for: Marketing, product launches

3. **minimal**
   - Maximum whitespace
   - Serif fonts
   - Elegant simplicity
   - Best for: Executive presentations

---

## 📤 Response Format

```json
{
  "message": "Infographic generated successfully",
  "course_title": "Your Course Title",
  "total_slides": 42,
  "completion_status": "complete",
  "structure_s3_key": "projects/your-course/infographics/infographic_structure.json",
  "html_s3_key": "projects/your-course/infographics/infographic.html",
  "pptx_s3_key": "projects/your-course/infographics/Your_Course_Title.pptx"
}
```

### Output Files:

1. **`infographic_structure.json`** - Full slide structure with all content
2. **`infographic.html`** - Standalone HTML (can be viewed in browser)
3. **`Your_Course_Title.pptx`** - **Editable PowerPoint** with text boxes!

---

## ✨ Key Features

### 1. Semantic HTML Structure
Each slide is a clean HTML section:
```html
<div class="slide">
  <h1 class="slide-title">Clear Title</h1>
  <p class="slide-subtitle">Context</p>
  <div class="content-block">
    <h2 class="block-heading">Key Concepts</h2>
    <ul class="bullets">
      <li>Concise point 1</li>
      <li>Concise point 2</li>
    </ul>
  </div>
</div>
```

### 2. Layout Hints
AI determines best layout per slide:
- `single-column` - Traditional presentation
- `two-column` - Side-by-side content
- `image-focus` - Large visual with minimal text
- `text-focus` - More detailed content
- `title` - Title slide
- `summary` - Summary/conclusion

### 3. Content Quality
- **Maximum 5 bullets per slide**
- **Each bullet under 15 words**
- **One key concept per slide**
- **Generous whitespace**
- **Clear hierarchy** (h1 > h2 > bullets)

### 4. Editable PowerPoint
- Text is in **text boxes** (not images!)
- Users can edit titles, bullets, notes
- Images are placeholders (will be enhanced in future)
- Professional color schemes
- Standard 16:9 format (1280x720)

---

## 🔧 Deployment

### Quick Deploy (Infographic Generator Only):
```bash
cd CG-Backend
./deploy-ppt-only.sh
```
- ⏱️ **~30 seconds**
- ✅ **Safe** - doesn't touch content generator
- 📦 Builds and deploys only infographic function

### Full Stack Deploy:
```bash
cd CG-Backend
sam deploy
```
- ⏱️ **~8 minutes**
- ⚠️ Rebuilds ALL functions
- Use only when necessary

---

## 🧪 Testing

### 1. Direct Lambda Invocation:
```bash
aws lambda invoke \
  --function-name StrandsInfographicGenerator \
  --payload '{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "projects/test-course",
    "book_version_key": "projects/test-course/theory-book/book_version.json",
    "slides_per_lesson": 5,
    "style": "professional"
  }' \
  /tmp/infographic-response.json

cat /tmp/infographic-response.json | jq .
```

### 2. Via API Gateway:
```bash
curl -X POST \
  https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod/generate-infographic \
  -H "Content-Type: application/json" \
  -d '{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "projects/test-course",
    "book_version_key": "projects/test-course/theory-book/book_version.json"
  }'
```

### 3. Check Logs:
```bash
aws logs tail /aws/lambda/StrandsInfographicGenerator --follow
```

---

## 📊 Performance

| Metric | Value | Notes |
|--------|-------|-------|
| **Function Timeout** | 900s (15 min) | AWS Lambda hard limit |
| **Memory** | 1024 MB | Standard, sufficient |
| **Batch Size** | 10 lessons | Default, configurable |
| **Slides/Lesson** | 5 slides | Default, configurable |
| **Generation Time** | ~30-45s per lesson | With Bedrock AI |
| **Recommended Batch** | 10-12 lessons | Stays under timeout |

---

## 🎯 Architecture Advantages

### vs. Old PPT Generator:

| Aspect | Old (python-pptx) | New (HTML→PPT) |
|--------|------------------|----------------|
| **Overlaps** | ❌ Constant issue | ✅ CSS prevents by design |
| **Layout Control** | ❌ Complex calculations | ✅ Semantic HTML |
| **Editability** | ❌ Text in shapes | ✅ Text in text boxes |
| **Maintenance** | ❌ 2566 lines | ✅ Clean structure |
| **Content Quality** | ❌ Overwhelming | ✅ Concise (max 5 bullets) |
| **AI Prompts** | ❌ Generic | ✅ Optimized for infographics |
| **Output Formats** | ❌ PPT only | ✅ HTML + PPT + PDF-ready |

---

## 🔮 Future Enhancements

### Phase 1 (Next Sprint):
1. **Image Resolution** - Load actual S3 images into HTML/PPT
2. **Chart Integration** - Add charts for data visualization
3. **Icon Library** - Professional icons for concepts
4. **Custom Templates** - User-defined color schemes

### Phase 2:
1. **Interactive HTML** - Click to expand, animations
2. **PDF Export** - Direct PDF generation (Puppeteer)
3. **Video Slides** - Embed video content
4. **Multi-language** - Support for non-English content

### Phase 3:
1. **Brand Customization** - Upload logos, custom themes
2. **Analytics** - Track which slides are most viewed
3. **Collaboration** - Share and comment on slides
4. **Version Control** - Track slide revisions

---

## 📚 Related Documentation

- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **API Reference**: `docs/CONFIG.md`
- **Architecture**: `ARCHITECTURE.md`
- **Strands Integration**: `CG-Backend/lambda/strands_infographic_generator/`

---

## 🤝 Frontend Integration

### Update API Call:
```javascript
// Old (REMOVE):
const response = await fetch(`${API_BASE}/generate-ppt`, { ... });  ❌

// New (USE THIS):
const response = await fetch(`${API_BASE}/generate-infographic`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    course_bucket: 'crewai-course-artifacts',
    project_folder: `projects/${projectId}`,
    book_version_key: bookVersionKey,
    style: 'professional',  // NEW: Choose style
    slides_per_lesson: 5     // NEW: Control density
  })
});

const result = await response.json();
console.log('PPT generated:', result.pptx_s3_key);
```

### Download Links:
```javascript
// User can download:
const htmlUrl = getPresignedUrl(result.html_s3_key);     // View in browser
const pptxUrl = getPresignedUrl(result.pptx_s3_key);     // Edit in PowerPoint
const jsonUrl = getPresignedUrl(result.structure_s3_key); // For analysis
```

---

## ✅ Migration Checklist

- [x] Remove old `StrandsPPTGenerator` function
- [x] Create new `StrandsInfographicGenerator` function
- [x] Update SAM template
- [x] Update deployment script
- [x] Deploy to AWS
- [x] Test new endpoint
- [ ] Update frontend API calls
- [ ] Update documentation links
- [ ] User acceptance testing
- [ ] Monitor logs for issues

---

**Status**: ✅ **DEPLOYED AND READY**
**Deployment Date**: November 4, 2025
**Function ARN**: `arn:aws:lambda:us-east-1:746434296869:function:StrandsInfographicGenerator`
**API Endpoint**: `https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod/generate-infographic`
