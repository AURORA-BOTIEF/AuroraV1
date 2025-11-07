import importlib.util
import os
import sys
import types


def load_module():
    path = os.path.join(os.path.dirname(__file__), "..", "CG-Backend", "lambda", "strands_ppt_generator", "strands_ppt_generator.py")
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("strands_ppt_generator", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_env_parsing_and_weights(monkeypatch):
    """Verify environment-driven config flags are parsed correctly at import time.

    This test reloads the module under different environment settings and
    asserts the module-level flags `USE_TFIDF`, `TFIDF_WEIGHT`, and
    `LEGACY_WEIGHT` reflect the environment.
    """
    # Case A: defaults (unset) -> expect USE_TFIDF True and default weights
    monkeypatch.delenv('AURORA_USE_TFIDF', raising=False)
    monkeypatch.delenv('AURORA_TFIDF_WEIGHT', raising=False)
    monkeypatch.delenv('AURORA_LEGACY_WEIGHT', raising=False)

    if 'strands_ppt_generator' in sys.modules:
        del sys.modules['strands_ppt_generator']
    mod = load_module()
    assert getattr(mod, 'USE_TFIDF', True) is True
    assert abs(getattr(mod, 'TFIDF_WEIGHT', 0.6) - 0.6) < 1e-6
    assert abs(getattr(mod, 'LEGACY_WEIGHT', 0.4) - 0.4) < 1e-6

    # Case B: disable TF-IDF using several falsey forms
    for false_val in ('0', 'false', 'no', ''):
        monkeypatch.setenv('AURORA_USE_TFIDF', false_val)
        if 'strands_ppt_generator' in sys.modules:
            del sys.modules['strands_ppt_generator']
        m2 = load_module()
        assert getattr(m2, 'USE_TFIDF') is False

    # Case C: set custom weights
    monkeypatch.setenv('AURORA_USE_TFIDF', '1')
    monkeypatch.setenv('AURORA_TFIDF_WEIGHT', '0.75')
    monkeypatch.setenv('AURORA_LEGACY_WEIGHT', '0.25')
    if 'strands_ppt_generator' in sys.modules:
        del sys.modules['strands_ppt_generator']
    m3 = load_module()
    assert abs(getattr(m3, 'TFIDF_WEIGHT') - 0.75) < 1e-6
    assert abs(getattr(m3, 'LEGACY_WEIGHT') - 0.25) < 1e-6
