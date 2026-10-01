#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thor — Setup Guide (SUG) Builder
================================

Genera la Setup Guide consolidada por curso (plantilla visual de referencia NETEC)
de forma **determinista**: no inventa datos. Consolida el outline, el master plan de
laboratorios (`labguide/lab-master-plan.json`) y los laboratorios ya generados
(`labguide/lab-*.md`). Todo dato no confirmado se emite como marcador visible.

Salidas:
    {project_folder}/setupguide/setup-guide.json
    {project_folder}/setupguide/Setup_Guide.pdf

Entrada (API Gateway o invocación directa):
    { "project_folder": "...", "course_bucket": "crewai-course-artifacts",
      "author": "Aurora AI" }
"""

import datetime
import json
import logging
import os
import re
import unicodedata
import urllib.request
from io import BytesIO

import boto3
import yaml
from botocore.exceptions import ClientError
from jinja2 import Template
from xhtml2pdf import pisa

from setup_guide_template import SETUP_GUIDE_TEMPLATE

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

ORG_DEFAULT = os.getenv("GITHUB_ORG", "Netec-Mx")

# Marcadores permitidos (no inventar información)
PH_KEY = "[CLAVE COMPLETA]"
PH_VERSION = "[V1.0]"
PH_DATE = "[FECHA DE VALIDACIÓN]"
PH_LINK = "[INSERTAR ENLACE]"
PH_OFFICIAL = "[ENLACE OFICIAL]"
PH_VERSION_VALIDATE = "[VERSIÓN POR VALIDAR]"
PH_REGION = "[REGIÓN POR DEFINIR]"
PH_VALIDATION = "[COMANDO DE PRUEBA]"
PH_LICENSE = "[LICENCIA POR VALIDAR]"
PH_USER = "[USUARIO POR DEFINIR]"

VAGUE_VERSION_RE = re.compile(
    r"(?i)(latest|\u00faltima|ultima|current|actual|reciente|^v?[\dx]+\.x|&gt;=|>=|\+)"
)


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------
def strip_accents(text):
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in normalized if not unicodedata.combining(c))


def clean_inline(text):
    """Limpia markdown inline para presentación en tablas de la SUG."""
    if text is None:
        return ""
    value = str(text)
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("`", "")
    value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    value = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", value)
    value = re.sub(r"^\s*[-*+]\s+", "", value)
    value = re.sub(r"^\s*>\s*", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_obj(obj):
    """Normaliza tipografía problemática para xhtml2pdf (igual que book_to_pdf)."""
    replacements = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2015": "-", "\u00ad": "",
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
        "\u2026": "...", "\u00a0": " ",
    }
    if isinstance(obj, str):
        for char, rep in replacements.items():
            obj = obj.replace(char, rep)
        return obj
    if isinstance(obj, list):
        return [normalize_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: normalize_obj(v) for k, v in obj.items()}
    return obj


def truncate(text, limit=320):
    text = clean_inline(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


# ---------------------------------------------------------------------------
# Acceso a S3
# ---------------------------------------------------------------------------
def read_s3_text(bucket, key):
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def find_outline(bucket, project_folder):
    """Devuelve (key, data) del outline YAML del curso, o (None, {})."""
    for prefix in (f"{project_folder}/outline/", f"{project_folder}/"):
        try:
            resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=50)
        except ClientError:
            continue
        for obj in resp.get("Contents", []):
            key = obj.get("Key", "")
            if key.lower().endswith((".yaml", ".yml")):
                try:
                    raw = yaml.safe_load(read_s3_text(bucket, key)) or {}
                    return key, raw
                except Exception as exc:  # noqa: BLE001
                    logger.warning("No se pudo parsear outline %s: %s", key, exc)
    return None, {}


def load_master_plan(bucket, project_folder):
    key = f"{project_folder}/labguide/lab-master-plan.json"
    try:
        return key, json.loads(read_s3_text(bucket, key))
    except Exception as exc:  # noqa: BLE001
        logger.info("Sin master plan (%s): %s", key, exc)
        return None, {}


def list_lab_files(bucket, project_folder):
    """Descubre los laboratorios (uno por lab_id, el más reciente)."""
    prefix = f"{project_folder}/labguide/"
    try:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    except ClientError:
        return {}
    if "Contents" not in resp:
        return {}
    pattern = re.compile(r"lab-(\d{2}-\d{2}-\d{2})", re.IGNORECASE)
    latest = {}
    for obj in resp["Contents"]:
        key = obj["Key"]
        if not key.endswith(".md"):
            continue
        match = pattern.search(key.split("/")[-1])
        lab_id = match.group(1) if match else key
        if lab_id not in latest or obj["LastModified"] > latest[lab_id]["last_modified"]:
            latest[lab_id] = {"key": key, "last_modified": obj["LastModified"]}
    labs = {}
    for lab_id, info in latest.items():
        try:
            labs[lab_id] = read_s3_text(bucket, info["key"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo leer lab %s: %s", info["key"], exc)
    return labs


# ---------------------------------------------------------------------------
# Parseo de markdown de laboratorios
# ---------------------------------------------------------------------------
def extract_section(md, names):
    """Extrae el cuerpo de la primera sección H2/H3 cuyo título contenga alguno de names."""
    if not md:
        return ""
    names_norm = [strip_accents(n).lower() for n in names]
    lines = md.splitlines()
    start = None
    level = None
    for idx, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            title = strip_accents(match.group(2)).lower()
            if any(name in title for name in names_norm):
                start = idx + 1
                level = len(match.group(1))
                break
    if start is None:
        return ""
    body = []
    for line in lines[start:]:
        match = re.match(r"^(#{1,6})\s+", line.strip())
        if match and len(match.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body).strip()


def extract_code_blocks(text):
    return [block.strip() for block in re.findall(r"```[a-zA-Z0-9]*\n(.*?)```", text, re.DOTALL)]


def parse_md_table(text):
    """Convierte la primera tabla markdown encontrada en una lista de dicts."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    header = None
    rows = []
    for line in lines:
        if "|" not in line:
            if header and rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
            continue
        if header:
            rows.append({header[i]: (cells[i] if i < len(cells) else "") for i in range(len(header))})
    return rows


