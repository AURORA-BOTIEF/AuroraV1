"""Trazabilidad de referentes de fichero (verificaciones A1 y B1).

Regla de tres niveles
---------------------
1. **Declarado** en una fuente (temario, manual, documentos): se afirma.
2. **Derivable / autocerrado**: el propio laboratorio lo crea antes de usarlo: se afirma.
3. **No declarado ni derivable**: no se afirma. Debe omitirse o marcarse con un
   marcador visible (``[POR CONFIRMAR]`` y similares).

El fallo que combate este módulo: un plan o un laboratorio que **nombra ficheros,
rutas o carpetas que ninguna fuente aporta**. Medición real (16/10/2026): el plan
generado contenía ``Demanda_Historica.xlsx``, ``C:\\Forecasting_Logistica\\`` y
``Practica1_MAPE_SKU.xlsx``, ausentes del temario y del manual.

Alcance de la fase 1
--------------------
Solo **referentes de fichero** (rutas y nombres con extensión). Las URL quedan
fuera a propósito: una URL inventada se combate comprobando que esté viva, no
buscándola en el temario, así que pertenece a la verificación C1. Las versiones y
las entidades con nombre llegan en la fase 3.

Sin dependencias externas: solo biblioteca estándar.
"""

import os
import re
import unicodedata

# --------------------------------------------------------------------------- #
# Patrones
# --------------------------------------------------------------------------- #

_EXTENSIONES = (
    "xlsx|xlsm|xls|csv|tsv|md|pbix|pbit|ps1|psm1|py|ipynb|json|txt|zip|rar|7z|"
    "png|jpg|jpeg|gif|svg|docx|doc|pptx|ppt|pdf|sql|sh|bat|cmd|yaml|yml|log|"
    "evtx|pem|pfx|cer|key|bak|db|sqlite|parquet|xml|html|css|js|ts"
)

_FICHERO_RE = re.compile(
    r"(?<![\w.\-\\/])"
    r"(?P<nombre>[A-Za-z0-9_\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00c1\u00c9\u00cd\u00d3\u00da\u00d1]"
    r"[A-Za-z0-9_.\-\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00c1\u00c9\u00cd\u00d3\u00da\u00d1]*)"
    r"\.(?P<ext>" + _EXTENSIONES + r")",
    re.IGNORECASE,
)

_RUTA_WINDOWS_RE = re.compile(r"(?<![\w])[A-Za-z]:\\[^\s`\"'<>|*?]+")
_RUTA_UNC_RE = re.compile(r"\\\\[^\s`\"'<>|*?]+")
_RUTA_UNIX_RE = re.compile(r"(?<![\w])/(?:[\w.\-]+/)+[\w.\-]+")

# Las URL quedan FUERA a propósito de la fase 1. Una URL inventada se combate
# comprobando que esté viva (verificación C1), no buscándola en el temario. Si no se
# neutralizan antes de extraer, su cola («/support.microsoft.com/es-es/office/...»)
# se confunde con una ruta local y genera falsos positivos.
_URL_RE = re.compile(r"https?://[^\s`\"'<>\)\]]+")

# Los marcadores visibles ya expresan «dato no declarado»: no son un referente.
_MARCADOR_RE = re.compile(r"\[[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d10-9 _/\-]{3,}\]|<[a-z_]{3,}>")

# Verbos que introducen (crean) un fichero. Si la primera aparición de un
# referente no declarado está en este contexto, el laboratorio lo crea: es válido.
#
# Se escriben en su forma NORMALIZADA (sin acentos) y se comparan por palabra
# completa. Comparar por subcadena haría que «general» activase «genera» y la
# comprobación quedaría vacua.
_VERBOS_CREACION = (
    "crea", "crear", "creas", "creara", "crearas", "creacion",
    "guarda", "guardar", "guardaras", "guardar como",
    "genera", "generar", "generaras", "generacion",
    "exporta", "exportar", "exportaras", "exportacion",
    "descarga", "descargar", "descargaras",
    "construye", "elabora", "escribe", "nombra", "renombra", "renombrar",
    "adjunta", "nuevo archivo", "nueva hoja", "crear una copia",
)

_VERBOS_CREACION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(v) for v in _VERBOS_CREACION) + r")\b"
)

_VENTANA_CONTEXTO = 260


# --------------------------------------------------------------------------- #
# Normalización
# --------------------------------------------------------------------------- #

def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y con separadores unificados (``\\`` y ``_`` → espacio)."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower().replace("\\", "/")
    texto = re.sub(r"[\s_]+", " ", texto)
    return texto


