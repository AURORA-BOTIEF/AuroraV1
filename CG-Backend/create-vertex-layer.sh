#!/bin/bash

# Creates a Lambda Layer for Vertex AI dependencies
# This separates the large google-cloud-aiplatform SDK from the function code

set -e

LAYER_NAME="vertex-ai-layer"
BUILD_DIR="layer-build"
PYTHON_VERSION="python3.12"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Creating Vertex AI Lambda Layer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Clean previous build
echo "🧹 Cleaning previous build..."
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR/$PYTHON_VERSION/site-packages

# Install Vertex AI SDK
echo "📦 Installing google-cloud-aiplatform..."
pip install --target $BUILD_DIR/$PYTHON_VERSION/site-packages --platform manylinux2014_aarch64 --only-binary=:all: google-cloud-aiplatform>=1.38.0

# Remove unnecessary files to reduce size
echo "🗑️  Removing unnecessary files..."
cd $BUILD_DIR/$PYTHON_VERSION/site-packages
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Remove the massive discovery cache (90MB!) - we don't need it
echo "🗑️  Removing googleapiclient discovery cache (90MB)..."
rm -rf googleapiclient/discovery_cache/documents/* 2>/dev/null || true

cd ../../..

# Create zip
echo "📦 Creating layer package..."
cd $BUILD_DIR
zip -r9 ../${LAYER_NAME}.zip . > /dev/null
cd ..

LAYER_SIZE=$(du -h ${LAYER_NAME}.zip | cut -f1)
echo "   Layer package size: $LAYER_SIZE"

# Publish to AWS Lambda
echo "🚀 Publishing layer to AWS Lambda..."
LAYER_ARN=$(aws lambda publish-layer-version \
    --layer-name $LAYER_NAME \
    --description "Vertex AI SDK for Imagen 4.0 image generation" \
    --license-info "Apache-2.0" \
    --zip-file fileb://${LAYER_NAME}.zip \
    --compatible-runtimes $PYTHON_VERSION \
    --compatible-architectures arm64 \
    --region us-east-1 \
    --query 'LayerVersionArn' \
    --output text)

echo "✅ Layer created successfully!"
echo "   ARN: $LAYER_ARN"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Add this ARN to ImagesGen Lambda in template.yaml:"
echo "   Layers:"
echo "     - $LAYER_ARN"
echo ""
echo "2. Remove google-cloud-aiplatform from lambda/images_gen/requirements.txt"
echo ""
echo "3. Run: bash deploy-with-dependencies.sh full"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
