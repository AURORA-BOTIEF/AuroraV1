#!/bin/bash
#
# CRITICAL DEPLOYMENT SCRIPT
# ==========================
# This script ensures Lambda functions are deployed WITH their dependencies.
#
# PROBLEM: 
# When you run `sam deploy`, it re-uploads ALL Lambda functions from the template,
# OVERWRITING any manually-deployed versions with dependencies. This breaks
# functions that need pyyaml and other external packages.
#
# SOLUTION:
# 1. Deploy template changes first (Step Functions, API Gateway, etc.)
# 2. Then rebuild and redeploy Lambda functions WITH dependencies
#
# USAGE:
#   ./deploy-with-dependencies.sh [template-only|full|FunctionName1,FunctionName2,...]
#
# OPTIONS:
#   template-only - Only deploy template changes (Step Functions, etc.)
#   full         - Deploy template AND rebuild all Lambda functions with deps
#   FunctionName1,FunctionName2 - Deploy only specific functions (comma-separated)
#
# EXAMPLES:
#   ./deploy-with-dependencies.sh full                                    # Deploy everything
#   ./deploy-with-dependencies.sh StrandsInfographicGenerator             # Deploy only infographic generator
#   ./deploy-with-dependencies.sh StrandsContentGen,StrandsLabWriter      # Deploy multiple specific functions
#

set -e  # Exit on error

# Validate prerequisites
echo "🔍 Validating prerequisites..."

# Check if we're in the right directory
if [ ! -f "template.yaml" ]; then
    echo "❌ Error: template.yaml not found. Please run this script from the CG-Backend directory."
    exit 1
fi

# Check if sam CLI is available
if ! command -v sam &> /dev/null; then
    echo "❌ Error: AWS SAM CLI not found. Please install it first."
    exit 1
fi

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI not found. Please install it first."
    exit 1
fi

# Check if jq is available (optional but helpful)
if ! command -v jq &> /dev/null; then
    echo "⚠️  Warning: jq not found. Install it for better output formatting."
fi

echo "✅ All prerequisites met"
echo ""

# Functions that need external dependencies (pyyaml, Pillow, python-pptx, etc.)
FUNCTIONS_WITH_DEPS=(
    "StarterApiFunction"            # Needs: pyyaml
    "StrandsContentGen"             # Needs: pyyaml
    "StrandsVisualPlanner"          # Needs: boto3 (but included for consistency)
    "StrandsLabPlanner"             # Needs: pyyaml
    "StrandsLabWriter"              # Needs: pyyaml
    "StrandsInfographicGenerator"   # Needs: python-pptx, Pillow (HTML to editable PPT)
    "BatchExpander"                 # Needs: pyyaml
    "LabBatchExpander"              # Needs: pyyaml
    "ImagesGen"                     # ALL dependencies in GeminiLayer (empty requirements.txt)
    "BookBuilder"                   # Standard lib only (but deployed for consistency)
)

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  AURORA COURSE GENERATOR - SAFE DEPLOYMENT SCRIPT                 ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

MODE="${1:-full}"

# Parse mode to determine which functions to deploy
if [ "$MODE" == "template-only" ]; then
    FUNCTIONS_TO_DEPLOY=()
elif [ "$MODE" == "full" ]; then
    FUNCTIONS_TO_DEPLOY=("${FUNCTIONS_WITH_DEPS[@]}")
else
    # Specific functions mode - comma-separated list
    IFS=',' read -ra FUNCTIONS_TO_DEPLOY <<< "$MODE"
    MODE="specific"
fi

if [ "$MODE" == "template-only" ]; then
    echo "📋 Mode: Template Only (Step Functions, API Gateway, etc.)"
    echo ""
    echo "⚠️  WARNING: This will OVERWRITE Lambda functions without dependencies!"
    echo "⚠️  You MUST run this script again with 'full' mode after!"
    echo ""
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "❌ Aborted"
        exit 1
    fi
    
    echo ""
    echo "🚀 Deploying template changes..."
    sam deploy --no-confirm-changeset
    
    echo ""
    echo "✅ Template deployed successfully"
    echo ""
    echo "⚠️  NEXT STEP: Run './deploy-with-dependencies.sh full' to fix Lambda functions!"
    echo ""
    exit 0
