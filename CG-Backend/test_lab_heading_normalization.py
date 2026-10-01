import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lambda"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lambda", "strands_lab_writer"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lambda", "content_validator"))

import strands_lab_writer
from content_validator import ContentValidator


def _spanish_lab_after_normalize() -> str:
    raw = """# Lab 06-00-01: Gestión de una solicitud

## Metadatos
| Elemento | Valor |
|---|---|
| Duración | 31 minutos |

## Descripción general
Resumen del laboratorio.

## Objetivos de aprendizaje
- Aplicar Copilot en Outlook.

## Requisitos previos
### Conocimientos
- Outlook.

## Entorno de laboratorio
### Hardware recomendado
- Laptop.

## Procedimiento paso a paso
### Paso 1. Localizar los mensajes
**Objective:** Encontrar el hilo.
**Instructions:** Abrir Outlook.
**Verification:** El hilo está visible.

### Paso 2: Redactar el correo
**Objective:** Redactar.
**Instructions:** Usar Copilot.
**Verification:** Borrador listo.

# Resumen de solicitud documental
cuerpo de muestra

## Validación y Pruebas
Comprobar el envío.

## Solución de Problemas
### Issue 1: No aparece Copilot
### Issue 2: El hilo está incompleto

## Limpieza
Cerrar Outlook.

## Resumen
El laboratorio cierra el flujo documental.
"""
    return strands_lab_writer.normalize_lab_markdown(raw, is_spanish=True)


def test_validator_accepts_normalized_spanish_lab():
    content = _spanish_lab_after_normalize()
    report = ContentValidator().validate_lab(content)
    error_rules = [e.rule for e in report.errors]
    assert "required_section" not in error_rules, report.errors
    assert "lab_steps" not in error_rules, report.errors
    assert "single_h1" not in error_rules, report.errors
    assert report.is_valid is True


def test_validator_accepts_spanish_step_and_environment_aliases():
    content = """# Lab 03-00-01: Documentación

## Metadatos
x

## Descripción General
x

## Objetivos de Aprendizaje
x

## Requisitos previos
x

## Entorno del Laboratorio
x

## Instrucciones Paso a Paso
### Paso 1: Crear el documento
**Objective:** Crear.
**Instructions:** Abrir Word.
**Verification:** El archivo existe.

## Validación y Pruebas
x

## Solución de Problemas
x

## Limpieza
x

## Resumen
x
"""
    report = ContentValidator().validate_lab(content)
    error_rules = [e.rule for e in report.errors]
    assert "required_section" not in error_rules, report.errors
    assert "lab_steps" not in error_rules, report.errors
