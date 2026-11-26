"""Bracketed Setup Guide template tokens.

A token such as ``[VERSIÓN POR VALIDAR]`` is a blank, not course content.
The guide fills it from the outline, the lab plan, or the labs when that
value is already known. One optional model call may fill the rest. Anything
still blank is replaced with a bilingual neutral sentence so the PDF never
keeps the raw brackets. Those leftovers are the quality warning.
"""

from __future__ import annotations

import datetime
import json
import re
import unicodedata
from collections import Counter
from typing import Any, Callable, Optional

NEUTRO = "Verificar con el instructor / Verify with the instructor"
INSTRUCCION_CLAVE = (
    "Use la clave proporcionada por el instructor / Use the key provided by the instructor"
)

# Official vendor documentation. A row is used only when the course text names
# that product. These are not guessed per execution.
_PRODUCTOS = (
    {
        "nombres": ("copilot chat", "microsoft 365 copilot", "m365 copilot"),
        "url": "https://learn.microsoft.com/microsoft-365/copilot/",
        "download": "https://www.microsoft.com/microsoft-365/copilot",
        "support": "https://learn.microsoft.com/microsoft-365/copilot/",
        "license": (
            "Licencia de Microsoft 365 Copilot asignada al alumno. / "
            "Microsoft 365 Copilot license assigned to the learner."
        ),
    },
    {
        "nombres": ("github copilot",),
        "url": "https://docs.github.com/copilot",
        "download": "https://github.com/features/copilot",
        "support": "https://docs.github.com/copilot",
        "license": "Licencia de GitHub Copilot. / GitHub Copilot license.",
    },
    {
        "nombres": ("visual studio code", "vscode"),
        "url": "https://code.visualstudio.com/docs",
        "download": "https://code.visualstudio.com/download",
        "support": "https://code.visualstudio.com/docs",
        "license": "Licencia MIT de Visual Studio Code. / Visual Studio Code MIT license.",
    },
    {
        "nombres": ("python",),
        "url": "https://www.python.org/doc/",
        "download": "https://www.python.org/downloads/",
        "support": "https://www.python.org/doc/",
        "license": "Licencia PSF de Python. / Python PSF license.",
    },
    {
        "nombres": ("ubuntu",),
        "url": "https://ubuntu.com/download",
        "download": "https://ubuntu.com/download/desktop",
        "support": "https://ubuntu.com/download",
        "license": "Licencia de Ubuntu (código abierto). / Ubuntu open-source license.",
    },
    {
        "nombres": ("postgresql", "postgres"),
        "url": "https://www.postgresql.org/docs/",
        "download": "https://www.postgresql.org/download/",
        "support": "https://www.postgresql.org/docs/",
        "license": "Licencia PostgreSQL. / PostgreSQL license.",
    },
    {
        "nombres": ("docker",),
        "url": "https://docs.docker.com/get-started/",
        "download": "https://docs.docker.com/get-docker/",
        "support": "https://docs.docker.com/get-started/",
        "license": "Licencia de Docker según el plan del instructor. / Docker license for the instructor's plan.",
    },
    {
        "nombres": ("git",),
        "url": "https://git-scm.com/doc",
        "download": "https://git-scm.com/downloads",
        "support": "https://git-scm.com/doc",
        "license": "Licencia GPL de Git. / Git GPL license.",
    },
    {
        "nombres": ("node.js", "nodejs"),
        "url": "https://nodejs.org/en/docs",
        "download": "https://nodejs.org/en/download",
        "support": "https://nodejs.org/en/docs",
        "license": "Licencia MIT de Node.js. / Node.js MIT license.",
    },
    {
        "nombres": ("microsoft 365", "office 365"),
        "url": "https://learn.microsoft.com/microsoft-365/",
        "download": "https://www.microsoft.com/microsoft-365",
        "support": "https://learn.microsoft.com/microsoft-365/",
        "license": "Licencia de Microsoft 365. / Microsoft 365 license.",
    },
)

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
        if clave in ("placeholders", "template_tokens"):
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


