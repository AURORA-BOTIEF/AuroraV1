# PPT Batch Orchestration - Production Deployment Guide

## Overview

This solution enables automatic generation of complete PowerPoint presentations for large courses by orchestrating multiple Lambda invocations through AWS Step Functions. It solves the 15-minute Lambda timeout limitation by:

1. **Batch Processing**: Splits large courses into manageable lesson batches (6 lessons per batch)
2. **Parallel Execution**: Processes 2 batches concurrently through Step Functions
3. **Automatic Continuation**: Each batch completes independently, avoiding timeouts
4. **Smart Merging**: Combines all batch PPTs into a single final presentation
5. **Cost Optimized**: Reduces per-batch processing time from 800+ seconds to optimize cost

## Architecture

```
┌─────────────────────────────────┐
│  PPT Batch Orchestrator         │
│  (Lambda Entry Point)           │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Step Functions State Machine   │
│  (PptBatchOrchestrator)         │
└──────────────┬──────────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
┌──────────────┐ ┌──────────────┐
│   Batch 1    │ │   Batch 2    │ (Parallel, Max=2)
│ Lessons 1-6  │ │ Lessons 7-12 │
└──────┬───────┘ └──────┬───────┘
       │                │
       ▼                ▼
┌──────────────┐ ┌──────────────┐
│ Infographic  │ │ Infographic  │
│ Generator    │ │ Generator    │
│ Lambda       │ │ Lambda       │
└──────┬───────┘ └──────┬───────┘
       │                │
       ▼                ▼
   PPT Batch 1     PPT Batch 2
   (147 slides)    (147 slides)
       │                │
       └────────┬───────┘
                ▼
        ┌──────────────────┐
        │   PPT Merger     │
        │   Lambda         │
        └────────┬─────────┘
                 ▼
        Final Combined PPT
        (294 slides total)
```

## Components

### 1. PPT Batch Orchestrator (`ppt_batch_orchestrator.py`)

**Purpose**: Entry point that:
- Loads the course book from S3
- Calculates lesson batches
- Creates Step Functions execution

**Input**:
```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "model_provider": "bedrock",
  "auto_combine": true
}
```

**Output**:
```json
{
  "statusCode": 202,
  "execution_arn": "arn:aws:states:us-east-1:746434296869:execution:...",
  "execution_name": "ppt-orchestration-...",
  "total_lessons": 16,
  "total_batches": 3,
  "batches": [
    {"batch_index": 0, "lesson_start": 1, "lesson_end": 6},
    {"batch_index": 1, "lesson_start": 7, "lesson_end": 12},
    {"batch_index": 2, "lesson_start": 13, "lesson_end": 16}
  ]
}
```

### 2. Step Functions State Machine (`ppt_batch_orchestrator_state_machine.json`)

**Purpose**: Orchestrates batch processing workflow

**Key Features**:
- Parallel batch processing (MaxConcurrency: 2)
- Automatic timeout handling (900s Lambda hard limit)
- PPT merging on completion
- Error handling and retries

**States**:
- `ValidateInput`: Verify parameters
- `ExpandPptBatches`: Prepare batch tasks
- `ProcessPptBatchesInParallel`: Execute batches concurrently
- `AggregateResults`: Combine results
- `CheckIfAutoComplete`: Route to merger if enabled
- `InvokePptMerger`: Merge all batches
- `PptOrchestrationComplete`: Success

### 3. Infographic Generator (Existing)

**Purpose**: Generates PPT for a single batch of lessons

**Supports**:
- `lesson_start`: Starting lesson number (1-based)
- `lesson_end`: Ending lesson number (inclusive)
- `max_lessons_per_batch`: Batch size
- Returns partial results on timeout

**Output S3 Keys**:
```
{project_folder}/infographics/infographic_structure.json (partial or complete)
{project_folder}/infographics/infographic.html
{project_folder}/infographics/{course_title}.pptx
```

### 4. PPT Merger (`ppt_merger.py`)

**Purpose**: Combines multiple PPT batch files into one

**Input**:
```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "ppt_batch_results": [
    {
      "ppt_s3_key": "251031-databricks-ciencia-datos/infographics/batch_1_lessons_1-6.pptx",
      "batch_index": 0,
      "lessons_count": 6
    }
  ]
}
```

