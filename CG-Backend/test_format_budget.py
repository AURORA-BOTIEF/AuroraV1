"""Format budget: cap or merge practices before lab generation.

The audit's failure is a 2-hour module with 30 minutes of practice and 11 labs.
Pre-flight only warned (2.7 min/lab) and generation continued. The saved plan
must come back to 1 or 2 practices, and the named overruns MS-4018 (185 min),
MS-4023 (97 min) and AI-3025 (143 min) must not exceed the syllabus minutes.

No AWS and no model calls.

    python3 test_format_budget.py
"""

import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLANNER = os.path.join(_HERE, "lambda", "strands_lab_planner")
sys.path.insert(0, _PLANNER)

from format_budget import (  # noqa: E402
    aplicar_presupuesto_de_formato,
    detectar_formato,
)


def _planes(duraciones, modulo="01"):
    return [
        {
            "lab_id": f"{modulo}-00-{indice:02d}",
            "lab_title": f"Práctica {indice}",
            "estimated_duration": minutos,
            "objectives": [f"Objetivo {indice}"],
            "scope": f"Alcance de la práctica {indice}.",
            "expected_outcomes": [f"Resultado {indice}"],
        }
        for indice, minutos in enumerate(duraciones, start=1)
    ]


def _curso(**kwargs):
    curso = {
        "title": kwargs.pop("title"),
        "total_duration_minutes": kwargs.pop("total"),
        "modules": kwargs.pop("modules"),
    }
    curso.update(kwargs)
    return curso


def _modulo(duracion, porcentaje, actividades, titulo="Módulo"):
    modulo = {"title": titulo, "duration_minutes": duracion}
    if porcentaje is not None:
        modulo["percent_practice"] = porcentaje
    modulo["lab_activities"] = actividades
    return modulo


def _aplicar(curso, duraciones, modulo="01"):
    plan = {"lab_plans": _planes(duraciones, modulo)}
    informe = aplicar_presupuesto_de_formato(curso, plan)
    return plan, informe


def _suma(plan):
    return sum(lab["estimated_duration"] for lab in plan["lab_plans"])


def test_una_conferencia_de_2h_se_detecta_por_los_minutos():
    """2 h with 30 min of practice is a conference even without the word."""
    curso = _curso(
        title="Sesión de Copilot",
        total=120,
        modules=[_modulo(120, 25, [])],
    )
    assert detectar_formato(curso) == "conference"


def test_el_campo_formato_manda_sobre_la_duracion():
    curso = _curso(
        title="Programa largo",
        formato="seminario",
        total=960,
        modules=[_modulo(120, 25, [])],
    )
    assert detectar_formato(curso) == "seminar"
    curso["format"] = "conference"
    assert detectar_formato(curso) == "conference"
    curso["format"] = "curso completo"
    assert detectar_formato(curso) == "course"


def test_un_seminario_de_90_min_no_se_trata_como_conferencia():
    curso = _curso(
        title="Seminario de herramientas",
        total=90,
        modules=[_modulo(90, 50, [])],
    )
    assert detectar_formato(curso) == "seminar"


def test_once_practicas_en_una_conferencia_de_2h_caben_en_una_o_dos():
    """Audit regression: 11 labs, 2 h, 25% practice (30 min) → 1 or 2 labs."""
    curso = _curso(
        title="Conferencia de 2 horas",
        total=120,
        modules=[_modulo(120, 25, [{"title": f"Práctica {i}"} for i in range(1, 12)])],
    )
    plan, informe = _aplicar(curso, [30] * 11)
    duraciones = [lab["estimated_duration"] for lab in plan["lab_plans"]]

    assert informe["perfil"] == "conference"
    assert informe["excede"] is False
    assert 1 <= len(plan["lab_plans"]) <= 2
    assert _suma(plan) <= 30
    assert _suma(plan) <= 120
    assert all(12 <= minutos <= 30 for minutos in duraciones)
    fuentes = []
    for grupo in informe["modulos"][0]["combinados"]:
        fuentes.extend(grupo["fuentes"])
    assert fuentes == [f"01-00-{indice:02d}" for indice in range(1, 12)]
    assert "syllabus_items_combined" in plan["lab_plans"][0]
    assert "Actividades del temario reunidas" in plan["lab_plans"][0]["scope"]
    for lab in plan["lab_plans"]:
        assert lab["presupuesto_duracion"]["declarada"] == lab["estimated_duration"]