def _corpus(*partes) -> str:
    trozos = []
    for parte in partes:
        if isinstance(parte, str):
            trozos.append(parte)
        elif isinstance(parte, dict):
            trozos.append(json.dumps(parte, ensure_ascii=False, default=str))
    return "\n".join(trozos)


def _nombre_en(nombre: str, plano: str) -> bool:
    return re.search(
        r"(?:^|[^a-z0-9])" + re.escape(nombre) + r"(?:[^a-z0-9]|$)",
        plano or "",
    ) is not None


def _productos_en(texto: str) -> list:
    plano = _norm(texto)
    hallados = []
    for producto in _PRODUCTOS:
        if any(_nombre_en(nombre, plano) for nombre in producto["nombres"]):
            hallados.append(producto)
    # A longer name wins over a shorter one that is its prefix ("copilot" vs "microsoft 365").
    hallados.sort(key=lambda item: max(len(nombre) for nombre in item["nombres"]), reverse=True)
    return hallados


def _comandos_de_labs(texto: str) -> list:
    comandos = []
    for bloque in re.findall(r"```[a-zA-Z0-9]*\n(.*?)```", texto or "", re.S):
        linea = next((fila.strip() for fila in bloque.splitlines() if fila.strip()), "")
        if linea and not tokens_en_texto(linea) and len(linea) <= 180:
            comandos.append(linea)
    for coincidencia in re.finditer(
        r"(?im)^(?:compruebe|verifique|valide|check|verify|prompt de prueba)\b.{0,180}",
        texto or "",
    ):
        linea = " ".join(coincidencia.group(0).split())
        if linea and not tokens_en_texto(linea):
            comandos.append(linea[:180])
    return comandos


def _urls_en(texto: str) -> list:
    halladas = []
    for url in re.findall(r"https?://[^\s)\]>'\"]+", texto or ""):
        limpia = url.rstrip(".,;")
        if "example.invalid" in limpia or tokens_en_texto(limpia):
            continue
        halladas.append(limpia)
    return halladas


