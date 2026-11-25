"""Auditoría posterior del curso: manifiesto de entradas con hash y enlaces.

Se ejecuta después de la Setup Guide. Escribe dos artefactos en ``{proyecto}/labguide/``:

- ``inputs-manifest.json``: SHA-256 de las entradas (temario, manual, petición) y de
  las salidas (plan, laboratorios, guía). En una actualización permite saber qué
  cambió sin comparar el curso entero a mano.
- ``enlaces.json``: enlaces públicos de los laboratorios con su estado. Solo se
  marcan como muertos los 404/410 y los dominios inexistentes; 403/429/5xx y los
  timeouts son «no verificables»: el servidor existe y puede estar bloqueando bots.

Un enlace muerto es una compuerta: la lambda sigue respondiendo 200 (el informe
queda escrito) y devuelve ``gate.bloquea``. Step Functions lee ese campo y manda
el curso a ``NotifyFailure``. No se lanza una excepción: el ``Catch`` del estado
sigue yendo a ``NotifyCompletion`` cuando la lambda falla de verdad, y eso no
debe tragarse el caso de los enlaces muertos. ``LINK_AUDIT_GATE=0`` deja el
informe como evidencia y pone ``bloquea`` en falso.

Medido el 26/10/2026 sobre 1.313 laboratorios: 5.150 enlaces públicos, 3.870 vivos,
831 muertos y 449 no verificables. La mayoría de los 831 del crudo eran IPs privadas,
servicios internos, namespaces XML y plantillas; de ahí los filtros.
"""

import concurrent.futures
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
BUCKET_POR_DEFECTO = os.getenv("COURSE_BUCKET", "crewai-course-artifacts")

URL = re.compile(r"https?://[^\s)\]\"'<>`]+")
PLANTILLA = re.compile(r"[$\[\]{}<>]|\.\.\.|xxx|placeholder|tu-usuario|your-", re.IGNORECASE)
PLANTILLA_RUTA = re.compile(
    r"github\.com/(usuario|tu-usuario|your-?user|username|user/repo|ejemplo)/",
    re.IGNORECASE,
)

# Prefijos que no son enlaces navegables: namespaces XML y hosts de fuentes.
NO_NAVEGABLE = (
    "w3.org/", "maven.apache.org/POM", "schemas.android.com", "xmlns",
    "purl.org/", "springframework.org/schema", "hibernate.org/xsd",
    "apache.org/xsd", "jboss.org/", "xmlsoap.org/", "schemas.microsoft.com",
    "schemas.openxmlformats.org", "json-schema.org", "openapis.org",
    "oracle.com/weblogic", "evolveum.com/xml/ns", "fonts.googleapis.com",
    "fonts.gstatic.com", "schema-registry",
)
DOMINIOS_PLANTILLA = (
    "example.com", "example.org", "example.net", "empresa.com", "ejemplo.com",
    "contoso.com", "contoso", "test.com", "dominio.com", "mydomain",
)
SUFIJOS_INTERNOS = (
    ".local", ".internal", ".lab", ".test", ".invalid", ".example", ".svc",
    ".cluster.local", ".ejemplo",
)


def parse_event_body(event):
    """Acepta invocación directa (Step Functions) o API Gateway."""
    if isinstance(event, dict) and isinstance(event.get("body"), str):
        try:
            return json.loads(event["body"])
        except json.JSONDecodeError:
            return {}
    return event or {}


def sha256_de_bytes(datos):
    return hashlib.sha256(datos).hexdigest()


def hash_de_objeto(bucket, key):
    respuesta = s3.get_object(Bucket=bucket, Key=key)
    datos = respuesta["Body"].read()
    return {"key": key, "sha256": sha256_de_bytes(datos), "bytes": len(datos)}


def listar(bucket, prefijo):
    claves = []
    paginador = s3.get_paginator("list_objects_v2")
    for pagina in paginador.paginate(Bucket=bucket, Prefix=prefijo):
        for objeto in pagina.get("Contents", []):
            claves.append(objeto["Key"])
    return claves


