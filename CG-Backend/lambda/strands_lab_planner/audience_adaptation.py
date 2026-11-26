"""Audience and course-format profiles for THOR audience adaptation (audit item 7).

Deterministic: no LLM calls. Used by content generation, lab planner and lab writer prompts.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

SHORT_COURSE_MAX_MINUTES = 180
COPILOT_PRODUCTIVITY_STEP_SCALE = 0.6
COPILOT_PRODUCTIVITY_BLOCK_SCALE = 0.75
SHORT_COURSE_THEORY_WORD_SCALE = 0.75
COPILOT_THEORY_WORD_SCALE = 0.55

_COPILOT_MARKERS = (
    "copilot",
    "m365",
    "microsoft 365",
    "office 365",
    "productividad",
    "productivity",
    "usuario final",
    "usuarios finales",
    "end user",
    "end-user",
    "end users",
)

_PRODUCTIVITY_MARKERS = (
    "productividad",
    "productivity",
    "usuario final",
    "usuarios finales",
    "end user",
    "end-user",
    "herramientas de productividad",
    "productivity tools",
)


def _as_text_list(value: Union[str, List[Any], None]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.replace(";", ",").split(",")
        return [p.strip() for p in raw if p and p.strip()]
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if isinstance(item, dict):
                bit = item.get("title") or item.get("name") or item.get("label")
                if bit:
                    out.append(str(bit).strip())
            elif item is not None and str(item).strip():
                out.append(str(item).strip())
        return out
    return [str(value).strip()] if str(value).strip() else []


def _hay_marcador(texto: str, marcadores: tuple[str, ...]) -> bool:
    t = (texto or "").lower()
    return any(m in t for m in marcadores)


def _duracion_total_minutos(course_info: dict) -> int:
    for key in ("total_duration_minutes", "duration_minutes", "total_minutes"):
        try:
            val = int(course_info.get(key) or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            return val
    try:
        hours = float(course_info.get("duration_hours") or course_info.get("course_duration_hours") or 0)
    except (TypeError, ValueError):
        hours = 0.0
    if hours > 0:
        return int(round(hours * 60))
    total = 0
    for mod in course_info.get("modules") or []:
        if not isinstance(mod, dict):
            continue
        try:
            total += int(mod.get("duration_minutes") or 0)
        except (TypeError, ValueError):
            pass
    return total


def resolve_audience_profile(course_info: Optional[dict]) -> Dict[str, Any]:
    """Build a stable profile dict from syllabus ``course`` metadata."""
    course_info = course_info or {}
    audience_bits = _as_text_list(course_info.get("audience"))
    audience_bits.extend(_as_text_list(course_info.get("target_audience")))
    corpus = " ".join(
        [
            course_info.get("title", ""),
            course_info.get("description", ""),
            " ".join(audience_bits),
        ]
    )

    copilot_signal = _hay_marcador(corpus, _COPILOT_MARKERS)
    productivity_signal = _hay_marcador(corpus, _PRODUCTIVITY_MARKERS) or copilot_signal
    total_minutes = _duracion_total_minutos(course_info)
    is_short = 0 < total_minutes <= SHORT_COURSE_MAX_MINUTES

    is_copilot_productivity = bool(copilot_signal and productivity_signal)

    if is_copilot_productivity:
        profile_name = "copilot_productivity"
    elif is_short:
        profile_name = "short_seminar"
    else:
        profile_name = "standard"

    return {
        "profile": profile_name,
        "is_copilot_productivity": is_copilot_productivity,
        "is_short_course": is_short,
        "total_duration_minutes": total_minutes,
        "audience_labels": audience_bits,
        "step_scale": COPILOT_PRODUCTIVITY_STEP_SCALE if is_copilot_productivity else 1.0,
        "block_scale": COPILOT_PRODUCTIVITY_BLOCK_SCALE if is_copilot_productivity else 1.0,
        "theory_word_scale": (
            COPILOT_THEORY_WORD_SCALE
            if is_copilot_productivity
            else (SHORT_COURSE_THEORY_WORD_SCALE if is_short else 1.0)
        ),
    }


def adjust_presupuesto(presupuesto: dict, profile: Optional[dict]) -> dict:
    """Tighten step/block ceilings for Copilot productivity courses."""
    if not presupuesto:
        return presupuesto or {}
    profile = profile or {}
    step_scale = float(profile.get("step_scale") or 1.0)
    block_scale = float(profile.get("block_scale") or 1.0)
    if step_scale >= 1.0 and block_scale >= 1.0:
        return presupuesto
    out = dict(presupuesto)
    out["pasos_max"] = max(2, int(out.get("pasos_max", 0) * step_scale))
    out["pasos_objetivo"] = max(2, int(out.get("pasos_objetivo", 0) * step_scale))
    out["bloques_max"] = max(1, int(out.get("bloques_max", 0) * block_scale))
    out["bloques_objetivo"] = max(1, int(out.get("bloques_objetivo", 0) * block_scale))
    out["audience_adjusted"] = True
    return out


def planner_audience_block(profile: dict, course_info: dict) -> str:
    if not profile or profile.get("profile") == "standard":
        return ""
    audience_line = ", ".join(profile.get("audience_labels") or []) or "N/A"
    if profile.get("is_copilot_productivity"):
        return f"""