def canonico(referente: str) -> str:
    """Forma canónica de un referente para comparar sin falsos negativos.

    A diferencia de :func:`normalizar`, aquí los ``_`` y los ``.`` **se conservan**:
    ``Demanda_Historica.xlsx`` no debe confundirse con «demanda histórica».
    """
    if not referente:
        return ""
    texto = unicodedata.normalize("NFD", str(referente))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower().replace("\\", "/").strip(" \t.`\"'()[],;:*")
    return texto


def quitar_marcadores(texto: str) -> str:
    """Sustituye los marcadores visibles por espacios (misma longitud)."""
    return _MARCADOR_RE.sub(lambda m: " " * len(m.group(0)), texto or "")


# --------------------------------------------------------------------------- #
# Extracción
# --------------------------------------------------------------------------- #

def extraer_referentes(texto: str) -> list[dict]:
    """Referentes de fichero de ``texto``, en orden de aparición y sin duplicados.

    Cada elemento: ``{"tipo": "ruta"|"fichero", "valor": str, "inicio": int}``.
    """
    if not texto:
        return []
    # Se neutralizan primero los marcadores (ya expresan «sin confirmar») y las URL
    # (fuera de alcance): ambos con espacios, para no desplazar los índices.
    limpio = _URL_RE.sub(lambda m: " " * len(m.group(0)), quitar_marcadores(texto))

    hallados: list[dict] = []
    vistos: set[str] = set()

    def anadir(tipo: str, valor: str, inicio: int) -> None:
        # La puntuación de la frase no forma parte del referente:
        # «... en C:\Datos\.» no es la ruta «C:\Datos\.».
        valor = valor.rstrip(".,;:")
        clave = canonico(valor)
        if not clave or clave in vistos:
            return
        vistos.add(clave)
        hallados.append({"tipo": tipo, "valor": valor, "inicio": inicio})

    for patron, tipo in (
        (_RUTA_WINDOWS_RE, "ruta"),
        (_RUTA_UNC_RE, "ruta"),
        (_RUTA_UNIX_RE, "ruta"),
    ):
        for m in patron.finditer(limpio):
            anadir(tipo, m.group(0), m.start())

    for m in _FICHERO_RE.finditer(limpio):
        anadir("fichero", m.group(0), m.start())

    hallados.sort(key=lambda r: r["inicio"])
    return hallados


def claves_de(referente: dict) -> list[str]:
    """Claves con las que se considera declarado un referente.

    Un fichero se declara por su nombre completo. Una ruta se declara por la ruta
    completa **o** por el nombre de su último componente (el directorio puede
    estar descrito aparte).
    """
    valor = referente["valor"]
    claves = [canonico(valor)]
    if referente["tipo"] == "ruta":
        nombre = os.path.basename(valor.replace("\\", "/").rstrip("/"))
        if nombre:
            claves.append(canonico(nombre))
    return [c for c in claves if c]


# --------------------------------------------------------------------------- #
# Auditoría del plan (A1)
# --------------------------------------------------------------------------- #

_CAMPOS_IGNORADOS = ("generated_at", "referential_integrity")


def _textos_del_plan(plan: dict) -> list[tuple[str, str]]:
    """Pares ``(campo, texto)`` del plan, para saber dónde está cada referente."""
    salida: list[tuple[str, str]] = []

    def recorrer(objeto, camino: str) -> None:
        if isinstance(objeto, dict):
            for clave, valor in objeto.items():
                if clave in _CAMPOS_IGNORADOS:
                    continue
                recorrer(valor, f"{camino}.{clave}" if camino else str(clave))
        elif isinstance(objeto, list):
            for i, valor in enumerate(objeto):
                recorrer(valor, f"{camino}[{i}]")
        elif isinstance(objeto, str) and objeto.strip():
            salida.append((camino, objeto))

    recorrer(plan, "")
    return salida


def auditar_plan(plan: dict, fuentes: str) -> dict:
    """A1: todo referente de fichero del plan debe estar en las fuentes.

    Args:
        plan: plan maestro ya construido.
        fuentes: texto de temario + manual + documentos, concatenado.

    Returns:
        ``{"total": n, "violaciones": [{"campo", "valor"}], "ok": bool}``
    """
    fuentes_norm = canonico(fuentes)
    violaciones: list[dict] = []
    vistos: set[str] = set()
    total = 0

    for campo, texto in _textos_del_plan(plan or {}):
        for referente in extraer_referentes(texto):
            total += 1
            claves = claves_de(referente)
            if any(clave and clave in fuentes_norm for clave in claves):
                continue
            if referente["valor"] in vistos:
                continue
            vistos.add(referente["valor"])
            violaciones.append({"campo": campo, "valor": referente["valor"]})

    return {"total": total, "violaciones": violaciones, "ok": not violaciones}


