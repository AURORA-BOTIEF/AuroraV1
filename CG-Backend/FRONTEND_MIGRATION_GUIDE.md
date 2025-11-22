# 🔄 Frontend Migration Guide - PPT to Infographic Generator

## ⚡ Quick Changes Required

### 1. Update API Endpoint

**OLD** (Remove):
```javascript
const API_ENDPOINT = `${API_BASE}/generate-ppt`;
```

**NEW** (Use this):
```javascript
const API_ENDPOINT = `${API_BASE}/generate-infographic`;
```

---

### 2. Update Request Body

**OLD**:
```javascript
const requestBody = {
  course_bucket: 'crewai-course-artifacts',
  project_folder: `projects/${projectId}`,
  book_version_key: bookKey,
  model_provider: 'bedrock'
};
```

**NEW** (with additional options):
```javascript
const requestBody = {
  course_bucket: 'crewai-course-artifacts',
  project_folder: `projects/${projectId}`,
  book_version_key: bookKey,
  model_provider: 'bedrock',
  
  // NEW OPTIONAL PARAMETERS:
  style: 'professional',        // 'professional' | 'modern' | 'minimal'
  slides_per_lesson: 5,         // Number of slides per lesson
  lesson_start: 1,              // For batch processing
  lesson_end: 10,               // For batch processing
  max_lessons_per_batch: 10     // Max lessons per run
};
```

---

### 3. Update Response Handling

**OLD**:
```javascript
const response = await fetch(API_ENDPOINT, { ... });
const result = await response.json();

// Old response structure:
{
  message: "...",
  pptx_s3_key: "...",
  total_slides: 25
}
```

**NEW**:
```javascript
const response = await fetch(API_ENDPOINT, { ... });
const result = await response.json();

// New response structure:
{
  message: "Infographic generated successfully",
  course_title: "Your Course Title",
  total_slides: 42,
  completion_status: "complete",    // or "partial"
  
  // Three output files:
  structure_s3_key: "path/to/infographic_structure.json",  // NEW
  html_s3_key: "path/to/infographic.html",                // NEW
  pptx_s3_key: "path/to/Your_Course_Title.pptx"
}
```

---

### 4. Add Style Selector (Optional)

Add a style picker in your UI:

```jsx
const [infographicStyle, setInfographicStyle] = useState('professional');

<select 
  value={infographicStyle} 
  onChange={(e) => setInfographicStyle(e.target.value)}
>
  <option value="professional">Professional (Corporate)</option>
  <option value="modern">Modern (Bold & Minimal)</option>
  <option value="minimal">Minimal (Elegant)</option>
</select>
```

Then include in request:
```javascript
body: JSON.stringify({
  ...existingParams,
  style: infographicStyle
})
```

---

### 5. Update Download Logic

**OLD** (single download):
```javascript
const downloadPPT = () => {
  const pptUrl = getPresignedUrl(result.pptx_s3_key);
  window.open(pptUrl);
};
```

**NEW** (multiple download options):
```javascript
const downloadPPT = () => {
  const pptUrl = getPresignedUrl(result.pptx_s3_key);
  window.open(pptUrl);
};

const viewHTML = () => {
  const htmlUrl = getPresignedUrl(result.html_s3_key);
  window.open(htmlUrl, '_blank');  // Opens in browser
};

const downloadStructure = () => {
  const jsonUrl = getPresignedUrl(result.structure_s3_key);
  window.open(jsonUrl);
};
```

**UI Example**:
```jsx
<div className="download-options">
  <button onClick={downloadPPT}>
    📥 Download PowerPoint (Editable)
  </button>
  <button onClick={viewHTML}>
    🌐 View HTML Preview
  </button>
  <button onClick={downloadStructure}>
    📋 Download Structure (JSON)
  </button>
</div>
```

---

### 6. Update Loading Messages

**OLD**:
```javascript
setStatus('Generating PowerPoint presentation...');
```

**NEW** (more informative):
```javascript
setStatus('Generating infographic slides...');
setProgress(0);

// Later, if using batch processing:
if (result.completion_status === 'partial') {
  setStatus(`Generated ${result.total_slides} slides (partial - continue batch)`);
} else {
  setStatus(`✅ Generated ${result.total_slides} slides successfully!`);
}
```

---

### 7. Complete Example

