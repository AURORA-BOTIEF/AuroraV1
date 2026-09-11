#!/usr/bin/env python3
"""
Test Visual Optimizer overflow detection logic locally
"""

from bs4 import BeautifulSoup

# Copy the overflow detection function for testing
def test_overflow_detection():
    """Test overflow detection with sample HTML"""
    
    # Constants matching CSS
    SLIDE_HEIGHT = 720
    MAX_CONTENT_HEIGHT_WITH_SUBTITLE = 460
    MAX_CONTENT_HEIGHT_NO_SUBTITLE = 520
    BULLET_HEIGHT = 44
    IMAGE_HEIGHT = 450
    HEADING_HEIGHT = 65
    CALLOUT_HEIGHT = 75
    SPACING = 20
    
    # Sample slide with 4 bullets + 1 image (should overflow)
    sample_html = """
    <div class="slide">
        <h1 class="slide-title">Test Slide</h1>
        <div class="slide-content">
            <ul class="bullets">
                <li>Bullet point 1 with some text that might wrap</li>
                <li>Bullet point 2 with some text that might wrap</li>
                <li>Bullet point 3 with some text that might wrap</li>
                <li>Bullet point 4 with some text that might wrap</li>
            </ul>
            <div class="image-container">
                <img src="test.png" alt="test">
            </div>
        </div>
    </div>
    """
    
    soup = BeautifulSoup(sample_html, 'html.parser')
    slide = soup.find('div', class_='slide')
    
    # Calculate content height
    content_height = 0
    content_blocks = slide.find_all(['ul', 'div'], class_=['bullets', 'image-container'])
    
    for block_idx, block in enumerate(content_blocks):
        if block_idx > 0:
            content_height += SPACING
        
        # Bullet lists
        if 'bullets' in block.get('class', []):
            bullets = block.find_all('li')
            for bullet in bullets:
                text_len = len(bullet.get_text(strip=True))
                lines = max(1, (text_len // 90) + 1)
                content_height += BULLET_HEIGHT * lines
        
        # Images
        elif 'image-container' in block.get('class', []):
            content_height += IMAGE_HEIGHT
    
    max_height = MAX_CONTENT_HEIGHT_NO_SUBTITLE
    overflow_threshold = max_height * 1.10
    
    print(f"Test Slide:")
    print(f"  Content height: {content_height}px")
    print(f"  Max height: {max_height}px")
    print(f"  Overflow threshold (110%): {overflow_threshold}px")
    print(f"  Overflow: {'YES' if content_height > overflow_threshold else 'NO'}")
    print(f"  Excess: {content_height - max_height}px")
    
    # Expected: 4 bullets (~44px each = 176px) + 1 image (450px) + spacing (20px) = ~646px
    # This should overflow (646px > 572px threshold)
    
    return content_height > overflow_threshold

if __name__ == '__main__':
    result = test_overflow_detection()
    print(f"\n✅ Test passed: Overflow detected correctly" if result else "\n❌ Test failed")
