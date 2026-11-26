"""Bracketed Setup Guide template tokens.

A token such as ``[VERSIÓN POR VALIDAR]`` is a blank, not course content.
The guide fills it from the outline, the lab plan, or the labs when that
value is already known. One optional model call may fill the rest. Anything
still blank is replaced with a bilingual neutral sentence so the PDF never
keeps the raw brackets. Those leftovers are the quality warning.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from typing import Any, Callable, Optional

NEUTRO = "Verificar con el instructor / Verify with the instructor"

_TOKEN_RE = re.compile(r"\[([^\[\]\n]{1,160})\]")
_VAGO_RE = re.compile(
    r"(?i)(latest|ultima|última|current|actual|reciente|^v?[\dx]+\.x|>=|\+)"
)
_MARCADORES = (
    "POR VALIDAR",
    "POR CONFIRMAR",
    "POR DEFINIR",
    "POR COMPLETAR",
    "INSERTAR",
    "CLAVE COMPLETA",
    "COMANDO DE PRUEBA",
    "LICENCIA POR",
    "FECHA DE VALIDACION",
    "ENLACE OFICIAL",
    "USUARIO POR",
    "REGION POR",
    "RESULTADO POR",
    "EVIDENCIA POR",
)
_EXACTOS = {"ENLACE", "V1.0"}


def _sin_acentos(texto: str) -> str:
    normal = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in normal if not unicodedata.combining(c))


def es_token_de_plantilla(interior: str) -> bool:
    """True for a fill-in bracket, not for an ordinary label such as a lab id."""
    bruto = (interior or "").strip()
    if not bruto or len(bruto) > 160:
        return False
    plano = _sin_acentos(bruto).upper()
    if plano in _EXACTOS:
        return True
    return any(marca in plano for marca in _MARCADORES)


def tokens_en_texto(texto: str) -> list:
    """Every template token, one entry per occurrence, in reading order."""
    if not texto:
        return []
    hallados = []
    for coincidencia in _TOKEN_RE.finditer(str(texto)):
        if es_token_de_plantilla(coincidencia.group(1)):
            hallados.append(f"[{coincidencia.group(1).strip()}]")
    return hallados


def tokens_en_objeto(nodo: Any) -> list:
    """Walk strings. Skip the placeholders list so the record is not a token."""
    hallados = []

    def caminar(valor, clave=None):
        if clave == "placeholders":
            return
        if isinstance(valor, dict):
            for llave, item in valor.items():
                caminar(item, llave)
        elif isinstance(valor, list):
            for item in valor:
                caminar(item)
        elif isinstance(valor, str):
            hallados.extend(tokens_en_texto(valor))

    caminar(nodo)
    return hallados


def _concreto(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    texto = " ".join(str(valor).split())
    if not texto or tokens_en_texto(texto) or _VAGO_RE.search(texto):
        return None
    return texto


def _norm(texto: str) -> str:
    return " ".join(_sin_acentos(texto or "").lower().split())


def _version_cerca(nombre: str, texto: str) -> Optional[str]:
    if not nombre or not texto:
        return None
    patron = re.compile(re.escape(nombre) + r".{0,60}?(\d+\.\d+(?:\.\d+)*)", re.I)
    coincidencia = patron.search(texto)
    if not coincidencia:
        return None
    version = coincidencia.group(1)
    if re.fullmatch(r"\d{2}\.\d{2}(?:\.\d{2})?", version):
        return None
    return version


def _comando_cerca(nombre: str, texto: str) -> Optional[str]:
    if not nombre or not texto:
        return None
    posicion = texto.lower().find(nombre.lower())
    if posicion < 0:
        return None
    ventana = texto[posicion:posicion + 800]
    bloque = re.search(r"```[a-zA-Z0-9]*\n(.*?)```", ventana, re.S)
    if not bloque:
        return None
    linea = next((fila.strip() for fila in bloque.group(1).splitlines() if fila.strip()), "")
    if not linea or tokens_en_texto(linea) or len(linea) > 180:
        return None
    return linea


def construir_catalogo(course_meta: dict, master_plan: dict, labs: dict) -> dict:
    """Values the course already stated. Nothing here is invented."""
    meta = course_meta or {}
    plan = master_plan or {}
    software = {}
    for item in plan.get("software_requirements") or []:
        if not isinstance(item, dict):
            continue
        nombre = _norm(str(item.get("name") or ""))
        if not nombre:
            continue
        ficha = software.setdefault(nombre, {})
        for destino, origen in (
            ("version", item.get("version")),
            ("license", item.get("license")),
            ("source", item.get("source") or item.get("url")),
            ("command", item.get("validation") or item.get("test_command")),
        ):
            valor = _concreto(origen)
            if valor and not ficha.get(destino):
                ficha[destino] = valor
    texto_labs = "\n".join(str(cuerpo) for cuerpo in (labs or {}).values())
    for nombre, ficha in software.items():
        visible = str(item_name(nombre, plan))
        if not ficha.get("version"):
            version = _version_cerca(visible, texto_labs)
            if version:
                ficha["version"] = version
        if not ficha.get("command"):
            comando = _comando_cerca(visible, texto_labs)
            if comando:
                ficha["command"] = comando
    fecha = None
    for candidato in (
        meta.get("last_validation"),
        meta.get("validation_date"),
        (plan.get("validation") or {}).get("date") if isinstance(plan.get("validation"), dict) else None,
    ):
        fecha = _concreto(candidato)
        if fecha:
            break
    return {
        "course_key": _concreto(meta.get("key")),
        "course_version": _concreto(meta.get("version")),
        "validation_date": fecha,
        "software": software,
        "llm": {},
    }


def item_name(nombre_norm: str, plan: dict) -> str:
    for item in (plan or {}).get("software_requirements") or []:
        if isinstance(item, dict) and _norm(str(item.get("name") or "")) == nombre_norm:
            return str(item.get("name") or nombre_norm)
    return nombre_norm


def _relleno_aceptable(valor: Any) -> Optional[str]:
    texto = _concreto(valor)
    if not texto or len(texto) > 240:
        return None
    return texto


def _buscar(token: str, fila: Optional[dict], catalogo: dict) -> Optional[str]:
    plano = _sin_acentos(token).upper()
    if "CLAVE COMPLETA" in plano and catalogo.get("course_key"):
        return catalogo["course_key"]
    if plano.strip("[]") == "V1.0" and catalogo.get("course_version"):
        return catalogo["course_version"]
    if "FECHA DE VALIDACION" in plano and catalogo.get("validation_date"):
        return catalogo["validation_date"]
    ficha = {}
    if isinstance(fila, dict):
        ficha = (catalogo.get("software") or {}).get(_norm(str(fila.get("name") or ""))) or {}
    if "VERSION POR VALIDAR" in plano and ficha.get("version"):
        return ficha["version"]
    if "COMANDO DE PRUEBA" in plano and ficha.get("command"):
        return ficha["command"]
    if "LICENCIA POR" in plano and ficha.get("license"):
        return ficha["license"]
    if "ENLACE" in plano and ficha.get("source"):
        return ficha["source"]
    sugerido = (catalogo.get("llm") or {}).get(token)
    return _relleno_aceptable(sugerido)


def _sustituir(texto: str, catalogo: dict, fila: Optional[dict], sin_relleno: list) -> str:
    def cambio(coincidencia):
        interior = coincidencia.group(1)
        if not es_token_de_plantilla(interior):
            return coincidencia.group(0)
        token = f"[{interior.strip()}]"
        relleno = _buscar(token, fila, catalogo)
        if relleno:
            return relleno
        sin_relleno.append(token)
        return NEUTRO

    return _TOKEN_RE.sub(cambio, texto)


def reemplazar_texto(texto: str, catalogo: dict) -> tuple:
    sin_relleno = []
    if texto is None:
        return texto, sin_relleno
    return _sustituir(str(texto), catalogo, None, sin_relleno), sin_relleno


def reemplazar_objeto(nodo: Any, catalogo: dict) -> tuple:
    """Return the tree with tokens replaced, plus the ones that became neutral text."""
    sin_relleno = []

    def caminar(valor, fila=None, clave=None):
        if clave == "placeholders":
            return valor
        if isinstance(valor, dict):
            fila_local = valor if valor.get("name") and ("version" in valor or "pending" in valor) else fila
            return {llave: caminar(item, fila_local, llave) for llave, item in valor.items()}
        if isinstance(valor, list):
            return [caminar(item, fila) for item in valor]
        if isinstance(valor, str):
            return _sustituir(valor, catalogo, fila, sin_relleno)
        return valor

    return caminar(nodo), sin_relleno


def mensaje_de_tokens(tokens: list) -> str:
    cuentas = Counter(tokens)
    detalle = ", ".join(
        f"{token} x{cuenta}" if cuenta > 1 else token for token, cuenta in cuentas.items()
    )
    return (
        "La Setup Guide se entregó. Tokens de plantilla sin dato de curso, sustituidos por "
        f"'{NEUTRO}': {detalle}. "
        "The Setup Guide was delivered. Template tokens without a course value were replaced "
        f"with '{NEUTRO}': {detalle}."
    )


def quality_issue_de_tokens(tokens: list) -> Optional[dict]:
    if not tokens:
        return None
    return {
        "step": "InvokeSetupGuide",
        "severity": "warning",
        "deliverable": "Setup Guide",
        "error": mensaje_de_tokens(tokens),
    }


def aplicar_sugerencia_llm(tokens: list, sugeridos: Any) -> dict:
    """Keep only model values that are concrete and do not reintroduce a token."""
    if isinstance(sugeridos, str):
        try:
            sugeridos = json.loads(sugeridos)
        except json.JSONDecodeError:
            return {}
    if not isinstance(sugeridos, dict):
        return {}
    validos = set(tokens)
    salida = {}
    for token in validos:
        valor = _relleno_aceptable(sugeridos.get(token))
        if valor:
            salida[token] = valor
    return salida


def finalizar_tokens(
    doc: dict,
    catalogo: dict,
    html: Optional[str] = None,
    llm: Optional[Callable] = None,
    render_html: Optional[Callable] = None,
) -> tuple:
    """Fill what the catalog and one model call know. Neutralize the rest.

    ``placeholders`` lists every occurrence that could not be filled, and
    ``placeholders_count`` is the length of that list. When ``render_html`` is
    given, the PDF HTML is rendered again from the filled document and only
    the template's own brackets are scanned, so a filled field is not counted
    twice. The returned HTML has no raw template brackets.
    """
    catalogo = dict(catalogo or {})
    catalogo.setdefault("llm", {})
    vistos = tokens_en_objeto(doc)
    if render_html is not None:
        html = render_html(doc)
    if html:
        vistos.extend(tokens_en_texto(html))
    unicos = list(dict.fromkeys(vistos))
    if llm and unicos:
        try:
            sugeridos = llm(unicos, catalogo)
        except Exception:
            sugeridos = {}
        catalogo["llm"] = {**catalogo.get("llm", {}), **aplicar_sugerencia_llm(unicos, sugeridos)}
    doc_listo, sin_doc = reemplazar_objeto(doc, catalogo)
    if render_html is not None:
        html = render_html(doc_listo)
    html_listo, sin_html = reemplazar_texto(html, catalogo) if html is not None else (None, [])
    if render_html is not None:
        pendientes = list(sin_doc) + list(sin_html)
    else:
        restos = Counter(sin_html)
        for token in sin_doc:
            if restos[token]:
                restos[token] -= 1
        pendientes = list(sin_doc) + list(restos.elements())
    metadata = dict(doc_listo.get("metadata") or {})
    metadata["placeholders_count"] = len(pendientes)
    doc_listo["metadata"] = metadata
    doc_listo["placeholders"] = pendientes
    return doc_listo, html_listo
