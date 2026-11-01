"""Pruebas de la puerta de calidad (ContentValidator) sobre el camino vivo.

Qué se comprueba, y sobre qué artefacto:

- ``content_validator.py``: el validador real, con laboratorios completos y con
  los defectos que la puerta debe bloquear.
- ``current_state_machine.json``: que el estado desplegado consuma ``all_valid``
  y que exista el modo sombra.

La calibración que respalda estas reglas está en
``docs/spec-integridad-referencial-labs.md`` §21.
"""

import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUTA_VALIDADOR = os.path.join(_HERE, "lambda", "content_validator", "content_validator.py")
_RUTA_MAQUINA = os.path.join(_HERE, "current_state_machine.json")


def _cargar_validador():
    # El modulo crea un cliente S3 al importarse; la bateria no debe tocar AWS.
    import boto3

    original = boto3.client
    boto3.client = lambda *a, **k: object()
    try:
        spec = importlib.util.spec_from_file_location("content_validator_test", _RUTA_VALIDADOR)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules["content_validator_test"] = modulo
        spec.loader.exec_module(modulo)
    finally:
        boto3.client = original
    return modulo


cv = _cargar_validador()


_LAB_COMPLETO = """# Lab 01-00-01: Preparar el entorno

## Metadatos

| Campo | Valor |
|---|---|
| Lab | 01-00-01 |
| Duracion | 45 min |

## Descripción General

Este laboratorio prepara el entorno de trabajo.

## Objetivos de Aprendizaje

- Instalar las dependencias del proyecto.

## Prerrequisitos

- Cuenta de laboratorio activa.

## Entorno de Laboratorio

Una maquina Linux con acceso a internet.

## Instrucciones Paso a Paso

### Paso 1: Instalar las dependencias

```bash
# Este comentario no es un titulo de Markdown
pip install -r requirements.txt
```

### Paso 2: Verificar la instalacion

Ejecute `pip list` y compare con `requirements.txt`.

## Validación y Pruebas

Resultado esperado: la lista incluye las cinco dependencias.

## Solución de Problemas

- Si falla la red, revise el proxy.

## Limpieza

Elimine el entorno virtual.

## Resumen

El entorno queda listo.
"""


def _reglas(informe, severidad):
    if severidad == cv.ValidationSeverity.ERROR:
        return [r.rule for r in informe.errors]
    if severidad == cv.ValidationSeverity.WARNING:
        return [r.rule for r in informe.warnings]
    return [r.rule for r in informe.info]


def test_un_laboratorio_completo_es_valido():
    informe = cv.ContentValidator().validate_lab(_LAB_COMPLETO)
    assert informe.is_valid is True, [(e.rule, e.message) for e in informe.errors]


def test_un_comentario_de_shell_no_es_un_titulo():
    """620 de 1.294 laboratorios reales tienen `#` dentro de una cerca de bash."""
    assert _LAB_COMPLETO.count("# Este comentario") == 1
    informe = cv.ContentValidator().validate_lab(_LAB_COMPLETO)
    assert "single_h1" not in _reglas(informe, cv.ValidationSeverity.ERROR)


def test_los_pasos_se_aceptan_en_h2_h3_y_h4():
    for encabezado in ("## Paso 1: Uno", "### Paso 2: Dos", "#### Paso 3: Tres"):
        informe = cv.ContentValidator().validate_lab(_LAB_COMPLETO + "\n" + encabezado + "\n\nTexto.\n")
        assert "lab_steps" not in _reglas(informe, cv.ValidationSeverity.ERROR), encabezado


def test_los_pasos_con_letra_o_guion_se_reconocen():
    """"Paso A1:", "Paso A-1:" y "PASO 1 —" existen en el corpus real."""
    lab = (
        _LAB_COMPLETO
        + "\n### Paso A1: Preparar\n\nTexto.\n"
        + "\n### Paso A-2: Firmar\n\nTexto.\n"
        + "\n### PASO 3 — Desplegar\n\nTexto.\n"
    )
    informe = cv.ContentValidator().validate_lab(lab)
    assert "lab_steps" not in _reglas(informe, cv.ValidationSeverity.ERROR)


def test_un_laboratorio_sin_pasos_es_un_error_estructural():
    lab = _LAB_COMPLETO.split("## Instrucciones Paso a Paso")[0] + "## Instrucciones Paso a Paso\n\nProsa sin pasos.\n"
    informe = cv.ContentValidator().validate_lab(lab)
    assert "lab_steps" in _reglas(informe, cv.ValidationSeverity.ERROR)
    assert informe.is_valid is False


def test_dos_h1_reales_siguen_siendo_un_error():
    lab = _LAB_COMPLETO + "\n# Verificar estado del listener\n\nTexto.\n"
    informe = cv.ContentValidator().validate_lab(lab)
    assert "single_h1" in _reglas(informe, cv.ValidationSeverity.ERROR)


def test_una_seccion_ausente_es_un_aviso_y_no_bloquea():
    """503 de 1.294 laboratorios reales titulan alguna seccion de otra forma."""
    lab = _LAB_COMPLETO.replace("## Metadatos", "## Ficha del laboratorio")
    informe = cv.ContentValidator().validate_lab(lab)
    assert "required_section" in _reglas(informe, cv.ValidationSeverity.WARNING)
    assert "required_section" not in _reglas(informe, cv.ValidationSeverity.ERROR)
    assert informe.is_valid is True


def test_un_salto_de_nivel_es_un_aviso_y_no_bloquea():
    lab = _LAB_COMPLETO + "\n#### Paso 4: Cuarto\n\nTexto.\n"
    informe = cv.ContentValidator().validate_lab(lab)
    assert "heading_hierarchy" in _reglas(informe, cv.ValidationSeverity.WARNING)
    assert informe.is_valid is True


