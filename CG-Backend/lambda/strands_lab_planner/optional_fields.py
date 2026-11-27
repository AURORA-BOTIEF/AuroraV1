"""Optional course-start fields. See ``lambda/optional_fields.py``.

Copied into this function's CodeUri so the planner package can import it.
"""

from __future__ import annotations

CAMPOS_OPCIONALES_DE_INICIO = (
    "lab_requirements",
    "manual_s3_keys",
    "manual_text_s3_key",
    "lab_ids_to_regenerate",
    "lesson_to_generate",
    "lesson_requirements",
    "lesson_ids_to_update",
)


def leer_campos_opcionales(event) -> dict:
    if not isinstance(event, dict):
        return {clave: None for clave in CAMPOS_OPCIONALES_DE_INICIO}
    return {clave: event.get(clave) for clave in CAMPOS_OPCIONALES_DE_INICIO}


def resolver_master_plan_key(event):
    if not isinstance(event, dict):
        return None
    directo = event.get("master_plan_key")
    if directo:
        return directo
    for nodo in ("lab_planner_result", "master_lab_plan_result"):
        bloque = event.get(nodo)
        if not isinstance(bloque, dict):
            continue
        payload = bloque.get("Payload")
        if isinstance(payload, dict) and payload.get("master_plan_key"):
            return payload.get("master_plan_key")
        if bloque.get("master_plan_key"):
            return bloque.get("master_plan_key")
    return None
