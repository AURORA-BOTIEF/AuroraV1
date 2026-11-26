"""Offline checks for the release-candidate batch on top of 92013f3b.

No AWS calls. Each new behavior has an env off-switch and still ships a warning
when the repair cannot finish the job.
"""

from __future__ import annotations

import importlib.util
import os
import sys

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

_AQUI = os.path.dirname(os.path.abspath(__file__))


def _cargar(nombre, ruta):
    """Load this file even when pytest already imported a sibling of the same name."""
    sys.modules.pop(nombre, None)
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _mismo_archivo(*rutas):
    with open(rutas[0], "rb") as origen:
        canon = origen.read()
    for ruta in rutas[1:]:
        with open(ruta, "rb") as copia:
            assert copia.read() == canon, ruta


def test_la_reparacion_de_validacion_sustituye_la_frase_no_medible():
    modulo = _cargar(
        "measurable_evidence_writer",
        os.path.join(_AQUI, "lambda", "strands_lab_writer", "measurable_evidence.py"),
    )
    guia = "Salida esperada: el script funciona correctamente y queda production-ready."
    os.environ.pop("VALIDATION_REPAIR", None)
    reparada = modulo.reparar_validacion_no_medible(guia)
    assert "funciona correctamente" not in reparada
    assert "production-ready" not in reparada
    assert "Compruebe los elementos" in reparada
    assert "Check the elements" in reparada
    assert modulo.hallazgos_validacion_no_medible(reparada) == []
    os.environ["VALIDATION_REPAIR"] = "0"
    try:
        assert modulo.reparar_validacion_no_medible(guia) == guia
    finally:
        os.environ.pop("VALIDATION_REPAIR", None)


def test_el_recorte_de_lectura_baja_la_prosa_al_presupuesto():
    presupuesto = _cargar(
        "reading_budget_writer",
        os.path.join(_AQUI, "lambda", "strands_lab_writer", "reading_budget.py"),
    )

    prosa = " ".join(["palabra"] * 800)
    guia = f"# Lab\n\n{prosa}\n\n## Paso 1\n\n1. Ejecute el comando.\n"
    os.environ.pop("READING_TRIM", None)
    recortada = presupuesto.recortar_a_presupuesto(guia, 5)
    medida = presupuesto.medir_lectura(recortada, 5)
    assert medida["palabras"] <= medida["palabras_max"], medida
    assert "1. Ejecute el comando." in recortada
    os.environ["READING_TRIM"] = "0"
    try:
        assert presupuesto.recortar_a_presupuesto(guia, 5) == guia
    finally:
        os.environ.pop("READING_TRIM", None)


def test_el_planner_recibe_el_ejemplo_lpi010():
    modulo = _cargar(
        "golden_lab_planner",
        os.path.join(_AQUI, "lambda", "strands_lab_planner", "golden_lab_example.py"),
    )
    os.environ.pop("PLANNER_GOLDEN_LAB", None)
    texto = modulo.build_planner_golden_section()
    assert modulo.GOLDEN_LAB_SECTION_MARKER in texto
    assert "LPI-010" in texto
    assert "No copie" in texto or "Do not copy" in texto
    os.environ["PLANNER_GOLDEN_LAB"] = "0"
    try:
        assert modulo.build_planner_golden_section() == ""
    finally:
        os.environ.pop("PLANNER_GOLDEN_LAB", None)


def test_el_deck_reintenta_una_vez_y_sigue_fallando_si_el_segundo_intento_cae():
    modulo = _cargar(
        "deck_builder_retry",
        os.path.join(_AQUI, "lambda", "deck_builder", "deck_builder.py"),
    )
    llamadas = {"n": 0}

    def falla():
        llamadas["n"] += 1
        raise RuntimeError("pptx crash")

    os.environ.pop("DECK_RETRY", None)
    try:
        modulo.ejecutar_con_reintento(falla)
    except RuntimeError:
        pass
    else:
        raise AssertionError("the second failure must still raise")
    assert llamadas["n"] == 2

    llamadas["n"] = 0
    os.environ["DECK_RETRY"] = "0"
    try:
        modulo.ejecutar_con_reintento(falla)
    except RuntimeError:
        pass
    assert llamadas["n"] == 1
    os.environ.pop("DECK_RETRY", None)

    llamadas["n"] = 0

    def se_recupera():
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise RuntimeError("once")
        return {"statusCode": 200}

    assert modulo.ejecutar_con_reintento(se_recupera)["statusCode"] == 200
    assert llamadas["n"] == 2


