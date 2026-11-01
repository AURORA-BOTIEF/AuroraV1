"""Selección del contexto relevante del manual de referencia (paso 0 de calidad).

Problema que resuelve
---------------------
El pipeline recortaba el manual por encabezado (``manual[:10000]``,
``manual_ref_text[:12000]``, ``manual_reference_text[:14000]``). En un curso real el
manual extraído del PDF ronda las 230.000 letras, así que el modelo solo veía ~4%
del documento y **inventaba** el resto: escenarios, cifras y entregables que no
estaban en el temario. Eso explica el retrabajo reportado por los instructores.

Qué hace
--------
Divide el manual en ventanas deslizantes, puntúa cada ventana por su solapamiento
léxico con el laboratorio/lección que se va a generar, y devuelve las mejores
ventanas (en orden de documento) dentro de un presupuesto de caracteres.

Garantías de seguridad
----------------------
- **Sin dependencias**: solo biblioteca estándar (Lambda arm64 / python3.12).
- **Determinista**: misma entrada → misma salida (útil para cachés y pruebas).
- **Degradación segura**: si algo no cuadra (sin query, sin coincidencias,
  documento pequeño) devuelve el recorte por encabezado de siempre.
- **Interruptor de apagado**: ``MANUAL_CONTEXT_ENABLED=0`` vuelve al recorte por
  encabezado sin revertir el código.
- **Presupuesto configurable**: ``MANUAL_CONTEXT_MAX_CHARS`` (por defecto 30000).

Uso
---
    from manual_context import select_manual_context, flatten_to_text

    excerpt = select_manual_context(
        manual_reference_text,
        query_text=flatten_to_text(lab_plan),
        title_text=lab_plan.get("lab_title", ""),
        label=lab_id,
    )
"""

from __future__ import annotations

import os
import re
import unicodedata

# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #

DEFAULT_MAX_CHARS = 30_000
# 0 por defecto: el encabezado del manual suele traer el aviso legal y el prompt ya
# recibe el contexto del curso desde el temario. Medido sobre un curso real: cubrir
# 1.200–2.500 caracteres de encabezado no mejora la cobertura y sí gasta presupuesto.
DEFAULT_PREAMBLE_CHARS = 0
DEFAULT_WINDOW_CHARS = 2_000
DEFAULT_OVERLAP_CHARS = 400
MIN_TERM_LEN = 4
_TITLE_WEIGHT_BOOST = 2.0
_REPEAT_BONUS = 0.2
MAX_TERM_WEIGHT_LEN = 12

OMISSION_MARKER = "\n\n[... contenido del manual omitido ...]\n\n"

# Palabras vacías ES/EN: no aportan a la relevancia y ensucian la puntuación.
_STOPWORDS = frozenset(
    """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aunque bajo bien
    cada como con contra cual cuales cuando cuanto cuenta dado de del desde donde dos
    durante e el ella ellas ello ellos en entre era eran eres es esa esas ese eso esos
    esta estaba estado estas este esto estos estoy fin fue fueron ha hace hacen hacia han
    hasta hay la las le les lo los mas me mediante menos mi mientras misma mismo mucha
    mucho muy nada ni ninguna ninguno no nos nosotros nuestra nuestro o otra otras otro
    otros para pero poco por porque primera que quien quienes se sea segun ser si siempre
    sin sino sobre son su sus tal tambien tan tanto te tener tiene tienen toda todas todo
    todos tu un una unas uno unos usted ustedes va vamos van varios ver y ya yo
    about above after again against all also among and any are because been before being
    below between both but came can cannot come could did does doing done down during each
    either else even ever every few first for from further get got had has have having her
    here hers him his how however into it its itself just like made make many may me might
    more most much must my never new no nor not now of off on once only or other our out
    over own said same see shall she should since some such than that the their them then
    there these they this those though through thus to too under until up upon use used
    using very was way we well were what when where whether which while who whom why will
    with within without would yet you your
    """.split()
)


