# PPT Batch Orchestration - Deployment Checklist

## Pre-Deployment Verification

- [ ] AWS CLI installed and configured
- [ ] AWS credentials have proper permissions
- [ ] Target AWS region: `us-east-1`
- [ ] Existing S3 bucket: `crewai-course-artifacts` exists
- [ ] Existing IAM roles:
  - [ ] `LambdaExecutionRole` (for Lambda functions)
  - [ ] `StepFunctionsExecutionRole` (for Step Functions)
- [ ] Existing Lambda Layer: `PPTLayer` (for python-pptx dependencies)
- [ ] Existing Lambda: `StrandsInfographicGenerator` (already deployed)
- [ ] Read access to: `/home/juan/AuroraV1/CG-Backend` directory

## Deployment Steps

### Step 1: Prepare Environment

```bash
cd /home/juan/AuroraV1/CG-Backend
ls -la deploy-ppt-orchestration.sh
```

- [ ] Script exists and is executable
- [ ] All source files present:
  - [ ] `lambda/ppt_batch_orchestrator/ppt_batch_orchestrator.py`
  - [ ] `lambda/ppt_merger/ppt_merger.py`
  - [ ] `ppt_batch_orchestrator_state_machine.json`

### Step 2: Execute Deployment Script

```bash
./deploy-ppt-orchestration.sh
```

Expected output:
- [ ] "Deploying PptBatchOrchestrator Lambda..."
- [ ] "✓ PptBatchOrchestrator deployed"
- [ ] "Deploying StrandsPptMerger Lambda..."
- [ ] "✓ StrandsPptMerger deployed"
- [ ] "Creating/Updating Step Functions State Machine..."
- [ ] "✓ State machine created/updated"
- [ ] Deployment summary with next steps

### Step 3: Verify Deployments

#### Verify PptBatchOrchestrator Lambda

```bash
aws lambda get-function --function-name PptBatchOrchestrator --region us-east-1
```

- [ ] Function exists
- [ ] Runtime: python3.12
- [ ] Handler: ppt_batch_orchestrator.lambda_handler
- [ ] Timeout: 60 seconds
- [ ] Memory: 512 MB
- [ ] Environment variables set correctly

#### Verify StrandsPptMerger Lambda

```bash
aws lambda get-function --function-name StrandsPptMerger --region us-east-1
```

- [ ] Function exists
- [ ] Runtime: python3.12
- [ ] Handler: ppt_merger.lambda_handler
- [ ] Timeout: 600 seconds
- [ ] Memory: 1024 MB
- [ ] Layer attached: PPTLayer

#### Verify Step Functions State Machine

```bash
aws stepfunctions list-state-machines --region us-east-1 | grep PptBatchOrchestrator
```

- [ ] State machine "PptBatchOrchestrator" exists
- [ ] Get the state machine ARN:

```bash
STATEMACHINE_ARN=$(aws stepfunctions list-state-machines \
  --region us-east-1 \
  --query "stateMachines[?name=='PptBatchOrchestrator'].stateMachineArn" \
  --output text)
echo $STATEMACHINE_ARN
```

- [ ] ARN is valid (starts with `arn:aws:states:`)

## Testing Phase

### Test 1: Validate Lambdas (5 minutes)

#### Test PptBatchOrchestrator

```bash
aws lambda invoke \
  --function-name PptBatchOrchestrator \
  --payload '{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "test-course-small",
    "auto_combine": false
  }' \
  --region us-east-1 \
  test_response.json

cat test_response.json | jq .
```

Expected response:
- [ ] `statusCode: 202` (Accepted)
- [ ] `execution_arn` present
- [ ] `total_lessons` > 0
- [ ] `total_batches` calculated
- [ ] No errors in response

Check logs:
```bash
aws logs tail /aws/lambda/PptBatchOrchestrator --since 5m --region us-east-1
```

- [ ] No ERROR messages in logs
- [ ] State machine execution started message visible

### Test 2: Run Small Course (15 minutes)

Use a course with 3-6 lessons for quick validation.

