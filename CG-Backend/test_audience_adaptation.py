"""Offline tests for THOR audience adaptation (audit backlog item 7 / fix #10)."""

import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_CARPETA_WRITER = os.path.join("lambda", "strands_lab_writer")
_CARPETA_PLANNER = os.path.join("lambda", "strands_lab_planner")
_CARPETA_CONTENT = os.path.join("lambda", "strands_content_gen")
_WRITER = os.path.join(_HERE, "lambda", "strands_lab_writer")
_PLANNER = os.path.join(_HERE, "lambda", "strands_lab_planner")
_CONTENT = os.path.join(_HERE, "lambda", "strands_content_gen")
for _p in (_WRITER, _PLANNER, _CONTENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from audience_adaptation import (  # noqa: E402
    adjust_presupuesto,
    content_audience_block,
    planner_audience_block,
    resolve_audience_profile,
    scale_theory_target_words,
)
from referent_check import presupuesto_de_duracion  # noqa: E402


class _ClienteSimulado:
    def __getattr__(self, _nombre):
        return lambda *a, **k: None


def _cargar_modulo(nombre: str, carpeta: str):
    """Import a Lambda module with boto3 stubbed (no AWS)."""
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", nombre)
    previos = {n: sys.modules.get(n) for n in nombres}

    class _ClientErrorSimulado(Exception):
        pass

    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: _ClienteSimulado()
    botocore_sim = types.ModuleType("botocore")
    config_sim = types.ModuleType("botocore.config")
    config_sim.Config = lambda *a, **k: None
    exceptions_sim = types.ModuleType("botocore.exceptions")
    exceptions_sim.ClientError = _ClientErrorSimulado
    botocore_sim.config = config_sim
    botocore_sim.exceptions = exceptions_sim
    sys.modules.update(
        {
            "boto3": boto3_sim,
            "botocore": botocore_sim,
            "botocore.config": config_sim,
            "botocore.exceptions": exceptions_sim,
        }
    )
    sys.modules.pop(nombre, None)
    ruta = os.path.join(_HERE, carpeta)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    import importlib

    modulo = importlib.import_module(nombre)
    for clave, previo in previos.items():
        if clave == nombre:
            continue
        if previo is None:
            sys.modules.pop(clave, None)
        else:
            sys.modules[clave] = previo
    return modulo


COPILOT_COURSE = {
    "title": "Microsoft 365 Copilot para usuarios finales",
    "description": "Seminario de productividad con Copilot Chat en M365.",
    "duration_minutes": 90,
    "audience": [
        "Profesionales de oficina que buscan productividad",
        "Usuarios finales de Microsoft 365",
    ],
    "language": "es",
}

STANDARD_COURSE = {
    "title": "Administración avanzada de Kubernetes",
    "description": "Curso técnico de clústeres en producción.",
    "duration_minutes": 480,
    "audience": ["Administradores de sistemas"],
    "language": "es",
}


def test_resolve_copilot_productivity_profile():
    profile = resolve_audience_profile(COPILOT_COURSE)
    assert profile["is_copilot_productivity"]
    assert profile["is_short_course"]
    assert profile["profile"] == "copilot_productivity"
    assert profile["step_scale"] < 1.0


def test_standard_course_keeps_default_profile():
    profile = resolve_audience_profile(STANDARD_COURSE)
    assert profile["profile"] == "standard"
    assert profile["step_scale"] == 1.0
    assert not content_audience_block(profile, spanish=True)


def test_adjust_presupuesto_reduces_steps_for_copilot():
    base = presupuesto_de_duracion(45)
    profile = resolve_audience_profile(COPILOT_COURSE)
    tuned = adjust_presupuesto(base, profile)
    assert tuned["pasos_max"] < base["pasos_max"]
    assert tuned["pasos_objetivo"] < base["pasos_objetivo"]
    assert tuned["pasos_max"] == 13  # 22 * 0.6 rounded down


def test_theory_word_scale_for_copilot():
    assert scale_theory_target_words(2000, resolve_audience_profile(COPILOT_COURSE), is_lab_or_demo=False) == 1100
    assert scale_theory_target_words(2000, resolve_audience_profile(COPILOT_COURSE), is_lab_or_demo=True) == 2000


def test_planner_block_mentions_demos():
    block = planner_audience_block(resolve_audience_profile(COPILOT_COURSE), COPILOT_COURSE)
    assert "AUDIENCE & FORMAT" in block
    assert "Demo" in block
    assert "fewer steps" in block.lower()


def test_writer_compact_prompt_receives_audience_and_tighter_budget():
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)

    lab_plan = {
        "lab_id": "01-00-01",
        "lab_title": "Resumir correos con Copilot",
        "objectives": ["usar Copilot en Outlook"],
        "scope": "productividad",
        "estimated_duration": 45,
        "complexity": "medium",
        "bloom_level": "Apply",
        "prerequisites": [],
        "key_technologies": ["Microsoft 365 Copilot"],
    }
    profile = resolve_audience_profile(COPILOT_COURSE)
    master_context = {
        "target_language": "Spanish (Español)",
        "manual_reference_text": "",
        "additional_requirements": "",
        "hardware_requirements": [],
        "software_requirements": [],
        "special_considerations": [],
        "overall_objectives": [],
        "audience_profile": profile,
    }
    prompt = modulo._compact_single_lab_prompt(lab_plan, master_context, "", "resumen del lab")
    assert "ADAPTACIÓN DE AUDIENCIA (Copilot" in prompt
    assert "Máximo 13 pasos con acción y 45 bloques" in prompt