def first_paragraph(text):
    for line in (text or "").splitlines():
        cleaned = clean_inline(line)
        if cleaned:
            return cleaned
    return ""


# ---------------------------------------------------------------------------
# Extracción de metadatos del curso
# ---------------------------------------------------------------------------
def extract_course_meta(outline_key, outline_data):
    course = outline_data.get("course", outline_data) if isinstance(outline_data, dict) else {}
    if not isinstance(course, dict):
        course = {}

    raw_title = (
        course.get("title")
        or outline_data.get("title")
        or outline_data.get("course_title")
        or "Curso Netec"
    )
    title = re.sub(r"^CURSO:\s*", "", str(raw_title), flags=re.IGNORECASE).strip()

    # Clave y versión: primero campos explícitos, luego convención de nombre de archivo.
    key = None
    version = None
    for candidate in ("key", "course_key", "clave", "code"):
        if course.get(candidate):
            key = str(course[candidate]).strip()
            break
    for candidate in ("version", "course_version", "versión"):
        if course.get(candidate):
            version = str(course[candidate]).strip()
            break
    if not key or not version:
        basename = (outline_key or "").split("/")[-1]
        match = re.search(r"\[([A-Za-z0-9_\-]+)\]\s*v?([0-9][0-9.]*)?", basename)
        if match:
            key = key or match.group(1)
            if match.group(2):
                version = version or f"v{match.group(2)}"

    def as_list(value):
        if not value:
            return []
        if isinstance(value, list):
            return [clean_inline(v) for v in value if clean_inline(v)]
        return [clean_inline(value)]

    return {
        "title": title,
        "key": key or PH_KEY,
        "version": (version if version and version.lower().startswith("v") else f"v{version}") if version else PH_VERSION,
        "description": clean_inline(course.get("description") or ""),
        "prerequisites": as_list(course.get("prerequisites")),
        "audience": as_list(course.get("audience") or course.get("target_audience")),
        "learning_outcomes": as_list(course.get("learning_outcomes") or course.get("objectives")),
        "level": clean_inline(course.get("level") or ""),
        "language": clean_inline(course.get("language") or "es"),
        "total_duration_minutes": course.get("total_duration_minutes"),
    }


