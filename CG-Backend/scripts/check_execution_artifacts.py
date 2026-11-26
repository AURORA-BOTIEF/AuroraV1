#!/usr/bin/env python3
"""Check that one course execution left the deliverables in S3 or on disk.

Exit codes:
    0  labs, lab-guide book, a PPTX, and the Setup Guide PDF are present,
       and no lab file is a placeholder
    2  the same files exist, but at least one lab is a placeholder
    1  a required deliverable is missing

This does not start a course and does not call a model. Pass ``--local`` with
a directory laid out like the project prefix (``labguide/``, ``book/``,
``setupguide/``). Without ``--local`` it lists ``s3://bucket/project/``.

Reliability target: 10 consecutive mixed courses, 100% delivered, and at least
90% of them with zero placeholders. Daily QA budget in production: 2 full courses.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_TOKENS = Path(__file__).resolve().parents[1] / "lambda" / "setup_guide_builder"
if str(_TOKENS) not in sys.path:
    sys.path.insert(0, str(_TOKENS))

from template_tokens import tokens_en_objeto, tokens_en_texto

MARCA = "AURORA_PLACEHOLDER_PENDING_REGENERATION"


def _listar_local(raiz: str) -> list:
    hallados = []
    for carpeta, _dirs, archivos in os.walk(raiz):
        for nombre in archivos:
            ruta = os.path.join(carpeta, nombre)
            hallados.append(os.path.relpath(ruta, raiz).replace(os.sep, "/"))
    return hallados


def _leer_local(raiz: str, clave: str) -> str:
    ruta = os.path.join(raiz, *clave.split("/"))
    with open(ruta, encoding="utf-8", errors="replace") as fichero:
        return fichero.read()


def _listar_s3(bucket: str, proyecto: str):
    import boto3

    cliente = boto3.client("s3")
    prefijo = proyecto.strip("/") + "/"
    claves = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefijo}
        if token:
            kwargs["ContinuationToken"] = token
        pagina = cliente.list_objects_v2(**kwargs)
        for item in pagina.get("Contents") or []:
            claves.append(item["Key"][len(prefijo):])
        if not pagina.get("IsTruncated"):
            break
        token = pagina.get("NextContinuationToken")
    return claves, cliente, bucket, prefijo


def _es_leccion(clave: str) -> bool:
    return clave.endswith(".md") and ("/lessons/" in f"/{clave}" or clave.startswith("lessons/"))


def _tokens_de_archivo(clave: str, texto: str) -> list:
    """Setup JSON lists tokens that were neutralized. Other files are scanned raw."""
    if clave == "setupguide/setup-guide.json":
        try:
            documento = json.loads(texto)
        except json.JSONDecodeError:
            return tokens_en_texto(texto)
        if not isinstance(documento, dict):
            return tokens_en_texto(texto)
        declarados = []
        for item in documento.get("placeholders") or []:
            if isinstance(item, str) and item:
                declarados.append(item)
            elif isinstance(item, dict) and item.get("token"):
                declarados.append(str(item["token"]))
        return declarados + tokens_en_objeto(documento)
    if clave.startswith("labguide/") and clave.endswith(".md"):
        return tokens_en_texto(texto)
    if _es_leccion(clave):
        return tokens_en_texto(texto)
    return []


def evaluar(claves: list, leer) -> dict:
    """Classify one project prefix. ``leer(relative_key)`` returns text."""
    labs = [clave for clave in claves if clave.startswith("labguide/lab-") and clave.endswith(".md")]
    libros = [
        clave for clave in claves
        if clave.startswith("book/") and "LabGuide" in clave
    ]
    ppt = [clave for clave in claves if clave.lower().endswith(".pptx")]
    pdf = [clave for clave in claves if clave == "setupguide/Setup_Guide.pdf"]
    placeholders = []
    template_tokens = []
    for clave in claves:
        es_lab = clave in labs
        if not (es_lab or clave == "setupguide/setup-guide.json" or _es_leccion(clave)):
            continue
        try:
            texto = leer(clave)
        except OSError:
            continue
        if es_lab and MARCA in texto:
            placeholders.append(clave)
        template_tokens.extend(f"{clave}: {token}" for token in _tokens_de_archivo(clave, texto))
    placeholders.extend(template_tokens)
    faltan = []
    if not labs:
        faltan.append("labs")
    if not libros:
        faltan.append("lab guide book")
    if not ppt:
        faltan.append("PPT")
    if not pdf:
        faltan.append("Setup PDF")
    return {
        "labs": labs,
        "lab_guide_book": libros,
        "pptx": ppt,
        "setup_pdf": pdf,
        "placeholders": placeholders,
        "template_tokens": template_tokens,
        "missing": faltan,
        "delivered": not faltan,
    }


def codigo_de_salida(informe: dict) -> int:
    if informe["missing"]:
        return 1
    if informe["placeholders"]:
        return 2
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", help="Project directory instead of S3")
    parser.add_argument("--bucket", default=os.getenv("COURSE_BUCKET", "crewai-course-artifacts"))
    parser.add_argument("--project", help="S3 project prefix")
    args = parser.parse_args(argv)
    if args.local:
        claves = _listar_local(args.local)
        informe = evaluar(claves, lambda clave: _leer_local(args.local, clave))
    else:
        if not args.project:
            print("Pass --project or --local", file=sys.stderr)
            return 1
        claves, cliente, bucket, prefijo = _listar_s3(args.bucket, args.project)

        def leer(clave):
            objeto = cliente.get_object(Bucket=bucket, Key=prefijo + clave)
            return objeto["Body"].read().decode("utf-8", errors="replace")

        informe = evaluar(claves, leer)
    print(
        "delivered={delivered} labs={n_labs} book={n_book} ppt={n_ppt} "
        "pdf={n_pdf} placeholders={n_ph} missing={missing}".format(
            delivered=informe["delivered"],
            n_labs=len(informe["labs"]),
            n_book=len(informe["lab_guide_book"]),
            n_ppt=len(informe["pptx"]),
            n_pdf=len(informe["setup_pdf"]),
            n_ph=len(informe["placeholders"]),
            missing=",".join(informe["missing"]) or "none",
        )
    )
    return codigo_de_salida(informe)


if __name__ == "__main__":
    sys.exit(main())