# --------------------------------------------------------------------------- #
# Auditoría de un laboratorio (B1)
# --------------------------------------------------------------------------- #

def _limites_de_paso(texto: str, posicion: int) -> tuple[int, int]:
    """Inicio y fin del bloque que contiene ``posicion``.

    El bloque es el «paso» (delimitado por encabezados) o el párrafo.
    """
    inicio = texto.rfind("\n###", 0, posicion)
    inicio = 0 if inicio == -1 else inicio
    fin = texto.find("\n###", posicion)
    fin = len(texto) if fin == -1 else fin
    return inicio, fin


def _es_creacion(texto: str, referente: dict) -> bool:
    """¿La aparición del referente está en un contexto de creación?

    El contexto es deliberadamente estrecho: la línea de encabezado del paso (que
    declara la intención, p. ej. «### Paso 3: Crear un informe») más una ventana
    alrededor del referente. **No** se acepta cualquier verbo presente en el
    cuerpo del paso: si se aceptase, un paso que dice «crearás un informe»
    blanquearía todos los ficheros que ese paso inventa, y la comprobación sería
    vacua.
    """
    inicio_paso, _ = _limites_de_paso(texto, referente["inicio"])
    fin_encabezado = texto.find("\n", inicio_paso)
    if fin_encabezado == -1:
        fin_encabezado = len(texto)
    encabezado = texto[inicio_paso:fin_encabezado]

    desde = max(0, referente["inicio"] - _VENTANA_CONTEXTO)
    hasta = min(len(texto), referente["inicio"] + len(referente["valor"]) + _VENTANA_CONTEXTO)

    contexto = normalizar(encabezado + " " + texto[desde:hasta])
    return bool(_VERBOS_CREACION_RE.search(contexto))


def auditar_laboratorio(laboratorio_md: str, fuentes: str, plan: str = "") -> dict:
    """B1: todo fichero referenciado debe estar declarado o haberse creado antes.

    Recorre las apariciones **en orden**. Una aparición es válida si el referente
    ya se introdujo antes en el propio laboratorio, si está declarado en las
    fuentes o en el plan, o si la aparición está en un contexto de creación.

    No cubre las referencias a laboratorios **posteriores** (verificación B2) ni
    los ficheros introducidos en laboratorios **anteriores**: eso necesita el
    conjunto completo y pertenece a la fase 2.
    """
    fuentes_norm = canonico(fuentes)
    plan_norm = canonico(plan)
    violaciones: list[dict] = []
    conocidos: set[str] = set()

    for referente in extraer_referentes(laboratorio_md or ""):
        claves = claves_de(referente)
        if any(clave in conocidos for clave in claves):
            conocidos.update(claves)
            continue
        if any(clave and (clave in fuentes_norm or clave in plan_norm) for clave in claves):
            conocidos.update(claves)
            continue
        if _es_creacion(laboratorio_md, referente):
            conocidos.update(claves)
            continue
        violaciones.append(
            {
                "valor": referente["valor"],
                "tipo": referente["tipo"],
                "inicio": referente["inicio"],
            }
        )

    return {"total": len(conocidos), "violaciones": violaciones, "ok": not violaciones}


def mensaje_de_correccion(violaciones: list[dict], ambito: str) -> str:
    """Instrucción para el reintento correctivo: omitir o marcar, nunca inventar."""
    if not violaciones:
        return ""
    if ambito == "plan":
        lineas = [f"- «{v['valor']}» (campo {v['campo']})" for v in violaciones[:20]]
        intro = (
            "El plan contiene ficheros o rutas que NO aparecen en el temario ni en el manual. "
            "Elimínalos o sustitúyelos por una descripción funcional; si el dato es "
            "imprescindible, escríbelo como [POR CONFIRMAR]. No inventes nombres de fichero."
        )
    else:
        lineas = [f"- «{v['valor']}»" for v in violaciones[:20]]
        intro = (
            "El laboratorio referencia ficheros o rutas que no están en el temario, ni en el "
            "manual, ni en el plan, y que no se crean en ningún paso anterior. Elimínalos, "
            "sustitúyelos por una descripción funcional, o crea el fichero explícitamente en un "
            "paso anterior. Si el dato es imprescindible, escríbelo como [POR CONFIRMAR]."
        )
    return intro + "\n" + "\n".join(lineas)
