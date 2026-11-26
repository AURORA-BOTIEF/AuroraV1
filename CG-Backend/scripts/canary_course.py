#!/usr/bin/env python3
"""Launch one small canary course. Not called by deploy.ps1.

Default is a dry run: it prints the execution input and exits 0. It does not
call AWS unless `--execute` is passed. `--execute` uploads a one-module
outline to S3 and starts the state machine; that is a paid run. Do not use
`--execute` from tests.

The start payload mirrors a real QA course from the testing environment:
`content_source=s3`, `outline_s3_key`, `lab_requirements` (empty string),
and the other root fields a real start sends. `--image-model` defaults to
`gpt-image-2`; pass `none` to skip images.

After the execution finishes, check the prefix with
`scripts/check_execution_artifacts.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# The script directory and the backend root stay importable when the file is
# launched from another working directory (python path would otherwise miss
# sibling modules such as check_execution_artifacts).
_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent
for _ruta in (_SCRIPTS, _BACKEND, _BACKEND / "lambda"):
    _texto = str(_ruta)
    if _texto not in sys.path:
        sys.path.insert(0, _texto)

# Same model the course form offers as OpenAI GPT Image 2. "none" skips images.
IMAGE_MODEL_POR_DEFECTO = "gpt-image-2"

# Root fields a real start always sends. Empty string or null is fine.
# Tasks that used to read the optional ones with `.$` now receive the whole
# state, so a missing optional key is not a States.Runtime on those tasks.
# Pass states still copy the keys when a real course sends them.
CAMPOS_DE_INICIO = (
    "allow_openai_fallback",
    "content_source",
    "content_type",
    "course_bucket",
    "course_duration_hours",
    "course_language",
    "course_topic",
    "image_model",
    "lab_ids_to_regenerate",
    "lab_requirements",
    "lesson_ids_to_update",
    "lesson_requirements",
    "lesson_to_generate",
    "manual_s3_keys",
    "manual_text_s3_key",
    "model_provider",
    "modules_to_generate",
    "outline_s3_key",
    "performance_mode",
    "project_folder",
    "request_timestamp",
    "total_modules",
    "update_mode",
    "user_email",
    "user_id",
)

# Mid-flow fields the state machine adds; the start payload must not need them.
CAMPOS_A_OMITIR_DEL_INICIO = {
    "quality_issues",
    "master_lab_plan_result",
    "provider_lock",
    "resume_from",
    "error",
    "batch_expansion",
    "lab_batch_expansion",
}

_OUTLINE_NOMBRE = "canary.yaml"
_OUTLINE_LOCAL = Path(__file__).with_name("canary_outline.yaml")

# States on the content_type=both path that read root input with JSONPath.
_ESTADOS_DE_INICIO = (
    "GenerateLabMasterPlan",
    "InvokeLabPlanner",
    "ExpandModulesToBatches",
    "BothTheoryAndLabsBranch",
    "PrepareNewCourseParams",
)


def clave_outline(proyecto: str) -> str:
    return f"{proyecto.strip('/')}/outline/{_OUTLINE_NOMBRE}"


def campos_requeridos_al_inicio(estados: dict) -> set:
    """Root `$.field` paths those states need before mid-flow results exist."""
    requeridos = set()
    for nombre in _ESTADOS_DE_INICIO:
        estado = estados.get(nombre) or {}
        # Only Parameters: ResultPath values are mid-flow outputs, not start input.
        _recoger_rutas(estado.get('Parameters') or {}, requeridos)
    return {campo for campo in requeridos if campo not in CAMPOS_A_OMITIR_DEL_INICIO}


def _recoger_rutas(nodo, requeridos: set) -> None:
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if isinstance(valor, str) and valor.startswith("$.") and "." not in valor[2:] and "[" not in valor:
                requeridos.add(valor[2:])
            else:
                _recoger_rutas(valor, requeridos)
    elif isinstance(nodo, list):
        for item in nodo:
            _recoger_rutas(item, requeridos)


def entrada_canary(
    proyecto: str,
    correo: str,
    idioma: str = "es",
    outline_s3_key: str | None = None,
    bucket: str | None = None,
    image_model: str = IMAGE_MODEL_POR_DEFECTO,
) -> dict:
    """One short module, theory and labs, Spanish, same fields as a QA start."""
    clave = outline_s3_key or clave_outline(proyecto)
    return {
        "course_topic": "Canary: Microsoft 365 Copilot Chat",
        "course_duration_hours": 1,
        "modules_to_generate": [1],
        "total_modules": 1,
        "lesson_to_generate": None,
        "performance_mode": "standard",
        "model_provider": "bedrock",
        "user_id": "thor-qa",
        "user_email": correo,
        "request_timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "content_source": "s3",
        "outline_s3_key": clave,
        "manual_s3_keys": None,
        "manual_text_s3_key": None,
        "course_bucket": bucket or os.getenv("COURSE_BUCKET", "crewai-course-artifacts"),
        "project_folder": proyecto,
        "allow_openai_fallback": True,
        "content_type": "both",
        "lab_requirements": "",
        "lesson_requirements": "",
        "lab_ids_to_regenerate": None,
        "course_language": idioma,
        "image_model": image_model or IMAGE_MODEL_POR_DEFECTO,
        "lesson_ids_to_update": None,
        "update_mode": False,
        "canary": True,
    }


def subir_outline(bucket: str, proyecto: str, ruta: Path | None = None) -> str:
    """Upload the bundled one-module outline. Returns the S3 key."""
    import boto3

    local = ruta or _OUTLINE_LOCAL
    if not local.is_file():
        raise FileNotFoundError(f"Canary outline not found: {local}")
    clave = clave_outline(proyecto)
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=clave,
        Body=local.read_bytes(),
        ContentType="text/yaml",
    )
    return clave


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Upload the outline and start the state machine. Paid.")
    parser.add_argument("--project", default="")
    parser.add_argument("--email", default=os.getenv("OWNER_ALERT_EMAIL", "juan.ossa@netec.com"))
    parser.add_argument("--state-machine-arn", default=os.getenv("STATE_MACHINE_ARN", ""))
    parser.add_argument("--bucket", default=os.getenv("COURSE_BUCKET", "crewai-course-artifacts"))
    parser.add_argument(
        "--image-model",
        default=IMAGE_MODEL_POR_DEFECTO,
        help="Image model for the start payload. Default gpt-image-2. Pass none to skip images.",
    )
    args = parser.parse_args(argv)
    proyecto = args.project or f"canary-{time.strftime('%Y%m%d-%H%M%S')}"
    cuerpo = entrada_canary(proyecto, args.email, bucket=args.bucket, image_model=args.image_model)
    print(json.dumps(cuerpo, ensure_ascii=False, indent=2))
    if not args.execute:
        print("Dry run. Pass --execute to upload the outline and start the state machine. This script is not part of deploy.")
        return 0
    if not args.state_machine_arn:
        print("STATE_MACHINE_ARN or --state-machine-arn is required with --execute", file=sys.stderr)
        return 1
    clave = subir_outline(args.bucket, proyecto)
    if clave != cuerpo["outline_s3_key"]:
        cuerpo["outline_s3_key"] = clave
    import boto3

    cliente = boto3.client("stepfunctions")
    respuesta = cliente.start_execution(
        stateMachineArn=args.state_machine_arn,
        name=proyecto[:80],
        input=json.dumps(cuerpo),
    )
    print(respuesta.get("executionArn", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
