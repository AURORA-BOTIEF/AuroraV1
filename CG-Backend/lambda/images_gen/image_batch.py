"""Image-batch accounting that cannot loop on a failed prompt.

A failed Gemini call used to leave the same prompts in ``remaining_prompts``
because only successes advanced the cursor. The state machine then called
ImagesGen again with the same two prompts. Failures are consumed and recorded
as a quality issue. Prompts not attempted (timeout or batch cap) stay queued.

``States.Array`` wraps the previous accumulator and the new batch as two
elements, so each pass nested the list. ``fusionar_imagenes`` flattens that
shape and any deeper nesting back into one list of image records.
"""

from __future__ import annotations

from typing import Any, Optional


def modelo_desactivado(image_model: Any) -> bool:
    """True for an explicit skip. A missing value is not a skip: the caller may default it."""
    if image_model is None:
        return False
    texto = str(image_model).strip().lower()
    return texto in ("", "none")


def aplanar_imagenes(valor: Any) -> list:
    """Flatten a list, a States.Array nest, or an id-to-record map."""
    if isinstance(valor, dict):
        if "id" in valor or "status" in valor or "s3_key" in valor:
            return [valor]
        plano = []
        for item in valor.values():
            plano.extend(aplanar_imagenes(item))
        return plano
    if not isinstance(valor, list):
        return []
    plano = []
    for item in valor:
        plano.extend(aplanar_imagenes(item))
    return plano


def fusionar_imagenes(previas: Any, nuevas: Any) -> list:
    """One flat list. A later record with the same id replaces the earlier one."""
    fusion = {}
    orden = []
    for img in aplanar_imagenes(previas) + aplanar_imagenes(nuevas):
        if not isinstance(img, dict):
            continue
        identificador = str(img.get("id") or "")
        clave = identificador or f"anon-{len(orden)}"
        if clave not in fusion:
            orden.append(clave)
        fusion[clave] = img
    return [fusion[clave] for clave in orden]


def prompts_no_intentados(prompts: Any, attempted: int) -> list:
    """Prompts at and after ``attempted`` still need a pass. Attempted ones are consumed."""
    if not isinstance(prompts, list):
        return []
    try:
        inicio = int(attempted)
    except (TypeError, ValueError):
        inicio = 0
    if inicio < 0:
        inicio = 0
    if inicio >= len(prompts):
        return []
    return list(prompts[inicio:])


def hallazgo_de_imagenes(failed_images: Any) -> Optional[dict]:
    """Bilingual warning. None when this batch did not fail an image."""
    if not isinstance(failed_images, list) or not failed_images:
        return None
    identificadores = [str(item.get("id") or "?") for item in failed_images if isinstance(item, dict)]
    if not identificadores:
        identificadores = ["?"]
    n = len(identificadores)
    visibles = ", ".join(identificadores[:20])
    extra = "" if n <= 20 else f" (+{n - 20})"
    return {
        "step": "GenerateBatchImages",
        "severity": "warning",
        "error": (
            f"{n} imagen(es) fallaron y no se reintentan{extra}: {visibles}. "
            f"{n} image(s) failed and will not be retried{extra}: {visibles}."
        ),
    }


def combinar_hallazgos(previo: Any, nuevo: Any) -> Optional[dict]:
    """Keep an earlier warning when a later batch succeeds."""
    textos = []
    for item in (previo, nuevo):
        if isinstance(item, dict) and item.get("error"):
            textos.append(str(item.get("error")))
        elif isinstance(item, str) and item.strip():
            textos.append(item.strip())
    if not textos:
        return None
    return {
        "step": "GenerateBatchImages",
        "severity": "warning",
        "error": " | ".join(textos),
    }


def cerrar_lote(
    prompts: Any,
    attempted: int,
    failed_images: Any,
    generated_images: Any,
    accumulated_images: Any,
    prior_quality_issue: Any,
) -> dict:
    """End one pass. Failed prompts are not returned in remaining_prompts."""
    restantes = prompts_no_intentados(prompts, attempted)
    return {
        "remaining_prompts": restantes,
        "statistics_remaining": len(restantes),
        "quality_issue": combinar_hallazgos(prior_quality_issue, hallazgo_de_imagenes(failed_images)),
        "accumulated_images": fusionar_imagenes(accumulated_images, generated_images),
    }


def respuesta_sin_imagenes(
    *,
    course_bucket: Any,
    project_folder: Any,
    accumulated_images: Any = None,
    prior_quality_issue: Any = None,
    message: str,
    quality_issue: Any = None,
) -> dict:
    """A terminal ImagesGen payload: nothing left to retry, course continues."""
    hallazgo = combinar_hallazgos(prior_quality_issue, quality_issue)
    return {
        "statusCode": 200,
        "message": message,
        "generated_images": [],
        "bucket": course_bucket,
        "project_folder": project_folder,
        "lesson_keys": [],
        "image_mappings": {},
        "remaining_prompts": [],
        "accumulated_images": fusionar_imagenes(accumulated_images, []),
        "quality_issue": hallazgo,
        "statistics": {
            "total_requested": 0,
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "remaining": 0,
            "success_rate": "0%",
            "timeout_stopped": False,
        },
        "failed_details": [],
    }
