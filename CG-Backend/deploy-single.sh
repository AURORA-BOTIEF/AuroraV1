#!/bin/bash
#
# SINGLE FUNCTION DEPLOYMENT
# ===========================
# Deploy ANY single Lambda function by name without touching others
#
# USAGE:
#   ./deploy-single.sh StrandsPPTGenerator
#   ./deploy-single.sh StrandsContentGen
#   ./deploy-single.sh ImagesGen
#

set -e

if [ -z "$1" ]; then
    echo ""
    echo "❌ Error: Function name required"
    echo ""
    echo "Usage: $0 <FunctionName>"
    echo ""
    echo "Available functions:"
    echo "  • StrandsPPTGenerator      - PPT generation"
    echo "  • StrandsContentGen        - Content generation"
    echo "  • StrandsVisualPlanner     - Visual planning"
    echo "  • StrandsLabPlanner        - Lab planning"
    echo "  • StrandsLabWriter         - Lab writing"
    echo "  • ImagesGen                - Image generation"
    echo "  • BookBuilder              - Book building"
    echo "  • BatchExpander            - Batch expansion"
    echo "  • LabBatchExpander         - Lab batch expansion"
    echo "  • StarterApiFunction       - API starter"
    echo ""
    exit 1
fi

FUNCTION="$1"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  SINGLE FUNCTION DEPLOYMENT: $FUNCTION"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

# Validate environment
if [ ! -f "template.yaml" ]; then
    echo "❌ Error: template.yaml not found"
    exit 1
fi

# Build
echo "🔨 Building $FUNCTION..."
if ! sam build "$FUNCTION"; then
    echo "❌ Build failed"
    exit 1
fi

# Verify build
if [ ! -d ".aws-sam/build/$FUNCTION" ]; then
    echo "❌ Build directory not found"
    exit 1
fi

echo "✅ Build successful"
echo ""

# Get physical name
echo "🔍 Looking up Lambda function..."
PHYSICAL_NAME=$(aws cloudformation describe-stack-resources \
    --stack-name crewai-course-generator-stack \
    --logical-resource-id "$FUNCTION" \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text 2>/dev/null || echo "$FUNCTION")

echo "   Function: $PHYSICAL_NAME"
echo ""

# Create package
echo "📦 Creating deployment package..."
cd .aws-sam/build/"$FUNCTION"
zip -q -r /tmp/"$FUNCTION".zip .
ZIP_SIZE=$(stat -f%z /tmp/"$FUNCTION".zip 2>/dev/null || stat -c%s /tmp/"$FUNCTION".zip)
ZIP_SIZE_MB=$(echo "scale=2; $ZIP_SIZE / 1048576" | bc 2>/dev/null || echo "?")
echo "   Size: ${ZIP_SIZE_MB}MB"
cd - > /dev/null
echo ""

# Deploy
echo "🚀 Deploying to Lambda..."
if aws lambda update-function-code \
    --function-name "$PHYSICAL_NAME" \
    --zip-file fileb:///tmp/"$FUNCTION".zip \
    --no-cli-pager > /dev/null 2>&1; then
    echo "✅ Deployment successful"
else
    echo "❌ Deployment failed"
    rm -f /tmp/"$FUNCTION".zip
    exit 1
fi

rm -f /tmp/"$FUNCTION".zip

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ $FUNCTION DEPLOYED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ All other Lambda functions remain UNCHANGED"
echo ""
echo "📊 Check logs:"
echo "   aws logs tail /aws/lambda/$PHYSICAL_NAME --follow"
echo ""
