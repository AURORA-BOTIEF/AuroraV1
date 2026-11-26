"""Template tokens in the Setup Guide, labs, and lessons.

No AWS and no model call. A failed fill becomes the bilingual neutral sentence
and a warning. It does not block delivery.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault("SETUP_GUIDE_LLM", "0")

_AQUI = os.path.dirname(os.path.abspath(__file__))
_TOKENS = os.path.join(_AQUI, "lambda", "setup_guide_builder")
_SCRIPTS = os.path.join(_AQUI, "scripts")
for _ruta in (_TOKENS, _SCRIPTS, os.path.join(_AQUI, "lambda")):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

import check_execution_artifacts as artefactos
import template_tokens as tokens
from quality_report import construir_informe_de_calidad, informe_tiene_hallazgos

_CANARY = (
    "[VERSIÓN POR VALIDAR]",
    "[COMANDO DE PRUEBA]",
    "[CLAVE COMPLETA]",
    "[LICENCIA POR VALIDAR]",
    "[FECHA DE VALIDACIÓN]",
    "[POR CONFIRMAR]",
)


def _guia_con_tokens():
    return {
        "metadata": {"last_validation": "[FECHA DE VALIDACIÓN]", "placeholders_count": 0},
        "identification": {"key": "[CLAVE COMPLETA]", "version": "[V1.0]"},
        "software": [
            {
                "name": "Ubuntu",
                "version": "[VERSIÓN POR VALIDAR]",
                "validation": "[COMANDO DE PRUEBA]",
                "license": "[LICENCIA POR VALIDAR]",
                "pending": True,
            },
            {
                "name": "Editor",
                "version": "[VERSIÓN POR VALIDAR]",
                "validation": "[COMANDO DE PRUEBA]",
                "license": "MIT",
                "pending": True,
            },
        ],
        "note": "Revise [POR CONFIRMAR] antes de empezar.",
        "placeholders": [],
    }


def test_detecta_cada_token_y_el_conteo_coincide_con_la_lista():
    texto = " ".join(_CANARY) + " [VERSIÓN POR VALIDAR] [CLAVE COMPLETA]"
    hallados = tokens.tokens_en_texto(texto)
    assert hallados.count("[VERSIÓN POR VALIDAR]") == 2
    assert hallados.count("[CLAVE COMPLETA]") == 2
    assert "[POR CONFIRMAR]" in hallados
    assert "[SIN DEPENDENCIAS DECLARADAS]" not in tokens.tokens_en_texto(
        "Dependencias: [SIN DEPENDENCIAS DECLARADAS]"
    )
    assert tokens.tokens_en_texto("[POSTSQL_ESS]") == []


def test_rellena_desde_el_catalogo_y_neutraliza_el_resto():
    catalogo = tokens.construir_catalogo(
        {"key": "M365", "version": "v2.0"},
        {
            "software_requirements": [
                {"name": "Ubuntu", "version": "latest", "license": "GPL"},
                {"name": "Editor", "version": "1.2.3", "license": "[LICENCIA POR VALIDAR]"},
            ]
        },
        {"01-01-01": "Instale Ubuntu 24.04.2 y compruebe.\n```bash\nlsb_release -a\n```"},
    )
    assert catalogo["course_key"] == "M365"
    assert catalogo["software"]["ubuntu"]["version"] == "24.04.2"
    assert catalogo["software"]["ubuntu"]["license"] == "GPL"
    assert catalogo["software"]["ubuntu"]["command"] == "lsb_release -a"
    assert catalogo["software"]["editor"]["version"] == "1.2.3"
    assert "license" not in catalogo["software"]["editor"]

    llamadas = []

    def llm(pendientes, _catalogo):
        llamadas.append(list(pendientes))
        return {"[POR CONFIRMAR]": "el panel de Copilot", "[FECHA DE VALIDACIÓN]": "[POR CONFIRMAR]"}

    html = "<p>[INSERTAR ENLACE]</p><p>[VERSIÓN POR VALIDAR]</p>"
    doc, html_listo = tokens.finalizar_tokens(_guia_con_tokens(), catalogo, html=html, llm=llm)
    assert llamadas and len(llamadas) == 1
    assert doc["software"][0]["version"] == "24.04.2"
    assert doc["software"][0]["validation"] == "lsb_release -a"
    assert doc["software"][0]["license"] == "GPL"
    assert doc["software"][1]["version"] == "1.2.3"
    assert doc["identification"]["key"] == "M365"
    assert doc["identification"]["version"] == "v2.0"
    assert "el panel de Copilot" in doc["note"]
    assert doc["metadata"]["last_validation"] == tokens.NEUTRO
    assert doc["metadata"]["placeholders_count"] == len(doc["placeholders"])
    assert "[FECHA DE VALIDACIÓN]" in doc["placeholders"]
    assert "[INSERTAR ENLACE]" in doc["placeholders"]
    visible = dict(doc)
    visible.pop("placeholders")
    plano = json.dumps(visible, ensure_ascii=False) + html_listo
    for token in _CANARY:
        assert token not in plano, token
    assert tokens.NEUTRO in html_listo
    assert "[INSERTAR ENLACE]" not in html_listo
    hallazgo = tokens.quality_issue_de_tokens(doc["placeholders"])
    assert hallazgo["severity"] == "warning"
    assert "Setup Guide se entregó" in hallazgo["error"]
    assert "The Setup Guide was delivered" in hallazgo["error"]


def test_un_llm_que_falla_no_bloquea_la_guia():
    def explota(_tokens, _catalogo):
        raise RuntimeError("bedrock no disponible")

    doc, html = tokens.finalizar_tokens(
        {"metadata": {}, "texto": "[POR CONFIRMAR]", "placeholders": []},
        {},
        html="<span>[ENLACE OFICIAL]</span>",
        llm=explota,
    )
    assert doc["texto"] == tokens.NEUTRO
    assert "[ENLACE OFICIAL]" not in html
    assert doc["metadata"]["placeholders_count"] == len(doc["placeholders"]) == 2


def test_el_render_no_cuenta_dos_veces_un_campo_ya_relleno():
    doc = {"metadata": {}, "software": [{"name": "Ubuntu", "version": "[VERSIÓN POR VALIDAR]", "pending": True}], "placeholders": []}
    catalogo = {"software": {"ubuntu": {"version": "24.04"}}, "llm": {}}

    def render(documento):
        return f"<td>{documento['software'][0]['version']}</td><span>[INSERTAR ENLACE]</span>"

    listo, html = tokens.finalizar_tokens(doc, catalogo, render_html=render)
    assert listo["software"][0]["version"] == "24.04"
    assert listo["placeholders"] == ["[INSERTAR ENLACE]"]
    assert listo["metadata"]["placeholders_count"] == 1
    assert "[VERSIÓN POR VALIDAR]" not in html
    assert "[INSERTAR ENLACE]" not in html


def test_el_checker_marca_tokens_de_guia_labs_y_lecciones():
    with tempfile.TemporaryDirectory() as tmp:
        for relativo, cuerpo in (
            ("labguide/lab-01-01-01-canary.md", "# Lab\n"),
            ("lessons/module-1-lesson-1-intro.md", "Versión [VERSIÓN POR VALIDAR] del cliente.\n"),
            ("book/Curso_LabGuide_complete.md", "# Libro\n"),
            ("decks/Glosario.pptx", "pptx"),
            ("setupguide/Setup_Guide.pdf", "%PDF"),
            (
                "setupguide/setup-guide.json",
                json.dumps({"placeholders": [], "software": [{"version": "[COMANDO DE PRUEBA]"}]}),
            ),
        ):
            ruta = os.path.join(tmp, *relativo.split("/"))
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            modo = "wb" if relativo.endswith(".pdf") else "w"
            with open(ruta, modo, encoding=None if modo == "wb" else "utf-8") as fichero:
                fichero.write(cuerpo if modo == "w" else cuerpo.encode())
        informe = artefactos.evaluar(
            artefactos._listar_local(tmp),
            lambda clave: artefactos._leer_local(tmp, clave),
        )
        assert artefactos.codigo_de_salida(informe) == 2
        texto = "\n".join(informe["template_tokens"])
        assert "COMANDO DE PRUEBA" in texto
        assert "lessons/module-1-lesson-1-intro.md" in texto
        assert informe["delivered"] is True


def test_el_informe_de_calidad_incluye_el_token_aunque_el_cuerpo_sea_texto():
    event = {
        "status": "success",
        "input": {
            "project_folder": "canary",
            "quality_issues": {"ready": True},
            "setup_guide_result": {
                "Payload": {
                    "statusCode": 200,
                    "body": json.dumps({
                        "placeholders": ["[FECHA DE VALIDACIÓN]"],
                        "placeholders_count": 1,
                        "quality_issue": {
                            "step": "InvokeSetupGuide",
                            "severity": "warning",
                            "deliverable": "Setup Guide",
                            "error": "La Setup Guide se entregó. The Setup Guide was delivered.",
                        },
                    }),
                }
            },
        },
    }
    informe = construir_informe_de_calidad(event)
    assert informe_tiene_hallazgos(informe)
    assert any(item["step"] == "InvokeSetupGuide" and item["severity"] == "warning" for item in informe["quality_issues"])
    assert informe["placeholders"][0]["token"] == "[FECHA DE VALIDACIÓN]"
    assert informe["delivered"] is True


def test_la_canary_acepta_image_model_desde_otro_directorio():
    ruta = os.path.join(_SCRIPTS, "canary_course.py")
    proc = subprocess.run(
        [sys.executable, ruta, "--project", "desde-tmp", "--image-model", "none"],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    cuerpo = json.loads(proc.stdout.split("Dry run")[0])
    assert cuerpo["image_model"] == "none"
    spec = importlib.util.spec_from_file_location("canary_desde_otro_dir", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    assert os.path.dirname(ruta) in sys.path
    assert modulo.entrada_canary("p", "a@b.c")["image_model"] == "gpt-image-2"
    assert modulo.main(["--project", "p", "--image-model", "gpt-image-2"]) == 0


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
        except Exception as exc:  # noqa: BLE001
            fallos.append((nombre, exc))
            print(f"FALLO  {nombre}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