def test_el_pie_del_libro_se_reconstruye_tras_reparar_enlaces():
    modulo = _cargar(
        "post_generation_audit_stats",
        os.path.join(_AQUI, "lambda", "post_generation_audit", "post_generation_audit.py"),
    )
    libro = (
        "# Curso\n\n"
        "# Lesson 1: Intro\n\n"
        "Visite https://example.invalid/viejo para el caso.\n\n"
        "## Book Statistics\n\n"
        "- **Total Lessons**: 9\n"
        "- **Total Words**: 1\n"
    )
    os.environ.pop("BOOK_STATS_REFRESH", None)
    nuevo = modulo.reconstruir_pie_estadisticas(libro.replace("https://example.invalid/viejo", "https://learn.microsoft.com/caso"))
    assert "Total Lessons**: 1" in nuevo or "Total Lessons**: 1" in nuevo
    assert "Total Words**: 1\n" not in nuevo
    assert "revisados tras la reparación de enlaces" in nuevo
    assert "Reviewed after link repair" in nuevo
    assert "https://example.invalid/viejo" not in nuevo
    os.environ["BOOK_STATS_REFRESH"] = "0"
    try:
        assert modulo.reconstruir_pie_estadisticas(libro) == libro
    finally:
        os.environ.pop("BOOK_STATS_REFRESH", None)


def test_una_audiencia_con_demos_convierte_la_teoria():
    # The content generator's CodeUri is strands_content_gen/. The root file and
    # the planner/writer copies are the same bytes; this load does not use whichever
    # sibling a previous test left in sys.modules.
    sys.modules.pop("audience_adaptation", None)
    audiencia = _cargar(
        "audience_adaptation_content_gen",
        os.path.join(_AQUI, "lambda", "strands_content_gen", "audience_adaptation.py"),
    )
    assert audiencia.__file__.replace("\\", "/").endswith(
        "lambda/strands_content_gen/audience_adaptation.py"
    )

    perfil = audiencia.resolve_audience_profile(
        {
            "title": "Copilot para productividad",
            "description": "Usuarios finales de Microsoft 365",
            "total_duration_minutes": 120,
        }
    )
    assert perfil["is_copilot_productivity"] is True
    os.environ.pop("THEORY_TO_DEMO", None)
    leccion = audiencia.promover_teoria_a_demo(
        {"title": "Qué es un prompt", "type": "theory", "description": "Conceptos."},
        perfil,
    )
    assert leccion["title"].startswith("Demo:")
    assert leccion["type"] == "demo"
    assert "demostración del instructor" in leccion["description"]
    assert "Short instructor demo" in leccion["description"]
    ya = audiencia.promover_teoria_a_demo(
        {"title": "Demo: Copilot en Word", "type": "demo"},
        perfil,
    )
    assert ya["title"] == "Demo: Copilot en Word"
    estandar = audiencia.resolve_audience_profile(
        {"title": "Arquitectura de plataforma", "total_duration_minutes": 2400}
    )
    igual = audiencia.promover_teoria_a_demo(
        {"title": "Teoría larga", "type": "theory"},
        estandar,
    )
    assert igual["title"] == "Teoría larga"
    os.environ["THEORY_TO_DEMO"] = "0"
    try:
        apagada = audiencia.promover_teoria_a_demo(
            {"title": "Qué es un prompt", "type": "theory"},
            perfil,
        )
        assert apagada["type"] == "theory"
    finally:
        os.environ.pop("THEORY_TO_DEMO", None)


def test_las_copias_desplegadas_no_se_quedan_atras():
    """Siblings that share a module name must be the file each CodeUri will import."""
    _mismo_archivo(
        os.path.join(_AQUI, "audience_adaptation.py"),
        os.path.join(_AQUI, "lambda", "strands_content_gen", "audience_adaptation.py"),
        os.path.join(_AQUI, "lambda", "strands_lab_planner", "audience_adaptation.py"),
        os.path.join(_AQUI, "lambda", "strands_lab_writer", "audience_adaptation.py"),
    )
    _mismo_archivo(
        os.path.join(_AQUI, "lambda", "strands_lab_planner", "referent_check.py"),
        os.path.join(_AQUI, "lambda", "strands_lab_writer", "referent_check.py"),
    )
    _mismo_archivo(
        os.path.join(_AQUI, "lambda", "strands_lab_writer", "measurable_evidence.py"),
        os.path.join(_AQUI, "lambda", "content_validator", "measurable_evidence.py"),
    )
    _mismo_archivo(
        os.path.join(_AQUI, "lambda", "strands_lab_writer", "golden_lab_example.py"),
        os.path.join(_AQUI, "lambda", "strands_lab_planner", "golden_lab_example.py"),
    )
    _mismo_archivo(
        os.path.join(_AQUI, "lambda", "strands_lab_writer", "fixtures", "golden_lab_lpi010_slice.md"),
        os.path.join(_AQUI, "lambda", "strands_lab_planner", "fixtures", "golden_lab_lpi010_slice.md"),
    )


if __name__ == "__main__":
    pruebas = [
        (nombre, funcion)
        for nombre, funcion in sorted(globals().items())
        if nombre.startswith("test_") and callable(funcion)
    ]
    fallos = 0
    for nombre, funcion in pruebas:
        try:
            funcion()
        except Exception as exc:
            fallos += 1
            print(f"FAIL {nombre}: {exc}")
        else:
            print(f"ok   {nombre}")
    print(f"{len(pruebas) - fallos}/{len(pruebas)}")
    raise SystemExit(1 if fallos else 0)
