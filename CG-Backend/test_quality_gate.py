"""Quality gate: high-confidence findings that survive the final retry are not delivered.

Offline. No AWS calls and no model calls. The audit examples (undeclared xlsx,
syllabus quantity, impossible duration, environment, file-shaped omission) are
the fixtures.
"""

import importlib.util
import io
import json
import os
import sys
import types
from contextlib import redirect_stdout

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

_HERE = os.path.dirname(os.path.abspath(__file__))
_WRITER = os.path.join(_HERE, "lambda", "strands_lab_writer")
_PLANNER = os.path.join(_HERE, "lambda", "strands_lab_planner")
_LAMBDA = os.path.join(_HERE, "lambda")


class _ClienteSimulado:
    def __getattr__(self, _nombre):
        return lambda *a, **k: None


class _Cuerpo:
    def __init__(self, texto):
        self._texto = texto if isinstance(texto, str) else texto.decode("utf-8")

    def read(self):
        return self._texto.encode("utf-8")


class _S3Simulado:
    def __init__(self, objetos=None):
        self.objetos = dict(objetos or {})
        self.puts = []

    def get_object(self, Bucket=None, Key=None):  # noqa: N803
        if Key not in self.objetos:
            raise KeyError(Key)
        return {"Body": _Cuerpo(self.objetos[Key])}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        cuerpo = kwargs.get("Body", "")
        if isinstance(cuerpo, bytes):
            cuerpo = cuerpo.decode("utf-8")
        self.objetos[kwargs.get("Key")] = cuerpo
        return {}


def _cargar(nombre, carpeta):
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", nombre)
    previos = {n: sys.modules.get(n) for n in nombres}

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
    sys.modules.update({
        "boto3": boto3_sim,
        "botocore": botocore_sim,
        "botocore.config": config_sim,
        "botocore.exceptions": exceptions_sim,
    })
    sys.modules.pop(nombre, None)
    sys.modules.pop("referent_check", None)
    ruta = os.path.join(_HERE, carpeta)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    try:
        return importlib.import_module(nombre)
    finally:
        for clave, previo in previos.items():
            if previo is None:
                sys.modules.pop(clave, None)
            else:
                sys.modules[clave] = previo


def _stub_boto3():
    """Keep imports of status/notification/validator offline when boto3 is absent."""
    if "boto3" in sys.modules and hasattr(sys.modules["boto3"], "client"):
        return
    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: _ClienteSimulado()
    botocore_sim = types.ModuleType("botocore")
    exceptions_sim = types.ModuleType("botocore.exceptions")

    class _ClientError(Exception):
        def __init__(self, *a, **k):
            self.response = {"Error": {"Code": "Stub", "Message": "stub"}}
            super().__init__("stub")

    exceptions_sim.ClientError = _ClientError
    botocore_sim.exceptions = exceptions_sim
    sys.modules["boto3"] = boto3_sim
    sys.modules["botocore"] = botocore_sim
    sys.modules["botocore.exceptions"] = exceptions_sim


def _cargar_archivo(ruta):
    nombre = "mod_" + os.path.splitext(os.path.basename(ruta))[0]
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_TEMARIO = """
course:
  title: Curso de fondos
  total_duration_minutes: 120
El escenario consta de seis fondos multiactivo.
"""

_LAB_PLAN = {
    "lab_id": "01-00-01",
    "lab_title": "Fondos",
    "estimated_duration": 45,
    "objectives": ["Revisar el escenario"],
    "scope": "Fondos",
    "expected_outcomes": ["Indicadores calculados"],
}


