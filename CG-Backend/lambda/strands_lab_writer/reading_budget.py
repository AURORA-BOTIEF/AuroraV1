"""Reading budget for a lab, tied to its declared duration.

A student reads technical Spanish at about 200 words per minute. That is the
same rate ``referent_check`` already uses to turn prose into minutes. The
October instructor report described a lab that took 17 minutes just to read,
and live QA on the release candidate measured the same shape: MS-4004.1 labs
of 12–13 minutes ran 2,300–3,000 words (11–15 minutes of reading) and MS-4019
lab 02-00-01 ran 5,900 words in a 55-minute slot.

The budget is therefore not the reading speed. It is how many words of
student-facing prose are allowed per declared minute, chosen so reading stays
a minority of the slot:

- ``LAB_READING_WORDS_PER_MINUTE`` defaults to 60.
- 60 / 200 = 30% of the slot spent reading, 70% left for doing (prompts,
  clicks, waiting on the model, checking evidence).
- A 12-minute lab may contain 720 words of prose (about 4 minutes of reading),
  not 2,300–3,000. A 55-minute lab may contain 3,300, not 5,900.

The fictitious-data annex is not part of that prose. It is sample rows the
student pastes, so it has its own cap (``LAB_ANNEX_MAX_WORDS``, default 500:
about two and a half minutes of reading, enough for the rows the steps use).

Both numbers are read from the environment on each call so a deploy can tune
them without a code change. ``READING_BUDGET_RETRY=0`` records the finding and
does not ask the model again. The last attempt never fails the lab: the
finding is medium confidence and the quality gate only blocks on high.
"""

from __future__ import annotations

import math
import os
import re
from typing import Optional

_APAGADO = ("0", "false", "no", "off")
_VELOCIDAD_LECTURA = 200
_PRESUPUESTO_POR_MINUTO = 60
_TOPE_ANEXO = 500
_ANEXO_RE = re.compile(
    r"^##\s+(?:Anexo \(datos ficticios\)|Annex \(fictitious data\))\s*$",
    re.MULTILINE,
)
_CERCA_RE = re.compile(r"```.*?```", re.DOTALL)
_PALABRA_RE = re.compile(r"\w+", re.UNICODE)


def _entero(nombre: str, defecto: int, minimo: int = 1) -> int:
    crudo = os.getenv(nombre, str(defecto))
    try:
        valor = int(str(crudo).strip())
    except (TypeError, ValueError):
        valor = defecto
    return max(minimo, valor)


def velocidad_de_lectura() -> int:
    """Words a student reads per minute. Justifies the budget; it is not the budget."""
    return _entero("LAB_READING_SPEED_WPM", _VELOCIDAD_LECTURA)


def palabras_por_minuto_presupuesto() -> int:
    """Student-facing words allowed per declared minute. Default leaves most of the slot for doing."""
    return _entero("LAB_READING_WORDS_PER_MINUTE", _PRESUPUESTO_POR_MINUTO)


def tope_de_anexo() -> int:
    return _entero("LAB_ANNEX_MAX_WORDS", _TOPE_ANEXO)


def reintento_habilitado() -> bool:
    """``READING_BUDGET_RETRY=0`` records the overrun and ships the lab."""
    return os.getenv("READING_BUDGET_RETRY", "1").strip().lower() not in _APAGADO


def presupuesto_de_lectura(minutos) -> dict:
    """Word ceilings for one lab. ``{}`` when the lab has no declared duration."""
    try:
        declarada = int(minutos or 0)
    except (TypeError, ValueError):
        declarada = 0
    if declarada <= 0:
        return {}
    velocidad = velocidad_de_lectura()
    por_minuto = palabras_por_minuto_presupuesto()
    palabras_max = declarada * por_minuto
    return {
        "declarada": declarada,
        "palabras_por_minuto": por_minuto,
        "velocidad_lectura": velocidad,
        "palabras_max": palabras_max,
        "minutos_lectura": math.ceil(palabras_max / velocidad) if velocidad else 0,
        "fraccion": round(por_minuto / velocidad, 2) if velocidad else 0,
        "anexo_max": tope_de_anexo(),
    }


def partir_anexo(markdown: str) -> tuple[str, str]:
    """Split the fictitious-data annex off the student-facing body.

    The annex runs from its heading until the next level-2 heading, or to the
    end of the guide when the writer appended it there.
    """
    texto = markdown or ""
    coincidencia = _ANEXO_RE.search(texto)
    if not coincidencia:
        return texto, ""
    inicio = coincidencia.start()
    resto = texto[coincidencia.end():]
    siguiente = re.search(r"\n##\s+(?!#)", resto)
    if siguiente:
        fin = coincidencia.end() + siguiente.start()
        return (texto[:inicio] + texto[fin:]).strip(), texto[inicio:fin].strip()
    return texto[:inicio].strip(), texto[inicio:].strip()


