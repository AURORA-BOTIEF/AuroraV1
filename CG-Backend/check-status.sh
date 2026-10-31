#!/bin/bash
# Quick Start Script for Next Session
# Run this to see the current state and next steps

echo "═══════════════════════════════════════════════════════"
echo "  SIMPLIFIED ARCHITECTURE - STATUS CHECK"
echo "═══════════════════════════════════════════════════════"
echo ""

# Check we're in the right directory
if [ ! -f "template.yaml" ]; then
    echo "❌ Error: Not in CG-Backend directory"
    echo "Run: cd /home/juan/AuroraV1/CG-Backend"
    exit 1
fi

echo "✅ Current directory: $(pwd)"
echo ""

# Check key files exist
echo "📁 Checking files..."
files=(
    "lambda/batch_expander.py"
    "lambda/strands_content_gen/strands_content_gen.py"
    "template.yaml"
    "README_DOCS.md"
    "QUICK_FIX_DEPLOYMENT.md"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (MISSING!)"
    fi
done
echo ""

# Check for PhaseCoordinator references
echo "🔍 Checking for deployment blocker..."
phasecoord_count=$(grep -c "PhaseCoordinator" template.yaml 2>/dev/null || echo "0")
echo "  Found $phasecoord_count PhaseCoordinator references in template.yaml"

if [ "$phasecoord_count" -gt 0 ]; then
    echo ""
    echo "⚠️  DEPLOYMENT BLOCKER DETECTED!"
    echo "  Location: BothTheoryAndLabsBranch (lines ~917-1260)"
    echo "  Fix: See QUICK_FIX_DEPLOYMENT.md"
    echo "  Time: 5 minutes"
    echo ""
    echo "📖 Read: cat QUICK_FIX_DEPLOYMENT.md"
else
    echo "  ✅ No blockers found!"
fi
echo ""

# Show next steps
echo "═══════════════════════════════════════════════════════"
echo "  NEXT STEPS"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "1️⃣  Read documentation:"
echo "    cat README_DOCS.md"
echo ""
echo "2️⃣  Fix deployment blocker (if exists):"
echo "    cat QUICK_FIX_DEPLOYMENT.md"
echo "    # Then edit template.yaml to remove PhaseCoordinator refs"
echo ""
echo "3️⃣  Build and deploy:"
echo "    sam build"
echo "    sam deploy --no-confirm-changeset"
echo ""
echo "4️⃣  Test with 7-module course:"
echo "    # Monitor Step Functions + CloudWatch"
echo "    # Expected: ~45 minutes, 2 concurrent batches"
echo ""
echo "═══════════════════════════════════════════════════════"
echo "📚 All documentation: ls -lh *.md"
echo "═══════════════════════════════════════════════════════"
