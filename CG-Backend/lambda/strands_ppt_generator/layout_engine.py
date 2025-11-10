"""Layout engine for making slide layout decisions.

Contract (inputs/outputs):
- Input: slide_data (dict) with optional keys: 'title', 'bullets' (list[str]),
  'caption' (str), 'image_url' (str).
- Output: dict with keys: 'choice' (one of 'text-only','image-only','split-right','split-top'),
  'reason' (short explanation), and optional 'confidence' (0..1).

This module is intentionally small and deterministic. It provides a single
entrypoint `decide_layout_choice` with simple heuristics used by tests and
to bootstrap the more complex layout engine later.

Edge cases handled:
- Empty or missing text fields
- Presence/absence of image_url
- Long vs short text (word-count thresholds)

"""
from typing import Dict, Any, Optional


WORD_SHORT = 20
WORD_MEDIUM = 60


def _word_count(slide_data: Dict[str, Any]) -> int:
    words = 0
    if slide_data.get("title"):
        words += len(str(slide_data["title"]).split())
    if slide_data.get("caption"):
        words += len(str(slide_data["caption"]).split())
    bullets = slide_data.get("bullets") or []
    if isinstance(bullets, (list, tuple)):
        for b in bullets:
            words += len(str(b).split())
    return words


def decide_layout_choice(slide_data: Dict[str, Any], image_size_provider: Optional[callable] = None) -> Dict[str, Any]:
    """Return a richer layout descriptor for a single slide.

    The function returns a dict with at least:
      - choice: one of 'text-only','image-only','split-right','split-top'
      - reason: short explanation
      - confidence: float 0..1
    Optionally, when an image is present, a 'rects' key will be included:
      rects: {
          'image': {'x': 0..1, 'y':0..1, 'w':0..1, 'h':0..1},  # fractions of slide width/height
          'text':  {'x':..., 'y':..., 'w':..., 'h':...}
      }

    If an image_size_provider is supplied (callable(image_url) -> {'width':w,'height':h}),
    the descriptor may prefer banner or side layouts based on aspect ratio.
    """
    wc = _word_count(slide_data)
    has_image = bool(slide_data.get("image_url"))

    # base descriptor
    desc = {"choice": "text-only", "reason": "default", "confidence": 0.8}

    if not has_image:
        desc.update({"choice": "text-only", "reason": "no image present", "confidence": 0.95})
        return desc

    # If we have image dimensions, use aspect to bias layout
    aspect = None
    if image_size_provider:
        try:
            dims = image_size_provider(slide_data.get('image_url'))
            if dims and isinstance(dims, dict) and dims.get('width') and dims.get('height'):
                w = float(dims.get('width'))
                h = float(dims.get('height')) or 1.0
                aspect = w / h if h else None
        except Exception:
            aspect = None

    # Decide choice using heuristics, incorporating aspect when available
    if wc <= WORD_SHORT:
        choice = 'image-only'
        reason = 'short text, image prominent'
        confidence = 0.95
    elif wc <= WORD_MEDIUM:
        # moderate text: choose split; banner if wide image, side if tall
        if aspect is not None:
            if aspect >= 1.5:
                choice = 'split-top'
                reason = 'moderate text and wide image -> banner'
                confidence = 0.9
            elif aspect <= 0.9:
                choice = 'split-right'
                reason = 'moderate text and tall image -> side'
                confidence = 0.9
            else:
                choice = 'split-right'
                reason = 'moderate text, default to side split'
                confidence = 0.85
        else:
            choice = 'split-right'
            reason = 'moderate text, default split-right'
            confidence = 0.85
    else:
        choice = 'text-only'
        reason = 'too much text; prefer readable text layout'
        confidence = 0.8

    desc.update({"choice": choice, "reason": reason, "confidence": confidence})

    # Provide suggested rects (fractions) for common choices to guide renderer
    # Fractions are relative to full slide width and height (0..1)
    # These are conservative and leave margins for title/notes
    if choice == 'image-only':
        desc['rects'] = {
            'image': {'x': 0.07, 'y': 0.15, 'w': 0.86, 'h': 0.68},
            'text': {'x': 0.07, 'y': 0.82, 'w': 0.86, 'h': 0.12}
        }
    elif choice == 'split-top':
        desc['rects'] = {
            'image': {'x': 0.07, 'y': 0.10, 'w': 0.86, 'h': 0.36},
            'text': {'x': 0.07, 'y': 0.48, 'w': 0.86, 'h': 0.42}
        }
    elif choice == 'split-right':
        desc['rects'] = {
            'image': {'x': 0.56, 'y': 0.18, 'w': 0.38, 'h': 0.64},
            'text': {'x': 0.07, 'y': 0.18, 'w': 0.46, 'h': 0.64}
        }
    else:
        # text-only -> only suggest text rect
        desc['rects'] = {
            'text': {'x': 0.07, 'y': 0.18, 'w': 0.86, 'h': 0.72}
        }

    return desc


__all__ = ["decide_layout_choice"]
