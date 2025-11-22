"""
Test HTML to detect overflow slides.
Uses same logic as client-side JavaScript.
"""
from bs4 import BeautifulSoup

def test_html_overflow():
    with open('/tmp/test_layout.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    slides = soup.find_all('div', class_='slide')
    
    print(f"📊 Total slides: {len(slides)}")
    
    overflow_slides = []
    for idx, slide in enumerate(slides, 1):
        # Check if already marked
        if 'overflow-warning' in slide.get('class', []):
            overflow_slides.append({
                'number': idx,
                'title': slide.find('h1', class_='slide-title').text if slide.find('h1', class_='slide-title') else 'No title',
                'pre-marked': True
            })
    
    print(f"\n⚠️  Slides PRE-MARKED with overflow: {len(overflow_slides)}")
    for slide in overflow_slides[:10]:
        print(f"   Slide {slide['number']}: {slide['title']}")
    
    # Estimate content height (rough calculation)
    print(f"\n🔍 Analyzing content heights...")
    potential_overflows = []
    
    for idx, slide in enumerate(slides, 1):
        # Skip title slides
        classes = slide.get('class', [])
        if 'course-title' in classes or 'module-title' in classes or 'lesson-title' in classes:
            continue
        
        # Count elements
        title = slide.find('h1', class_='slide-title')
        subtitle = slide.find('p', class_='slide-subtitle')
        bullets = slide.find_all('ul', class_='bullets')
        images = slide.find_all('img')
        callouts = slide.find_all('div', class_='callout')
        
        # Rough height estimation
        height = 0
        if title:
            height += 80  # Title
        if subtitle:
            height += 60  # Subtitle
        
        # Bullets
        for ul in bullets:
            items = ul.find_all('li')
            height += len(items) * 44  # 44px per bullet
        
        # Images
        for img in images:
            height += 600  # Max image height
        
        # Callouts
        height += len(callouts) * 80
        
        # Check if exceeds 720px
        if height > 720:
            potential_overflows.append({
                'number': idx,
                'title': title.text if title else 'No title',
                'estimated_height': height,
                'bullets': sum(len(ul.find_all('li')) for ul in bullets),
                'images': len(images),
                'callouts': len(callouts)
            })
    
    print(f"\n⚠️  Slides with ESTIMATED overflow ({len(potential_overflows)} total):")
    for slide in potential_overflows[:20]:
        print(f"   Slide {slide['number']}: {slide['estimated_height']}px - {slide['title']}")
        print(f"      Bullets: {slide['bullets']}, Images: {slide['images']}, Callouts: {slide['callouts']}")
    
    return potential_overflows

if __name__ == '__main__':
    test_html_overflow()