# --------------------------------------------------------------------------- #
# Configuración desde el entorno
# --------------------------------------------------------------------------- #

def manual_context_enabled() -> bool:
    """``MANUAL_CONTEXT_ENABLED`` (por defecto activado). Cualquier valor tipo 0/false/no/off apaga."""
    raw = os.getenv("MANUAL_CONTEXT_ENABLED", "1")
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


def max_chars_from_env(default: int = DEFAULT_MAX_CHARS) -> int:
    """Presupuesto de caracteres del excerpt (``MANUAL_CONTEXT_MAX_CHARS``)."""
    raw = os.getenv("MANUAL_CONTEXT_MAX_CHARS", str(default))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


# --------------------------------------------------------------------------- #
# Normalización y términos
# --------------------------------------------------------------------------- #

def _normalize(text: str) -> str:
    """Minúsculas, sin acentos, solo [a-z0-9] separado por espacios.

    Imprescindible porque el manual viene de un PDF (``/swapfile``, ``lsblk -o``) y el
    temario viene en YAML con acentos correctos; sin normalizar, "aplicación" nunca
    coincidiría con el texto extraído.
    """
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^0-9a-z]+", " ", text)


def _terms(text: str) -> set[str]:
    """Términos informativos: sin vacías, sin números sueltos y con longitud mínima."""
    return {
        token
        for token in _normalize(text).split()
        if len(token) >= MIN_TERM_LEN and token not in _STOPWORDS and not token.isdigit()
    }


def flatten_to_text(value: object) -> str:
    """Aplana dicts/listas/tuplas a un texto de consulta (ignora las claves).

    Sirve para construir la consulta directamente desde el plan de laboratorio o el
    módulo del temario sin escribir un extractor distinto en cada Lambda.
    """
    parts: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            if node.strip():
                parts.append(node)
        elif isinstance(node, dict):
            for item in node.values():
                walk(item)
        elif isinstance(node, (list, tuple, set, frozenset)):
            for item in node:
                walk(item)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            parts.append(str(node))

    walk(value)
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Puntuación
# --------------------------------------------------------------------------- #

def _query_weights(query_text: str, title_text: str) -> dict[str, float]:
    """Peso por término: más largo = más específico; los del título pesan doble."""
    if not query_text:
        query_text = title_text
    body_terms = _terms(query_text or "")
    title_terms = _terms(title_text or "")

    weights: dict[str, float] = {}
    for term in body_terms | title_terms:
        weight = min(len(term), MAX_TERM_WEIGHT_LEN) / 8.0
        if term in title_terms:
            weight *= _TITLE_WEIGHT_BOOST
        weights[term] = weight
    return weights


def _score_windows(
    text: str, weights: dict[str, float], window_chars: int, overlap_chars: int
) -> list[tuple[float, int, int]]:
    """Ventanas deslizantes con score > 0: [(score, inicio, fin)]."""
    step = max(1, window_chars - overlap_chars)
    total = len(text)
    scored: list[tuple[float, int, int]] = []

    start = 0
    while start < total:
        end = min(start + window_chars, total)
        counts: dict[str, int] = {}
        for token in _normalize(text[start:end]).split():
            counts[token] = counts.get(token, 0) + 1

        score = 0.0
        for term, weight in weights.items():
            hits = counts.get(term, 0)
            if hits:
                score += weight * (1.0 + _REPEAT_BONUS * (hits - 1))

        if score > 0:
            scored.append((score, start, end))

        if end >= total:
            break
        start += step

    return scored


def _merge_interval(intervals: list[tuple[int, int]], start: int, end: int) -> list[tuple[int, int]]:
    """Devuelve una lista nueva con [start, end) fusionado (une solapes y contigüidad)."""
    merged = list(intervals)
    merged.append((start, end))
    merged.sort()
    out: list[tuple[int, int]] = []
    for a, b in merged:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _pick_intervals(
    windows: list[tuple[float, int, int]], budget: int
) -> list[tuple[int, int]]:
    """Elige ventanas por score hasta agotar el presupuesto y devuelve rangos ordenados."""
    ranked = sorted(windows, key=lambda item: (-item[0], item[1]))
    intervals: list[tuple[int, int]] = []

    for _, start, end in ranked:
        candidate = _merge_interval(intervals, start, end)
        used = sum(b - a for a, b in candidate)
        if used > budget and intervals:
            continue
        intervals = candidate
        if used >= budget:
            break

    return sorted(intervals)