def construir_manifest(bucket, project_folder):
    """Hash de lo que entra y de lo que sale, con las claves de S3.

    La petición del curso no se hashea aparte: el plan la conserva en
    ``additional_requirements`` y su hash ya la cubre.
    """
    outline = [
        hash_de_objeto(bucket, clave)
        for clave in listar(bucket, f"{project_folder}/outline/")
        if clave.endswith((".yaml", ".yml"))
    ]
    manual = [
        hash_de_objeto(bucket, clave)
        for clave in listar(bucket, f"{project_folder}/labguide/")
        if clave.endswith("manual.txt")
    ]
    plan = [
        hash_de_objeto(bucket, clave)
        for clave in listar(bucket, f"{project_folder}/labguide/")
        if clave.endswith("lab-master-plan.json")
    ]
    labs = [
        hash_de_objeto(bucket, clave)
        for clave in listar(bucket, f"{project_folder}/labguide/")
        if re.search(r"lab-\d{2}-\d{2}-\d{2}.*\.md$", clave)
    ]
    guia = [
        hash_de_objeto(bucket, clave)
        for clave in listar(bucket, f"{project_folder}/setupguide/")
        if clave.endswith((".json", ".pdf"))
    ]

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_folder": project_folder,
        "inputs": {
            "outline": outline,
            "manual": manual,
        },
        "outputs": {
            "plan": plan,
            "labs": labs,
            "setup_guide": guia,
        },
    }


def diferencia_de_manifest(previo: dict, nuevo: dict) -> dict:
    """Diferencia de dos manifiestos: qué cambió por categoría.

    Los manifiestos listan artefactos con ``clave`` y ``sha256``. Una clave que
    ya no está se elimina; una clave nueva es nuevo; clave con un hash distinto
    fue actualizado; igual, no tocado. Es el registro de la actualización
    selectiva: instructor puede ver qué se regeneró y qué quedó vigilado.
    """
    entradas_previas = {}
    for categoria, ficheros in {**(previo.get("inputs") or {}), **(previo.get("outputs") or {})}.items():
        for entrada in ficheros or ():
            entradas_previas[entrada.get("key")] = entrada
    entradas_nuevas = {}
    for categoria, ficheros in {**(nuevo.get("inputs") or {}), **(nuevo.get("outputs") or {})}.items():
        for entrada in ficheros or ():
            entradas_nuevas[entrada.get("key")] = entrada

    actualizados, nuevos, no_tocados = [], [], []
    for clave, entrada in sorted(entradas_nuevas.items()):
        previa = entradas_previas.get(clave)
        if previa is None:
            nuevos.append(entrada)
        elif previa.get("sha256") != entrada.get("sha256"):
            actualizados.append(
                {
                    **entrada,
                    "sha256_antes": previa.get("sha256"),
                    "sha256_despues": entrada.get("sha256"),
                }
            )
        else:
            no_tocados.append(entrada)
    eliminados = [
        entrada for clave, entrada in sorted(entradas_previas.items()) if clave not in entradas_nuevas
    ]
    return {
        "actualizados": actualizados,
        "nuevos": nuevos,
        "no_tocados": no_tocados,
        "eliminados": eliminados,
        "resumen": {
            "actualizados": len(actualizados),
            "nuevos": len(nuevos),
            "no_tocados": len(no_tocados),
            "eliminados": len(eliminados),
        },
    }


def _texto_de_s3(bucket: str, clave: str) -> str | None:
    """Cuerpo del objeto como texto, o None si no existe."""
    try:
        return s3.get_object(Bucket=bucket, Key=clave)["Body"].read().decode("utf-8", "replace")
    except Exception:
        return None


