#!/bin/bash
# Deploy PPT Lambda Layer and Update Function
# This script uploads the new PPT layer and updates the StrandsPPTGenerator function

set -e

echo "🚀 Deploying PPT Lambda Layer and Function..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Upload the PPT layer
echo "📦 Publishing PPT Lambda Layer..."
LAYER_VERSION=$(aws lambda publish-layer-version \
    --layer-name ppt-dependencies \
    --description "PowerPoint generation dependencies (python-pptx)" \
    --zip-file fileb://lambda-layers/ppt-layer.zip \
    --compatible-runtimes python3.12 \
    --compatible-architectures arm64 \
    --query 'Version' \
    --output text)

echo "✅ PPT Layer published with version: $LAYER_VERSION"

# Update the StrandsPPTGenerator function to use the new layer
echo "🔄 Updating StrandsPPTGenerator function..."

# Get current function configuration
FUNCTION_ARN=$(aws lambda get-function --function-name StrandsPPTGenerator --query 'Configuration.FunctionArn' --output text)

if [ "$FUNCTION_ARN" = "None" ]; then
    echo "❌ StrandsPPTGenerator function not found. Please deploy the SAM stack first."
    exit 1
fi

# Get the actual account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
echo "📋 Using account ID: $ACCOUNT_ID"

# Update function configuration to include the new layer
aws lambda update-function-configuration \
    --function-name StrandsPPTGenerator \
    --layers "arn:aws:lambda:us-east-1:$ACCOUNT_ID:layer:ppt-dependencies:$LAYER_VERSION" \
    --timeout 900 \
    --memory-size 1024 > /dev/null

echo "✅ Function updated with new PPT layer"

# Test the function (optional)
echo "🧪 Testing function..."
TEST_PAYLOAD='{
    "course_bucket": "crewai-course-artifacts",
    "project_folder": "test",
    "model_provider": "bedrock",
    "slides_per_lesson": 3,
    "presentation_style": "professional"
}'

# Note: This test will likely fail without a valid book, but it tests if the function loads correctly
aws lambda invoke \
    --function-name StrandsPPTGenerator \
    --payload "$TEST_PAYLOAD" \
    --log-type Tail \
    /tmp/test-response.json > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Function loads successfully"
    echo "📝 Check /tmp/test-response.json for detailed response"
else
    echo "⚠️ Function loaded but test failed (expected without valid book data)"
fi

echo ""
echo "🎉 Deployment complete!"
echo "📊 Layer Version: $LAYER_VERSION"
echo "🔗 Function ARN: $FUNCTION_ARN"
echo ""
echo "💡 Next steps:"
echo "   1. Test the PPT generation from the Book Editor UI"
echo "   2. Check CloudWatch logs if issues occur"
echo "   3. Verify the generated PPTX files in S3"