AUDIENCE & FORMAT (syllabus — Copilot / end-user productivity):
- Target audience: {audience_line}
- Prefer instructor-led demos and quick, visible outcomes over long theory in the lab plan.
- Keep each practice scope short: fewer steps, prompt-in-UI work over shell pipelines.
- Where the syllabus allows, mark suitable activities as Demo (instructor performs; students observe).
- Objectives should emphasize applied tool use, not deep platform architecture.
"""
    if profile.get("is_short_course"):
        mins = profile.get("total_duration_minutes") or course_info.get("duration_minutes", "")
        return f"""
AUDIENCE & FORMAT (short course ~{mins} minutes):
- Target audience: {audience_line}
- Favor demos and concise practices; avoid stacking many long labs in one module.
- Theory in the book should stay brief and point students to the live demo/lab for detail.
"""
    return ""


def writer_audience_block(profile: dict, spanish: bool = True) -> str:
    if not profile or profile.get("profile") == "standard":
        return ""
    if profile.get("is_copilot_productivity"):
        if spanish:
            return """
ADAPTACIÓN DE AUDIENCIA (Copilot / productividad usuario final):
- Prioriza resultados rápidos en la interfaz (prompts, botones, paneles) frente a teoría o scripts largos.
- Menos pasos por práctica: cada paso debe mostrar un cambio visible en menos de 2 minutos.
- Incluye prompts listos para copiar cuando aplique; evita recorridos de configuración profunda salvo que el temario lo exija.
- La validación debe comprobar elementos concretos (lista, borrador, resumen), no párrafos deterministas largos.
"""
        return """
AUDIENCE ADAPTATION (Copilot / end-user productivity):
- Favor quick UI outcomes (prompts, buttons, panels) over long theory or shell-heavy flows.
- Fewer steps per practice: each step should show a visible change in under about 2 minutes.
- Provide copy-ready prompts where applicable; avoid deep setup detours unless the syllabus requires them.
- Validation should check concrete elements (lists, drafts, summaries), not long deterministic paragraphs.
"""
    if profile.get("is_short_course"):
        if spanish:
            return """
ADAPTACIÓN DE AUDIENCIA (seminario breve):
- Mantén las instrucciones compactas y orientadas a la demostración efectiva de la herramienta.
"""
        return """
AUDIENCE ADAPTATION (short seminar):
- Keep instructions compact and focused on effective tool demonstration.
"""
    return ""


def content_audience_block(profile: dict, spanish: bool = True) -> str:
    if not profile or profile.get("profile") == "standard":
        return ""
    audience_line = ", ".join(profile.get("audience_labels") or []) or "N/A"
    if profile.get("is_copilot_productivity"):
        if spanish:
            return f"""