def urls_de(texto):
    """URLs de un markdown, sin el énfasis ni la puntuación que las envuelve.

    Una URL seguida de un marcador de plantilla (``<...>`` o ``\\<...>``) se
    descarta: es un ejemplo, no un enlace navegable.
    """
    texto = texto or ""
    for coincidencia in URL.finditer(texto):
        cruda = coincidencia.group(0)
        siguiente = texto[coincidencia.end():coincidencia.end() + 1]
        if cruda.endswith("\\") or siguiente in ("<", "\\"):
            continue
        yield cruda.strip().rstrip(".,;:*")


def es_enlace_publico(url):
    """(host, motivo). Un enlace interno o de plantilla no se comprueba."""
    if PLANTILLA.search(url):
        return None, "plantilla"
    if PLANTILLA_RUTA.search(url):
        return None, "plantilla"
    try:
        partes = urllib.parse.urlparse(url)
    except ValueError:
        return None, "ilegible"
    host = (partes.hostname or "").lower()
    if not host or "." not in host:
        return None, "host interno"
    if any(sufijo in host for sufijo in SUFIJOS_INTERNOS):
        return None, "host interno"
    if any(host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS_PLANTILLA):
        return None, "plantilla"
    if any(fragmento in url for fragmento in NO_NAVEGABLE):
        return None, "namespace"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    ):
        return None, "ip privada"
    return host, ""


def _peticion(url, metodo):
    solicitud = urllib.request.Request(
        url,
        method=metodo,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AuroraLinkCheck/1.0)"},
    )
    with urllib.request.urlopen(solicitud, timeout=8) as respuesta:
        return respuesta.status


def revisar_enlace(url):
    """(clase, detalle): vivo, muerto o no_verificable."""
    try:
        estado = _peticion(url, "HEAD")
        if estado in (403, 405, 501):
            estado = _peticion(url, "GET")
        return ("vivo" if 200 <= estado < 400 else "no_verificable", estado)
    except urllib.error.HTTPError as error:
        if error.code in (404, 410):
            return "muerto", error.code
        return "no_verificable", error.code
    except urllib.error.URLError as error:
        if isinstance(error.reason, socket.gaierror):
            return "muerto", "DNS inexistente"
        return "no_verificable", type(error.reason).__name__
    except Exception as error:  # noqa: BLE001
        return "no_verificable", type(error).__name__


_APAGADO = ("0", "false", "no", "off")


def compuerta_de_enlaces(informe, activa=None):
    """Dead public links fail the course. Unverifiable responses do not.

    ``activa`` overrides ``LINK_AUDIT_GATE`` (default on). 403/429/5xx stay in
    the report and do not set ``bloquea``.
    """
    if activa is None:
        activa = os.getenv("LINK_AUDIT_GATE", "1").strip().lower() not in _APAGADO
    muertos = int(((informe or {}).get("resumen") or {}).get("muertos") or 0)
    bloquea = bool(activa and muertos > 0)
    return {
        "bloquea": bloquea,
        "activa": bool(activa),
        "muertos": muertos,
        "motivo": "enlaces_muertos" if bloquea else "",
    }