```jsx
import { useState } from 'react';

const InfographicGenerator = ({ projectId, bookVersionKey }) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [style, setStyle] = useState('professional');
  const [slidesPerLesson, setSlidesPerLesson] = useState(5);

  const generateInfographic = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${process.env.REACT_APP_API_BASE}/generate-infographic`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            course_bucket: 'crewai-course-artifacts',
            project_folder: `projects/${projectId}`,
            book_version_key: bookVersionKey,
            model_provider: 'bedrock',
            style: style,
            slides_per_lesson: slidesPerLesson,
            max_lessons_per_batch: 10
          })
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
      
      // Success notification
      console.log(`✅ Generated ${data.total_slides} slides`);
      console.log(`Status: ${data.completion_status}`);
      
    } catch (error) {
      console.error('Generation failed:', error);
      alert(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const downloadPPT = () => {
    if (result?.pptx_s3_key) {
      const url = getPresignedUrl(result.pptx_s3_key);
      window.open(url);
    }
  };

  const viewHTML = () => {
    if (result?.html_s3_key) {
      const url = getPresignedUrl(result.html_s3_key);
      window.open(url, '_blank');
    }
  };

  return (
    <div className="infographic-generator">
      <h2>Generate Infographic Slides</h2>
      
      {/* Style Selector */}
      <div className="form-group">
        <label>Presentation Style:</label>
        <select value={style} onChange={(e) => setStyle(e.target.value)}>
          <option value="professional">Professional</option>
          <option value="modern">Modern</option>
          <option value="minimal">Minimal</option>
        </select>
      </div>

      {/* Slides Per Lesson */}
      <div className="form-group">
        <label>Slides per Lesson:</label>
        <input
          type="number"
          value={slidesPerLesson}
          onChange={(e) => setSlidesPerLesson(Number(e.target.value))}
          min="3"
          max="10"
        />
      </div>

      {/* Generate Button */}
      <button 
        onClick={generateInfographic} 
        disabled={loading || !bookVersionKey}
      >
        {loading ? '⏳ Generating...' : '🎨 Generate Infographic'}
      </button>

      {/* Results */}
      {result && (
        <div className="results">
          <h3>✅ {result.message}</h3>
          <p>Course: {result.course_title}</p>
          <p>Total Slides: {result.total_slides}</p>
          <p>Status: {result.completion_status}</p>

          <div className="download-buttons">
            <button onClick={downloadPPT}>
              📥 Download PowerPoint
            </button>
            <button onClick={viewHTML}>
              🌐 Preview HTML
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default InfographicGenerator;
```

---

## 🎨 Style Guide for Users

When displaying style options to users:

### Professional
- **Best for**: Corporate training, certifications, formal education
- **Colors**: Blues, grays, structured
- **Text**: Moderate density, clear hierarchy
- **Use case**: Oracle Database Training, AWS Certification, etc.

### Modern
- **Best for**: Product launches, marketing, creative content
- **Colors**: Bold, high-contrast
- **Text**: Minimal, impactful
- **Use case**: New feature announcements, sales presentations

### Minimal
- **Best for**: Executive briefings, elegant reports
- **Colors**: Black, white, grays
- **Text**: Sparse, refined
- **Use case**: C-level presentations, design reviews

---

## 🚨 Breaking Changes

1. **Endpoint changed**: `/generate-ppt` → `/generate-infographic`
2. **Response structure changed**: Now includes 3 files (HTML, JSON, PPT)
3. **New parameters**: `style`, `slides_per_lesson` (optional but recommended)
4. **New response field**: `completion_status` (indicates if partial batch)

---

## ✅ Migration Checklist

- [ ] Update API endpoint URL
- [ ] Update request body to include new optional parameters
- [ ] Update response handling for new structure
- [ ] Add UI for style selection (optional but nice)
- [ ] Update download logic to handle multiple files
- [ ] Update loading/success messages
- [ ] Test with different styles
- [ ] Test with different slides_per_lesson values
- [ ] Handle `completion_status: "partial"` appropriately
- [ ] Update user documentation/help text

---

## 📞 Support

**Questions?** Contact:
- Backend team for API issues
- Check logs: `aws logs tail /aws/lambda/StrandsInfographicGenerator --follow`
- Review documentation: `CG-Backend/INFOGRAPHIC_GENERATOR.md`

---

**Migration Difficulty**: 🟢 Low (mostly find-and-replace)
**Estimated Time**: 30-60 minutes
**Testing Required**: Yes - test all 3 styles and download options
