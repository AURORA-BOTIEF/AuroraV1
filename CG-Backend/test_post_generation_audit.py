"""Pruebas de la auditoría posterior: manifiesto con hash y enlaces.

Se ejecuta después de la Setup Guide y escribe dos artefactos. Aquí se prueba con
un S3 simulado: lo que se verifica es la clasificación, el hash y el filtro de
enlaces, no la red.
"""

import hashlib
import io
import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))


def _cargar_modulo(nombre, carpeta):
    """Importa el módulo Lambda con boto3 simulado: sin AWS ni credenciales."""
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", nombre)
    previos = {n: sys.modules.get(n) for n in nombres}

    class _ClientErrorSimulado(Exception):
        pass

    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: object()
    botocore_sim = types.ModuleType("botocore")
    config_sim = types.ModuleType("botocore.config")
    config_sim.Config = lambda *a, **k: None
    exceptions_sim = types.ModuleType("botocore.exceptions")
    exceptions_sim.ClientError = _ClientErrorSimulado
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
    sys.modules.pop(nombre, None)

    ruta = os.path.join(_HERE, carpeta)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    try:
        import importlib

        return importlib.import_module(nombre)
    finally:
        for clave, valor in previos.items():
            if valor is None:
                sys.modules.pop(clave, None)
            else:
                sys.modules[clave] = valor


class _Paginador:
    def __init__(self, objetos):
        self.objetos = objetos

    def paginate(self, Bucket, Prefix):
        claves = [clave for clave in self.objetos if clave.startswith(Prefix)]
        yield {"Contents": [{"Key": clave} for clave in claves]}


class _S3Simulado:
    def __init__(self, objetos=None):
        self.objetos = dict(objetos or {})

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objetos[Key])}

    def get_paginator(self, nombre):
        return _Paginador(self.objetos)

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objetos[Key] = Body


def _modulo():
    return _cargar_modulo(
        "post_generation_audit", os.path.join("lambda", "post_generation_audit")
    )


def test_el_manifiesto_hashea_entradas_y_salidas():
    modulo = _modulo()
    s3 = _S3Simulado(
        {
            "curso/outline/temario.yaml": b"course:\n  title: Curso\n",
            "curso/labguide/manual.txt": b"manual",
            "curso/labguide/lab-master-plan.json": b'{"lab_plans": []}',
            "curso/labguide/lab-01-00-01-alta.md": b"# Lab 1",
            "curso/labguide/lab-01-00-02-baja.md": b"# Lab 2",
            "curso/setupguide/setup-guide.json": b"{}",
            "curso/setupguide/Setup_Guide.pdf": b"%PDF",
        }
    )
    modulo.s3 = s3

    manifiesto = modulo.construir_manifest("bucket", "curso")

    assert manifiesto["version"] == 1
    assert len(manifiesto["inputs"]["outline"]) == 1
    assert len(manifiesto["inputs"]["manual"]) == 1
    assert len(manifiesto["outputs"]["plan"]) == 1
    assert len(manifiesto["outputs"]["labs"]) == 2
    assert len(manifiesto["outputs"]["setup_guide"]) == 2
    esperado = hashlib.sha256(b"# Lab 1").hexdigest()
    assert manifiesto["outputs"]["labs"][0]["sha256"] in (esperado, hashlib.sha256(b"# Lab 2").hexdigest())
    assert len(manifiesto["outputs"]["labs"][0]["sha256"]) == 64
    assert "request" not in manifiesto["inputs"]


def test_el_filtro_descarta_lo_que_no_es_un_enlace_navegable():
    modulo = _modulo()
    descartados = [
        "http://10.10.10.100/",
        "https://192.168.56.20:8080/health",
        "http://localhost:8080",
        "http://schema-registry:8081",
        "http://es01:9200",
        "https://kubernetes.default.svc",
        "https://example.com/x",
        "https://api.ventas.ejemplo/v1/extract",
        "http://maven.apache.org/POM/4.0.0",
        "http://schemas.android.com/apk/res/android",
        "https://fonts.googleapis.com",
        "https://tu-usuario.github.io/landing-curso/",
        "https://github.com/usuario/repo.git",
        "http://$(minikube ip):8080",
        "https://labagentes[N",
    ]
    for url in descartados:
        host, motivo = modulo.es_enlace_publico(url)
        assert host is None, (url, motivo)


