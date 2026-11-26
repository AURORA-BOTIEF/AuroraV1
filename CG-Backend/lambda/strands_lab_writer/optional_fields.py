"""Optional course-start fields and the structural-retry view of a full state.

``RegenerateInvalidLabs`` passes the whole execution state. The shaped batch
payload still has ``lab_ids`` at the top. A real ``lab_ids`` list is kept.
``force_regenerate`` is set only when the ids come from the validation result,
which is what the previous payload literal did.
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


def normalizar_evento_writer(event: dict) -> dict:
    """Tolerate extra keys. Do not replace a lab id list or a real manual key."""
    if not isinstance(event, dict):
        return {}
    evento = dict(event)
    opcionales = leer_campos_opcionales(evento)
    for clave, valor in opcionales.items():
        if clave not in evento:
            evento[clave] = valor
    if not evento.get("master_plan_key"):
        clave_plan = resolver_master_plan_key(evento)
        if clave_plan:
            evento["master_plan_key"] = clave_plan
    if not evento.get("lab_ids"):
        validacion = evento.get("lab_validation_result")
        invalidos = []
        if isinstance(validacion, dict):
            invalidos = [lab for lab in (validacion.get("invalid_lab_ids") or []) if lab]
        if invalidos:
            evento["lab_ids"] = invalidos
            evento["force_regenerate"] = True
            evento["structural_retry"] = True
    return evento
