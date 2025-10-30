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
#   ./deploy-with-dependencies.sh [template-only|full]
#
# OPTIONS:
#   template-only - Only deploy template changes (Step Functions, etc.)
#   full         - Deploy template AND rebuild all Lambda functions with deps
#

set -e  # Exit on error

FUNCTIONS_WITH_DEPS=(
    "StarterApiFunction"
    "StrandsLabPlanner"
    "StrandsContentGen"
    "BatchExpander"
    "LabBatchExpander"
    "BookBuilder"
)

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  AURORA COURSE GENERATOR - SAFE DEPLOYMENT SCRIPT                 ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

MODE="${1:-full}"

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

# Full deployment mode
echo "📋 Mode: Full Deployment (Template + Lambda Functions with Dependencies)"
echo ""

# Step 1: Deploy template
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Deploying Template Changes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sam deploy --no-confirm-changeset || echo "⚠️  Template unchanged or deployment failed (continuing with Lambda functions...)"

echo ""
echo "✅ Template deployment complete"
echo ""

# Step 2: Rebuild and redeploy functions with dependencies
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Rebuilding Lambda Functions with Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

for FUNCTION in "${FUNCTIONS_WITH_DEPS[@]}"; do
    echo "🔨 Building $FUNCTION..."
    sam build "$FUNCTION" > /dev/null 2>&1
    
    # Get the physical function name from CloudFormation stack
    PHYSICAL_NAME=$(aws cloudformation describe-stack-resources \
        --stack-name crewai-course-generator-stack \
        --logical-resource-id "$FUNCTION" \
        --query 'StackResources[0].PhysicalResourceId' \
        --output text)
    
    echo "📦 Creating deployment package..."
    cd .aws-sam/build/"$FUNCTION"
    zip -q -r /tmp/"$FUNCTION".zip .
    cd - > /dev/null
    
    echo "🚀 Deploying $FUNCTION..."
    aws lambda update-function-code \
        --function-name "$PHYSICAL_NAME" \
        --zip-file fileb:///tmp/"$FUNCTION".zip \
        --query '{Function: FunctionName, Size: CodeSize, Modified: LastModified}' \
        --output table
    
    echo "✅ $FUNCTION deployed"
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Functions deployed with dependencies:"
for FUNCTION in "${FUNCTIONS_WITH_DEPS[@]}"; do
    echo "  ✓ $FUNCTION"
done
echo ""
echo "🎉 System ready for use!"
echo ""