def test_content_prompt_builder_includes_audience_block():
    """Live path: generate_batch_single_call must embed the audience section in the prompt."""
    from unittest.mock import patch

    modulo = _cargar_modulo("strands_content_gen", _CARPETA_CONTENT)

    module_data = {
        "title": "Copilot en el día a día",
        "description": "",
        "duration_minutes": 90,
        "bloom_level": "Apply",
        "lessons": [
            {
                "title": "Introducción a Copilot Chat",
                "duration_minutes": 30,
                "bloom_level": "Understand",
                "topics": [{"title": "Panel de Copilot", "duration_minutes": 15}],
                "lab_activities": [],
            }
        ],
    }
    captured = {}

    def fake_bedrock(prompt, model_id=None):
        captured["prompt"] = prompt
        return (
            "═══════════════════════════════════════════════════════════════════════\n"
            "# 1.1: Intro\n\n## Objetivos de Aprendizaje\n\n- Ver\n\n## Introducción\n\nTexto\n"
        )

    course_data = dict(COPILOT_COURSE)
    course_data["modules"] = [module_data]

    with patch.object(modulo, "call_bedrock", side_effect=fake_bedrock):
        with patch.object(modulo, "parse_lessons_from_response", return_value=[{"title": "x"}]):
            modulo.generate_batch_single_call(
                1,
                0,
                1,
                module_data,
                course_data,
                model_provider="bedrock",
            )

    prompt = captured.get("prompt", "")
    assert "ADAPTACIÓN DE AUDIENCIA (Copilot" in prompt
    # 30 min theory lesson scaled to 55% of default (~1565 → ~861 words)
    assert "Extensión objetivo: ~860 palabras" in prompt


def test_planner_master_plan_prompt_includes_audience():
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)

    prompts = []

    def modelo_de_prueba(prompt, model_id):
        prompts.append(prompt)
        return json.dumps(
            {
                "overall_objectives": ["obj"],
                "hardware_requirements": [],
                "software_requirements": [],
                "lab_plans": [
                    {
                        "lab_id": "01-00-01",
                        "lab_title": "Copilot en Outlook",
                        "objectives": ["resumir"],
                        "scope": "demo guiada",
                        "estimated_duration": 15,
                        "bloom_level": "Apply",
                        "prerequisites": [],
                        "key_technologies": ["Copilot"],
                        "expected_outcomes": ["borrador"],
                        "complexity": "easy",
                    }
                ],
                "special_considerations": [],
            }
        )

    modulo.call_bedrock_agent = modelo_de_prueba
    labs = [
        {
            "lab_id": "01-00-01",
            "module_number": 1,
            "lesson_number": 0,
            "lab_title": "Copilot en Outlook",
            "duration_minutes": 15,
            "bloom_level": "Apply",
            "context_topics": ["Copilot"],
        }
    ]
    modulo.generate_lab_master_plan(
        labs=labs,
        course_info=COPILOT_COURSE,
        additional_requirements=None,
        model_provider="bedrock",
    )
    assert prompts
    assert "AUDIENCE & FORMAT" in prompts[0]
    assert "fewer steps" in prompts[0].lower()


if __name__ == "__main__":
    for _name in sorted(n for n in globals() if n.startswith("test_")):
        globals()[_name]()
        print("OK", _name)
    print("ALL PASSED", len([n for n in globals() if n.startswith("test_")]))