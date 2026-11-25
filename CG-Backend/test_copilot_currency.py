"""C6: Microsoft 365 Copilot surfaces must match the verified catalog.

The October audit named Plan My Day, Researcher, Analyst, Agent Builder and
Workflows/Frontier as names a lab could use with no check against official
docs. These tests resolve those names offline. Nothing here opens a socket.

    python test_copilot_currency.py
    pytest test_copilot_currency.py
"""

import io
import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_CARPETA = os.path.join(_HERE, "lambda", "strands_lab_writer")
if _CARPETA not in sys.path:
    sys.path.insert(0, _CARPETA)

os.environ.pop("COPILOT_CATALOG_RETRIEVAL", None)
os.environ.pop("CURRENCY_RETRY", None)

from copilot_currency import (  # noqa: E402
    aplicar_recuperacion,
    auditar_superficies_copilot,
    cargar_catalogo,
    mensaje_de_correccion_moneda,
    texto_de_catalogo_para_prompt,
)


def _nombres(informe):
    return [h["nombre"] for h in informe["hallazgos"] if h.get("bloquea")]


def _ids(informe):
    return [r["id"] for r in informe["resueltos"]]


def test_el_catalogo_esta_versionado_y_cada_fila_tiene_fuente_oficial():
    catalogo = cargar_catalogo()
    assert catalogo["catalog_version"] == "2026-11-25.1"
    assert catalogo["verified_on"] == "2026-11-25"
    assert catalogo["retrieval"]["default"] is False
    ids = []
    for feature in catalogo["features"]:
        ids.append(feature["id"])
        assert feature["doc_url"].startswith("https://"), feature["id"]
        assert feature["status"] in ("available", "preview", "deprecated")
        assert feature["aliases"] or feature.get("aliases_sensitive")
        assert feature["availability"]
        if feature["status"] == "deprecated":
            assert feature.get("replaced_by"), feature["id"]
        if feature["status"] == "preview":
            assert feature.get("requires_any"), feature["id"]
    assert len(ids) == len(set(ids))
    for requerido in (
        "plan-my-day",
        "researcher",
        "analyst",
        "agent-builder",
        "workflows",
        "frontier",
    ):
        assert requerido in ids


def test_las_superficies_verificadas_del_audit_se_aceptan():
    """Plan My Day, Researcher, Analyst, Agent Builder and Frontier are current."""
    texto = """
    # Lab 02-01-01: Agentes de Microsoft 365 Copilot
    En Microsoft 365 Copilot abre Copilot Chat y Copilot Studio.
    1. Crea el agente con Agent Builder a partir de la plantilla Plan My Day.
    2. En Copilot, selecciona el agente Researcher y pide un informe con citas.
    3. Abre el agente Analyst y adjunta el archivo de datos.
    4. El programa Frontier da acceso previo; no es un botón de la aplicación.
    """
    informe = auditar_superficies_copilot(texto, recuperar=False)
    assert informe["ok"], informe["hallazgos"]
    assert informe["catalog_version"] == "2026-11-25.1"
    for identificado in (
        "plan-my-day",
        "researcher",
        "analyst",
        "agent-builder",
        "frontier",
        "copilot-chat",
        "copilot-studio",
    ):
        assert identificado in _ids(informe), _ids(informe)


def test_workflows_sin_frontier_se_bloquea_y_con_frontier_no():
    sin = auditar_superficies_copilot(
        "En Microsoft 365 Copilot, abre el agente Workflows y automatiza el correo.",
        recuperar=False,
    )
    assert not sin["ok"]
    assert any(h["tipo"] == "disponibilidad" and h["id"] == "workflows" for h in sin["hallazgos"])

    con = auditar_superficies_copilot(
        "Workflows Agent está en vista previa del programa Frontier. "
        "En Copilot, añádelo desde el almacén de agentes.",
        recuperar=False,
    )
    assert con["ok"], con["hallazgos"]
    assert "workflows" in _ids(con)


