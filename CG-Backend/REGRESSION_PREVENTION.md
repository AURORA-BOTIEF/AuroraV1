# Regression Prevention Strategy
**Created**: October 24, 2025  
**Purpose**: Prevent breaking changes when implementing new features

---

## 🚨 Recent Issues & Fixes

### Issue #1: StarterApi Missing Dependencies (Oct 24, 2025)
**Problem**: Lambda deployed without `pyyaml` dependency  
**Symptom**: `Runtime.ImportModuleError: No module named 'yaml'`  
**Impact**: ALL course generation failed with 500 errors  

**Root Cause**:
- SAM built the function but didn't include requirements.txt dependencies
- Lambda was deployed without proper build step

**Fix Applied**:
```bash
cd CG-Backend
sam build StarterApiFunction
# Create proper deployment package
cd .aws-sam/build/StarterApiFunction && zip -r /tmp/package.zip .
aws lambda update-function-code --function-name ... --zip-file fileb:///tmp/package.zip
```

**Prevention**:
- ✅ Always run `sam build` before deploying Lambda functions
- ✅ Check CloudWatch logs after deployment to verify function starts
- ✅ Test critical endpoints immediately after deployment

---

### Issue #2: Lab Planner Incompatible with Outline Format (Oct 24, 2025)
**Problem**: Lab Planner only looked for `labs` key, not `lab_activities`  
**Symptom**: "No lab activities found in the course outline" error  
**Impact**: Course generation failed even though labs were defined  

**Root Cause**:
- Lab Planner supported `labs` at module level
- Outline used `lab_activities` at module level
- Code only checked `module.get('labs', [])` - missed `lab_activities`

**Fix Applied**:
```python
# OLD (brittle):
module_labs = module.get('labs', [])

# NEW (flexible):
module_labs = module.get('labs', []) or module.get('lab_activities', [])
```

**Prevention**:
- ✅ Support multiple outline formats simultaneously
- ✅ Use flexible key lookups with fallbacks
- ✅ Test with multiple outline examples before deploying

---

### Issue #3: BatchExpander & LabBatchExpander Missing Dependencies (Oct 24, 2025)
**Problem**: Same as Issue #1 - Missing pyyaml dependency  
**Symptom**: `Unable to import module 'batch_expander': No module named 'yaml'`  
**Impact**: Course generation failed at batch expansion phase  

**Root Cause**: Same SAM deployment issue affecting multiple Lambda functions

**Fix Applied**: Same as Issue #1 - rebuilt with `sam build` and deployed

**Prevention**: See Issue #1 prevention strategies

---

### Issue #4: Step Functions Context Loss (Oct 24, 2025)
**Problem**: `CombineResultsAndBuildBook` state replaced entire execution context  
**Symptom**: `JSONPath '$.master_lab_plan_result.Payload.master_plan_key' could not be found`  
**Impact**: Lab generation failed in "both" mode after theory content was built  

**Root Cause**:
- `CombineResultsAndBuildBook` uses `Parameters` (not `ResultSelector`)
- `Parameters` **REPLACES** entire context instead of merging
- `master_lab_plan_result` was created early in workflow but lost before labs phase
- Flow: GenerateLabMasterPlan → Theory Generation → Book Building → Lab Generation
- Context was replaced between book building and lab generation

**Fix Applied**:
```yaml
# Added to CombineResultsAndBuildBook Parameters:
master_lab_plan_result.$: $.master_lab_plan_result
model_provider.$: $.model_provider
```

**Prevention**:
- ✅ When using `Parameters` in Step Functions, explicitly preserve ALL needed context
- ✅ Trace data flow through entire state machine, not just adjacent states
- ✅ Test "both" mode (theory + labs) which exercises full workflow
- ✅ Check execution history to see exact input/output at each state

**Deployment**: 2025-10-24 20:08:51 UTC (Commit: df7280c)

---

### Issue #5: SAM Deploy Overwrites Lambda Dependencies (Oct 24, 2025) ⚠️ CRITICAL
**Problem**: `sam deploy` re-uploads ALL Lambda functions, overwriting manually-deployed versions  
**Symptom**: Functions that were fixed and working suddenly break again with "No module named 'yaml'"  
**Impact**: **CATASTROPHIC** - Every template deployment breaks all Lambda functions with dependencies  

