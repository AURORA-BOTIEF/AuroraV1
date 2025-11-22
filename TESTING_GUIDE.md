# 🧪 Testing Guide for PPT Generator Fixes

## Quick Start - How to Verify the Fixes

### Fix #1 & #3: Title & Subtitle Alignment ✅

**Test Scenario:**
Generate a slide with a long title that wraps to 2-3 lines

**Expected Behavior:**
- ✅ Title box expands to fit all text
- ✅ Subtitle appears **below** title (not overlapping)
- ✅ Content starts **below** subtitle
- ✅ No red "overflow" warnings in PowerPoint

**Visual Example:**
```
┌─────────────────────────────────────┐
│ Herramientas de Estimación: DBU     │ ← Line 1 of title (32pt bold)
│ Estimator y Price Calculator        │ ← Line 2 of title (auto-wrapped)
│                                     │ ← Small gap (0.1")
│ Costo Total (20pt, steel blue)      │ ← Subtitle (positioned below title)
│                                     │ ← Small gap (0.15")
│ • Este es un elemento de contenido  │ ← Content starts here
│ • Con bullets alineados correctamente│
│                                     │
└─────────────────────────────────────┘
```

**How to Verify in PowerPoint:**
1. Open generated PPT
2. Look for slide with long title
3. Check that:
   - Title is fully visible (not cut off)
   - Subtitle doesn't overlap title
   - Content flows below subtitle
   - No red border warnings

---

### Fix #2: Content Overflow Detection ✅

**Test Scenario:**
Generate a slide with lots of content (many bullets + callout)

**Expected Behavior:**
- ✅ Check CloudWatch logs in Lambda
- ✅ Look for these log patterns:

```
✅ Content fits safely: 5.2" / 7.2" (safety margin: 2.0")
```
OR
```
⚠️ OVERFLOW DETECTED: Content extends 0.5" beyond safe zone
   Text box ends at: 7.7" (max safe: 7.2", slide height: 7.5")
   💡 RECOMMENDATION: Split content across multiple slides or reduce bullet count
```

**What Changed:**
- Before: Vague warnings about "0.1" overflow"
- After: Specific measurements + actionable recommendations

**CloudWatch Log Location:**
```
AWS Lambda → Functions → StrandsInfographicGenerator → Monitor → Logs
Search for: "OVERFLOW DETECTED" or "Content fits safely"
```

---

### Fix #3: Continuation Slide Preparation ✅

**Test Scenario:**
Generate a course with moderately long lessons

**Expected Behavior:**
- ✅ Continuation slides are created (if needed)
- ✅ Overflow detection warns about content needing splits
- ✅ (Future) Continuation slides will have content split intelligently

**How to Verify:**
1. Check CloudWatch logs for overflow warnings
2. Count slides generated
3. Look for `(cont. 1)`, `(cont. 2)` in slide titles
4. Verify they have body content (don't expect full fix yet)

---

## Technical Details for Developers

### Key Function Changes

**Function 1: `_set_slide_title()`**
```python
# Returns: title_height (float in inches)
title_height = _set_slide_title(slide, title, colors)
# Before: returned nothing
# After: returns actual height needed (0.7" - 1.5" range)
```

**Function 2: `_set_slide_subtitle()`**
```python
# Changed signature:
# Before: _set_slide_subtitle(slide, subtitle, colors)
# After: _set_slide_subtitle(slide, subtitle, colors, title_height=0.7)

# Returns: total_height (float in inches)
subtitle_height = _set_slide_subtitle(slide, subtitle, colors, title_height)
# Before: returned subtitle_height only
# After: returns (subtitle_height + subtitle_top - 0.5)
#        = total height from 0.5" top to bottom of subtitle
```

**Function 3: `_add_content_blocks()`**
```python
# Now uses returned heights correctly:
_add_content_blocks(slide, content_blocks, colors, 
                    has_images=False, subtitle_height=subtitle_height)
# subtitle_height now represents actual total height from top
# Not just the subtitle box height
```

### Measurement System

**Slide Dimensions:**
- Width: 13.333" (16:9 aspect ratio)
- Height: 7.5"

**Default Positions (New):**
- Title top: 0.5"
- Title height: 0.7" (minimum) to 1.5" (maximum)
- Subtitle top: 0.5" + title_height + 0.1" gap
- Subtitle height: 0.5" (minimum) to 0.9" (typical with 2 lines)
- Content top: subtitle_bottom + 0.15" gap
- Content max bottom: 7.5" - 0.3" (safety margin) = 7.2"

---

## Troubleshooting

### Problem: Title still overlaps subtitle

**Diagnosis:**
1. Check if `_set_slide_subtitle()` is being called with `title_height` parameter
2. Verify `_set_slide_title()` is returning the height
3. Check CloudWatch logs for actual measurements

**Solution:**
```python
# Make sure this is being called:
title_height = _set_slide_title(slide, title_data['title'], colors)
if slide_data.get('subtitle'):
    subtitle_height = _set_slide_subtitle(
        slide, 
        slide_data['subtitle'], 
        colors, 
        title_height=title_height  # ← This parameter must be passed!
    )
```

### Problem: Content position still wrong

**Diagnosis:**
- Check the value of `subtitle_height` returned
- Verify it's being passed to `_add_content_blocks()`

**Solution:**
```python
# Verify the flow:
logger.info(f"Title height returned: {title_height}")
logger.info(f"Subtitle height returned: {subtitle_height}")
logger.info(f"Content box top: {content_top}")
```

---

## Regression Testing Checklist

After deploying the fixes, verify:

- [ ] Short titles (1 line) still work correctly
- [ ] Long titles (2-3 lines) don't overflow
- [ ] Slides without subtitles calculate content position correctly
- [ ] Slides with subtitles align properly
- [ ] Overflow warnings show accurate measurements
- [ ] Content doesn't exceed 7.2" (safe zone)
- [ ] Footer/logo not overlapped by content
- [ ] Callouts positioned correctly below bullets

---

## Performance Impact

**None** - All changes are:
- ✅ Local calculations (no external API calls)
- ✅ Mathematical computations (text length measuring)
- ✅ Same number of PPT operations

**Logging Impact:**
- +2-3 additional log lines per slide (for debugging)
- Can be reduced in production if needed

---

## Related Files Not Modified

These files may need updates in future improvements (Phase 2):

1. `/CG-Backend/lambda/strands_infographic_generator/infographic_generator.py`
   - AI prompt for content generation (already warns about content limits)
   - Continuation slide creation logic (doesn't distribute content yet)

2. `/CG-Backend/lambda/ppt_batch_orchestrator/ppt_batch_orchestrator.py`
   - May need retry logic if content is too long

3. `/CG-Backend/lambda/images_gen/images_gen.py`
   - Image sizing might interact with content positioning

---

## Support

For issues or questions about these fixes:

1. Check CloudWatch logs for detailed measurements
2. Enable debug logging to see all calculations
3. Test with simple cases first (1 title line, no subtitle)
4. Then test complex cases (multi-line title + long subtitle + many bullets)