def test_un_nombre_inventado_y_uno_retirado_se_bloquean():
    """Unknown button/agent, plus the retired product names."""
    texto = """
    En Copilot, pulsa el botón "Plan Your Week" y abre el agente Magic Scheduler.
    Entra también a Bing Chat Enterprise y crea el bot en Power Virtual Agents.
    """
    informe = auditar_superficies_copilot(texto, recuperar=False)
    assert not informe["ok"]
    bloqueos = {(h["tipo"], h["nombre"]) for h in informe["hallazgos"]}
    assert ("unknown", "Plan Your Week") in bloqueos, bloqueos
    assert ("unknown", "Magic Scheduler") in bloqueos, bloqueos
    assert ("deprecated", "Bing Chat Enterprise") in bloqueos, bloqueos
    assert ("deprecated", "Power Virtual Agents") in bloqueos, bloqueos
    mensaje = mensaje_de_correccion_moneda(informe["hallazgos"])
    assert "Bing Chat Enterprise" in mensaje
    assert "Microsoft Copilot" in mensaje
    assert "[POR CONFIRMAR]" in mensaje
    assert "Magic Scheduler" in mensaje


def test_analyst_y_workflows_genericos_no_se_confunden_con_el_producto():
    prosa = (
        "The analyst reviews the CSV. Estos workflows de GitHub Actions "
        "compilan el repo. The frontier of the research is open."
    )
    informe = auditar_superficies_copilot(prosa, recuperar=False)
    assert informe["ok"], informe["hallazgos"]
    assert informe["hallazgos"] == []
    assert informe["resueltos"] == []


def test_github_copilot_y_un_boton_generico_no_bloquean():
    texto = (
        "Haga clic en GitHub Copilot y pida un resumen. "
        "En Copilot, pulse el botón \"Guardar\"."
    )
    informe = auditar_superficies_copilot(texto, recuperar=False)
    assert informe["ok"], informe["hallazgos"]


def test_el_manual_autoriza_un_nombre_desconocido_pero_no_uno_retirado():
    manual = "El curso usa el agente Magic Scheduler descrito en el manual del instructor."
    desconocido = auditar_superficies_copilot(
        "En Copilot, abre el agente Magic Scheduler y revisa la agenda.",
        manual=manual,
        recuperar=False,
    )
    assert desconocido["ok"], desconocido["hallazgos"]
    assert any(r["fuente"] == "manual" and r["nombre"] == "Magic Scheduler" for r in desconocido["resueltos"])

    retirado = auditar_superficies_copilot(
        "Abre Bing Chat Enterprise como indica el manual.",
        manual="El manual todavía dice Bing Chat Enterprise.",
        recuperar=False,
    )
    assert not retirado["ok"]
    assert _nombres(retirado) == ["Bing Chat Enterprise"]


def test_sin_bandera_no_hay_recuperacion_ni_red():
    import urllib.request

    def explota(*_args, **_kwargs):
        raise AssertionError("la auditoría no debe abrir la red")

    original = urllib.request.urlopen
    urllib.request.urlopen = explota
    try:
        os.environ.pop("COPILOT_CATALOG_RETRIEVAL", None)
        informe = auditar_superficies_copilot(
            "En Copilot, abre el agente Researcher.",
            fetcher=explota,
            recuperar=False,
        )
        assert informe["ok"], informe["hallazgos"]
        assert informe["retrieval_aplicada"] is False
    finally:
        urllib.request.urlopen = original


def test_la_recuperacion_inyectada_retira_o_confirma_sin_red():
    catalogo = cargar_catalogo()

    def pagina(url):
        if url.endswith("researcher-agent"):
            return "<html>Researcher is deprecated and was retired from Copilot.</html>"
        if "analyst" in url:
            return "<html>This page moved. Nothing about the old name remains.</html>"
        if "agent-builder" in url or "plugins/agent-builder" in url:
            raise TimeoutError("docs caidos")
        return f"<html>{url} Agent Builder Researcher Analyst Plan My Day Workflows Frontier</html>"

    ajustado = aplicar_recuperacion(catalogo, pagina)
    por_id = {f["id"]: f for f in ajustado["features"]}
    assert por_id["researcher"]["status"] == "deprecated"
    assert por_id["analyst"]["status"] == "unresolved"
    assert por_id["agent-builder"]["status"] == "available"
    assert por_id["agent-builder"]["retrieval"]["ok"] is False
    assert ajustado["retrieval_aplicada"] is True
    # The checked-in catalog object is not mutated.
    original = {f["id"]: f["status"] for f in cargar_catalogo()["features"]}
    assert original["researcher"] == "available"
    assert original["analyst"] == "available"

    retiro = auditar_superficies_copilot(
        "En Copilot, abre el agente Researcher.",
        fetcher=pagina,
        recuperar=True,
    )
    assert not retiro["ok"]
    assert any(h["id"] == "researcher" and h["tipo"] == "deprecated" for h in retiro["hallazgos"])

    perdida = auditar_superficies_copilot(
        "En Copilot, abre el agente Analyst.",
        fetcher=pagina,
        recuperar=True,
    )
    assert not perdida["ok"]
    assert any(h["id"] == "analyst" and h["tipo"] == "unknown" for h in perdida["hallazgos"])


