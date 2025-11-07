# 🚀 Aurora Deployment Guide

## 🎯 Problem Solved

**Before:** Deploying PPT fixes broke content generator  
**After:** Deploy each system independently - zero risk of breaking unrelated code

---

## 📋 Quick Reference

### Deploy Single Function (Safest!)
```bash
# Deploy ONLY PPT Generator
./deploy-ppt-only.sh

# Deploy ONLY Content Generator  
./deploy-content-only.sh

# Deploy ANY single function
./deploy-single.sh <FunctionName>
```

### Deploy Full System (When Needed)
```bash
# Deploy everything with dependencies
./deploy-with-dependencies.sh full
```

---

## 🎯 Which Script Should I Use?

| Situation | Script | Impact |
|-----------|--------|--------|
| **Fixed PPT bug** | `deploy-ppt-only.sh` | Only PPT changes |
| **Fixed content generator** | `deploy-content-only.sh` | Only content functions change |
| **Fixed single function** | `deploy-single.sh <Name>` | Only that function changes |
| **Updated template.yaml** | `deploy-with-dependencies.sh template-only` | Infrastructure only |
| **Changed dependencies/layers** | `deploy-with-dependencies.sh full` | Everything rebuilds |
| **New feature across multiple functions** | `deploy-with-dependencies.sh full` | Everything rebuilds |

---

## 🛡️ Safety Guarantees

### ✅ deploy-ppt-only.sh
- **Changes:** StrandsPPTGenerator only
- **Safe:** ✅ Content generator untouched
- **Safe:** ✅ Images generator untouched  
- **Safe:** ✅ Lab functions untouched
- **Safe:** ✅ API Gateway untouched
- **Safe:** ✅ Step Functions untouched

### ✅ deploy-content-only.sh
- **Changes:** StrandsContentGen, StrandsVisualPlanner, BookBuilder, BatchExpander
- **Safe:** ✅ PPT generator untouched
- **Safe:** ✅ Images generator untouched
- **Safe:** ✅ Lab functions untouched

### ✅ deploy-single.sh
- **Changes:** Only the function you specify
- **Safe:** ✅ Everything else untouched

### ⚠️ deploy-with-dependencies.sh full
- **Changes:** ALL Lambda functions rebuild
- **Risk:** ⚠️ Can break working functions if dependencies changed
- **Use When:** Dependency updates or major changes

---

## 📖 Detailed Usage

### Scenario 1: You Fixed a PPT Bug
```bash
cd /home/juan/AuroraV1/CG-Backend

# Make your code changes in lambda/strands_ppt_generator/

# Deploy ONLY PPT - nothing else touched
./deploy-ppt-only.sh

# Test
aws logs tail /aws/lambda/StrandsPPTGenerator --follow
```

**Result:** PPT deployed, content generator still works perfectly ✅

### Scenario 2: You Updated Content Generator Logic
```bash
cd /home/juan/AuroraV1/CG-Backend

# Make your changes in lambda/strands_content_gen/

# Deploy ONLY content functions
./deploy-content-only.sh

# Test
aws logs tail /aws/lambda/StrandsContentGen --follow
```

**Result:** Content generator updated, PPT still works perfectly ✅

### Scenario 3: You Need to Deploy Just One Function
```bash
cd /home/juan/AuroraV1/CG-Backend

# Deploy just ImagesGen
./deploy-single.sh ImagesGen

# Deploy just BookBuilder
./deploy-single.sh BookBuilder
```

**Result:** Only that function changes, everything else untouched ✅

### Scenario 4: You Updated template.yaml (Step Function, API, etc.)
```bash
cd /home/juan/AuroraV1/CG-Backend

# Deploy ONLY infrastructure changes
./deploy-with-dependencies.sh template-only

# Then rebuild Lambda functions if needed
./deploy-with-dependencies.sh full
```

**Result:** Infrastructure updated safely

### Scenario 5: You Updated Lambda Layer Dependencies
```bash
cd /home/juan/AuroraV1/CG-Backend

# Example: Updated Strands SDK version in requirements-strands.txt
./create-vertex-layer.sh  # Rebuild layer

# Now redeploy ALL functions to pick up new layer
./deploy-with-dependencies.sh full
```

**Result:** All functions get new dependencies

---

## 🔍 Troubleshooting

### "Build failed for <Function>"
**Cause:** Syntax error or missing dependency  
**Fix:** Check the function's code and requirements.txt

### "CloudFormation lookup failed"
**Cause:** Stack name incorrect or function doesn't exist yet  
**Fix:** Verify stack name in script matches actual stack

### "Deployment failed for <Function>"  
**Cause:** IAM permissions or Lambda doesn't exist
**Fix:** 
```bash
# Check if function exists
aws lambda get-function --function-name <FunctionName>

# Check IAM permissions
aws sts get-caller-identity
```

### "All functions rebuilding when I don't want them to"
**Cause:** Using wrong script  
**Fix:** Use `deploy-ppt-only.sh` or `deploy-single.sh` instead of `deploy-with-dependencies.sh`

---

## 📊 Deployment Time Comparison

| Script | Functions Changed | Time | Risk |
|--------|------------------|------|------|
| `deploy-single.sh` | 1 | ~30 sec | ✅ None |
| `deploy-ppt-only.sh` | 1 | ~30 sec | ✅ None |
| `deploy-content-only.sh` | 4 | ~2 min | ✅ Low |
| `deploy-with-dependencies.sh full` | 17+ | ~8 min | ⚠️ High |

---

## 🎯 Best Practices

1. **Use the most specific script possible**
   - Fixed PPT? → Use `deploy-ppt-only.sh`
   - Fixed content? → Use `deploy-content-only.sh`
   - Fixed one function? → Use `deploy-single.sh`

2. **Test after deployment**
   ```bash
   # Watch logs to verify deployment
   aws logs tail /aws/lambda/<FunctionName> --follow
   ```

3. **Avoid full deployments unless necessary**
   - Only use `deploy-with-dependencies.sh full` when you've changed:
     - Lambda layer dependencies
     - Multiple unrelated functions
     - Template infrastructure

4. **Keep backups of working code**
   ```bash
   # Before major changes
   git commit -am "Working state before deployment"
   ```

---

## 🚀 Next Steps: Multi-Stack Architecture (Future)

For even better isolation, consider splitting into separate stacks:
- `template-content.yaml` - Content generation
- `template-labs.yaml` - Lab generation  
- `template-ppt.yaml` - PPT & images
- `template-shared.yaml` - Layers, S3, IAM

See `DEPLOYMENT_STRATEGY.md` for details.

---

## 💡 Quick Command Reference

```bash
# Deploy PPT only
./deploy-ppt-only.sh

# Deploy content only
./deploy-content-only.sh

# Deploy any single function
./deploy-single.sh <FunctionName>

# Deploy template changes only (no Lambda updates)
./deploy-with-dependencies.sh template-only

# Full rebuild (use sparingly!)
./deploy-with-dependencies.sh full

# Check function logs
aws logs tail /aws/lambda/<FunctionName> --follow

# List all functions
aws lambda list-functions --query 'Functions[].FunctionName'

# Get function info
aws lambda get-function --function-name <FunctionName>
```

---

## ✅ Summary

**Key Takeaway:** You now have **safe, isolated deployment** for each system component.

- Need to fix PPT? → Use `deploy-ppt-only.sh` → Content generator stays safe ✅
- Need to fix content? → Use `deploy-content-only.sh` → PPT stays safe ✅  
- Need to fix one function? → Use `deploy-single.sh` → Everything else stays safe ✅

**No more breaking working code when deploying unrelated changes!** 🎉
