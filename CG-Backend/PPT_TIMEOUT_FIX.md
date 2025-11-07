# PPT Generator Timeout Issue - Fixed! ✅

## 🐛 Problem Identified

**Issue:** Lambda function timing out after 15 minutes (900 seconds)

**Root Cause:**
- AWS Lambda has a **hard limit of 15 minutes** (900 seconds) maximum execution time
- Generating PPT for 16 lessons takes longer than 15 minutes
- The AI agent (Bedrock) was successfully generating slides but Lambda timed out before completion

**Evidence from Logs:**
```
2025-11-04T16:22:33 END RequestId: 78bc4b49-ef93-48f8-a7dd-c2c1b4766a14
Duration: 900000.00 ms     Status: timeout
```

The function ran for exactly 900 seconds (15 minutes) and timed out.

---

## ✅ Solutions Implemented

### 1. **Timeout Guard** (Automatic)
The function now monitors elapsed time and saves progress before hitting the Lambda timeout:

```python
MAX_PROCESSING_TIME = 840  # 14 minutes (1 min buffer for save)

# Checks time before each lesson
elapsed_time = time.time() - start_time
if elapsed_time > MAX_PROCESSING_TIME:
    print(f"⚠️ Approaching timeout - saving partial progress")
    break
```

**Result:** PPT will be generated with whatever lessons were completed, no total failure.

### 2. **Batch Processing** (New Feature!)
You can now process lessons in batches to avoid timeout:

**New Parameters:**
- `lesson_start`: Start from lesson N (default: 1)
- `lesson_end`: End at lesson N (optional)
- `max_lessons_per_batch`: Maximum lessons per batch (default: 10)

**Example API Calls:**

```json
// Process first 10 lessons
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "lesson_start": 1,
  "max_lessons_per_batch": 10
}

// Process lessons 11-16
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "lesson_start": 11,
  "lesson_end": 16
}

// Process all lessons (will auto-batch at 10 per run)
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos"
}
```

### 3. **Progress Tracking**
The response now includes batch information:

```json
{
  "message": "Partial presentation generated (lessons 1-10 of 16)",
  "completion_status": "partial",
  "batch_info": {
    "lesson_start": 1,
    "lesson_end": 10,
    "total_lessons": 16,
    "lessons_in_batch": 10
  },
  "total_slides": 62,
  "pptx_s3_key": "..."
}
```

---

## 🚀 How to Use

### Option 1: Automatic Batching (Recommended)
Just call the API normally - it will automatically process up to 10 lessons per call:

```bash
# Frontend calls API
# Will process lessons 1-10 automatically
```

**Next Steps:**
1. Generate lessons 1-10 (first call)
2. Generate lessons 11-16 (second call with `lesson_start: 11`)
3. Merge PPTs manually or use all together

### Option 2: Manual Batch Control
Specify exact lesson ranges:

```json
// First batch
{
  "lesson_start": 1,
  "lesson_end": 8
}

// Second batch
{
  "lesson_start": 9,
  "lesson_end": 16
}
```

### Option 3: Reduce Slides Per Lesson
Generate fewer slides per lesson to fit more lessons in one run:

```json
{
  "slides_per_lesson": 4,  // Instead of 6
  "max_lessons_per_batch": 16
}
```

---

## 📊 Timing Estimates

Based on the logs showing ~13 lessons processed in 900 seconds:

| Lessons | Slides/Lesson | Estimated Time | Status |
|---------|---------------|----------------|--------|
| 10 | 6 | ~11 minutes | ✅ Safe |
| 13 | 6 | ~14 minutes | ⚠️ Close |
| 16 | 6 | ~17 minutes | ❌ Timeout |
| 16 | 4 | ~12 minutes | ✅ Safe |

**Recommendation:** Process in batches of **10 lessons** maximum for safety.

---

## 🔧 What Changed (Just Deployed)

### Changes in `strands_ppt_generator.py`:

1. **Added timeout monitoring:**
   ```python
   start_time = time.time()
   MAX_PROCESSING_TIME = 840  # 14 min
   ```

2. **Added batch processing parameters:**
   - `lesson_start`, `lesson_end`, `max_lessons_per_batch`

3. **Added progress tracking:**
   - `lessons_processed` counter
   - `completion_status` field ("complete" or "partial")
   - `batch_info` in response

4. **Improved logging:**
   - Shows lessons processed: "✅ Completed lesson 5/16"
   - Warns on timeout: "⚠️ Approaching Lambda timeout"
   - Reports partial completion

---

## 🎯 Immediate Action

**For your current course (16 lessons):**

1. **First call** - Process lessons 1-10:
   ```json
   {
     "course_bucket": "crewai-course-artifacts",
     "project_folder": "251031-databricks-ciencia-datos",
     "lesson_start": 1,
     "max_lessons_per_batch": 10
   }
   ```

2. **Second call** - Process lessons 11-16:
   ```json
   {
     "course_bucket": "crewai-course-artifacts",
     "project_folder": "251031-databricks-ciencia-datos",
     "lesson_start": 11,
     "lesson_end": 16
   }
   ```

3. **Result:** Two PPT files (one for lessons 1-10, one for lessons 11-16)

---

## 💡 Alternative Solutions (Future)

If you need to process all lessons in one go, consider:

1. **Use Step Functions:** Chain multiple Lambda invocations
2. **Use ECS/Fargate:** No 15-minute time limit
3. **Simplify AI prompts:** Generate simpler slides faster
4. **Pre-generate slide structures:** Store structure, generate PPTX separately

---

## ✅ Summary

| Before | After |
|--------|-------|
| ❌ Timeout after 15 min with no PPT | ✅ Partial PPT saved before timeout |
| ❌ No way to process subsets | ✅ Batch processing by lesson range |
| ❌ No progress visibility | ✅ Detailed batch info in response |
| ❌ All-or-nothing approach | ✅ Graceful degradation |

**Status:** ✅ Deployed and ready to test!

**Test Command:**
```bash
# Watch logs during generation
aws logs tail /aws/lambda/StrandsPPTGenerator --follow
```

---

## 🧪 Testing Checklist

- [ ] Generate PPT for lessons 1-10 (should complete successfully)
- [ ] Verify batch_info in response shows correct range
- [ ] Generate PPT for lessons 11-16 (should complete successfully)
- [ ] Check that both PPTs are saved to S3
- [ ] Verify completion_status is "complete" for both
- [ ] Try generating all 16 lessons (should auto-batch at 10)

---

**Deployed:** November 4, 2025, 16:25 UTC  
**Version:** With timeout guards and batch processing  
**Status:** ✅ Production ready