```bash
aws lambda invoke \
  --function-name PptBatchOrchestrator \
  --payload '{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "test-small-course",
    "auto_combine": true
  }' \
  --region us-east-1 \
  small_test.json

cat small_test.json | jq -r '.execution_arn' | tee execution_arn.txt
```

Monitor execution:

```bash
EXEC_ARN=$(cat execution_arn.txt)

# Check status periodically (every 30 seconds)
watch -n 30 "aws stepfunctions describe-execution --execution-arn $EXEC_ARN --region us-east-1 | jq '.status'"
```

Expected progression:
- [ ] Initial status: `RUNNING`
- [ ] Eventually: `SUCCEEDED`
- [ ] Time: ~13-15 minutes

Watch logs in real-time:
```bash
aws logs tail /aws/stepfunctions/PptBatchOrchestrator --follow --region us-east-1
```

- [ ] No FAILED states
- [ ] Batch processing stages visible
- [ ] Merger stage appears
- [ ] No ERROR messages

Verify S3 output:
```bash
aws s3 ls s3://crewai-course-artifacts/test-small-course/infographics/ --recursive
```

- [ ] `infographic_structure.json` present (partial or complete)
- [ ] Final PPT file present (if `auto_combine: true`)
- [ ] File sizes reasonable (>1 MB for PPT)

### Test 3: Run Large Course (30 minutes)

Test with your actual 16-lesson course.

```bash
aws lambda invoke \
  --function-name PptBatchOrchestrator \
  --payload '{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "251031-databricks-ciencia-datos",
    "auto_combine": true
  }' \
  --region us-east-1 \
  large_test.json

cat large_test.json | jq -r '.execution_arn' | tee large_execution_arn.txt
```

Monitor execution (same as test 2, but longer):

```bash
EXEC_ARN=$(cat large_execution_arn.txt)
aws stepfunctions describe-execution --execution-arn $EXEC_ARN --region us-east-1 | jq .
```

- [ ] Execution starts successfully
- [ ] Status transitions through stages
- [ ] Final status: `SUCCEEDED` after ~30 minutes
- [ ] No `FAILED` status at any point

Verify full workflow:
```bash
# Get execution history
aws stepfunctions get-execution-history --execution-arn $EXEC_ARN --region us-east-1 | jq '.events[] | select(.type=="TaskStateExited") | .taskStateExitedEventDetails'
```

- [ ] Multiple `TaskStateExited` events visible
- [ ] Indicates multiple batches processed
- [ ] Merger task completed successfully

Verify S3 outputs:
```bash
aws s3 ls s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/ --recursive --human-readable
```

Expected files:
- [ ] `infographic_structure.json` (batch structure)
- [ ] `infographic.html` (visual preview)
- [ ] `*-complete.pptx` (final merged PPT)

Check PPT quality:
```bash
# Download and verify
aws s3 cp s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/251031-databricks-ciencia-datos-complete.pptx ./final_ppt.pptx

# Verify file
file final_ppt.pptx
ls -lh final_ppt.pptx
```

- [ ] File exists and has content (>5 MB for 16-lesson course)
- [ ] File type: Microsoft PowerPoint presentation

## Monitoring Setup

### CloudWatch Logs

Create log groups monitor:
```bash
# Check if log groups exist
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/PptBatch --region us-east-1
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/StrandsPptMerger --region us-east-1
```

- [ ] `/aws/lambda/PptBatchOrchestrator` exists
- [ ] `/aws/lambda/StrandsPptMerger` exists
- [ ] `/aws/lambda/StrandsInfographicGenerator` exists (from previous)

### CloudWatch Alarms (Optional but Recommended)

```bash
# Create alarm for Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name PptBatchOrchestrator-Errors \
  --alarm-description "Alert when PptBatchOrchestrator Lambda errors increase" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=FunctionName,Value=PptBatchOrchestrator \
  --region us-east-1
```

- [ ] Alarm created successfully

## Documentation Review

