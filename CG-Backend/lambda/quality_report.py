"""Build the owner-facing quality report for one course execution.

The course is delivered either way. This report is what the owner reads.
"""

from __future__ import annotations

import json
from typing import Any, Optional


def _texto(valor: Any, limite: int = 4000) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        texto = valor
    else:
        try:
            texto = json.dumps(valor, ensure_ascii=False, default=str)
        except TypeError:
            texto = str(valor)
    return texto[:limite]


def _entrada(event: dict) -> dict:
    bruto = event.get("input") if isinstance(event, dict) else None
    if isinstance(bruto, dict):
        return bruto
    return event if isinstance(event, dict) else {}


def _issues_desde_objeto(quality_issues: Any) -> list:
    if not isinstance(quality_issues, dict):
        return []
    issues = []
    for clave, valor in quality_issues.items():
        if clave in ("ready",) and not isinstance(valor, dict):
            continue
        if isinstance(valor, dict):
            issues.append(
                {
                    "step": valor.get("step") or clave,
                    "error": _texto(valor.get("error") if "error" in valor else valor),
                    "severity": valor.get("severity") or "warning",
                    "deliverable": valor.get("deliverable") or "",
                }
            )
        elif valor not in (None, "", [], {}):
            issues.append(
                {
                    "step": clave,
                    "error": _texto(valor),
                    "severity": "warning",
                    "deliverable": "",
                }
            )
    return issues


def _anadir_si_falta(issues: list, step: str, error: Any, severity: str, deliverable: str = "") -> None:
    if error in (None, "", [], {}):
        return
    if any(item.get("step") == step for item in issues):
        return
    issues.append(
        {
            "step": step,
            "error": _texto(error),
            "severity": severity,
            "deliverable": deliverable,
        }
    )


def _cuerpo_setup(datos: dict) -> dict:
    """Read the Setup Guide payload. The Lambda body is a JSON string."""
    resultado = datos.get("setup_guide_result")
    if not isinstance(resultado, dict):
        return {}
    payload = resultado.get("Payload") if isinstance(resultado.get("Payload"), dict) else resultado
    if not isinstance(payload, dict):
        return {}
    cuerpo = payload.get("body")
    if isinstance(cuerpo, str):
        try:
            cuerpo = json.loads(cuerpo)
        except json.JSONDecodeError:
            cuerpo = {}
    if not isinstance(cuerpo, dict):
        cuerpo = {}
    else:
        cuerpo = dict(cuerpo)
    if isinstance(payload.get("quality_issue"), dict):
        cuerpo["quality_issue"] = payload["quality_issue"]
    if payload.get("placeholders") and not cuerpo.get("placeholders"):
        cuerpo["placeholders"] = payload["placeholders"]
    return cuerpo


