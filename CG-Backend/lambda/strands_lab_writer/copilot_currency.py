"""Currency check for Microsoft 365 Copilot surfaces named in a lab.

A lab may name a Copilot feature, agent, or button only when this catalog
(verified against official documentation) or the uploaded manual resolves it.
Deprecated names and names that are not in either source block the lab.
Preview and template entries also block when the lab never states the
availability the catalog requires (Frontier, plantilla, and so on).

``COPILOT_CATALOG_RETRIEVAL=1`` refreshes each catalog row from its ``doc_url``
before the check. The default is off: generation does not call the network.
Tests pass a fake fetcher and never open a socket.

The catalog file is ``copilot_feature_catalog.json`` next to this module.
Add a row only with a doc URL taken from current official Microsoft docs.
"""

from __future__ import annotations

import copy
import json
import os
import re
import unicodedata
from pathlib import Path

_CATALOG_PATH = Path(__file__).with_name("copilot_feature_catalog.json")
_CACHE: dict | None = None

# Single-word aliases match only when one of these sits within the window.
# "Frontier" is not a cue: the match would always succeed on its own name.
_PISTAS = (
    "copilot",
    "microsoft 365",
    "m365",
    "agente",
    "agent",
)
_RADIO = 80
_RADIO_UI = 240

# Words that are host apps or ordinary buttons, not a Copilot surface.
_GENERICOS = {
    "chat", "studio", "lab", "labs", "pro", "premium", "microsoft", "excel",
    "word", "powerpoint", "teams", "outlook", "windows", "edge", "loop",
    "onenote", "sharepoint", "onedrive", "forms", "whiteboard", "copilot",
    "siguiente", "anterior", "continuar", "cancelar", "aceptar", "cerrar",
    "guardar", "enviar", "next", "back", "cancel", "ok", "close", "save",
    "send", "nuevo", "nueva", "new", "abrir", "open", "inicio", "home",
    "agentes", "agents", "mas", "more", "ayuda", "help", "buscar", "search",
    "configuracion", "settings", "opciones", "options", "menu", "archivo",
    "archivos", "documento", "documentos", "mensaje", "mensajes",
    "conversacion", "file", "files", "ver", "mostrar", "show", "view",
    "editar", "edit", "eliminar", "delete", "agregar", "add", "insertar",
    "insert", "crear", "hacer", "clic", "click", "seleccionar", "pulsar",
    "yes", "si", "no",
}

_DESPUES_DE_COPILOT = re.compile(
    r"\bCopilot\s+([A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'-]*"
    r"(?:\s+[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'-]*){0,3})"
)
_AGENTE = re.compile(
    r"\b(?:agente|agent|Agente|Agent)\s+(?:de\s+|del\s+|of\s+)?"
    r"([A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'-]*"
    r"(?:\s+[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'-]*){0,3})"
)
_ETIQUETA_UI = re.compile(
    r"(?:bot[oó]n|button|pesta[nñ]a|tab|men[uú]|menu|panel)\s+"
    r"[\"“«']([^\"”»'\n]{2,60})[\"”»']",
    re.IGNORECASE,
)
_RETIRADO_EN_PAGINA = (
    "is deprecated",
    "has been retired",
    "was retired",
    "no longer available",
    "ya no esta disponible",
    "esta en desuso",
)

_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "yes", "on")