**Root Cause**:
- When you run `sam deploy`, SAM re-packages and uploads ALL Lambda functions defined in template.yaml
- This includes functions that were manually rebuilt with `sam build` and deployed with dependencies
- The template deployment uses the raw source code WITHOUT running `sam build` first
- Result: All manually-fixed functions are overwritten with dependency-less versions

**Timeline of Discovery**:
1. 18:43 UTC - Fixed StarterApi with dependencies ✅
2. 19:18 UTC - Fixed Lab Planner ✅
3. 19:31 UTC - Fixed BatchExpander ✅
4. 19:32 UTC - Fixed LabBatchExpander ✅
5. 20:08 UTC - Deployed template.yaml changes (Step Functions fix) ✅
6. 20:14 UTC - Frontend broke again! ❌
7. 20:14 UTC - Discovered StarterApi missing yaml module AGAIN ❌
8. Root cause: `sam deploy` at 20:08 overwrote ALL Lambda functions

**Fix Applied**:
Created `deploy-with-dependencies.sh` script that:
1. Deploys template changes first (`sam deploy`)
2. Then rebuilds and redeploys EACH function with dependencies
3. Uses `sam build <FunctionName>` to include requirements.txt
4. Manually deploys each function with `aws lambda update-function-code`

**The ONLY Safe Deployment Method**:
```bash
# From CG-Backend directory:
./deploy-with-dependencies.sh full
```

**Never Run These Commands Alone**:
```bash
sam deploy                    # ❌ BREAKS Lambda functions!
sam deploy --no-confirm      # ❌ BREAKS Lambda functions!
sam sync --stack-name ...    # ❌ BREAKS Lambda functions!
```

**Prevention**:
- ✅ ALWAYS use `deploy-with-dependencies.sh` script for ANY deployment
- ✅ Script is version-controlled and documented
- ✅ Script rebuilds: StarterApiFunction, StrandsLabPlanner, BatchExpander, LabBatchExpander
- ✅ Add new functions to script if they need external dependencies
- ⚠️  **MEMORIZE THIS**: Template changes = Must redeploy Lambda functions with deps

**Re-deployment**: 2025-10-24 20:19:12 UTC (StarterApi fixed again)

---

## 📋 Pre-Deployment Checklist

Before deploying ANY changes to AWS:

### 1. **Code Review Checklist**
- [ ] Does this change affect existing functionality?
- [ ] Are there multiple ways users might format their inputs?
- [ ] Have I tested with BOTH old and new data formats?
- [ ] Did I add error handling for missing/unexpected data?
- [ ] Are dependencies listed in `requirements.txt`?

### 2. **Testing Checklist**
- [ ] Test with **existing outline examples** (outline-example*.yaml)
- [ ] Test with **different content_type values** (theory, labs, both)
- [ ] Test with **different model providers** (bedrock, openai)
- [ ] Check CloudWatch logs after deployment
- [ ] Verify at least ONE end-to-end course generation

### 3. **Deployment Checklist**
- [ ] Run `sam build` if deploying Lambda functions
- [ ] Check package size (should include dependencies)
- [ ] Deploy to AWS
- [ ] Wait 30 seconds for function to be ready
- [ ] Test critical endpoints immediately
- [ ] Monitor CloudWatch logs for errors

### 4. **Rollback Plan**
- [ ] Document function ARN before deployment
- [ ] Keep previous deployment package as backup
- [ ] Know how to revert: `aws lambda update-function-code --function-name ... --zip-file fileb://backup.zip`

---

## 🛡️ Defensive Coding Patterns

### Pattern 1: Flexible Key Lookups
**Bad**:
```python
labs = module['labs']  # Breaks if key missing or named differently
```

**Good**:
```python
labs = module.get('labs', []) or module.get('lab_activities', [])
```

### Pattern 2: Graceful Degradation
**Bad**:
```python
if not labs:
    return {'statusCode': 400, 'error': 'No labs found'}  # Fails entire workflow
```

**Good**:
```python
if not labs:
    return {
        'statusCode': 200,  # Success
        'message': 'No labs found - skipping lab generation',
        'total_labs': 0
    }
```

