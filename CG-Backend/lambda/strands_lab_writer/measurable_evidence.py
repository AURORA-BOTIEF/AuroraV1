"""Rules for verifiable lab validation criteria (THOR item 5 / audit backlog #8).

Shared between the lab writer retry path and ``content_validator`` (keep both copies in sync).
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

_SUSTITUTO_NO_MEDIBLE = (
    "Compruebe los elementos que el paso pide. / "
    "Check the elements the step asks for."
)

# Phrases and shapes that cannot be verified objectively in a lab guide.
UNMEASURABLE_PHRASE_RE = re.compile(
    r"(?is)"
    r"("
    r"\b\d{1,2}\s*%\s*(de\s*)?(éxito|exito|success)\b|"
    r"\b5\s*(pruebas|tests)\s*genéric|"
    r"listo para producción|"
    r"ready for production|"
    r"funciona correctamente|"
    r"\bproduction[- ]ready\b|"
    r"verifique que todo funcione|"
    r"deber[ií]a ver que funciona|"
    r"works as expected|"
    r"everything is working"
    r")"
)

_PASO_RE = re.compile(r"(?m)^###\s")
_ARCHIVO_RE = re.compile(
    r"\b[\w.-]+\.(?:txt|csv|xlsx|xls|docx|json|sh|py|md|png|pptx|yml|yaml|log|conf)\b",
    re.IGNORECASE,
)
_SALIDA_RE = re.compile(r"`([^`]{2,80})`")
_UI_RE = re.compile(
    r"(?i)\b(bot[oó]n|button|panel|men[uú]|menu|pesta[nñ]a|tab)\s+"
    r"[A-Za-zÁÉÍÓÚáéíóúñ0-9_-]{2,}"
)
_CONTEO_RE = re.compile(
    r"(?i)\b\d+\s+(?:elementos|items|filas|rows|archivos|files|registros|records|l[ií]neas|lines)\b"
)

# Examples from the old refinement pass — must not appear as “real” values.
INVENTED_SECRET_RE = re.compile(
    r"(?i)\b("
    r"pg_password(?:_\d+)?|"
    r"api[_-]?key[_-]?\d+|"
    r"password[_-]?\d{2,}|"
    r"secret[_-]?\d+"
    r")\b"
)

AI_TOOL_RE = re.compile(
    r"(?i)\b("
    r"copilot|m365 copilot|copilot chat|designer|planner|"
    r"chatgpt|openai|gemini|gpt-?4|claude|"
    r"llm|ia generativa|modelo de lenguaje|inteligencia artificial generativa"
    r")\b"
)

STEP_SPLIT_RE = re.compile(r"(?im)^###\s*(?:Step|Paso)\s+\d+[:.]")

EXPECTED_OUTPUT_LABEL_RE = re.compile(
    r"(?is)"
    r"\*\*\s*(?:"
    r"Expected\s+[Oo]utput|Expected\s+[Rr]esult|"
    r"Salida\s+[Ee]sperada|Resultado\s+[Ee]sperado"
    r")\s*:?\s*\*\*\s*:?\s*"
)

LIST_SHAPE_RE = re.compile(
    r"(?im)"
    r"(^\s*[-*•]\s|\b\d+[.)]\s|"
    r"\b(debe incluir|must include|elementos requeridos|required elements|"
    r"comprueba que|verifica que|check that)\b)"
)


def _secciones_de_pasos(content: str) -> List[Tuple[str, str]]:
    """Return (heading line, body) for each step block."""
    matches = list(STEP_SPLIT_RE.finditer(content))
    if not matches:
        return []
    secciones: List[Tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        bloque = content[start:end]
        primera = bloque.split("\n", 1)
        titulo = primera[0].strip()
        cuerpo = primera[1] if len(primera) > 1 else ""
        secciones.append((titulo, cuerpo))
    return secciones


def _texto_salida_esperada(cuerpo_paso: str) -> str | None:
    match = EXPECTED_OUTPUT_LABEL_RE.search(cuerpo_paso)
    if not match:
        return None
    resto = cuerpo_paso[match.end() :]
    fin = re.search(r"\n\*\*\s*(?:Verification|Verificaci)", resto, re.IGNORECASE)
    if fin:
        resto = resto[: fin.start()]
    return resto.strip()


def hallazgos_validacion_no_medible(content: str) -> List[str]:
    """Return human-readable findings; empty list means no retry-worthy issues."""
    hallazgos: List[str] = []

    for match in UNMEASURABLE_PHRASE_RE.finditer(content):
        hallazgos.append(f"Frase no medible: {match.group(0)[:80]}")

    for match in INVENTED_SECRET_RE.finditer(content):
        hallazgos.append(f"Credencial o secreto inventado: {match.group(0)}")

    for titulo, cuerpo in _secciones_de_pasos(content):
        if not AI_TOOL_RE.search(cuerpo):
            continue
        salida = _texto_salida_esperada(cuerpo)
        if not salida:
            continue
        # Strip fenced code: deterministic CLI output is fine inside ``` blocks.
        salida_prosa = re.sub(r"```.*?```", "", salida, flags=re.DOTALL).strip()
        if len(salida_prosa) < 40:
            continue
        if LIST_SHAPE_RE.search(salida_prosa):
            continue
        if len(salida_prosa) > 120:
            hallazgos.append(
                f"Salida esperada determinista en paso con IA ({titulo[:60]}): "
                "use lista de elementos requeridos, no un párrafo literal."
            )

    return hallazgos


def mensaje_correccion_validacion(hallazgos: List[str]) -> str:
    lineas = [
        "CORRECCIÓN (validación verificable):",
        "- En pasos con Copilot, LLM o IA generativa, **Expected output** debe ser una lista "
        "de elementos o secciones requeridas (tono, campos, citas), nunca el texto literal "
        "que podría devolver el modelo.",
        "- En pasos con comando o fichero determinista, la salida puede ser código o salida de consola.",
        "- No inventes contraseñas, API keys ni rutas locales; usa [POR CONFIRMAR] o datos del manual.",
        "- No uses porcentajes vagos, «funciona correctamente» ni «listo para producción».",
    ]
    for h in hallazgos[:12]:
        lineas.append(f"- Corregir: {h}")
    return "\n".join(lineas)


def _ventana_del_paso(content: str, inicio: int) -> str:
    """The step that contains ``inicio``, or the whole guide when it has no steps."""
    cortes = [marca.start() for marca in _PASO_RE.finditer(content)]
    desde = 0
    hasta = len(content)
    for corte in cortes:
        if corte <= inicio:
            desde = corte
        elif corte > inicio:
            hasta = corte
            break
    return content[desde:hasta]


def _pista_medible(ventana: str, frase: str) -> Tuple[str, str]:
    """A file, output line, UI state, or count already written in the step."""
    limpio = ventana.replace(frase, " ")
    archivo = _ARCHIVO_RE.search(limpio)
    if archivo:
        return "archivo", archivo.group(0)
    salida = _SALIDA_RE.search(limpio)
    if salida:
        return "salida", f"`{salida.group(1)}`"
    interfaz = _UI_RE.search(limpio)
    if interfaz:
        return "ui", interfaz.group(0)
    conteo = _CONTEO_RE.search(limpio)
    if conteo:
        return "conteo", conteo.group(0)
    return "", ""


def _redaccion_medible(tipo: str, pista: str) -> str:
    if tipo == "archivo":
        return (
            f"Compruebe que el archivo {pista} existe y muestra el valor del paso. / "
            f"Check that the file {pista} exists and shows the value from the step."
        )
    if tipo == "salida":
        return (
            f"Compruebe que la salida incluye {pista}. / "
            f"Check that the output includes {pista}."
        )
    if tipo == "ui":
        return (
            f"Compruebe que la interfaz muestra {pista}. / "
            f"Check that the interface shows {pista}."
        )
    if tipo == "conteo":
        return (
            f"Compruebe que el resultado cuenta {pista}. / "
            f"Check that the result counts {pista}."
        )
    return ""


def reparar_validacion_no_medible(content: str) -> str:
    """Rewrite unverifiable phrases. ``VALIDATION_REPAIR=0`` leaves the text.

    ``VALIDATION_CONTEXT_REPAIR=1`` (default) rewrites each phrase into a
    measurable check using a file, output line, UI state, or count already in
    the same step. When the step has none, the phrase stays so the writer can
    record a low R5 warning. ``VALIDATION_CONTEXT_REPAIR=0`` uses the generic
    bilingual substitute. This does not invent a password or a value.
    """
    if os.environ.get("VALIDATION_REPAIR", "1") == "0":
        return content or ""
    texto = content or ""
    contextual = os.environ.get("VALIDATION_CONTEXT_REPAIR", "1") != "0"

    def reemplazo(coincidencia: "re.Match") -> str:
        if not contextual:
            return _SUSTITUTO_NO_MEDIBLE
        tipo, pista = _pista_medible(_ventana_del_paso(texto, coincidencia.start()), coincidencia.group(0))
        redaccion = _redaccion_medible(tipo, pista)
        if not redaccion:
            return coincidencia.group(0)
        return redaccion

    texto = UNMEASURABLE_PHRASE_RE.sub(reemplazo, texto)
    return INVENTED_SECRET_RE.sub("[POR CONFIRMAR]", texto)