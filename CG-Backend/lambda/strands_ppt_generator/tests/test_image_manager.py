import os
import io
import sys
import pytest

# Ensure the module path includes the directory where image_manager.py lives
THIS_DIR = os.path.dirname(__file__)
PKG_DIR = os.path.abspath(os.path.join(THIS_DIR, '..'))
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)

import image_manager


def create_sample_image_bytes(width=800, height=600, color=(200, 50, 50)):
    """Create a sample RGB PNG image in memory and return raw bytes. Skips test if Pillow missing."""
    if image_manager.Image is None:
        pytest.skip("Pillow not available; skipping image generation tests")
    from PIL import Image
    bio = io.BytesIO()
    im = Image.new('RGB', (width, height), color=color)
    im.save(bio, format='PNG')
    return bio.getvalue()


def test_get_image_size_from_bytes():
    img_bytes = create_sample_image_bytes(800, 600)
    size = image_manager.get_image_size_from_bytes(img_bytes)
    assert size is not None, "Expected to get image size"
    assert size[0] == 800 and size[1] == 600


def test_resize_image_bytes_smaller():
    img_bytes = create_sample_image_bytes(1600, 1200)
    # Request a max size smaller than original
    resized = image_manager.resize_image_bytes(img_bytes, max_width=800, max_height=600, fmt='PNG')
    assert resized is not None, "Resizing returned None"
    new_size = image_manager.get_image_size_from_bytes(resized)
    assert new_size is not None
    assert new_size[0] <= 800 and new_size[1] <= 600


def test_resize_image_bytes_no_upscale():
    img_bytes = create_sample_image_bytes(400, 300)
    # Request a max size larger than original; should not upscale
    resized = image_manager.resize_image_bytes(img_bytes, max_width=800, max_height=600, fmt='PNG')
    assert resized is not None
    new_size = image_manager.get_image_size_from_bytes(resized)
    assert new_size == (400, 300)


def test_create_placeholder_image():
    if image_manager.Image is None:
        pytest.skip("Pillow not available; skipping placeholder generation test")
    ph_bytes = image_manager.create_placeholder_image(text='Test Placeholder', size=(640, 360))
    assert ph_bytes is not None
    size = image_manager.get_image_size_from_bytes(ph_bytes)
    assert size == (640, 360)