### Pattern 3: Type-Safe Parsing
**Bad**:
```python
lab_title = lab['title']  # Assumes lab is dict
```

**Good**:
```python
if isinstance(lab, dict):
    lab_title = lab.get('title', 'Untitled')
else:
    lab_title = str(lab)  # Handle string format too
```

### Pattern 4: Comprehensive Error Context
**Bad**:
```python
except Exception as e:
    print(f"Error: {e}")
```

**Good**:
```python
except Exception as e:
    print(f"❌ Error in {function_name}:")
    print(f"   Input: {input_data}")
    print(f"   Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
```

---

## 📝 Outline Format Compatibility Matrix

The system MUST support all these formats:

### Format 1: Labs at Lesson Level
```yaml
modules:
  - title: "Module 1"
    lessons:
      - title: "Lesson 1"
        lab_activities:
          - title: "Lab 1"
            duration_minutes: 30
```

### Format 2: Labs at Module Level (labs key)
```yaml
modules:
  - title: "Module 1"
    lessons: [...]
    labs:
      - title: "Lab 1"
        duration_minutes: 30
```

### Format 3: Labs at Module Level (lab_activities key) ✅ FIXED
```yaml
modules:
  - title: "Module 1"
    lessons: [...]
    lab_activities:
      - title: "Lab 1"
        duration_minutes: 30
```

### Format 4: Simple String Labs
```yaml
modules:
  - title: "Module 1"
    lab_activities:
      - "Configure RMAN"  # String format
      - "Practice backups"
```

**Current Support**: ✅ All 4 formats now supported (as of Oct 24, 2025)

---

## 🧪 Test Cases to Run Before Each Deployment

### Test Suite: Critical Path

1. **Theory-Only Course (Claude)**
   - Outline: `outline-example.yaml`
   - content_type: `"theory"`
   - Expected: Success, theory book generated, no lab errors

2. **Theory-Only Course (GPT-5)**
   - Outline: `outline-example.yaml`
   - content_type: `"theory"`
   - model_provider: `"openai"`
   - Expected: Success, theory book with images

3. **Theory + Labs (Module-Level Labs)**
   - Outline: `outline-example3-es.yaml` or `outline-orac-dr.yaml`
   - content_type: `"both"`
   - Expected: Success, theory book + lab guide both generated

4. **Labs Only (No Theory)**
   - Outline: `outline-example3-es.yaml`
   - content_type: `"labs"`
   - Expected: Success, lab guide generated

5. **Outline with No Labs + content_type="both"**
   - Outline: `outline-example.yaml` (no labs)
   - content_type: `"both"`
   - Expected: Success with warning, theory generated, labs skipped gracefully

---

## 🔧 Quick Diagnostics

### When Course Generation Fails:

#### Step 1: Check Step Functions Execution
```bash
aws stepfunctions describe-execution \
  --execution-arn "arn:aws:states:...:execution:CourseGeneratorStateMachine:..." \
  --region us-east-1 \
  --query '{status: status, error: error, cause: cause}'
```

#### Step 2: Check Lambda CloudWatch Logs
```bash
# StarterApi
aws logs tail /aws/lambda/crewai-course-generator-stack-StarterApiFunction-PDGNdlsWAJTI --since 10m

# Content Generator
aws logs tail /aws/lambda/StrandsContentGen --since 10m

# Lab Planner
aws logs tail /aws/lambda/StrandsLabPlanner --since 10m

# Visual Planner
aws logs tail /aws/lambda/StrandsVisualPlanner --since 10m

# Images Generator
aws logs tail /aws/lambda/ImagesGen --since 10m

# Book Builder
aws logs tail /aws/lambda/crewai-course-generator-stack-BookBuilder-F8jUrBbphojQ --since 10m
```

#### Step 3: Check S3 Output
```bash
aws s3 ls s3://crewai-course-artifacts/{project_folder}/
aws s3 ls s3://crewai-course-artifacts/{project_folder}/lessons/
aws s3 ls s3://crewai-course-artifacts/{project_folder}/prompts/
aws s3 ls s3://crewai-course-artifacts/{project_folder}/images/
```