def sanitize_repo_name(name):
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "-", (name or "").strip())
    return sanitized.strip("-")


def repo_url_for(project_folder):
    return f"https://github.com/{ORG_DEFAULT}/{sanitize_repo_name(project_folder)}"


def repo_exists(url):
    """Comprobación best-effort y no bloqueante de que el repositorio es público."""
    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "aurora-thor-sug"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return 200 <= response.status < 400
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Construcción de secciones
# ---------------------------------------------------------------------------
def _normalize_for_dedup(text):
    """Normaliza texto para detectar duplicados entre lotes del master plan."""
    base = strip_accents(clean_inline(text)).lower()
    base = re.sub(r"[^a-z0-9 ]+", " ", base)
    return re.sub(r"\s+", " ", base).strip()


def _dedup_requirements(items):
    """Elimina requisitos duplicados (exactos o contenidos unos en otros).

    El master plan se construye por lotes, por lo que el mismo requisito puede
    aparecer varias veces con redacción ligeramente distinta.
    """
    unique = []
    seen = []
    for item in items:
        text = clean_inline(item)
        if not text:
            continue
        norm = _normalize_for_dedup(text)
        if not norm:
            continue
        # Duplicado exacto o subcadena de uno ya registrado (y viceversa)
        if any(norm == existing or norm in existing or existing in norm for existing in seen):
            continue
        seen.append(norm)
        unique.append(text)
    return unique


def build_hardware(master_plan):
    """Clasifica los hardware_requirements en filas de componente, sin duplicados."""
    rows = []
    seen_labels = set()
    for req in _dedup_requirements(master_plan.get("hardware_requirements", []) or []):
        text = clean_inline(req)
        low = strip_accents(text).lower()
        if "ram" in low or "memoria" in low:
            component = "Memoria RAM"
        elif any(token in low for token in ("disco", "ssd", "hdd", "almacenamiento", "storage")):
            component = "Almacenamiento"
        elif any(token in low for token in ("cpu", "vcpu", "procesador", "nucleo", "core")):
            component = "Procesamiento"
        elif any(token in low for token in ("red", "network", "adaptador", "nic", "internet", "resolucion", "pantalla")):
            component = "Red y visualización"
        elif "gpu" in low or "grafica" in low:
            component = "GPU"
        else:
            # Requisitos operativos (permisos, hipervisor) -> no son "hardware" de equipo
            continue
        if component in seen_labels:
            continue
        seen_labels.add(component)
        rows.append({
            "component": component,
            "minimum": text,
            "recommended": "[POR CONFIRMAR]",
            "status": "Requiere confirmación",
        })
    return rows


COUNTER_LABELS = [
    ("ram", "RAM"),
    ("ssd", "DISCO PRINCIPAL"),
    ("hdd", "DISCO PRINCIPAL"),
    ("disco", "DISCOS ADICIONALES"),
    ("gb", "ALMACENAMIENTO"),
    ("adaptador", "ADAPTADORES DE RED"),
]


def build_counter_value(low, row):
    match = re.search(r"(\d+[\.,]?\d*\s*(?:gb|tb))", low)
    if not match:
        match = re.search(r"(\d+)\s*(?:nucleos?|núcleos?|cores?|vcpu)", low)
    if not match:
        match = re.search(r"(\d+)\s*x", low)
    return match.group(1).upper() if match else ""


