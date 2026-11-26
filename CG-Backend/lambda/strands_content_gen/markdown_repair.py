"""Repair lab and lesson markdown before it is saved or validated.

Untagged fences get a language (json, powershell, bash, or text). A VISUAL
marker is written as ``[VISUAL:``. ``MARKDOWN_REPAIR=0`` returns the text
unchanged. A caller that cannot import this module keeps the original text.
"""

from __future__ import annotations

import json
import os
import re

_POWERSHELL_RE = re.compile(
    r"(?m)^\s*(?:Get|Set|New|Remove|Write|Import|Export|Invoke)-[A-Za-z]+\b"
)
_BASH_RE = re.compile(
    r"(?m)^\s*(?:#!/(?:usr/bin/env )?(?:bash|sh)\b|sudo\s|apt(?:-get)?\s|chmod\s|"
    r"echo\s|ls(?:\s|$)|cd\s|npm\s|docker\s|kubectl\s|\$\s)"
)
_VISUAL_RE = re.compile(r"\[([Vv][Ii][Ss][Uu][Aa][Ll])(\s*):")


def reparacion_activa() -> bool:
    return os.getenv("MARKDOWN_REPAIR", "1") != "0"


def inferir_lenguaje(cuerpo: str) -> str:
    """Language for one fence body. Unknown prose stays ``text``."""
    texto = (cuerpo or "").strip()
    if not texto:
        return "text"
    if texto[0] in "{[":
        try:
            json.loads(texto)
        except (json.JSONDecodeError, ValueError):
            pass
        else:
            return "json"
    if _POWERSHELL_RE.search(texto):
        return "powershell"
    if _BASH_RE.search(texto):
        return "bash"
    return "text"


def etiquetar_vallas(texto: str) -> str:
    """Add a language to opening fences that have none. Closing fences stay bare."""
    if not texto:
        return texto or ""
    lineas = texto.splitlines(keepends=True)
    salida = []
    dentro = False
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        despojada = linea.lstrip()
        if despojada.startswith("```"):
            if dentro:
                dentro = False
                salida.append(linea)
                i += 1
                continue
            dentro = True
            marca = despojada[3:].strip()
            if marca:
                salida.append(linea)
                i += 1
                continue
            cuerpo = []
            j = i + 1
            while j < len(lineas) and not lineas[j].lstrip().startswith("```"):
                cuerpo.append(lineas[j])
                j += 1
            lenguaje = inferir_lenguaje("".join(cuerpo))
            sangria = linea[: len(linea) - len(despojada)]
            fin = "\n" if linea.endswith("\n") else ""
            if linea.endswith("\r\n"):
                fin = "\r\n"
            salida.append(f"{sangria}```{lenguaje}{fin}")
            i += 1
            continue
        salida.append(linea)
        i += 1
    return "".join(salida)


def normalizar_visual(texto: str) -> str:
    """``[visual:`` and ``[Visual:`` become ``[VISUAL:``, with one space after the colon."""
    if not texto:
        return texto or ""
    piezas = []
    cursor = 0
    for coincidencia in _VISUAL_RE.finditer(texto):
        piezas.append(texto[cursor:coincidencia.start()])
        despues = texto[coincidencia.end():]
        if despues.startswith(" "):
            piezas.append("[VISUAL:")
        else:
            piezas.append("[VISUAL: ")
        cursor = coincidencia.end()
    piezas.append(texto[cursor:])
    return "".join(piezas)


def reparar_markdown(texto: str) -> str:
    """Fill fence languages and normalize VISUAL casing. Does not invent content."""
    if not texto or not reparacion_activa():
        return texto or ""
    return etiquetar_vallas(normalizar_visual(texto))
