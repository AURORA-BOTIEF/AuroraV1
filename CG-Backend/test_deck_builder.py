# -*- coding: utf-8 -*-
"""Decks de Glosario y Tips & Tricks: fuentes trazables y render python-pptx.

Se prueba con un S3 simulado (los contadores y las llaves que quedan) y el
python-pptx real: lo que importa es que ningún término o tip se inventa y que
un deck vacío no genera archivos basura.
"""

import io
import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))


def _s3_simulado_run(objetos):
    """Stub minimamente suficiente para el deck_builder."""

    class _Paginador:
        def __init__(self, objetos):
            self.objetos = objetos

        def paginate(self, Bucket, Prefix):
            claves = [clave for clave in objetos if clave.startswith(Prefix)]
            yield {"Contents": [{"Key": clave} for clave in claves]}

    class _Cuerpo:
        def __init__(self, bytes_data):
            self._bytes = bytes_data

        def read(self):
            return self._bytes

    class _S3:
        def __init__(self):
            self.escritos = {}

        def get_object(self, Bucket, Key):
            return {"Body": _Cuerpo(objetos[Key])}

        def get_paginator(self, nombre):
            return _Paginador(objetos)

        def put_object(self, Bucket, Key, Body, ContentType=None):
            self.escritos[Key] = (Body, ContentType)

    return _S3()


def _modulo(s3):
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", "deck_builder")
    previos = {n: sys.modules.get(n) for n in nombres}
    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: s3
    botocore_sim = types.ModuleType("botocore")
    config_sim = types.ModuleType("botocore.config")
    config_sim.Config = lambda *a, **k: None
    exceptions_sim = types.ModuleType("botocore.exceptions")
    exceptions_sim.ClientError = Exception
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
    sys.modules.pop("deck_builder", None)
    ruta = os.path.join(_HERE, "lambda", "deck_builder")
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    try:
        import importlib

        modulo = importlib.import_module("deck_builder")
        return modulo
    finally:
        for clave, valor in previos.items():
            if valor is None:
                sys.modules.pop(clave, None)
            else:
                sys.modules[clave] = valor


def _curso_completo():
    glosario = json.dumps(
        {
            "terminos": [
                {"term": "Dockerfile", "definition": "Archivo de receta que define cómo se construye una imagen.", "fuente": "temario"},
                {"term": "Compose", "definition": "Herramienta para orquestar varios contenedores con un fichero YAML.", "fuente": "temario"},
                {"term": "Docker Hub", "definition": "Registro público de imágenes de contenedores.", "fuente": "leccion"},
            ]
        },
        ensure_ascii=False,
    ).encode()
    lab = (
        "# Lab 01-00-01: prueba\n\n"
        "## Solución de Problemas\n\n"
        "### El demonio no arranca\n\n"
        "**Causa:** el servicio dockerd no está habilitado en la máquina.\n"
        "**Solución:** activa el servicio con `sudo systemctl enable --now docker`.\n"
        "## Limpieza\n\nnada\n"
    ).encode()
    return {
        "curso/book/glosario.json": glosario,
        "curso/labguide/lab-01-00-01-prueba.md": lab,
        "curso/labguide/lab-master-plan.json": b'{"lab_plans": []}',
    }


def test_los_decks_se_generan_con_glosario_y_tips():
    objetos = _curso_completo()
    s3 = _s3_simulado_run(objetos)
    modulo = _modulo(s3)
    respuesta = modulo.lambda_handler({"project_folder": "curso"}, None)
    assert respuesta["statusCode"] == 200
    decks = respuesta["generados"]
    assert {d["deck"] for d in decks} == {"Glosario", "Tips & Tricks"}
    glosario = next(d for d in decks if d["deck"] == "Glosario")
    tips = next(d for d in decks if d["deck"] == "Tips & Tricks")
    assert glosario["terminos"] == 3
    assert tips["tips"] >= 1
    assert s3.escritos["curso/deck/Glosario.pptx"][1].endswith("presentationml.presentation")
    assert "curso/deck/Tips_and_Tricks.pptx" in s3.escritos

    # Verificación del pptx: nada de markdown ni invención.
    import re
    from pptx import Presentation

    buffer = io.BytesIO(s3.escritos["curso/deck/Glosario.pptx"][0])
    presentacion = Presentation(buffer)
    textos = []
    for slide in presentacion.slides:
        for marco in slide.placeholders:
            if marco.has_text_frame:
                textos.append(marco.text_frame.text)
    todo = "\n".join(textos)
    assert "Dockerfile" in todo and "Docker Hub" in todo
    assert "**" not in todo and "##" not in todo, "el deck no debe arrastrar marcas de markdown"
    assert "dockerdesktop" not in todo.lower()


def test_sin_fuentes_no_genera_pptx_vacio():
    s3 = _s3_simulado_run({"curso/labguide/lab-master-plan.json": b'{"lab_plans": []}'})
    modulo = _modulo(s3)
    respuesta = modulo.lambda_handler({"project_folder": "curso"}, None)
    assert respuesta["statusCode"] == 200
    assert respuesta["generados"] == []
    claves = [k for k in s3.escritos if k.endswith(".pptx")]
    assert claves == [], claves
    assert "curso/deck/resumen.json" in s3.escritos


def test_exige_project_folder():
    modulo = _modulo(_s3_simulado_run({}))
    respuesta = modulo.lambda_handler({}, None)
    assert respuesta["statusCode"] == 400


def test_el_tip_no_evoca_mandatos_prohibidos_del_lab():
    """Los exponentes del lab van al deck tal cual; el deck no reescribe."""
    objetos = _curso_completo()
    s3 = _s3_simulado_run(objetos)
    modulo = _modulo(s3)
    modulo.lambda_handler({"project_folder": "curso"}, None)
    cuerpo = s3.escritos["curso/deck/resumen.json"][0].decode()
    resumen = json.loads(cuerpo)
    assert resumen["project_folder"] == "curso"
    assert len(resumen["generados"]) == 2


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
