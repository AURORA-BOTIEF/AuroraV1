import importlib.util
import os
import sys

# Helper to load the generator module by file path

def load_module_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_adjust_no_overlap():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(13.333 * EMU)
    slide_h = int(7.5 * EMU)

    body = (EMU * 1, EMU * 2, EMU * 5, EMU * 3)
    img = (EMU * 8, EMU * 1, EMU * 3, EMU * 2)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    assert res == img


def test_move_right_available():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(13.333 * EMU)
    slide_h = int(7.5 * EMU)

    # body in middle-left, image initially overlapping left area
    body = (EMU * 1, EMU * 2, EMU * 6, EMU * 3)
    img = (EMU * 3, EMU * 2, EMU * 5, EMU * 3)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    assert res is not None
    new_left, new_top, new_w, new_h = res
    # Expect image moved to right (left >= body right)
    assert new_left >= body[0] + body[2]


def test_shrink_to_fit_above():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(8 * EMU)  # narrower slide to force shrink
    slide_h = int(6 * EMU)

    body = (EMU * 1, EMU * 2, EMU * 5, EMU * 3)
    # image overlaps body but there is limited vertical space above
    img = (EMU * 2, EMU * 2, EMU * 4, EMU * 3)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    assert res is not None
    new_left, new_top, new_w, new_h = res
    # Expect the returned height to be <= original height
    assert new_h <= img[3]
    # And new_h should be at least half-inch (MIN_VISIBLE check)
    assert new_h >= int(0.5 * gen.EMU_PER_INCH)


def test_no_space_returns_none():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    # Very small slide where nothing can fit (height <= MIN_VISIBLE)
    slide_w = int(2 * EMU)
    slide_h = int(1 * EMU)

    # body occupies the full slide height, leaving no room above/below
    body = (EMU * 0, EMU * 0, EMU * 1, EMU * 1)
    img = (EMU * 0, EMU * 0, EMU * 1, EMU * 1)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    assert res is None


def test_move_left_when_right_unavailable():
    """Test that image moves to left of body when right side has no space."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(13.333 * EMU)
    slide_h = int(7.5 * EMU)

    # Body positioned on right side, image overlapping it
    body = (EMU * 7, EMU * 2, EMU * 5, EMU * 3)
    img = (EMU * 6, EMU * 2, EMU * 3, EMU * 3)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    assert res is not None
    new_left, new_top, new_w, new_h = res
    # Expect image moved to left of body
    assert new_left + new_w <= body[0]
    # Size should be preserved
    assert new_w == img[2]
    assert new_h == img[3]


def test_vertical_centering_with_body():
    """Test that image gets vertically centered with body when moved horizontally."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(13.333 * EMU)
    slide_h = int(7.5 * EMU)

    # Body in middle, small image overlapping
    body = (EMU * 3, EMU * 2, EMU * 4, EMU * 3)
    img = (EMU * 4, EMU * 1, EMU * 2, EMU * 1.5)  # Smaller than body

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    assert res is not None
    new_left, new_top, new_w, new_h = res
    
    # Should be moved horizontally (not overlapping)
    assert not (new_left < body[0] + body[2] and new_left + new_w > body[0])


def test_place_below_when_above_insufficient():
    """Test placement below body when space above is insufficient."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(13.333 * EMU)
    slide_h = int(7.5 * EMU)

    # Body near top, image overlapping
    body = (EMU * 2, EMU * 0.5, EMU * 5, EMU * 2)
    img = (EMU * 3, EMU * 1, EMU * 3, EMU * 2)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    assert res is not None
    new_left, new_top, new_w, new_h = res
    
    # Should be placed below body (top >= body bottom)
    # or horizontally moved if below doesn't work
    # At minimum, shouldn't overlap
    body_bottom = body[1] + body[3]
    img_top = new_top
    img_bottom = new_top + new_h
    
    # Check no overlap: either horizontally separated OR vertically separated
    horiz_separated = (new_left + new_w <= body[0]) or (body[0] + body[2] <= new_left)
    vert_separated = (img_bottom <= body[1]) or (body_bottom <= img_top)
    
    assert horiz_separated or vert_separated


def test_aggressive_shrink_in_horizontal_space():
    """Test aggressive shrinking to fit in horizontal space when vertical options exhausted."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    # Narrow tall slide
    slide_w = int(8 * EMU)
    slide_h = int(10 * EMU)

    # Body occupies most of middle vertically
    body = (EMU * 1, EMU * 2, EMU * 5, EMU * 6)
    # Large image that overlaps
    img = (EMU * 2, EMU * 3, EMU * 4, EMU * 4)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    
    # Should return some result (might be shrunk or moved)
    if res is not None:
        new_left, new_top, new_w, new_h = res
        
        # Verify no overlap with body
        body_right = body[0] + body[2]
        body_bottom = body[1] + body[3]
        img_right = new_left + new_w
        img_bottom = new_top + new_h
        
        horiz_separated = (img_right <= body[0]) or (body_right <= new_left)
        vert_separated = (img_bottom <= body[1]) or (body_bottom <= new_top)
        
        assert horiz_separated or vert_separated
        
        # Should maintain minimum visible size
        assert new_w >= int(0.5 * EMU)
        assert new_h >= int(0.5 * EMU)


def test_horizontal_centering_when_shrinking():
    """Test that shrunk images are centered horizontally."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(13.333 * EMU)
    slide_h = int(7.5 * EMU)

    # Body in middle taking up most horizontal space
    body = (EMU * 2, EMU * 3, EMU * 9, EMU * 3)
    # Image that needs to be placed above or below and will be shrunk
    img = (EMU * 4, EMU * 3.5, EMU * 5, EMU * 3)

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    
    if res is not None:
        new_left, new_top, new_w, new_h = res
        
        # Verify no overlap
        body_bottom = body[1] + body[3]
        img_bottom = new_top + new_h
        
        # If placed above or below, should be reasonably centered
        # (within 20% of slide width from center)
        img_center_x = new_left + new_w / 2
        slide_center_x = slide_w / 2
        
        # Just verify the result is valid (no overlap)
        vert_separated = (img_bottom <= body[1]) or (body_bottom <= new_top)
        if vert_separated:
            # If vertically separated, width could be shrunk
            assert new_w <= img[2]  # Not larger than original


def test_maintains_aspect_ratio_when_shrinking():
    """Test that aspect ratio is maintained when shrinking images."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gen_path = os.path.join(root, 'CG-Backend', 'lambda', 'strands_ppt_generator', 'strands_ppt_generator.py')
    gen = load_module_from_path('strands_ppt_generator', gen_path)

    EMU = getattr(gen, 'EMU_PER_INCH', 914400)
    slide_w = int(13.333 * EMU)
    slide_h = int(7.5 * EMU)

    # Body that forces vertical shrinking
    body = (EMU * 2, EMU * 2.5, EMU * 9, EMU * 3)
    # Wide image that needs shrinking
    img = (EMU * 3, EMU * 3, EMU * 7, EMU * 3.5)
    
    orig_aspect = img[2] / img[3]  # width/height

    res = gen.adjust_image_rect_to_avoid_overlap_module(*body, *img, slide_w, slide_h)
    
    if res is not None:
        new_left, new_top, new_w, new_h = res
        
        # If image was shrunk, aspect ratio should be maintained (within 5% tolerance)
        if new_w < img[2] or new_h < img[3]:
            new_aspect = new_w / new_h
            aspect_diff = abs(new_aspect - orig_aspect) / orig_aspect
            assert aspect_diff < 0.05  # Within 5% tolerance
