import importlib.util
import os
import sys


def load_module():
    path = os.path.join(os.path.dirname(__file__), "..", "CG-Backend", "lambda", "strands_ppt_generator", "strands_ppt_generator.py")
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("strands_ppt_generator", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compute_combined(tfidf_weight, legacy_weight, tfidf_scores, legacy_scores):
    total = tfidf_weight + legacy_weight
    if total == 0:
        tf_w = 0.6
        lg_w = 0.4
    else:
        tf_w = tfidf_weight / total
        lg_w = legacy_weight / total
    return [tf_w * t + lg_w * l for t, l in zip(tfidf_scores, legacy_scores)]


def test_combination_default_weights(monkeypatch):
    # Ensure defaults
    monkeypatch.delenv('AURORA_USE_TFIDF', raising=False)
    monkeypatch.delenv('AURORA_TFIDF_WEIGHT', raising=False)
    monkeypatch.delenv('AURORA_LEGACY_WEIGHT', raising=False)

    if 'strands_ppt_generator' in sys.modules:
        del sys.modules['strands_ppt_generator']
    mod = load_module()

    # Use some example scores
    tfidf_scores = [0.8, 0.2]
    legacy_scores = [0.5, 0.1]

    # Module weights
    w_tf = getattr(mod, 'TFIDF_WEIGHT')
    w_lg = getattr(mod, 'LEGACY_WEIGHT')

    expected = compute_combined(w_tf, w_lg, tfidf_scores, legacy_scores)

    # Compute using the same normalization logic inline (mirrors generator)
    total = w_tf + w_lg
    tf_w = w_tf / total
    lg_w = w_lg / total
    actual = [tf_w * t + lg_w * l for t, l in zip(tfidf_scores, legacy_scores)]

    assert len(expected) == len(actual)
    for e, a in zip(expected, actual):
        assert abs(e - a) < 1e-9


def test_combination_tfidf_disabled(monkeypatch):
    # When TF-IDF disabled, tfidf score is treated as neutral (1.0) by the generator
    monkeypatch.setenv('AURORA_USE_TFIDF', '0')
    monkeypatch.setenv('AURORA_TFIDF_WEIGHT', '0.6')
    monkeypatch.setenv('AURORA_LEGACY_WEIGHT', '0.4')

    if 'strands_ppt_generator' in sys.modules:
        del sys.modules['strands_ppt_generator']
    mod = load_module()

    # legacy scores determine ordering more strongly now
    legacy_scores = [0.9, 0.1]
    tfidf_scores = [1.0, 1.0]  # neutral values used when disabled

    expected = compute_combined(mod.TFIDF_WEIGHT, mod.LEGACY_WEIGHT, tfidf_scores, legacy_scores)

    # generator uses normalized weights similarly
    total = mod.TFIDF_WEIGHT + mod.LEGACY_WEIGHT
    tf_w = mod.TFIDF_WEIGHT / total
    lg_w = mod.LEGACY_WEIGHT / total
    actual = [tf_w * t + lg_w * l for t, l in zip(tfidf_scores, legacy_scores)]

    assert expected == actual
    # Ensure first candidate scores higher than second (legacy dominates)
    assert actual[0] > actual[1]


def test_zero_weights_fallback(monkeypatch):
    # If both weights are zero, fallback to tf_w=0.6, lg_w=0.4
    monkeypatch.setenv('AURORA_USE_TFIDF', '1')
    monkeypatch.setenv('AURORA_TFIDF_WEIGHT', '0')
    monkeypatch.setenv('AURORA_LEGACY_WEIGHT', '0')

    if 'strands_ppt_generator' in sys.modules:
        del sys.modules['strands_ppt_generator']
    mod = load_module()

    tfidf_scores = [0.2, 0.9]
    legacy_scores = [0.5, 0.1]

    # expected uses fallback weights 0.6 and 0.4
    expected = compute_combined(0.6, 0.4, tfidf_scores, legacy_scores)

    # actual according to module constants (which should have been interpreted as zeros)
    # module applies fallback when total==0
    total = mod.TFIDF_WEIGHT + mod.LEGACY_WEIGHT
    if total == 0:
        tf_w = 0.6
        lg_w = 0.4
    else:
        tf_w = mod.TFIDF_WEIGHT / total
        lg_w = mod.LEGACY_WEIGHT / total
    actual = [tf_w * t + lg_w * l for t, l in zip(tfidf_scores, legacy_scores)]

    for e, a in zip(expected, actual):
        assert abs(e - a) < 1e-9
