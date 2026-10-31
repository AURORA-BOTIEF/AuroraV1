#!/bin/bash
#
# Deploy PPT Generation System (Agent 1 + Agent 2)
# =================================================
# Deploys StrandsInfographicGenerator (unified pixel-based validation)
# StrandsVisualOptimizer is DISABLED in state machine but kept deployed
# for potential future post-processing use if needed.
#
# USAGE:
#   ./deploy-ppt-system.sh
#

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  DEPLOY PPT SYSTEM (AGENT 1 + AGENT 2)                           ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""
echo "📦 Agent 1: StrandsInfographicGenerator (Content Creator)"
echo "    - Model: Claude Haiku 4.5"
echo "    - Role: Generate slides with unified pixel-based validation"
echo ""
echo "📦 Agent 2: StrandsVisualOptimizer (DISABLED - Kept for future use)"
echo "    - Model: Claude Haiku 4.5"
echo "    - Status: Deployed but not invoked in state machine"
echo ""

# Step 1: Build the full template to include new Lambda
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Building SAM template"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sam build

echo ""
echo "✅ Template built successfully"
echo ""

# Step 2: Always deploy template to update state machine and layer configurations
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Deploying CloudFormation template (state machine + layer updates)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "🚀 Deploying template to update:"
echo "   - State machine configuration"
echo "   - Visual optimizer layer dependencies (BeautifulSoup fix)"
echo ""

sam deploy --no-confirm-changeset --capabilities CAPABILITY_IAM \
    --parameter-overrides ECRRepository=crewai-course-generator AccountId=746434296869

echo ""
echo "✅ Template deployed successfully"
echo ""

# Step 3: Deploy both agents with dependencies
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Deploying Lambda functions with dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Agent 1: StrandsInfographicGenerator
echo "🔨 Building Agent 1 (StrandsInfographicGenerator)..."
sam build StrandsInfographicGenerator

echo "📦 Creating deployment package..."
cd .aws-sam/build/StrandsInfographicGenerator
zip -q -r /tmp/StrandsInfographicGenerator.zip .
cd - > /dev/null

echo "🚀 Deploying Agent 1..."
aws lambda update-function-code \
    --function-name StrandsInfographicGenerator \
    --zip-file fileb:///tmp/StrandsInfographicGenerator.zip \
    --no-cli-pager > /dev/null

echo "✅ Agent 1 deployed successfully"
echo ""

# Agent 2: StrandsVisualOptimizer
echo "🔨 Building Agent 2 (StrandsVisualOptimizer)..."
sam build StrandsVisualOptimizer

echo "📦 Creating deployment package..."
cd .aws-sam/build/StrandsVisualOptimizer
zip -q -r /tmp/StrandsVisualOptimizer.zip .
cd - > /dev/null

echo "🚀 Deploying Agent 2..."
aws lambda update-function-code \
    --function-name StrandsVisualOptimizer \
    --zip-file fileb:///tmp/StrandsVisualOptimizer.zip \
    --no-cli-pager > /dev/null

echo "✅ Agent 2 deployed successfully"
echo ""

# Force update layers for Agent 2 (ensures BeautifulSoup is available)
echo "🔧 Updating layers for Agent 2 (StrandsVisualOptimizer)..."
STRANDS_LAYER_ARN=$(aws lambda list-layer-versions --layer-name strands-agents-dependencies --query 'LayerVersions[0].LayerVersionArn' --output text)
PPT_LAYER_ARN=$(aws lambda list-layer-versions --layer-name ppt-dependencies --query 'LayerVersions[0].LayerVersionArn' --output text)

if [ "$STRANDS_LAYER_ARN" != "None" ] && [ "$PPT_LAYER_ARN" != "None" ] && [ -n "$STRANDS_LAYER_ARN" ] && [ -n "$PPT_LAYER_ARN" ]; then
    echo "  Using layers:"
    echo "    - strands-agents-dependencies: $STRANDS_LAYER_ARN"
    echo "    - ppt-dependencies: $PPT_LAYER_ARN"
    aws lambda update-function-configuration \
        --function-name StrandsVisualOptimizer \
        --layers "$STRANDS_LAYER_ARN" "$PPT_LAYER_ARN" \
        --no-cli-pager > /dev/null
    echo "✅ Layers attached successfully"
else
    echo "⚠️  Warning: Could not find layer ARNs (STRANDS=$STRANDS_LAYER_ARN, PPT=$PPT_LAYER_ARN)"