def _log(label: str, manual_len: int, excerpt_len: int, used: int, scored: int, note: str = "") -> None:
    tag = f"[{label}]" if label else ""
    detail = f" — {note}" if note else ""
    print(
        f"📚 Manual{tag}: {manual_len:,} chars → excerpt {excerpt_len:,} chars "
        f"({used}/{scored} ventanas){detail}"
    )


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #

def select_manual_context(
    manual_text: str,
    query_text: str = "",
    *,
    title_text: str = "",
    max_chars: int | None = None,
    preamble_chars: int | None = None,
    window_chars: int = DEFAULT_WINDOW_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    label: str = "",
) -> str:
    """Devuelve las secciones del manual relevantes para ``query_text``.

    Args:
        manual_text: manual de referencia completo (texto plano extraído del PDF).
        query_text: contenido a generar (título, objetivo, descripción, temas…).
        title_text: título del lab/lección; sus términos pesan doble.
        max_chars: presupuesto; por defecto ``MANUAL_CONTEXT_MAX_CHARS``.
        preamble_chars: encabezado que siempre se incluye (por defecto 0; ver la
            constante ``DEFAULT_PREAMBLE_CHARS``).
        label: etiqueta para el log (p. ej. el ``lab_id``).

    Returns:
        El excerpt listo para insertar en el prompt. Nunca devuelve algo más grande
        que ``max_chars`` y nunca lanza excepción por datos inesperados.
    """
    if not manual_text or not manual_text.strip():
        return ""

    try:
        budget = int(max_chars if max_chars is not None else max_chars_from_env())
    except (TypeError, ValueError):
        budget = DEFAULT_MAX_CHARS
    if budget <= 0:
        return manual_text

    if len(manual_text) <= budget:
        _log(label, len(manual_text), len(manual_text), 0, 0, "el manual completo cabe en el presupuesto")
        return manual_text

    if not manual_context_enabled():
        excerpt = manual_text[:budget]
        _log(label, len(manual_text), len(excerpt), 0, 0, "selección desactivada (MANUAL_CONTEXT_ENABLED=0)")
        return excerpt

    preamble_size = DEFAULT_PREAMBLE_CHARS if preamble_chars is None else int(preamble_chars)
    preamble_size = max(0, min(preamble_size, budget))
    preamble = manual_text[:preamble_size]
    remaining = budget - len(preamble)

    weights = _query_weights(query_text, title_text)
    if remaining <= 0 or not weights:
        excerpt = manual_text[:budget]
        _log(label, len(manual_text), len(excerpt), 0, 0, "sin consulta útil: recorte por encabezado")
        return excerpt

    windows = _score_windows(manual_text, weights, window_chars, overlap_chars)
    if not windows:
        excerpt = manual_text[:budget]
        _log(label, len(manual_text), len(excerpt), 0, 0, "sin coincidencias: recorte por encabezado")
        return excerpt

    intervals = _pick_intervals(windows, remaining)
    if not intervals:
        excerpt = manual_text[:budget]
        _log(label, len(manual_text), len(excerpt), 0, len(windows), "sin ventanas elegidas: recorte por encabezado")
        return excerpt

    parts: list[str] = []
    if preamble.strip():
        parts.append(preamble.strip())
    for start, end in intervals:
        chunk = manual_text[start:end].strip()
        if chunk:
            parts.append(chunk)

    excerpt = OMISSION_MARKER.join(parts)
    if len(excerpt) > budget:
        excerpt = excerpt[:budget]

    _log(label, len(manual_text), len(excerpt), len(intervals), len(windows))
    return excerpt