def build_counters(hardware_rows, master_plan):
    counters = []
    for row in hardware_rows:
        low = strip_accents(row["minimum"]).lower()
        value = build_counter_value(low, row)
        if not value:
            continue
        if "ram" in low or "memoria" in low:
            counters.append({"value": value, "label": "RAM"})
        elif any(t in low for t in ("disco", "ssd", "hdd", "almacenamiento")):
            counters.append({"value": value, "label": "ALMACENAMIENTO"})
        elif any(t in low for t in ("red", "adaptador", "nic")):
            counters.append({"value": value, "label": "ADAPTADORES DE RED"})
        elif any(t in low for t in ("cpu", "vcpu", "procesador", "nucleo")):
            counters.append({"value": value, "label": "PROCESAMIENTO"})
    # sin duplicar etiquetas
    unique = []
    labels = set()
    for counter in counters:
        if counter["label"] not in labels:
            unique.append(counter)
            labels.add(counter["label"])
    return unique[:4]


def build_preparation(master_plan, labs):
    steps = []
    special = [clean_inline(s) for s in (master_plan.get("special_considerations") or []) if clean_inline(s)]
    if special:
        steps.append({
            "order": "01",
            "title": "Confirmar constantes del entorno",
            "description": "Definir y verificar los valores base del entorno antes de instalar componentes.",
            "commands": [],
            "expected_result": "Los valores del entorno coinciden con los definidos para el curso.",
            "evidence": "Registro de los valores confirmados (puertos, nombres y rutas).",
            "warning": "",
        })
        steps[0]["commands"] = special[:8]

    # Paso por cada bloque de setup detectado en los laboratorios (deduplicado)
    seen_commands = set()
    extra = []
    for lab_id in sorted(labs.keys()):
        md = labs[lab_id]
        env = extract_section(md, ["entorno de laboratorio", "initial setup", "configuracion inicial", "ambiente"])
        for block in extract_code_blocks(env):
            signature = strip_accents(block)[:80].lower()
            if signature in seen_commands:
                continue
            seen_commands.add(signature)
            extra.append((lab_id, block))
    for idx, (lab_id, block) in enumerate(extra[:6], start=len(steps) + 1):
        steps.append({
            "order": f"{idx:02d}",
            "title": f"Preparar entorno del laboratorio {lab_id}",
            "description": "Comandos de preparación inicial del laboratorio.",
            "commands": block.splitlines()[:12],
            "expected_result": "Los comandos finalizan sin errores críticos.",
            "evidence": "Captura o registro de la salida del comando.",
            "warning": "Verificar los dispositivos y rutas antes de ejecutar comandos destructivos.",
        })

    if not steps:
        steps.append({
            "order": "01",
            "title": "Preparar el entorno",
            "description": PH_VERSION_VALIDATE,
            "commands": [],
            "expected_result": "[RESULTADO POR DEFINIR]",
            "evidence": "[EVIDENCIA POR DEFINIR]",
            "warning": "Confirmar los comandos con el instructor antes de ejecutarlos.",
        })
    return steps


def _classify_network(text):
    low = strip_accents(text).lower()
    keys = ("puerto", "port", "dominio", "dns", "proxy", "vpn", "red", "url", "endpoint", "region", "region")
    return any(k in low for k in keys)


def build_previous_knowledge(course_meta, master_plan):
    special = [clean_inline(s) for s in (master_plan.get("special_considerations") or []) if clean_inline(s)]
    knowledge = list(course_meta.get("prerequisites") or [])
    if not knowledge and course_meta.get("audience"):
        knowledge = list(course_meta["audience"])
    accounts, licenses, permissions, network, timing = [], [], [], [], []
    for item in special:
        low = strip_accents(item).lower()
        if any(k in low for k in ("licencia", "licencia", "suscripcion", "suscripción", "plan")):
            licenses.append(item)
        elif any(k in low for k in ("credencial", "contrasena", "contraseña", "usuario", "cuenta", "password")):
            accounts.append(item)
        elif any(k in low for k in ("permiso", "rol", "privilegio", "admin")):
            permissions.append(item)
        elif _classify_network(item):
            network.append(item)
        else:
            timing.append(item)
    if not accounts:
        accounts = [f"Usuario local: {PH_USER}", "Contraseña inicial: credencial temporal para laboratorio aislado"]
    if not permissions:
        permissions = ["Privilegios de administración local (sudo) para la preparación"]
    if not network:
        network = ["[DOMINIOS, PUERTOS Y PROXY POR VALIDAR]"]
    if not timing:
        timing = ["Los accesos deben estar disponibles antes de iniciar el curso."]
    return {
        "knowledge": knowledge,
        "accounts": accounts,
        "licenses": licenses,
        "permissions": permissions,
        "network": network,
        "timing": timing,
    }