def test_el_filtro_acepta_un_enlace_publico():
    modulo = _modulo()
    host, motivo = modulo.es_enlace_publico("https://learn.microsoft.com/es-es/copilot/")
    assert host == "learn.microsoft.com", motivo
    assert motivo == ""


def test_urls_de_limpia_el_enfasis_y_la_puntuacion():
    modulo = _modulo()
    texto = "Ver **https://learn.microsoft.com/x**, y (https://owasp.org/y)."
    assert list(modulo.urls_de(texto)) == [
        "https://learn.microsoft.com/x",
        "https://owasp.org/y",
    ]


def test_urls_de_descarta_plantillas_con_marcador():
    modulo = _modulo()
    texto = (
        "Ver https://hub.docker.com/r/<usuario>/app/tags y "
        "https://hub.docker.com/r/\\<usuario\\>/app/tags."
    )
    assert list(modulo.urls_de(texto)) == []
    assert list(modulo.urls_de("<https://owasp.org/x>")) == ["https://owasp.org/x"]


def test_revisar_enlaces_no_repite_urls_y_agrupa_los_labs():
    modulo = _modulo()
    s3 = _S3Simulado(
        {
            "curso/labguide/lab-01-00-01-a.md": b"Ver https://owasp.org/x y https://owasp.org/x",
            "curso/labguide/lab-01-00-02-b.md": b"Ver https://owasp.org/x",
            "curso/labguide/lab-02-00-01-c.md": b"Ver https://learn.microsoft.com/y",
        }
    )
    modulo.s3 = s3
    respuestas = {
        "https://owasp.org/x": ("muerto", 404),
        "https://learn.microsoft.com/y": ("vivo", 200),
    }
    modulo.revisar_enlace = lambda url: respuestas[url]

    informe = modulo.revisar_enlaces("bucket", "curso")

    assert informe["resumen"] == {
        "publicos": 2,
        "vivos": 1,
        "muertos": 1,
        "no_verificables": 0,
    }
    assert informe["muertos"][0]["url"] == "https://owasp.org/x"
    assert informe["muertos"][0]["labs"] == ["lab-01-00-01-a.md", "lab-01-00-02-b.md"]


def test_el_handler_escribe_los_dos_artefactos():
    modulo = _modulo()
    s3 = _S3Simulado(
        {
            "curso/outline/temario.yaml": b"course: {}",
            "curso/labguide/lab-master-plan.json": b"{}",
            "curso/labguide/lab-01-00-01-a.md": b"# Lab",
        }
    )
    modulo.s3 = s3
    modulo.revisar_enlaces = lambda bucket, proyecto: {
        "resumen": {"publicos": 0, "vivos": 0, "muertos": 0, "no_verificables": 0},
        "muertos": [],
        "no_verificables": [],
    }

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["statusCode"] == 200
    assert respuesta["manifest_key"] == "curso/labguide/inputs-manifest.json"
    assert respuesta["enlaces_key"] == "curso/labguide/enlaces.json"
    manifiesto = json.loads(s3.objetos["curso/labguide/inputs-manifest.json"])
    assert manifiesto["project_folder"] == "curso"
    assert "curso/labguide/enlaces.json" in s3.objetos


def test_el_handler_exige_project_folder():
    modulo = _modulo()
    respuesta = modulo.lambda_handler({}, None)
    assert respuesta["statusCode"] == 400


def test_la_compuerta_viene_apagada():
    """The handler default does not set bloquea. Dead links stay in the report."""
    modulo = _modulo()
    anterior = os.environ.pop("LINK_AUDIT_GATE", None)
    try:
        informe = {"resumen": {"publicos": 1, "vivos": 0, "muertos": 1, "no_verificables": 0}}
        apagada = modulo.compuerta_de_enlaces(informe)
    finally:
        if anterior is not None:
            os.environ["LINK_AUDIT_GATE"] = anterior
    assert apagada["bloquea"] is False
    assert apagada["activa"] is False
    assert apagada["muertos"] == 1


