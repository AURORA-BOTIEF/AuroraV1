# -*- coding: utf-8 -*-
"""Diff de manifiesto en la auditoría: register de la actualización selectiva."""

import io
import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def _cargar_modulo(nombre, carpeta):
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", nombre)
    previos = {n: sys.modules.get(n) for n in nombres}

    class _ClientError(Exception):
        pass

    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: object()
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
        claves = [c for c in self.objetos if c.startswith(Prefix)]
        yield {"Contents": [{"Key": c, "Size": len(self.objetos[c])} for c in claves]}


class _Cuerpo:
    def __init__(self, bytes_data):
        self._bytes = bytes_data

    def read(self):
        return self._bytes


class _S3Simulado:
    def __init__(self, objetos=None):
        self.objetos = dict(objetos or {})

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objetos[Key])}

    def get_paginator(self, nombre):
        return _Paginador(self.objetos)

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objetos[Key] = Body


import hashlib


def _sha(body_bytes):
    return hashlib.sha256(body_bytes).hexdigest()


def _modulo_con(objetos):
    modulo = _cargar_modulo(
        "post_generation_audit", os.path.join("lambda", "post_generation_audit")
    )
    modulo.s3 = _S3Simulado(objetos)
    return modulo


def test_la_actualizacion_registra_el_en_diff():
    cuerpo_previo = {
        "version": 1,
        "generated_at": "2026-10-01T00:00:00+00:00",
        "project_folder": "p",
        "inputs": {"outline": [], "manual": []},
        "outputs": {
            "plan": [],
            "labs": [
                {
                    "key": "p/labguide/lab-01-00-01-a.md",
                    "sha256": _sha(b"# lab v1"),
                    "bytes": 8,
                },
                {
                    "key": "p/labguide/lab-01-00-02-b.md",
                    "sha256": _sha(b"# lab vigente"),
                    "bytes": 12,
                },
            ],
            "setup_guide": [{"key": "p/labguide/viejo.json", "sha256": _sha(b"t"), "bytes": 1}],
        },
    }
    nuevos_cuerpos = {
        "p/labguide/lab-01-00-01-a.md": b"# lab v2 actualizado",
        "p/labguide/lab-01-00-02-b.md": b"# lab vigente",
        "p/labguide/lab-master-plan.json": b'{"lab_plans": []}',
        "p/labguide/lab-01-00-03-nuevo.md": b"# lab nuevo",
        "p/labguide/inputs-manifest.json": json.dumps(cuerpo_previo).encode("utf-8"),
    }
    objetos = dict(nuevos_cuerpos)
    # filler for auditing listing
    objetos["p/outline/curso.yaml"] = b"course: {}"

    modulo = _modulo_con(objetos)
    respuesta = modulo.lambda_handler({"project_folder": "p", "update_mode": True}, None)
    assert respuesta["statusCode"] == 200, respuesta
    assert respuesta["updates_key"]
    diff = json.loads(modulo.s3.objetos["p/labguide/updates-manifest.json"].decode("utf-8"))
    claves_actualizadas = {e["key"] for e in diff["actualizados"]}
    claves_nuevas = {e["key"] for e in diff["nuevos"]}
    claves_no_tocadas = {e["key"] for e in diff["no_tocados"]}
    claves_eliminadas = {e["key"] for e in diff["eliminados"]}
    assert "p/labguide/lab-01-00-01-a.md" in claves_actualizadas, claves_actualizadas
    assert "p/labguide/lab-01-00-03-nuevo.md" in claves_nuevas, claves_nuevas
    assert "p/labguide/lab-01-00-02-b.md" in claves_no_tocadas, claves_no_tocadas
    assert "p/labguide/viejo.json" in claves_eliminadas, claves_eliminadas
    assert diff["resumen"]["actualizados"] >= 1 and diff["resumen"]["nuevos"] >= 1
    # El nuevo manifiesto queda para el proximo diff.



def test_sin_update_mode_no_escribe_diff():
    objetos = {
        "p/labguide/lab-01-00-01-a.md": b"# lab",
        "p/labguide/lab-master-plan.json": b'{"lab_plans": []}',
    }
    modulo = _modulo_con(objetos)
    respuesta = modulo.lambda_handler({"project_folder": "p"}, None)  # update_mode ausente
    assert respuesta["statusCode"] == 200
    assert not respuesta.get("updates_key")


def test_sin_previo_iguales():
    objetos = {
        "p/labguide/lab-01-00-01-a.md": b"# lab",
        "p/labguide/lab-master-plan.json": b'{"lab_plans": []}',
    }
    modulo = _modulo_con(objetos)
    respuesta = modulo.lambda_handler({"project_folder": "p", "update_mode": True}, None)
    # Sin manifiesto previo: no hay diff (no es una actualización sobre un manifest).
    assert respuesta["statusCode"] == 200, respuesta
    assert not respuesta.get("updates_key")


def test_diferencia_de_pares_de_hashes():
    modulo = _cargar_modulo("post_generation_audit", os.path.join("lambda", "post_generation_audit"))
    previo = {
        "inputs": {},
        "outputs": {
            "plan": [{"key": "p/labguide/plan.json", "sha256": "old", "bytes": 3}]
        },
    }
    nuevo = {
        "inputs": {},
        "outputs": {
            "plan": [{"key": "p/labguide/plan.json", "sha256": "new", "bytes": 3}]
        },
    }
    diff = modulo.diferencia_de_manifest(previo, nuevo)
    assert diff["resumen"] == {
        "actualizados": 1,
        "nuevos": 0,
        "no_tocados": 0,
        "eliminados": 0,
    }
    assert diff["actualizados"][0]["sha256_antes"] == "old"
    assert diff["actualizados"][0]["sha256_despues"] == "new"


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
            print(f"FALLO  {nombre}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