def _ejecutar_writer(plan, contenidos, max_intentos=1, objetos=None, requisitos=""):
    modulo = _cargar("strands_lab_writer", "lambda/strands_lab_writer")
    base = {"p/outline.yaml": _TEMARIO, "p/manual.txt": "Manual sin ficheros extra."}
    base.update(objetos or {})
    s3 = _S3Simulado(base)
    modulo.s3_client = s3
    modulo.MAX_LAB_GENERATION_ATTEMPTS = max_intentos
    contextos = []

    def _generador(lab_plans, master_context, model_provider="bedrock",
                   lesson_content="", previous_lab_context=""):
        contextos.append(dict(master_context))
        indice = min(len(contextos), len(contenidos)) - 1
        return {lab_plans[0]["lab_id"]: contenidos[indice]}

    modulo.generate_all_labs_batch = _generador
    modulo._verify_and_refine_lab_guide = lambda guide, plan_, ctx, model_provider="bedrock": guide
    modulo._finalize_lab_markdown = lambda markdown, is_demo, is_spanish=True: markdown
    modulo.load_master_plan_from_s3 = lambda bucket, key: plan
    def _guardar(**kw):
        clave = f"p/labguide/lab-{kw['lab_id']}.md"
        s3.objetos[clave] = kw["lab_guide"]
        return clave

    modulo.save_lab_guide_to_s3 = _guardar
    modulo._lab_skip_if_exists_enabled = lambda: False
    modulo._find_existing_lab_guide_key = lambda bucket, project, lab_id: None
    plan = dict(plan)
    if requisitos:
        plan["additional_requirements"] = requisitos
    salida_log = io.StringIO()
    with redirect_stdout(salida_log):
        resultado = modulo.lambda_handler(
            {
                "course_bucket": "bucket",
                "master_plan_key": "p/labguide/lab-master-plan.json",
                "project_folder": "p",
                "outline_s3_key": "p/outline.yaml",
                "manual_text_s3_key": "p/manual.txt",
                "lab_ids": ["01-00-01"],
                "lab_lesson_keys": {},
            },
            None,
        )
    return modulo, resultado, s3, salida_log.getvalue(), contextos


def _lab_limpio():
    return """# Lab 01-00-01: Fondos

## Descripcion General
El escenario consta de seis fondos multiactivo.

### Paso 1: Revisar
**Instructions:**
1. Lea el escenario entregado en clase.
**Expected output:** El escenario leido.
"""


def _lab_xlsx():
    return """# Lab 01-00-01: Fondos

## Descripcion General
El escenario consta de seis fondos multiactivo.

### Paso 1: Abrir los datos
**Instructions:**
1. Abra el archivo Ventas_MultiRegional_2024.xlsx desde OneDrive.
**Expected output:** El libro abierto.
"""


def _lab_tres_fondos():
    return """# Lab 01-00-01: Fondos

## Descripcion General
Trabaja con tres fondos multiactivo.

### Paso 1: Revisar
**Instructions:**
1. Cuente los fondos del escenario.
**Expected output:** El conteo anotado.
"""


def _lab_b6():
    partes = ["# Lab 01-00-01: Carga\n", "| **Duración** | 15 minutos |\n"]
    for paso in range(1, 10):
        bloques = "\n".join(
            f"```bash\necho paso{paso}-{bloque}\n```" for bloque in range(4)
        )
        partes.append(f"### Paso {paso}: Accion\n{bloques}\n")
    return "\n".join(partes)


def _lab_objetivo_ausente():
    return """# Lab 01-00-01: Fondos

## Descripcion General
El escenario consta de seis fondos multiactivo.

### Paso 1: Revisar
Siga el escenario.
"""


def test_alta_confianza_bloquea_y_baja_queda_en_aviso():
    modulo = _cargar("strands_lab_writer", "lambda/strands_lab_writer")
    bloquean, avisos = modulo.partir_hallazgos([
        {"verificacion": "B1", "confianza": "alta", "valor": "Ventas_MultiRegional_2024.xlsx"},
        {"verificacion": "A2", "confianza": "alta", "valor": "fondos: 6 vs 3"},
        {"verificacion": "B6", "confianza": "alta", "valor": "15 min no alcanzan"},
        {"verificacion": "C2", "confianza": "alta", "valor": "bash prohibido"},
        {"verificacion": "B3p", "confianza": "alta", "valor": "Idea_Coach.pptx"},
        {"verificacion": "A5", "confianza": "alta", "valor": "objetivo ausente"},
        {"verificacion": "B5", "confianza": "baja", "valor": "ampliacion de hardware"},
        {"verificacion": "C2", "confianza": "baja", "valor": "mencion en prosa"},
        {"verificacion": "B3p", "confianza": "baja", "valor": "mencionado sin creacion"},
    ])
    codigos = {f["verificacion"] for f in bloquean}
    assert codigos == {"B1", "A2", "B6", "C2", "B3p", "A5"}
    assert {f["verificacion"] for f in avisos} == {"B5", "C2", "B3p"}
    assert all(f["confianza"] == "baja" for f in avisos)
    assert modulo.resumir_hallazgos([]) == "passed"
    assert modulo.resumir_hallazgos(bloquean).startswith("NEEDS_REVIEW")


