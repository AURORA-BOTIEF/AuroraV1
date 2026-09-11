"""Unit tests for HTML-first incremental structure merge."""

import unittest

from infographic_generator import (
    IncrementalMergeError,
    merge_html_first_incremental_structure,
)


def _intro_slide(title: str = "Curso") -> dict:
    return {"layout": "intro-cover", "title": title, "slide_number": 1}


def _lesson_slide(title: str = "Lección") -> dict:
    return {"layout": "lesson-title", "title": title, "slide_number": 2}


def _structure(slides, **kwargs) -> dict:
    base = {
        "slides": slides,
        "total_slides": len(slides),
        "completion_status": "partial",
        "last_batch_index": 0,
        "execution_id": "run-aaaa",
        "lessons_processed": 1,
        "batch_slide_spans": [{
            "batch_index": 0,
            "start_idx": 0,
            "end_idx": max(0, len(slides) - 1),
            "lessons_processed": 1,
        }],
    }
    base.update(kwargs)
    return base


class TestMergeHtmlFirstIncrementalStructure(unittest.TestCase):
    def test_stale_batch_zero_resets_with_intro(self):
        existing = _structure(
            [_intro_slide(), _lesson_slide("old")],
            completion_status="complete",
            last_batch_index=3,
            execution_id="old-run",
        )
        incoming = _structure(
            [_intro_slide("Nuevo"), _lesson_slide("1.1")],
            completion_status="partial",
            last_batch_index=0,
            lessons_processed=1,
        )

        merged = merge_html_first_incremental_structure(
            existing,
            incoming,
            batch_index=0,
            body_execution_id="new-run",
        )

        self.assertEqual(merged["slides"][0]["layout"], "intro-cover")
        self.assertEqual(merged["slides"][0]["title"], "Nuevo")
        self.assertEqual(merged["execution_id"], "new-run")
        self.assertEqual(merged["batch_slide_spans"][0]["batch_index"], 0)

    def test_stale_mid_batch_raises_instead_of_dropping_intro(self):
        existing = _structure(
            [_intro_slide(), _lesson_slide("1.1")],
            completion_status="complete",
            last_batch_index=5,
            execution_id="finished-run",
        )
        incoming = _structure(
            [_lesson_slide("3.1")],
            completion_status="partial",
            last_batch_index=3,
            lessons_processed=3,
        )

        with self.assertRaises(IncrementalMergeError):
            merge_html_first_incremental_structure(
                existing,
                incoming,
                batch_index=3,
                body_execution_id="other-run",
            )

    def test_same_execution_appends_incrementally(self):
        existing = _structure([_intro_slide(), _lesson_slide("1.1")], last_batch_index=0)
        incoming = _structure([_lesson_slide("1.2")], lessons_processed=1)

        merged = merge_html_first_incremental_structure(
            existing,
            incoming,
            batch_index=1,
            body_execution_id="run-aaaa",
        )

        self.assertEqual(len(merged["slides"]), 3)
        self.assertEqual(merged["slides"][0]["layout"], "intro-cover")
        self.assertEqual(merged["last_batch_index"], 1)
        self.assertEqual(len(merged["batch_slide_spans"]), 2)


if __name__ == "__main__":
    unittest.main()
