# PPT Batch Orchestration - Quick Reference

## What Problem Does This Solve?

AWS Lambda has a hard timeout limit of 15 minutes (900 seconds). Your infographic generator takes ~780 seconds to process 6 lessons, which works fine. But when you need to generate PPTs for 16+ lessons, a single Lambda invocation will timeout.

**Solution**: Automatically split large courses into 6-lesson batches, process them in parallel through Step Functions, and merge the results into one final PPT.

---

## High-Level Architecture

```
User Request → Orchestrator Lambda → Step Functions → Parallel Batch Processing → Merger → Final PPT
```

### Example: 16-Lesson Course

1. **Input**: Course with 16 lessons
2. **Orchestrator calculates**: 3 batches
   - Batch 1: Lessons 1-6
   - Batch 2: Lessons 7-12
   - Batch 3: Lessons 13-16
3. **Step Functions executes**:
   - Batch 1 & 2 run in parallel (0-13 minutes)
   - Batch 3 runs (13-26 minutes)
4. **Merger combines**: 3 PPT files → 1 final PPT (26-30 minutes)
5. **Output**: Single `.pptx` file in S3

---

## Components You Need to Deploy

### 1. **PptBatchOrchestrator** (Lambda)
- **File**: `lambda/ppt_batch_orchestrator/ppt_batch_orchestrator.py`
- **Purpose**: Entry point - calculates batches and starts Step Functions
- **Timeout**: 60 seconds
- **Memory**: 512 MB

### 2. **PptBatchOrchestrator** (Step Functions)
- **File**: `ppt_batch_orchestrator_state_machine.json`
- **Purpose**: Orchestrates batch processing workflow
- **Key Feature**: Parallel execution with max concurrency = 2

### 3. **StrandsPptMerger** (Lambda)
- **File**: `lambda/ppt_merger/ppt_merger.py`
- **Purpose**: Combines multiple PPT files into one
- **Dependencies**: `python-pptx` (use PPTLayer)
- **Timeout**: 600 seconds (10 minutes)
- **Memory**: 1024 MB

---

## Deployment (3 Commands)

### Option 1: Automated (Recommended)

```bash
cd /home/juan/AuroraV1/CG-Backend
./deploy-ppt-orchestration.sh
```

This deploys all 3 components automatically.

### Option 2: Manual

**Step 1: Deploy Orchestrator Lambda**
```bash
cd /home/juan/AuroraV1/CG-Backend/lambda/ppt_batch_orchestrator
zip -r function.zip ppt_batch_orchestrator.py

# Update existing function
aws lambda update-function-code \
  --function-name PptBatchOrchestrator \
  --zip-file fileb://function.zip
```

**Step 2: Deploy Merger Lambda**
```bash
cd /home/juan/AuroraV1/CG-Backend/lambda/ppt_merger
pip install python-pptx -t .
zip -r function.zip ppt_merger.py pptx* PIL* lxml*

aws lambda update-function-code \
  --function-name StrandsPptMerger \
  --zip-file fileb://function.zip
```

**Step 3: Create State Machine**
```bash
cd /home/juan/AuroraV1/CG-Backend
aws stepfunctions create-state-machine \
  --name PptBatchOrchestrator \
  --definition file://ppt_batch_orchestrator_state_machine.json \
  --role-arn arn:aws:iam::746434296869:role/StepFunctionsExecutionRole
```

---

## Usage

### Trigger PPT Generation

```bash
aws lambda invoke \
  --function-name PptBatchOrchestrator \
  --payload '{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "251031-databricks-ciencia-datos",
    "model_provider": "bedrock",
    "auto_combine": true
  }' \
  --region us-east-1 \
  response.json

cat response.json
```

### Response

```json
{
  "statusCode": 202,
  "execution_arn": "arn:aws:states:us-east-1:746434296869:execution:PptBatchOrchestrator:ppt-orchestration-...",
  "total_lessons": 16,
  "total_batches": 3,
  "batches": [
    {"batch_index": 0, "lesson_start": 1, "lesson_end": 6},
    {"batch_index": 1, "lesson_start": 7, "lesson_end": 12},
    {"batch_index": 2, "lesson_start": 13, "lesson_end": 16}
  ]
}
```

### Monitor Execution

```bash
# Check status
aws stepfunctions describe-execution \
  --execution-arn "arn:aws:states:us-east-1:746434296869:execution:PptBatchOrchestrator:ppt-orchestration-..." \
  --region us-east-1

# Watch logs
aws logs tail /aws/lambda/PptBatchOrchestrator --follow
aws logs tail /aws/lambda/StrandsInfographicGenerator --follow
aws logs tail /aws/lambda/StrandsPptMerger --follow
```

### Download Final PPT

Once execution completes:

