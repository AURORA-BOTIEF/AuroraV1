#!/bin/bash
# Test HTML-First Architecture
# ==============================
# This script tests the new HTML-first implementation
# Expected result: Production-ready HTML with ZERO overflow

set -e

PROJECT_FOLDER="251031-databricks-ciencia-datos"
COURSE_BUCKET="aurora-course-generator"

echo "=========================================="
echo "HTML-FIRST ARCHITECTURE TEST"
echo "=========================================="
echo ""
echo "Testing new architecture with guaranteed zero overflow"
echo ""

# Test 1: Invoke Lambda directly with html_first=true
echo "🧪 Test 1: Direct Lambda invocation (html_first=true)"
echo "----------------------------------------------"

aws lambda invoke \
  --function-name StrandsInfographicGenerator \
  --payload '{
    "course_bucket": "'$COURSE_BUCKET'",
    "project_folder": "'$PROJECT_FOLDER'",
    "model_provider": "bedrock",
    "slides_per_lesson": 5,
    "style": "professional",
    "html_first": true,
    "lesson_start": 1,
    "lesson_end": 2
  }' \
  /tmp/html_first_response.json

echo ""
echo "✅ Lambda response:"
cat /tmp/html_first_response.json | python3 -m json.tool

# Extract HTML S3 key from response
HTML_KEY=$(cat /tmp/html_first_response.json | python3 -c "import json, sys; data=json.load(sys.stdin); body=json.loads(data.get('body', '{}')); print(body.get('html_s3_key', ''))")

if [ -z "$HTML_KEY" ]; then
  echo "❌ Error: No HTML key found in response"
  exit 1
fi

echo ""
echo "📥 Downloading HTML output..."
aws s3 cp "s3://$COURSE_BUCKET/$HTML_KEY" /tmp/html_first_output.html

echo ""
echo "📊 HTML Statistics:"
echo "  - File size: $(wc -c < /tmp/html_first_output.html) bytes"
echo "  - Total slides: $(grep -c 'class="slide"' /tmp/html_first_output.html || echo 0)"
echo "  - Overflow slides: $(grep -c 'class="slide-content overflow"' /tmp/html_first_output.html || echo 0)"

OVERFLOW_COUNT=$(grep -c 'class="slide-content overflow"' /tmp/html_first_output.html || echo 0)

echo ""
if [ "$OVERFLOW_COUNT" -eq 0 ]; then
  echo "✅ SUCCESS: Zero overflow slides! HTML-first architecture working perfectly!"
else
  echo "⚠️  WARNING: Found $OVERFLOW_COUNT overflow slides"
  echo "   (This should be investigated)"
fi

echo ""
echo "🌐 HTML file location:"
echo "   s3://$COURSE_BUCKET/$HTML_KEY"
echo ""
echo "   Or open in browser:"
echo "   https://$COURSE_BUCKET.s3.amazonaws.com/$HTML_KEY"

echo ""
echo "=========================================="
echo "TEST COMPLETE"
echo "=========================================="