def revisar_enlaces(bucket, project_folder):
    """Comprueba los enlaces públicos de los laboratorios, una vez por URL."""
    claves = [
        clave
        for clave in listar(bucket, f"{project_folder}/labguide/")
        if re.search(r"lab-\d{2}-\d{2}-\d{2}.*\.md$", clave)
    ]
    origen = {}
    for clave in claves:
        texto = s3.get_object(Bucket=bucket, Key=clave)["Body"].read().decode("utf-8", "replace")
        for url in urls_de(texto):
            host, _ = es_enlace_publico(url)
            if host:
                origen.setdefault(url, []).append(clave.split("/")[-1])

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        resultados = dict(zip(origen, pool.map(revisar_enlace, origen)))

    resumen = {"publicos": len(origen), "vivos": 0, "muertos": 0, "no_verificables": 0}
    detalle = {"muertos": [], "no_verificables": []}
    for url, (clase, estado) in resultados.items():
        resumen["vivos" if clase == "vivo" else clase + "s"] += 1
        if clase != "vivo":
            detalle[clase + "s"].append(
                {"url": url, "estado": estado, "labs": sorted(set(origen[url]))}
            )
    detalle["muertos"].sort(key=lambda item: str(item["estado"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_folder": project_folder,
        "resumen": resumen,
        **detalle,
    }


_GENERICOS_URL = frozenset({
    "www", "com", "html", "htm", "en", "es", "learn", "microsoft", "docs",
    "support", "copilot", "index", "default", "org", "net",
})
_LOCALES_URL = frozenset({
    "es-es", "en-us", "es-mx", "en-gb", "pt-br", "fr-fr", "de-de", "es", "en",
})
_UMBRAL_REEMPLAZO = 8
_ENLACE_MD = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _reparacion_activa():
    """``LINK_REPAIR=0`` keeps the old behavior: a dead link blocks immediately."""
    return os.getenv("LINK_REPAIR", "1").strip().lower() not in _APAGADO


def _catalogo_copilot():
    """Checked-in catalog. The audit package carries its own copy; the writer copy is the fallback in the repo."""
    aqui = os.path.dirname(os.path.abspath(__file__))
    for ruta in (
        os.path.join(aqui, "copilot_feature_catalog.json"),
        os.path.join(aqui, "..", "strands_lab_writer", "copilot_feature_catalog.json"),
    ):
        if os.path.isfile(ruta):
            with open(ruta, encoding="utf-8") as fichero:
                return json.load(fichero)
    return {}


def _tokens_de_url(url):
    partes = urllib.parse.urlparse(url or "")
    segmentos = [
        segmento
        for segmento in (partes.path or "").lower().split("/")
        if segmento and segmento not in _LOCALES_URL
    ]
    tokens = []
    for segmento in segmentos:
        tokens.extend(pieza for pieza in re.split(r"[-_]+", segmento) if pieza)
    return tokens


def _tokens_de_frase(frase):
    return [
        pieza
        for pieza in re.split(r"[^0-9a-záéíóúñü]+", (frase or "").lower())
        if pieza
    ]


def puntuacion_de_reemplazo(url_muerta, url_candidata, aliases=None, ancla=""):
    """Higher means the candidate is the same page or the catalog row the dead URL was inventing.

    An exact path (ignoring locale) outranks an alias hit. A two-word catalog
    name that is the tail of the dead path (``copilot-chat``) outranks a shorter
    overlap such as ``microsoft`` + ``copilot`` alone.
    """
    tok_muerta = _tokens_de_url(url_muerta)
    tok_candidata = _tokens_de_url(url_candidata)
    distintivos_muerta = set(tok_muerta) - _GENERICOS_URL
    distintivos_candidata = set(tok_candidata) - _GENERICOS_URL
    comunes = distintivos_muerta & distintivos_candidata
    union = distintivos_muerta | distintivos_candidata
    jaccard = (len(comunes) / len(union)) if union else 0.0
    score = jaccard * 10
    if jaccard >= 0.99 and distintivos_muerta:
        score += 40
    bolsa = set(tok_muerta) | set(_tokens_de_frase(ancla))
    vistos = []
    for alias in aliases or ():
        alias_set = [pieza for pieza in alias if pieza]
        if not alias_set or alias_set in vistos:
            continue
        vistos.append(alias_set)
        if len(alias_set) < 2 or not set(alias_set) <= bolsa:
            continue
        score += 5 * len(alias_set)
        if len(tok_muerta) >= 2 and tok_muerta[-len(alias_set):] == alias_set:
            score += 20
    return score


def _ancla_de(texto, url):
    for coincidencia in _ENLACE_MD.finditer(texto or ""):
        if url in coincidencia.group(2):
            return coincidencia.group(1)
    return ""


def _texto_plano(url):
    """Visible words for a bare URL that has no separate anchor. Not itself a URL."""
    ruta = urllib.parse.urlparse(url or "").path.strip("/")
    ultimo = ruta.split("/")[-1] if ruta else ""
    palabras = re.sub(r"[-_]+", " ", ultimo).strip()
    return palabras or "enlace"


def _sustituir_url_exacta(texto, url, nueva):
    """Replace ``url`` only when it is the whole URL, including one with a trailing period.

    A longer URL that merely starts with this one (``.../foo`` inside ``.../foo.bar``)
    stays. Sentence punctuation that ``urls_de`` strips (``. , ; : *``) does not.
    """
    patron = re.compile(
        re.escape(url) + r"(?=(?:[.,;:*]+)?(?:\s|$|[)\]\"'<>`]))"
    )
    return patron.sub(lambda _coincidencia: nueva, texto)


def aplicar_reparacion_en_texto(texto, url, reemplazo):
    """Point the link at ``reemplazo``, or drop the URL and keep the anchor."""
    if reemplazo:
        return _sustituir_url_exacta(texto or "", url, reemplazo), "reemplazo"

    def _quitar(coincidencia):
        if url not in coincidencia.group(2):
            return coincidencia.group(0)
        ancla = coincidencia.group(1).strip()
        if ancla.lower().startswith("http"):
            return _texto_plano(url)
        return ancla

    sin_markdown = _ENLACE_MD.sub(_quitar, texto or "")
    sin_angulos = sin_markdown.replace(f"<{url}>", _texto_plano(url))
    return _sustituir_url_exacta(sin_angulos, url, _texto_plano(url)), "retirado"


def _textos_de_fuentes(bucket, project_folder):
    textos = []
    for clave in listar(bucket, f"{project_folder}/outline/"):
        if clave.endswith((".yaml", ".yml", ".md", ".txt")):
            texto = _texto_de_s3(bucket, clave)
            if texto:
                textos.append(texto)
    for clave in listar(bucket, f"{project_folder}/labguide/"):
        nombre = clave.split("/")[-1].lower()
        if nombre.endswith("manual.txt") or nombre.endswith(".md") and "manual" in nombre:
            texto = _texto_de_s3(bucket, clave)
            if texto:
                textos.append(texto)
    return textos


def _candidatos_de_reemplazo(bucket, project_folder):
    """(url, alias token lists) from the catalog, the manual and the syllabus."""
    candidatos = []
    for feature in (_catalogo_copilot().get("features") or []):
        if feature.get("status") == "deprecated":
            continue
        url = (feature.get("doc_url") or "").strip()
        if not url:
            continue
        aliases = []
        nombres = [feature.get("canonical_name") or ""]
        nombres.extend(feature.get("aliases") or [])
        for nombre in nombres:
            tokens = _tokens_de_frase(nombre)
            if tokens:
                aliases.append(tokens)
        candidatos.append((url, aliases))
    for texto in _textos_de_fuentes(bucket, project_folder):
        for url in urls_de(texto):
            host, _motivo = es_enlace_publico(url)
            if host:
                candidatos.append((url, []))
    return candidatos


def _claves_de_laboratorios(bucket, project_folder):
    return [
        clave
        for clave in listar(bucket, f"{project_folder}/labguide/")
        if re.search(r"lab-\d{2}-\d{2}-\d{2}.*\.md$", clave)
    ]


def reparar_enlaces_muertos(bucket, project_folder, informe, revisar=None):
    """Replace each dead URL with the closest verified candidate, or drop the URL.

    ``revisar`` is the HTTP checker (``(url) -> (clase, detalle)``). Tests inject
    it. The default is ``revisar_enlace``, so a suite that patches that function
    stays offline. After the files are rewritten the labs are audited again.
    """
    revisar = revisar or revisar_enlace
    cache = {}

    def vivo(url):
        if url not in cache:
            clase, _detalle = revisar(url)
            cache[url] = clase == "vivo"
        return cache[url]

    candidatos = _candidatos_de_reemplazo(bucket, project_folder)
    reparaciones = []
    cuerpos = {}
    for clave in _claves_de_laboratorios(bucket, project_folder):
        texto = _texto_de_s3(bucket, clave)
        if texto is not None:
            cuerpos[clave] = texto
    cambio = False
    for muerto in (informe or {}).get("muertos") or []:
        url = (muerto or {}).get("url") or ""
        if not url:
            continue
        for clave, texto in list(cuerpos.items()):
            if url not in texto:
                continue
            ancla = _ancla_de(texto, url)
            mejor = None
            mejor_score = 0.0
            for candidata, aliases in candidatos:
                if candidata == url or not vivo(candidata):
                    continue
                score = puntuacion_de_reemplazo(url, candidata, aliases, ancla)
                if score > mejor_score:
                    mejor_score = score
                    mejor = candidata
            reemplazo = mejor if mejor_score >= _UMBRAL_REEMPLAZO else None
            nuevo, accion = aplicar_reparacion_en_texto(texto, url, reemplazo)
            if nuevo == texto:
                continue
            cuerpos[clave] = nuevo
            cambio = True
            reparaciones.append({
                "url": url,
                "accion": accion,
                "reemplazo": reemplazo or "",
                "lab": clave.split("/")[-1],
                "ancla": ancla,
            })
    if cambio:
        for clave, texto in cuerpos.items():
            s3.put_object(
                Bucket=bucket,
                Key=clave,
                Body=texto.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
            )
    fresco = revisar_enlaces(bucket, project_folder)
    fresco["reparaciones"] = reparaciones
    return fresco


def lambda_handler(event, context):
    body = parse_event_body(event)
    project_folder = (body.get("project_folder") or "").strip()
    if not project_folder:
        return {"statusCode": 400, "body": json.dumps({"error": "project_folder es requerido"})}
    bucket = body.get("course_bucket") or BUCKET_POR_DEFECTO

    update_mode = bool(body.get("update_mode"))
    try:
        manifest = construir_manifest(bucket, project_folder)
        manifest_key = f"{project_folder}/labguide/inputs-manifest.json"
        updates_key = None
        if update_mode:
            previo = _texto_de_s3(bucket, manifest_key)
            if previo:
                try:
                    diff = diferencia_de_manifest(json.loads(previo), manifest)
                    updates_key = f"{project_folder}/labguide/updates-manifest.json"
                    s3.put_object(
                        Bucket=bucket,
                        Key=updates_key,
                        Body=json.dumps(
                            {
                                "version": 1,
                                "generated_at": manifest["generated_at"],
                                "project_folder": project_folder,
                                **diff,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ).encode("utf-8"),
                        ContentType="application/json",
                    )
                except json.JSONDecodeError:
                    logger.warning("Manifiesto previo ilegible: no hay diff de actualización")
        s3.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

        enlaces = revisar_enlaces(bucket, project_folder)
        if _reparacion_activa() and int(((enlaces.get("resumen") or {}).get("muertos") or 0)):
            try:
                enlaces = reparar_enlaces_muertos(bucket, project_folder, enlaces)
            except Exception:
                # A repair crash must not become a Lambda error: that Catch
                # skips the gate and the course would ship with dead links.
                logger.error("La reparación de enlaces falló; la compuerta usa el primer informe", exc_info=True)
        enlaces["gate"] = compuerta_de_enlaces(enlaces)
        enlaces_key = f"{project_folder}/labguide/enlaces.json"
        s3.put_object(
            Bucket=bucket,
            Key=enlaces_key,
            Body=json.dumps(enlaces, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

        logger.info(
            "Auditoría: %s entradas, %s salidas, %s enlaces públicos (%s muertos)",
            len(manifest["inputs"]["outline"]),
            len(manifest["outputs"]["labs"]),
            enlaces["resumen"]["publicos"],
            enlaces["resumen"]["muertos"],
        )
        return {
            "statusCode": 200,
            "manifest_key": manifest_key,
            "updates_key": updates_key,
            "enlaces_key": enlaces_key,
            "resumen_enlaces": enlaces["resumen"],
            "gate": enlaces["gate"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en la auditoría posterior: %s", exc, exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}
