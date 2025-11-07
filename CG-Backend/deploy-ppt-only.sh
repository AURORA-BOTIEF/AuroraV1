#!/bin/bash
#
# SAFE INFOGRAPHIC DEPLOYMENT SCRIPT
# ====================================
# Deploy ONLY the Infographic Generator without touching any other Lambda functions
#
# PROBLEM: 
# Your deploy-with-dependencies.sh rebuilds ALL functions, risking breakage
# of working content generator when you just want to fix infographic issues.
#
# SOLUTION:
# This script builds and deploys ONLY StrandsInfographicGenerator, leaving all
# other functions completely untouched.
#
# USAGE:
#   ./deploy-ppt-only.sh
#

set -e  # Exit on error

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  INFOGRAPHIC GENERATOR - ISOLATED DEPLOYMENT                      ║"
echo "║  (Content generator and other functions remain untouched)         ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

# Validate we're in the right directory
if [ ! -f "template.yaml" ]; then
    echo "❌ Error: template.yaml not found. Please run from CG-Backend directory."
    exit 1
fi

# Validate SAM CLI
if ! command -v sam &> /dev/null; then
    echo "❌ Error: AWS SAM CLI not found. Please install it first."
    exit 1
fi

# Validate AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI not found. Please install it first."
    exit 1
fi

FUNCTION="StrandsInfographicGenerator"

echo "🔨 Building $FUNCTION..."
echo ""

# Build only this function
if ! sam build "$FUNCTION"; then
    echo ""
    echo "❌ Build failed for $FUNCTION"
    exit 1
fi

# Verify build directory exists
if [ ! -d ".aws-sam/build/$FUNCTION" ]; then
    echo "❌ Build directory not found: .aws-sam/build/$FUNCTION"
    exit 1
fi

echo ""
echo "✅ Build successful"
echo ""

# Get the physical function name from CloudFormation
echo "🔍 Looking up Lambda function name..."
PHYSICAL_NAME=$(aws cloudformation describe-stack-resources \
    --stack-name crewai-course-generator-stack \
    --logical-resource-id "$FUNCTION" \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text 2>/dev/null)

if [ -z "$PHYSICAL_NAME" ] || [ "$PHYSICAL_NAME" == "None" ]; then
    echo "⚠️  CloudFormation lookup failed, trying logical name: $FUNCTION"
    PHYSICAL_NAME="$FUNCTION"
fi

echo "   Lambda function: $PHYSICAL_NAME"
echo ""

# Create deployment package
echo "📦 Creating deployment package..."
cd .aws-sam/build/"$FUNCTION"

if ! zip -q -r /tmp/"$FUNCTION".zip .; then
    echo "❌ Failed to create deployment zip"
    exit 1
fi

# Show package size
ZIP_SIZE=$(stat -f%z /tmp/"$FUNCTION".zip 2>/dev/null || stat -c%s /tmp/"$FUNCTION".zip 2>/dev/null)
ZIP_SIZE_MB=$(echo "scale=2; $ZIP_SIZE / 1048576" | bc)
echo "   Package size: ${ZIP_SIZE_MB}MB"
echo ""

cd - > /dev/null

# Deploy to Lambda
echo "🚀 Deploying to Lambda..."
echo ""

DEPLOY_OUTPUT=$(aws lambda update-function-code \
    --function-name "$PHYSICAL_NAME" \
    --zip-file fileb:///tmp/"$FUNCTION".zip \
    --no-cli-pager 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Deployment failed!"
    echo "$DEPLOY_OUTPUT"
    exit 1
fi

# Extract deployment info
if command -v jq &> /dev/null; then
    CODE_SIZE=$(echo "$DEPLOY_OUTPUT" | jq -r '.CodeSize // empty' 2>/dev/null)
    LAST_MODIFIED=$(echo "$DEPLOY_OUTPUT" | jq -r '.LastModified // empty' 2>/dev/null)
    RUNTIME=$(echo "$DEPLOY_OUTPUT" | jq -r '.Runtime // empty' 2>/dev/null)
    
    if [ ! -z "$CODE_SIZE" ]; then
        CODE_SIZE_MB=$(echo "scale=2; $CODE_SIZE / 1048576" | bc)
        echo "   Lambda code size: ${CODE_SIZE_MB}MB"
    fi
    if [ ! -z "$LAST_MODIFIED" ]; then
        echo "   Last modified: $LAST_MODIFIED"
    fi
    if [ ! -z "$RUNTIME" ]; then
        echo "   Runtime: $RUNTIME"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT SUCCESSFUL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ StrandsInfographicGenerator deployed - HTML to editable PPT!"
echo "✅ Content generator and ALL other functions remain UNCHANGED"
echo "✅ No risk of breaking existing functionality"
echo ""
echo "🧪 Testing the deployment:"
echo "   aws lambda invoke --function-name $PHYSICAL_NAME \\"
echo "     --payload '{\"course_bucket\":\"...\",\"project_folder\":\"...\",\"book_version_key\":\"...\"}' \\"
echo "     /tmp/infographic-response.json"
echo ""
echo "📊 Check logs:"
echo "   aws logs tail /aws/lambda/$PHYSICAL_NAME --follow"
echo ""

# Cleanup
rm -f /tmp/"$FUNCTION".zip

echo "🎉 Ready to test!"
echo ""