def test_el_prompt_vivo_incluye_el_catalogo_y_la_correccion():
    modulo = _cargar_writer()
    prompt = modulo._compact_single_lab_prompt(
        {
            "lab_id": "02-01-01",
            "lab_title": "Agentes de Copilot",
            "objectives": ["Usar Researcher"],
        },
        {"target_language": "Spanish (Español)"},
        "",
        "resumen",
    )
    assert "2026-11-25.1" in prompt
    assert "Plan My Day" in prompt
    assert "Bing Chat Enterprise" in prompt
    assert "Workflows" in prompt
    assert "[POR CONFIRMAR]" in prompt

    correccion = mensaje_de_correccion_moneda(
        [
            {
                "nombre": "Magic Scheduler",
                "tipo": "unknown",
                "bloquea": True,
            }
        ]
    )
    prompt_reintento = modulo._compact_single_lab_prompt(
        {
            "lab_id": "02-01-01",
            "lab_title": "Agentes de Copilot",
            "objectives": ["Usar Researcher"],
        },
        {
            "target_language": "Spanish (Español)",
            "currency_correction": correccion,
        },
        "",
        "resumen",
    )
    assert "CORRECCIÓN OBLIGATORIA (moneda de Microsoft 365 Copilot)" in prompt_reintento
    assert "Magic Scheduler" in prompt_reintento


_LAB_LIMPIO = """# Lab 01-01-01: Agentes de Copilot

## Descripcion General
En Microsoft 365 Copilot, abre el agente Researcher y pide un informe con citas.

### Paso 1: Abrir el agente
**Objective:** Abrir Researcher.
**Instructions:**
1. En Copilot, selecciona el agente Researcher.
**Expected output:** El agente responde con un informe citado.
**Verification:** El informe muestra las fuentes.
"""

_LAB_INVENTADO = """# Lab 01-01-01: Agentes de Copilot

## Descripcion General
En Copilot, abre el agente Magic Scheduler.

### Paso 1: Abrir el agente
**Objective:** Abrir el agente.
**Instructions:**
1. En Copilot, selecciona el agente Magic Scheduler.
**Expected output:** El agente responde.
**Verification:** Hay una respuesta en el chat.
"""

_LAB_BING = """# Lab 01-01-01: Chat empresarial

## Descripcion General
Abre Bing Chat Enterprise y pregunta por la política.

### Paso 1: Entrar
**Objective:** Abrir el chat.
**Instructions:**
1. Abre Bing Chat Enterprise.
**Expected output:** Aparece el cuadro de chat.
**Verification:** El cuadro acepta la pregunta.
"""


class _Cuerpo:
    def __init__(self, texto):
        self._texto = texto if isinstance(texto, str) else texto.decode("utf-8")

    def read(self):
        return self._texto.encode("utf-8")


class _S3:
    def __init__(self, objetos=None):
        self.objetos = dict(objetos or {})

    def get_object(self, Bucket=None, Key=None):
        if Key not in self.objetos:
            raise KeyError(Key)
        return {"Body": _Cuerpo(self.objetos[Key])}

    def put_object(self, **kwargs):
        cuerpo = kwargs.get("Body", "")
        if isinstance(cuerpo, bytes):
            cuerpo = cuerpo.decode("utf-8")
        self.objetos[kwargs.get("Key")] = cuerpo
        return {}


def _cargar_writer():
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", "strands_lab_writer")
    previos = {n: sys.modules.get(n) for n in nombres}

    class _ClientError(Exception):
        def __init__(self, *args, **kwargs):
            self.response = {"Error": {"Code": "NoSuchKey"}}

    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: types.SimpleNamespace()
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
    sys.modules.pop("strands_lab_writer", None)
    if _CARPETA not in sys.path:
        sys.path.insert(0, _CARPETA)
    import importlib

    modulo = importlib.import_module("strands_lab_writer")
    for clave, previo in previos.items():
        if clave == "strands_lab_writer":
            continue
        if previo is None:
            sys.modules.pop(clave, None)
        else:
            sys.modules[clave] = previo
    return modulo


