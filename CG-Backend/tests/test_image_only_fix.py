"""
Test to verify fix_image_only_slides works correctly in batch merge scenario.
"""
import json
import sys
sys.path.insert(0, '/home/juan/AuroraV1/CG-Backend/lambda/strands_infographic_generator')
from infographic_generator import fix_image_only_slides


def test_fix_image_only_slides():
    """Test that image-only slides get bullets added."""
    # Simulate actual problematic slide from S3
    slides = [
        {
            "slide_number": 10,
            "title": "¿Qué es Azure Databricks? (cont. 2)",
            "layout_hint": "image-left",
            "content_blocks": [
                {
                    "type": "image",
                    "image_reference": "01-01-0001",
                    "caption": "Azure Databricks - Plataforma integrada"
                }
            ]
        },
        {
            "slide_number": 11,
            "title": "Casos de uso y cargas de trabajo principales (cont. 2)",
            "layout_hint": "image-right",
            "content_blocks": [
                {
                    "type": "image",
                    "image_reference": "01-01-0002",
                    "caption": "Casos de uso de Azure Databricks"
                }
            ]
        }
    ]
    
    # Run fix
    fixed_slides = fix_image_only_slides(slides, is_spanish=True)
    
    # Verify slide 1 (image-left: image first, bullets second)
    assert len(fixed_slides[0]['content_blocks']) == 2, \
        f"Expected 2 blocks, got {len(fixed_slides[0]['content_blocks'])}"
    assert fixed_slides[0]['content_blocks'][0]['type'] == 'image', \
        f"Expected image first for image-left, got {fixed_slides[0]['content_blocks'][0]['type']}"
    assert fixed_slides[0]['content_blocks'][1]['type'] == 'bullets', \
        f"Expected bullets second for image-left, got {fixed_slides[0]['content_blocks'][1]['type']}"
    assert len(fixed_slides[0]['content_blocks'][1]['items']) == 5, \
        f"Expected 5 bullets, got {len(fixed_slides[0]['content_blocks'][1]['items'])}"
    
    # Verify slide 2 (image-right: bullets first, image second)
    assert len(fixed_slides[1]['content_blocks']) == 2, \
        f"Expected 2 blocks, got {len(fixed_slides[1]['content_blocks'])}"
    assert fixed_slides[1]['content_blocks'][0]['type'] == 'bullets', \
        f"Expected bullets first for image-right, got {fixed_slides[1]['content_blocks'][0]['type']}"
    assert fixed_slides[1]['content_blocks'][1]['type'] == 'image', \
        f"Expected image second for image-right, got {fixed_slides[1]['content_blocks'][1]['type']}"
    assert len(fixed_slides[1]['content_blocks'][0]['items']) == 5, \
        f"Expected 5 bullets, got {len(fixed_slides[1]['content_blocks'][0]['items'])}"
    
    print("✅ Test passed: fix_image_only_slides works correctly!")
    print(f"   Fixed {len(fixed_slides)} slides")
    print(f"   Slide 1 (image-left): {fixed_slides[0]['content_blocks'][0]['type']} + {fixed_slides[0]['content_blocks'][1]['type']}")
    print(f"   Slide 2 (image-right): {fixed_slides[1]['content_blocks'][0]['type']} + {fixed_slides[1]['content_blocks'][1]['type']}")
    
    return fixed_slides


def test_actual_s3_structure():
    """Test fix on actual S3 structure file."""
    with open('/tmp/infographic_structure.json', 'r') as f:
        structure = json.load(f)
    
    slides = structure.get('slides', [])
    
    # Count image-only slides before fix
    before_count = sum(
        1 for slide in slides
        if len(slide.get('content_blocks', [])) == 1 
        and slide['content_blocks'][0].get('type') == 'image'
    )
    
    print(f"\n📊 Before fix: {before_count} image-only slides out of {len(slides)} total")
    
    # Apply fix
    fixed_slides = fix_image_only_slides(slides, is_spanish=True)
    
    # Count image-only slides after fix
    after_count = sum(
        1 for slide in fixed_slides
        if len(slide.get('content_blocks', [])) == 1 
        and slide['content_blocks'][0].get('type') == 'image'
    )
    
    print(f"📊 After fix: {after_count} image-only slides (should be 0)")
    
    assert after_count == 0, f"Fix failed! Still have {after_count} image-only slides"
    
    # Show sample fixed slide
    sample_fixed = [s for s in fixed_slides if len(s.get('content_blocks', [])) == 2 
                    and any(b.get('type') == 'image' for b in s['content_blocks'])][0]
    
    print(f"\n✅ Test passed! All image-only slides fixed.")
    print(f"\nSample fixed slide:")
    print(f"  Title: {sample_fixed['title']}")
    print(f"  Layout: {sample_fixed['layout_hint']}")
    print(f"  Blocks: {[b['type'] for b in sample_fixed['content_blocks']]}")
    print(f"  Bullets: {len([b for b in sample_fixed['content_blocks'] if b['type'] == 'bullets'][0]['items'])} items")


if __name__ == '__main__':
    print("="*80)
    print("TEST 1: Basic functionality")
    print("="*80)
    test_fix_image_only_slides()
    
    print("\n" + "="*80)
    print("TEST 2: Actual S3 structure")
    print("="*80)
    test_actual_s3_structure()
    
    print("\n" + "="*80)
    print("ALL TESTS PASSED ✅")
    print("="*80)