**Output**:
```json
{
  "statusCode": 200,
  "ppt_s3_key": "251031-databricks-ciencia-datos/infographics/251031-databricks-ciencia-datos-complete.pptx",
  "total_slides": 294,
  "total_batches": 3
}
```

## Deployment Steps

### Step 1: Deploy Orchestrator Lambda

```bash
# Package the orchestrator
cd /home/juan/AuroraV1/CG-Backend/lambda/ppt_batch_orchestrator
zip -r function.zip ppt_batch_orchestrator.py

# Deploy (update existing or create new)
aws lambda create-function \
  --function-name PptBatchOrchestrator \
  --runtime python3.12 \
  --role arn:aws:iam::746434296869:role/LambdaExecutionRole \
  --handler ppt_batch_orchestrator.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 60 \
  --memory-size 512 \
  --region us-east-1

# Or update:
aws lambda update-function-code \
  --function-name PptBatchOrchestrator \
  --zip-file fileb://function.zip \
  --region us-east-1
```

### Step 2: Deploy PPT Merger Lambda

```bash
# Package the merger with dependencies
cd /home/juan/AuroraV1/CG-Backend/lambda/ppt_merger
pip install python-pptx -t .
zip -r function.zip ppt_merger.py python-pptx* PIL* lxml*

# Deploy
aws lambda create-function \
  --function-name StrandsPptMerger \
  --runtime python3.12 \
  --role arn:aws:iam::746434296869:role/LambdaExecutionRole \
  --handler ppt_merger.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 600 \
  --memory-size 1024 \
  --layers arn:aws:lambda:us-east-1:746434296869:layer:PPTLayer:1 \
  --region us-east-1
```

**Note**: Use existing PPTLayer which already has python-pptx

### Step 3: Create Step Functions State Machine

```bash
# Create or update state machine
aws stepfunctions create-state-machine \
  --name PptBatchOrchestrator \
  --definition file://ppt_batch_orchestrator_state_machine.json \
  --role-arn arn:aws:iam::746434296869:role/StepFunctionsExecutionRole \
  --region us-east-1
```

### Step 4: Configure IAM Permissions

Ensure the following permissions are in the Lambda execution role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::crewai-course-artifacts",
        "arn:aws:s3:::crewai-course-artifacts/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "states:StartExecution",
        "states:DescribeExecution"
      ],
      "Resource": "arn:aws:states:us-east-1:746434296869:stateMachine:PptBatchOrchestrator"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:us-east-1:746434296869:function:StrandsInfographicGenerator",
        "arn:aws:lambda:us-east-1:746434296869:function:StrandsPptMerger"
      ]
    }
  ]
}
```

## Usage Examples

### Example 1: Full Orchestration with Auto-Merge

```bash
# Trigger orchestrator
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

**Response**:
```json
{
  "statusCode": 202,
  "execution_arn": "arn:aws:states:us-east-1:746434296869:execution:PptBatchOrchestrator:ppt-orchestration-251031-databricks-ciencia-datos-20251113-205000",
  "total_batches": 3,
  "batches": [
    {"batch_index": 0, "lesson_start": 1, "lesson_end": 6},
    {"batch_index": 1, "lesson_start": 7, "lesson_end": 12},
    {"batch_index": 2, "lesson_start": 13, "lesson_end": 16}
  ]
}
```

### Example 2: Check Execution Status

```bash
aws stepfunctions describe-execution \
  --execution-arn "arn:aws:states:us-east-1:746434296869:execution:PptBatchOrchestrator:ppt-orchestration-251031-databricks-ciencia-datos-20251113-205000" \
  --region us-east-1
```

### Example 3: Monitor Through CloudWatch

```bash
# Watch Step Functions execution
aws logs tail /aws/stepfunctions/PptBatchOrchestrator --follow --region us-east-1

# Watch Lambda execution
aws logs tail /aws/lambda/StrandsInfographicGenerator --follow --region us-east-1
```

## Performance Characteristics

### Batch Processing

| Metric | Value |
|--------|-------|
| Lessons per batch | 6 |
| Processing time per batch | ~780 seconds (13 min) |
| Lambda timeout buffer | 120 seconds |
| Max concurrent batches | 2 |
| Total execution time (16 lessons) | ~7-8 minutes (2 batches parallel) |

