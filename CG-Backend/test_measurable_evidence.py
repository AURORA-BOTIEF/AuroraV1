"""Offline tests for verifiable validation (THOR audit item 5 / backlog #8)."""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "lambda", "strands_lab_writer", "measurable_evidence.py")


def _load():
    spec = importlib.util.spec_from_file_location("measurable_evidence", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


me = _load()


_LAB_COPILOT_MALA = """# Lab 01-00-01: Copilot

## Instrucciones Paso a Paso

### Paso 1: Redactar con Copilot

**Objetivo:** Generar un borrador.

**Instrucciones:**

1. Abra Copilot y pegue el contexto del caso.

**Expected Output:**

La respuesta del asistente debe comenzar exactamente con «Estimado equipo, adjunto el análisis
comparativo de los fondos multiactivo con recomendaciones de rebalanceo trimestral y una tabla
de riesgos detallada para cada escenario macroeconómico contemplado en el manual del curso.»

**Verificación:** Revise que el tono sea formal.
"""

_LAB_COPILOT_BUENA = """# Lab 01-00-01: Copilot

## Instrucciones Paso a Paso

### Paso 1: Redactar con Copilot

**Objetivo:** Generar un borrador.

**Instrucciones:**

1. Abra Copilot y pegue el contexto del caso.

**Expected Output:**

- Debe incluir tono formal.
- Cita al menos dos fondos del manual.
- Incluye una tabla de riesgos.

**Verificación:** Comprueba que cada viñeta anterior esté presente en la respuesta.
"""


def test_detecta_frase_no_medible():
    lab = _LAB_COPILOT_BUENA + "\n\nEl procedimiento funciona correctamente en todos los casos.\n"
    hallazgos = me.hallazgos_validacion_no_medible(lab)
    assert any("funciona correctamente" in h for h in hallazgos)


def test_detecta_secreto_inventado():
    lab = _LAB_COPILOT_BUENA.replace(
        "**Verificación:**",
        "Use password `pg_password_123` en la conexión.\n\n**Verificación:**",
    )
    hallazgos = me.hallazgos_validacion_no_medible(lab)
    assert any("pg_password" in h for h in hallazgos)


def test_detecta_salida_determinista_en_paso_ia():
    hallazgos = me.hallazgos_validacion_no_medible(_LAB_COPILOT_MALA)
    assert any("Salida esperada determinista" in h for h in hallazgos)


def test_acepta_lista_de_elementos_en_paso_ia():
    hallazgos = me.hallazgos_validacion_no_medible(_LAB_COPILOT_BUENA)
    assert not any("Salida esperada determinista" in h for h in hallazgos)


def test_mensaje_correccion_incluye_reglas():
    texto = me.mensaje_correccion_validacion(["Frase no medible: foo"])
    assert "lista" in texto.lower()
    assert "Frase no medible" in texto


def test_refinement_prompt_no_inventa_secretos():
    ruta = os.path.join(_HERE, "lambda", "strands_lab_writer", "strands_lab_writer.py")
    fuente = open(ruta, encoding="utf-8").read()
    assert "pg_password_123" not in fuente
    assert "[POR CONFIRMAR]" in fuente


def _ejecutar():
    pruebas = [
        (n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)
    ]
    fallos = 0
    for nombre, funcion in pruebas:
        try:
            funcion()
        except AssertionError as exc:
            fallos += 1
            print(f"FALLO  {nombre}: {exc}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas correctas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(_ejecutar())