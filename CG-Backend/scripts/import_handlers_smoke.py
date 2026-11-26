#!/usr/bin/env python3
"""Import every Python Lambda handler from a SAM build directory.

Run after ``sam build`` and before ``sam deploy``. An ImportError aborts the
deploy. The script does not call AWS or a model. Layers that ``sam build``
materialized next to the functions are put on ``PYTHONPATH``.

Usage:
    python scripts/import_handlers_smoke.py --build .aws-sam/build
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

try:
    import yaml
except ImportError:  # The SAM template is a small YAML subset when PyYAML is absent.
    yaml = None


def _cargar_plantilla(ruta: str) -> dict:
    texto = open(ruta, encoding="utf-8").read()
    if yaml is not None:
        return yaml.safe_load(texto) or {}
    raise RuntimeError("PyYAML is required to read the SAM template")


def _capas_locales(build_dir: str) -> list:
    """Directories sam build wrote for layers: ``<layer>/python`` or the layer root."""
    capas = []
    if not os.path.isdir(build_dir):
        return capas
    for nombre in sorted(os.listdir(build_dir)):
        raiz = os.path.join(build_dir, nombre)
        if not os.path.isdir(raiz):
            continue
        python_dir = os.path.join(raiz, "python")
        if os.path.isdir(python_dir):
            capas.append(python_dir)
    return capas


def funciones_python(plantilla: dict) -> list:
    """``(logical_id, handler_module, code_uri)`` for Python functions."""
    recursos = (plantilla or {}).get("Resources") or {}
    encontradas = []
    for logical_id, recurso in recursos.items():
        if not isinstance(recurso, dict):
            continue
        tipo = str(recurso.get("Type") or "")
        if tipo not in ("AWS::Serverless::Function", "AWS::Lambda::Function"):
            continue
        props = recurso.get("Properties") or {}
        handler = str(props.get("Handler") or "")
        runtime = str(props.get("Runtime") or "python3.11").lower()
        if "python" not in runtime or "." not in handler:
            continue
        modulo = handler.split(".", 1)[0]
        code_uri = props.get("CodeUri") or "."
        encontradas.append((logical_id, modulo, str(code_uri)))
    return encontradas


def revisar_build(build_dir: str, ejecutable: str = sys.executable) -> list:
    """Import each handler in a fresh interpreter. Return human-readable failures."""
    plantilla = os.path.join(build_dir, "template.yaml")
    if not os.path.isfile(plantilla):
        return [f"SAM template not found: {plantilla}"]
    funciones = funciones_python(_cargar_plantilla(plantilla))
    if not funciones:
        return [f"No Python functions in {plantilla}"]
    capas = _capas_locales(build_dir)
    fallos = []
    for logical_id, modulo, code_uri in funciones:
        carpeta = code_uri if os.path.isabs(code_uri) else os.path.join(build_dir, code_uri)
        if not os.path.isdir(carpeta):
            fallos.append(f"{logical_id}: CodeUri is not a directory: {carpeta}")
            continue
        pythonpath = os.pathsep.join([carpeta, *capas])
        entorno = os.environ.copy()
        previo = entorno.get("PYTHONPATH")
        entorno["PYTHONPATH"] = pythonpath if not previo else pythonpath + os.pathsep + previo
        entorno.setdefault("AWS_DEFAULT_REGION", "us-east-1")
        entorno.setdefault("AWS_EC2_METADATA_DISABLED", "true")
        comando = [ejecutable, "-c", f"import {modulo}"]
        resultado = subprocess.run(
            comando,
            env=entorno,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if resultado.returncode != 0:
            detalle = (resultado.stderr or resultado.stdout or "").strip().splitlines()
            cola = detalle[-8:] if detalle else ["import failed"]
            fallos.append(f"{logical_id}: import {modulo} failed\n" + "\n".join(cola))
    return fallos


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", default=os.path.join(".aws-sam", "build"))
    args = parser.parse_args(argv)
    fallos = revisar_build(os.path.abspath(args.build))
    if fallos:
        print("Import smoke failed. Deploy aborted.", file=sys.stderr)
        for fallo in fallos:
            print(fallo, file=sys.stderr)
            print("---", file=sys.stderr)
        return 1
    print(f"Import smoke passed: {args.build}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