- [ ] Read: `PPT_PRODUCTION_READY.md`
- [ ] Read: `PPT_QUICK_REFERENCE.md`
- [ ] Reference: `PPT_ORCHESTRATION_GUIDE.md` (bookmark for later)
- [ ] Reference: `PPT_ARCHITECTURE_DIAGRAMS.md` (bookmark for later)
- [ ] Read: `IMPLEMENTATION_SUMMARY.md`

## IAM Permissions Audit

Verify the Lambda execution role has correct permissions:

```bash
LAMBDA_ROLE_ARN="arn:aws:iam::746434296869:role/LambdaExecutionRole"

aws iam get-role-policy --role-name LambdaExecutionRole --policy-name s3-access 2>/dev/null || \
aws iam get-role-policy --role-name LambdaExecutionRole --policy-name s3-crewai-access 2>/dev/null || \
echo "Check role policies manually"
```

Required permissions (should be present):
- [ ] S3 GetObject on crewai-course-artifacts
- [ ] S3 PutObject on crewai-course-artifacts
- [ ] States StartExecution on PptBatchOrchestrator state machine
- [ ] Lambda InvokeFunction on StrandsInfographicGenerator
- [ ] Lambda InvokeFunction on StrandsPptMerger

If missing, ask DevOps team to add permissions.

## Troubleshooting Tests

### Test: What happens if bucket doesn't exist?

```bash
aws lambda invoke \
  --function-name PptBatchOrchestrator \
  --payload '{
    "course_bucket": "nonexistent-bucket",
    "project_folder": "test"
  }' \
  --region us-east-1 \
  error_test.json

cat error_test.json
```

- [ ] Returns error gracefully
- [ ] Status code: 400 (bad request) or 500 (server error)
- [ ] Error message is descriptive

### Test: What happens if course_bucket parameter is missing?

```bash
aws lambda invoke \
  --function-name PptBatchOrchestrator \
  --payload '{
    "project_folder": "test"
  }' \
  --region us-east-1 \
  error_test2.json

cat error_test2.json
```

- [ ] Returns validation error
- [ ] Message indicates missing parameter
- [ ] Status code: 400

## Team Training

- [ ] Send documentation files to team
- [ ] Explain the 5 key documents:
  1. PPT_PRODUCTION_READY.md - Overview
  2. PPT_QUICK_REFERENCE.md - Daily reference
  3. PPT_ORCHESTRATION_GUIDE.md - Deep dive
  4. PPT_ARCHITECTURE_DIAGRAMS.md - Visual reference
  5. IMPLEMENTATION_SUMMARY.md - How it was built

- [ ] Demo the workflow to team
- [ ] Show how to monitor via CloudWatch
- [ ] Show how to troubleshoot

## Performance Baseline

Record baseline performance:

```bash
echo "Recording baseline performance at: $(date)" | tee performance_baseline.txt

# Note execution time for small course
time aws lambda invoke --function-name PptBatchOrchestrator ... >> performance_baseline.txt

# Note execution time for large course (will take 30 min)
# time aws lambda invoke --function-name PptBatchOrchestrator ... >> performance_baseline.txt
```

- [ ] Small course time recorded
- [ ] Large course time recorded (if already done)
- [ ] Baseline file saved for comparison

## Sign-Off

- [ ] All deployment steps completed
- [ ] All verification tests passed
- [ ] Team trained and documented
- [ ] Baseline performance recorded
- [ ] Ready for production use

**Deployment Completed By:** _________________ 
**Date:** _________________ 
**Approved By:** _________________ 

---

## Post-Deployment

### Monitor for One Week

- [ ] Check CloudWatch logs daily
- [ ] Monitor Lambda metrics
- [ ] Track execution times
- [ ] Gather any errors/issues

### Optimization (If Needed)

- [ ] Analyze execution times
- [ ] Adjust batch size if needed
- [ ] Tune concurrency if needed
- [ ] Document optimizations

### Scale to Production

- [ ] Add API Gateway endpoint
- [ ] Integrate with frontend
- [ ] Document for users
- [ ] Launch to production

---

**Congratulations! Your PPT batch orchestration system is now deployed and tested! 🎉**