def test_un_contenido_sin_encabezados_es_un_error():
    informe = cv.ContentValidator().validate_lab("Texto plano sin estructura.\n")
    assert "heading_hierarchy" in _reglas(informe, cv.ValidationSeverity.ERROR)


_LAB_CON_PASOS_ETIQUETADOS_ES = """# Lab 01-00-01: Leer un inventario

## Descripción General

Laboratorio de ejemplo.

## Instrucciones Paso a Paso

### Paso 1: Crear el fichero

**Objetivo:** Tener los datos de entrada.

**Instrucciones:**

1. Crea `inventario.txt` con tres líneas.

**Verificación:** El fichero existe y tiene tres líneas.
"""


def test_los_pasos_etiquetados_en_espanol_no_generan_avisos_de_estructura():
    """La guía real se escribe en el idioma del curso.

    Medido el 22/10/2026 sobre 120 laboratorios reales: 1.459 de los 1.657 avisos
    eran este falso positivo (pasos correctamente etiquetados como ``**Objetivo:**``
    que la regla buscaba en inglés).
    """
    informe = cv.ContentValidator().validate_lab(_LAB_CON_PASOS_ETIQUETADOS_ES)
    assert "step_structure" not in _reglas(informe, cv.ValidationSeverity.WARNING), [
        (w.message, w.line_number) for w in informe.warnings
    ]


def test_los_pasos_etiquetados_en_ingles_siguen_aceptandose():
    lab = _LAB_CON_PASOS_ETIQUETADOS_ES.replace(
        "**Objetivo:**", "**Objective:**"
    ).replace("**Instrucciones:**", "**Instructions:**").replace(
        "**Verificación:**", "**Verification:**"
    )
    informe = cv.ContentValidator().validate_lab(lab)
    assert "step_structure" not in _reglas(informe, cv.ValidationSeverity.WARNING)


def test_las_etiquetas_con_los_dos_puntos_fuera_de_las_negritas_se_aceptan():
    """El corpus real usa `**Objetivo**:` tanto como `**Objetivo:**`."""
    lab = _LAB_CON_PASOS_ETIQUETADOS_ES.replace(
        "**Objetivo:**", "**Objetivo**:"
    ).replace("**Instrucciones:**", "**Instrucciones**:").replace(
        "**Verificación:**", "**Verificación**:"
    )
    informe = cv.ContentValidator().validate_lab(lab)
    assert "step_structure" not in _reglas(informe, cv.ValidationSeverity.WARNING), [
        w.message for w in informe.warnings if w.rule == "step_structure"
    ]


def test_el_recuento_de_bloques_sin_lenguaje_no_cuenta_las_vallas_de_cierre():
    """Un bloque sin lenguaje se informaba como dos (apertura + cierre)."""
    lab = _LAB_COMPLETO + """
```bash
echo hola
```

```
resultado de ejemplo
```
"""
    informe = cv.ContentValidator().validate_lab(lab)
    mensajes = [w.message for w in informe.warnings if w.rule == "code_block_language"]
    assert mensajes, "debería avisar del bloque sin lenguaje"
    assert mensajes[0].startswith("Found 1 code block"), mensajes[0]


def test_el_handler_devuelve_all_valid_y_falla_si_se_le_pide():
    modulo = cv
    modulo.load_content_from_s3 = lambda bucket, key: _LAB_COMPLETO + "\n# Suelto\n\nTexto.\n"
    modulo.save_validation_report = lambda *a, **k: "informe"
    evento = {
        "course_bucket": "bucket",
        "project_folder": "p",
        "content_keys": ["p/labguide/lab-01-00-01-x.md"],
        "content_type": "lab",
        "fail_on_error": False,
    }
    salida = modulo.lambda_handler(dict(evento), None)
    assert salida["statusCode"] == 200, salida
    assert salida["all_valid"] is False
    assert salida["total_errors"] == 1

    estricto = modulo.lambda_handler(dict(evento, fail_on_error=True), None)
    assert estricto["statusCode"] == 400


def test_el_estado_desplegado_consume_all_valid():
    """La puerta no sirve si el `all_valid` del validador no lo lee ningun `Choice`."""
    with open(_RUTA_MAQUINA, encoding="utf-8") as f:
        maquina = json.load(f)
    estados = maquina["States"]

    for nombre in ("ValidateLabContent", "ValidateLabContentBoth"):
        assert estados[nombre]["Next"] == "CheckLabValidation", nombre

    puerta = estados["CheckLabValidation"]
    assert puerta["Type"] == "Choice"
    assert puerta["Default"] == "InvokeLabGuideBuilder"

    sombra = [c for c in puerta["Choices"] if c.get("Variable") == "$.lab_validation_shadow"]
    assert sombra and sombra[0]["IsPresent"] is True

    bloqueo = [
        c
        for c in puerta["Choices"]
        if c.get("Next") == "NotifyFailure"
        and any(
            cond.get("Variable") == "$.lab_validation_result.all_valid"
            and cond.get("BooleanEquals") is False
            for cond in c.get("And", [])
        )
    ]
    assert bloqueo, "no hay rama que bloquee cuando all_valid es false"
    assert "NotifyFailure" in estados


def _ejecutar():
    pruebas = [
        (nombre, funcion)
        for nombre, funcion in sorted(globals().items())
        if nombre.startswith("test_") and callable(funcion)
    ]
    fallos = 0
    for nombre, funcion in pruebas:
        try:
            funcion()
        except AssertionError as exc:
            fallos += 1
            print(f"FALLO  {nombre}: {exc}")
        except Exception as exc:  # noqa: BLE001
            fallos += 1
            print(f"ERROR  {nombre}: {type(exc).__name__}: {exc}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas correctas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(_ejecutar())
