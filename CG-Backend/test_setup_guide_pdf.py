"""Setup Guide PDF: long practice titles must not raise LayoutError.

Offline. boto3 is stubbed. xhtml2pdf renders the lab matrix locally.
"""

import importlib
import os
import sys
import types

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

_HERE = os.path.dirname(os.path.abspath(__file__))


def _modulo():
    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: types.SimpleNamespace()
    botocore_sim = types.ModuleType("botocore")
    exceptions_sim = types.ModuleType("botocore.exceptions")

    class _ClientError(Exception):
        pass

    exceptions_sim.ClientError = _ClientError
    botocore_sim.exceptions = exceptions_sim
    sys.modules["boto3"] = boto3_sim
    sys.modules["botocore"] = botocore_sim
    sys.modules["botocore.exceptions"] = exceptions_sim
    ruta = os.path.join(_HERE, "lambda", "setup_guide_builder")
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    sys.modules.pop("setup_guide_builder", None)
    return importlib.import_module("setup_guide_builder")


_TITULO = (
    "Configurar Microsoft 365 Copilot Chat para el equipo de atención y "
    "documentar el flujo completo de una consulta de cliente con citas, "
    "un resumen y el siguiente paso acordado con el alumno"
)
_LAB = """# Lab

## Entorno de laboratorio
| Recurso | Valor |
| --- | --- |
| Cuenta | demostración |

Estado inicial: | tabla cruda | que no debe | verse |

## Validación y pruebas
```text
Prompt de prueba: actúa como instructor y escribe un ensayo de tres páginas sobre la historia de los fondos con citas, un cierre y una lista de riesgos.
```
Compruebe que el panel muestra el escenario.
"""


def _plan():
    return {
        "lab_plans": [
            {
                "lab_id": "01-00-01",
                "lab_title": _TITULO,
                "estimated_duration": 12,
                "objectives": [
                    "Dejar el chat listo para una consulta de cliente con el tono del equipo y las fuentes del manual."
                ],
                "expected_outcomes": ["El panel muestra la consulta resuelta."],
                "prerequisites": ["Cuenta de Microsoft 365 con licencia de Copilot asignada al alumno."],
            }
        ]
    }


def _contexto(matriz):
    return {
        "logo_path": "",
        "course_title": "Curso",
        "course_key": "MS-4004",
        "version": "1",
        "status": "BORRADOR",
        "last_validation": "—",
        "description": "",
        "date": "Noviembre 2026",
        "repo_url": "https://example.invalid/curso",
        "identification": {"links": []},
        "previous_knowledge": {"network": []},
        "infrastructure": {"hardware": [], "network": []},
        "counters": [],
        "capabilities": [],
        "software": [],
        "additional_requirements": "",
        "accesses": [],
        "preparation": [],
        "validation": {"checklist": [], "full_test": "", "troubleshooting": []},
        "lab_matrix": matriz,
        "references": [],
    }


def test_la_celda_de_lab_cabe_y_los_campos_sucios_se_resumen():
    modulo = _modulo()
    matriz = modulo.build_lab_matrix(_plan(), {"01-00-01": _LAB}, "https://example.invalid/curso")
    assert len(matriz) == 1
    fila = matriz[0]
    assert fila["name"].startswith("01-00-01")
    assert len(fila["name"]) <= 60
    assert "…" in fila["name"]
    assert "|" not in fila["initial_state"]
    assert "tabla cruda" not in fila["initial_state"]
    assert "Entorno preparado" in fila["initial_state"]
    assert "Prompt de prueba" not in fila["evidence"] or len(fila["evidence"]) <= 70
    assert "tres páginas" not in fila["evidence"]
    assert len(fila["evidence"]) <= 70
    for campo, ancho in modulo._ANCHO_CELDA_PT.items():
        texto = fila["access"]["label"] if campo == "access" else fila[campo]
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph
        from xml.sax.saxutils import escape

        parrafo = Paragraph(
            escape(texto or ""),
            ParagraphStyle("m", fontName="Helvetica", fontSize=7.5, leading=9),
        )
        assert parrafo.minWidth() <= ancho + 0.5, (campo, parrafo.minWidth(), ancho, texto)


def test_la_matriz_larga_genera_un_pdf():
    modulo = _modulo()
    from jinja2 import Template

    matriz = modulo.build_lab_matrix(_plan(), {"01-00-01": _LAB}, "https://example.invalid/curso")
    html = Template(modulo.SETUP_GUIDE_TEMPLATE).render(_contexto(matriz))
    datos = modulo._pdf_desde_html(html)
    assert datos.startswith(b"%PDF")
    assert len(datos) > 1000


def test_una_tabla_2x8_se_parte_y_el_pdf_sale():
    """A 2-column, 8-row table is what raised LayoutError on page 27."""
    modulo = _modulo()
    filas = "<tr><th>Campo</th><th>Valor</th></tr>"
    filas += "".join(
        f"<tr><td>Fila {indice}</td><td>{'tokenlarguisimo' * 40}</td></tr>"
        for indice in range(7)
    )
    html = f"<html><body><table>{filas}</table></body></html>"
    partido = modulo.partir_tablas_altas(html)
    assert partido.lower().count("<table") == 2
    assert "…" in partido
    datos = modulo._pdf_desde_html(html)
    assert datos.startswith(b"%PDF")


def test_un_layout_error_no_se_traga():
    modulo = _modulo()
    from reportlab.platypus.doctemplate import LayoutError

    def _falla(*_args, **_kwargs):
        raise LayoutError("Flowable too large")

    original = modulo.pisa.CreatePDF
    modulo.pisa.CreatePDF = _falla
    try:
        try:
            modulo._pdf_desde_html("<html><body><p>x</p></body></html>")
        except RuntimeError as exc:
            assert "layout failed" in str(exc).lower()
        else:
            raise AssertionError("a LayoutError must not return a PDF")
    finally:
        modulo.pisa.CreatePDF = original


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
            print(f"FALLO  {nombre}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