def build_software(master_plan):
    software = []
    seen_names = []
    for item in master_plan.get("software_requirements", []) or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = clean_inline(item.get("name"))
        name_norm = _normalize_for_dedup(name)
        if not name_norm:
            continue
        # El master plan se agrega por lotes: deduplicar por nombre normalizado
        if any(name_norm == existing or name_norm in existing or existing in name_norm for existing in seen_names):
            continue
        seen_names.append(name_norm)
        raw_version = clean_inline(item.get("version") or "")
        pending = (not raw_version) or bool(VAGUE_VERSION_RE.search(raw_version))
        version = PH_VERSION_VALIDATE if pending else raw_version
        software.append({
            "name": name,
            "version": version,
            "purpose": clean_inline(item.get("purpose") or item.get("installation_notes") or ""),
            "source": clean_inline(item.get("source") or ""),
            "moment": "Antes del curso",
            "validation": PH_VALIDATION,
            "license": clean_inline(item.get("license") or PH_LICENSE),
            "pending": pending,
        })
    return software


def build_accesses(master_plan):
    rows = []
    for item in _dedup_requirements(master_plan.get("special_considerations", []) or []):
        text = clean_inline(item)
        if not text:
            continue
        if ":" in text:
            element, _, definition = text.partition(":")
            rows.append({"element": element.strip(), "definition": definition.strip() or PH_REGION})
        else:
            rows.append({"element": "Constante del entorno", "definition": text})
    if not rows:
        rows = [
            {"element": "Usuario local", "definition": PH_USER},
            {"element": "Contraseña inicial", "definition": "Credencial temporal para laboratorio aislado"},
            {"element": "Internet", "definition": "[DOMINIOS, PUERTOS, DNS Y PROXY POR VALIDAR]"},
        ]
    return rows[:12]


DEFAULT_TROUBLESHOOTING = [
    {
        "symptom": "Sin acceso a repositorios",
        "probable_cause": "DNS, proxy o firewall",
        "how_to_validate": "curl; resolvectl; apt update",
        "corrective_action": "Validar conectividad, dominios y puertos.",
    },
    {
        "symptom": "El laboratorio difiere de la guía",
        "probable_cause": "Versión o estado inicial distinto",
        "how_to_validate": "Comparar la matriz de prácticas y el encabezado del lab",
        "corrective_action": "Alinear la versión o actualizar la documentación.",
    },
]


def build_troubleshooting(labs):
    rows = []
    seen = set()
    for lab_id in sorted(labs.keys()):
        md = labs[lab_id]
        section = extract_section(md, ["solucion de problemas", "solución de problemas", "troubleshooting"])
        for row in parse_md_table(section):
            values = {strip_accents(k).lower(): clean_inline(v) for k, v in row.items()}
            symptom = values.get("sintoma") or values.get("síntoma") or values.get("symptom")
            cause = values.get("causa probable") or values.get("probable cause") or values.get("causa")
            validate = values.get("como validar") or values.get("cómo validar") or values.get("how to validate")
            action = values.get("accion correctiva") or values.get("acción correctiva") or values.get("corrective action")
            if not symptom:
                continue
            signature = strip_accents(symptom).lower()
            if signature in seen:
                continue
            seen.add(signature)
            rows.append({
                "symptom": symptom,
                "probable_cause": cause or "[CAUSA POR VALIDAR]",
                "how_to_validate": validate or "[VALIDACIÓN POR DEFINIR]",
                "corrective_action": action or "[ACCIÓN POR DEFINIR]",
            })
    for item in DEFAULT_TROUBLESHOOTING:
        signature = strip_accents(item["symptom"]).lower()
        if signature not in seen:
            rows.append(item)
            seen.add(signature)
    return rows


