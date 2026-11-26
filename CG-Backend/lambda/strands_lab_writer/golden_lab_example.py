"""
Few-shot golden lab slice for the compact lab writer prompt (THOR audit item 9).

Loads a small on-disk fixture and injects it when the lab plan looks like a fully
specified technical practice (duration + declared outline contract + technologies).
"""

from __future__ import annotations

import os
from typing import Any, Dict

# Stable marker for unit tests (also appears in the prompt header).
GOLDEN_LAB_SECTION_MARKER = "QUALITY REFERENCE LAB (FEW-SHOT — LPI-010 target)"

_FIXTURE_NAME = "golden_lab_lpi010_slice.md"


def _fixture_path() -> str:
    return os.path.join(os.path.dirname(__file__), "fixtures", _FIXTURE_NAME)


def load_golden_lab_slice() -> str:
    """Return the curated markdown slice; empty string if the fixture is missing."""
    path = _fixture_path()
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _is_spanish_target(target_language: str) -> bool:
    tl = (target_language or "").lower()
    return "spanish" in tl or "español" in tl or tl.startswith("es")


def _plan_is_fully_specified(lab_plan: dict) -> bool:
    """Outline contract + duration: the syllabus supplied enough structure to anchor quality."""
    duration = lab_plan.get("estimated_duration") or lab_plan.get("duration_minutes")
    try:
        duration_ok = duration is not None and int(duration) > 0
    except (TypeError, ValueError):
        duration_ok = False
    if not duration_ok:
        return False

    objective = (lab_plan.get("outline_objective") or "").strip()
    descripcion = (lab_plan.get("outline_description") or "").strip()
    if objective or descripcion:
        return True

    objectives = lab_plan.get("objectives") or []
    technologies = lab_plan.get("key_technologies") or []
    return bool(objectives and technologies)


def _is_demo_lab(lab_plan: dict) -> bool:
    if lab_plan.get("is_demo"):
        return True
    if str(lab_plan.get("lab_type", "")).lower() == "demo":
        return True
    title = str(lab_plan.get("lab_title", "")).lower()
    return "demo" in title or "demostración" in title or "demostracion" in title


def _plan_is_technical(lab_plan: dict) -> bool:
    if _is_demo_lab(lab_plan):
        return False

    tech_blob = " ".join(
        str(x) for x in (lab_plan.get("key_technologies") or []) + (lab_plan.get("objectives") or [])
    ).lower()
    scope = str(lab_plan.get("scope") or "").lower()
    combined = f"{tech_blob} {scope}"
    technical_tokens = (
        "linux",
        "bash",
        "shell",
        "python",
        "docker",
        "kubernetes",
        "sql",
        "powershell",
        "cli",
        "ubuntu",
        "red hat",
        "rhel",
        "lpi",
        "devops",
        "git",
        "network",
        "seguridad",
        "sistema operativo",
    )
    return any(token in combined for token in technical_tokens)


def should_include_golden_lab_example(lab_plan: dict, master_context: Dict[str, Any]) -> bool:
    """Gate: inject the few-shot only for non-demo technical labs with syllabus anchors."""
    if _is_demo_lab(lab_plan):
        return False
    if not _plan_is_fully_specified(lab_plan):
        return False
    if not _plan_is_technical(lab_plan):
        return False
    if not load_golden_lab_slice():
        return False
    return True


def build_planner_golden_section() -> str:
    """Few-shot for the lab planner. ``PLANNER_GOLDEN_LAB=0`` returns empty.

    The planner sees the same LPI-010 slice as the writer and is told not to
    copy its file names into the plan.
    """
    if os.environ.get("PLANNER_GOLDEN_LAB", "1") == "0":
        return ""
    slice_md = load_golden_lab_slice()
    if not slice_md:
        return ""
    return (
        f"{GOLDEN_LAB_SECTION_MARKER}:\n"
        "Use this Linux Essentials (LPI-010) slice as the shape of a lab plan: "
        "metadata, one objective, numbered steps, expected output and a check. "
        "Do not copy its file names, paths or commands into this course. "
        "Úselo como forma del plan (metadatos, objetivo, pasos, salida esperada "
        "y comprobación). No copie sus ficheros, rutas ni comandos.\n\n"
        f"{slice_md}\n"
    )


def build_golden_lab_prompt_section(
    lab_plan: dict,
    master_context: Dict[str, Any],
) -> str:
    """Spanish/English wrapper around the fixture; empty when gated off."""
    if not should_include_golden_lab_example(lab_plan, master_context):
        return ""

    slice_md = load_golden_lab_slice()
    if not slice_md:
        return ""

    is_spanish = _is_spanish_target(master_context.get("target_language", ""))
    if is_spanish:
        intro = (
            f"{GOLDEN_LAB_SECTION_MARKER}:\n"
            "El siguiente fragmento proviene del curso de referencia **Linux Essentials (LPI-010)** "
            "cuando esté disponible en el repositorio; mientras tanto es un recorte estructural "
            "de alta calidad. **Imite la estructura de secciones, la tabla de metadatos y el "
            "formato de cada paso** (Objetivo, Instrucciones numeradas, Salida esperada, Verificación). "
            "No copie nombres de ficheros ni rutas: adapte al temario actual.\n"
        )
    else:
        intro = (
            f"{GOLDEN_LAB_SECTION_MARKER}:\n"
            "The excerpt below is the **Linux Essentials (LPI-010)** quality target when that "
            "course is checked in; until then it is a high-quality structural stand-in. "
            "**Mirror section headings, the metadata table, and per-step fields** (Objective, "
            "numbered Instructions, Expected output, Verification). Do not copy file names or paths; "
            "adapt to the current lab specification.\n"
        )
    return f"{intro}\n---BEGIN GOLDEN LAB SLICE---\n{slice_md}\n---END GOLDEN LAB SLICE---\n"