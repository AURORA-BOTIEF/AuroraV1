#!/usr/bin/env python3
"""Launch one small canary course. Not called by deploy.ps1.

Default is a dry run: it prints the execution input and exits 0. It does not
call AWS unless ``--execute`` is passed. ``--execute`` starts the state machine
and is a paid run; do not use it from tests.

After the execution finishes, check the prefix with
``scripts/check_execution_artifacts.py``.

Resume only the labs that were placeholders:
    start a new execution with ``lab_ids_to_regenerate`` set to ``failed_lab_ids``
    from ``<project>/validation/quality-report.json`` and leave
    ``LAB_SKIP_IF_EXISTS=true`` (the template default). A lab file that contains
    ``AURORA_PLACEHOLDER_PENDING_REGENERATION`` is rewritten. Finished labs are reused.

Reliability target: 10 consecutive mixed courses, 100% delivered, and at least
90% with zero placeholders.
Daily QA budget in production: 2 full courses. The canary is the small extra
check after a deploy; it is not one of those two full courses.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def entrada_canary(proyecto: str, correo: str, idioma: str = "es") -> dict:
    """One short module, theory and labs, Spanish by default."""
    return {
        "content_type": "both",
        "content_source": "outline",
        "course_bucket": os.getenv("COURSE_BUCKET", "crewai-course-artifacts"),
        "course_language": idioma,
        "course_topic": "Canary: Microsoft 365 Copilot Chat",
        "course_duration_hours": 1,
        "project_folder": proyecto,
        "user_email": correo,
        "model_provider": "bedrock",
        "image_model": "none",
        "modules_to_generate": [1],
        "total_modules": 1,
        "update_mode": False,
        "lab_ids_to_regenerate": [],
        "lesson_ids_to_update": None,
        "performance_mode": "standard",
        "canary": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Start the state machine. Paid.")
    parser.add_argument("--project", default="")
    parser.add_argument("--email", default=os.getenv("OWNER_ALERT_EMAIL", "juan.ossa@netec.com"))
    parser.add_argument("--state-machine-arn", default=os.getenv("STATE_MACHINE_ARN", ""))
    args = parser.parse_args(argv)
    proyecto = args.project or f"canary-{time.strftime('%Y%m%d-%H%M%S')}"
    cuerpo = entrada_canary(proyecto, args.email)
    print(json.dumps(cuerpo, ensure_ascii=False, indent=2))
    if not args.execute:
        print("Dry run. Pass --execute to start the state machine. This script is not part of deploy.")
        return 0
    if not args.state_machine_arn:
        print("STATE_MACHINE_ARN or --state-machine-arn is required with --execute", file=sys.stderr)
        return 1
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