def test_el_writer_no_entrega_el_xlsx_no_declarado_tras_el_ultimo_intento():
    """An undeclared xlsx is inlined as a fictitious annex, so the finding does not remain.

    The quality gate still fails the lab when a high-confidence finding is left
    (duration, objective, environment). A file the annex can carry is no longer
    one of those findings.
    """
    _modulo, resultado, s3, log, contextos = _ejecutar_writer(
        {"lab_plans": [_LAB_PLAN]}, [_lab_xlsx()], max_intentos=1
    )
    assert resultado["statusCode"] == 200, resultado
    assert resultado["quality_status"] == "passed", resultado
    assert resultado["labs_needing_review"] == []
    guia = s3.objetos["p/labguide/lab-01-00-01.md"]
    assert "Anexo (datos ficticios)" in guia
    assert "Ventas_MultiRegional_2024.xlsx" in guia
    assert "QUALITY GATE" in log
    assert len(contextos) == 1
    informe = json.loads(s3.objetos["p/validation/labs-referential-integrity.json"])
    assert informe["quality_status"] == "passed"


def test_el_writer_reintenta_y_solo_entonces_marca_needs_review():
    """The third text is no longer a silent pass when the xlsx is still there."""
    limpio = _lab_limpio()
    malo = _lab_xlsx()
    _modulo, corregido, _s3, _log, contextos = _ejecutar_writer(
        {"lab_plans": [_LAB_PLAN]}, [malo, limpio], max_intentos=3
    )
    assert corregido["quality_status"] == "passed", corregido
    assert contextos and len(contextos) == 2

    _modulo, final, s3, log, contextos = _ejecutar_writer(
        {"lab_plans": [_LAB_PLAN]}, [malo, malo, malo], max_intentos=3
    )
    assert final["statusCode"] == 200
    # Attempts 1 and 2 ask the model to drop the file. The guide that ships
    # still cannot depend on an undelivered workbook, so the annex inlines it
    # and the gate passes.
    assert len(contextos) == 3
    assert final["quality_status"] == "passed", final
    assert "Anexo (datos ficticios)" in s3.objetos["p/labguide/lab-01-00-01.md"]
    assert "referential_correction" in (contextos[1] or {})


def test_cantidad_duracion_objetivo_entorno_y_omision_bloquean():
    """Audit shapes: six funds vs three, 15 min / 9 steps, missing objective, C2, B3p."""
    writer = _cargar("strands_lab_writer", "lambda/strands_lab_writer")
    sys.path.insert(0, _WRITER)
    from referent_check import auditar_laboratorio  # noqa: E402

    cantidad = auditar_laboratorio(_lab_tres_fondos(), fuentes=_TEMARIO)
    bloquean, _avisos = writer.partir_hallazgos(cantidad["violaciones"])
    assert any(f["verificacion"] == "A2" for f in bloquean), cantidad["violaciones"]

    duracion = auditar_laboratorio(_lab_b6(), fuentes=_TEMARIO)
    bloquean, _avisos = writer.partir_hallazgos(duracion["violaciones"])
    assert any(f["verificacion"] == "B6" for f in bloquean), duracion.get("duracion")

    entorno = auditar_laboratorio(
        "\n".join(
            ["# Lab", "### Paso 1: Uno", "```bash", "echo 1", "```",
             "### Paso 2: Dos", "```bash", "echo 2", "```",
             "### Paso 3: Tres", "```bash", "echo 3", "```"]
        ),
        fuentes=_TEMARIO,
        entorno={"etiquetas": ["powershell"], "prohibidos": ["sed"]},
    )
    # sed is not in this lab; the bash fences against a powershell label are the hit.
    bloquean, avisos = writer.partir_hallazgos(entorno["violaciones"])
    assert any(f["verificacion"] == "C2" and f["confianza"] == "alta" for f in bloquean), entorno
    assert all(f["confianza"] != "alta" for f in avisos)

    omision = auditar_laboratorio(
        _lab_limpio(),
        fuentes=_TEMARIO,
        expected_outcomes=["Archivo 'Idea_Coach.pptx' de la presentacion"],
    )
    bloquean, _avisos = writer.partir_hallazgos(omision["violaciones"])
    assert any(f["verificacion"] == "B3p" and "Idea_Coach.pptx" in f["valor"] for f in bloquean)

    plan = dict(_LAB_PLAN, outline_objective="Conciliar los seis fondos del escenario.")
    hallazgo = writer.hallazgo_objetivo_ausente(_lab_objetivo_ausente(), plan)
    assert hallazgo and hallazgo["confianza"] == "alta" and hallazgo["verificacion"] == "A5"
    assert writer.hallazgo_objetivo_ausente(
        _lab_objetivo_ausente() + "\nConciliar los seis fondos del escenario.\n", plan
    ) is None

    _modulo, resultado, _s3, log, _ctx = _ejecutar_writer(
        {"lab_plans": [_LAB_PLAN]}, [_lab_b6()], max_intentos=1
    )
    assert resultado["quality_status"] == "needs_review"
    assert any(f["verificacion"] == "B6" for f in resultado["labs_needing_review"][0]["findings"])
    assert "needs_review" in log

    _modulo, resultado, _s3, log, _ctx = _ejecutar_writer(
        {"lab_plans": [plan]}, [_lab_objetivo_ausente()], max_intentos=1
    )
    assert resultado["quality_status"] == "needs_review"
    assert any(f["verificacion"] == "A5" for f in resultado["labs_needing_review"][0]["findings"])

    _modulo, resultado, _s3, log, _ctx = _ejecutar_writer(
        {"lab_plans": [_LAB_PLAN]},
        ["\n".join([
            "# Lab 01-00-01: Fondos",
            "El escenario consta de seis fondos multiactivo.",
            "### Paso 1: Uno", "```bash", "echo 1", "```",
            "### Paso 2: Dos", "```bash", "echo 2", "```",
            "### Paso 3: Tres", "```bash", "echo 3", "```",
        ])],
        max_intentos=1,
        requisitos="Use la etiqueta powershell en cada bloque.",
    )
    assert resultado["quality_status"] == "needs_review", resultado
    assert any(f["verificacion"] == "C2" for f in resultado["labs_needing_review"][0]["findings"])