def test_la_compuerta_bloquea_solo_enlaces_muertos():
    """A moved Learn page (404) fails the course. 403 stays a report."""
    modulo = _modulo()
    muerto = {
        "resumen": {"publicos": 2, "vivos": 0, "muertos": 1, "no_verificables": 1},
    }
    sano = {
        "resumen": {"publicos": 2, "vivos": 1, "muertos": 0, "no_verificables": 1},
    }
    assert modulo.compuerta_de_enlaces(muerto, activa=True)["bloquea"] is True
    assert modulo.compuerta_de_enlaces(muerto, activa=True)["motivo"] == "enlaces_muertos"
    assert modulo.compuerta_de_enlaces(sano, activa=True)["bloquea"] is False
    apagada = modulo.compuerta_de_enlaces(muerto, activa=False)
    assert apagada["bloquea"] is False
    assert apagada["muertos"] == 1


def _con_compuerta(encendida):
    anterior = os.environ.get("LINK_AUDIT_GATE")
    os.environ["LINK_AUDIT_GATE"] = "1" if encendida else "0"
    return anterior


def _restaurar_compuerta(anterior):
    if anterior is None:
        os.environ.pop("LINK_AUDIT_GATE", None)
    else:
        os.environ["LINK_AUDIT_GATE"] = anterior


def test_el_handler_marca_la_compuerta_sin_fallar_la_lambda():
    """Dead links set gate.bloquea and still return 200 so the report is kept.

    Step Functions reads the payload. Raising here would hit Catch and the
    course would succeed without a gate.
    """
    modulo = _modulo()
    s3 = _S3Simulado(
        {"curso/labguide/lab-01-00-01-a.md": b"Ver https://learn.microsoft.com/old"}
    )
    modulo.s3 = s3
    # The gate test mocks the audit report. Repair still asks the checker
    # whether a catalog URL is alive, so the checker stays injected.
    modulo.revisar_enlace = lambda url: ("muerto", 404)
    modulo.revisar_enlaces = lambda bucket, proyecto: {
        "resumen": {"publicos": 1, "vivos": 0, "muertos": 1, "no_verificables": 0},
        "muertos": [
            {
                "url": "https://learn.microsoft.com/old",
                "estado": 404,
                "labs": ["lab-01-00-01-a.md"],
            }
        ],
        "no_verificables": [],
    }

    anterior = _con_compuerta(True)
    try:
        respuesta = modulo.lambda_handler(
            {"project_folder": "curso", "course_bucket": "bucket"}, None
        )
    finally:
        _restaurar_compuerta(anterior)

    assert respuesta["statusCode"] == 200, respuesta
    assert respuesta["gate"]["bloquea"] is True
    assert respuesta["gate"]["muertos"] == 1
    informe = json.loads(s3.objetos["curso/labguide/enlaces.json"])
    assert informe["gate"]["bloquea"] is True
    assert informe["muertos"][0]["estado"] == 404


_URL_CHAT_INVENTADA = (
    "https://learn.microsoft.com/es-es/copilot/microsoft-365/microsoft-365-copilot-chat"
)
_URL_CHAT_CATALOGO = (
    "https://support.microsoft.com/en-us/microsoft-365-copilot/"
    "get-started-with-microsoft-365-copilot-chat"
)
_URL_CHAT_MANUAL = (
    "https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-chat"
)
_URL_PRODUCTO = "https://learn.microsoft.com/en-us/copilot/plan/copilot-overview"
_URL_AGENT_BUILDER = "https://learn.microsoft.com/en-us/plugins/agent-builder-build-agents"
_URL_PROMPT = (
    "https://learn.microsoft.com/es-es/microsoft-365-copilot/"
    "microsoft-365-copilot-prompt-engineering"
)
_URL_ID_FALSO = (
    "https://support.microsoft.com/es-es/topic/"
    "bienvenido-a-microsoft-365-copilot-chat-5e2d3f57"
)
_URL_CHAT_SOPORTE = "https://support.microsoft.com/copilot-chat"
_URL_RECAP = "https://learn.microsoft.com/en-us/microsoftteams/meeting-recap"
_URL_RECAP_SOPORTE = (
    "https://support.microsoft.com/es-es/office/recapitular-una-reunion-en-microsoft-teams"
)
_URL_ONEDRIVE = "https://learn.microsoft.com/en-us/onedrive/onedrive-overview"
_URL_FINCEN = "https://www.fincen.gov/resources/statutes-and-regulations"


