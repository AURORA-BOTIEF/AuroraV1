#!/bin/bash
# Build Lambda Layer for Google Gemini API + Vertex AI + Pillow (NO DOCKER!)
# ARM64 architecture for cost savings

set -e

echo "🔨 Building Gemini + Vertex AI Lambda Layer (ARM64)..."

# Clean previous build
rm -rf ./python
rm -f gemini-layer.zip

# Create directory structure
mkdir -p python

# Install dependencies for ARM64
echo "📦 Installing dependencies for ARM64..."
pip install \
    --python-version 3.12 \
    --platform manylinux2014_aarch64 \
    --implementation cp \
    --only-binary=:all: \
    --upgrade \
    --target ./python \
    -r requirements-gemini.txt

# Remove unnecessary files to reduce size
echo "🗑️  Removing unnecessary files..."
cd python
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Remove the massive discovery cache (90MB!) - we don't need it
echo "🗑️  Removing googleapiclient discovery cache (saves 90MB)..."
rm -rf googleapiclient/discovery_cache/documents/* 2>/dev/null || true

cd ..

# Create zip file
echo "📦 Creating layer zip..."
zip -r gemini-layer.zip python/ > /dev/null

# Get size
SIZE=$(du -h gemini-layer.zip | cut -f1)
UNZIP_SIZE=$(unzip -l gemini-layer.zip | tail -1 | awk '{print $1}' | numfmt --to=iec-i --suffix=B)
echo "✅ Layer built successfully!"
echo "📊 Zipped size: $SIZE"
echo "📊 Unzipped size: $UNZIP_SIZE"
echo "📁 Location: $(pwd)/gemini-layer.zip"

# Cleanup
rm -rf ./python

echo "🎉 Gemini + Vertex AI layer ready for deployment!"