def test_la_baja_confianza_no_bloquea_el_writer():
    mencionado = """# Lab 01-00-01: Fondos

## Descripcion General
El escenario consta de seis fondos multiactivo.

### Paso 1: Revisar
Abra `data_transform.py` y observe las funciones.
"""
    plan = dict(_LAB_PLAN, expected_outcomes=["Archivo 'data_transform.py' con al menos 6 funciones"])
    _modulo, resultado, _s3, log, contextos = _ejecutar_writer(
        {"lab_plans": [plan]}, [mencionado], max_intentos=1
    )
    assert resultado["statusCode"] == 200
    assert resultado["quality_status"] == "passed", resultado
    assert resultado["labs_needing_review"] == []
    assert resultado["quality_warnings"], resultado
    assert "low-confidence" in log
    assert len(contextos) == 1


def test_el_planner_falla_la_puerta_si_la_cantidad_o_el_objetivo_no_cuadran():
    modulo = _cargar("strands_lab_planner", "lambda/strands_lab_planner")
    puerta = modulo.clasificar_hallazgos_de_plan(
        {"violaciones": [
            {"verificacion": "A1", "confianza": "alta", "valor": "Ventas_MultiRegional_2024.xlsx", "campo": "scope"},
            {"verificacion": "A1", "confianza": "baja", "valor": "salida.csv", "campo": "outcomes"},
        ]},
        {"ok": False, "suma_plan": 90, "total_curso": 60, "labs_plan": 3, "labs_temario": 2, "faltan": 0, "sobran": 1},
        {"conflictos": [{
            "lab_id": "01-00-01",
            "campo": "objective",
            "temario": "Conciliar seis fondos",
            "plan": "Revisar tres fondos",
        }]},
        {"modulos": [{"modulo": 1, "senales": ["poco_tiempo"], "por_laboratorio": 2.7}]},
    )
    assert puerta["quality_status"] == "needs_review"
    codigos = [h["verificacion"] for h in puerta["quality_findings"]]
    assert "A1" in codigos and "A3" in codigos and "A5" in codigos
    assert all(h["verificacion"] != "A1" or h["confianza"] == "alta" for h in puerta["quality_findings"])
    assert any(h["verificacion"] == "preflight" and h["confianza"] == "baja" for h in puerta["quality_warnings"])
    assert "NEEDS_REVIEW" in puerta["quality_summary"]

    limpia = modulo.clasificar_hallazgos_de_plan(
        {"violaciones": [{"verificacion": "A1", "confianza": "baja", "valor": "salida.csv"}]},
        {"ok": True, "suma_plan": 40, "total_curso": 120, "labs_plan": 2, "labs_temario": 2, "faltan": 0, "sobran": 0},
        {"conflictos": []},
        {"modulos": [{"modulo": 1, "senales": ["poco_tiempo"], "por_laboratorio": 2.7}]},
    )
    assert limpia["quality_status"] == "passed"
    assert limpia["quality_findings"] == []
    assert limpia["quality_warnings"]