#### Step 4: Common Error Patterns

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `Runtime.ImportModuleError: No module named 'X'` | Missing dependency | Rebuild Lambda with `sam build`, redeploy |
| `No lab activities found` | Outline format incompatible | Update Lab Planner to support format |
| `Field not found: $.content_type` | Step Functions state mapping issue | Check Pass state Parameters in template.yaml |
| `openai.ChatCompletion no longer supported` | Old OpenAI API syntax | Update to v1.0+ (`from openai import OpenAI`) |
| `max_tokens not supported` | Using GPT-5 with wrong parameter | Use `max_completion_tokens` instead |
| Visual tags not replaced | Description mismatch | Check Visual Planner preserves original descriptions |

---

## 🚀 Deployment Process (Standard)

### For Lambda Functions:

```bash
# 1. Navigate to backend
cd /home/juan/AuroraV1/CG-Backend

# 2. Build specific function (includes dependencies)
sam build StarterApiFunction  # or StrandsContentGen, etc.

# 3. Create deployment package
cd .aws-sam/build/StarterApiFunction
zip -r /tmp/function_deploy.zip .

# 4. Deploy
aws lambda update-function-code \
  --function-name crewai-course-generator-stack-StarterApiFunction-PDGNdlsWAJTI \
  --zip-file fileb:///tmp/function_deploy.zip \
  --region us-east-1

# 5. Wait and verify
sleep 10
aws logs tail /aws/lambda/crewai-course-generator-stack-StarterApiFunction-PDGNdlsWAJTI --since 1m

# 6. Test immediately
# Try generating a test course in the UI
```

### For Step Functions (template.yaml):

```bash
cd /home/juan/AuroraV1/CG-Backend
sam build
sam deploy --no-confirm-changeset

# Monitor stack update
aws cloudformation describe-stacks \
  --stack-name crewai-course-generator-stack \
  --query 'Stacks[0].StackStatus'
```

---

## 📊 Health Check Script

Create this script to verify system health:

```bash
#!/bin/bash
# health_check.sh

echo "🔍 Checking AWS Resources..."

# Check Lambda functions
echo "Lambda Functions:"
aws lambda get-function --function-name StrandsContentGen --query 'Configuration.LastModified'
aws lambda get-function --function-name StrandsLabPlanner --query 'Configuration.LastModified'
aws lambda get-function --function-name StrandsVisualPlanner --query 'Configuration.LastModified'
aws lambda get-function --function-name ImagesGen --query 'Configuration.LastModified'

# Check Step Functions
echo "Step Functions:"
aws stepfunctions describe-state-machine \
  --state-machine-arn "arn:aws:states:us-east-1:746434296869:stateMachine:CourseGeneratorStateMachine" \
  --query 'status'

# Recent executions
echo "Recent Executions:"
aws stepfunctions list-executions \
  --state-machine-arn "arn:aws:states:us-east-1:746434296869:stateMachine:CourseGeneratorStateMachine" \
  --max-items 5 \
  --query 'executions[].[name,status,startDate]' \
  --output table

echo "✅ Health check complete"
```

---

## 🎯 Success Criteria

Before considering a deployment "safe":

1. ✅ All Lambda functions show `Active` state
2. ✅ CloudWatch logs show successful cold starts (no import errors)
3. ✅ At least 1 test course generation completes successfully
4. ✅ All existing outline examples still work
5. ✅ No new errors in CloudWatch logs
6. ✅ Git commit pushed with descriptive message

---

## 📚 Additional Resources

- **AWS Lambda Best Practices**: https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html
- **Step Functions Error Handling**: https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
- **SAM Build Documentation**: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html

---

## 📝 Change Log

| Date | Change | Reason | Fixed By |
|------|--------|--------|----------|
| 2025-10-24 | Added `lab_activities` support at module level | Outline format incompatibility | Lab Planner update |
| 2025-10-24 | Fixed StarterApi missing pyyaml | Incomplete deployment | Proper SAM build |
| 2025-10-23 | Visual Planner description preservation | Image mapping failures | Preserve original descriptions |
| 2025-10-23 | OpenAI API v1.0+ migration | API compatibility | Update all OpenAI calls |
| 2025-10-23 | GPT-5 max_completion_tokens | Parameter incompatibility | Conditional parameter logic |

---

**Remember**: When in doubt, test with existing examples first! 🧪