def build_checklist(course_meta):
    return [
        "Repositorio y enlaces de cada laboratorio verificados.",
        "Versiones exactas documentadas y probadas.",
        "CPU, RAM, discos y adaptadores de red confirmados.",
        "Sistema actualizado sin errores críticos.",
        "Software, archivos, cuentas, licencias y permisos disponibles.",
        "Prueba completa ejecutada desde un entorno limpio.",
    ]


def build_lab_matrix(master_plan, labs, repo_url):
    matrix = []
    plans = master_plan.get("lab_plans") or []
    for plan in plans:
        lab_id = str(plan.get("lab_id") or "").strip()
        title = clean_inline(plan.get("lab_title") or plan.get("title") or "Laboratorio")
        module_number = plan.get("module_number")
        try:
            module_number = int(module_number) if module_number is not None else int(lab_id.split("-")[0])
        except (ValueError, TypeError, IndexError):
            module_number = 1

        md = labs.get(lab_id, "")
        env = extract_section(md, ["entorno de laboratorio", "ambiente", "initial setup"])
        validation = extract_section(md, ["validacion y pruebas", "validación y pruebas", "validacion", "validación"])

        objectives = plan.get("objectives") or []
        objective = clean_inline(objectives[0]) if objectives else clean_inline(plan.get("scope") or "")
        outcomes = plan.get("expected_outcomes") or []
        expected = clean_inline(outcomes[0]) if outcomes else "[RESULTADO POR DEFINIR]"

        prereq = plan.get("prerequisites") or []
        dependencies = ", ".join(clean_inline(p) for p in prereq) if prereq else "[SIN DEPENDENCIAS DECLARADAS]"

        initial_state = ""
        env_clean = "\n".join(
            line for line in env.splitlines()
            if not line.strip().startswith("```") and not re.match(r"^\s*(bash|sh|shell|powershell)\s*$", line.strip(), re.IGNORECASE)
        )
        for line in env_clean.splitlines():
            if re.search(r"(?i)estado inicial", line):
                initial_state = clean_inline(line.split(":", 1)[-1])
                break
        if not initial_state:
            candidate = first_paragraph(env_clean)
            candidate_norm = strip_accents(candidate).lower() if candidate else ""
            # Descartar comandos y encabezados de subsección (p. ej. "### Hardware Mínimo")
            is_header = bool(
                candidate and re.match(r"^#{1,6}\s", candidate.strip())
            )
            looks_like_command = bool(
                candidate and (
                    re.match(r"^[a-z0-9_.\-/]+(\s+-{1,2}\w+)", candidate, re.IGNORECASE)
                    or (len(candidate.split()) <= 3 and " " not in candidate.strip())
                )
            )
            is_env_noise = any(
                token in candidate_norm
                for token in ("hardware minimo", "requisitos de hardware", "software requerido", "requisitos de software")
            )
            initial_state = (
                candidate
                if (candidate and not looks_like_command and not is_header and not is_env_noise)
                else "Entorno preparado según esta Setup Guide"
            )

        evidence = ""
        validation_codes = extract_code_blocks(validation)
        if validation_codes:
            evidence = " | ".join(clean_inline(c) for c in validation_codes[0].splitlines()[:2])
        if not evidence:
            evidence = first_paragraph(validation) or "[EVIDENCIA POR DEFINIR]"

        duration = plan.get("estimated_duration") or plan.get("duration_minutes")
        duration_text = f"{duration} min" if duration else "[DURACIÓN POR CONFIRMAR]"

        anchor = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip().lower()
        anchor = re.sub(r"[\s_]+", "-", anchor)
        anchor = re.sub(r"-{2,}", "-", anchor).strip("-") or "laboratorio"

        matrix.append({
            "number": lab_id or "-",
            "name": title,
            "objective": truncate(objective, 180) or "[OBJETIVO POR DEFINIR]",
            "duration": duration_text,
            "dependencies": truncate(dependencies, 140),
            "initial_state": truncate(initial_state, 140),
            "expected_result": truncate(expected, 160),
            "evidence": truncate(evidence, 160),
            "access": {
                "label": f"Capítulo {module_number:02d}",
                "url": f"{repo_url}/blob/main/Capitulo{module_number:02d}/README.md#{anchor}",
            },
        })
    return matrix


