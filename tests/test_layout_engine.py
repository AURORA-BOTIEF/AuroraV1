import importlib.util
from pathlib import Path

# Load layout_engine by path to avoid import path issues
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "layout_engine",
    str(root / "CG-Backend" / "lambda" / "strands_ppt_generator" / "layout_engine.py"),
)
layout_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout_engine)


def test_decide_layout_text_only_when_no_image():
    slide = {"title": "Overview", "bullets": ["point a", "point b"]}
    decision = layout_engine.decide_layout_choice(slide)
    assert decision["choice"] == "text-only"


def test_decide_layout_image_only_for_short_text():
    slide = {"title": "Pic", "caption": "A short caption.", "image_url": "http://example.com/img.png"}
    decision = layout_engine.decide_layout_choice(slide)
    assert decision["choice"] in ("image-only", "split-right")


def test_decide_layout_split_for_moderate_text():
    bullets = ["This is a bullet with several words"] * 5
    slide = {"title": "Data", "bullets": bullets, "image_url": "x"}
    decision = layout_engine.decide_layout_choice(slide)
    assert decision["choice"] in ("split-right", "text-only")
