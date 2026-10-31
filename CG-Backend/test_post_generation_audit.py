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