def _plegar(texto: str) -> str:
    """Case- and accent-folded text, with collapsed whitespace."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin.casefold().split())


def cargar_catalogo(ruta: str | Path | None = None) -> dict:
    """Load the versioned catalog. The default path is cached."""
    global _CACHE
    if ruta is not None:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    if _CACHE is None:
        _CACHE = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return _CACHE


def recuperacion_habilitada() -> bool:
    """True only when ``COPILOT_CATALOG_RETRIEVAL`` is explicitly on."""
    return os.getenv("COPILOT_CATALOG_RETRIEVAL", "0").strip().lower() in _ENCENDIDO


def fetcher_http(url: str) -> str:
    """GET a documentation page. Used only when retrieval is enabled."""
    import urllib.request

    solicitud = urllib.request.Request(
        url,
        headers={"User-Agent": "AuroraCatalogRefresh/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(solicitud, timeout=8) as respuesta:
        return respuesta.read(200_000).decode("utf-8", "replace")


def aplicar_recuperacion(catalogo: dict, fetcher) -> dict:
    """Return a copy of the catalog adjusted by each feature's doc page.

    A page that no longer contains the canonical name marks the row
    ``unresolved`` (uses of that name then block). A retirement phrase next
    to the name marks an available or preview row ``deprecated``. A fetch
    error leaves the checked-in status alone and records the error: a
    network failure must not invent a deprecation.
    """
    copia = copy.deepcopy(catalogo)
    for feature in copia.get("features") or []:
        url = feature.get("doc_url") or ""
        if not url:
            continue
        try:
            pagina = fetcher(url)
        except Exception as exc:  # noqa: BLE001 - the caller decides the fetcher
            feature["retrieval"] = {"ok": False, "error": type(exc).__name__}
            continue
        if not pagina:
            feature["retrieval"] = {"ok": False, "error": "empty"}
            continue
        doblada = _plegar(pagina)
        nombre = _plegar(feature.get("canonical_name") or "")
        if not nombre or nombre not in doblada:
            feature["status"] = "unresolved"
            feature["retrieval"] = {"ok": True, "nombre_en_pagina": False}
            continue
        inicio = doblada.find(nombre)
        ventana = doblada[max(0, inicio - 160): inicio + len(nombre) + 160]
        if any(marca in ventana for marca in _RETIRADO_EN_PAGINA):
            if feature.get("status") in ("available", "preview"):
                feature["status"] = "deprecated"
                feature["retrieval"] = {
                    "ok": True, "nombre_en_pagina": True, "marca": "retired",
                }
                continue
        feature["retrieval"] = {"ok": True, "nombre_en_pagina": True}
    copia["retrieval_aplicada"] = True
    return copia


def _pistas_de(feature: dict) -> tuple[str, ...]:
    extra = tuple(_plegar(p) for p in (feature.get("context_cues_extra") or []))
    return _PISTAS + extra


def _hay_pista(texto: str, inicio: int, fin: int, feature: dict, radio: int = _RADIO) -> bool:
    ventana = _plegar(texto[max(0, inicio - radio): min(len(texto), fin + radio)])
    return any(pista in ventana for pista in _pistas_de(feature))


def _linea(texto: str, inicio: int) -> str:
    anterior = texto.rfind("\n", 0, inicio)
    siguiente = texto.find("\n", inicio)
    if siguiente < 0:
        siguiente = len(texto)
    return texto[anterior + 1: siguiente]


def _excluida(feature: dict, texto: str, inicio: int) -> bool:
    linea = _plegar(_linea(texto, inicio))
    return any(_plegar(marca) in linea for marca in (feature.get("exclude_if") or []))


def _compilar(alias: str, sensible: bool):
    banderas = 0 if sensible else re.IGNORECASE
    return re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", banderas)


def _alias_de(feature: dict) -> list[tuple[str, bool]]:
    """(alias, case-sensitive). Longer aliases are matched first by the caller."""
    pares = [(alias, False) for alias in feature.get("aliases") or []]
    pares += [(alias, True) for alias in feature.get("aliases_sensitive") or []]
    return pares


def _es_generico(frase: str) -> bool:
    palabras = _plegar(frase).split()
    return not palabras or all(palabra in _GENERICOS for palabra in palabras)


def _es_titulo(frase: str) -> bool:
    palabras = [p for p in frase.split() if any(c.isalpha() for c in p)]
    if len(palabras) < 2:
        return False
    return all(p[:1].isupper() for p in palabras)


def _unicos(items: list, clave) -> list:
    vistos = set()
    salida = []
    for item in items:
        marca = clave(item)
        if marca in vistos:
            continue
        vistos.add(marca)
        salida.append(item)
    return salida


def _solapa(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _en_manual(frase: str, manual: str) -> bool:
    clave = _plegar(frase)
    return len(clave) >= 4 and clave in _plegar(manual)


def _alias_conocido(frase: str, features: list[dict]) -> bool:
    clave = _plegar(frase)
    for feature in features:
        for alias, _sensible in _alias_de(feature):
            if _plegar(alias) == clave:
                return True
    return False


def _coincidencias(texto: str, features: list[dict]) -> list[dict]:
    """Catalog hits. A longer alias wins when two hits cover the same span."""
    crudas = []
    for feature in features:
        for alias, sensible in _alias_de(feature):
            palabras = alias.split()
            # A single token is ambiguous (Analyst, Workflows, Frontier).
            exige_pista = len(palabras) < 2 or bool(feature.get("aliases_sensitive") and sensible)
            if len(palabras) >= 2 and not sensible:
                exige_pista = False
            for hallazgo in _compilar(alias, sensible).finditer(texto):
                if _excluida(feature, texto, hallazgo.start()):
                    continue
                if exige_pista and not _hay_pista(texto, hallazgo.start(), hallazgo.end(), feature):
                    continue
                crudas.append(
                    {
                        "feature": feature,
                        "nombre": hallazgo.group(0),
                        "span": (hallazgo.start(), hallazgo.end()),
                        "alias": alias,
                    }
                )
    crudas.sort(key=lambda item: (item["span"][0], -(item["span"][1] - item["span"][0])))
    aceptadas = []
    for item in crudas:
        if any(_solapa(item["span"], previo["span"]) for previo in aceptadas):
            continue
        aceptadas.append(item)
    return aceptadas


def _candidatos_desconocidos(texto: str) -> list[dict]:
    """Narrow surface shapes: a title after Copilot, an agent name, a button label."""
    vistos = []

    def agregar(nombre: str, span: tuple[int, int], origen: str, exige_pista_ui: bool = False):
        limpio = " ".join((nombre or "").split())
        if not limpio or _es_generico(limpio):
            return
        if origen == "ui" and not _es_titulo(limpio):
            return
        if exige_pista_ui and not re.search(
            r"copilot|microsoft\s*365|\bm365\b",
            texto[max(0, span[0] - _RADIO_UI): span[1] + _RADIO_UI],
            re.IGNORECASE,
        ):
            return
        vistos.append({"nombre": limpio, "span": span, "origen": origen})

    for hallazgo in _DESPUES_DE_COPILOT.finditer(texto):
        agregar(hallazgo.group(1), hallazgo.span(1), "copilot")
    for hallazgo in _AGENTE.finditer(texto):
        agregar(hallazgo.group(1), hallazgo.span(1), "agente")
    for hallazgo in _ETIQUETA_UI.finditer(texto):
        agregar(hallazgo.group(1), hallazgo.span(1), "ui", exige_pista_ui=True)
    return vistos


def _requisito_incumplido(feature: dict, corpus: str) -> str:
    frases = feature.get("requires_any") or []
    if not frases:
        return ""
    doblado = _plegar(corpus)
    if any(_plegar(frase) in doblado for frase in frases):
        return ""
    return ", ".join(frases)


def auditar_superficies_copilot(
    texto: str,
    *,
    manual: str = "",
    catalogo: dict | None = None,
    fetcher=None,
    recuperar: bool | None = None,
) -> dict:
    """Resolve Copilot surfaces in ``texto``.

    ``recuperar`` defaults to the environment flag. When it is on and
    ``fetcher`` is omitted, the HTTP fetcher runs. When it is off, ``fetcher``
    is not called.
    """
    base = catalogo or cargar_catalogo()
    if recuperar is None:
        recuperar = recuperacion_habilitada()
    if recuperar:
        base = aplicar_recuperacion(base, fetcher or fetcher_http)
    features = list(base.get("features") or [])
    corpus = f"{texto or ''}\n{manual or ''}"
    hallazgos = []
    resueltos = []
    spans = []

    for golpe in _coincidencias(texto or "", features):
        feature = golpe["feature"]
        spans.append(golpe["span"])
        estado = feature.get("status") or "available"
        comun = {
            "nombre": feature.get("canonical_name") or golpe["nombre"],
            "id": feature.get("id"),
            "doc_url": feature.get("doc_url") or "",
            "verificacion": "C6",
            "confianza": "alta",
        }
        if estado in ("deprecated", "unresolved"):
            hallazgos.append(
                {
                    **comun,
                    "tipo": "deprecated" if estado == "deprecated" else "unknown",
                    "bloquea": True,
                    "reemplazo": feature.get("replaced_by") or "",
                    "detalle": feature.get("availability") or "",
                }
            )
            continue
        # Preview is verified, but only where the catalog's availability holds.
        falta = _requisito_incumplido(feature, corpus) if estado == "preview" else ""
        if falta:
            hallazgos.append(
                {
                    **comun,
                    "tipo": "disponibilidad",
                    "bloquea": True,
                    "reemplazo": "",
                    "detalle": falta,
                }
            )
            continue
        resueltos.append(
            {
                "nombre": comun["nombre"],
                "id": feature.get("id"),
                "status": estado,
                "doc_url": comun["doc_url"],
                "fuente": "catalogo",
            }
        )

    for candidato in _candidatos_desconocidos(texto or ""):
        if any(_solapa(candidato["span"], span) for span in spans):
            continue
        if _alias_conocido(candidato["nombre"], features):
            continue
        if _en_manual(candidato["nombre"], manual or ""):
            resueltos.append(
                {
                    "nombre": candidato["nombre"],
                    "id": "",
                    "status": "manual",
                    "doc_url": "",
                    "fuente": "manual",
                }
            )
            continue
        hallazgos.append(
            {
                "nombre": candidato["nombre"],
                "id": "",
                "doc_url": "",
                "verificacion": "C6",
                "confianza": "alta",
                "tipo": "unknown",
                "bloquea": True,
                "reemplazo": "",
                "detalle": f"Mención {candidato['origen']} sin entrada de catálogo ni manual.",
            }
        )

    hallazgos = _unicos(
        hallazgos, lambda h: (h.get("tipo"), h.get("id") or "", _plegar(h.get("nombre") or ""))
    )
    resueltos = _unicos(resueltos, lambda r: (r.get("id") or "", _plegar(r.get("nombre") or ""), r.get("fuente")))
    bloqueos = [h for h in hallazgos if h.get("bloquea")]
    return {
        "check": "C6",
        "catalog_version": base.get("catalog_version") or "",
        "retrieval_aplicada": bool(base.get("retrieval_aplicada")),
        "ok": not bloqueos,
        "hallazgos": hallazgos,
        "resueltos": resueltos,
    }


def mensaje_de_correccion_moneda(hallazgos: list[dict]) -> str:
    """Spanish retry instruction. The rejected name must not survive."""
    if not hallazgos:
        return ""
    lineas = []
    for hallazgo in hallazgos[:20]:
        nombre = hallazgo.get("nombre") or ""
        tipo = hallazgo.get("tipo")
        if tipo == "deprecated":
            reemplazo = hallazgo.get("reemplazo") or "[POR CONFIRMAR]"
            fuente = hallazgo.get("doc_url") or "[ENLACE OFICIAL]"
            lineas.append(
                f"- «{nombre}» está retirado. Sustitúyelo por «{reemplazo}» "
                f"y borra el nombre viejo. Fuente: {fuente}."
            )
        elif tipo == "disponibilidad":
            lineas.append(
                f"- «{nombre}» solo puede usarse si el laboratorio declara su "
                f"disponibilidad ({hallazgo.get('detalle') or 'la del catálogo'}). "
                f"Si no puedes declararla, escribe [POR CONFIRMAR] y borra el nombre."
            )
        else:
            lineas.append(
                f"- «{nombre}» no está en el catálogo verificado ni en el manual. "
                f"Usa un nombre del catálogo o escribe [POR CONFIRMAR] y borra el nombre inventado."
            )
    intro = (
        "Estas superficies de Microsoft 365 Copilot no están resueltas contra la "
        "documentación oficial. Corrige el laboratorio sin conservar el nombre rechazado:"
    )
    return intro + "\n" + "\n".join(lineas)


def texto_de_catalogo_para_prompt(is_spanish: bool, catalogo: dict | None = None) -> str:
    """Standing rule for the live lab prompt, generated from the catalog."""
    base = catalogo or cargar_catalogo()
    version = base.get("catalog_version") or ""
    disponibles = []
    vistas = []
    retirados = []
    for feature in base.get("features") or []:
        nombre = feature.get("canonical_name") or ""
        estado = feature.get("status")
        if estado == "deprecated":
            reemplazo = feature.get("replaced_by") or "[POR CONFIRMAR]"
            retirados.append(f"{nombre} → {reemplazo}")
        elif estado == "preview":
            vistas.append(nombre)
        elif estado == "available" and feature.get("kind") == "template":
            disponibles.append(f"{nombre} (plantilla)")
        elif estado == "available":
            disponibles.append(nombre)
    if is_spanish:
        return (
            f"SUPERFICIES DE MICROSOFT 365 COPILOT (REQUISITO DURO, catálogo {version}):\n"
            f"Solo puedes nombrar estas superficies verificadas: {', '.join(disponibles)}.\n"
            f"Estas exigen que el laboratorio declare su disponibilidad "
            f"(plantilla, Frontier, vista previa): {', '.join(vistas)}.\n"
            f"Retiradas, no las presentes como interfaz actual: {', '.join(retirados)}.\n"
            "Cualquier otro agente, botón o característica de Copilot se escribe como "
            "[POR CONFIRMAR]. No inventes nombres de UI.\n"
        )
    return (
        f"MICROSOFT 365 COPILOT SURFACES (HARD REQUIREMENT, catalog {version}):\n"
        f"You may name only these verified surfaces: {', '.join(disponibles)}.\n"
        f"These require the lab to state their availability "
        f"(template, Frontier, preview): {', '.join(vistas)}.\n"
        f"Retired, do not present them as the current UI: {', '.join(retirados)}.\n"
        "Any other Copilot agent, button, or feature is written as [POR CONFIRMAR]. "
        "Do not invent UI names.\n"
    )


def construir_informe_moneda(informes: dict, catalog_version: str = "") -> dict:
    """JSON document stored next to the other lab validation reports."""
    bloqueos = sum(
        1
        for informe in informes.values()
        for hallazgo in informe.get("hallazgos") or []
        if hallazgo.get("bloquea")
    )
    if not catalog_version:
        for informe in informes.values():
            catalog_version = informe.get("catalog_version") or ""
            if catalog_version:
                break
    return {
        "check": "C6",
        "catalog_version": catalog_version,
        "labs": len(informes),
        "total_bloqueos": bloqueos,
        "ok": bloqueos == 0,
        "por_laboratorio": informes,
    }