def _sin_red(modulo):
    def _urlopen(*_args, **_kwargs):
        raise AssertionError("offline test called urllib.request.urlopen")

    modulo.urllib.request.urlopen = _urlopen


def _checker(mapa):
    def revisar(url):
        return mapa.get(url, ("muerto", 404))

    return revisar


def _texto(s3, clave):
    valor = s3.objetos[clave]
    if isinstance(valor, bytes):
        return valor.decode("utf-8")
    return valor


def _catalogo_vivo(modulo):
    """Every checked-in doc URL answers 200. Dead URLs are whatever the test omits."""
    mapa = {}
    for feature in modulo._catalogo_copilot().get("features") or []:
        url = (feature.get("doc_url") or "").strip()
        if url:
            mapa[url] = ("vivo", 200)
    return _checker(mapa)


def test_el_catalogo_de_la_auditoria_es_el_del_writer():
    aqui = os.path.dirname(os.path.abspath(__file__))
    auditoria = os.path.join(
        aqui, "lambda", "post_generation_audit", "copilot_feature_catalog.json"
    )
    writer = os.path.join(
        aqui, "lambda", "strands_lab_writer", "copilot_feature_catalog.json"
    )
    with open(auditoria, "rb") as fichero:
        izquierda = fichero.read()
    with open(writer, "rb") as fichero:
        derecha = fichero.read()
    assert izquierda == derecha


def test_copilot_chat_inventado_puntuacion_del_catalogo():
    """The made-up Learn path ends in copilot-chat, so that catalog row wins."""
    modulo = _modulo()
    catalogo = modulo._catalogo_copilot()
    puntuaciones = []
    for feature in catalogo["features"]:
        if feature.get("status") == "deprecated":
            continue
        aliases = [modulo._tokens_de_frase(feature.get("canonical_name") or "")]
        aliases.extend(
            modulo._tokens_de_frase(alias) for alias in (feature.get("aliases") or [])
        )
        puntuaciones.append((
            modulo.puntuacion_de_reemplazo(
                _URL_CHAT_INVENTADA, feature.get("doc_url") or "", aliases, "Copilot Chat"
            ),
            feature["id"],
        ))
    puntuaciones.sort(reverse=True)
    assert puntuaciones[0][1] == "copilot-chat", puntuaciones[:3]
    assert puntuaciones[0][0] >= modulo._UMBRAL_REEMPLAZO
    por_id = {feature["id"]: feature["doc_url"] for feature in catalogo["features"]}
    assert por_id["copilot-chat"] == _URL_CHAT_CATALOGO
    assert "researcher-agent" not in por_id["copilot-chat"]
    manual = modulo.puntuacion_de_reemplazo(_URL_CHAT_INVENTADA, _URL_CHAT_MANUAL, [], "")
    assert manual > puntuaciones[0][0]