def _handler_planner(modulo, outline, plan_del_modelo):
    modulo.load_outline_from_s3 = lambda *a, **k: outline
    modulo.generate_lab_master_plan = lambda **k: plan_del_modelo
    modulo.auditar_y_corregir_plan = lambda plan, **k: (plan, {"total": 0, "violaciones": [], "ok": True})
    modulo.save_master_plan_to_s3 = lambda bucket, project_folder, master_plan: "p/labguide/lab-master-plan.json"
    modulo.s3_client = _S3Simulado({})
    log = io.StringIO()
    with redirect_stdout(log):
        resultado = modulo.lambda_handler(
            {
                "course_bucket": "bucket",
                "outline_s3_key": "p/outline/curso.yaml",
                "project_folder": "p",
                "model_provider": "bedrock",
            },
            None,
        )
    return resultado, log.getvalue()


def test_el_handler_del_planner_marca_needs_review_sin_cambiar_el_200():
    modulo = _cargar("strands_lab_planner", "lambda/strands_lab_planner")
    outline = {
        "course": {
            "title": "Curso de prueba",
            "total_duration_minutes": 120,
            "modules": [{
                "title": "Modulo 1",
                "lab_activities": [
                    {"title": "Practica uno", "duration_minutes": 18, "objective": "Conciliar seis fondos"},
                    {"title": "Practica dos", "duration_minutes": 22},
                ],
            }],
        }
    }
    de_mas = {
        "lab_plans": [
            {"lab_id": "01-00-01", "lab_title": "Practica uno", "estimated_duration": 18,
             "objectives": ["Conciliar seis fondos"], "scope": "a", "expected_outcomes": ["c"]},
            {"lab_id": "01-00-02", "lab_title": "Practica dos", "estimated_duration": 22,
             "objectives": ["a"], "scope": "b", "expected_outcomes": ["c"]},
            {"lab_id": "01-00-03", "lab_title": "Practica extra", "estimated_duration": 30,
             "objectives": ["a"], "scope": "b", "expected_outcomes": ["c"]},
        ]
    }
    resultado, log = _handler_planner(modulo, outline, de_mas)
    assert resultado["statusCode"] == 200, resultado
    assert resultado["quality_status"] == "needs_review", resultado.get("quality_summary")
    assert any(h["verificacion"] == "A3" for h in resultado["quality_findings"])
    assert "needs_review" in log

    alineado = {
        "lab_plans": [
            {"lab_id": "01-00-01", "lab_title": "Practica uno", "estimated_duration": 40,
             "objectives": ["otra cosa"], "scope": "a", "expected_outcomes": ["c"]},
            {"lab_id": "01-00-02", "lab_title": "Practica dos", "estimated_duration": 30,
             "objectives": ["a"], "scope": "b", "expected_outcomes": ["c"]},
        ]
    }
    resultado, _log = _handler_planner(modulo, outline, alineado)
    assert resultado["statusCode"] == 200
    assert resultado["quality_status"] == "passed", resultado.get("quality_findings")