### Example: 16-Lesson Course

- **Batch 1** (Lessons 1-6): Starts at 0:00, completes at 13:00
- **Batch 2** (Lessons 7-12): Starts at 0:00, completes at 13:00
- **Batch 3** (Lessons 13-16): Starts at 13:00, completes at 13:00
- **Merge**: Starts at 13:30, completes at 13:35
- **Total time**: ~14 minutes (including waiting and merge)

### Cost Optimization

- **Batch processing**: Multiple smaller invocations instead of one huge timeout
- **Parallel execution**: Reduces total wall-clock time
- **Selective merging**: Only merge if `auto_combine=true`
- **Lambda cost**: ~3-4 invocations per 16-lesson course instead of 1 failed + retries

## Monitoring & Troubleshooting

### Check Batch Progress

```bash
# List all S3 files generated
aws s3 ls s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/ --recursive

# Check infographic structure for completion status
aws s3 cp s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/infographic_structure.json - | python3 -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d.get('batch_info', {}), indent=2))"
```

### Common Issues & Solutions

**Issue**: Batch timeout even with the default 3-lesson batch size

**Solution**: Reduce the batch size by lowering the `MAX_LESSONS_PER_BATCH` env var or pass `"batch_size"` to the orchestrator payload
```python
# In the Lambda environment or template.yaml
MAX_LESSONS_PER_BATCH = 3  # Lower to 2 (or 1) for particularly dense lessons
```

**Issue**: PPT merger fails with memory error

**Solution**: Increase Lambda memory for StrandsPptMerger to 2048 MB or reduce batch concurrency to 1

**Issue**: Step Functions execution times out

**Solution**: Check if individual batch lambda functions are timing out (check CloudWatch logs for warning timestamps)

## Advanced Configuration

### Custom Batch Sizes

Adjust the batch size limit in the Lambda's environment variables (template.yaml sets it to 3 by default) or override it per request:

```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "batch_size": 2
}
```

The orchestrator will cap `batch_size` at the configured `MAX_LESSONS_PER_BATCH` limit to ensure each invocation finishes within the 900s timeout. To permanently lower the limit, change the environment variable before deploying the stack.

### Conditional Merging

Pass `auto_combine: false` to generate batches without final merge:

```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "auto_combine": false
}
```

Later invoke merger manually:
```bash
aws lambda invoke \
  --function-name StrandsPptMerger \
  --payload '{...}' \
  response.json
```

## Production Checklist

- [ ] Deploy PptBatchOrchestrator Lambda
- [ ] Deploy StrandsPptMerger Lambda
- [ ] Create Step Functions state machine
- [ ] Test with small course (2-3 lessons)
- [ ] Test with medium course (8-10 lessons)
- [ ] Test with large course (16+ lessons)
- [ ] Verify S3 output for all batches
- [ ] Verify final merged PPT is correct
- [ ] Configure CloudWatch alarms
- [ ] Document API for frontend integration
- [ ] Train team on monitoring/troubleshooting

## Frontend Integration

### API Endpoint (via API Gateway)

```
POST /api/ppt-orchestration
Content-Type: application/json

{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251031-databricks-ciencia-datos",
  "auto_combine": true
}

Response 202 Accepted:
{
  "execution_arn": "...",
  "total_batches": 3,
  "estimated_time_seconds": 840
}
```

### Polling for Completion

```javascript
// Check execution status
async function checkPptStatus(executionArn) {
  const response = await fetch('/api/execution-status', {
    method: 'POST',
    body: JSON.stringify({ executionArn })
  });
  
  const status = await response.json();
  // status.status: 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  // status.output: {...} when SUCCEEDED
}
```

### S3 Direct Download

Once complete, PPT available at:
```
https://crewai-course-artifacts.s3.amazonaws.com/{project_folder}/infographics/{project_folder}-complete.pptx
```

## Next Steps

1. Deploy the three components (Orchestrator, Merger, State Machine)
2. Test with your Databricks course (16 lessons)
3. Monitor performance and adjust batch size if needed
4. Integrate with API Gateway for frontend access
5. Add CloudWatch dashboards for monitoring
6. Document for your team