def test_un_enlace_muerto_se_cambia_por_el_del_catalogo_y_no_bloquea():
    modulo = _modulo()
    _sin_red(modulo)
    lab = (
        "# Lab\n\nConsulte [Copilot Chat]"
        f"({_URL_CHAT_INVENTADA}) y siga.\n"
    )
    s3 = _S3Simulado({"curso/labguide/lab-01-00-01-a.md": lab.encode("utf-8")})
    modulo.s3 = s3
    modulo.revisar_enlace = _checker({_URL_CHAT_CATALOGO: ("vivo", 200)})

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["statusCode"] == 200, respuesta
    assert respuesta["gate"]["bloquea"] is False
    assert respuesta["gate"]["muertos"] == 0
    texto = s3.objetos["curso/labguide/lab-01-00-01-a.md"]
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8")
    assert _URL_CHAT_INVENTADA not in texto
    assert _URL_CHAT_CATALOGO in texto
    assert "Copilot Chat" in texto
    informe = json.loads(s3.objetos["curso/labguide/enlaces.json"])
    assert informe["reparaciones"][0]["accion"] == "reemplazo"
    assert informe["reparaciones"][0]["reemplazo"] == _URL_CHAT_CATALOGO


def test_el_manual_vivo_gana_al_catalogo():
    modulo = _modulo()
    _sin_red(modulo)
    lab = f"Vea [Copilot Chat]({_URL_CHAT_INVENTADA}).\n"
    s3 = _S3Simulado({
        "curso/labguide/lab-01-00-01-a.md": lab.encode("utf-8"),
        "curso/outline/temario.yaml": f"doc: {_URL_CHAT_MANUAL}\n".encode("utf-8"),
        "curso/labguide/manual.txt": b"sin enlaces",
    })
    modulo.s3 = s3
    modulo.revisar_enlace = _checker({
        _URL_CHAT_CATALOGO: ("vivo", 200),
        _URL_CHAT_MANUAL: ("vivo", 200),
    })

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["gate"]["bloquea"] is False
    texto = s3.objetos["curso/labguide/lab-01-00-01-a.md"]
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8")
    assert _URL_CHAT_MANUAL in texto
    assert _URL_CHAT_CATALOGO not in texto


def test_sin_parecido_se_quita_el_enlace_y_se_queda_el_texto():
    modulo = _modulo()
    _sin_red(modulo)
    muerta = "https://owasp.org/pagina-inventada-sin-parecido"
    lab = (
        f"Consulte [la guía oficial]({muerta}) antes.\n"
        f"Tambien vea {muerta}.\n"
    )
    s3 = _S3Simulado({"curso/labguide/lab-02-00-01-b.md": lab.encode("utf-8")})
    modulo.s3 = s3
    modulo.revisar_enlace = _checker({})

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["gate"]["bloquea"] is False, respuesta
    texto = s3.objetos["curso/labguide/lab-02-00-01-b.md"]
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8")
    assert "http" not in texto
    assert "la guía oficial" in texto
    assert "pagina inventada sin parecido" in texto
    informe = json.loads(s3.objetos["curso/labguide/enlaces.json"])
    assert {item["accion"] for item in informe["reparaciones"]} == {"retirado"}


def test_si_el_reemplazo_sigue_muerto_la_compuerta_bloquea():
    """Repair runs once. A link that is dead on the second audit still blocks."""
    modulo = _modulo()
    _sin_red(modulo)
    veces = {"n": 0}

    def revisar(url):
        if url == _URL_CHAT_CATALOGO:
            veces["n"] += 1
            if veces["n"] == 1:
                return "vivo", 200
            return "muerto", 404
        return "muerto", 404

    lab = f"Consulte [Copilot Chat]({_URL_CHAT_INVENTADA}).\n"
    s3 = _S3Simulado({"curso/labguide/lab-01-00-01-a.md": lab.encode("utf-8")})
    modulo.s3 = s3
    modulo.revisar_enlace = revisar

    anterior = _con_compuerta(True)
    try:
        respuesta = modulo.lambda_handler(
            {"project_folder": "curso", "course_bucket": "bucket"}, None
        )
    finally:
        _restaurar_compuerta(anterior)

    assert respuesta["statusCode"] == 200, respuesta
    assert respuesta["gate"]["bloquea"] is True
    assert respuesta["gate"]["muertos"] >= 1
    texto = s3.objetos["curso/labguide/lab-01-00-01-a.md"]
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8")
    assert _URL_CHAT_CATALOGO in texto