═══════════════════════════════════════════════════════════════════════════════
ADAPTACIÓN DE AUDIENCIA (Copilot / productividad — obligatorio)
═══════════════════════════════════════════════════════════════════════════════
- Audiencia del temario: {audience_line}
- Menos teoría repetitiva: en cada lección teórica, resume conceptos y remite a la demostración o guía de laboratorio para el detalle operativo.
- Prioriza uso efectivo de la herramienta frente a arquitectura o historia del producto.
- Donde el temario incluya práctica o demo, el libro no debe duplicar pasos largos; enlaza conceptualmente a la guía de laboratorio.
- Reduce la extensión objetivo (~{int(profile.get('theory_word_scale', 1) * 100)}% del habitual) salvo lecciones marcadas como laboratorio/demo.
"""
        return f"""
═══════════════════════════════════════════════════════════════════════════════
AUDIENCE ADAPTATION (Copilot / productivity — mandatory)
═══════════════════════════════════════════════════════════════════════════════
- Syllabus audience: {audience_line}
- Less repetitive theory: in each theory lesson, summarize concepts and point to the demo or lab guide for operational detail.
- Prioritize effective tool use over platform architecture or product history.
- Where the syllabus includes practice or demo, do not duplicate long steps in the book; reference the lab guide conceptually.
- Reduce target length (~{int(profile.get('theory_word_scale', 1) * 100)}% of the usual) except lessons marked lab/demo.
"""
    if profile.get("is_short_course"):
        if spanish:
            return f"""
═══════════════════════════════════════════════════════════════════════════════
ADAPTACIÓN DE AUDIENCIA (curso breve)
═══════════════════════════════════════════════════════════════════════════════
- Audiencia: {audience_line}
- Prioriza demostraciones y aplicación práctica; evita capítulos teóricos extensos que repitan la demo.
"""
        return f"""
═══════════════════════════════════════════════════════════════════════════════
AUDIENCE ADAPTATION (short course)
═══════════════════════════════════════════════════════════════════════════════
- Audience: {audience_line}
- Favor demos and hands-on application; avoid lengthy theory chapters that repeat the demo.
"""
    return ""


def _ya_es_practica(lesson: dict) -> bool:
    tipo = str(lesson.get("type") or lesson.get("lesson_type") or "").lower()
    titulo = str(lesson.get("title") or "").lower()
    if tipo in {
        "demo", "demostracion", "demostración", "lab", "practice", "activity",
        "lab_activity", "laboratorio", "práctica", "practica",
    }:
        return True
    return titulo.startswith("demo") or "demostración" in titulo or "laboratorio" in titulo


def promover_teoria_a_demo(lesson: dict, profile: Optional[dict]) -> dict:
    """Turn a theory-only lesson into a short instructor demo when the audience needs one.

    ``THEORY_TO_DEMO=0`` leaves the lesson. Standard courses are unchanged.
    Copilot and short-course profiles get a demo title and a bilingual note.
    """
    if os.environ.get("THEORY_TO_DEMO", "1") == "0":
        return lesson
    if not isinstance(lesson, dict) or not profile:
        return lesson
    if not (profile.get("is_copilot_productivity") or profile.get("is_short_course")):
        return lesson
    if _ya_es_practica(lesson):
        return lesson
    nuevo = dict(lesson)
    titulo = str(nuevo.get("title") or "Demostración").strip()
    if not titulo.lower().startswith("demo"):
        nuevo["title"] = f"Demo: {titulo}"
    nuevo["type"] = "demo"
    nota = (
        "Segmento breve de demostración del instructor. "
        "/ Short instructor demo segment."
    )
    nuevo["description"] = (str(nuevo.get("description") or "") + " " + nota).strip()
    return nuevo


def scale_theory_target_words(base_words: int, profile: Optional[dict], *, is_lab_or_demo: bool) -> int:
    if is_lab_or_demo:
        return base_words
    profile = profile or {}
    scale = float(profile.get("theory_word_scale") or 1.0)
    if scale >= 1.0:
        return base_words
    scaled = int(base_words * scale)
    return max(400, min(base_words, scaled))