def test_ms_4018_185_min_no_supera_el_temario():
    """MS-4018 planned 185 minutes. A 2 h conference budgets 30 of them."""
    curso = _curso(
        title="MS-4018",
        format="conferencia",
        total=120,
        modules=[_modulo(120, 25, [{"title": "Práctica", "duration_minutes": 185}])],
    )
    plan, informe = _aplicar(curso, [185])
    assert informe["excede"] is False
    assert _suma(plan) <= 30
    assert _suma(plan) < 185
    assert plan["lab_plans"][0]["estimated_duration"] <= 120


def test_ms_4023_97_min_no_supera_el_temario():
    """MS-4023 planned 97 minutes. The seminar budgets 64."""
    curso = _curso(
        title="MS-4023",
        format="seminar",
        total=160,
        modules=[
            _modulo(
                160,
                40,
                [{"title": f"Práctica {i}", "duration_minutes": minutos} for i, minutos in enumerate((20, 20, 20, 20, 17), start=1)],
            )
        ],
    )
    plan, informe = _aplicar(curso, [20, 20, 20, 20, 17])
    assert detectar_formato(curso) == "seminar"
    assert informe["excede"] is False
    assert _suma(plan) <= 64
    assert _suma(plan) < 97
    assert _suma(plan) <= 160
    assert all(lab["estimated_duration"] <= 64 for lab in plan["lab_plans"])


def test_ai_3025_143_min_no_supera_el_temario():
    """AI-3025 planned 143 minutes. The module budgets 96 of a full course."""
    curso = _curso(
        title="AI-3025",
        format="curso completo",
        total=960,
        modules=[
            _modulo(
                240,
                40,
                [
                    {"title": "Práctica 1", "duration_minutes": 48},
                    {"title": "Práctica 2", "duration_minutes": 48},
                    {"title": "Práctica 3", "duration_minutes": 47},
                ],
            )
        ],
    )
    plan, informe = _aplicar(curso, [48, 48, 47])
    assert detectar_formato(curso) == "course"
    assert informe["excede"] is False
    assert _suma(plan) <= 96
    assert _suma(plan) < 143
    assert _suma(plan) <= 960


def test_una_conferencia_sin_porcentaje_reserva_30_minutos_de_demo():
    curso = _curso(
        title="Conferencia de adopción",
        total=120,
        modules=[{"title": "Módulo", "duration_minutes": 120}],
    )
    plan, informe = _aplicar(curso, [20] * 11)
    assert informe["perfil"] == "conference"
    assert 1 <= len(plan["lab_plans"]) <= 2
    assert _suma(plan) <= 30


def test_no_infla_una_practica_que_ya_cabe():
    """A syllabus lab of 10 minutes stays 10. The gate only cuts overruns."""
    curso = _curso(
        title="Curso de prueba",
        total=120,
        modules=[_modulo(120, 50, [])],
    )
    plan, informe = _aplicar(curso, [10, 10])
    assert informe["ajustado"] is False
    assert [lab["estimated_duration"] for lab in plan["lab_plans"]] == [10, 10]


def test_un_curso_largo_que_cabe_no_se_fusiona():
    curso = _curso(
        title="Programa de datos",
        format="curso completo",
        total=960,
        modules=[_modulo(300, 50, [])],
    )
    plan, informe = _aplicar(curso, [30, 30, 30, 30])
    assert informe["perfil"] == "course"
    assert informe["ajustado"] is False
    assert len(plan["lab_plans"]) == 4
    assert _suma(plan) == 120


def test_un_modulo_corto_dentro_de_un_curso_largo_sigue_teniendo_techo():
    """A 16 h course does not exempt a 2 h module that only budgets 30 min."""
    curso = _curso(
        title="Programa de datos",
        total=960,
        modules=[_modulo(120, 25, [], titulo="Módulo corto")],
    )
    plan, informe = _aplicar(curso, [30] * 11)
    assert informe["perfil"] == "course"
    assert 1 <= len(plan["lab_plans"]) <= 2
    assert _suma(plan) <= 30


