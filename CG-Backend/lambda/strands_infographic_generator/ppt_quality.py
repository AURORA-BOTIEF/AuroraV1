"""Offline PPT quality helpers (THOR audit item 8 / backlog #11).

- Glossary pagination without truncating definitions at 250/240 characters.
- Configurable per-course slide-count cap from ``course_duration_hours``.
- Detect unusable slides: empty body, empty tables, near-duplicate text, black table shells.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Slides per hour of course (matches infographic dynamic budget ~14/h).
DEFAULT_SLIDES_PER_HOUR = float(os.getenv("PPT_SLIDES_PER_HOUR", "14"))
DEFAULT_MIN_COURSE_SLIDES = int(os.getenv("PPT_MIN_COURSE_SLIDES", "10"))

# Glossary layout: paginate by character budget instead of chopping definitions.
DEFAULT_GLOSSARY_CHARS_PER_SLIDE = int(os.getenv("PPT_GLOSSARY_CHARS_PER_SLIDE", "900"))
DEFAULT_GLOSSARY_TERMS_PER_SLIDE = int(os.getenv("PPT_GLOSSARY_TERMS_PER_SLIDE", "6"))
MIN_SLIDE_FINGERPRINT_CHARS = 12

# Layouts that are allowed to carry little on-slide text (titles, dividers, thanks).
STRUCTURAL_LAYOUTS = frozenset(
    {
        "course-title",
        "module-title",
        "lesson-title",
        "module-end-logo",
        "intro-cover",
        "intro-legal",
        "intro-agenda",
        "intro-content",
        "lab-intro",
        "gracias",
        "thank-you",
        "chapter-summary",
    }
)

STRUCTURAL_HTML_CLASSES = frozenset(
    {
        "course-title-slide",
        "module-title-slide",
        "lesson-title-slide",
        "module-end-logo-slide",
        "intro-cover-slide",
        "intro-legal-slide",
        "intro-agenda-slide",
        "intro-content-slide",
        "lab-intro-slide",
        "gracias-slide",
        "chapter-summary-slide",
    }
)


class PptQualityError(Exception):
    """Raised when generated slides fail THOR PPT quality gates."""

    def __init__(self, report: Dict[str, Any]):
        self.report = report
        issues = report.get("issues") or []
        summary = "; ".join(
            f"{i.get('code')}: {i.get('message', '')}" for i in issues[:5]
        )
        super().__init__(summary or "PPT quality validation failed")


def max_slides_for_course(course_duration_hours: Optional[float]) -> Optional[int]:
    """Upper bound on deck size from course duration (None = no cap configured)."""
    if course_duration_hours is None:
        return None
    try:
        hours = float(course_duration_hours)
    except (TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    return max(DEFAULT_MIN_COURSE_SLIDES, int(round(hours * DEFAULT_SLIDES_PER_HOUR)))


def _glossary_entry_pair(entry: Union[Dict[str, Any], Tuple[str, str], List[Any]]) -> Tuple[str, str]:
    if isinstance(entry, dict):
        return str(entry.get("term") or ""), str(entry.get("definition") or "")
    if isinstance(entry, (tuple, list)) and len(entry) >= 2:
        return str(entry[0]), str(entry[1])
    return "", ""


def paginate_glossary_entries(
    entries: Sequence[Union[Dict[str, Any], Tuple[str, str], List[Any]]],
    *,
    chars_per_slide: int = DEFAULT_GLOSSARY_CHARS_PER_SLIDE,
    max_terms_per_slide: int = DEFAULT_GLOSSARY_TERMS_PER_SLIDE,
) -> List[List[Dict[str, str]]]:
    """Split glossary items across slides; definitions stay intact (no ellipsis chop)."""
    pages: List[List[Dict[str, str]]] = []
    current: List[Dict[str, str]] = []
    current_chars = 0
    for raw in entries or []:
        term, definition = _glossary_entry_pair(raw)
        term = term.strip()
        definition = definition.strip()
        if not term:
            continue
        entry_chars = len(term) + len(definition) + 4
        if current and (
            current_chars + entry_chars > chars_per_slide
            or len(current) >= max_terms_per_slide
        ):
            pages.append(current)
            current = []
            current_chars = 0
        current.append({"term": term, "definition": definition})
        current_chars += entry_chars
    if current:
        pages.append(current)
    return pages


def _normalize_fingerprint_text(text: str) -> str:
    folded = re.sub(r"\s+", " ", (text or "").strip().lower())
    folded = re.sub(r"[^\w\s]", "", folded, flags=re.UNICODE)
    return folded


def slide_text_fingerprint(slide: Dict[str, Any]) -> str:
    """Stable hash of on-slide instructional text (for duplicate detection)."""
    parts: List[str] = []
    for block in slide.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "bullets":
            parts.extend(str(x) for x in (block.get("items") or []))
        elif btype == "glossary":
            for it in block.get("items") or []:
                if isinstance(it, dict):
                    parts.append(it.get("term") or "")
                    parts.append(it.get("definition") or "")
        elif btype == "table":
            parts.extend(str(x) for x in (block.get("headers") or []))
            for row in block.get("rows") or []:
                parts.extend(str(c) for c in row)
        elif btype == "code":
            parts.append(block.get("code") or "")
        elif btype == "image":
            parts.append(block.get("caption") or block.get("alt") or "")
    payload = _normalize_fingerprint_text("\n".join(parts))
    if len(payload) < MIN_SLIDE_FINGERPRINT_CHARS:
        return ""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _table_block_is_empty(block: Dict[str, Any]) -> bool:
    if block.get("type") != "table":
        return False
    headers = [str(h).strip() for h in (block.get("headers") or [])]
    rows = block.get("rows") or []
    all_cells: List[str] = list(headers)
    for row in rows:
        all_cells.extend(str(c).strip() for c in row)
    if not all_cells:
        return True
    return not any(all_cells)


def _slide_collect_text(slide: Dict[str, Any]) -> str:
    parts: List[str] = [slide.get("title") or "", slide.get("subtitle") or ""]
    for block in slide.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "bullets":
            parts.extend(str(x) for x in (block.get("items") or []))
        elif btype == "glossary":
            for it in block.get("items") or []:
                if isinstance(it, dict):
                    parts.extend([it.get("term") or "", it.get("definition") or ""])
        elif btype == "code":
            parts.append(block.get("code") or "")
        elif btype == "table" and not _table_block_is_empty(block):
            parts.extend(str(x) for x in (block.get("headers") or []))
            for row in block.get("rows") or []:
                parts.extend(str(c) for c in row)
    return "\n".join(p.strip() for p in parts if p and str(p).strip())


def is_structure_slide_empty(slide: Dict[str, Any]) -> bool:
    layout = (slide.get("layout") or "").replace("_", "-")
    if layout in STRUCTURAL_LAYOUTS or slide.get("layout") == "glossary":
        return False
    text = _slide_collect_text(slide)
    if len(text) >= 12:
        return False
    blocks = slide.get("content_blocks") or []
    if not blocks:
        return True
    has_substance = False
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "bullets" and any(str(x).strip() for x in (block.get("items") or [])):
            has_substance = True
        elif btype == "code" and str(block.get("code") or "").strip():
            has_substance = True
        elif btype == "glossary" and block.get("items"):
            has_substance = True
        elif btype == "table" and not _table_block_is_empty(block):
            has_substance = True
    if has_substance:
        return False
    # Image-only or empty table shell.
    if any(b.get("type") == "image" for b in blocks if isinstance(b, dict)):
        return True
    if any(_table_block_is_empty(b) for b in blocks if isinstance(b, dict)):
        return True
    return len(text) < 8


def validate_slide_structure(
    slides: Sequence[Dict[str, Any]],
    *,
    course_duration_hours: Optional[float] = None,
    reject_on_issues: bool = True,
) -> Dict[str, Any]:
    """Validate infographic slide dicts before HTML/PPT export."""
    issues: List[Dict[str, Any]] = []
    cap = max_slides_for_course(course_duration_hours)
    if cap is not None and len(slides) > cap:
        issues.append(
            {
                "code": "slide_count_cap",
                "message": f"Deck has {len(slides)} slides but cap for {course_duration_hours}h is {cap}",
                "slide_count": len(slides),
                "cap": cap,
            }
        )

    seen: Dict[str, int] = {}
    for idx, slide in enumerate(slides or []):
        if not isinstance(slide, dict):
            continue
        if is_structure_slide_empty(slide):
            issues.append(
                {
                    "code": "empty_slide",
                    "message": f"Slide {idx + 1} has no usable instructional content",
                    "slide_index": idx,
                    "title": slide.get("title"),
                }
            )
        for b_i, block in enumerate(slide.get("content_blocks") or []):
            if isinstance(block, dict) and _table_block_is_empty(block):
                issues.append(
                    {
                        "code": "empty_table",
                        "message": f"Slide {idx + 1} has a table with no cell text (black-box risk)",
                        "slide_index": idx,
                        "block_index": b_i,
                        "title": slide.get("title"),
                    }
                )
        fp = slide_text_fingerprint(slide)
        if fp:
            if fp in seen:
                issues.append(
                    {
                        "code": "duplicate_slide",
                        "message": f"Slide {idx + 1} duplicates slide {seen[fp] + 1} text",
                        "slide_index": idx,
                        "duplicate_of": seen[fp],
                        "title": slide.get("title"),
                    }
                )
            else:
                seen[fp] = idx

    report = {
        "ok": not issues,
        "issues": issues,
        "slide_count": len(slides or []),
        "slide_cap": cap,
    }
    if reject_on_issues and issues:
        raise PptQualityError(report)
    return report


def _html_slide_is_structural(slide_html) -> bool:
    for cls in STRUCTURAL_HTML_CLASSES:
        if slide_html.find(class_=cls):
            return True
    return False


def _html_table_is_empty(table_elem) -> bool:
    if table_elem is None:
        return False
    cells = [td.get_text(strip=True) for td in table_elem.find_all(["td", "th"])]
    if not cells:
        return True
    return not any(cells)


def validate_html_slides(
    slides_html: Sequence[Any],
    *,
    course_duration_hours: Optional[float] = None,
    reject_on_issues: bool = True,
) -> Dict[str, Any]:
    """Validate parsed HTML slide divs prior to python-pptx conversion."""
    issues: List[Dict[str, Any]] = []
    cap = max_slides_for_course(course_duration_hours)
    if cap is not None and len(slides_html) > cap:
        issues.append(
            {
                "code": "slide_count_cap",
                "message": f"HTML deck has {len(slides_html)} slides but cap is {cap}",
                "slide_count": len(slides_html),
                "cap": cap,
            }
        )

    seen: Dict[str, int] = {}
    for idx, slide_html in enumerate(slides_html or []):
        if _html_slide_is_structural(slide_html):
            continue
        text = slide_html.get_text(separator=" ", strip=True)
        has_table = slide_html.find("table")
        if _html_table_is_empty(has_table):
            issues.append(
                {
                    "code": "empty_table",
                    "message": f"HTML slide {idx + 1} table has no visible cell text",
                    "slide_index": idx,
                }
            )
        # Near-black unusable: only a table element and no text (rendered black box).
        if has_table and len(text) < 15 and not slide_html.find(class_="bullets"):
            issues.append(
                {
                    "code": "black_slide",
                    "message": f"HTML slide {idx + 1} is table-only with almost no text",
                    "slide_index": idx,
                }
            )
        if len(text) < 12 and not has_table:
            if not slide_html.find("img") and not slide_html.find(class_="code-block"):
                issues.append(
                    {
                        "code": "empty_slide",
                        "message": f"HTML slide {idx + 1} has no visible text",
                        "slide_index": idx,
                    }
                )
        fp = hashlib.sha256(_normalize_fingerprint_text(text).encode("utf-8")).hexdigest()[:20]
        if len(_normalize_fingerprint_text(text)) >= MIN_SLIDE_FINGERPRINT_CHARS:
            if fp in seen:
                issues.append(
                    {
                        "code": "duplicate_slide",
                        "message": f"HTML slide {idx + 1} duplicates slide {seen[fp] + 1}",
                        "slide_index": idx,
                        "duplicate_of": seen[fp],
                    }
                )
            else:
                seen[fp] = idx

    report = {"ok": not issues, "issues": issues, "slide_count": len(slides_html or []), "slide_cap": cap}
    if reject_on_issues and issues:
        raise PptQualityError(report)
    return report


def resolve_course_duration_hours(book_data: Optional[Dict[str, Any]]) -> Optional[float]:
    if not book_data:
        return None
    cm = book_data.get("course_metadata") or {}
    bm = book_data.get("metadata") or {}
    for key in ("course_duration_hours",):
        for src in (cm, bm, book_data):
            val = src.get(key) if isinstance(src, dict) else None
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
    for src in (cm, bm):
        dur_min = src.get("total_duration_minutes") or src.get("duration")
        if dur_min is not None:
            try:
                return float(dur_min) / 60.0
            except (TypeError, ValueError):
                pass
    return None


def validate_presentation(
    presentation,
    *,
    course_duration_hours: Optional[float] = None,
    reject_on_issues: bool = True,
) -> Dict[str, Any]:
    """Validate a finished python-pptx Presentation."""
    issues: List[Dict[str, Any]] = []
    slides = list(presentation.slides)
    cap = max_slides_for_course(course_duration_hours)
    if cap is not None and len(slides) > cap:
        issues.append(
            {
                "code": "slide_count_cap",
                "message": f"PPTX has {len(slides)} slides but cap is {cap}",
                "slide_count": len(slides),
                "cap": cap,
            }
        )

    seen: Dict[str, int] = {}
    for idx, slide in enumerate(slides):
        texts: List[str] = []
        has_table = False
        table_empty = True
        for shape in slide.shapes:
            if shape.has_table:
                has_table = True
                table = shape.table
                for r in range(len(table.rows)):
                    for c in range(len(table.columns)):
                        cell_text = table.cell(r, c).text.strip()
                        if cell_text:
                            table_empty = False
                        texts.append(cell_text)
            elif shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    texts.append(t)
        body = "\n".join(texts).strip()
        if has_table and table_empty:
            issues.append(
                {
                    "code": "empty_table",
                    "message": f"PPTX slide {idx + 1} has an empty table",
                    "slide_index": idx,
                }
            )
        if has_table and len(body) < 8:
            issues.append(
                {
                    "code": "black_slide",
                    "message": f"PPTX slide {idx + 1} is table-only with no cell text",
                    "slide_index": idx,
                }
            )
        fp = hashlib.sha256(_normalize_fingerprint_text(body).encode("utf-8")).hexdigest()[:20]
        if len(_normalize_fingerprint_text(body)) >= MIN_SLIDE_FINGERPRINT_CHARS:
            if fp in seen:
                issues.append(
                    {
                        "code": "duplicate_slide",
                        "message": f"PPTX slide {idx + 1} duplicates slide {seen[fp] + 1}",
                        "slide_index": idx,
                        "duplicate_of": seen[fp],
                    }
                )
            else:
                seen[fp] = idx

    report = {"ok": not issues, "issues": issues, "slide_count": len(slides), "slide_cap": cap}
    if reject_on_issues and issues:
        raise PptQualityError(report)
    return report