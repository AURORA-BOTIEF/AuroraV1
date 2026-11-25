# -*- coding: utf-8 -*-
"""Smoke test: deck_builder imports from its packaged folder, not the repo root."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
PKG = BACKEND / "lambda" / "deck_builder"
CANONICAL = BACKEND / "ppt_quality.py"
PACKAGED = [
    BACKEND / "lambda" / "deck_builder" / "ppt_quality.py",
    BACKEND / "lambda" / "ppt_merger" / "ppt_quality.py",
    BACKEND / "lambda" / "strands_infographic_generator" / "ppt_quality.py",
]


def test_ppt_quality_copies_match_canonical():
    src = CANONICAL.read_bytes()
    assert src, "canonical ppt_quality.py is empty"
    for dest in PACKAGED:
        assert dest.is_file(), f"missing packaged ppt_quality.py: {dest}"
        assert dest.read_bytes() == src, f"stale packaged copy (run sync_ppt_quality_packages.py): {dest}"


def test_deck_builder_imports_from_packaged_folder():
    """Import deck_builder with only its CodeUri on sys.path.

    The CG-Backend root is removed so a packaging miss cannot be hidden by the
    canonical ppt_quality.py that lives next to this test.
    """
    assert (PKG / "deck_builder.py").is_file()
    assert (PKG / "ppt_quality.py").is_file()

    pkg = str(PKG.resolve())
    backend = str(BACKEND.resolve())
    repo = str(BACKEND.parent.resolve())
    saved_path = sys.path[:]
    drop_keys = [
        key
        for key in list(sys.modules)
        if key in {"deck_builder", "ppt_quality"}
        or key.startswith("deck_builder.")
        or key.startswith("ppt_quality.")
    ]
    saved_modules = {key: sys.modules[key] for key in drop_keys}
    injected = []

    def _stub_pptx():
        if "pptx" in sys.modules:
            return
        pptx = types.ModuleType("pptx")
        class _Dummy:
            def __init__(self, *a, **k):
                pass

        pptx.Presentation = _Dummy
        sys.modules["pptx"] = pptx
        injected.append("pptx")
        for name, attrs in (
            ("pptx.dml", {}),
            ("pptx.dml.color", {"RGBColor": _Dummy}),
            ("pptx.util", {"Inches": _Dummy, "Pt": _Dummy}),
        ):
            if name in sys.modules:
                continue
            mod = types.ModuleType(name)
            for attr, value in attrs.items():
                setattr(mod, attr, value)
            sys.modules[name] = mod
            injected.append(name)

    def _stub_boto3():
        if "boto3" in sys.modules:
            return
        boto3 = types.ModuleType("boto3")
        boto3.client = lambda *a, **k: None
        sys.modules["boto3"] = boto3
        injected.append("boto3")

    try:
        for key in drop_keys:
            sys.modules.pop(key, None)
        _stub_pptx()
        _stub_boto3()

        cleaned = []
        for entry in saved_path:
            if entry in ("", "."):
                continue
            try:
                resolved = str(Path(entry).resolve())
            except OSError:
                cleaned.append(entry)
                continue
            if resolved in {backend, repo}:
                continue
            cleaned.append(entry)
        sys.path[:] = [pkg] + [p for p in cleaned if p != pkg]

        deck_builder = importlib.import_module("deck_builder")
        ppt_quality = importlib.import_module("ppt_quality")

        assert Path(deck_builder.__file__).resolve().parent == PKG.resolve()
        assert Path(ppt_quality.__file__).resolve() == (PKG / "ppt_quality.py").resolve()
        assert hasattr(deck_builder, "lambda_handler")
        assert hasattr(ppt_quality, "paginate_glossary_entries")
    finally:
        sys.path[:] = saved_path
        for key in list(sys.modules):
            if key in {"deck_builder", "ppt_quality"} or key.startswith("deck_builder.") or key.startswith("ppt_quality."):
                sys.modules.pop(key, None)
        for key, value in saved_modules.items():
            sys.modules[key] = value
        for key in injected:
            sys.modules.pop(key, None)