def contar_palabras(texto: str, incluir_cercas: bool = False) -> int:
    """Words the student reads. Fenced commands are not prose unless ``incluir_cercas``."""
    cuerpo = texto or ""
    if not incluir_cercas:
        cuerpo = _CERCA_RE.sub(" ", cuerpo)
    return len(_PALABRA_RE.findall(cuerpo))


def medir_lectura(markdown: str, minutos) -> dict:
    """Count body and annex against the budget. The annex never spends the body budget."""
    presupuesto = presupuesto_de_lectura(minutos)
    cuerpo, anexo = partir_anexo(markdown)
    palabras = contar_palabras(cuerpo, incluir_cercas=False)
    palabras_anexo = contar_palabras(anexo, incluir_cercas=True) if anexo else 0
    if not presupuesto:
        return {
            "excede": False,
            "motivo": "sin duración declarada",
            "palabras": palabras,
            "palabras_anexo": palabras_anexo,
            "palabras_max": 0,
            "anexo_max": 0,
            "duracion": 0,
        }
    excede_cuerpo = palabras > presupuesto["palabras_max"]
    excede_anexo = palabras_anexo > presupuesto["anexo_max"]
    informe = {
        "excede": excede_cuerpo or excede_anexo,
        "excede_cuerpo": excede_cuerpo,
        "excede_anexo": excede_anexo,
        "palabras": palabras,
        "palabras_anexo": palabras_anexo,
        **presupuesto,
        "duracion": presupuesto["declarada"],
    }
    return informe


def texto_para_prompt(minutos, en_espanol: bool = True) -> str:
    """The budget the writer sees before it drafts the lab."""
    presupuesto = presupuesto_de_lectura(minutos)
    if not presupuesto:
        if en_espanol:
            return (
                "PRESUPUESTO DE LECTURA: no hay duración declarada. "
                "No pases de 1200 palabras de prosa que el alumno lee "
                "(sin cercas de código). No rellenes con teoría.\n"
            )
        return (
            "READING BUDGET: this lab has no declared duration. "
            "Stay under 1200 words of prose the student reads "
            "(code fences excluded). Do not pad with theory.\n"
        )
    if en_espanol:
        return f"""PRESUPUESTO DE LECTURA (REQUISITO DURO: LA MAYOR PARTE DEL TIEMPO ES PARA HACER):
El alumno lee unas {presupuesto['velocidad_lectura']} palabras por minuto. Esta práctica dura {presupuesto['declarada']} minutos.
- Prosa que el alumno lee, sin cercas de código y sin el anexo de datos ficticios: como máximo {presupuesto['palabras_max']} palabras ({presupuesto['palabras_por_minuto']} palabras por minuto declarado). Eso son unos {presupuesto['minutos_lectura']} minutos de lectura, el {int(presupuesto['fraccion'] * 100)}% del hueco. El resto es para ejecutar, esperar y comprobar.
- El apartado «Anexo (datos ficticios)» no entra en esas {presupuesto['palabras_max']} palabras. Su tope propio es {presupuesto['anexo_max']} palabras: solo las filas que los pasos usan.
- No añadas contexto, teoría ni ejemplos para alargar. Si no cabe, recorta las explicaciones y deja los pasos.
"""
    return f"""READING BUDGET (HARD REQUIREMENT: MOST OF THE SLOT IS FOR DOING):
A student reads about {presupuesto['velocidad_lectura']} words per minute. This lab lasts {presupuesto['declarada']} minutes.
- Prose the student reads, excluding code fences and the fictitious-data annex: at most {presupuesto['palabras_max']} words ({presupuesto['palabras_por_minuto']} words per declared minute). That is about {presupuesto['minutos_lectura']} minutes of reading, {int(presupuesto['fraccion'] * 100)}% of the slot. The rest is for doing, waiting, and checking.
- The "Annex (fictitious data)" section does not count toward those {presupuesto['palabras_max']} words. Its own cap is {presupuesto['anexo_max']} words: only the rows the steps use.
- Do not add context, theory, or examples to make the lab longer. If it does not fit, cut the explanations and keep the steps.
"""


