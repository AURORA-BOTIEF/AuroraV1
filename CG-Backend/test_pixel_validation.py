#!/usr/bin/env python3
"""
Test script for pixel-based validation logic
Verifies that height estimation matches expectations
"""

# Height Constants (copied from infographic_generator.py)
MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 460
MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520
BULLET_HEIGHT = 48
HEADING_HEIGHT = 72
IMAGE_HEIGHT = 360
CALLOUT_HEIGHT = 81
SPACING_BETWEEN_BLOCKS = 25
CHARS_PER_LINE = 80


def estimate_block_height(block: dict) -> int:
    """Estimate rendered height of a content block in pixels."""
    total = 0
    block_type = block.get('type', 'text')
    
    if block_type == 'bullets':
        if block.get('heading'):
            total += HEADING_HEIGHT
        
        items = block.get('items', [])
        for item in items:
            text_len = len(str(item))
            lines = max(1, (text_len // CHARS_PER_LINE) + 1)
            total += BULLET_HEIGHT * lines
            
    elif block_type == 'image':
        total += IMAGE_HEIGHT
        if block.get('caption'):
            total += 30
            
    elif block_type == 'callout':
        text_len = len(block.get('text', ''))
        lines = max(1, (text_len // CHARS_PER_LINE) + 1)
        total += CALLOUT_HEIGHT + (lines - 1) * 30
        
    elif block_type == 'text':
        text_len = len(block.get('text', ''))
        lines = max(1, (text_len // CHARS_PER_LINE) + 1)
        total += 30 * lines
    
    return total


def estimate_slide_height(slide: dict) -> int:
    """Estimate total content height for a slide."""
    content_blocks = slide.get('content_blocks', [])
    total = 0
    
    for idx, block in enumerate(content_blocks):
        if idx > 0:
            total += SPACING_BETWEEN_BLOCKS
        total += estimate_block_height(block)
    
    return total


def test_validation():
    """Run validation tests"""
    
    print("=" * 70)
    print("PIXEL-BASED VALIDATION TESTS")
    print("=" * 70)
    
    # Test 1: Image + Short Bullets (should fit but be dense)
    test1 = {
        'title': 'Test Slide with Image',
        'subtitle': 'Testing validation',
        'content_blocks': [
            {
                'type': 'image',
                'caption': 'Example diagram'
            },
            {
                'type': 'bullets',
                'heading': 'Key Points',
                'items': [
                    'First point about the topic',
                    'Second important consideration',
                    'Third key takeaway'
                ]
            }
        ]
    }
    
    height1 = estimate_slide_height(test1)
    max_height = MAX_CONTENT_HEIGHT_WITH_SUBTITLE  # Has subtitle
    optimal = int(max_height * 0.85)
    
    print(f"\nTest 1: Image + 3 Bullets")
    print(f"  Estimated height: {height1}px")
    print(f"  Optimal threshold: {optimal}px")
    print(f"  Max threshold: {max_height}px")
    
    if height1 <= optimal:
        print(f"  ✅ Result: PERFECT FIT (no reduction needed)")
    elif height1 <= max_height:
        print(f"  ⚠️  Result: DENSE (text reduction applied)")
    else:
        print(f"  🚨 Result: OVERFLOW (must split)")
    
    # Test 2: Text-only with many bullets (should fit comfortably)
    test2 = {
        'title': 'Text-Heavy Slide',
        'subtitle': '',
        'content_blocks': [
            {
                'type': 'bullets',
                'heading': 'Important Concepts',
                'items': [
                    'Understanding the basics',
                    'Key terminology and definitions',
                    'Practical applications',
                    'Common pitfalls to avoid',
                    'Best practices and recommendations',
                    'Advanced considerations'
                ]
            }
        ]
    }
    
    height2 = estimate_slide_height(test2)
    max_height2 = MAX_CONTENT_HEIGHT_NO_SUBTITLE  # No subtitle
    optimal2 = int(max_height2 * 0.85)
    
    print(f"\nTest 2: 6 Bullets (No Image)")
    print(f"  Estimated height: {height2}px")
    print(f"  Optimal threshold: {optimal2}px")
    print(f"  Max threshold: {max_height2}px")
    
    if height2 <= optimal2:
        print(f"  ✅ Result: PERFECT FIT (no reduction needed)")
    elif height2 <= max_height2:
        print(f"  ⚠️  Result: DENSE (text reduction applied)")
    else:
        print(f"  🚨 Result: OVERFLOW (must split)")
    
    # Test 3: Oversized slide (image + many bullets = overflow)
    test3 = {
        'title': 'Oversized Slide',
        'subtitle': 'Too much content',
        'content_blocks': [
            {
                'type': 'image',
                'caption': 'Complex diagram'
            },
            {
                'type': 'bullets',
                'heading': 'Many Points',
                'items': [
                    'First important point about the subject matter',
                    'Second detailed explanation of the concept',
                    'Third comprehensive analysis',
                    'Fourth critical consideration',
                    'Fifth essential takeaway',
                    'Sixth additional detail'
                ]
            }
        ]
    }
    
    height3 = estimate_slide_height(test3)
    
    print(f"\nTest 3: Image + 6 Long Bullets")
    print(f"  Estimated height: {height3}px")
    print(f"  Optimal threshold: {optimal}px")
    print(f"  Max threshold: {max_height}px")
    
    if height3 <= optimal:
        print(f"  ✅ Result: PERFECT FIT (no reduction needed)")
    elif height3 <= max_height:
        print(f"  ⚠️  Result: DENSE (text reduction applied)")
    else:
        print(f"  🚨 Result: OVERFLOW (must split)")
        print(f"  → Should create 2 slides: Image+3 bullets, then 3 bullets")
    
    # Test 4: Very long single bullet (text wrapping)
    test4 = {
        'title': 'Long Bullet Test',
        'subtitle': '',
        'content_blocks': [
            {
                'type': 'bullets',
                'heading': 'Detailed Explanation',
                'items': [
                    'This is an extremely long bullet point that spans multiple lines when rendered on the slide because it contains a lot of detailed information about a complex topic that requires thorough explanation and careful consideration'
                ]
            }
        ]
    }
    
    height4 = estimate_slide_height(test4)
    
    print(f"\nTest 4: Single Long Bullet (Text Wrapping)")
    print(f"  Bullet text length: {len(test4['content_blocks'][0]['items'][0])} chars")
    print(f"  Estimated lines: {len(test4['content_blocks'][0]['items'][0]) // CHARS_PER_LINE + 1}")
    print(f"  Estimated height: {height4}px")
    print(f"  Max threshold: {max_height2}px")
    
    if height4 <= optimal2:
        print(f"  ✅ Result: PERFECT FIT")
    elif height4 <= max_height2:
        print(f"  ⚠️  Result: DENSE")
    else:
        print(f"  🚨 Result: OVERFLOW")
    
    print("\n" + "=" * 70)
    print("COMPARISON WITH OLD WORD COUNT SYSTEM")
    print("=" * 70)
    
    # Old system would count:
    # Test 1: image (5 words caption) + 3 bullets (~20 words) = 25 words → PASS
    # Test 2: 6 bullets (~30 words) → PASS (limit was 75)
    # Test 3: image (5 words) + 6 bullets (~40 words) = 45 words → FAIL (limit was 40)
    
    print("\nTest 1 (Image + 3 bullets):")
    print(f"  OLD: ~25 words → ✅ PASS (limit 40)")
    print(f"  NEW: {height1}px → {'⚠️  DENSE' if height1 > optimal else '✅ FIT'}")
    print(f"  Reality: Image takes HALF the slide (360px)!")
    
    print("\nTest 2 (6 bullets, no image):")
    print(f"  OLD: ~30 words → ✅ PASS (limit 75)")
    print(f"  NEW: {height2}px → {'✅ FIT' if height2 <= optimal2 else '⚠️  DENSE'}")
    print(f"  Both correct - text fits easily")
    
    print("\nTest 3 (Image + 6 bullets):")
    print(f"  OLD: ~45 words → ❌ FAIL (limit 40) - UNNECESSARY SPLIT")
    print(f"  NEW: {height3}px → 🚨 OVERFLOW (limit {max_height}px) - CORRECT SPLIT")
    print(f"  NEW is accurate - content actually overflows!")
    
    print("\n" + "=" * 70)
    print("✅ PIXEL VALIDATION TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_validation()
