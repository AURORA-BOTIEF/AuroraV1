import os
import sys

# allow importing the lambda package modules in tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CG-Backend', 'lambda'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from strands_ppt_generator import image_text_matcher as matcher


def test_choose_best_image_simple():
    imgs = [
        {'alt_text': 'database migration schema'},
        {'alt_text': 'user interface design mockups'},
        {'alt_text': 'load testing and performance tuning'},
    ]
    # query that should match 'load testing'
    res = matcher.choose_best_image('perform load testing performance', imgs, top_n=2)
    assert res[0][0] == 2
    assert res[0][1] > 0

    # query for database
    res2 = matcher.choose_best_image('run database migrations', imgs, top_n=1)
    assert res2[0][0] == 0