def test_porcentaje_cero_descarta_las_practicas():
    curso = _curso(
        title="Curso teórico",
        total=120,
        modules=[_modulo(120, 0, [])],
    )
    plan, informe = _aplicar(curso, [30, 30, 30])
    assert plan["lab_plans"] == []
    assert len(informe["modulos"][0]["descartados"]) == 3
    assert informe["suma_despues"] == 0


def test_el_idioma_ingles_no_recibe_la_nota_en_espanol():
    curso = _curso(
        title="Conference",
        language="en",
        total=120,
        modules=[_modulo(120, 25, [])],
    )
    plan, _informe = _aplicar(curso, [30] * 4)
    assert plan["lab_plans"][0]["scope"].startswith("Syllabus activities combined")


def test_la_suma_de_los_modulos_no_supera_el_total_del_curso():
    """Each module fits its own budget and the course total still wins."""
    curso = _curso(
        title="Seminario",
        total=100,
        modules=[
            _modulo(80, 100, [], titulo="A"),
            _modulo(80, 100, [], titulo="B"),
        ],
    )
    plan = {"lab_plans": _planes([40, 40], "01") + _planes([40, 40], "02")}
    informe = aplicar_presupuesto_de_formato(curso, plan)
    assert informe["excede"] is False
    assert informe["recorte_total_curso"] is True
    assert _suma(plan) <= 100
    assert all(lab["estimated_duration"] <= 80 for lab in plan["lab_plans"])


def test_el_total_del_curso_recorta_aunque_el_modulo_no_tenga_porcentaje():
    curso = _curso(
        title="Taller",
        total=90,
        modules=[{"title": "Módulo", "duration_minutes": 90}],
    )
    plan, informe = _aplicar(curso, [100, 85])
    assert informe["excede"] is False
    assert _suma(plan) <= 90


# --------------------------------------------------------------------------- #
# Live planner path. The model is stubbed; A3 runs first and would otherwise
# copy the overrun back onto the plan.
# --------------------------------------------------------------------------- #


class _ClienteSimulado:
    def __getattr__(self, _nombre):
        return lambda *a, **k: None


def _cargar_planner():
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", "strands_lab_planner")
    previos = {nombre: sys.modules.get(nombre) for nombre in nombres}

    class _ClientError(Exception):
        pass

    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: _ClienteSimulado()
    botocore_sim = types.ModuleType("botocore")
    config_sim = types.ModuleType("botocore.config")
    config_sim.Config = lambda *a, **k: None
    exceptions_sim = types.ModuleType("botocore.exceptions")
    exceptions_sim.ClientError = _ClientError
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
    sys.modules.pop("strands_lab_planner", None)
    if _PLANNER not in sys.path:
        sys.path.insert(0, _PLANNER)
    try:
        import importlib

        return importlib.import_module("strands_lab_planner")
    finally:
        for clave, previo in previos.items():
            if previo is None:
                sys.modules.pop(clave, None)
            else:
                sys.modules[clave] = previo


def _handler(outline, planes, evento_extra=None, plan_existente=None):
    modulo = _cargar_planner()
    guardado = {}
    modulo.load_outline_from_s3 = lambda *a, **k: outline
    modulo.generate_lab_master_plan = lambda **k: {"lab_plans": planes}
    modulo.auditar_y_corregir_plan = lambda plan, **k: (
        plan,
        {"total": 0, "violaciones": [], "ok": True},
    )
    modulo.load_master_plan_from_s3 = lambda *a, **k: plan_existente
    modulo.save_master_plan_to_s3 = lambda bucket, project_folder, master_plan: (
        guardado.update({"plan": master_plan}) or "p/labguide/lab-master-plan.json"
    )
    modulo.s3_client = _ClienteSimulado()
    evento = {
        "course_bucket": "bucket",
        "outline_s3_key": "p/outline/curso.yaml",
        "project_folder": "p",
        "model_provider": "bedrock",
    }
    if evento_extra:
        evento.update(evento_extra)
    resultado = modulo.lambda_handler(evento, None)
    assert resultado["statusCode"] == 200, resultado
    return guardado["plan"]


