# Multi-Agent PPT Generation Architecture

## Implementation Date: October 27, 2025

## Overview
Replaced single-agent hardcoded layout system with dynamic three-agent architecture that intelligently adapts slide layouts based on content characteristics.

## Architecture

### Agent 1: Content Curator
**Role**: Extract and structure content with metadata

**Responsibilities**:
- Analyze lesson content for key concepts
- Create 3-7 bullet points per slide
- Count character lengths and assess complexity
- Identify visual support requirements
- Generate metadata for layout decisions

**Output**: Structured JSON with bullets + metadata
```json
{
  "bullet_count": 4,
  "total_text_length": 156,
  "avg_bullet_length": 39,
  "complexity": "moderate",
  "needs_visual": true,
  "visual_importance": "high",
  "content_density": "light"
}
```

### Agent 2: Layout Designer
**Role**: Calculate optimal slide layouts dynamically

**Responsibilities**:
- Analyze content metadata
- Choose layout type (text_only, text_focused, balanced, visual_focused, image_full)
- Calculate precise dimensions for 16:9 format
- Determine font sizing
- Match content to available images

**Layout Types**:
1. **text_only**: 12.333" wide (no image)
2. **text_focused**: 7.5" text + 4.333" image
3. **balanced**: 6.0" text + 5.833" image (equal emphasis)
4. **visual_focused**: 5.0" text + 6.833" image
5. **image_full**: Full screen image with caption

**Output**: Precise dimensions and styling
```json
{
  "layout_type": "balanced",
  "dimensions": {
    "text_left": 0.5,
    "text_width": 6.0,
    "image_left": 7.0,
    "image_width": 5.833,
    "gap": 0.5
  },
  "styling": {
    "bullet_font_size": 14,
    "max_bullets": 5
  }
}
```

### Agent 3: Quality Supervisor
**Role**: Validate and ensure professional quality

**Validation Rules**:
- ✓ Minimum 0.5" gap between text and image
- ✓ No elements exceed slide bounds
- ✓ Appropriate bullet count for layout type
- ✓ Font sizes readable (≥12pt)
- ✓ Logical layout choice for content

**Output**: Approval or adjustment requests
```json
{
  "approved": true,
  "message": "Layout optimal for content"
}
```

## Key Benefits

### 1. **Dynamic Adaptation**
- No more hardcoded 6.0" text / 5.8" image dimensions
- Layouts adapt to content density
- Heavy content → more text space
- Complex diagrams → more image space

### 2. **Intelligent Decisions**
- Agent analyzes bullet count, character length, complexity
- Chooses optimal layout type automatically
- Prevents overwhelming slides
- Ensures no text/image overlap

### 3. **Quality Assurance**
- Automated validation before generation
- Catches spacing violations
- Ensures professional appearance
- Iterative refinement possible

### 4. **Maintainable**
- Clear separation of concerns
- Each agent has specific role
- Easy to adjust rules/thresholds
- Modular architecture

## Implementation Details

### Files Modified
1. **ppt_agents.py** (NEW)
   - Three agent definitions
   - Process pipeline function
   - 662 lines of agent logic

2. **strands_ppt_generator.py** (UPDATED)
   - Integrated multi-agent system
   - Updated `generate_presentation_structure()`
   - Dynamic dimension handling in `generate_pptx_file()`

### Workflow
```
1. Content Curator
   ↓ (structured content + metadata)
2. Layout Designer  
   ↓ (precise dimensions + styling)
3. Quality Supervisor
   ↓ (validated specs)
4. PPTX Generator
   ↓ (final .pptx file)
```

### Example Flow
**Input**: Lesson with 5 bullet points (220 chars total), needs diagram

**Content Curator Output**:
- bullet_count: 5
- total_text_length: 220
- complexity: moderate
- needs_visual: true
- visual_importance: high

**Layout Designer Decision**:
- Layout: **balanced** (equal text/image)
- Text: 6.0" wide at 0.5" left
- Image: 5.833" wide at 7.0" left
- Font: 14pt, max 5 bullets
- Gap: 0.5"

**Quality Supervisor Check**:
- ✓ 6.0 + 0.5 + 5.833 = 12.333" (fits!)
- ✓ 5 bullets = max for balanced layout
- ✓ 14pt font readable
- **APPROVED**

## Expected Improvements

### Before (Hardcoded)
- ❌ Same 6.0" / 5.8" for all slides
- ❌ Images overwhelming on text-heavy slides
- ❌ Text cramped on visual-heavy slides
- ❌ No adaptation to content
- ❌ 10+ deployment iterations to tweak

### After (Multi-Agent)
- ✅ Dynamic layouts per slide
- ✅ Appropriate sizing for content type
- ✅ Balanced visual hierarchy
- ✅ Professional appearance
- ✅ Self-optimizing system

## Testing Plan
1. Deploy multi-agent system
2. Generate PPT from theory book
3. Verify varied layouts across slides
4. Check for:
   - No text/image overlap
   - Appropriate sizing per content
   - Professional appearance
   - No blank slides

## Rollback Plan
If issues occur:
1. Git revert to commit before multi-agent changes
2. Redeploy previous version
3. System restores to hardcoded layout

## Success Metrics
- ✓ No text/image overlap reported
- ✓ Varied layout types used (not all "balanced")
- ✓ Professional appearance confirmed
- ✓ No blank slides
- ✓ Content appropriately fitted

## Notes
- First deployment will show if agent prompts need tuning
- May need to adjust validation thresholds
- Layout Designer decision logic can be refined
- Quality Supervisor can be made more strict/lenient as needed

---
**Status**: Ready for deployment
**Deployment Command**: `bash deploy-with-dependencies.sh`
**Estimated Deploy Time**: 3-5 minutes
