# Image Mapping Fix - BookBuilder
**Date:** October 22, 2025  
**Status:** ✅ **FIXED & DEPLOYED**

---

## Problem

When BookBuilder auto-discovered images for book generation, visual tags remained unreplaced in the final book instead of being converted to actual image references.

**Example Issue:**
```markdown
<!-- In generated book (WRONG): -->
[VISUAL: Diagrama de la arquitectura de memoria de Oracle mostrando SGA, PGA y sus componentes principales]

<!-- Expected (CORRECT): -->
![VISUAL: Diagrama...](https://crewai-course-artifacts.s3.amazonaws.com/251022-FJ-01/images/01-01-0001.png)
```

---

## Root Cause

The BookBuilder's auto-discovery logic was creating incorrect mappings:

**Old Logic (Lines 90-110):**
```python
# Scanned images folder and created mappings like:
visual_tag = f"[VISUAL: {img_id}]"  # e.g., "[VISUAL: 01-01-0001]"
image_mappings[visual_tag] = img_key
```

**Problem:** Lesson files contain visual tags with full descriptions like:
```markdown
[VISUAL: Diagrama de la arquitectura de memoria de Oracle mostrando SGA, PGA y sus componentes principales]
```

But the old logic created mappings for:
```python
"[VISUAL: 01-01-0001]"  # This doesn't match the description in lessons!
```

**Result:** No replacements happened because tags didn't match.

---

## Solution

Updated BookBuilder to scan the `prompts/` folder instead of `images/` folder:

**New Logic:**
1. Scan `{project_folder}/prompts/*.json` files
2. Each prompt JSON contains:
   ```json
   {
     "id": "01-01-0001",
     "description": "Diagrama de la arquitectura de memoria de Oracle...",
     "filename": "01-01-0001_abc123.png"
   }
   ```
3. Create mappings using the **description** field:
   ```python
   visual_tag = f"[VISUAL: {description}]"
   image_path = f"{project_folder}/images/{img_id}.png"
   image_mappings[visual_tag] = image_path
   ```

**Fallback:** If prompts folder doesn't exist or fails, falls back to old image-based mapping for backward compatibility.

---

## Implementation Details

**File Modified:** `/home/juan/AuroraV1/CG-Backend/lambda/book_builder.py`

**Changes:**
- Lines 90-110: Replaced image folder scanning with prompts folder scanning
- Added JSON parsing for each prompt file
- Extract `description` and `id` fields
- Build correct mappings from description → image path
- Added comprehensive logging for debugging
- Added fallback to image-based mapping if prompts unavailable

**Key Code:**
```python
if not image_mappings:
    print("No image_mappings provided, scanning prompts folder to reconstruct mappings...")
    prompts_prefix = f"{project_folder}/prompts/"
    
    prompts_response = s3_client.list_objects_v2(Bucket=course_bucket, Prefix=prompts_prefix)
    
    for prompt_obj in prompts_response['Contents']:
        if prompt_key.endswith('.json'):
            prompt_data = json.loads(prompt_response['Body'].read())
            description = prompt_data.get('description', '')
            img_id = prompt_data.get('id', '')
            
            if description and img_id:
                visual_tag = f"[VISUAL: {description}]"
                image_path = f"{project_folder}/images/{img_id}.png"
                image_mappings[visual_tag] = image_path
```

---

## Verification

**Test Project:** 251022-FJ-01 (Oracle Performance Tuning)

**Before Fix:**
- Visual tags remained unreplaced: 23 instances of `[VISUAL: description]`
- Images not displayed in book

**After Fix:**
- All 23 visual tags successfully replaced
- Images properly embedded as markdown references
- Verified with CloudWatch logs:
  ```
  ✅ Mapped: [VISUAL: Diagrama de la arquitectura de memoria de Oracle... -> 01-01-0001.png
  ✅ Mapped: [VISUAL: Tabla comparativa de los tres modos de gestión... -> 01-01-0002.png
  ...
  Created 23 image mappings from prompts folder
  ```

**Rebuilt Book:**
```bash
aws s3 cp s3://crewai-course-artifacts/251022-FJ-01/book/Fundamentos_Oracle_Performance_Tuning_complete.md
```

**Sample Output:**
```markdown
![VISUAL: Diagrama de la arquitectura de memoria de Oracle mostrando SGA, PGA y sus componentes principales](https://crewai-course-artifacts.s3.amazonaws.com/251022-FJ-01/images/01-01-0001.png)
```

---

## Deployment

**Build & Deploy:**
```bash
cd /home/juan/AuroraV1/CG-Backend
sam build
sam deploy --no-confirm-changeset
```

**Status:** ✅ Successfully deployed to AWS  
**Stack:** crewai-course-generator-stack  
**Function:** BookBuilder (crewai-course-generator-stack-BookBuilder-F8jUrBbphojQ)

---

## Testing Commands

**Invoke BookBuilder directly:**
```bash
aws lambda invoke \
  --region us-east-1 \
  --function-name crewai-course-generator-stack-BookBuilder-F8jUrBbphojQ \
  --cli-binary-format raw-in-base64-out \
  --payload '{"course_bucket":"crewai-course-artifacts","project_folder":"251022-FJ-01","book_title":"Your_Book_Title"}' \
  /tmp/bookbuilder-response.json

cat /tmp/bookbuilder-response.json | jq '.'
```

**Check logs:**
```bash
aws logs tail /aws/lambda/crewai-course-generator-stack-BookBuilder-F8jUrBbphojQ \
  --region us-east-1 \
  --since 5m \
  --format short
```

**Download generated book:**
```bash
aws s3 cp s3://crewai-course-artifacts/251022-FJ-01/book/Your_Book_Title_complete.md ./book.md

# Verify images are embedded:
grep '!\[' book.md | head -n 10
```

---

## Impact

**Before:** All auto-discovered books had unreplaced visual tags  
**After:** All books now properly embed images from prompts metadata

**Affected Features:**
- ✅ BookBuilder Lambda (standalone invocations)
- ✅ Step Functions book generation (theory-only mode)
- ✅ Step Functions book generation (both mode)
- ✅ Manual book rebuilds via Lambda invoke

**Backward Compatibility:**
- ✅ Books with explicit `image_mappings` payload still work
- ✅ Books without prompts folder fall back to image-based mapping
- ✅ No breaking changes to existing workflows

---

## Related Files

**Modified:**
- `/home/juan/AuroraV1/CG-Backend/lambda/book_builder.py` (lines 90-140)

**Tested:**
- Project: 251022-FJ-01
- Lessons: 2 lessons (module-1-lesson-1, module-1-lesson-2)
- Images: 23 images (01-01-0001.png through 01-02-0023.png)
- Prompts: 23 JSON files in prompts/ folder

---

## Commits

**Git History:**
```
f19245d - Fix: BookBuilder now scans prompts folder for correct image mappings
6738f8b - Add PPT generator layer + StrandsPPTGenerator; BookEditor UI/markdown fixes
```

**Branch:** testing  
**Remote:** other (https://github.com/AURORA-BOTIEF/AuroraV1.git)

---

## Next Steps

- ✅ Fix deployed and tested
- ✅ Changes committed and pushed to remote testing branch
- ✅ Book regenerated successfully with images embedded
- ⏳ User to verify in Book Editor frontend that images display correctly

---

**Status:** ✅ **COMPLETE**  
**Verified:** October 22, 2025, 22:40 UTC
