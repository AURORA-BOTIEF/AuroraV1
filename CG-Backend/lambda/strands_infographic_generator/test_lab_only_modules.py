"""Tests for lab-only PPT chapters (theory-less modules still get lab slides)."""
import unittest

from html_first_generator import (
    _lesson_is_bookend_or_lab_placeholder,
    _module_has_substantive_theory,
    _outline_lab_activities,
    _should_emit_lab_only_module,
)


class TestOutlineLabActivities(unittest.TestCase):
    def test_reads_lab_activities(self):
        module = {
            'lab_activities': [
                {'title': 'Práctica. Exploración', 'duration_minutes': 12},
                {'title': ''},
            ]
        }
        labs = _outline_lab_activities(module)
        self.assertEqual(len(labs), 1)
        self.assertEqual(labs[0]['title'], 'Práctica. Exploración')

    def test_falls_back_to_labs_key(self):
        module = {'labs': ['Demo: Comparar opciones']}
        labs = _outline_lab_activities(module)
        self.assertEqual(labs[0]['title'], 'Demo: Comparar opciones')

    def test_empty_module(self):
        self.assertEqual(_outline_lab_activities({}), [])
        self.assertEqual(_outline_lab_activities(None), [])


class TestSubstantiveTheory(unittest.TestCase):
    def test_bookend_only_is_not_theory(self):
        book = {
            'lessons': [
                {'module_number': 1, 'title': 'Introducción', 'is_intro': True},
                {'module_number': 1, 'title': 'Resumen del Capítulo', 'is_summary': True},
            ]
        }
        self.assertFalse(_module_has_substantive_theory(book, 1))

    def test_real_lesson_counts_as_theory(self):
        book = {
            'lessons': [
                {'module_number': 7, 'title': '7.1: Cierre del Capítulo 7 — 5 min'},
            ]
        }
        self.assertTrue(_module_has_substantive_theory(book, 7))
        self.assertFalse(_module_has_substantive_theory(book, 1))

    def test_placeholder_detects_intro_and_lab_types(self):
        self.assertTrue(_lesson_is_bookend_or_lab_placeholder({'title': 'Introducción'}))
        self.assertTrue(_lesson_is_bookend_or_lab_placeholder({'title': 'Lab 1', 'type': 'lab'}))
        self.assertFalse(_lesson_is_bookend_or_lab_placeholder(
            {'title': '7.1: Cierre del Capítulo 7 — 5 min'}
        ))


class TestShouldEmitLabOnlyModule(unittest.TestCase):
    def test_practice_only_chapters_then_theory(self):
        """ECD-style outline: labs in 1–6, a single theory lesson in 7."""
        book = {
            'lessons': [
                {'module_number': 7, 'title': '7.1: Cierre del Capítulo 7 — 5 min'},
            ],
            'outline_modules': [
                {'title': 'Cap 1', 'lessons': [], 'lab_activities': [{'title': 'Lab 1'}]},
                {'title': 'Cap 2', 'lessons': [], 'lab_activities': [{'title': 'Lab 2'}]},
                {'title': 'Cap 3', 'lessons': [], 'lab_activities': [{'title': 'Lab 3'}]},
                {'title': 'Cap 4', 'lessons': [], 'lab_activities': [{'title': 'Lab 4'}]},
                {'title': 'Cap 5', 'lessons': [], 'lab_activities': [{'title': 'Lab 5'}]},
                {'title': 'Cap 6', 'lessons': [], 'lab_activities': [{'title': 'Lab 6'}]},
                {'title': 'Cap 7', 'lessons': [{'title': 'Cierre'}], 'lab_activities': []},
            ],
        }
        for n in range(1, 7):
            self.assertTrue(_should_emit_lab_only_module(book, n), n)
        self.assertFalse(_should_emit_lab_only_module(book, 7))

    def test_theory_chapter_with_labs_is_not_lab_only(self):
        book = {
            'lessons': [{'module_number': 1, 'title': '1.1 Conceptos'}],
            'outline_modules': [
                {
                    'title': 'Cap 1',
                    'lessons': [{'title': '1.1 Conceptos'}],
                    'lab_activities': [{'title': 'Lab'}],
                },
            ],
        }
        self.assertFalse(_should_emit_lab_only_module(book, 1))

    def test_zero_theory_still_emits_labs(self):
        book = {
            'lessons': [],
            'outline_modules': [
                {'title': 'Cap 1', 'lessons': [], 'lab_activities': [{'title': 'Lab 1'}]},
            ],
        }
        self.assertTrue(_should_emit_lab_only_module(book, 1))


if __name__ == '__main__':
    unittest.main()
