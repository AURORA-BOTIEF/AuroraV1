# PPT Generation Cleanup Plan
**Date**: November 21, 2025  
**Context**: HTML-First architecture deprecation - PPT is now OPTIONAL

---

## Overview

With the HTML-First architecture, **HTML is the primary production output**. PowerPoint (PPTX) generation is now **optional** for backward compatibility or specific use cases.

This cleanup removes:
1. ❌ **Legacy PPT generators** (not used)
2. ❌ **Test files for deprecated features**
3. ❌ **Duplicate HTML→PPT converters**
4. ✅ **Keep merger** (still used for HTML generation from batches)

---

## Files to DELETE (Safe to Remove)

### 1. Legacy PPT Generator Lambda (Deprecated - Not Used)
```
CG-Backend/lambda/strands_ppt_generator/
├── strands_ppt_generator.py          # OLD generator - replaced by html_to_ppt_converter
├── requirements.txt
└── tests/
    ├── test_placeholder_integration.py
    └── test_overlap_detection.py
```
**Reason**: This was the original PPT generator. Replaced by `html_to_ppt_converter.py` in ppt_merger.

### 2. Duplicate HTML→PPT Converter
```
CG-Backend/lambda/strands_infographic_generator/html_to_ppt_converter.py
```
**Reason**: Duplicate of `ppt_merger/html_to_ppt_converter.py`. Already commented out in imports (line 40).

### 3. Test Files for Deprecated Features
```
CG-Backend/test_ppt_mixed_images.py
CG-Backend/test_html_to_ppt.py
CG-Backend/test_ppt_layout.py
CG-Backend/tests/test_ppt_image_slides.py
CG-Backend/tests/test_ppt_merger.py
/home/juan/AuroraV1/tests/test_integration_pptx.py
/home/juan/AuroraV1/tests/test_ppt_integration_smoke.py
```
**Reason**: These test the legacy JSON→PPT pipeline which is deprecated.

---

## Files to KEEP (Still Used)

### 1. PPT Merger Lambda ✅
```
CG-Backend/lambda/ppt_merger/
├── ppt_merger.py                  # KEEP - Merges batch HTML + optional PPT conversion
├── html_generator.py              # KEEP - Generates final HTML from structure
├── html_to_ppt_converter.py       # KEEP - Optional HTML→PPT conversion
├── mark_overflow_slides.py        # KEEP - HTML overflow detection
└── requirements.txt               # KEEP
```
**Reason**: 
- **Primary purpose**: Merges batch HTML files into final HTML ✅ (HTML-First needs this)
- **Secondary purpose**: Optional PPT conversion for users who want PPTX
- Used in state machine for batch processing

### 2. PPT Batch Orchestrator ✅
```
CG-Backend/lambda/ppt_batch_orchestrator/
└── ppt_batch_orchestrator.py      # KEEP - Orchestrates batch workflow
```
**Reason**: Controls batch processing workflow (HTML generation + optional PPT merge)

---

## Cleanup Actions

### Step 1: Remove Legacy PPT Generator
```bash
rm -rf /home/juan/AuroraV1/CG-Backend/lambda/strands_ppt_generator/
```
**Impact**: None - Not referenced in state machine or template

### Step 2: Remove Duplicate Converter
```bash
rm /home/juan/AuroraV1/CG-Backend/lambda/strands_infographic_generator/html_to_ppt_converter.py
```
**Impact**: None - Already commented out (line 40 of infographic_generator.py)

### Step 3: Remove Test Files
```bash
rm /home/juan/AuroraV1/CG-Backend/test_ppt_mixed_images.py
rm /home/juan/AuroraV1/CG-Backend/test_html_to_ppt.py
rm /home/juan/AuroraV1/CG-Backend/test_ppt_layout.py
rm /home/juan/AuroraV1/CG-Backend/tests/test_ppt_image_slides.py
rm /home/juan/AuroraV1/CG-Backend/tests/test_ppt_merger.py
rm /home/juan/AuroraV1/tests/test_integration_pptx.py
rm /home/juan/AuroraV1/tests/test_ppt_integration_smoke.py
```
**Impact**: None - Testing deprecated features

