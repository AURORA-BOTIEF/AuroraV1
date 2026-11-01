#!/bin/bash
# Build Lambda Layer for Strands Agents
# Based on: https://strandsagents.com/0.1.x/documentation/docs/user-guide/deploy/deploy_to_aws_lambda/

set -e

echo "🚀 Building Strands Agents Lambda Layer..."

# Clean previous builds
rm -rf ./strands-layer
rm -f ./strands-layer.zip

# Create layer directory structure
mkdir -p ./strands-layer/python

echo "📦 Installing dependencies for ARM64 architecture..."

# Install dependencies for Lambda ARM64 architecture
pip install -r requirements-strands.txt \
    --python-version 3.12 \
    --platform manylinux2014_aarch64 \
    --target ./strands-layer/python \
    --only-binary=:all:

echo "🗜️  Creating ZIP file..."

# Create ZIP
cd strands-layer
zip -r ../strands-layer.zip python/ -q

cd ..

echo "✅ Lambda Layer built successfully!"
echo "📦 File: strands-layer.zip"
echo "📊 Size: $(du -h strands-layer.zip | cut -f1)"
