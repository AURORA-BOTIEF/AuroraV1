"""Offline tests for delivery that is never blocked by a quality check.

No AWS and no model calls. Covers model fallback, the owner report, the
placeholder lab, the import smoke, and the artifact checker.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_AQUI, "scripts")
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
sys.path.insert(0, os.path.join(_AQUI, "lambda"))

import bedrock_fallback as fb
import check_execution_artifacts as artefactos
import import_handlers_smoke as humo
from quality_report import alerta_al_propietario, construir_informe_de_calidad, informe_tiene_hallazgos


class _Error(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.response = {"Error": {"Code": code, "Message": message}}


def test_la_cuota_diaria_cambia_de_modelo_sin_esperar():
    vistos = []

    def invocar(modelo):
        vistos.append(modelo)
        if "opus" in modelo:
            raise _Error("ThrottlingException", "Too many tokens per day")
        return "laboratorio"

    texto, modelo = fb.run_model_chain(
        invocar,
        fb.fallback_model_ids("us.anthropic.claude-opus-4-6-v1"),
        sleep=lambda _n: (_ for _ in ()).throw(AssertionError("daily quota must not sleep")),
    )
    assert texto == "laboratorio"
    assert modelo == "us.anthropic.claude-sonnet-4-6"
    assert vistos[0].endswith("opus-4-6-v1")
    assert vistos[1] == "us.anthropic.claude-sonnet-4-6"


def test_el_throttle_por_minuto_espera_y_luego_cambia():
    esperas = []

    def invocar(modelo):
        if modelo.endswith("opus-4-6-v1"):
            raise _Error("ThrottlingException", "Too many requests")
        return "ok"

    texto, modelo = fb.run_model_chain(
        invocar,
        ["us.anthropic.claude-opus-4-6-v1", "us.anthropic.claude-sonnet-4-6"],
        max_attempts=5,
        sleep=lambda n: esperas.append(n),
    )
    assert texto == "ok"
    assert modelo.endswith("sonnet-4-6")
    # Two backoffs on the first model, the third throttle switches.
    assert esperas == [0, 1]


def test_access_denied_y_service_quota_cambian_enseguida():
    assert fb.classify_bedrock_error(_Error("AccessDeniedException", "no"), 0) == "switch"
    assert fb.classify_bedrock_error(
        _Error("ServiceQuotaExceededException", "daily"), 0
    ) == "switch"
    assert fb.classify_bedrock_error(_Error("ThrottlingException", "rate"), 1) == "backoff"
    assert fb.classify_bedrock_error(_Error("ThrottlingException", "rate"), 3) == "switch"
    assert fb.classify_bedrock_error(RuntimeError("boom"), 0) == "give_up"


def test_el_informe_avisa_al_propietario_y_no_al_alumno():
    informe = construir_informe_de_calidad(
        {
            "status": "success",
            "input": {
                "project_folder": "curso",
                "quality_issues": {
                    "ready": True,
                    "decks": {"step": "InvokeDeckBuilder", "error": "import", "severity": "error", "deliverable": "PPT missing"},
                },
                "setup_guide_error": {"Error": "LayoutError"},
                "failed_lab_ids": ["01-01-01"],
                "placeholders": [{"lab_id": "01-01-01"}],
                "models_used": {"01-01-02": "us.anthropic.claude-sonnet-4-6"},
            },
        }
    )
    assert informe["delivered"] is True
    assert "PPT missing" in informe["missing_deliverables"]
    assert "PDF missing" in informe["missing_deliverables"]
    assert informe["failed_lab_ids"] == ["01-01-01"]
    assert informe_tiene_hallazgos(informe)
    assert all(item["step"] != "ready" for item in informe["quality_issues"])
    asunto, texto = alerta_al_propietario(informe, "arn:exec", "curso")
    assert "was delivered" in texto
    assert "se entregó" in texto
    assert "lab_ids_to_regenerate" in texto
    assert "PPT missing" in texto
    assert "PDF missing" in texto
    assert asunto.startswith("Aurora quality report")
    limpio = construir_informe_de_calidad({"status": "success", "input": {"quality_issues": {"ready": True}}})
    assert informe_tiene_hallazgos(limpio) is False


def test_el_placeholder_es_bilingue_y_lleva_la_marca():
    ruta = os.path.join(_AQUI, "lambda", "strands_lab_writer", "strands_lab_writer.py")
    spec = importlib.util.spec_from_file_location("writer_placeholder", ruta)
    # Importing the writer pulls the package. The currency tests already do that.
    sys.path.insert(0, os.path.join(_AQUI, "lambda", "strands_lab_writer"))
    modulo = importlib.import_module("strands_lab_writer")
    texto = modulo.markdown_de_laboratorio_pendiente("01-01-01", "Canary", "ThrottlingException")
    h1 = [linea for linea in texto.splitlines() if linea.startswith("# ")]
    assert h1 == ["# Lab 01-01-01: Canary"]
    assert "PENDIENTE DE REGENERACIÓN" in texto
    assert "PENDING REGENERATION" in texto
    assert modulo.MARCA_PLACEHOLDER in texto
    assert "Paso 1" in texto
    del spec


def test_el_humo_aborta_si_un_handler_no_importa():
    with tempfile.TemporaryDirectory() as tmp:
        buena = os.path.join(tmp, "GoodFn")
        mala = os.path.join(tmp, "BadFn")
        os.makedirs(buena)
        os.makedirs(mala)
        with open(os.path.join(buena, "good_mod.py"), "w", encoding="utf-8") as fichero:
            fichero.write("def lambda_handler(event, context):\n    return 200\n")
        with open(os.path.join(mala, "bad_mod.py"), "w", encoding="utf-8") as fichero:
            fichero.write("import module_that_does_not_exist_reliability\n")
        plantilla = {
            "Resources": {
                "GoodFn": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Runtime": "python3.11",
                        "Handler": "good_mod.lambda_handler",
                        "CodeUri": "GoodFn",
                    },
                },
                "BadFn": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Runtime": "python3.11",
                        "Handler": "bad_mod.lambda_handler",
                        "CodeUri": "BadFn",
                    },
                },
            }
        }
        import yaml
        with open(os.path.join(tmp, "template.yaml"), "w", encoding="utf-8") as fichero:
            yaml.safe_dump(plantilla, fichero)
        fallos = humo.revisar_build(tmp)
        assert len(fallos) == 1
        assert "BadFn" in fallos[0]
        assert "module_that_does_not_exist_reliability" in fallos[0]
        solo = dict(plantilla)
        del solo["Resources"]["BadFn"]
        with open(os.path.join(tmp, "template.yaml"), "w", encoding="utf-8") as fichero:
            yaml.safe_dump(solo, fichero)
        assert humo.revisar_build(tmp) == []



def test_el_humo_acepta_handlers_anidados():
    assert humo.modulo_de_handler('assignments/assign_course.lambda_handler') == 'assignments.assign_course'
    assert humo.modulo_de_handler('auth/post_confirmation.lambda_handler') == 'auth.post_confirmation'
    assert humo.modulo_de_handler('book_to_pdf.lambda_handler') == 'book_to_pdf'


def test_el_humo_no_omite_un_modulo_faltante():
    stderr = "ModuleNotFoundError: No module named 'ppt_quality'"
    assert humo.es_incompatibilidad_binaria(stderr) is False
    binario = "ImportError: cannot import name 'etree' from 'lxml' (C:\\build\\lxml\\__init__.py)"
    assert humo.es_incompatibilidad_binaria(binario) is True


def test_el_checker_distinguie_faltantes_y_placeholders():

    with tempfile.TemporaryDirectory() as tmp:
        for relativo in (
            "labguide/lab-01-01-01-canary.md",
            "book/Curso_LabGuide_complete.md",
            "decks/Glosario.pptx",
            "setupguide/Setup_Guide.pdf",
        ):
            ruta = os.path.join(tmp, *relativo.split("/"))
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as fichero:
                fichero.write("# Lab\n")
        informe = artefactos.evaluar(
            artefactos._listar_local(tmp),
            lambda clave: artefactos._leer_local(tmp, clave),
        )
        assert artefactos.codigo_de_salida(informe) == 0
        with open(os.path.join(tmp, "labguide", "lab-01-01-01-canary.md"), "a", encoding="utf-8") as fichero:
            fichero.write("\n<!-- AURORA_PLACEHOLDER_PENDING_REGENERATION -->\n")
        informe = artefactos.evaluar(
            artefactos._listar_local(tmp),
            lambda clave: artefactos._leer_local(tmp, clave),
        )
        assert artefactos.codigo_de_salida(informe) == 2
        os.remove(os.path.join(tmp, "setupguide", "Setup_Guide.pdf"))
        informe = artefactos.evaluar(
            artefactos._listar_local(tmp),
            lambda clave: artefactos._leer_local(tmp, clave),
        )
        assert artefactos.codigo_de_salida(informe) == 1
        assert "Setup PDF" in informe["missing"]
        guia = os.path.join(tmp, "setupguide", "setup-guide.json")
        os.makedirs(os.path.dirname(guia), exist_ok=True)
        with open(guia, "w", encoding="utf-8") as fichero:
            fichero.write('{"placeholders": [], "software": [{"version": "[VERSIÓN POR VALIDAR]"}]}')
        # The PDF is still missing, so delivery is incomplete.
        informe = artefactos.evaluar(
            artefactos._listar_local(tmp),
            lambda clave: artefactos._leer_local(tmp, clave),
        )
        assert any("VERSIÓN POR VALIDAR" in item for item in informe["template_tokens"])
        pdf = os.path.join(tmp, "setupguide", "Setup_Guide.pdf")
        with open(pdf, "wb") as fichero:
            fichero.write(b"%PDF-1.4")
        informe = artefactos.evaluar(
            artefactos._listar_local(tmp),
            lambda clave: artefactos._leer_local(tmp, clave),
        )
        assert artefactos.codigo_de_salida(informe) == 2


def test_la_canary_en_seco_no_llama_a_aws():
    import canary_course

    cuerpo = canary_course.entrada_canary("canary-test", "juan.ossa@netec.com")
    assert cuerpo["content_type"] == "both"
    assert cuerpo["content_source"] == "s3"
    assert cuerpo["modules_to_generate"] == [1]
    assert cuerpo["total_modules"] == 1
    assert cuerpo["course_language"] == "es"
    assert cuerpo["user_email"] == "juan.ossa@netec.com"
    assert cuerpo["outline_s3_key"] == "canary-test/outline/canary.yaml"
    assert cuerpo["image_model"] == "gpt-image-2"
    assert canary_course.entrada_canary("canary-test", "juan.ossa@netec.com", image_model="none")["image_model"] == "none"
    assert "lab_requirements" in cuerpo
    assert canary_course.main(["--project", "canary-test", "--email", "juan.ossa@netec.com"]) == 0


def test_el_payload_canario_tiene_los_campos_del_flujo():
    import json
    import canary_course

    plantilla = os.path.join(_AQUI, "current_state_machine.json")
    with open(plantilla, encoding="utf-8") as fichero:
        estados = json.load(fichero)["States"]
    requeridos = canary_course.campos_requeridos_al_inicio(estados)
    cuerpo = canary_course.entrada_canary("canary-test", "juan.ossa@netec.com")
    faltan = sorted(requeridos - set(cuerpo))
    assert faltan == [], f"canary start payload missing {faltan}"
    for campo in canary_course.CAMPOS_DE_INICIO:
        assert campo in cuerpo, campo
    # Real QA starts send an empty string, not a missing key.
    assert "lab_requirements" in cuerpo
    assert cuerpo["content_source"] == "s3"
    assert cuerpo["outline_s3_key"]


def test_el_presupuesto_de_formato_no_esta_en_un_raise():
    ruta = os.path.join(_AQUI, "lambda", "strands_lab_planner", "strands_lab_planner.py")
    texto = open(ruta, encoding="utf-8").read()
    assert "quality_warning" in texto
    assert "The format cap never fails the course" in texto
    # The old raise lived on the exceed branch. It must not come back.
    assert "raise ValueError" not in texto.split("if ajuste_formato.get(\"excede\")")[1].split("if preflight")[0]


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