def test_un_fallo_de_reparacion_no_salta_la_compuerta():
    modulo = _modulo()
    _sin_red(modulo)
    s3 = _S3Simulado({
        "curso/labguide/lab-01-00-01-a.md": f"Vea {_URL_CHAT_INVENTADA}\n".encode("utf-8")
    })
    modulo.s3 = s3
    modulo.revisar_enlace = _checker({})
    modulo.revisar_enlaces = lambda bucket, proyecto: {
        "resumen": {"publicos": 1, "vivos": 0, "muertos": 1, "no_verificables": 0},
        "muertos": [{"url": _URL_CHAT_INVENTADA, "estado": 404, "labs": ["lab-01-00-01-a.md"]}],
        "no_verificables": [],
    }

    def _rompe(*_args, **_kwargs):
        raise RuntimeError("repair broke")

    modulo.reparar_enlaces_muertos = _rompe
    anterior = _con_compuerta(True)
    try:
        respuesta = modulo.lambda_handler(
            {"project_folder": "curso", "course_bucket": "bucket"}, None
        )
    finally:
        _restaurar_compuerta(anterior)
    assert respuesta["statusCode"] == 200, respuesta
    assert respuesta["gate"]["bloquea"] is True


def test_link_repair_apagado_no_reescribe_y_bloquea():
    modulo = _modulo()
    _sin_red(modulo)
    anterior = os.environ.get("LINK_REPAIR")
    anterior_compuerta = _con_compuerta(True)
    os.environ["LINK_REPAIR"] = "0"
    try:
        lab = f"Consulte [Copilot Chat]({_URL_CHAT_INVENTADA}).\n"
        libro = f"# Lab Guide\n\n{lab}"
        s3 = _S3Simulado({
            "curso/labguide/lab-01-00-01-a.md": lab.encode("utf-8"),
            "curso/book/Lab_Guide_LabGuide_complete.md": libro.encode("utf-8"),
        })
        modulo.s3 = s3
        modulo.revisar_enlace = _checker({_URL_CHAT_CATALOGO: ("vivo", 200)})
        respuesta = modulo.lambda_handler(
            {"project_folder": "curso", "course_bucket": "bucket"}, None
        )
    finally:
        _restaurar_compuerta(anterior_compuerta)
        if anterior is None:
            os.environ.pop("LINK_REPAIR", None)
        else:
            os.environ["LINK_REPAIR"] = anterior

    assert respuesta["gate"]["bloquea"] is True
    texto = s3.objetos["curso/labguide/lab-01-00-01-a.md"]
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8")
    assert _URL_CHAT_INVENTADA in texto
    assert _URL_CHAT_INVENTADA in _texto(s3, "curso/book/Lab_Guide_LabGuide_complete.md")
    informe = json.loads(s3.objetos["curso/labguide/enlaces.json"])
    assert "reparaciones" not in informe


def test_las_urls_del_catalogo_son_learn_o_support():
    """The three bad targets from QA are gone. Every row is Learn or Support."""
    modulo = _modulo()
    catalogo = modulo._catalogo_copilot()
    assert catalogo["catalog_version"] == "2026-11-25.2"
    assert catalogo["doc_urls_checked_on"] == "2026-11-25"
    por_id = {feature["id"]: feature for feature in catalogo["features"]}
    assert por_id["microsoft-365-copilot"]["doc_url"] == _URL_PRODUCTO
    assert por_id["copilot-chat"]["doc_url"] == _URL_CHAT_CATALOGO
    assert por_id["copilot-studio"]["doc_url"] == (
        "https://learn.microsoft.com/en-us/microsoft-copilot-studio/"
        "fundamentals-what-is-copilot-studio"
    )
    assert por_id["agent-builder"]["doc_url"] == _URL_AGENT_BUILDER
    assert por_id["plan-my-day"]["doc_url"] == (
        "https://learn.microsoft.com/en-us/plugins/agent-template-plan-my-day"
    )
    assert por_id["bing-chat-enterprise"]["doc_url"] == _URL_PRODUCTO
    for feature in catalogo["features"]:
        url = feature["doc_url"]
        assert url.startswith("https://learn.microsoft.com/") or url.startswith(
            "https://support.microsoft.com/"
        ), feature["id"]
        assert "blogs.bing.com" not in url
        assert "power-virtual-agents-now-part" not in url


