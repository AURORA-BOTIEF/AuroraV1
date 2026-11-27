# -*- coding: utf-8 -*-
"""THOR backlog #11: PPT glossary pagination, slide cap, quality gates."""

import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ppt_quality as pq
from ppt_quality import PptQualityError


def test_glossary_pagination_keeps_full_definition():
  long_def = (
      "Arquitectura de referencia que define cómo los componentes cliente, daemon y registro "
      "interactúan en un entorno de contenedores, incluyendo el ciclo de vida de imágenes, "
      "capas de sistema de archivos, redes bridge y overlay, volúmenes persistentes y políticas "
      "de seguridad para aislar cargas de trabajo en hosts compartidos."
  )
  assert len(long_def) > 250
  pages = pq.paginate_glossary_entries(
      [
          {"term": "Docker", "definition": long_def},
          {"term": "Imagen", "definition": long_def},
      ],
      chars_per_slide=400,
      max_terms_per_slide=1,
  )
  assert len(pages) >= 2
  joined = " ".join(e["definition"] for page in pages for e in page)
  assert long_def in joined
  assert joined.count(long_def) == 2
  assert "…" not in joined


def test_max_slides_for_course_duration():
  assert pq.max_slides_for_course(2.0) == int(round(2.0 * pq.DEFAULT_SLIDES_PER_HOUR))
  assert pq.max_slides_for_course(1.5) == int(round(1.5 * pq.DEFAULT_SLIDES_PER_HOUR))
  assert pq.max_slides_for_course(None) is None


def test_detect_duplicate_and_empty_slides():
  s1 = {
      "title": "Conceptos",
      "layout": "text_only",
      "content_blocks": [{
          "type": "bullets",
          "items": [
              "Concepto alfa con suficiente texto para huella",
              "Concepto beta con suficiente texto para huella",
          ],
      }],
  }
  s2 = {
      "title": "Copia",
      "layout": "text_only",
      "content_blocks": [{
          "type": "bullets",
          "items": [
              "Concepto alfa con suficiente texto para huella",
              "Concepto beta con suficiente texto para huella",
          ],
      }],
  }
  s_empty = {"title": "Vacío", "layout": "text_only", "content_blocks": []}
  try:
    pq.validate_slide_structure(
        [s1, s2, s_empty],
        course_duration_hours=None,
    )
    raise AssertionError("expected PptQualityError")
  except PptQualityError as exc:
    codes = {i["code"] for i in exc.report["issues"]}
  assert "duplicate_slide" in codes
  assert "empty_slide" in codes


def test_reject_slide_count_over_cap():
  slides = [
      {
          "title": f"T{i}",
          "layout": "text_only",
          "content_blocks": [{"type": "bullets", "items": [f"Único contenido {i}"]}],
      }
      for i in range(30)
  ]
  try:
    pq.validate_slide_structure(slides, course_duration_hours=1.0)
    raise AssertionError("expected PptQualityError")
  except PptQualityError as exc:
    assert any(i["code"] == "slide_count_cap" for i in exc.report["issues"])


def test_reject_empty_table_block():
  bad = {
      "title": "Tabla",
      "layout": "text_only",
      "content_blocks": [
          {"type": "table", "headers": [], "rows": [["", ""], ["", ""]]},
      ],
  }
  try:
    pq.validate_slide_structure([bad], course_duration_hours=None)
    raise AssertionError("expected PptQualityError")
  except PptQualityError:
    pass


def test_book_builder_definition_not_truncated_at_250():
  sys.path.insert(0, os.path.join(_HERE, "lambda"))
  from book_builder import _definicion_por_encabezado

  parrafo_largo = (
      "Definición íntegra del concepto Docker: "
      + "componentes, redes, volúmenes y políticas. " * 8
  )
  assert len(parrafo_largo) > 250
  contenido = f"""
## Docker
### Visión General del Concepto
{parrafo_largo}
"""
  definicion = _definicion_por_encabezado(contenido, "Docker")
  assert definicion
  assert len(definicion) > 250
  assert definicion == parrafo_largo.strip()


def test_html_glossary_parser_preserves_long_definition():
  sys.path.insert(0, os.path.join(_HERE, "lambda", "ppt_merger"))
  from html_to_ppt_styled import _parse_glossary_items_from_md

  long_def = "x" * 320
  md = f"- **Contenedor**: {long_def}"
  items = _parse_glossary_items_from_md(md)
  assert len(items) == 1
  term, defn = items[0]
  assert term == "Contenedor"
  assert defn == long_def
  assert "…" not in defn


def test_deck_glosario_uses_multiple_slides_for_long_terms():
  long_a = "a" * 400
  long_b = "b" * 400
  pages = pq.paginate_glossary_entries(
      [
          {"term": "Alpha", "definition": long_a},
          {"term": "Beta", "definition": long_b},
      ],
      chars_per_slide=500,
      max_terms_per_slide=4,
  )
  assert len(pages) >= 2


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8")
  tests = [
    (name, fn)
    for name, fn in sorted(globals().items())
    if name.startswith("test_") and callable(fn)
  ]
  failed = []
  for name, fn in tests:
    try:
      fn()
    except Exception as exc:  # noqa: BLE001
      failed.append((name, exc))
      print(f"FAIL {name}: {exc}")
    else:
      print(f"ok   {name}")
  print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
  sys.exit(1 if failed else 0)