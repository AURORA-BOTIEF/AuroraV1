"""Auditoría posterior del curso: manifiesto de entradas con hash y enlaces.

Se ejecuta después de la Setup Guide y no bloquea el flujo. Escribe dos artefactos
de evidencia en ``{proyecto}/labguide/``:

- ``inputs-manifest.json``: SHA-256 de las entradas (temario, manual, petición) y de
  las salidas (plan, laboratorios, guía). En una actualización permite saber qué
  cambió sin comparar el curso entero a mano.
- ``enlaces.json``: enlaces públicos de los laboratorios con su estado. Solo se
  marcan como muertos los 404/410 y los dominios inexistentes; 403/429/5xx y los
  timeouts son «no verificables»: el servidor existe y puede estar bloqueando bots.

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


def urls_de(texto):
    """URLs de un markdown, sin el énfasis ni la puntuación que las envuelve."""
    for cruda in URL.findall(texto or ""):
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


def lambda_handler(event, context):
    body = parse_event_body(event)
    project_folder = (body.get("project_folder") or "").strip()
    if not project_folder:
        return {"statusCode": 400, "body": json.dumps({"error": "project_folder es requerido"})}
    bucket = body.get("course_bucket") or BUCKET_POR_DEFECTO

    try:
        manifest = construir_manifest(bucket, project_folder)
        manifest_key = f"{project_folder}/labguide/inputs-manifest.json"
        s3.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

        enlaces = revisar_enlaces(bucket, project_folder)
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
            "enlaces_key": enlaces_key,
            "resumen_enlaces": enlaces["resumen"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Error en la auditoría posterior: %s", exc, exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}