def construir_informe_de_calidad(event: dict) -> dict:
    """Flatten warnings, placeholders, fallback models, and missing files."""
    datos = _entrada(event)
    issues = _issues_desde_objeto(datos.get("quality_issues"))
    _anadir_si_falta(issues, "InvokeSetupGuide", datos.get("setup_guide_error"), "error", "PDF missing")
    cuerpo_setup = _cuerpo_setup(datos)
    hallazgo_setup = cuerpo_setup.get("quality_issue")
    if isinstance(hallazgo_setup, dict):
        _anadir_si_falta(
            issues,
            hallazgo_setup.get("step") or "InvokeSetupGuide",
            hallazgo_setup.get("error"),
            hallazgo_setup.get("severity") or "warning",
            hallazgo_setup.get("deliverable") or "Setup Guide",
        )
    _anadir_si_falta(issues, "InvokeDeckBuilder", datos.get("decks_error"), "error", "PPT missing")
    _anadir_si_falta(issues, "InvokePostGenerationAudit", datos.get("audit_error"), "warning", "")
    _anadir_si_falta(issues, "InvokeBookBuilder", datos.get("book_error"), "error", "book missing")
    _anadir_si_falta(issues, "InvokeLabGuideBuilder", datos.get("lab_guide_error"), "error", "lab guide missing")

    for aviso in datos.get("quality_warnings") or []:
        if isinstance(aviso, dict):
            issues.append(
                {
                    "step": "lab_quality",
                    "error": _texto(aviso),
                    "severity": "warning",
                    "deliverable": "",
                }
            )
    for revision in datos.get("labs_needing_review") or []:
        if isinstance(revision, dict):
            issues.append(
                {
                    "step": "lab_quality",
                    "error": _texto(revision),
                    "severity": "warning",
                    "deliverable": "",
                }
            )

    placeholders = list(datos.get("placeholders") or [])
    for token in cuerpo_setup.get("placeholders") or []:
        if isinstance(token, str) and token:
            placeholders.append({"kind": "setup_guide", "token": token})
        elif isinstance(token, dict) and token.get("token"):
            placeholders.append({"kind": "setup_guide", "token": token["token"]})
    for marca in datos.get("theory_placeholders") or []:
        if marca in (True, "true"):
            placeholders.append({"kind": "lesson", "placeholder": True})
    for aviso in datos.get("theory_warnings") or []:
        if aviso:
            _anadir_si_falta(issues, "GenerateBatchContent", aviso, "warning", "")
    failed = list(datos.get("failed_lab_ids") or [])
    models = datos.get("models_used") or []
    if isinstance(models, dict):
        models = [models]

    entregado = event.get("status", "success") != "failed"
    return {
        "project_folder": datos.get("project_folder") or event.get("project_folder") or "",
        "delivered": bool(entregado),
        "quality_issues": issues,
        "placeholders": placeholders,
        "failed_lab_ids": failed,
        "models_used": models,
        "missing_deliverables": sorted(
            {
                item["deliverable"]
                for item in issues
                if item.get("deliverable")
            }
        ),
        "resume": {
            "lab_ids_to_regenerate": failed,
            "LAB_SKIP_IF_EXISTS": "true",
            "note": (
                "Start a new execution with lab_ids_to_regenerate set to failed_lab_ids. "
                "LAB_SKIP_IF_EXISTS=true reuses finished labs. A lab whose file contains "
                "AURORA_PLACEHOLDER_PENDING_REGENERATION is regenerated. "
                "Inicie una ejecución con lab_ids_to_regenerate igual a failed_lab_ids. "
                "LAB_SKIP_IF_EXISTS=true reutiliza los laboratorios ya terminados. "
                "Un laboratorio cuya ficha contiene AURORA_PLACEHOLDER_PENDING_REGENERATION se regenera."
            ),
        },
    }


def informe_tiene_hallazgos(informe: dict) -> bool:
    if not isinstance(informe, dict):
        return False
    return bool(
        informe.get("quality_issues")
        or informe.get("placeholders")
        or informe.get("failed_lab_ids")
        or informe.get("missing_deliverables")
    )


def alerta_al_propietario(informe: dict, execution_arn: str = "", project_folder: str = "") -> tuple:
    """Bilingual owner alert. Spanish first, then English. Not sent to the learner."""
    proyecto = project_folder or informe.get("project_folder") or "proyecto"
    arn = execution_arn or "N/A"
    lineas = []
    for item in informe.get("quality_issues") or []:
        entrega = f" [{item.get('deliverable')}]" if item.get("deliverable") else ""
        lineas.append(f"- {item.get('severity', 'warning')} {item.get('step')}{entrega}: {item.get('error')}")
    if informe.get("failed_lab_ids"):
        lineas.append("- failed_lab_ids: " + ", ".join(str(x) for x in informe["failed_lab_ids"]))
    if informe.get("placeholders"):
        lineas.append("- placeholders: " + _texto(informe["placeholders"], 1500))
    if informe.get("models_used"):
        lineas.append("- models_used: " + _texto(informe["models_used"], 1500))
    detalle = "\n".join(lineas) or "(sin detalle / no detail)"
    subject = f"Aurora quality report / informe de calidad: {proyecto}"
    texto = f"""Informe de calidad para el propietario. El curso se entregó al usuario.
Quality report for the owner. The course was delivered to the learner.

Proyecto / Project: {proyecto}
Execution ARN: {arn}
Informe / Report: {proyecto}/validation/quality-report.json

{detalle}

Para regenerar solo los laboratorios fallidos, inicie una ejecución con
lab_ids_to_regenerate igual a failed_lab_ids y LAB_SKIP_IF_EXISTS=true.
To regenerate only the failed labs, start an execution with
lab_ids_to_regenerate set to failed_lab_ids and LAB_SKIP_IF_EXISTS=true.
"""
    return subject, texto