def construir_catalogo(
    course_meta: dict,
    master_plan: dict,
    labs: dict,
    generated_on: Optional[str] = None,
    repo_url: Optional[str] = None,
) -> dict:
    """Values the course already stated, plus official docs for a named product."""
    meta = course_meta or {}
    plan = master_plan or {}
    texto_labs = "\n".join(str(cuerpo) for cuerpo in (labs or {}).values())
    corpus = _corpus(meta.get("title"), meta.get("description"), texto_labs, plan)
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
            ("command", item.get("validation") or item.get("test_command") or item.get("installation_notes")),
        ):
            valor = _concreto(origen)
            if valor and not ficha.get(destino):
                if destino == "command" and len(valor) > 180:
                    valor = valor[:180].rstrip()
                ficha[destino] = valor
    for nombre, ficha in list(software.items()):
        visible = str(item_name(nombre, plan))
        if not ficha.get("version"):
            version = _version_cerca(visible, texto_labs)
            if version:
                ficha["version"] = version
        if not ficha.get("command"):
            comando = _comando_cerca(visible, texto_labs)
            if comando:
                ficha["command"] = comando
        producto = _productos_en(visible)
        if producto:
            ficha.setdefault("source", producto[0]["url"])
            ficha.setdefault("download", producto[0]["download"])
            ficha.setdefault("license", producto[0]["license"])
    productos = _productos_en(corpus)
    producto = productos[0] if productos else None
    comandos = _comandos_de_labs(texto_labs)
    urls = _urls_en(corpus)
    if producto:
        urls.extend([producto["url"], producto["download"], producto["support"]])
    if repo_url:
        urls.append(repo_url)
    fecha = None
    for candidato in (
        meta.get("last_validation"),
        meta.get("validation_date"),
        (plan.get("validation") or {}).get("date") if isinstance(plan.get("validation"), dict) else None,
    ):
        fecha = _concreto(candidato)
        if fecha:
            break
    generada = (generated_on or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", generada):
        generada = datetime.datetime.utcnow().date().isoformat()
    return {
        "course_key": _concreto(meta.get("key")),
        "course_version": _concreto(meta.get("version")),
        "validation_date": fecha,
        "generated_on": generada,
        "software": software,
        "commands": comandos,
        "official_url": (producto or {}).get("url") or (urls[0] if urls else ""),
        "download_url": (producto or {}).get("download") or "",
        "support_url": (producto or {}).get("support") or "",
        "license": (producto or {}).get("license") or "",
        "repo_url": repo_url or "",
        "urls_permitidas": list(dict.fromkeys(urls)),
        "corpus": corpus[:8000],
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


def _ficha_de(fila: Optional[dict], catalogo: dict) -> dict:
    if not isinstance(fila, dict):
        return {}
    nombre = fila.get("name") or fila.get("capability") or ""
    return (catalogo.get("software") or {}).get(_norm(str(nombre))) or {}


def _buscar(token: str, fila: Optional[dict], catalogo: dict) -> Optional[str]:
    plano = _sin_acentos(token).upper()
    if "CLAVE COMPLETA" in plano:
        return INSTRUCCION_CLAVE
    if plano.strip("[]") == "V1.0" and catalogo.get("course_version"):
        return catalogo["course_version"]
    if "FECHA DE VALIDACION" in plano:
        return catalogo.get("generated_on") or datetime.datetime.utcnow().date().isoformat()
    ficha = _ficha_de(fila, catalogo)
    if "VERSION POR VALIDAR" in plano and ficha.get("version"):
        return ficha["version"]
    if "COMANDO DE PRUEBA" in plano:
        if ficha.get("command"):
            return ficha["command"]
        comandos = catalogo.get("commands") or []
        if comandos:
            return comandos[0]
    if "LICENCIA POR" in plano:
        if ficha.get("license"):
            return ficha["license"]
        if catalogo.get("license"):
            return catalogo["license"]
    if "ENLACE" in plano or "INSERTAR" in plano:
        if ficha.get("source"):
            return ficha["source"]
        if catalogo.get("official_url"):
            return catalogo["official_url"]
        if catalogo.get("repo_url"):
            return catalogo["repo_url"]
    sugerido = (catalogo.get("llm") or {}).get(token)
    return _relleno_aceptable(sugerido)


def _sustituir(texto: str, catalogo: dict, fila: Optional[dict], sin_relleno: list, rellenos: list) -> str:
    def cambio(coincidencia):
        interior = coincidencia.group(1)
        if not es_token_de_plantilla(interior):
            return coincidencia.group(0)
        token = f"[{interior.strip()}]"
        relleno = _buscar(token, fila, catalogo)
        if relleno:
            rellenos.append(token)
            return relleno
        sin_relleno.append(token)
        return NEUTRO

    return _TOKEN_RE.sub(cambio, texto)


def _fila_local(valor: dict, fila):
    if valor.get("name") and any(clave in valor for clave in ("version", "pending", "license", "source")):
        return valor
    if valor.get("capability"):
        return {"name": valor.get("capability"), **valor}
    return fila


def reemplazar_texto(texto: str, catalogo: dict) -> tuple:
    sin_relleno = []
    rellenos = []
    if texto is None:
        return texto, sin_relleno, rellenos
    return _sustituir(str(texto), catalogo, None, sin_relleno, rellenos), sin_relleno, rellenos


def reemplazar_objeto(nodo: Any, catalogo: dict) -> tuple:
    """Return the tree, the neutralized tokens, and the tokens that were filled."""
    sin_relleno = []
    rellenos = []

    def caminar(valor, fila=None, clave=None):
        if clave in ("placeholders", "template_tokens"):
            return valor
        if isinstance(valor, dict):
            fila_local = _fila_local(valor, fila)
            return {llave: caminar(item, fila_local, llave) for llave, item in valor.items()}
        if isinstance(valor, list):
            return [caminar(item, fila) for item in valor]
        if isinstance(valor, str):
            return _sustituir(valor, catalogo, fila, sin_relleno, rellenos)
        return valor

    return caminar(nodo), sin_relleno, rellenos


def mensaje_de_tokens(tokens: list, rellenados: int = 0, paso: str = "Setup Guide") -> str:
    cuentas = Counter(tokens)
    detalle = ", ".join(
        f"{token} x{cuenta}" if cuenta > 1 else token for token, cuenta in cuentas.items()
    ) or "ninguno / none"
    return (
        f"La {paso} se entregó. Tokens rellenados: {rellenados}. "
        f"Tokens neutralizados: {len(tokens)}: {detalle}. "
        f"The {paso} was delivered. Tokens filled: {rellenados}. "
        f"Tokens neutralized: {len(tokens)}: {detalle}."
    )


def quality_issue_de_tokens(tokens: list, rellenados: int = 0) -> Optional[dict]:
    if not tokens and not rellenados:
        return None
    if not tokens:
        return None
    return {
        "step": "InvokeSetupGuide",
        "severity": "warning",
        "deliverable": "Setup Guide",
        "error": mensaje_de_tokens(tokens, rellenados),
        "tokens_filled": rellenados,
        "tokens_neutralized": len(tokens),
    }


def _valor_de_modelo(token: str, valor: Any, catalogo: dict) -> Optional[str]:
    texto = _relleno_aceptable(valor)
    if not texto:
        return None
    if re.search(r"(?i)(api[_-]?key|secret|password|BEGIN PRIVATE|\bsk-[a-z0-9]|AKIA)", texto):
        return None
    plano = _sin_acentos(token).upper()
    if "CLAVE COMPLETA" in plano:
        return None
    if texto.startswith("http://") or texto.startswith("https://"):
        if texto not in set(catalogo.get("urls_permitidas") or []):
            return None
    if "VERSION" in plano or plano.strip("[]") == "V1.0":
        numero = re.search(r"\d+\.\d+(?:\.\d+)*", texto)
        corpus = catalogo.get("corpus") or ""
        if not numero or numero.group(0) not in corpus:
            return None
    if "COMANDO DE PRUEBA" in plano:
        corpus = (catalogo.get("corpus") or "").lower()
        conocidos = [cmd.lower() for cmd in (catalogo.get("commands") or [])]
        if texto.lower() not in conocidos and texto.lower() not in corpus:
            return None
    return texto


def aplicar_sugerencia_llm(tokens: list, sugeridos: Any, catalogo: Optional[dict] = None) -> dict:
    """Keep model values that are concrete, already in the course, and not secrets."""
    catalogo = catalogo or {}
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
        valor = _valor_de_modelo(token, sugeridos.get(token), catalogo)
        if valor:
            salida[token] = valor
    return salida


def _url_para_etiqueta(etiqueta: str, catalogo: dict) -> str:
    """Pick a URL the course already has. This document has no public URL."""
    plano = _norm(etiqueta)
    if "este documento" in plano or "this document" in plano or plano.startswith("setup guide"):
        return ""
    if any(palabra in plano for palabra in ("repositorio", "readme", "github", "capitulo")):
        return catalogo.get("repo_url") or catalogo.get("official_url") or ""
    if any(palabra in plano for palabra in ("instal", "download", "descarga", "archivo")):
        return catalogo.get("download_url") or catalogo.get("official_url") or ""
    if any(palabra in plano for palabra in ("soporte", "incidencia", "support")):
        return catalogo.get("support_url") or catalogo.get("official_url") or ""
    if any(palabra in plano for palabra in ("documentacion", "oficial", "official", "docs")):
        return catalogo.get("official_url") or ""
    return catalogo.get("official_url") or catalogo.get("repo_url") or ""


def asignar_enlaces(doc: dict, catalogo: dict) -> int:
    """Write known URLs into empty link fields before HTML turns them into tokens."""
    if not isinstance(doc, dict):
        return 0
    rellenos = 0

    def poner(objeto, etiqueta=""):
        nonlocal rellenos
        if not isinstance(objeto, dict) or objeto.get("url"):
            return
        url = _url_para_etiqueta(etiqueta or str(objeto.get("label") or ""), catalogo)
        if url:
            objeto["url"] = url
            rellenos += 1

    identificacion = doc.get("identification") or {}
    for enlace in identificacion.get("links") or []:
        poner(enlace)
    for enlace in doc.get("references") or []:
        poner(enlace)
    for fila in doc.get("software") or []:
        if not isinstance(fila, dict) or fila.get("source"):
            continue
        ficha = _ficha_de(fila, catalogo)
        url = ficha.get("source") or ficha.get("download") or ""
        if url:
            fila["source"] = url
            rellenos += 1
    for fila in doc.get("capabilities") or []:
        if not isinstance(fila, dict):
            continue
        acceso = fila.get("access")
        if isinstance(acceso, str) and not acceso:
            ficha = _ficha_de({"name": fila.get("capability") or fila.get("name")}, catalogo)
            url = ficha.get("source") or catalogo.get("official_url") or ""
            if url:
                fila["access"] = url
                rellenos += 1
        elif isinstance(acceso, dict):
            poner(acceso, etiqueta=str(fila.get("capability") or fila.get("name") or "repositorio"))
    for fila in doc.get("lab_matrix") or []:
        if isinstance(fila, dict):
            poner(fila.get("access") if isinstance(fila.get("access"), dict) else {}, etiqueta="repositorio")
    return rellenos


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
    enlaces_rellenos = asignar_enlaces(doc, catalogo)
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
        catalogo["llm"] = {
            **catalogo.get("llm", {}),
            **aplicar_sugerencia_llm(unicos, sugeridos, catalogo),
        }
    doc_listo, sin_doc, rellenos_doc = reemplazar_objeto(doc, catalogo)
    if render_html is not None:
        html = render_html(doc_listo)
    if html is not None:
        html_listo, sin_html, rellenos_html = reemplazar_texto(html, catalogo)
    else:
        html_listo, sin_html, rellenos_html = None, [], []
    if render_html is not None:
        pendientes = list(sin_doc) + list(sin_html)
        rellenos = list(rellenos_doc) + list(rellenos_html)
    else:
        restos = Counter(sin_html)
        for token in sin_doc:
            if restos[token]:
                restos[token] -= 1
        pendientes = list(sin_doc) + list(restos.elements())
        restos_ok = Counter(rellenos_html)
        for token in rellenos_doc:
            if restos_ok[token]:
                restos_ok[token] -= 1
        rellenos = list(rellenos_doc) + list(restos_ok.elements())
    metadata = dict(doc_listo.get("metadata") or {})
    metadata["placeholders_count"] = len(pendientes)
    metadata["tokens_filled"] = len(rellenos) + enlaces_rellenos
    metadata["tokens_neutralized"] = len(pendientes)
    doc_listo["metadata"] = metadata
    doc_listo["placeholders"] = pendientes
    doc_listo["template_tokens"] = {
        "filled": len(rellenos) + enlaces_rellenos,
        "neutralized": len(pendientes),
    }
    return doc_listo, html_listo


def sanear_plan_maestro(
    plan: dict,
    course_meta: Optional[dict] = None,
    labs: Optional[dict] = None,
) -> tuple:
    """Fill template tokens in the lab master plan, then neutralize the rest.

    Returns the plan and a quality warning when any token was neutralized.
    A failure must be caught by the caller so planning still saves the plan.
    """
    catalogo = construir_catalogo(course_meta or {}, plan or {}, labs or {})
    saneado, neutralizados, rellenos = reemplazar_objeto(plan or {}, catalogo)
    if not isinstance(saneado, dict):
        saneado = {}
    saneado["template_tokens"] = {
        "filled": len(rellenos),
        "neutralized": len(neutralizados),
        "placeholders": list(neutralizados),
    }
    hallazgo = None
    if neutralizados:
        hallazgo = {
            "step": "InvokeLabPlanner",
            "severity": "warning",
            "deliverable": "",
            "error": mensaje_de_tokens(
                neutralizados,
                len(rellenos),
                paso="plan de laboratorios / lab master plan",
            ),
            "tokens_filled": len(rellenos),
            "tokens_neutralized": len(neutralizados),
        }
    return saneado, hallazgo