def _outline_conferencia(n, duracion_lab):
    return {
        "course": {
            "title": "Conferencia de 2 horas",
            "total_duration_minutes": 120,
            "modules": [
                {
                    "title": "Módulo único",
                    "duration_minutes": 120,
                    "percent_practice": 25,
                    "lab_activities": [
                        {"title": f"Práctica {indice}", "duration_minutes": duracion_lab}
                        for indice in range(1, n + 1)
                    ],
                }
            ],
        }
    }


def _planes_modelo(n, minutos):
    return [
        {
            "lab_id": f"01-00-{indice:02d}",
            "lab_title": f"Práctica {indice}",
            "estimated_duration": minutos,
            "objectives": ["objetivo del modelo"],
            "scope": f"Alcance {indice}.",
            "expected_outcomes": ["resultado"],
        }
        for indice in range(1, n + 1)
    ]


def test_el_planner_reduce_las_11_practicas_antes_de_guardar():
    """Live path: A3 copies the syllabus minutes, then the gate cuts them."""
    plan = _handler(_outline_conferencia(11, 30), _planes_modelo(11, 40))
    duraciones = [lab["estimated_duration"] for lab in plan["lab_plans"]]
    assert 1 <= len(plan["lab_plans"]) <= 2
    assert sum(duraciones) <= 30
    assert all(minutos <= 30 for minutos in duraciones)
    preflight = plan["metadata"]["preflight_duracion"]
    assert preflight["gate"]["aplicado"] is True
    assert preflight["gate"]["excede"] is False
    assert "poco_tiempo" not in preflight["modulos"][0]["senales"]
    assert "sobre_comprometido" not in preflight["modulos"][0]["senales"]
    assert preflight["modulos"][0]["por_laboratorio"] >= 12
    presupuesto = plan["metadata"]["format_budget"]
    assert presupuesto["perfil"] == "conference"
    assert presupuesto["suma_antes"] == 330
    assert presupuesto["suma_despues"] <= 30
    assert presupuesto["excede"] is False
    # Merging the extra labs is the product rule. It must not look like an
    # unexplained syllabus-count mismatch to the quality gate.
    assert plan["metadata"]["quality_gate"]["quality_status"] == "passed", plan["metadata"]["quality_gate"]


def test_el_planner_no_deja_pasar_ms_4018_ms_4023_ni_ai_3025():
    """The three named overruns are cut on the handler, after A3."""
    ms_4018 = _handler(
        {
            "course": {
                "title": "MS-4018",
                "format": "conferencia",
                "total_duration_minutes": 120,
                "modules": [
                    {
                        "title": "Módulo",
                        "duration_minutes": 120,
                        "percent_practice": 25,
                        "lab_activities": [
                            {"title": "Práctica única", "duration_minutes": 185}
                        ],
                    }
                ],
            }
        },
        [
            {
                "lab_id": "01-00-01",
                "lab_title": "Práctica única",
                "estimated_duration": 185,
                "objectives": ["a"],
                "scope": "Alcance.",
                "expected_outcomes": ["c"],
            }
        ],
    )
    assert sum(lab["estimated_duration"] for lab in ms_4018["lab_plans"]) <= 30

    ms_4023 = _handler(
        {
            "course": {
                "title": "MS-4023",
                "format": "seminar",
                "total_duration_minutes": 160,
                "modules": [
                    {
                        "title": "Módulo",
                        "duration_minutes": 160,
                        "percent_practice": 40,
                        "lab_activities": [
                            {"title": f"Práctica {i}", "duration_minutes": minutos}
                            for i, minutos in enumerate((20, 20, 20, 20, 17), start=1)
                        ],
                    }
                ],
            }
        },
        _planes_modelo(5, 40),
    )
    assert sum(lab["estimated_duration"] for lab in ms_4023["lab_plans"]) <= 64
    assert sum(lab["estimated_duration"] for lab in ms_4023["lab_plans"]) < 97

    ai_3025 = _handler(
        {
            "course": {
                "title": "AI-3025",
                "format": "curso completo",
                "total_duration_minutes": 960,
                "modules": [
                    {
                        "title": "Módulo",
                        "duration_minutes": 240,
                        "percent_practice": 40,
                        "lab_activities": [
                            {"title": f"Práctica {i}", "duration_minutes": minutos}
                            for i, minutos in enumerate((48, 48, 47), start=1)
                        ],
                    }
                ],
            }
        },
        _planes_modelo(3, 80),
    )
    assert sum(lab["estimated_duration"] for lab in ai_3025["lab_plans"]) <= 96
    assert sum(lab["estimated_duration"] for lab in ai_3025["lab_plans"]) < 143


