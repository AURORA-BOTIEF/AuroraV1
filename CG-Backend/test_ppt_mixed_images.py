# Small test harness to exercise the PPT generator with a valid and an invalid image URL
import importlib.util
import sys
from pathlib import Path

# Load the strands_ppt_generator module by path so relative imports fall back to local imports
module_path = Path('CG-Backend/lambda/strands_ppt_generator/strands_ppt_generator.py').resolve()
spec = importlib.util.spec_from_file_location('spg', str(module_path))
spg = importlib.util.module_from_spec(spec)
loader = spec.loader
if loader is None:
    raise RuntimeError('Cannot load module')
loader.exec_module(spg)

# Build a minimal presentation_structure expected by generate_pptx_file
presentation_structure = {
    'presentation_title': 'Mixed Images Test',
    'style': 'professional',
    'slides': [
        {'slide_type': 'title', 'title': 'Mixed Images Test', 'subtitle': 'Testing image handling'},
        {'slide_type': 'image', 'title': 'Valid Image', 'image_url': 'https://via.placeholder.com/1200x600.png?text=Valid+Image', 'caption': 'This should download and be resized.'},
        {'slide_type': 'image', 'title': 'Broken Image', 'image_url': 'http://example.invalid/nonexistent.png', 'caption': 'This should fail and produce a placeholder.'},
        {'slide_type': 'content', 'title': 'Text Backup Slide', 'bullets': ['First point', 'Second', 'Third']}    
    ]
}

# call generator
print('Running generator...')
try:
    pptx_bytes = spg.generate_pptx_file(presentation_structure, book_data={})
    out_path = Path('CG-Backend/test_mixed_images.pptx')
    out_path.write_bytes(pptx_bytes)
    print('✅ Generated:', out_path)
except Exception as e:
    print('❌ Generator failed:', e)
    raise