### Step 4: Clean Commented Import
```python
# In infographic_generator.py line 40:
# REMOVE: # from html_to_ppt_converter import convert_html_to_pptx_new
```
**Impact**: Clean code - import was already commented

---

## Architecture After Cleanup

### HTML-First Workflow (Production)
```
User Request
    ↓
StrandsInfographicGenerator (HTML-First mode)
    ↓ generates HTML slides directly
    ↓ saves to S3: project/infographics/infographic_structure.json
    ↓ saves to S3: project/infographics/batch_N.html (if batched)
    ↓
StrandsPptMerger (if batched)
    ↓ merges batch HTML files → final HTML
    ↓ saves to S3: project/infographics/final.html
    ↓ (OPTIONAL) converts HTML → PPT
    ↓ saves to S3: project/infographics/project.pptx (if requested)
    ↓
✅ Final Output: HTML (primary) + PPT (optional)
```

### PPT Generation (Optional Path)
If user explicitly requests PPT:
- `action: "merge_and_convert"` in ppt_merger
- HTML→PPT conversion via `html_to_ppt_converter.py`
- Uses python-pptx library

If user only needs HTML:
- `action: "merge_to_html"` in ppt_merger
- Skips PPT generation entirely

---

## Validation After Cleanup

### Before Cleanup
```bash
# Count PPT-related files
find CG-Backend -name "*ppt*" -type f | wc -l
# Result: ~15-20 files
```

### After Cleanup
```bash
# Count PPT-related files
find CG-Backend -name "*ppt*" -type f | wc -l
# Result: ~5 files (merger, orchestrator, converter only)
```

### Files Remaining
- `ppt_batch_orchestrator.py` - Batch workflow orchestration
- `ppt_merger.py` - HTML merge + optional PPT conversion
- `html_to_ppt_converter.py` - HTML→PPT converter (optional feature)
- `mark_overflow_slides.py` - HTML overflow detection
- State machine JSON files (configuration)

---

## Rollback Plan

If you need to restore deleted files:

```bash
# View deleted files in git history
git log --diff-filter=D --summary | grep -i ppt

# Restore specific file
git checkout <commit-hash> -- <file-path>

# Example:
git checkout HEAD~1 -- CG-Backend/lambda/strands_ppt_generator/
```

---

## Production Impact Assessment

### ✅ SAFE - No Production Impact
- Legacy PPT generator not used in current architecture
- Test files don't affect runtime
- Duplicate converter already commented out
- Merger still available for optional PPT generation

### ⚠️ What Changes
- Users can still get PPT files (via merger)
- But primary output is HTML (production-ready)
- Smaller codebase, easier maintenance
- Fewer dependencies in Lambda layers

---

## Recommendations

### Immediate Cleanup (Safe)
1. ✅ Remove `strands_ppt_generator/` (legacy generator)
2. ✅ Remove duplicate `html_to_ppt_converter.py` in infographic_generator
3. ✅ Remove test files for deprecated features
4. ✅ Clean commented imports

### Future Consideration (After Validation)
If HTML becomes the ONLY format used:
- Remove `ppt_merger/html_to_ppt_converter.py` (6-12 months)
- Remove python-pptx dependency from Lambda layer
- Simplify state machine (no PPT conversion step)

But for now, **KEEP merger** for:
- Batch HTML merging (required for HTML-First batches)
- Optional PPT conversion (backward compatibility)

---

## Summary

**Deleting**: 11 files (~2,000 lines of deprecated code)  
**Keeping**: PPT merger for HTML merge + optional conversion  
**Impact**: Zero (deprecated code only)  
**Next Step**: Execute cleanup commands above

Would you like me to proceed with the cleanup?
