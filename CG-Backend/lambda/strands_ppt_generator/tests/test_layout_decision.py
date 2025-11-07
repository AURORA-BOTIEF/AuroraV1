import os
import sys

# allow import of module when tests run from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from strands_ppt_generator import decide_layout_choice


def make_slide(words=10, bullets=None, caption=''):
    return {
        'title': 'Test',
        # create bullets so total word count approximates 'words'
        'bullets': bullets or (['word'] * words),
        'caption': caption
        , 'image_url': 'http://example.com/test.png'
    }


def test_image_only_for_very_short_text():
    s = make_slide(words=5)
    # Provide a wide image dim
    provider = lambda url: {'width': 1600, 'height': 900}
    assert decide_layout_choice(s, image_size_provider=provider) == 'image-only'


def test_split_top_for_wide_image_and_medium_text():
    s = make_slide(words=40)
    provider = lambda url: {'width': 1600, 'height': 600}
    assert decide_layout_choice(s, image_size_provider=provider) == 'split-top'


def test_split_right_for_tall_image():
    s = make_slide(words=40)
    provider = lambda url: {'width': 600, 'height': 1200}
    assert decide_layout_choice(s, image_size_provider=provider) == 'split-right'


def test_text_only_for_long_text():
    s = make_slide(words=300)
    provider = lambda url: {'width': 1600, 'height': 900}
    assert decide_layout_choice(s, image_size_provider=provider) == 'text-only'