def build_setup_guide(bucket, project_folder, outline_key, outline_data, master_plan, labs):
    course_meta = extract_course_meta(outline_key, outline_data)
    repo_url = repo_url_for(project_folder)
    repo_ok = repo_exists(repo_url)

    hardware_rows = build_hardware(master_plan)
    counters = build_counters(hardware_rows, master_plan)
    software = build_software(master_plan)
    preparation = build_preparation(master_plan, labs)
    previous_knowledge = build_previous_knowledge(course_meta, master_plan)
    accesses = build_accesses(master_plan)
    troubleshooting = build_troubleshooting(labs)
    lab_matrix = build_lab_matrix(master_plan, labs, repo_url)

    status_repo = "Verificado" if repo_ok else "Por confirmar"
    readme_url = f"{repo_url}#readme" if repo_ok else ""
    references = [
        {"label": "Repositorio principal", "url": repo_url if repo_ok else ""},
        {"label": "README del curso", "url": readme_url},
        {"label": "Setup Guide (este documento)", "url": ""},
        {"label": "Documentación oficial", "url": ""},
        {"label": "Soporte o incidencias", "url": ""},
    ]
    identification_links = [
        {"label": "Repositorio de laboratorios", "url": repo_url, "status": status_repo},
        {"label": "README principal", "url": readme_url, "status": "Verificado" if repo_ok else "Por confirmar"},
        {"label": "Archivos de instalación", "url": "", "status": "Por confirmar"},
        {"label": "Documentación oficial", "url": "", "status": "Por confirmar"},
    ]

    validation = {
        "checklist": build_checklist(course_meta),
        "full_test": "Ejecutar la prueba integral desde un entorno limpio siguiendo los pasos 04 y 05 y confirmar que todos los laboratorios pueden completarse sin pasos previos implícitos.",
        "troubleshooting": troubleshooting,
    }

    now = datetime.datetime.utcnow()
    doc = {
        "metadata": {
            "project_folder": project_folder,
            "generated_at": now.isoformat() + "Z",
            "course_title": course_meta["title"],
            "course_key": course_meta["key"],
            "version": course_meta["version"],
            "status": "BORRADOR",
            "last_validation": PH_DATE,
            "source": {"outline": outline_key, "master_plan": f"{project_folder}/labguide/lab-master-plan.json" if master_plan else None, "labs": sorted(labs.keys())},
            "placeholders_count": 0,
        },
        "identification": {
            "title": course_meta["title"],
            "key": course_meta["key"],
            "version": course_meta["version"],
            "status": "BORRADOR",
            "description": course_meta["description"],
            "links": identification_links,
        },
        "previous_knowledge": previous_knowledge,
        "infrastructure": {
            "hardware": hardware_rows,
            "counters": counters,
            "virtual_machines": [],
            "network": previous_knowledge["network"],
        },
        "software": software,
        "accesses": accesses,
        "preparation": preparation,
        "validation": validation,
        "lab_matrix": lab_matrix,
        "references": references,
        "placeholders": [],
    }

    pending_versions = sum(1 for s in software if s.get("pending"))
    doc["metadata"]["placeholders_count"] = (
        pending_versions
        + sum(1 for link in identification_links if not link["url"])
        + (0 if repo_ok else 1)
    )

    # Fallback de descripción
    if not doc["identification"]["description"]:
        doc["identification"]["description"] = (
            "Centralizar las condiciones necesarias para replicar los laboratorios "
            "sin depender de explicaciones adicionales del desarrollador."
        )
    doc["validation"]["full_test"] = (
        f"Ejecutar la prueba integral desde un entorno limpio siguiendo los pasos de "
        f"instalaci\u00f3n y validaci\u00f3n de esta gu\u00eda, y confirmar que los "
        f"{len(lab_matrix)} laboratorios pueden completarse sin pasos previos impl\u00edcitos."
    )
    return doc