fi

# Full deployment or specific functions mode
if [ "$MODE" == "specific" ]; then
    echo "📋 Mode: Specific Functions Only"
    echo "📦 Functions to deploy: ${FUNCTIONS_TO_DEPLOY[@]}"
    echo ""
else
    echo "📋 Mode: Full Deployment (Template + Lambda Functions with Dependencies)"
    echo ""
fi

# Step 1: Deploy template (only if full mode)
if [ "$MODE" == "full" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "STEP 1: Deploying Template Changes"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    sam deploy --no-confirm-changeset || echo "⚠️  Template unchanged or deployment failed (continuing with Lambda functions...)"

    echo ""
    echo "✅ Template deployment complete"
    echo ""
fi

# Step 2: Rebuild and redeploy functions with dependencies
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$MODE" == "specific" ]; then
    echo "STEP: Deploying Specific Lambda Functions"
else
    echo "STEP 2: Rebuilding Lambda Functions with Dependencies"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Track deployment status
DEPLOYED_COUNT=0
FAILED_COUNT=0
FAILED_FUNCTIONS=()

for FUNCTION in "${FUNCTIONS_TO_DEPLOY[@]}"; do
    echo "🔨 Building $FUNCTION..."
    
    # Build with error handling
    BUILD_OUTPUT=$(sam build "$FUNCTION" 2>&1)
    BUILD_EXIT_CODE=$?
    
    if [ $BUILD_EXIT_CODE -ne 0 ]; then
        echo "❌ Build failed for $FUNCTION"
        echo "$BUILD_OUTPUT"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_FUNCTIONS+=("$FUNCTION (build failed)")
        continue
    fi
    
    # Verify build directory exists
    if [ ! -d ".aws-sam/build/$FUNCTION" ]; then
        echo "❌ Build directory not found for $FUNCTION"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_FUNCTIONS+=("$FUNCTION (no build dir)")
        continue
    fi
    
    # Check if requirements.txt exists and log dependencies
    if [ -f "lambda/$(echo $FUNCTION | sed 's/Function$//' | sed 's/\([A-Z]\)/_\L\1/g' | sed 's/^_//')/requirements.txt" ] || \
       [ -f ".aws-sam/build/$FUNCTION/requirements.txt" ]; then
        echo "📦 Dependencies detected for $FUNCTION"
    fi
    
    # Get the physical function name from CloudFormation stack
    # Some functions (like ImagesGen) use explicit FunctionName, others use auto-generated names
    PHYSICAL_NAME=$(aws cloudformation describe-stack-resources \
        --stack-name crewai-course-generator-stack \
        --logical-resource-id "$FUNCTION" \
        --query 'StackResources[0].PhysicalResourceId' \
        --output text 2>/dev/null)
    
    # If CloudFormation query fails, the function might use an explicit name (e.g., ImagesGen)
    if [ -z "$PHYSICAL_NAME" ] || [ "$PHYSICAL_NAME" == "None" ]; then
        echo "⚠️  CloudFormation lookup failed, using logical name: $FUNCTION"
        PHYSICAL_NAME="$FUNCTION"
    fi
    
    echo "📦 Creating deployment package..."
    cd .aws-sam/build/"$FUNCTION"
    
    # Create zip with error handling
    if ! zip -q -r /tmp/"$FUNCTION".zip . 2>/dev/null; then
        echo "❌ Failed to create zip for $FUNCTION"
        cd - > /dev/null
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_FUNCTIONS+=("$FUNCTION (zip failed)")
        continue
    fi
    
    # Check zip size
    ZIP_SIZE=$(stat -f%z /tmp/"$FUNCTION".zip 2>/dev/null || stat -c%s /tmp/"$FUNCTION".zip 2>/dev/null)
    ZIP_SIZE_MB=$(echo "scale=2; $ZIP_SIZE / 1048576" | bc 2>/dev/null || echo "0")
    echo "   Package size: $(numfmt --to=iec-i --suffix=B $ZIP_SIZE 2>/dev/null || echo "$ZIP_SIZE bytes")"
    
    # Check if package exceeds Lambda direct upload limit (50MB)
    if [ $(echo "$ZIP_SIZE > 52428800" | bc 2>/dev/null || echo 0) -eq 1 ]; then
        echo "⚠️  Package exceeds 50MB limit ($ZIP_SIZE_MB MB), using S3 upload..."
        
        # Upload to S3 first
        S3_BUCKET="aws-sam-cli-managed-default-samclisourcebucket-ft8ensjaaupq"
        S3_KEY="lambda-deployments/$FUNCTION-$(date +%s).zip"
        
        if ! aws s3 cp /tmp/"$FUNCTION".zip s3://$S3_BUCKET/$S3_KEY --no-cli-pager 2>/dev/null; then
            echo "❌ Failed to upload $FUNCTION to S3"
            cd - > /dev/null
            FAILED_COUNT=$((FAILED_COUNT + 1))
            FAILED_FUNCTIONS+=("$FUNCTION (S3 upload failed)")
            continue
        fi
        
        echo "   Uploaded to S3: s3://$S3_BUCKET/$S3_KEY"
    fi
    
    cd - > /dev/null
    
    echo "🚀 Deploying $FUNCTION to Lambda..."
    
    # Deploy with error handling (use S3 if package is large)
    if [ $(echo "$ZIP_SIZE > 52428800" | bc 2>/dev/null || echo 0) -eq 1 ]; then
        DEPLOY_OUTPUT=$(aws lambda update-function-code \
            --function-name "$PHYSICAL_NAME" \
            --s3-bucket "$S3_BUCKET" \
            --s3-key "$S3_KEY" \
            --no-cli-pager 2>&1)
    else
        DEPLOY_OUTPUT=$(aws lambda update-function-code \
            --function-name "$PHYSICAL_NAME" \
            --zip-file fileb:///tmp/"$FUNCTION".zip \
            --no-cli-pager 2>&1)
    fi
    DEPLOY_EXIT_CODE=$?
    
    if [ $DEPLOY_EXIT_CODE -ne 0 ]; then
        echo "❌ Deployment failed for $FUNCTION"
        echo "   Error details:"
        echo "$DEPLOY_OUTPUT" | head -10
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_FUNCTIONS+=("$FUNCTION (deploy failed)")
        
        # Clean up S3 object if it was uploaded
        if [ $(echo "$ZIP_SIZE > 52428800" | bc 2>/dev/null || echo 0) -eq 1 ]; then
            aws s3 rm s3://$S3_BUCKET/$S3_KEY --no-cli-pager 2>/dev/null || true
        fi
        continue
    fi
    
    # Extract and display key info
    CODE_SIZE=$(echo "$DEPLOY_OUTPUT" | jq -r '.CodeSize // empty' 2>/dev/null)
    LAST_MODIFIED=$(echo "$DEPLOY_OUTPUT" | jq -r '.LastModified // empty' 2>/dev/null)
    
    if [ ! -z "$CODE_SIZE" ]; then
        echo "   Lambda size: $(numfmt --to=iec-i --suffix=B $CODE_SIZE 2>/dev/null || echo "$CODE_SIZE bytes")"
    fi
    if [ ! -z "$LAST_MODIFIED" ]; then
        echo "   Updated: $LAST_MODIFIED"
    fi
    
    echo "✅ $FUNCTION deployed successfully"
    DEPLOYED_COUNT=$((DEPLOYED_COUNT + 1))
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Deployment Summary:"
echo "   ✅ Successfully deployed: $DEPLOYED_COUNT functions"
if [ $FAILED_COUNT -gt 0 ]; then
    echo "   ❌ Failed: $FAILED_COUNT functions"
    echo ""
    echo "Failed functions:"
    for FUNC in "${FAILED_FUNCTIONS[@]}"; do
        echo "     - $FUNC"
    done
    echo ""
    echo "⚠️  Some functions failed to deploy. Please check the logs above."
    exit 1
else
    echo ""
    echo "📊 All functions deployed successfully:"
    for FUNCTION in "${FUNCTIONS_WITH_DEPS[@]}"; do
        echo "  ✓ $FUNCTION"
    done
fi
echo ""
echo "🎉 System ready for use!"
echo ""
