import io
import os
import sys
import importlib.util
from types import ModuleType

# Helper to load a module from a file path
def load_module_from_path(name: str, path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_one_by_one_png_bytes():
    try:
        from PIL import Image
        import io
        im = Image.new('RGB', (64, 64), color=(200, 200, 200))
        out = io.BytesIO()
        im.save(out, format='PNG')
        return out.getvalue()
    except Exception:
        # Fallback tiny PNG (1x1) binary header - but better to rely on Pillow in dev env
        return b''


def test_generate_pptx_integration(monkeypatch, tmp_path):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    le_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'layout_engine.py')
    im_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'image_manager.py')

    # Load modules and ensure they are available for import inside the generator
    layout_engine = load_module_from_path('layout_engine', le_path)
    image_manager = load_module_from_path('image_manager', im_path)

    # Monkeypatch the layout engine to force a deterministic layout choice
    def fake_decide(slide_data, image_size_provider=None):
        return 'image-only'

    layout_engine.decide_layout_choice = fake_decide

    # Monkeypatch image_manager.fetch_image_bytes to return a small PNG so generator doesn't call network
    png = make_one_by_one_png_bytes()
    def fake_fetch(url, s3_client=None):
        return png

    # Ensure image_manager has the fetch function we expect
    image_manager.fetch_image_bytes = fake_fetch

    # Now load generator
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    # Build a minimal presentation structure: title + single content slide referencing an image URL
    presentation_structure = {
        'presentation_title': 'Test Presentation',
        'style': 'modern',
        'slides': [
            {'slide_number': 1, 'slide_type': 'title', 'title': 'Test Presentation', 'subtitle': 'Integration Test'},
            {
                'slide_number': 2,
                'slide_type': 'content',
                'title': 'Image First Slide',
                'bullets': ['Point A', 'Point B'],
                'image_url': 'http://example.test/image.png',
                'image_reference': 'USE_IMAGE: Test'
            }
        ]
    }

    # Run generator - this should return PPTX bytes
    pptx_bytes = gen.generate_pptx_file(presentation_structure, book_data={})
    assert isinstance(pptx_bytes, (bytes, bytearray))
    # PPTX files are zip archives starting with PK
    assert pptx_bytes[:2] == b'PK'

    # Optionally write to tmp to aid debugging on failure
    out_path = tmp_path / 'test_output.pptx'
    out_path.write_bytes(pptx_bytes)
    assert out_path.exists()
