#!/bin/bash
#
# SAFE CONTENT GENERATOR DEPLOYMENT SCRIPT
# ==========================================
# Deploy ONLY content generation functions without touching PPT or other systems
#
# FUNCTIONS DEPLOYED:
#   - StrandsContentGen
#   - StrandsVisualPlanner
#   - BookBuilder
#   - BatchExpander
#
# OTHER FUNCTIONS REMAIN UNTOUCHED:
#   - StrandsPPTGenerator ✅
#   - ImagesGen ✅
#   - Lab functions ✅
#

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  CONTENT GENERATOR - ISOLATED DEPLOYMENT                          ║"
echo "║  (PPT, Images, and Lab functions remain untouched)                ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

# Validate environment
if [ ! -f "template.yaml" ]; then
    echo "❌ Error: template.yaml not found. Please run from CG-Backend directory."
    exit 1
fi

if ! command -v sam &> /dev/null || ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS SAM CLI and AWS CLI are required."
    exit 1
fi

# Content generation functions
CONTENT_FUNCTIONS=(
    "StrandsContentGen"
    "StrandsVisualPlanner"
    "BookBuilder"
    "BatchExpander"
)

echo "📋 Functions to deploy:"
for func in "${CONTENT_FUNCTIONS[@]}"; do
    echo "   • $func"
done
echo ""

read -p "Continue with deployment? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Deployment cancelled"
    exit 0
fi

echo ""
DEPLOYED=0
FAILED=0

for FUNCTION in "${CONTENT_FUNCTIONS[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔨 Building $FUNCTION..."
    echo ""
    
    if ! sam build "$FUNCTION" 2>&1 | grep -E "(Build Succeeded|Successfully)"; then
        echo "❌ Build failed for $FUNCTION"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    if [ ! -d ".aws-sam/build/$FUNCTION" ]; then
        echo "❌ Build directory not found for $FUNCTION"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # Get physical name
    PHYSICAL_NAME=$(aws cloudformation describe-stack-resources \
        --stack-name crewai-course-generator-stack \
        --logical-resource-id "$FUNCTION" \
        --query 'StackResources[0].PhysicalResourceId' \
        --output text 2>/dev/null || echo "$FUNCTION")
    
    echo "📦 Creating deployment package..."
    cd .aws-sam/build/"$FUNCTION"
    zip -q -r /tmp/"$FUNCTION".zip .
    cd - > /dev/null
    
    echo "🚀 Deploying to Lambda: $PHYSICAL_NAME..."
    if aws lambda update-function-code \
        --function-name "$PHYSICAL_NAME" \
        --zip-file fileb:///tmp/"$FUNCTION".zip \
        --no-cli-pager > /dev/null 2>&1; then
        echo "✅ $FUNCTION deployed successfully"
        DEPLOYED=$((DEPLOYED + 1))
    else
        echo "❌ Deployment failed for $FUNCTION"
        FAILED=$((FAILED + 1))
    fi
    
    rm -f /tmp/"$FUNCTION".zip
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 DEPLOYMENT SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Successfully deployed: $DEPLOYED functions"
if [ $FAILED -gt 0 ]; then
    echo "❌ Failed: $FAILED functions"
    exit 1
fi
echo ""
echo "✅ Content generation system updated"
echo "✅ PPT Generator UNTOUCHED ✓"
echo "✅ Images Generator UNTOUCHED ✓"
echo "✅ Lab functions UNTOUCHED ✓"
echo ""
echo "🎉 Content generator ready for use!"
echo ""