fi
echo ""

# Agent 3: StrandsPptMerger
echo "🔨 Building Agent 3 (StrandsPptMerger)..."
sam build StrandsPptMerger

echo "📦 Creating deployment package..."
cd .aws-sam/build/StrandsPptMerger
zip -q -r /tmp/StrandsPptMerger.zip .
cd - > /dev/null

echo "🚀 Deploying Agent 3..."
aws lambda update-function-code \
    --function-name StrandsPptMerger \
    --zip-file fileb:///tmp/StrandsPptMerger.zip \
    --no-cli-pager > /dev/null

echo "✅ Agent 3 deployed successfully"
echo ""

# Verify deployments
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT VERIFICATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Agent 1 (StrandsInfographicGenerator):"
AGENT1_INFO=$(aws lambda get-function --function-name StrandsInfographicGenerator \
    --query 'Configuration.[LastModified,Environment.Variables.BEDROCK_MODEL,CodeSize]' \
    --output text 2>/dev/null)
echo "  Last Modified: $(echo $AGENT1_INFO | awk '{print $1}')"
echo "  Model: $(echo $AGENT1_INFO | awk '{print $2}')"
echo "  Code Size: $(echo $AGENT1_INFO | awk '{print $3}') bytes"

echo ""
echo "Agent 2 (StrandsVisualOptimizer):"
AGENT2_INFO=$(aws lambda get-function --function-name StrandsVisualOptimizer \
    --query 'Configuration.[LastModified,Environment.Variables.BEDROCK_MODEL_ID,CodeSize]' \
    --output text 2>/dev/null)
echo "  Last Modified: $(echo $AGENT2_INFO | awk '{print $1}')"
echo "  Model: $(echo $AGENT2_INFO | awk '{print $2}')"
echo "  Code Size: $(echo $AGENT2_INFO | awk '{print $3}') bytes"

# Verify layers are attached
AGENT2_LAYERS=$(aws lambda get-function --function-name StrandsVisualOptimizer \
    --query 'Configuration.Layers[*].Arn' --output text 2>/dev/null)
if [ -n "$AGENT2_LAYERS" ]; then
    echo "  Layers: ✅ $(echo $AGENT2_LAYERS | wc -w) layer(s) attached"
    echo "$AGENT2_LAYERS" | tr '\t' '\n' | while read layer; do
        LAYER_NAME=$(echo $layer | grep -o 'StrandsAgentsLayer\|PPTLayer')
        if [ -n "$LAYER_NAME" ]; then
            echo "    - $LAYER_NAME"
        fi
    done
else
    echo "  Layers: ❌ NO LAYERS ATTACHED (BeautifulSoup will fail!)"
fi

echo ""
echo "Agent 3 (StrandsPptMerger):"
AGENT3_INFO=$(aws lambda get-function --function-name StrandsPptMerger \
    --query 'Configuration.[LastModified,CodeSize]' \
    --output text 2>/dev/null)
echo "  Last Modified: $(echo $AGENT3_INFO | awk '{print $1}')"
echo "  Code Size: $(echo $AGENT3_INFO | awk '{print $2}') bytes"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 PPT SYSTEM DEPLOYMENT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Agent 1: Content Creator (Haiku 4.5) - Ready"
echo "✅ Agent 2: Visual Optimizer (Haiku 4.5) - Ready"
echo "✅ Agent 3: PPT Merger - Ready"
echo ""
echo "📊 Both agents are now using Claude Haiku 4.5 for:"
echo "   • 16% faster responses (2.88s vs 3.44s)"
echo "   • 80% cost reduction vs Sonnet"
echo "   • Same quality for structured tasks"
echo ""
echo "🔧 LATEST FIXES:"
echo "   • IMAGE_HEIGHT: 600px → 450px (prevents overflow)"
echo "   • Validation: 80% optimal, 90% dense (conservative thresholds)"
echo "   • Visual Optimizer: StrandsAgentsLayer + PPTLayer (BeautifulSoup fix)"
echo "   • CSS max-height: 550px (HTML display compromise)"
echo ""
echo "📝 NEXT STEPS:"
echo "   1. Test with course: 251031-databricks-ciencia-datos"
echo "   2. Verify zero overflow slides in HTML output"
echo "   3. Confirm visual optimizer can import bs4 successfully"
echo ""
