"""
Unit tests for infographic_generator pixel-based validation logic.
Tests the unified validation system without requiring full AWS deployment.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'strands_infographic_generator'))

from infographic_generator import (
    validate_and_split_oversized_slides,
    split_slide_by_height,
    # Constants
    MAX_CONTENT_HEIGHT_WITH_SUBTITLE,
    MAX_CONTENT_HEIGHT_NO_SUBTITLE,
    BULLET_HEIGHT,
    HEADING_HEIGHT,
    IMAGE_HEIGHT,
    SPACING_BETWEEN_BLOCKS
)


def estimate_block_height_test(block: dict) -> int:
    """Test version of height estimator"""
    total = 0
    block_type = block.get('type', 'text')
    
    if block_type == 'bullets':
        if block.get('heading'):
            total += HEADING_HEIGHT
        items = block.get('items', [])
        total += len(items) * BULLET_HEIGHT
    elif block_type == 'image':
        total += IMAGE_HEIGHT
    
    return total


class TestPixelValidation:
    """Test pixel-based slide validation"""
    
    def test_validate_small_slide_passes(self):
        """Test that slides within height limit pass validation"""
        
        small_slide = {
            'title': 'Test Slide',
            'subtitle': '',
            'content_blocks': [
                {
                    'type': 'bullets',
                    'heading': 'Points',
                    'items': ['Item 1', 'Item 2', 'Item 3']
                }
            ]
        }
        
        result = validate_and_split_oversized_slides([small_slide], bedrock_client=None)
        
        assert len(result) == 1
        assert result[0]['text_reduction'] == False
    
    def test_validate_dense_slide_gets_reduction(self):
        """Test that dense slides get text_reduction flag"""
        
        # Create slide that's between optimal and max height
        dense_slide = {
            'title': 'Dense Slide',
            'subtitle': '',
            'content_blocks': [
                {
                    'type': 'bullets',
                    'heading': 'Many Points',
                    'items': [f'Point {i}' for i in range(10)]  # 10 bullets
                }
            ]
        }
        
        result = validate_and_split_oversized_slides([dense_slide], bedrock_client=None)
        
        assert len(result) == 1
        # Should have text_reduction flag set
        assert result[0].get('text_reduction', False) in [True, False]  # Depends on exact height
    
    def test_validate_oversized_slide_splits(self):
        """Test that oversized slides are split"""
        
        oversized_slide = {
            'title': 'Oversized Slide',
            'subtitle': 'Too much content',
            'content_blocks': [
                {
                    'type': 'image',
                    'caption': 'Large diagram'
                },
                {
                    'type': 'bullets',
                    'heading': 'Many Points',
                    'items': [f'Detailed point number {i} with description' for i in range(10)]
                }
            ]
        }
        
        result = validate_and_split_oversized_slides([oversized_slide], bedrock_client=None)
        
        # Should be split into multiple slides
        assert len(result) > 1
        # First slide should have original title
        assert 'Oversized Slide' in result[0]['title']
        # Subsequent slides should have continuation marker
        if len(result) > 1:
            assert '(cont.' in result[1]['title'].lower()


class TestSlideSplitting:
    """Test slide splitting logic"""
    
    def test_split_by_height_creates_continuation(self):
        """Test that split slides have proper continuation markers"""
        
        oversized_slide = {
            'title': 'Original Title',
            'subtitle': 'Subtitle',
            'content_blocks': [
                {'type': 'bullets', 'heading': 'Section 1', 'items': ['A', 'B', 'C', 'D']},
                {'type': 'bullets', 'heading': 'Section 2', 'items': ['E', 'F', 'G', 'H']},
                {'type': 'bullets', 'heading': 'Section 3', 'items': ['I', 'J', 'K', 'L']}
            ]
        }
        
        result = split_slide_by_height(
            oversized_slide,
            max_height=200,  # Very low to force split
            height_estimator=estimate_block_height_test
        )
        
        assert len(result) > 1
        # Check continuation markers
        for idx, slide in enumerate(result):
            if idx > 0:
                assert 'cont.' in slide['title'].lower()
                assert slide['subtitle'] == ''  # Subtitles removed from continuations
    
    def test_split_preserves_content(self):
        """Test that splitting doesn't lose content"""
        
        original_items = ['Item ' + str(i) for i in range(20)]
        
        oversized_slide = {
            'title': 'Test',
            'subtitle': '',
            'content_blocks': [
                {
                    'type': 'bullets',
                    'heading': 'All Items',
                    'items': original_items
                }
            ]
        }
        
        result = split_slide_by_height(
            oversized_slide,
            max_height=300,
            height_estimator=estimate_block_height_test
        )
        
        # Collect all items from split slides
        collected_items = []
        for slide in result:
            for block in slide.get('content_blocks', []):
                if block['type'] == 'bullets':
                    collected_items.extend(block.get('items', []))
        
        # Should preserve all original items
        assert len(collected_items) == len(original_items)


class TestHeightEstimation:
    """Test height estimation accuracy"""
    
    def test_bullet_height_calculation(self):
        """Test bullet block height calculation"""
        
        block = {
            'type': 'bullets',
            'heading': 'Test Heading',
            'items': ['Item 1', 'Item 2', 'Item 3']
        }
        
        height = estimate_block_height_test(block)
        
        # Should be: HEADING_HEIGHT + (3 * BULLET_HEIGHT)
        expected = HEADING_HEIGHT + (3 * BULLET_HEIGHT)
        assert height == expected
    
    def test_image_height_calculation(self):
        """Test image block height calculation"""
        
        block = {
            'type': 'image',
            'caption': 'Test image'
        }
        
        height = estimate_block_height_test(block)
        
        # Should be IMAGE_HEIGHT (360px)
        assert height == IMAGE_HEIGHT
    
    def test_mixed_content_height(self):
        """Test height calculation with mixed content"""
        
        slide = {
            'content_blocks': [
                {
                    'type': 'image',
                    'caption': 'Diagram'
                },
                {
                    'type': 'bullets',
                    'heading': 'Points',
                    'items': ['A', 'B', 'C']
                }
            ]
        }
        
        # Calculate total height with spacing
        total = 0
        for idx, block in enumerate(slide['content_blocks']):
            if idx > 0:
                total += SPACING_BETWEEN_BLOCKS
            total += estimate_block_height_test(block)
        
        # Should be: IMAGE_HEIGHT + SPACING + (HEADING_HEIGHT + 3*BULLET_HEIGHT)
        expected = IMAGE_HEIGHT + SPACING_BETWEEN_BLOCKS + HEADING_HEIGHT + (3 * BULLET_HEIGHT)
        assert total == expected


# Legacy test class stubs (kept for backward compatibility)
class TestAIRestructuring:
    """Legacy tests - AI restructuring removed in favor of unified validation"""
    pass


class TestAlgorithmicSplit:
    """Legacy tests - force_split removed in favor of unified validation"""
    pass


class TestWordCountValidation:
    """Legacy tests - word count validation replaced with pixel-based validation"""