def test_la_coincidencia_tematica_exige_ruta_o_titulo():
    modulo = _modulo()
    titulo_chat = "Get started with Microsoft Copilot Chat"
    assert modulo.es_coincidencia_tematica(
        _URL_CHAT_INVENTADA, _URL_CHAT_CATALOGO, titulo_chat
    ) is True
    assert modulo.es_coincidencia_tematica(
        _URL_CHAT_SOPORTE, _URL_CHAT_CATALOGO, titulo_chat
    ) is True
    assert modulo.es_coincidencia_tematica(
        _URL_PROMPT, _URL_PRODUCTO, "What is Microsoft Copilot?"
    ) is False
    assert modulo.es_coincidencia_tematica(
        _URL_ID_FALSO, _URL_CHAT_CATALOGO, titulo_chat
    ) is False
    assert modulo.es_coincidencia_tematica(
        _URL_ONEDRIVE, _URL_PRODUCTO, "What is Microsoft Copilot?"
    ) is False
    assert modulo.es_coincidencia_tematica(
        "https://learn.microsoft.com/en-us/microsoft-365-copilot/agent-builder",
        _URL_AGENT_BUILDER,
        "Build agents in Agent Builder",
    ) is True


def _laboratorio_con(enlaces):
    lineas = ["# Lab\n"]
    for ancla, url in enlaces:
        lineas.append(f"Consulte [{ancla}]({url}).\n")
    return "".join(lineas)


def test_prompt_engineering_se_retira_aunque_el_producto_este_vivo():
    """A Microsoft 365 Copilot slug is not a reason to point at the product page."""
    modulo = _modulo()
    _sin_red(modulo)
    lab = _laboratorio_con([("ingeniería de prompts", _URL_PROMPT)])
    s3 = _S3Simulado({"curso/labguide/lab-01-00-01-a.md": lab.encode("utf-8")})
    modulo.s3 = s3
    modulo.revisar_enlace = _catalogo_vivo(modulo)

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["gate"]["bloquea"] is False, respuesta
    texto = _texto(s3, "curso/labguide/lab-01-00-01-a.md")
    assert _URL_PROMPT not in texto
    assert _URL_PRODUCTO not in texto
    assert "ingeniería de prompts" in texto
    assert "http" not in texto


def test_los_enlaces_muertos_de_qa_sin_tema_se_retiran():
    """Real dead links from the 25 Nov QA. None of these is the catalog page."""
    modulo = _modulo()
    _sin_red(modulo)
    prefijo = "https://learn.microsoft.com/en-us/microsoft-365-copilot/"
    quitar = [
        ("bienvenida", _URL_ID_FALSO),
        ("ingeniería de prompts", _URL_PROMPT),
        ("resumen de la reunión", _URL_RECAP),
        ("recapitular la reunión", _URL_RECAP_SOPORTE),
        ("buenas prácticas", prefijo + "best-practices"),
        ("agentes", prefijo + "agents"),
        ("instrucciones", prefijo + "instructions"),
        ("agentes de SharePoint", prefijo + "instructions/sharepoint-agents"),
        ("el chat", prefijo + "chat"),
        ("OneDrive", _URL_ONEDRIVE),
        ("estatutos", _URL_FINCEN),
    ]
    lab = _laboratorio_con(quitar)
    s3 = _S3Simulado({"curso/labguide/lab-03-00-01-qa.md": lab.encode("utf-8")})
    modulo.s3 = s3
    modulo.revisar_enlace = _catalogo_vivo(modulo)

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["gate"]["bloquea"] is False, respuesta
    texto = _texto(s3, "curso/labguide/lab-03-00-01-qa.md")
    assert "http" not in texto, texto
    for ancla, url in quitar:
        assert url not in texto
        assert ancla in texto
    informe = json.loads(s3.objetos["curso/labguide/enlaces.json"])
    assert {item["accion"] for item in informe["reparaciones"]} == {"retirado"}
    for url in (
        _URL_PRODUCTO,
        _URL_CHAT_CATALOGO,
        _URL_AGENT_BUILDER,
    ):
        assert url not in texto


