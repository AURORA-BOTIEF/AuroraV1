# 🚀 Aurora Deployment Scripts

## Quick Start

### Deploy PPT Generator Only (Most Common)
```bash
./deploy-ppt-only.sh
```
✅ **Safe:** Content generator untouched  
⏱️ **Fast:** ~30 seconds

### Deploy Content Generator Only
```bash
./deploy-content-only.sh
```
✅ **Safe:** PPT generator untouched  
⏱️ **Fast:** ~2 minutes

### Deploy Any Single Function
```bash
./deploy-single.sh <FunctionName>
```
✅ **Safe:** Everything else untouched  
⏱️ **Fast:** ~30 seconds

### Deploy Everything (Use Sparingly!)
```bash
# Infrastructure only
./deploy-with-dependencies.sh template-only

# Full rebuild
./deploy-with-dependencies.sh full
```
⚠️ **Caution:** Rebuilds all functions (~8 minutes)

---

## 📖 Full Documentation

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete usage guide
- **[DEPLOYMENT_IMPROVEMENTS.md](DEPLOYMENT_IMPROVEMENTS.md)** - What was just fixed
- **[DEPLOYMENT_STRATEGY.md](DEPLOYMENT_STRATEGY.md)** - Future architecture

---

## 🎯 Which Script Should I Use?

| Changed | Script | Time | Safety |
|---------|--------|------|--------|
| **PPT code** | `./deploy-ppt-only.sh` | 30s | ✅ |
| **Content code** | `./deploy-content-only.sh` | 2m | ✅ |
| **One function** | `./deploy-single.sh <Name>` | 30s | ✅ |
| **Template** | `./deploy-with-dependencies.sh template-only` | 5m | ⚠️ |
| **Dependencies** | `./deploy-with-dependencies.sh full` | 8m | ⚠️⚠️ |

---

## 📝 Available Functions

```
StrandsPPTGenerator      - PPT generation
StrandsContentGen        - Content generation
StrandsVisualPlanner     - Visual planning
StrandsLabPlanner        - Lab planning
StrandsLabWriter         - Lab writing
ImagesGen                - Image generation
BookBuilder              - Book building
BatchExpander            - Batch expansion
LabBatchExpander         - Lab batch expansion
StarterApiFunction       - API starter
```

---

## ✅ What's New

**Just Deployed (Nov 4, 2024):**
- ✅ PPT Generator: Retry logic for Bedrock timeouts
- ✅ PPT Generator: Extended timeout (15 minutes)
- ✅ Safe deployment scripts (no more breaking content generator!)

---

## 🐛 Troubleshooting

**Build fails?**
```bash
# Check syntax
python -m py_compile lambda/<function>/<file>.py
```

**Deployment fails?**
```bash
# Check if function exists
aws lambda get-function --function-name <FunctionName>

# Check permissions
aws sts get-caller-identity
```

**Want to see logs?**
```bash
aws logs tail /aws/lambda/<FunctionName> --follow
```

---

## 💡 Best Practice

**Always use the most specific script possible!**

- ✅ PPT change? → `deploy-ppt-only.sh`
- ✅ Content change? → `deploy-content-only.sh`  
- ✅ One function? → `deploy-single.sh`
- ⚠️ Everything? → `deploy-with-dependencies.sh full`

**Why?** Faster deployments + zero risk to unrelated code

---

## 🎉 Quick Command Reference

```bash
# Deploy PPT only
./deploy-ppt-only.sh

# Deploy content only  
./deploy-content-only.sh

# Deploy single function
./deploy-single.sh <FunctionName>

# Check logs
aws logs tail /aws/lambda/<FunctionName> --follow

# List all functions
aws lambda list-functions --query 'Functions[].FunctionName'
```

---

**Need help?** Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
