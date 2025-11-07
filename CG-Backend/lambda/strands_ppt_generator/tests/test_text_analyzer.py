import os
import sys

# allow import from module directory when running tests from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from text_analyzer import estimate_text_complexity, shorten_bullets, split_slide_content


def test_estimate_text_complexity():
    slide = {'title': 'Short', 'caption': 'A small caption', 'bullets': ['one two three', 'four five']}
    m = estimate_text_complexity(slide)
    assert m['word_count'] >= 5
    assert m['sentence_count'] >= 1


def test_shorten_bullets():
    bullets = [f'bullet {i}' for i in range(10)]
    short = shorten_bullets(bullets, max_bullets=5)
    assert len(short) == 5
    assert 'bullet' in short[-1]


def test_split_slide_content_with_bullets():
    slide = {'title': 'T', 'bullets': ['word'] * 200}
    slides = split_slide_content(slide, max_words_per_slide=50)
    assert len(slides) >= 3