```bash
# Find the merged PPT
aws s3 ls s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/ | grep complete

# Download
aws s3 cp s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/251031-databricks-ciencia-datos-complete.pptx . --region us-east-1
```

---

## Key Parameters

### PptBatchOrchestrator Input

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `course_bucket` | Yes | - | S3 bucket with course data |
| `project_folder` | Yes | - | Course folder name |
| `model_provider` | No | `bedrock` | AI model to use |
| `auto_combine` | No | `true` | Auto-merge PPTs at end |

### Tuning Parameters

**Tweak the upper limit via the `MAX_LESSONS_PER_BATCH` env var (default: 3 lessons per batch).**
Set it lower for denser lessons or include a `"batch_size"` key in the orchestration payload to shrink a single run.

```python
MAX_LESSONS_PER_BATCH = 3  # Env var in template.yaml; reduce to 2 or 1 for heavier slides
MAX_CONCURRENT_BATCHES = 2  # Parallel batches (caution: may hit Lambda limits)
```

---

## Troubleshooting

### Problem: Step Functions execution times out

**Solution 1**: Reduce batch size (env var or API override)
```python
# Set in template or decrease the request-level override
MAX_LESSONS_PER_BATCH = 3  # Lower to 2 if you still hit timeouts
```

Alternatively, specify a smaller batch for this invocation:
```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "batch_size": 2
}
```

**Solution 2**: Check individual Lambda logs
```bash
aws logs tail /aws/lambda/StrandsInfographicGenerator --grep "ERROR\|WARNING"
```

### Problem: PPT Merger fails with memory error

**Solution**: Increase merger Lambda memory
```bash
aws lambda update-function-configuration \
  --function-name StrandsPptMerger \
  --memory-size 2048 \
  --region us-east-1
```

### Problem: No final merged PPT created

**Solution**: Check if `auto_combine` is true
```bash
# Re-run with auto_combine explicitly set
aws lambda invoke \
  --function-name PptBatchOrchestrator \
  --payload '{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "251031-databricks-ciencia-datos",
    "auto_combine": true
  }' \
  response.json
```

---

## Expected Performance

### For a 16-Lesson Course

| Stage | Duration | Notes |
|-------|----------|-------|
| Batch 1 & 2 (parallel) | 13 minutes | Processes lessons 1-12 |
| Batch 3 | 13 minutes | Processes lessons 13-16 |
| Merger | 5 minutes | Combines 3 PPT files |
| **Total** | **~30 minutes** | With 2 batches running in parallel |

### Cost Comparison

**Before (Single Lambda)**:
- 1 Lambda invocation → Timeout → Fail
- Cost: ~$0.02 + retry overhead
- Result: ❌ Failure

**After (Batch Orchestration)**:
- 3 Lambda invocations for infographic generation (~$0.06)
- 1 Lambda invocation for orchestrator (~$0.002)
- 1 Lambda invocation for merger (~$0.01)
- 1 Step Functions execution (~$0.001)
- Total: ~$0.073
- Result: ✅ Complete PPT with all lessons

---

## Integration with API Gateway (Optional)

Create an API Gateway endpoint that triggers the orchestrator:

```javascript
// Frontend code
async function generateCoursePPT(courseId) {
  const response = await fetch('/api/generate-ppt', {
    method: 'POST',
    body: JSON.stringify({
      course_bucket: 'crewai-course-artifacts',
      project_folder: courseId,
      auto_combine: true
    })
  });
  
  const data = await response.json();
  console.log(`PPT generation started: ${data.execution_arn}`);
  
  // Poll for completion
  let completed = false;
  while (!completed) {
    const status = await fetch(`/api/execution-status?arn=${data.execution_arn}`).then(r => r.json());
    if (status.status === 'SUCCEEDED') {
      console.log(`PPT ready: ${status.ppt_url}`);
      completed = true;
    }
    await new Promise(r => setTimeout(r, 5000)); // Poll every 5 seconds
  }
}
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `lambda/ppt_batch_orchestrator/ppt_batch_orchestrator.py` | Orchestrator Lambda |
| `lambda/ppt_merger/ppt_merger.py` | Merger Lambda |
| `ppt_batch_orchestrator_state_machine.json` | Step Functions definition |
| `deploy-ppt-orchestration.sh` | Automated deployment script |
| `PPT_ORCHESTRATION_GUIDE.md` | Detailed documentation |

---

## Support & Next Steps

1. **Deploy**: Run the deployment script
2. **Test**: Try with a small course first
3. **Monitor**: Watch CloudWatch logs
4. **Adjust**: Tune batch size if needed
5. **Integrate**: Connect to API Gateway
6. **Scale**: Use for all your courses!

For detailed information, see: **PPT_ORCHESTRATION_GUIDE.md**
