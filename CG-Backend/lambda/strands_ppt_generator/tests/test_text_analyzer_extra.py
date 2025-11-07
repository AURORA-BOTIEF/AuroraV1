import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from text_analyzer import shorten_bullets, split_slide_content


def test_shorten_bullets_key_terms():
    bullets = [
        'Install the database and configure settings',
        'Create admin user and seed data',
        'Run migrations and verify schema',
        'Configure monitoring and alerting',
        'Perform load testing and tuning',
        'Document runbooks and ops procedures',
        'Rollout plan and rollback steps'
    ]
    short = shorten_bullets(bullets, max_bullets=4)
    assert len(short) == 4
    # last bullet should include 'Also covers' or at least mention key terms like 'load' or 'monitoring'
    assert 'Also covers' in short[-1] or 'load' in short[-1] or 'monitor' in short[-1]


def test_split_long_single_bullet():
    long_bullet = 'This is a long bullet. It contains several sentences. It should be split across slides properly.'
    slide = {'title': 'LongBullet', 'bullets': [long_bullet]}
    slides = split_slide_content(slide, max_words_per_slide=6)
    # Expect multiple slides because long_bullet has >6 words
    assert len(slides) >= 2
    # Image should only be kept on first split if present
    slide_with_image = {'title': 'LongBullet', 'bullets': [long_bullet], 'image_url': 'http://x'}
    slides2 = split_slide_content(slide_with_image, max_words_per_slide=6)
    assert slides2[0].get('image_url') == 'http://x'
    if len(slides2) > 1:
        assert 'image_url' not in slides2[1]