def test_el_estado_visible_separa_needs_review_de_un_fallo_generico():
    _stub_boto3()
    spec = importlib.util.spec_from_file_location(
        "exec_status_gate", os.path.join(_LAMBDA, "exec_status.py")
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    visible = modulo.estado_visible_del_curso(
        "FAILED",
        "LabQualityNeedsReview",
        'NEEDS_REVIEW 01-00-01 B1: Ventas_MultiRegional_2024.xlsx',
        None,
    )
    assert visible["quality_status"] == "needs_review"
    assert visible["course_status"] == "needs_review"
    assert visible["needs_review"] is True
    assert "Ventas_MultiRegional_2024.xlsx" in visible["error"]

    sombra = modulo.estado_visible_del_curso(
        "SUCCEEDED",
        None,
        None,
        {"lab_quality_needs_review": True, "lab_quality_summary": "NEEDS_REVIEW A2", "quality_warnings": []},
    )
    assert sombra["course_status"] == "needs_review"
    assert "A2" in sombra["error"]

    decision = modulo.estado_visible_del_curso(
        "SUCCEEDED",
        None,
        None,
        {
            "lab_quality_decision": {"needs_review": True},
            "lab_quality_summaries": ["NEEDS_REVIEW 01-00-01 A2: seis fondos"],
        },
    )
    assert decision["course_status"] == "needs_review"
    assert "seis fondos" in decision["error"]

    limpio = modulo.estado_visible_del_curso(
        "SUCCEEDED", None, None, {"lab_quality_needs_review": False, "quality_warnings": [{"lab_id": "01"}]}
    )
    assert limpio["quality_status"] == "passed"
    assert limpio["needs_review"] is False
    assert limpio["error"] is None
    assert limpio["quality_warnings"] == [{"lab_id": "01"}]

    fallo = modulo.estado_visible_del_curso("FAILED", "States.TaskFailed", "timeout", None)
    assert fallo["quality_status"] == "failed"
    assert fallo["course_status"] == "failed"

    aviso = modulo.estado_visible_del_curso(
        "SUCCEEDED", None, None, {"setup_guide_error": {"Error": "Runtime"}}
    )
    assert aviso["course_status"] == "SUCCEEDED_WITH_WARNINGS"
    assert aviso["needs_review"] is False
    assert aviso["error"] is None
    assert aviso["generation_warnings"][0]["code"] == "setup_guide_error"

    enlaces = modulo.estado_visible_del_curso(
        "FAILED",
        "LinkAuditFailed",
        "Enlaces públicos muertos (404, 410 o DNS). El curso no se entregó.",
        None,
    )
    assert enlaces["course_status"] == "link_audit_failed"
    assert enlaces["needs_review"] is False


def test_la_notificacion_de_needs_review_no_dice_que_el_curso_salio():
    _stub_boto3()
    spec = importlib.util.spec_from_file_location(
        "notif_gate", os.path.join(_LAMBDA, "strands_notification", "strands_notification.py")
    )
    # The module builds a SES client at import. Region is set; no send happens here.
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    asunto, texto, html = modulo.construir_notificacion(
        "needs_review",
        "curso-fondos",
        "NEEDS_REVIEW 01-00-01 B1: Ventas_MultiRegional_2024.xlsx",
        "arn:exec",
    )
    assert "revisión" in asunto.lower() or "revision" in asunto.lower()
    assert "no se entregó" in texto
    assert "Ventas_MultiRegional_2024.xlsx" in texto
    assert "exitosamente" not in texto
    assert "Ventas_MultiRegional_2024.xlsx" in html
    _asunto_ok, texto_ok, _html_ok = modulo.construir_notificacion(
        "success", "curso-fondos", "", "arn:exec"
    )
    assert "exitosamente" in texto_ok
    asunto_aviso, texto_aviso, _html_aviso = modulo.construir_notificacion(
        "success", "curso-fondos", "", "arn:exec", advertencias_parciales=["Setup Guide"]
    )
    assert "advertencias" in asunto_aviso.lower()
    assert "Setup Guide" in texto_aviso
    assert "exitosamente" not in texto_aviso
    asunto_enlace, texto_enlace, _html_enlace = modulo.construir_notificacion(
        "link_audit_failed", "curso-fondos", "404", "arn:exec"
    )
    assert "enlaces" in asunto_enlace.lower()
    assert "no se entregó" in texto_enlace
    assert "labguide/enlaces.json" in texto_enlace
    assert "validation/link-audit.json" not in texto_enlace
    assert "exitosamente" not in texto_enlace


def test_un_aviso_del_validador_no_es_error_de_alta():
    """Content-validator warnings stay warnings. Structural errors still fail all_valid."""
    _stub_boto3()
    spec = importlib.util.spec_from_file_location(
        "cv_gate", os.path.join(_LAMBDA, "content_validator", "content_validator.py")
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    vago = "# Lab 01-00-01: X\n\nLa validacion funciona correctamente y tiene un 80% de éxito.\n"
    informe = modulo.ContentValidator().validate_lab(vago)
    assert any(w.rule == "unmeasurable_validation" for w in informe.warnings)
    assert informe.is_valid is False or informe.errors  # structural gaps may also be errors
    # The unmeasurable rule itself is a warning, not an error.
    assert all(e.rule != "unmeasurable_validation" for e in informe.errors)
    solo_aviso = modulo.ValidationResult(
        "unmeasurable_validation", modulo.ValidationSeverity.WARNING, "criterio vago"
    )
    assert solo_aviso.severity == modulo.ValidationSeverity.WARNING


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
        except Exception as exc:  # noqa: BLE001
            fallos += 1
            print(f"FALLO  {nombre}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas correctas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(_ejecutar())