def mensaje_acortar(medida: dict, en_espanol: bool = True) -> str:
    """Concrete shorten instruction: the counts from this draft and the ceilings."""
    if en_espanol:
        return (
            "CORRECCIÓN (presupuesto de lectura):\n"
            f"- Esta práctica dura {medida.get('duracion', 0)} minutos y el borrador "
            f"tiene {medida.get('palabras', 0)} palabras de prosa "
            f"(sin cercas de código y sin el anexo). El presupuesto es "
            f"{medida.get('palabras_max', 0)} palabras "
            f"({medida.get('palabras_por_minuto', 0)} por minuto declarado, "
            f"lectura a {medida.get('velocidad_lectura', _VELOCIDAD_LECTURA)} palabras/min, "
            f"como máximo {medida.get('minutos_lectura', 0)} minutos de lectura).\n"
            f"- El anexo de datos ficticios tiene {medida.get('palabras_anexo', 0)} palabras "
            f"y su tope propio es {medida.get('anexo_max', 0)}. No cuenta dentro de las "
            f"{medida.get('palabras_max', 0)} de la práctica.\n"
            "- Acorta la prosa hasta el presupuesto: quita contexto, teoría y ejemplos que el paso no usa. "
            "No muevas párrafos al anexo para esquivar el presupuesto. "
            "Si el anexo se pasa, deja solo las filas que los pasos usan.\n"
            f"- Esta corrección debe dejar como máximo {medida.get('palabras_max', 0)} palabras de prosa "
            f"y {medida.get('anexo_max', 0)} palabras en el anexo."
        )
    return (
        "CORRECTION (reading budget):\n"
        f"- This lab lasts {medida.get('duracion', 0)} minutes and the draft has "
        f"{medida.get('palabras', 0)} words of prose (code fences and the annex excluded). "
        f"The budget is {medida.get('palabras_max', 0)} words "
        f"({medida.get('palabras_por_minuto', 0)} per declared minute, "
        f"reading at {medida.get('velocidad_lectura', _VELOCIDAD_LECTURA)} words/min, "
        f"at most {medida.get('minutos_lectura', 0)} minutes of reading).\n"
        f"- The fictitious-data annex has {medida.get('palabras_anexo', 0)} words "
        f"and its own cap is {medida.get('anexo_max', 0)}. It does not count toward the "
        f"{medida.get('palabras_max', 0)} words of the practice.\n"
        "- Shorten the prose to the budget: drop context, theory, and examples a step does not use. "
        "Do not move paragraphs into the annex to dodge the budget. "
        "If the annex is over its cap, keep only the rows the steps use.\n"
        f"- This correction must leave at most {medida.get('palabras_max', 0)} words of prose "
        f"and {medida.get('anexo_max', 0)} words in the annex."
    )


def _recortar_prosa(cuerpo: str, max_palabras: int) -> str:
    partes = re.split(r"\n\s*\n", cuerpo or "")
    def cuenta(items: list[str]) -> int:
        return contar_palabras("\n\n".join(items))

    while len(partes) > 2 and cuenta(partes) > max_palabras:
        eliminado = False
        for indice in range(len(partes) - 1, 0, -1):
            trozo = partes[indice].strip()
            if not trozo or trozo.startswith("#") or trozo.startswith("```"):
                continue
            if re.match(r"\d+\.", trozo):
                continue
            del partes[indice]
            eliminado = True
            break
        if not eliminado:
            break
    return "\n\n".join(partes)


def _recortar_anexo(anexo: str, max_palabras: int) -> str:
    lineas = (anexo or "").splitlines()
    while len(lineas) > 3 and contar_palabras("\n".join(lineas), incluir_cercas=True) > max_palabras:
        if lineas[-1].strip():
            lineas.pop()
        else:
            lineas.pop()
    return "\n".join(lineas)


def recortar_a_presupuesto(markdown: str, minutos) -> str:
    """One trim of prose and annex rows. ``READING_TRIM=0`` leaves the guide.

    Headings, fenced commands and numbered steps stay. If the text is still
    over the budget, the caller records the existing reading warning.
    """
    texto = markdown or ""
    if os.environ.get("READING_TRIM", "1") == "0":
        return texto
    medida = medir_lectura(texto, minutos)
    if not medida.get("excede"):
        return texto
    cuerpo, anexo = partir_anexo(texto)
    if medida.get("excede_cuerpo"):
        cuerpo = _recortar_prosa(cuerpo, int(medida.get("palabras_max") or 0))
    if medida.get("excede_anexo") and anexo:
        anexo = _recortar_anexo(anexo, int(medida.get("anexo_max") or 0))
    if anexo:
        return cuerpo.rstrip() + "\n\n" + anexo.strip() + "\n"
    return cuerpo


def hallazgo_lectura(medida: dict) -> Optional[dict]:
    """Medium finding. The quality gate blocks only on high confidence."""
    if not medida or not medida.get("excede"):
        return None
    return {
        "valor": (
            f"{medida.get('duracion', 0)} min: {medida.get('palabras', 0)} palabras de lectura "
            f"(presupuesto {medida.get('palabras_max', 0)}, "
            f"{medida.get('palabras_por_minuto', 0)} palabras/min) "
            f"y anexo de {medida.get('palabras_anexo', 0)} "
            f"(tope {medida.get('anexo_max', 0)})"
        ),
        "tipo": "lectura",
        "inicio": 0,
        "confianza": "media",
        "verificacion": "R1",
    }
