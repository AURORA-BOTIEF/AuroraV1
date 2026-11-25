"""Reading budget: 60 words per declared minute, annex counted apart.

Offline. The writer is stubbed, so no model and no AWS call runs. 60 words per
minute is 30% of a 200-word reading speed, which leaves most of the slot for
doing the lab.
"""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import test_quality_gate as puerta  # noqa: E402


def _lectura():
    ruta = os.path.join(_HERE, "lambda", "strands_lab_writer", "reading_budget.py")
    spec = importlib.util.spec_from_file_location("reading_budget_test", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _presupuesto(minutos=12):
    modulo = _lectura()
    return modulo, modulo.presupuesto_de_lectura(minutos)


def _lab(palabras, anexo=0):
    relleno = " ".join(["palabra"] * palabras)
    cuerpo = f"""# Lab 01-00-01: Lectura

## Descripcion General
El escenario consta de seis fondos multiactivo.

### Paso 1: Revisar
**Instructions:**
1. Lea el escenario entregado en clase.
**Expected output:** El escenario leido.

{relleno}
"""
    if anexo:
        filas = " ".join(["dato"] * anexo)
        cuerpo += f"\n## Anexo (datos ficticios)\n\n{filas}\n"
    return cuerpo


def test_doce_minutos_permiten_720_palabras_y_el_anexo_va_aparte():
    modulo, presupuesto = _presupuesto(12)
    assert presupuesto["palabras_max"] == 720
    assert presupuesto["palabras_por_minuto"] == 60
    assert presupuesto["velocidad_lectura"] == 200
    assert presupuesto["anexo_max"] == 500
    assert presupuesto["minutos_lectura"] == 4
    assert presupuesto["fraccion"] == 0.3

    largo = modulo.medir_lectura(_lab(900), 12)
    assert largo["excede"] is True
    assert largo["excede_cuerpo"] is True
    assert largo["palabras"] > 720

    justo = modulo.medir_lectura(_lab(600), 12)
    assert justo["excede"] is False

    anexo = modulo.medir_lectura(_lab(600, anexo=600), 12)
    assert anexo["excede_anexo"] is True
    assert anexo["palabras_anexo"] > 500
    assert anexo["palabras"] <= 720

    anexo_corto = modulo.medir_lectura(_lab(600, anexo=40), 12)
    assert anexo_corto["excede"] is False
    assert anexo_corto["palabras_anexo"] > 0

    con_cerca = "```bash\n" + " ".join(["echo"] * 400) + "\n```\n" + _lab(100)
    medida = modulo.medir_lectura(con_cerca, 12)
    assert medida["palabras"] < 200


def test_el_entorno_cambia_el_presupuesto():
    modulo = _lectura()
    anterior = os.environ.get("LAB_READING_WORDS_PER_MINUTE")
    os.environ["LAB_READING_WORDS_PER_MINUTE"] = "10"
    try:
        assert modulo.presupuesto_de_lectura(12)["palabras_max"] == 120
    finally:
        if anterior is None:
            os.environ.pop("LAB_READING_WORDS_PER_MINUTE", None)
        else:
            os.environ["LAB_READING_WORDS_PER_MINUTE"] = anterior


def test_el_prompt_declara_el_presupuesto_y_no_pide_miles_de_palabras():
    modulo = puerta._cargar("strands_lab_writer", "lambda/strands_lab_writer")
    plan = {
        "lab_id": "01-00-01",
        "lab_title": "Lectura",
        "estimated_duration": 12,
        "objectives": ["Leer el escenario"],
    }
    espanol = modulo._compact_single_lab_prompt(
        plan, {"target_language": "Spanish (Español)"}, "", "LAB", ""
    )
    assert "720" in espanol
    assert "60" in espanol
    assert "PRESUPUESTO DE LECTURA" in espanol
    assert "4,000" not in espanol
    assert "8,000" not in espanol
    ingles = modulo._compact_single_lab_prompt(
        plan, {"target_language": "English"}, "", "LAB", ""
    )
    assert "READING BUDGET" in ingles
    assert "720" in ingles
    sin_duracion = _lectura().texto_para_prompt(None, en_espanol=True)
    assert "1200" in sin_duracion


def test_el_writer_reintenta_con_el_recorte_concreto_y_luego_pasa():
    plan = dict(puerta._LAB_PLAN)
    plan["estimated_duration"] = 12
    _modulo, resultado, _s3, _log, contextos = puerta._ejecutar_writer(
        {"lab_plans": [plan]}, [_lab(900), puerta._lab_limpio()], max_intentos=2
    )
    assert resultado["quality_status"] == "passed"
    assert resultado["labs_needing_review"] == []
    assert len(contextos) == 2
    correccion = contextos[1].get("reading_budget_correction") or ""
    assert "720" in correccion
    assert "CORRECCIÓN (presupuesto de lectura)" in correccion
    avisos = resultado["quality_warnings"]
    assert all(
        hallazgo.get("verificacion") != "R1"
        for aviso in avisos
        for hallazgo in aviso.get("findings") or []
    )


def test_el_ultimo_intento_largo_queda_en_aviso_medio():
    plan = dict(puerta._LAB_PLAN)
    plan["estimated_duration"] = 12
    _modulo, resultado, _s3, _log, contextos = puerta._ejecutar_writer(
        {"lab_plans": [plan]}, [_lab(900)], max_intentos=1
    )
    assert len(contextos) == 1
    assert resultado["quality_status"] == "passed"
    assert resultado["labs_needing_review"] == []
    r1 = [
        hallazgo
        for aviso in resultado["quality_warnings"]
        for hallazgo in aviso.get("findings") or []
        if hallazgo.get("verificacion") == "R1"
    ]
    assert len(r1) == 1
    assert r1[0]["confianza"] == "media"


def test_sin_reintento_solo_registra():
    plan = dict(puerta._LAB_PLAN)
    plan["estimated_duration"] = 12
    anterior = os.environ.get("READING_BUDGET_RETRY")
    os.environ["READING_BUDGET_RETRY"] = "0"
    try:
        _modulo, resultado, _s3, _log, contextos = puerta._ejecutar_writer(
            {"lab_plans": [plan]}, [_lab(900), puerta._lab_limpio()], max_intentos=3
        )
    finally:
        if anterior is None:
            os.environ.pop("READING_BUDGET_RETRY", None)
        else:
            os.environ["READING_BUDGET_RETRY"] = anterior
    assert len(contextos) == 1
    assert resultado["quality_status"] == "passed"
    assert any(
        hallazgo.get("verificacion") == "R1"
        for aviso in resultado["quality_warnings"]
        for hallazgo in aviso.get("findings") or []
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pruebas = [
        (nombre, funcion)
        for nombre, funcion in sorted(globals().items())
        if nombre.startswith("test_") and callable(funcion)
    ]
    fallos = []
    for nombre, funcion in pruebas:
        try:
            funcion()
        except Exception as exc:  # noqa: BLE001 - informe de test
            fallos.append((nombre, exc))
            print(f"FALLO  {nombre}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