def test_una_actualizacion_selectiva_no_reune_practicas():
    """Partial regeneration must not drop labs the caller did not ask to reshape."""
    outline = _outline_conferencia(11, 30)
    planes = _planes_modelo(11, 30)
    plan = _handler(
        outline,
        planes,
        evento_extra={"lab_ids_to_regenerate": [f"01-00-{i:02d}" for i in range(1, 12)]},
        plan_existente={"lab_plans": planes, "additional_requirements": ""},
    )
    assert len(plan["lab_plans"]) == 11
    assert plan["metadata"]["format_budget"]["motivo"] == "actualizacion_selectiva"
    assert plan["metadata"]["format_budget"]["ajustado"] is True
    assert plan["metadata"]["format_budget"]["labs_despues"] == 11
    assert sum(lab["estimated_duration"] for lab in plan["lab_plans"]) <= 30
    puerta = plan["metadata"]["quality_gate"]
    assert all(h.get("campo") != "format_budget" for h in puerta["quality_findings"])
    assert not any(
        h.get("verificacion") == "A3" and "excede" in str(h.get("detalle") or "")
        for h in puerta["quality_findings"]
    )


def test_un_lab_de_60_en_un_presupuesto_de_27_no_avisa_tras_rebalancear():
    """The canary warning was ``sobre_comprometido (27.0 min/lab)`` after the plan already fit."""
    plan = _handler(
        {
            "course": {
                "title": "Canary de formato",
                "total_duration_minutes": 90,
                "language": "es",
                "modules": [
                    {
                        "title": "Módulo",
                        "duration_minutes": 90,
                        "percent_practice": 30,
                        "lab_activities": [
                            {"title": "Práctica", "duration_minutes": 60}
                        ],
                    }
                ],
            }
        },
        [
            {
                "lab_id": "01-00-01",
                "lab_title": "Práctica",
                "estimated_duration": 60,
                "objectives": ["a"],
                "scope": "Alcance.",
                "expected_outcomes": ["c"],
            }
        ],
    )
    assert plan["lab_plans"][0]["estimated_duration"] <= 27
    preflight = plan["metadata"]["preflight_duracion"]
    assert preflight["avisos"] == 0, preflight
    assert "sobre_comprometido" not in preflight["modulos"][0]["senales"]
    avisos = plan["metadata"]["quality_gate"]["quality_warnings"]
    assert not any("sobre_comprometido" in (item.get("valor") or "") for item in avisos)


def test_regenerar_un_lab_no_cuenta_el_plan_completo_como_sobra():
    """lab_ids_to_regenerate still runs the gate, against the whole syllabus.

    A plan that already fits is not needs_review just because only one lab was
    sent back through the planner.
    """
    outline = _outline_conferencia(2, 15)
    planes = _planes_modelo(2, 15)
    plan = _handler(
        outline,
        planes[:1],
        evento_extra={"lab_ids_to_regenerate": ["01-00-01"]},
        plan_existente={"lab_plans": planes, "additional_requirements": "", "metadata": {}},
    )
    assert len(plan["lab_plans"]) == 2
    assert plan["metadata"]["quality_gate"]["quality_status"] == "passed", plan["metadata"]["quality_gate"]


if __name__ == "__main__":
    pruebas = [
        (nombre, funcion)
        for nombre, funcion in sorted(globals().items())
        if nombre.startswith("test_") and callable(funcion)
    ]
    fallos = []
    for nombre, funcion in pruebas:
        try:
            funcion()
        except Exception as exc:  # noqa: BLE001 - test report
            fallos.append((nombre, exc))
            print(f"FAIL  {nombre}: {exc}")
        else:
            print(f"ok    {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} passed")
    sys.exit(1 if fallos else 0)
