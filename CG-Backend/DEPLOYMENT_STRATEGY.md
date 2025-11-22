# Aurora V1 - Improved Deployment Strategy

## 🎯 Problem Statement

**Current Issue:**
- Single `template.yaml` with 17+ Lambda functions
- Deploying ANY change rebuilds ALL functions
- Risk of breaking working functions when deploying unrelated changes
- Content generator breaks when deploying PPT generator fixes
- Long deployment times (all functions rebuild even if unchanged)

## ✅ Recommended Solution: Multi-Stack Architecture

Split into **3 separate CloudFormation stacks** based on functional domains:

### Stack 1: Core Content Generation (`template-content.yaml`)
**Purpose:** Theory book generation pipeline
- StrandsContentGen
- StrandsVisualPlanner  
- BookBuilder
- BatchExpander
- StarterApiFunction (if only used by content gen)

**Deploy when:** Making changes to content generation logic

### Stack 2: Lab Generation (`template-labs.yaml`)
**Purpose:** Lab guide generation pipeline
- StrandsLabPlanner
- StrandsLabWriter
- LabBookBuilder (if separate)
- LabBatchExpander

**Deploy when:** Making changes to lab generation logic

### Stack 3: Presentation & Images (`template-ppt.yaml`)
**Purpose:** PPT generation and image management
- StrandsPPTGenerator
- ImagesGen
- Any image processing functions

**Deploy when:** Making changes to PPT or image generation

### Stack 4: Shared Infrastructure (`template-shared.yaml`)
**Purpose:** Resources used by multiple stacks
- Lambda Layers (StrandsAgentsLayer, GeminiLayer, PPTLayer)
- S3 Buckets
- IAM Roles (if shared)
- API Gateway (or use separate APIs per stack)
- Step Functions state machines

**Deploy when:** Updating dependencies or shared infrastructure

## 📋 Benefits of This Approach

1. **Isolation**: Deploy PPT changes without touching content generator
2. **Faster Deploys**: Only rebuild functions that changed
3. **Safer**: Reduces blast radius of deployment failures
4. **Clearer Ownership**: Each stack has a clear purpose
5. **Parallel Development**: Team can work on different stacks simultaneously
6. **Cost Optimization**: Only pay for CloudFormation change sets you actually need

## 🚀 Implementation Plan

### Phase 1: Create Separate Templates (1-2 hours)
1. Extract functions into separate template files
2. Set up cross-stack references using CloudFormation Exports/Imports
3. Update deployment scripts

### Phase 2: Create Targeted Deployment Scripts (30 min)
1. `deploy-content.sh` - Deploy content generation stack only
2. `deploy-labs.sh` - Deploy lab generation stack only  
3. `deploy-ppt.sh` - Deploy PPT stack only
4. `deploy-shared.sh` - Deploy shared infrastructure only
5. `deploy-all.sh` - Full deployment (when needed)

### Phase 3: Test & Validate (1 hour)
1. Deploy each stack independently
2. Verify cross-stack references work
3. Test end-to-end workflows

## 📁 Proposed File Structure

```
CG-Backend/
├── templates/
│   ├── template-shared.yaml      # Layers, S3, IAM
│   ├── template-content.yaml     # Theory content pipeline
│   ├── template-labs.yaml        # Lab pipeline
│   └── template-ppt.yaml         # PPT & images
├── scripts/
│   ├── deploy-shared.sh          # Deploy shared infrastructure
│   ├── deploy-content.sh         # Deploy content stack
│   ├── deploy-labs.sh            # Deploy labs stack
│   ├── deploy-ppt.sh             # Deploy PPT stack
│   └── deploy-all.sh             # Full deployment
├── lambda/                        # Lambda function code (unchanged)
└── lambda-layers/                 # Layer packages (unchanged)
```

## 🔧 Alternative: Use SAM Build with --cached

If splitting stacks is too much work right now, you can improve your current script:

```bash
# Use cached builds - only rebuilds changed functions
sam build --cached --parallel

# Deploy only specific function
sam deploy --no-confirm-changeset --parameter-overrides ParameterKey=DeployOnlyFunction,ParameterValue=StrandsPPTGenerator
```

However, this is **less reliable** than separate stacks.

## 🎯 Quick Win: Immediate Improvement

**For your current PPT deployment:**

Create `deploy-ppt-only.sh`:
```bash
#!/bin/bash
# Deploy ONLY the PPT generator without touching other functions
set -e

echo "🎨 Deploying PPT Generator ONLY..."

# Build only PPT function
sam build StrandsPPTGenerator

# Get the physical function name
PHYSICAL_NAME=$(aws cloudformation describe-stack-resources \
    --stack-name crewai-course-generator-stack \
    --logical-resource-id StrandsPPTGenerator \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text)

# Deploy
cd .aws-sam/build/StrandsPPTGenerator
zip -q -r /tmp/StrandsPPTGenerator.zip .
cd - > /dev/null

aws lambda update-function-code \
    --function-name "$PHYSICAL_NAME" \
    --zip-file fileb:///tmp/StrandsPPTGenerator.zip

echo "✅ PPT Generator deployed successfully"
echo "✅ Content generator and other functions UNTOUCHED"
```

This lets you deploy PPT changes **immediately** without risk to other functions.

## 📊 Decision Matrix

| Approach | Setup Time | Safety | Deploy Speed | Recommended? |
|----------|-----------|--------|--------------|--------------|
| **Current (single template)** | 0 min | ❌ Low | 🐌 Slow | No |
| **Multi-stack** | 2 hours | ✅ High | ⚡ Fast | **YES** |
| **SAM --cached** | 5 min | ⚠️ Medium | 🚀 Medium | Temporary |
| **Single-function deploy** | 15 min | ✅ High | ⚡ Fast | **Quick Win** |

## 🎯 My Recommendation

1. **RIGHT NOW**: Create `deploy-ppt-only.sh` (15 minutes) - Immediate relief
2. **THIS WEEK**: Split into 4 templates (2 hours) - Long-term solution
3. **ONGOING**: Use targeted deployment scripts - Never break working code again

Would you like me to:
1. Create the single-function deployment script for PPT? (Quick win)
2. Split your template into multiple stacks? (Best long-term solution)
3. Both?