def _ejecutar(contenidos, manual="Manual del curso, sin agentes inventados.", intentos=3, moneda="1"):
    modulo = _cargar_writer()
    s3 = _S3(
        {
            "p/outline.yaml": "course:\n  title: Copilot\n",
            "p/manual.txt": manual,
        }
    )
    modulo.s3_client = s3
    modulo.MAX_LAB_GENERATION_ATTEMPTS = intentos
    os.environ["CURRENCY_RETRY"] = moneda
    os.environ.pop("COPILOT_CATALOG_RETRIEVAL", None)
    contextos = []

    def generar(lab_plans, master_context, model_provider="bedrock", lesson_content="", previous_lab_context=""):
        contextos.append(dict(master_context))
        indice = min(len(contextos), len(contenidos)) - 1
        return {lab_plans[0]["lab_id"]: contenidos[indice]}

    modulo.generate_all_labs_batch = generar
    modulo._verify_and_refine_lab_guide = lambda guide, plan_, ctx, model_provider="bedrock": guide
    modulo._finalize_lab_markdown = lambda markdown, is_demo, is_spanish=True: markdown
    modulo.load_master_plan_from_s3 = lambda bucket, key: {
        "lab_plans": [
            {
                "lab_id": "01-01-01",
                "lab_title": "Agentes de Copilot",
                "objectives": ["Usar un agente"],
                "estimated_duration": 30,
            }
        ]
    }
    modulo.save_lab_guide_to_s3 = lambda **kw: f"p/labguide/lab-{kw['lab_id']}.md"
    modulo._lab_skip_if_exists_enabled = lambda: False
    modulo._find_existing_lab_guide_key = lambda bucket, project, lab_id: None

    try:
        resultado = modulo.lambda_handler(
            {
                "course_bucket": "bucket",
                "master_plan_key": "p/labguide/lab-master-plan.json",
                "project_folder": "p",
                "outline_s3_key": "p/outline.yaml",
                "manual_text_s3_key": "p/manual.txt",
                "lab_ids": ["01-01-01"],
                "lab_lesson_keys": {},
            },
            None,
        )
        error = None
    except Exception as exc:  # noqa: BLE001 - the handler is expected to raise on a blocked lab
        resultado = None
        error = exc
    finally:
        os.environ.pop("CURRENCY_RETRY", None)
    return resultado, error, contextos, s3


def test_el_writer_reintenta_un_agente_inventado_y_acepta_el_catalogo():
    resultado, error, contextos, _s3 = _ejecutar(
        [_LAB_INVENTADO, _LAB_LIMPIO],
        intentos=3,
    )
    assert error is None, error
    assert resultado["statusCode"] == 200
    assert len(contextos) == 2
    assert "Magic Scheduler" in (contextos[1].get("currency_correction") or "")
    assert not contextos[0].get("currency_correction")


def test_el_writer_falla_el_lab_si_el_nombre_retirado_sigue_ahi():
    """Last attempt still blocks. The third text is not saved."""
    resultado, error, contextos, s3 = _ejecutar([_LAB_BING, _LAB_BING], intentos=2)
    assert resultado is None
    assert error is not None
    assert "C6 currency check failed" in str(error)
    assert len(contextos) == 2
    informe = json.loads(s3.objetos["p/validation/copilot-currency.json"])
    assert informe["ok"] is False
    assert informe["total_bloqueos"] >= 1
    assert informe["catalog_version"] == "2026-11-25.1"
    hallazgos = informe["por_laboratorio"]["01-01-01"]["hallazgos"]
    assert any(h["nombre"] == "Bing Chat Enterprise" and h["bloquea"] for h in hallazgos)


def test_currency_retry_apagado_solo_registra():
    resultado, error, _contextos, s3 = _ejecutar([_LAB_INVENTADO], intentos=1, moneda="0")
    assert error is None, error
    assert resultado["statusCode"] == 200
    informe = json.loads(s3.objetos["p/validation/copilot-currency.json"])
    assert informe["ok"] is False
    assert informe["total_bloqueos"] >= 1


def test_el_prompt_en_ingles_tambien_nombra_el_catalogo():
    texto = texto_de_catalogo_para_prompt(False)
    assert "HARD REQUIREMENT" in texto
    assert "Researcher" in texto
    assert "Power Virtual Agents" in texto


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
    if fallos:
        import traceback

        for nombre, exc in fallos:
            print(f"\n--- {nombre} ---")
            traceback.print_exception(type(exc), exc, exc.__traceback__)
    sys.exit(1 if fallos else 0)