def test_copilot_chat_y_agent_builder_si_coinciden_se_cambian():
    modulo = _modulo()
    _sin_red(modulo)
    muerta_builder = "https://learn.microsoft.com/en-us/microsoft-365-copilot/agent-builder"
    lab = _laboratorio_con([
        ("Copilot Chat", _URL_CHAT_SOPORTE),
        ("Agent Builder", muerta_builder),
    ])
    s3 = _S3Simulado({"curso/labguide/lab-01-00-01-a.md": lab.encode("utf-8")})
    modulo.s3 = s3
    modulo.revisar_enlace = _catalogo_vivo(modulo)

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["gate"]["bloquea"] is False, respuesta
    texto = _texto(s3, "curso/labguide/lab-01-00-01-a.md")
    assert _URL_CHAT_SOPORTE not in texto
    assert muerta_builder not in texto
    assert _URL_CHAT_CATALOGO in texto
    assert _URL_AGENT_BUILDER in texto
    assert "researcher-agent" not in texto
    informe = json.loads(s3.objetos["curso/labguide/enlaces.json"])
    assert {item["accion"] for item in informe["reparaciones"]} == {"reemplazo"}


def test_la_reparacion_escribe_el_mismo_cambio_en_el_libro():
    """The book is built before the repair. The delivered copy must match the labs."""
    modulo = _modulo()
    _sin_red(modulo)
    lab = _laboratorio_con([
        ("Copilot Chat", _URL_CHAT_INVENTADA),
        ("estatutos", _URL_FINCEN),
    ])
    libro = f"# Lab Guide\n\n## Lab 1: Demo\n\n{lab}\n"
    datos = {
        "metadata": {"title": "Lab Guide", "total_words": 3},
        "modules": [
            {
                "module_number": 1,
                "module_title": "Capítulo 1 - Laboratorios",
                "labs": [
                    {
                        "lab_number": 1,
                        "title": "Demo",
                        "content": lab,
                        "word_count": len(lab.split()),
                    }
                ],
            }
        ],
    }
    s3 = _S3Simulado({
        "curso/labguide/lab-01-00-01-a.md": lab.encode("utf-8"),
        "curso/book/Lab_Guide_LabGuide_complete.md": libro.encode("utf-8"),
        "curso/book/Lab_Guide_LabGuide_data.json": json.dumps(datos).encode("utf-8"),
    })
    modulo.s3 = s3
    modulo.revisar_enlace = _catalogo_vivo(modulo)

    respuesta = modulo.lambda_handler(
        {"project_folder": "curso", "course_bucket": "bucket"}, None
    )

    assert respuesta["gate"]["bloquea"] is False, respuesta
    lab_texto = _texto(s3, "curso/labguide/lab-01-00-01-a.md")
    libro_texto = _texto(s3, "curso/book/Lab_Guide_LabGuide_complete.md")
    libro_json = json.loads(s3.objetos["curso/book/Lab_Guide_LabGuide_data.json"])
    contenido = libro_json["modules"][0]["labs"][0]["content"]
    for texto in (lab_texto, libro_texto, contenido):
        assert _URL_CHAT_INVENTADA not in texto
        assert _URL_FINCEN not in texto
        assert _URL_CHAT_CATALOGO in texto
        assert "estatutos" in texto
        assert "Copilot Chat" in texto
    assert contenido == lab_texto
    assert libro_json["modules"][0]["labs"][0]["word_count"] == len(contenido.split())
    informe = json.loads(s3.objetos["curso/labguide/enlaces.json"])
    assert informe["libro"]["actualizado"] is True
    assert "curso/book/Lab_Guide_LabGuide_complete.md" in informe["libro"]["claves"]
    assert "curso/book/Lab_Guide_LabGuide_data.json" in informe["libro"]["claves"]


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
