# -*- coding: utf-8 -*-
"""Derive user-visible course status from Step Functions output (non-blocking tail)."""

from __future__ import annotations

import json
from typing import Any


def _coerce_detail(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def warnings_from_execution_output(parsed_output: dict | None) -> list[dict]:
    if not isinstance(parsed_output, dict):
        return []
    warnings: list[dict] = []
    for key, label in (
        ("setup_guide_error", "Setup Guide"),
        ("audit_error", "Post-generation audit"),
        ("decks_error", "Deck builder"),
    ):
        if key in parsed_output and parsed_output.get(key) is not None:
            warnings.append(
                {
                    "code": key,
                    "component": label,
                    "detail": _coerce_detail(parsed_output.get(key)),
                }
            )
    return warnings


def course_status_label(step_functions_status: str, parsed_output: dict | None) -> str:
    """Surface partial completion without failing the execution."""
    if step_functions_status != "SUCCEEDED":
        return step_functions_status
    if warnings_from_execution_output(parsed_output):
        return "SUCCEEDED_WITH_WARNINGS"
    return "SUCCEEDED"