# ---------------------------------------------------------------------------
# Render PDF
# ---------------------------------------------------------------------------
def render_pdf(doc, bucket, author="Aurora AI"):
    local_logo = None
    try:
        local_logo = "/tmp/LogoNetec.png"
        s3.download_file(bucket, "logo/LogoNetec.png", local_logo)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo descargar el logo: %s", exc)
        local_logo = None

    doc = normalize_obj(doc)
    months_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }
    now = datetime.datetime.utcnow()
    context = {
        "logo_path": local_logo,
        "course_title": doc["identification"]["title"],
        "course_key": doc["identification"]["key"],
        "version": doc["identification"]["version"],
        "status": doc["identification"]["status"],
        "last_validation": doc["metadata"]["last_validation"],
        "description": doc["identification"]["description"],
        "date": f"{months_es[now.month]} {now.year}",
        "repo_url": doc["references"][0]["url"],
        "identification": doc["identification"],
        "previous_knowledge": doc["previous_knowledge"],
        "infrastructure": doc["infrastructure"],
        "counters": doc["infrastructure"]["counters"],
        "software": doc["software"],
        "accesses": doc["accesses"],
        "preparation": doc["preparation"],
        "validation": doc["validation"],
        "lab_matrix": doc["lab_matrix"],
        "references": doc["references"],
    }
    html = Template(SETUP_GUIDE_TEMPLATE).render(context)
    pdf_buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=pdf_buffer)
    if result.err:
        raise RuntimeError("La generación del PDF falló (pisa error)")
    return pdf_buffer.getvalue()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def parse_event_body(event):
    """API Gateway puede codificar el body en base64 (BinaryMediaTypes */*)."""
    import base64

    if not isinstance(event, dict):
        return {}
    if isinstance(event.get("body"), dict):
        return event["body"]
    if "body" not in event:
        return event if isinstance(event, dict) else {}
    raw = event.get("body")
    if raw is None or raw == "":
        raw = "{}"
    if event.get("isBase64Encoded", False) and raw and raw != "{}":
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
    }


def lambda_handler(event, context):
    logger.info("Inicio Setup Guide Builder")
    try:
        body = parse_event_body(event)
        project_folder = (body.get("project_folder") or "").strip()
        if not project_folder:
            return {
                "statusCode": 400,
                "headers": cors_headers(),
                "body": json.dumps({"error": "project_folder es requerido"}),
            }
        bucket = body.get("course_bucket") or os.getenv("COURSE_BUCKET", "crewai-course-artifacts")

        outline_key, outline_data = find_outline(bucket, project_folder)
        master_plan_key, master_plan = load_master_plan(bucket, project_folder)
        labs = list_lab_files(bucket, project_folder)

        if not outline_key and not master_plan and not labs:
            return {
                "statusCode": 404,
                "headers": cors_headers(),
                "body": json.dumps({"error": "No se encontró outline, master plan ni laboratorios para el proyecto."}),
            }

        doc = build_setup_guide(
            bucket, project_folder, outline_key, outline_data, master_plan, labs
        )

        json_key = f"{project_folder}/setupguide/setup-guide.json"
        s3.put_object(
            Bucket=bucket, Key=json_key,
            Body=json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

        pdf_bytes = render_pdf(doc, bucket)
        pdf_key = f"{project_folder}/setupguide/Setup_Guide.pdf"
        s3.put_object(Bucket=bucket, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")

        download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": pdf_key},
            ExpiresIn=3600,
        )
        logger.info("Setup Guide generada: %s", pdf_key)
        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps({
                "message": "Setup Guide generada correctamente",
                "project_folder": project_folder,
                "course_title": doc["metadata"]["course_title"],
                "course_key": doc["metadata"]["course_key"],
                "version": doc["metadata"]["version"],
                "setup_guide_json_key": json_key,
                "setup_guide_pdf_key": pdf_key,
                "download_url": download_url,
                "lab_count": len(doc["lab_matrix"]),
                "software_count": len(doc["software"]),
                "placeholders_count": doc["metadata"]["placeholders_count"],
                "placeholders": doc["placeholders"],
            }),
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Error generando Setup Guide: %s", exc, exc_info=True)
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": str(exc)}),
        }
