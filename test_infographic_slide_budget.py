from pathlib import Path
import sys


GENERATOR_DIR = (
    Path(__file__).resolve().parent
    / "CG-Backend"
    / "lambda"
    / "strands_infographic_generator"
)
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

from html_first_generator import HTMLFirstGenerator, _build_content_slide_budget
from html_first_generator import create_fallback_lesson_content_slides


def _make_slide(title: str, has_image: bool = False):
    content_blocks = []
    if has_image:
        content_blocks.append({"type": "image", "image_reference": f"img-{title}"})
    content_blocks.append({"type": "bullets", "items": [f"Contenido {title}"]})
    return {
        "title": title,
        "content_blocks": content_blocks,
    }


def test_budget_uses_lesson_duration_as_hard_max():
    lesson = {
        "title": "Introduccion breve",
        "module_number": 1,
        "duration_minutes": 15,
    }

    budget = _build_content_slide_budget(
        lesson,
        outline_modules=[],
        global_slides_per_lesson=5,
        image_count=3,
    )

    assert budget["source"] == "lesson.duration_minutes"
    assert budget["min_content_slides"] == 3
    assert budget["target_content_slides"] == 5
    assert budget["max_content_slides"] == 8
    assert budget["image_slide_target"] == 3


def test_budget_falls_back_to_outline_duration():
    lesson = {
        "title": "Pipelines de datos",
        "module_number": 1,
    }
    outline_modules = [
        {
            "lessons": [
                {"title": "Pipelines de datos", "duration_minutes": 32},
            ]
        }
    ]

    budget = _build_content_slide_budget(
        lesson,
        outline_modules=outline_modules,
        global_slides_per_lesson=6,
        image_count=4,
    )

    assert budget["source"] == "outline.lesson.duration_minutes"
    assert budget["duration_minutes"] == 32
    assert budget["min_content_slides"] == 7
    assert budget["target_content_slides"] == 11
    assert budget["max_content_slides"] == 16
    assert budget["image_slide_target"] == 4


def test_budget_for_longer_lessons_no_longer_caps_at_five_slides():
    lesson = {
        "title": "Arquitectura distribuida",
        "module_number": 1,
        "duration_minutes": 40,
        "topics": [{"title": "A"}, {"title": "B"}, {"title": "C"}],
        "content": "## Tema 1\nContenido\n## Tema 2\n```python\nprint('x')\n```\n| A | B |\n| - | - |\n| 1 | 2 |\n",
    }

    budget = _build_content_slide_budget(
        lesson,
        outline_modules=[],
        global_slides_per_lesson=5,
        image_count=2,
    )

    assert budget["min_content_slides"] == 8
    assert budget["target_content_slides"] >= 14
    assert budget["max_content_slides"] == 20


def test_clip_content_slides_prioritizes_image_slides():
    generator = HTMLFirstGenerator(model=None)
    slides = [
        _make_slide("01", has_image=False),
        _make_slide("02", has_image=True),
        _make_slide("03", has_image=False),
        _make_slide("04", has_image=True),
        _make_slide("05", has_image=False),
    ]

    clipped = generator._clip_content_slides_to_budget(slides, 3)

    assert len(clipped) == 3
    assert sum(
        1
        for slide in clipped
        if any(block.get("type") == "image" for block in slide.get("content_blocks", []))
    ) >= 2

def test_fallback_content_slides_skip_intro_and_use_substantive_sections():
    lesson = {
        "title": "Eventos distribuidos",
        "content": """
## Introducción
Esta lección presenta el contexto general.

## Arquitectura orientada a eventos
- Productores y consumidores desacoplados
- Brokers para distribución asíncrona

## Patrones de entrega
Se debe elegir entre at-most-once, at-least-once y exactly-once.
""",
    }

    slides = create_fallback_lesson_content_slides(lesson, is_spanish=True)

    assert slides
    assert all(slide["title"] != "Introducción" for slide in slides)
    assert any("Arquitectura orientada a eventos" in slide["title"] for slide in slides)