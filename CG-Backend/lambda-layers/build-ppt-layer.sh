#!/bin/bash
# Build Lambda Layer for PowerPoint Generation (python-pptx)
# ARM64 architecture for cost savings

set -e

echo "🔨 Building PPT Lambda Layer (ARM64)..."

# Clean previous build
rm -rf ./python
rm -f ppt-layer.zip

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
    -r requirements-ppt.txt

# Create zip file
echo "📦 Creating layer zip..."
zip -r ppt-layer.zip python/ > /dev/null

# Get size
SIZE=$(du -h ppt-layer.zip | cut -f1)
echo "✅ Layer built successfully!"
echo "📊 Size: $SIZE"
echo "📁 Location: $(pwd)/ppt-layer.zip"

# Cleanup
rm -rf ./python

echo "🎉 PPT layer ready for deployment!"