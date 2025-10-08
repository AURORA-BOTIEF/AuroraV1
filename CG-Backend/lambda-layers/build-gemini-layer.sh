#!/bin/bash
# Build Lambda Layer for Google Gemini API + Pillow (NO DOCKER!)
# ARM64 architecture for cost savings

set -e

echo "🔨 Building Gemini Lambda Layer (ARM64)..."

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

# Create zip file
echo "📦 Creating layer zip..."
zip -r gemini-layer.zip python/ > /dev/null

# Get size
SIZE=$(du -h gemini-layer.zip | cut -f1)
echo "✅ Layer built successfully!"
echo "📊 Size: $SIZE"
echo "📁 Location: $(pwd)/gemini-layer.zip"

# Cleanup
rm -rf ./python

echo "🎉 Gemini layer ready for deployment!"
