"""
Lab Writer - Agent 2: Step-by-Step Instructions
Reads master plan and generates detailed lab guides.

Features:
- Generates detailed step-by-step instructions for each lab
- Includes prerequisites, setup, execution, verification
- Adds troubleshooting tips
- Formats as professional Markdown
- Considers duration and Bloom level
"""

import os
import json
import re
import random
import time
import unicodedata
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Dict, List, Any, Optional

from markdown_repair import reparar_markdown
from optional_fields import normalizar_evento_writer
from copilot_currency import (
    auditar_superficies_copilot,
    construir_informe_moneda,
    mensaje_de_correccion_moneda,
    texto_de_catalogo_para_prompt,
)
from manual_context import select_manual_context, flatten_to_text
from audience_adaptation import adjust_presupuesto, writer_audience_block
from golden_lab_example import build_golden_lab_prompt_section
from referent_check import (
    auditar_laboratorio,
    duracion_declarada,
    entorno_de_peticion,
    mensaje_de_correccion,
    presupuesto_de_duracion,
    referencias_a_labs_posteriores,
    requisitos_declarados,
    salidas_de_laboratorios,
    texto_de_anclajes,
)
from measurable_evidence import hallazgos_validacion_no_medible, mensaje_correccion_validacion
from reading_budget import (
    hallazgo_lectura,
    medir_lectura,
    mensaje_acortar,
    reintento_habilitado as _reintento_lectura_habilitado,
    texto_para_prompt as _texto_presupuesto_lectura,
)
from bedrock_fallback import fallback_model_ids, run_model_chain

# Bedrock client: read_timeout must stay below Lambda timeout (900s) but high enough
# that boto3 does not abort a long generation and retry (which doubles wall time).
_BEDROCK_READ_TIMEOUT = int(os.getenv("BEDROCK_READ_TIMEOUT", "860"))
bedrock_config = Config(
    read_timeout=max(60, min(_BEDROCK_READ_TIMEOUT, 890)),
    connect_timeout=60,
    retries={"max_attempts": 2, "mode": "standard"},
)

# Cap output tokens: 32k allows very long runs; typical labs need far less.
LAB_BEDROCK_MAX_OUTPUT_TOKENS = max(
    4096,
    min(32000, int(os.getenv("LAB_BEDROCK_MAX_OUTPUT_TOKENS", "20000"))),
)
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=bedrock_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration
DEFAULT_BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-6")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")

# Retries per lab before failing the batch (Step Functions should not succeed with partial labs)
MAX_LAB_GENERATION_ATTEMPTS = int(os.getenv("MAX_LAB_GENERATION_ATTEMPTS", "3"))


def _reintento_referencial_habilitado() -> bool:
    """Interruptor operativo: ``REFERENTIAL_RETRY=0`` deja B1 en solo registro."""
    return os.getenv("REFERENTIAL_RETRY", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _reintento_duracion_habilitado() -> bool:
    """Interruptor operativo propio de B6: ``DURATION_RETRY=0`` deja solo registro."""
    return os.getenv("DURATION_RETRY", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _reintento_requisitos_habilitado() -> bool:
    """Interruptor operativo propio de B5: ``REQUIREMENTS_RETRY=0`` deja solo registro."""
    return os.getenv("REQUIREMENTS_RETRY", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _reintento_entorno_habilitado() -> bool:
    """Interruptor operativo propio de C2: ``ENTORNO_RETRY=0`` deja solo registro."""
    return os.getenv("ENTORNO_RETRY", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _reintento_validacion_medible_habilitado() -> bool:
    """``VALIDATION_EVIDENCE_RETRY=0`` deja la validación medible en solo registro."""
    return os.getenv("VALIDATION_EVIDENCE_RETRY", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _reintento_moneda_habilitado() -> bool:
    """C6 Copilot currency. ``CURRENCY_RETRY=0`` records the finding and ships the lab."""
    return os.getenv("CURRENCY_RETRY", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _reintento_entregables_habilitado() -> bool:
    """Interruptor operativo propio de B3p: **apagado por defecto**.

    La clase de omisión de entregables todavía no ha demostrado 0 falsos positivos
    sobre cursos reales (medición 21/10/2026: 145 laboratorios con omisión, sin
    revisar uno a uno). Se registra; el reintento se enciende con
    ``DELIVERABLES_RETRY=1`` cuando la calibración lo respalde.
    """
    return os.getenv("DELIVERABLES_RETRY", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _ficha_de_hallazgo(violacion: dict) -> dict:
    """Short, log-safe copy of one finding. The full object stays in the S3 report."""
    return {
        "verificacion": violacion.get("verificacion") or "B1",
        "confianza": violacion.get("confianza") or "baja",
        "valor": str(violacion.get("valor") or "")[:300],
    }


def partir_hallazgos(violaciones) -> tuple:
    """Split findings into a blocking set and warnings.

    High confidence (``confianza == "alta"``) blocks delivery after the final
    retry: syllabus quantity (A2), duration (B6), objective (A5), undeclared
    files (B1/B2), environment (C2), file-shaped omissions (B3p) and any other
    high-confidence validator finding. Medium confidence (a reading-budget
    overrun that survived the last attempt) and low confidence stay warnings.
    """
    bloquean: List[dict] = []
    advertencias: List[dict] = []
    for violacion in violaciones or ():
        if not isinstance(violacion, dict):
            continue
        ficha = _ficha_de_hallazgo(violacion)
        if ficha["confianza"] == "alta":
            bloquean.append(ficha)
        else:
            advertencias.append(ficha)
    return bloquean, advertencias


def hallazgo_objetivo_ausente(markdown: str, lab_plan: dict) -> Optional[dict]:
    """A5: the syllabus objective must still be in the guide we are about to save.

    ``asegurar_objetivo_declarado`` inserts it when the objectives section exists.
    If that insert cannot run, the mismatch is a high-confidence finding.
    """
    objetivo = " ".join(str((lab_plan or {}).get("outline_objective") or "").split())
    if not objetivo:
        return None
    if _sin_marcas(objetivo) in _sin_marcas(markdown or ""):
        return None
    return {
        "valor": f"objetivo del temario ausente o reescrito: {objetivo[:180]}",
        "tipo": "objetivo",
        "inicio": 0,
        "confianza": "alta",
        "verificacion": "A5",
    }


def resumir_hallazgos(bloquean, prefijo: str = "NEEDS_REVIEW") -> str:
    """One string the state machine can put in the execution cause."""
    if not bloquean:
        return "passed"
    partes = []
    for hallazgo in list(bloquean)[:12]:
        if isinstance(hallazgo, dict) and "findings" in hallazgo:
            lab_id = hallazgo.get("lab_id") or "?"
            for ficha in (hallazgo.get("findings") or [])[:4]:
                partes.append(
                    f"{lab_id} {ficha.get('verificacion')}: {str(ficha.get('valor') or '')[:160]}"
                )
        else:
            partes.append(
                f"{hallazgo.get('verificacion')}: {str(hallazgo.get('valor') or '')[:160]}"
            )
    texto = prefijo + " " + "; ".join(partes)
    return texto[:1800]


def _registrar_puerta_de_lab(lab_id: str, attempt: int, bloquean, advertencias) -> None:
    """Logs the gate decision. High confidence is not a silent accept."""
    if bloquean:
        print(
            f"  🚫 QUALITY GATE: lab {lab_id} needs_review after attempt "
            f"{attempt}/{MAX_LAB_GENERATION_ATTEMPTS}. "
            f"{len(bloquean)} high-confidence finding(s) remain. "
            f"The lab still ships; the finding is a warning on the quality report."
        )
        for ficha in bloquean[:12]:
            print(f"     🚫 {ficha['verificacion']} [{ficha['confianza']}] {ficha['valor']}")
        return
    if advertencias:
        print(
            f"  ⚠️  QUALITY GATE: lab {lab_id} passed with "
            f"{len(advertencias)} non-blocking warning(s)."
        )
        for ficha in advertencias[:8]:
            print(f"     ⚠️  {ficha['verificacion']} [{ficha['confianza']}] {ficha['valor']}")
        return
    print(f"  ✅ QUALITY GATE: lab {lab_id} passed")

# App-level Bedrock invoke retries inside call_bedrock_agent
BEDROCK_APP_MAX_ATTEMPTS = max(1, int(os.getenv("BEDROCK_APP_MAX_ATTEMPTS", "5")))

# Truncate lesson markdown injected into lab prompt (smaller = faster Bedrock, fewer timeouts)
LESSON_CONTEXT_MAX_CHARS = max(4000, int(os.getenv("LESSON_CONTEXT_MAX_CHARS", "18000")))


def _bedrock_error_is_transient(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = (exc.response.get("Error") or {}).get("Code", "") or ""
        return code in (
            "ThrottlingException",
            "TooManyRequestsException",
            "ServiceUnavailableException",
            "ModelTimeoutException",
            "InternalServerException",
        )
    msg = str(exc)
    return any(
        x in msg
        for x in (
            "ThrottlingException",
            "TooManyRequestsException",
            "ServiceUnavailableException",
            "ModelTimeoutException",
            "InternalServerException",
            "unable to process your request",
        )
    )


def _sleep_before_bedrock_retry(attempt_index: int, base: float = 3.0, cap: float = 90.0) -> None:
    delay = min(cap, base * (2**attempt_index))
    jitter = random.uniform(0, min(8.0, delay * 0.25))
    total = delay + jitter
    print(f"⏳ Bedrock backoff: sleep {total:.1f}s before next attempt")
    time.sleep(total)


def _lab_skip_if_exists_enabled() -> bool:
    return os.getenv("LAB_SKIP_IF_EXISTS", "").lower() in ("1", "true", "yes")


def _find_existing_lab_guide_key(bucket: str, project_folder: str, lab_id: str) -> Optional[str]:
    """Return first S3 key matching lab-{lab_id}-*.md if present."""
    prefix = f"{project_folder}/labguide/lab-{lab_id}-"
    try:
        resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10)
        for obj in resp.get("Contents") or []:
            k = obj.get("Key", "")
            if k.endswith(".md"):
                return k
    except Exception as e:
        print(f"⚠️  list_objects for existing lab {lab_id}: {e}")
    return None


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"⚠️  Error retrieving secret {secret_name}: {e}")
        return {}


def get_google_api_key() -> str:
    """Get Google API key from Secrets Manager or environment."""
    try:
        secret = get_secret("aurora/google-api-key")
        api_key = secret.get('api_key')
        if api_key:
            return api_key
    except Exception as e:
        print(f"⚠️ Failed to retrieve Google key from Secrets Manager: {e}")
    return os.getenv('GOOGLE_API_KEY')


def call_gemini_agent(prompt: str, api_key: str, model_id: str = "gemini-3.5-flash", max_attempts: int = 4) -> str:
    """Call Google Gemini API with retries.

    Retries transient errors AND empty/recitation responses (finish_reason 4),
    which otherwise abort the whole run on a single unlucky generation.
    """
    import time
    import google.generativeai as genai
    genai.configure(api_key=api_key)

    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            model = genai.GenerativeModel(model_id)
            response = model.generate_content(prompt)
            text = ""
            try:
                text = getattr(response, "text", None) or ""
            except Exception as txt_err:
                print(f"⚠️ Gemini response.text unavailable: {txt_err}")
            if not text.strip():
                parts = []
                for candidate in getattr(response, "candidates", None) or []:
                    content = getattr(candidate, "content", None)
                    for part in getattr(content, "parts", None) or []:
                        part_text = getattr(part, "text", None)
                        if part_text:
                            parts.append(part_text)
                text = "\n".join(parts)
            if text.strip():
                if attempt > 1:
                    print(f"✅ Gemini succeeded on attempt {attempt}/{max_attempts}")
                return text
            last_err = ValueError("Empty Gemini response (recitation or safety block)")
        except Exception as e:
            last_err = e
        print(f"⚠️ Gemini attempt {attempt}/{max_attempts} failed: {last_err}")
        if attempt < max_attempts:
            time.sleep(3 * attempt)

    print(f"❌ Gemini API error after {max_attempts} attempts: {last_err}")
    raise last_err


def is_demo_plan(lab_plan: dict) -> bool:
    """Determine if a lab plan is an instructor demo."""
    if lab_plan.get('is_demo'):
        return True
    title = str(lab_plan.get('lab_title', '')).lower()
    scope = str(lab_plan.get('scope', '')).lower()
    if 'demo' in title or 'demostración' in title or 'demostracion' in title:
        return True
    if re.search(r'instructor\s+dem(?:o|ue)str', title):
        return True
    if 'instructor-led demo' in scope or 'demostración guiada' in scope or 'demostración realizada por el instructor' in scope:
        return True
    if re.search(r'instructor\s+dem(?:o|ue)str', scope) or 'instructor-led' in scope:
        return True
    return False


def ensure_demo_title(title: str) -> str:
    """Ensure title has 'Demo'."""
    t = (title or "").strip()
    t_lower = t.lower()
    if t_lower.startswith("demostración:") or t_lower.startswith("demostracion:"):
        return re.sub(r'^(demostración|demostracion)\s*:\s*', 'Demo: ', t, flags=re.IGNORECASE).strip()
    if t_lower.startswith("demostración -") or t_lower.startswith("demostracion -"):
        return re.sub(r'^(demostración|demostracion)\s*-\s*', 'Demo - ', t, flags=re.IGNORECASE).strip()
    if t_lower.startswith("demostración") or t_lower.startswith("demostracion"):
        return re.sub(r'^(demostración|demostracion)\s*', 'Demo: ', t, flags=re.IGNORECASE).strip()
    if re.search(r'\bdemo\b', t_lower):
        return t
    t = re.sub(
        r'^(práctica|practica|laboratorio|lab)\s*[:\-–]\s*',
        '',
        t,
        flags=re.IGNORECASE,
    ).strip()
    return f"Demo: {t}"


def _ensure_demo_formatting(markdown: str, is_demo: bool, is_spanish: bool = True) -> str:
    """Ensure that Demo markdown has 'Demo' in title and the mandatory instructor note."""
    if not is_demo or not markdown:
        return markdown

    updated = markdown

    # 1. Check/fix H1 title
    lines = updated.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('# '):
            if 'demo' not in line.lower():
                if re.match(r'^#\s+Lab\s+[\d\-]+:\s*', line, flags=re.IGNORECASE):
                    lines[i] = re.sub(r'^(#\s+Lab\s+[\d\-]+:\s*)(.*)', r'\1Demo: \2', line, flags=re.IGNORECASE)
                else:
                    lines[i] = f"# Demo: {line.strip()[2:].strip()}"
            break
    updated = '\n'.join(lines)

    # 2. Check/inject instructor note
    has_instructor_note = (
        'realizada por el instructor' in updated.lower() or
        'instructor-led' in updated.lower() or
        'realizado por el instructor' in updated.lower() or
        ('el instructor' in updated.lower() and 'demostración' in updated.lower())
    )

    if not has_instructor_note:
        demo_note = (
            "> ℹ️ **Nota:** Esta práctica es una **Demostración realizada por el instructor**. "
            "El instructor ejecutará los pasos y comandos mientras los alumnos observan, toman notas y analizan el procedimiento, en lugar de realizarla individualmente.\n"
            if is_spanish
            else
            "> ℹ️ **Note:** This activity is an **Instructor-Led Demonstration**. "
            "The instructor will perform the steps and commands while students observe, take notes, and analyze the procedure, rather than performing it individually.\n"
        )
        overview_match = re.search(r'^##\s+Descripci[oó]n\s+[Gg]eneral\s*$', updated, flags=re.MULTILINE)
        if overview_match:
            heading = overview_match.group(0)
            updated = updated.replace(heading, f"{heading}\n\n{demo_note}", 1)
        elif "## Overview" in updated:
            updated = updated.replace("## Overview", f"## Overview\n\n{demo_note}", 1)
        elif "## Metadatos" in updated:
            updated = updated.replace("## Metadatos", f"{demo_note}\n## Metadatos")
        elif "## Metadata" in updated:
            updated = updated.replace("## Metadata", f"{demo_note}\n## Metadata")
        else:
            first_nl = updated.find('\n')
            if first_nl != -1:
                updated = updated[:first_nl+1] + f"\n{demo_note}\n" + updated[first_nl+1:]
            else:
                updated = f"{updated}\n\n{demo_note}"

    return updated


# Canonical H2 titles from schemas/lab_schema.md. Models often emit synonyms
# ("Requisitos previos", "Procedimiento paso a paso"); remap them deterministically.
_H2_CANONICAL_ES = {
    "metadatos": "Metadatos",
    "metadata": "Metadatos",
    "descripcion general": "Descripción General",
    "overview": "Descripción General",
    "objetivos de aprendizaje": "Objetivos de Aprendizaje",
    "learning objectives": "Objetivos de Aprendizaje",
    "prerrequisitos": "Prerrequisitos",
    "requisitos previos": "Prerrequisitos",
    "prerequisites": "Prerrequisitos",
    "entorno de laboratorio": "Entorno de Laboratorio",
    "entorno del laboratorio": "Entorno de Laboratorio",
    "lab environment": "Entorno de Laboratorio",
    "instrucciones paso a paso": "Instrucciones Paso a Paso",
    "procedimiento paso a paso": "Instrucciones Paso a Paso",
    "step-by-step instructions": "Instrucciones Paso a Paso",
    "step by step instructions": "Instrucciones Paso a Paso",
    "validacion y pruebas": "Validación y Pruebas",
    "validation & testing": "Validación y Pruebas",
    "validation and testing": "Validación y Pruebas",
    "solucion de problemas": "Solución de Problemas",
    "troubleshooting": "Solución de Problemas",
    "limpieza": "Limpieza",
    "cleanup": "Limpieza",
    "resumen": "Resumen",
    "summary": "Resumen",
}

_H2_CANONICAL_EN = {
    "metadatos": "Metadata",
    "metadata": "Metadata",
    "descripcion general": "Overview",
    "overview": "Overview",
    "objetivos de aprendizaje": "Learning Objectives",
    "learning objectives": "Learning Objectives",
    "prerrequisitos": "Prerequisites",
    "requisitos previos": "Prerequisites",
    "prerequisites": "Prerequisites",
    "entorno de laboratorio": "Lab Environment",
    "entorno del laboratorio": "Lab Environment",
    "lab environment": "Lab Environment",
    "instrucciones paso a paso": "Step-by-Step Instructions",
    "procedimiento paso a paso": "Step-by-Step Instructions",
    "step-by-step instructions": "Step-by-Step Instructions",
    "step by step instructions": "Step-by-Step Instructions",
    "validacion y pruebas": "Validation & Testing",
    "validation & testing": "Validation & Testing",
    "validation and testing": "Validation & Testing",
    "solucion de problemas": "Troubleshooting",
    "troubleshooting": "Troubleshooting",
    "limpieza": "Cleanup",
    "cleanup": "Cleanup",
    "resumen": "Summary",
    "summary": "Summary",
}


def _fold_heading_key(title: str) -> str:
    """Lowercase, strip punctuation/accents so synonym matching is stable."""
    t = unicodedata.normalize("NFKD", title or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().strip().rstrip(":").strip()
    t = t.replace("&", "and")
    t = re.sub(r"[–—-]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def normalize_lab_markdown(markdown: str, is_spanish: bool = True) -> str:
    """Force schema H2 titles, a single H1, and Paso/Step N: headings.

    The LLM is instructed to use canonical titles but frequently emits
    close Spanish synonyms or extra H1s (sample document titles). This
    pass keeps the generated body and only rewrites heading lines.
    """
    if not markdown:
        return markdown
    mapping = _H2_CANONICAL_ES if is_spanish else _H2_CANONICAL_EN
    seen_h1 = False
    out = []
    for line in markdown.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not m:
            out.append(line)
            continue
        hashes, title = m.group(1), m.group(2)
        level = len(hashes)
        if level == 1:
            if seen_h1:
                hashes = "##"
                level = 2
            else:
                seen_h1 = True
                out.append(line)
                continue
        if level == 2:
            key = _fold_heading_key(title)
            if key in mapping:
                out.append(f"## {mapping[key]}")
            else:
                out.append(f"## {title}")
            continue
        if level == 3:
            step = re.match(r"^(?:paso|step)\s+(\d+)\s*[.:]?\s*(.*)$", title, flags=re.IGNORECASE)
            if step:
                n, rest = step.group(1), (step.group(2) or "").strip()
                label = "Paso" if is_spanish else "Step"
                suffix = f" {rest}" if rest else ""
                out.append(f"### {label} {n}:{suffix}")
                continue
        if hashes == "##":
            out.append(f"## {title}")
        else:
            out.append(line)
    return "\n".join(out)


def _finalize_lab_markdown(markdown: str, is_demo: bool, is_spanish: bool = True) -> str:
    """Demo notice + schema heading normalization applied at every writer exit."""
    updated = _ensure_demo_formatting(markdown, is_demo=is_demo, is_spanish=is_spanish)
    return normalize_lab_markdown(updated, is_spanish=is_spanish)


def load_master_plan_from_s3(bucket: str, key: str) -> dict:
    """Load master plan JSON from S3."""
    try:
        print(f"📥 Loading master plan from s3://{bucket}/{key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        plan_data = json.loads(response['Body'].read().decode('utf-8'))
        print(f"✅ Master plan loaded successfully")
        return plan_data
    except Exception as e:
        print(f"❌ Error loading master plan: {e}")
        raise


def load_lesson_content(bucket: str, key: str) -> str:
    """Load lesson markdown content from S3."""
    try:
        if not key:
            return ""
        print(f"📥 Loading lesson content from s3://{bucket}/{key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        print(f"✅ Lesson content loaded ({len(content)} chars)")
        return content
    except Exception as e:
        print(f"⚠️ Error loading lesson content: {e}")
        return ""



# Model id that actually produced the last successful completion in this process.
_modelo_que_respondio: dict = {"id": None}

MARCA_PLACEHOLDER = "AURORA_PLACEHOLDER_PENDING_REGENERATION"


def modelo_que_produjo_el_lab() -> Optional[str]:
    return _modelo_que_respondio.get("id")


def _invoke_bedrock_once(prompt: str, model_id: str) -> str:
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": LAB_BEDROCK_MAX_OUTPUT_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    response_body = json.loads(response["body"].read())
    blocks = response_body.get("content") or []
    if not blocks:
        print(f"⚠️ Bedrock empty content[]; keys={list(response_body.keys())}")
        raise ValueError("Bedrock returned no content blocks")
    text = blocks[0].get("text") or ""
    if not (text or "").strip():
        sr = response_body.get("stop_reason")
        print(f"⚠️ Bedrock empty text; stop_reason={sr!r} body_keys={list(response_body.keys())}")
        raise ValueError(f"Bedrock returned empty assistant text (stop_reason={sr!r})")
    return text


def _respaldo_openai_o_gemini(prompt: str) -> Optional[str]:
    """Existing OpenAI, then Gemini, only when a secret or env key is configured."""
    try:
        secret_data = get_secret("aurora/openai-api-key")
        api_key = (secret_data or {}).get("api_key") or os.environ.get("OPENAI_API_KEY")
        if api_key:
            print("🔄 Bedrock exhausted. Trying OpenAI.")
            text = call_openai_agent(prompt, api_key, DEFAULT_OPENAI_MODEL)
            _modelo_que_respondio["id"] = DEFAULT_OPENAI_MODEL
            return text
    except Exception as exc:
        print(f"⚠️ OpenAI fallback unavailable: {exc}")
    try:
        google_key = get_google_api_key()
        if google_key:
            print("🔄 Bedrock exhausted. Trying Gemini.")
            text = call_gemini_agent(prompt, google_key)
            _modelo_que_respondio["id"] = "gemini"
            return text
    except Exception as exc:
        print(f"⚠️ Gemini fallback unavailable: {exc}")
    return None


def call_bedrock_agent(prompt: str, model_id: str) -> str:
    """Bedrock with per-minute backoff, then the fallback model chain.

    A daily token quota, ServiceQuotaExceeded, AccessDenied, or throttling
    that continues after backoff switches immediately to the next model in
    ``BEDROCK_FALLBACK_MODELS``. OpenAI and Gemini run only when a key exists.
    """
    try:
        text, used = run_model_chain(
            lambda mid: _invoke_bedrock_once(prompt, mid),
            fallback_model_ids(model_id),
            max_attempts=BEDROCK_APP_MAX_ATTEMPTS,
            sleep=_sleep_before_bedrock_retry,
            is_transient=_bedrock_error_is_transient,
        )
        _modelo_que_respondio["id"] = used
        if used != model_id:
            print(f"🔄 Bedrock answered with fallback model {used}")
        return text
    except Exception as bedrock_err:
        print(f"❌ Bedrock model chain failed: {bedrock_err}")
        alterno = _respaldo_openai_o_gemini(prompt)
        if alterno:
            return alterno
        raise


def markdown_de_laboratorio_pendiente(lab_id: str, titulo: str, motivo: str = "") -> str:
    """Bilingual placeholder. Spanish first. The run continues; this lab is regenerated later."""
    titulo = (titulo or lab_id or "laboratorio").strip()
    detalle = (motivo or "error de generación").strip()[:500]
    return f"""# Lab {lab_id}: {titulo}

> **PENDIENTE DE REGENERACIÓN / PENDING REGENERATION**
>
> Este laboratorio no pudo generarse en este intento y queda pendiente de regeneración.
> This lab could not be generated on this attempt and is pending regeneration.
>
> No use este texto como instrucción de práctica.
> Do not use this text as lab instructions.
>
> Motivo / Reason: {detalle}

<!-- {MARCA_PLACEHOLDER} -->

## Descripción general / Overview

Contenido pendiente de regeneración. / Content pending regeneration.

## Objetivos de aprendizaje / Learning objectives

- [ ] Pendiente de regeneración. / Pending regeneration.

## Instrucciones paso a paso / Step-by-step instructions

### Paso 1: Pendiente / Step 1: Pending

**Objetivo / Objective:** Regenerar este laboratorio. / Regenerate this lab.

**Instrucciones / Instructions:**

1. Este paso es un marcador. No lo ejecute. / This step is a marker. Do not run it.

**Resultado esperado / Expected output:** Un laboratorio regenerado. / A regenerated lab.

**Verificación / Verification:** El archivo ya no contiene la marca de pendiente. / The file no longer contains the pending marker.
"""


def put_object_con_reintento(intentos: int = 3, **kwargs):
    """Retry an S3 put. Return the error instead of raising after the last try."""
    ultimo = None
    for intento in range(1, max(1, intentos) + 1):
        try:
            return s3_client.put_object(**kwargs)
        except Exception as exc:  # noqa: BLE001 - the caller records the failure and continues
            ultimo = exc
            print(f"⚠️ S3 put attempt {intento}/{intentos} failed: {exc}")
            if intento < intentos:
                time.sleep(min(2.0, 0.2 * intento))
    return ultimo


def call_openai_agent(prompt: str, api_key: str, model_id: str = DEFAULT_OPENAI_MODEL) -> str:
    """Call OpenAI API with GPT-5.6-terra compatibility."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # GPT-5.6-terra and reasoning models use max_completion_tokens
        if model_id.startswith("o1-") or model_id.startswith("o3-") or "gpt-5" in model_id:
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=32000
            )
        else:
            # GPT-4 and earlier models
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are an expert technical instructor creating detailed, professional laboratory guides."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=16000,
                temperature=0.7
            )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        raise


THOR_QUALITY_RULES = """THOR QUALITY RULES (MANDATORY - informe de mejoras):
1. TERMINOLOGÍA: Distinguish a temporary chat instruction from a persistent agent/assistant. Use 'instrucción', 'prompt' and 'mensaje de sistema' correctly (no son sinónimos).
2. VERSIONES EXACTAS: Every technology MUST declare an exact version (edition + architecture) and an official source URL. Never use 'latest/última versión/versión actual/1.x/>=', or unresolvable placeholders. If unconfirmed, use '[VERSIÓN POR VALIDAR]' / '[ENLACE OFICIAL]'.
3. LICENCIAS Y HERRAMIENTAS: Differentiate Microsoft 365 Copilot, Copilot Chat, Designer, Planner and similar tools, stating the license and configuration for each.
4. DURACIÓN: Keep each lab within the time and complexity defined by the syllabus; for a 90-minute seminar prioritize effective tool usage.
5. DEPENDENCIAS: Reduce auxiliary files/dependencies; embed in the prompts any information that does not require an external file. Provide controlled scenarios, inputs and sources so results are comparable.
6. VALIDACIÓN MEDIBLE: Define measurable criteria and sufficient evidence (command, file, output, screenshot). For Copilot/LLM steps, Expected output must be a bullet list of required elements or sections—never a verbatim paragraph the model might return; omit Expected output when Verification already lists those checks. Do NOT claim production-ready from five generic tests, vague success rates, or invented passwords/paths.
7. LIMITACIONES DE IA: In Validation & Testing include at least one adversarial case: nonexistent/contradictory information, missing evidence, or instructions embedded in documents (prompt injection).
8. PROMPTING: Evaluate precision, traceability, uncertainty, usefulness and human supervision; do NOT require exposing internal reasoning as a success criterion.
9. PEDAGOGÍA: Favor experimentation and reinforcement over documentation/captures.
"""


def generate_lab_guide(
    lab_plan: dict,
    master_context: dict,
    model_provider: str = "bedrock"
) -> str:
    """
    Generate detailed step-by-step lab guide for a single lab.
    
    Args:
        lab_plan: Individual lab plan from master plan
        master_context: Overall context (hardware, software, objectives)
        model_provider: "bedrock" or "openai"
    
    Returns:
        Markdown formatted lab guide
    """
    
    lab_id = lab_plan['lab_id']
    is_demo = is_demo_plan(lab_plan)
    lab_title = ensure_demo_title(lab_plan['lab_title']) if is_demo else lab_plan['lab_title']
    target_language = master_context.get('target_language', 'English')
    is_spanish = 'spanish' in target_language.lower() or 'español' in target_language.lower() or 'es' in target_language.lower()
    
    print(f"  🔨 Generating lab guide: [{lab_id}] {lab_title} (Demo={is_demo})")
    print(f"  🌐 Language: {target_language}")
    
    # Build context from master plan
    hw_requirements = master_context.get('hardware_requirements', [])
    sw_requirements = master_context.get('software_requirements', [])
    special_considerations = master_context.get('special_considerations', [])
    
    # Build software list
    sw_list = []
    for sw in sw_requirements:
        if isinstance(sw, dict):
            sw_list.append(f"- {sw.get('name')} ({sw.get('version')}): {sw.get('purpose')}")
        else:
            sw_list.append(f"- {sw}")
    
    manual_ref_text = master_context.get('manual_reference_text', '')
    # Paso 0 de calidad: antes se recortaba por encabezado (manual[:12000] ≈ 5% de un
    # manual real de 230k caracteres) y el modelo rellenaba el resto inventando datos.
    # Ahora se seleccionan las secciones relevantes para ESTE laboratorio.
    manual_excerpt = select_manual_context(
        manual_ref_text,
        query_text=flatten_to_text(lab_plan),
        title_text=lab_title,
        label=lab_id,
    )
    manual_directive = (
        f"""
MANUAL ALIGNMENT REQUIREMENT:
CRITICAL: Base all instructions, commands, verification steps, and expected outputs 100% strictly on the provided reference manual content below:
=== REFERENCE MANUAL CONTENT ===
{manual_excerpt}
=== END REFERENCE MANUAL ===
"""
        if manual_excerpt and manual_excerpt.strip()
        else ""
    )

    demo_directive = (
        f"""
DEMO / DEMOSTRACIÓN (INSTRUCTOR-LED REQUIREMENT):
CRITICAL: This activity is an INSTRUCTOR-LED DEMONSTRATION conducted live by the instructor (NOT performed individually by students).
- The H1 title MUST contain the word 'Demo' (e.g., # Lab {lab_id}: {lab_title}).
- In the Overview section (Descripción General), you MUST include this exact notice block:
  > ℹ️ **Nota:** Esta práctica es una **Demostración realizada por el instructor**. El instructor ejecutará los pasos y comandos mientras los alumnos observan, toman notas y analizan el procedimiento, en lugar de realizarla individualmente.
- All steps should be framed as clear demonstration steps for the instructor to present to the class.
"""
        if is_demo
        else ""
    )

    add_req = master_context.get("additional_requirements", "")
    add_req_directive = (
        f"""
USER ADDITIONAL REQUIREMENTS (CRITICAL):
{add_req}
Ensure all steps, commands, scenarios, and configurations strictly adhere to these requirements.
"""
        if add_req and add_req.strip()
        else ""
    )

    # Build prompt with standardized schema
    prompt = f"""
You are creating a professional, detailed laboratory guide for technical training.

{manual_directive}
{demo_directive}
{add_req_directive}

LANGUAGE REQUIREMENT:
**ALL CONTENT MUST BE WRITTEN IN: {target_language}**

- ALL section titles MUST be in {target_language}
- ALL instructions, explanations, and descriptions MUST be in {target_language}
- Code commands can remain in their original language (usually English)
- Technical terms may remain in English where appropriate

If {target_language} is Spanish, use these EXACT H2 titles (no synonyms):
- "Metadatos" instead of "Metadata"
- "Descripción General" instead of "Overview"
- "Objetivos de Aprendizaje" instead of "Learning Objectives"
- "Prerrequisitos" instead of "Prerequisites" (NOT "Requisitos previos")
- "Entorno de Laboratorio" instead of "Lab Environment" (NOT "Entorno del laboratorio")
- "Instrucciones Paso a Paso" instead of "Step-by-Step Instructions" (NOT "Procedimiento paso a paso")
- "### Paso N:" instead of "### Step N:" (colon required)
- "Validación y Pruebas" instead of "Validation & Testing"
- "Solución de Problemas" instead of "Troubleshooting"
- "Limpieza" instead of "Cleanup"
- "Resumen" instead of "Summary"
- "Referencias Bibliográficas" instead of "Bibliographic References"
Only one H1 is allowed (the lab title). Nested sample documents must be ### or ####.

LAB INFORMATION:
- Lab ID: {lab_id}
- Title: {lab_title}
- Duration: {lab_plan['estimated_duration']} minutes
- Bloom Level: {lab_plan['bloom_level']}
- Complexity: {lab_plan.get('complexity', 'medium')}

OBJECTIVES:
{chr(10).join(f'- {obj}' for obj in lab_plan['objectives'])}

SCOPE:
{lab_plan['scope']}

PREREQUISITES:
{chr(10).join(f'- {prereq}' for prereq in lab_plan.get('prerequisites', ['None']))}

KEY TECHNOLOGIES:
{chr(10).join(f'- {tech}' for tech in lab_plan.get('key_technologies', []))}

EXPECTED OUTCOMES:
{chr(10).join(f'- {outcome}' for outcome in lab_plan.get('expected_outcomes', []))}

AVAILABLE HARDWARE:
{chr(10).join(f'- {hw}' for hw in hw_requirements)}

AVAILABLE SOFTWARE:
{chr(10).join(sw_list)}

SPECIAL CONSIDERATIONS:
{chr(10).join(f'- {consideration}' for consideration in special_considerations)}

═══════════════════════════════════════════════════════════════════════════════
MANDATORY LAB GUIDE STRUCTURE SCHEMA (FOLLOW EXACTLY)
═══════════════════════════════════════════════════════════════════════════════

```markdown
# Lab {lab_id}: {lab_title}

## Metadata

| Property | Value |
|----------|-------|
| **Duration** | {lab_plan['estimated_duration']} minutes |
| **Complexity** | {lab_plan.get('complexity', 'medium').capitalize()} |
| **Bloom Level** | {lab_plan['bloom_level']} |

## Overview

[2-3 sentences describing what this lab accomplishes]
[Explain the practical value and real-world relevance]

## Learning Objectives

By completing this lab, you will be able to:

- [ ] [Objective 1 - specific and measurable]
- [ ] [Objective 2 - specific and measurable]
- [ ] [Objective 3 - specific and measurable]

## Objetivo visual (THOR)

Brief diagram or screenshot summary of lab tasks; include placeholder path such as `../images/lab-visual.png`.

## Prerequisites

### Required Knowledge

- [Prior concept or skill 1]
- [Prior concept or skill 2]

### Required Access

- [Account, permission, or credential 1]
- [Account, permission, or credential 2]

## Lab Environment

### Hardware Requirements

| Component | Specification |
|-----------|---------------|
| [Component 1] | [Spec details] |
| [Component 2] | [Spec details] |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| [Software 1] | [X.Y.Z] | [Why it's needed] |
| [Software 2] | [X.Y.Z] | [Why it's needed] |

### Initial Setup

```bash
# Commands to prepare the environment
[setup_command_1]
[setup_command_2]
```

## Step-by-Step Instructions

### Step 1: [Clear Action Title]

**Objective:** [What this step accomplishes in one sentence]

**Instructions:**

1. [First action with specific details]
   
   ```bash
   [exact command to run]
   ```

2. [Second action]

3. [Third action]

**Expected Output:**

```
[What the user should see after completing this step]
```

**Verification:**

- [How to confirm this step succeeded]
- [What to check or look for]

---

### Step 2: [Next Action Title]

**Objective:** [What this step accomplishes]

**Instructions:**

1. [Action details]

   ```[language]
   [code or command]
   ```

2. [Continue with numbered actions]

**Expected Output:**

```
[Expected result]
```

**Verification:**

- [Verification criteria]

---

### Step N: [Final Step Title]

[Complete the lab with final configuration or deployment]

## Validation & Testing

### Success Criteria

Verify your lab is complete by confirming:

- [ ] [Criterion 1 - specific and testable]
- [ ] [Criterion 2 - specific and testable]
- [ ] [Criterion 3 - specific and testable]

### Testing Procedure

1. [Test action 1]
   
   ```bash
   [test command]
   ```
   
   **Expected Result:** [what should happen]

2. [Test action 2]
   
   **Expected Result:** [what should happen]

## Troubleshooting

### Issue 1: [Common Problem Description]

**Symptoms:**
- [What the user observes]

**Cause:**
[Why this happens]

**Solution:**

```bash
[Command or steps to fix]
```

---

### Issue 2: [Another Common Problem]

**Symptoms:**
- [Observable behavior]

**Cause:**
[Root cause explanation]

**Solution:**

```bash
[Fix command]
```

---

### Issue 3: [Third Common Problem]

[Same structure]

## Cleanup

To reset your environment after completing this lab:

```bash
# Cleanup commands
[cleanup_command_1]
[cleanup_command_2]
[cleanup_command_3]
```

> ⚠️ **Warning:** [Any important notes about cleanup]

## Summary

### What You Accomplished

- [Accomplishment 1]
- [Accomplishment 2]
- [Accomplishment 3]

### Key Takeaways

- [Important concept or skill learned]
- [Best practice discovered]

### Next Steps

- [Suggested follow-up lab or lesson]
- [Additional practice recommendation]

## Bibliographic References

- [Reference 1 title] - [Brief description]
- [Reference 2 title] - [Brief description]
```

═══════════════════════════════════════════════════════════════════════════════
CRITICAL FORMATTING RULES
═══════════════════════════════════════════════════════════════════════════════

**HEADING HIERARCHY (MANDATORY):**
- H1 (#): ONLY for lab title - ONE per document
- H2 (##): Major sections (Metadata, Overview, Steps, Troubleshooting, etc.)
- H3 (###): Steps within instructions, subsections, individual issues
- H4 (####): Details within H3 (if needed)
- NEVER skip heading levels (H1 → H3 is INVALID)

**REQUIRED SECTIONS (ALL MUST BE PRESENT):**
1. Metadata (H2) - Table with Duration, Complexity, Bloom Level
2. Overview (H2) - Brief description
3. Learning Objectives (H2) - 3-5 checkboxes
4. Prerequisites (H2) - Knowledge and access requirements
5. Lab Environment (H2) - Hardware, software, setup
6. Step-by-Step Instructions (H2) - Numbered steps as H3
7. Validation & Testing (H2) - Success criteria
8. Troubleshooting (H2) - At least 2-3 common issues
9. Cleanup (H2) - Reset commands
10. Summary (H2) - Accomplishments and takeaways

**STEP STRUCTURE (EVERY STEP MUST HAVE):**
- Objective - One sentence stating what this step accomplishes
- Instructions - Numbered list with specific actions
- Expected Output - Code block showing what user should see
- Verification - How to confirm success
- Use `---` horizontal rules between steps

**CODE BLOCKS (ALWAYS SPECIFY LANGUAGE):**
- Use REAL, EXECUTABLE commands - NO placeholders like <filename> or YOUR_VALUE
- Specify language: bash, python, yaml, json, etc.
- Include actual expected output

**COMPLEXITY GUIDELINES:**
- Beginner: 3-5 steps, heavy guidance, explicit commands
- Intermediate: 5-10 steps, balanced guidance
- Advanced: 10+ steps, less hand-holding

**BLOOM LEVEL ADAPTATION:**
- Remember/Understand: More explanation, guided steps
- Apply: Balanced guidance and independent work
- Analyze/Evaluate: More independent problem-solving
- Create: Less hand-holding, open-ended challenges

{THOR_QUALITY_RULES}
═══════════════════════════════════════════════════════════════════════════════

Return ONLY the Markdown content following this schema exactly, no additional commentary.
"""
    
    try:
        if model_provider == "openai":
            secret_data = get_secret("aurora/openai-api-key")
            api_key = secret_data.get('api_key') or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                print("    ⚠️  OpenAI API key not found, falling back to Bedrock")
                model_provider = "bedrock"
            else:
                lab_guide = call_openai_agent(prompt, api_key, DEFAULT_OPENAI_MODEL)
        
        elif model_provider in ("google", "gemini"):
            google_key = get_google_api_key()
            if not google_key:
                print("    ⚠️  Google API key not found, falling back to Bedrock")
                model_provider = "bedrock"
            else:
                lab_guide = call_gemini_agent(prompt, google_key)

        if model_provider == "bedrock":
            lab_guide = call_bedrock_agent(prompt, DEFAULT_BEDROCK_MODEL)
        
        # Clean up markdown if wrapped in code blocks
        if "```markdown" in lab_guide:
            lab_guide = lab_guide.split("```markdown")[1].split("```")[0].strip()
        elif lab_guide.startswith("```") and lab_guide.endswith("```"):
            lab_guide = lab_guide[3:-3].strip()
        
        lab_guide = _finalize_lab_markdown(lab_guide, is_demo=is_demo, is_spanish=is_spanish)
        print(f"    ✅ Lab guide generated ({len(lab_guide)} characters)")
        return lab_guide
    
    except Exception as e:
        print(f"    ❌ Error generating lab guide: {e}")
        raise


def save_lab_guide_to_s3(
    bucket: str,
    project_folder: str,
    lab_id: str,
    lab_title: str,
    lab_guide: str
) -> str:
    """Save lab guide Markdown to S3."""
    try:
        # Format filename
        safe_title = lab_title.lower()
        safe_title = ''.join(c if c.isalnum() or c.isspace() else '' for c in safe_title)
        safe_title = '-'.join(safe_title.split())[:50]  # Limit length
        
        filename = f"lab-{lab_id}-{safe_title}.md"
        key = f"{project_folder}/labguide/{filename}"
        try:
            cuerpo = reparar_markdown(lab_guide)
        except Exception as repair_exc:
            print(f"    ⚠️ Markdown repair skipped for {lab_id}: {repair_exc}")
            cuerpo = lab_guide

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=cuerpo.encode('utf-8'),
            ContentType='text/markdown'
        )
        
        print(f"    💾 Saved to s3://{bucket}/{key}")
        return key
    
    except Exception as e:
        print(f"    ❌ Error saving lab guide: {e}")
        raise


def _guardar_guia_con_reintento(
    bucket: str,
    project_folder: str,
    lab_id: str,
    lab_title: str,
    lab_guide: str,
    intentos: int = 3,
) -> str:
    """Retry the S3 write. An empty string means the lab was reported, not raised."""
    for intento in range(1, max(1, intentos) + 1):
        try:
            return save_lab_guide_to_s3(
                bucket=bucket,
                project_folder=project_folder,
                lab_id=lab_id,
                lab_title=lab_title,
                lab_guide=lab_guide,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    ⚠️ Save retry {intento}/{intentos} for {lab_id}: {exc}")
            if intento < intentos:
                time.sleep(min(2.0, 0.2 * intento))
    return ""


def _entregar_placeholders_tras_fallo(event: dict, exc: Exception) -> Optional[dict]:
    """If the handler crashes after the lab ids are known, still return a placeholder batch."""
    if not isinstance(event, dict):
        return None
    ids = [lab for lab in (event.get("lab_ids") or []) if lab]
    bucket = event.get("course_bucket")
    project = event.get("project_folder")
    if not ids or not bucket or not project:
        return None
    motivo = str(exc)[:500]
    keys = []
    avisos = []
    for lab_id in ids:
        texto = markdown_de_laboratorio_pendiente(lab_id, lab_id, motivo)
        key = _guardar_guia_con_reintento(bucket, project, lab_id, lab_id, texto)
        if key:
            keys.append(key)
        avisos.append(
            {
                "lab_id": lab_id,
                "findings": [
                    {"verificacion": "PLACEHOLDER", "confianza": "media", "valor": motivo[:300]}
                ],
            }
        )
    print(f"⚠️ Returning {len(keys)} placeholder lab(s) after {type(exc).__name__}")
    return {
        "statusCode": 200,
        "lab_guides_generated": len(keys),
        "lab_guide_keys": keys,
        "project_folder": project,
        "bucket": bucket,
        "model_provider": event.get("model_provider") or "bedrock",
        "quality_status": "placeholder",
        "quality_summary": "PENDIENTE DE REGENERACIÓN / PENDING REGENERATION",
        "labs_needing_review": [],
        "quality_warnings": avisos,
        "placeholders": [{"lab_id": lab_id, "reason": motivo} for lab_id in ids],
        "failed_lab_ids": list(ids),
        "models_used": {},
    }


def _strip_outer_markdown_fence(text: str) -> str:
    """If the model wrapped the whole lab in ```markdown ... ```, unwrap it."""
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if not lines:
        return t
    first = lines[0].strip()
    if not first.startswith("```"):
        return t
    for i in range(1, len(lines)):
        if lines[i].strip() == "```":
            return "\n".join(lines[1:i]).strip()
    return t


def _looks_like_lab_markdown(text: str) -> bool:
    """Heuristic: enough structure to treat as a lab guide when delimiters/JSON fail."""
    s = text.strip()
    if len(s) < 320:
        return False
    head = s[:4000]
    if s.startswith("#") or s.startswith("```"):
        return True
    if "##" in head:
        return True
    # Spanish / English common lab section cues
    cues = (
        "Metadatos",
        "Metadata",
        "Descripción",
        "Overview",
        "Objetivos",
        "Prerrequisitos",
        "Prerequisites",
        "Instrucciones",
        "Step-by-Step",
        "Paso ",
        "Laboratorio",
        "Lab ",
        "Entorno de Laboratorio",
        "Descripción General",
    )
    return any(c in head for c in cues)


def _normalize_lab_delimiters(text: str) -> str:
    """Models sometimes vary delimiter casing; normalize before splitting."""
    if not text:
        return text
    out = text
    pairs = (
        ("---lab_start---", "---LAB_START---"),
        ("---Lab_Start---", "---LAB_START---"),
        ("---LAB_start---", "---LAB_START---"),
        ("---lab_end---", "---LAB_END---"),
        ("---Lab_End---", "---LAB_END---"),
        ("---markdown---", "---MARKDOWN---"),
        ("---Markdown---", "---MARKDOWN---"),
    )
    for old, new in pairs:
        out = out.replace(old, new)
    return out


def _lesson_context_block(lesson_content: str) -> str:
    """Lesson excerpt for prompts (no Python comment leakage into the model)."""
    if not (lesson_content or "").strip():
        return ""
    excerpt = lesson_content[:LESSON_CONTEXT_MAX_CHARS]
    return f"""
═══════════════════════════════════════════════════════════════════════════════
CONTEXT: ACTUAL LESSON CONTENT
═══════════════════════════════════════════════════════════════════════════════
The user has just learned the following material. The lab MUST be based on this content.
Use specific commands, configurations, and concepts from this lesson where applicable.

{excerpt}
═══════════════════════════════════════════════════════════════════════════════
"""


def _get_previous_lab_context(bucket: str, project_folder: str, prev_lab_id: str) -> str:
    """Do not inject the previous lab. Each practice must run alone.

    The live prompt used to paste the previous guide and order the model to reuse
    its files, database names, ports and directories. That instruction is gone:
    a student opening only this chapter must not need the previous one.
    The arguments stay so older callers keep a stable signature.
    """
    del bucket, project_folder, prev_lab_id
    return ""


# Office, mail and tabular inputs the student cannot invent. A lab that names
# one of these without a source gets an inline fictitious annex.
_EXTENSIONES_ANEXO = frozenset(
    {"xlsx", "xlsm", "xls", "csv", "tsv", "docx", "doc", "eml"}
)
_TITULO_ANEXO_ES = "Anexo (datos ficticios)"
_TITULO_ANEXO_EN = "Annex (fictitious data)"


def _extension_de_entrada(nombre: str) -> str:
    base = os.path.basename((nombre or "").replace("\\", "/").rstrip("/"))
    if "." not in base:
        return ""
    return base.rsplit(".", 1)[-1].lower()


def _entradas_para_anexo(informe: dict) -> list[str]:
    """High-confidence B1 inputs that this chapter must carry itself.

    Excel, Word, ``.eml``, CSV and SharePoint ``/sites/`` paths. A file created
    in an earlier lab does not count: the audit is called without ``creados_antes``.
    """
    vistos: list[str] = []
    claves: set[str] = set()
    for hallazgo in (informe or {}).get("violaciones") or []:
        if hallazgo.get("verificacion") != "B1" or hallazgo.get("confianza") != "alta":
            continue
        valor = str(hallazgo.get("valor") or "").strip().rstrip(".,;:")
        if not valor:
            continue
        ruta = valor.replace("\\", "/")
        base = os.path.basename(ruta.rstrip("/")) or ruta
        extension = _extension_de_entrada(base)
        sharepoint = "/sites/" in ruta.lower()
        if extension not in _EXTENSIONES_ANEXO and not sharepoint:
            continue
        objetivo = base if extension in _EXTENSIONES_ANEXO else ruta
        clave = objetivo.lower()
        if clave in claves:
            continue
        claves.add(clave)
        vistos.append(objetivo)
    return vistos


def _cuerpo_ficticio(nombre: str, is_spanish: bool) -> str:
    """Inline fictitious payload. No extra filenames, so the annex adds no new dependency."""
    extension = _extension_de_entrada(nombre)
    if extension in {"csv", "tsv"}:
        separador = "\t" if extension == "tsv" else ","
        columnas = (
            ["region", "producto", "unidades"]
            if is_spanish
            else ["region", "product", "units"]
        )
        filas = [
            separador.join(columnas),
            separador.join(["Norte" if is_spanish else "North", "Alfa", "120"]),
            separador.join(["Sur" if is_spanish else "South", "Beta", "80"]),
        ]
        return "```" + extension + "\n" + "\n".join(filas) + "\n```\n"
    if extension in {"xlsx", "xlsm", "xls"}:
        if is_spanish:
            return (
                "| region | producto | unidades |\n"
                "| --- | --- | --- |\n"
                "| Norte | Alfa | 120 |\n"
                "| Sur | Beta | 80 |\n"
            )
        return (
            "| region | product | units |\n"
            "| --- | --- | --- |\n"
            "| North | Alfa | 120 |\n"
            "| South | Beta | 80 |\n"
        )
    if extension in {"docx", "doc"}:
        if is_spanish:
            return (
                "Titulo: Nota interna de practica\n\n"
                "Este documento es ficticio. Describe un pedido de ejemplo de 120 unidades "
                "y una conclusion breve para que los resultados se puedan comparar.\n"
            )
        return (
            "Title: Internal practice note\n\n"
            "This document is fictitious. It describes a sample order of 120 units "
            "and a short conclusion so results stay comparable.\n"
        )
    if extension == "eml":
        if is_spanish:
            mensaje = (
                "From: aviso@ejemplo.test\n"
                "To: alumno@ejemplo.test\n"
                "Subject: Caso de practica\n"
                "Date: Mon, 1 Jan 2024 09:00:00 +0000\n"
                "MIME-Version: 1.0\n"
                "Content-Type: text/plain; charset=utf-8\n"
                "\n"
                "Este mensaje es ficticio. El pedido de ejemplo tiene 120 unidades.\n"
            )
        else:
            mensaje = (
                "From: notice@example.test\n"
                "To: student@example.test\n"
                "Subject: Practice case\n"
                "Date: Mon, 1 Jan 2024 09:00:00 +0000\n"
                "MIME-Version: 1.0\n"
                "Content-Type: text/plain; charset=utf-8\n"
                "\n"
                "This message is fictitious. The sample order is 120 units.\n"
            )
        return "```text\n" + mensaje + "```\n"
    if is_spanish:
        return (
            "Inventario ficticio del sitio:\n\n"
            "- Elemento Alfa: 120 unidades\n"
            "- Elemento Beta: 80 unidades\n"
        )
    return (
        "Fictitious site inventory:\n\n"
        "- Item Alfa: 120 units\n"
        "- Item Beta: 80 units\n"
    )


def _seccion_anexo(nombre: str, is_spanish: bool) -> str:
    mostrado = (nombre or "").replace("`", "").strip()
    cuerpo = _cuerpo_ficticio(mostrado, is_spanish)
    if is_spanish:
        intro = (
            f"Guarde el archivo `{mostrado}` con el contenido siguiente. "
            "Los datos son ficticios y bastan para ejecutar esta práctica sin archivos externos."
        )
    else:
        intro = (
            f"Save the file `{mostrado}` with the following content. "
            "The data is fictitious and is enough to run this practice with no external files."
        )
    # `cat >` is already a creation mark, so the annex counts as delivered in
    # this lab for both Spanish (``guarde``) and English guides.
    return f"### {mostrado}\n\n{intro}\n\ncat > {mostrado}\n\n{cuerpo}"


def anexar_entradas_no_entregadas(
    markdown: str, informe: dict, is_spanish: bool = True
) -> str:
    """Inline fictitious annexes for input files this lab needs and nobody delivered.

    The heading is ``Anexo (datos ficticios)`` in Spanish guides. A file already
    present under that heading is left as it is.
    """
    pendientes = [
        nombre
        for nombre in _entradas_para_anexo(informe)
        if f"### {nombre}" not in (markdown or "")
    ]
    if not pendientes:
        return markdown
    titulo = _TITULO_ANEXO_ES if is_spanish else _TITULO_ANEXO_EN
    bloques = "".join(_seccion_anexo(nombre, is_spanish) for nombre in pendientes)
    if titulo in (markdown or ""):
        return (markdown or "").rstrip() + "\n\n" + bloques
    if is_spanish:
        intro = (
            f"## {titulo}\n\n"
            "Este anexo contiene datos ficticios para que la práctica se ejecute sola, "
            "sin archivos de un laboratorio anterior ni contenido de SharePoint.\n\n"
        )
    else:
        intro = (
            f"## {titulo}\n\n"
            "This annex holds fictitious data so the practice runs on its own, "
            "without files from a previous lab or SharePoint content.\n\n"
        )
    return (markdown or "").rstrip() + "\n\n" + intro + bloques


def _verify_and_refine_lab_guide(
    lab_guide: str,
    lab_plan: dict,
    master_context: dict,
    model_provider: str = "bedrock"
) -> str:
    """
    Automated verification pass: checks for unresolved placeholders or critical structural issues.
    Performs a single targeted refinement pass if needed.
    """
    lab_id = lab_plan.get('lab_id', 'Unknown')
    issues = []
    
    # Check for unresolved generic placeholders
    placeholders = re.findall(r'<[A-Z0-9_\-\s]{3,30}>|\[INSERT\s+[^\]]+\]|YOUR_PASSWORD_HERE|YOUR_API_KEY_HERE', lab_guide)
    if placeholders:
        issues.append(f"Unresolved placeholders found: {set(placeholders)}")

    # Check for minimum reasonable length
    if len(lab_guide.strip()) < 800:
        issues.append("Lab guide is incomplete or too short.")

    if not issues:
        return lab_guide

    print(f"  🔍 Verification found issues in Lab {lab_id}: {issues}")
    print(f"  ✨ Running automated refinement pass with Opus 4.6...")
    
    refinement_prompt = f"""You are an expert technical instructor refining a lab guide for Lab {lab_id}.

ISSUES DETECTED:
{chr(10).join('- ' + i for i in issues)}

LAB GUIDE CONTENT TO FIX:
{lab_guide[:12000]}

REQUIREMENTS:
- Replace generic placeholders (e.g. <YOUR_PASSWORD>, [INSERT HERE]) with visible markers such as [POR CONFIRMAR] or with values already stated in the manual—never invent passwords, API keys, hostnames or local paths.
- For Copilot/LLM/AI steps, Expected output must be a bullet list of required elements, not a verbatim model response.
- Ensure command syntax is valid and executable when commands are present.
- Return the COMPLETE corrected Markdown lab guide. Use the same ASCII delimiters (---LAB_START--- / ---MARKDOWN--- / ---LAB_END---).
"""
    try:
        if model_provider == "bedrock":
            refined = call_bedrock_agent(refinement_prompt, DEFAULT_BEDROCK_MODEL)
            if "---MARKDOWN---" in refined:
                header_part, rest = refined.split("---MARKDOWN---", 1)
                refined = rest.split("---LAB_END---")[0].strip()
            if len(refined.strip()) > 800:
                print(f"  ✅ Verification refinement pass completed ({len(refined)} chars)")
                return refined.strip()
    except Exception as ex:
        print(f"  ⚠️ Verification refinement pass skipped due to error: {ex}")

    return lab_guide


def _compact_single_lab_prompt(
    lab_plan: dict,
    master_context: dict,
    lesson_context_section: str,
    labs_summary_text: str,
    previous_lab_context_section: str = "",
) -> str:
    """
    Short prompt for the common case (one lab per Lambda).
    Avoids ~15k+ tokens of duplicated schema example that inflated input and output.
    """
    tl = master_context.get("target_language", "English")
    hw = master_context.get("hardware_requirements", []) or []
    sw = master_context.get("software_requirements", []) or []
    spec = master_context.get("special_considerations", []) or []
    objs = master_context.get("overall_objectives", []) or []
    hw_line = ", ".join(str(x) for x in hw[:10]) if hw else "N/A"
    sw_bits: List[str] = []
    for item in (sw or [])[:14]:
        if isinstance(item, dict):
            sw_bits.append(
                f"{item.get('name', '?')} ({item.get('version', '')})"
            )
        else:
            sw_bits.append(str(item))
    sw_line = ", ".join(sw_bits) if sw_bits else "N/A"
    spec_line = "; ".join(str(x) for x in spec[:6]) if spec else "N/A"
    obj_line = "; ".join(str(x) for x in objs[:6]) if objs else "N/A"
    lid = lab_plan["lab_id"]
    is_demo = is_demo_plan(lab_plan)
    title = ensure_demo_title(lab_plan["lab_title"]) if is_demo else lab_plan["lab_title"]
    is_spanish = "spanish" in tl.lower() or "español" in tl.lower() or "es" in tl.lower()

    demo_note_block = (
        "> ℹ️ **Nota:** Esta práctica es una **Demostración realizada por el instructor**. "
        "El instructor ejecutará los pasos y comandos mientras los alumnos observan, toman notas y analizan el procedimiento, en lugar de realizarla individualmente."
        if is_spanish
        else
        "> ℹ️ **Note:** This activity is an **Instructor-Led Demonstration**. "
        "The instructor will perform the steps and commands while students observe, take notes, and analyze the procedure, rather than performing it individually."
    )

    demo_section = (
        f"""
DEMO / DEMOSTRACIÓN (INSTRUCTOR-LED REQUIREMENT):
CRITICAL: This activity is an INSTRUCTOR DEMONSTRATION conducted live by the instructor (NOT an individual student lab).
- The H1 title MUST include the word 'Demo' (e.g., # Lab {lid}: {title}).
- In the Overview section (Descripción General), you MUST include this exact notice block:
  {demo_note_block}
- Frame all step-by-step instructions for the instructor to demonstrate clearly to the students.
"""
        if is_demo
        else ""
    )

    overview_rule = (
        "2. ## Descripción General — 2–4 sentences (MUST include the instructor Demo notice block right below this heading)"
        if is_demo and is_spanish
        else
        "2. ## Overview — 2–4 sentences (MUST include the instructor Demo notice block right below this heading)"
        if is_demo
        else
        "2. ## Descripción General — 2–4 sentences"
        if is_spanish
        else
        "2. ## Overview — 2–4 sentences"
    )
    structure_block = (
        """STRUCTURE (exactly ONE H1 for the lab title; nested sample documents must be ### or ####, never a second # heading).
H2 titles MUST be these exact Spanish strings — do not use synonyms such as "Requisitos previos", "Procedimiento paso a paso", or "Entorno del laboratorio":
1. ## Metadatos — table: Duration, Complexity, Bloom level
"""
        + overview_rule + """
3. ## Objetivos de Aprendizaje — 3–5 checkboxes
4. ## Prerrequisitos — knowledge + access
5. ## Entorno de Laboratorio — concise HW/SW tables if useful + setup commands
6. ## Instrucciones Paso a Paso — each step heading MUST be `### Paso N: Title` (colon, not period) with **Objective**, numbered **Instructions**, **Expected output** (opcional si no aporta), **Verification**
   - Paso con comando/fichero determinista: **Expected output** = salida o bloque de código verificable.
   - Paso con Copilot/LLM/IA: **Expected output** = lista con viñetas de elementos requeridos; nunca el párrafo literal del modelo. Omite la sección si **Verification** ya lista esos elementos.
7. ## Validación y Pruebas
8. ## Solución de Problemas — **exactly 2** realistic issues (symptoms, cause, fix)
9. ## Limpieza
10. ## Resumen (+ optional resources)
"""
        if is_spanish
        else
        """STRUCTURE (exactly ONE H1 for the lab title; nested sample documents must be ### or ####, never a second # heading).
H2 titles MUST be these exact English strings:
1. ## Metadata — table: Duration, Complexity, Bloom level
"""
        + overview_rule + """
3. ## Learning Objectives — 3–5 checkboxes
4. ## Prerequisites — knowledge + access
5. ## Lab Environment — concise HW/SW tables if useful + setup commands
6. ## Step-by-Step Instructions — each step heading MUST be `### Step N: Title` with **Objective**, numbered **Instructions**, **Expected output** (optional when not meaningful), **Verification**
   - Deterministic command/file step: **Expected output** = console output or fenced code block.
   - Copilot/LLM/AI step: **Expected output** = bullet list of required elements; never a verbatim model paragraph. Omit the section when **Verification** already states those checks.
7. ## Validation & Testing
8. ## Troubleshooting — **exactly 2** realistic issues (symptoms, cause, fix)
9. ## Cleanup
10. ## Summary (+ optional resources)
"""
    )

    add_req = master_context.get("additional_requirements", "")
    add_req_section = (
        f"""
USER REQUIREMENTS (CRITICAL - MUST BE INCORPORATED):
{add_req}
"""
        if add_req and add_req.strip()
        else ""
    )

    # C2: lo que la petición declara del entorno se extrae de forma determinista
    # y se repite como reglas operativas. Medido en producción (28/10/2026, curso
    # de Agent Skills): con la petición textual en el prompt el modelo ignoró las
    # prohibiciones (277 bloques bash frente a un pedido de PowerShell).
    entorno = entorno_de_peticion(add_req)
    if entorno:
        lineas_entorno = [
            "ENVIRONMENT CONSTRAINTS (from the user request — the lab is audited against these):"
        ]
        if entorno.get("os_requerido"):
            lineas_entorno.append(
                f"- Required operating system: {', '.join(entorno['os_requerido'])}."
            )
        if entorno.get("os_prohibido"):
            lineas_entorno.append(f"- Prohibited systems/shells: {', '.join(entorno['os_prohibido'])}.")
        if entorno.get("etiquetas"):
            lineas_entorno.append(
                "- Label EVERY command code block with the language "
                f"{' or '.join(entorno['etiquetas'])}; never use another shell label."
            )
        if entorno.get("prohibidos"):
            lineas_entorno.append(
                "- Absolutely no use of: "
                + ", ".join("`" + p + "`" for p in entorno["prohibidos"])
                + "."
            )
        lineas_entorno.append(
            "- Every command must run as written on the machine the user request defines; "
            "no workarounds with another shell."
        )
        entorno_section = "\n".join(lineas_entorno) + "\n"
    else:
        entorno_section = ""

    presupuesto = presupuesto_de_duracion(
        lab_plan.get("estimated_duration") or lab_plan.get("duration_minutes")
    )
    presupuesto = adjust_presupuesto(presupuesto, master_context.get("audience_profile"))
    audience_section = writer_audience_block(master_context.get("audience_profile") or {}, is_spanish)
    if presupuesto and is_spanish:
        presupuesto_section = f"""
PRESUPUESTO DE DURACIÓN (REQUISITO DURO: LOS TIEMPOS DEL TEMARIO SE CUMPLEN):
El laboratorio está declarado en {presupuesto['declarada']} minutos y debe caber en ellos. El trabajo
se mide a 2 minutos por paso con acción y 0,75 por bloque de código:
- Máximo {presupuesto['pasos_max']} pasos con acción y {presupuesto['bloques_max']} bloques: por encima, el laboratorio no cabe en su hueco.
- Objetivo: unos {presupuesto['pasos_objetivo']} pasos y {presupuesto['bloques_objetivo']} bloques. El resto del tiempo es lectura, verificación, diagnóstico y los dos casos de solución de problemas.
- No añadas comandos para llenar tiempo ni recortes los tópicos del temario para ahorrarlo: si no cabe, prioriza y dilo en el Resumen.
- La tabla de metadatos debe declarar exactamente {presupuesto['declarada']} minutos.
"""
    elif presupuesto:
        presupuesto_section = f"""
DURATION BUDGET (HARD REQUIREMENT: THE COURSE TIMES MUST HOLD):
This lab is declared at {presupuesto['declarada']} minutes and must fit in them. Work is measured at
2 minutes per action step and 0.75 per code block:
- At most {presupuesto['pasos_max']} action steps and {presupuesto['bloques_max']} code blocks: beyond that, the lab does not fit.
- Target: about {presupuesto['pasos_objetivo']} steps and {presupuesto['bloques_objetivo']} blocks. The remaining time is reading, verification, diagnosis and the two troubleshooting cases.
- Do not add commands just to fill time, and do not drop the syllabus topics to save it: if it does not fit, prioritise and say so in the Summary.
- The metadata table MUST declare exactly {presupuesto['declarada']} minutes.
"""
    else:
        presupuesto_section = ""

    minutos_lectura = lab_plan.get("estimated_duration") or lab_plan.get("duration_minutes")
    lectura_section = _texto_presupuesto_lectura(minutos_lectura, en_espanol=is_spanish)
    lectura_corr = master_context.get("reading_budget_correction", "")
    lectura_corr_section = (
        f"\n{lectura_corr}\n" if lectura_corr and str(lectura_corr).strip() else ""
    )

    etiqueta_anexo = _TITULO_ANEXO_ES if is_spanish else _TITULO_ANEXO_EN
    # previous_lab_context_section is ignored: the live prompt must not tell the
    # model to reuse the previous lab's files or outputs.
    del previous_lab_context_section
    autocontenido_section = f"""
SELF-CONTAINED PRACTICE (HARD REQUIREMENT):
This lab must run alone. Do not reuse files, outputs, database names, container names, usernames, ports or directories from any previous lab, and do not tell the student that those already exist.
When the lab needs an input file (Excel, Word, .eml, CSV or SharePoint content) that the syllabus or the manual does not deliver, inline that content in this lab under the heading "{etiqueta_anexo}" and state that the data is fictitious.
"""

    # Paso 0 de calidad: este es el builder que el handler SIEMPRE usa (el handler
    # llama a generate_all_labs_batch con UN solo lab, línea ~1946). Antes el manual
    # llegaba aquí por accidente: el planner lo colaba en additional_requirements
    # (primeros 10k caracteres, etiquetados como "USER REQUIREMENTS"). Ahora se
    # seleccionan las secciones relevantes para ESTE laboratorio.
    manual_excerpt = select_manual_context(
        master_context.get("manual_reference_text", ""),
        query_text=flatten_to_text(lab_plan),
        title_text=title,
        label=lid,
    )
    manual_section = (
        f"""
REFERENCE MANUAL (SOURCE OF TRUTH):
CRITICAL: Base all instructions, data, entities, figures and expected outputs on the
reference manual content below. Do not invent data, product names, funds, SKUs,
deliverables or tools that are not present in it.
=== REFERENCE MANUAL CONTENT ===
{manual_excerpt}
=== END REFERENCE MANUAL ===
"""
        if manual_excerpt and manual_excerpt.strip()
        else ""
    )

    # Reintento correctivo de B1: se le devuelven al modelo los ficheros y rutas que
    # no están en ninguna fuente y que ningún paso anterior crea.
    correction = master_context.get("referential_correction", "")
    correction_section = (
        f"""
CORRECCIÓN OBLIGATORIA (integridad referencial):
{correction}
Regla de tres niveles: solo puedes afirmar un dato si (a) está en el temario, el manual o el
plan de prácticas, o (b) un paso anterior de este mismo laboratorio lo crea. Si no se cumple,
omítelo o escríbelo como [POR CONFIRMAR]. No introduzcas nombres de fichero ni rutas nuevas.
"""
        if correction and correction.strip()
        else ""
    )

    golden_section = build_golden_lab_prompt_section(lab_plan, master_context)
    evidencia_corr = master_context.get("validation_evidence_correction", "")
    evidencia_section = (
        f"""
{evidencia_corr}
"""
        if evidencia_corr and evidencia_corr.strip()
        else ""
    )
    # A2e: names, places, deliverables and prohibitions the syllabus states.
    # The block is empty when nothing was declared, so a normal guide is unchanged.
    anclajes_section = texto_de_anclajes(
        master_context.get("syllabus_text") or "",
        en_espanol=is_spanish,
    )
    # C6: the verified catalog, plus the names rejected on the previous attempt.
    regla_moneda = texto_de_catalogo_para_prompt(is_spanish)
    currency = master_context.get("currency_correction", "")
    currency_section = (
        f"""
CORRECCIÓN OBLIGATORIA (moneda de Microsoft 365 Copilot):
{currency}
No dejes el nombre rechazado en el texto. Si no está en el catálogo ni en el manual,
escríbelo como [POR CONFIRMAR].
"""
        if currency and str(currency).strip()
        else ""
    )

    return f"""You are an expert technical instructor. Generate ONE complete lab guide in Markdown.

LANGUAGE: All section titles and prose in **{tl}**. Code/commands may remain in English.

COURSE CONTEXT (brief):
- Objectives: {obj_line}
- Typical hardware: {hw_line}
- Typical software: {sw_line}
- Notes: {spec_line}
{add_req_section}
{entorno_section}
{anclajes_section}
{manual_section}
{correction_section}
{evidencia_section}
{currency_section}
{regla_moneda}
LAB SPECIFICATION:
{labs_summary_text}
{autocontenido_section}
{lesson_context_section}
{demo_section}
{audience_section}

{structure_block}
{presupuesto_section}
{lectura_section}
{lectura_corr_section}
QUALITY: Be thorough and professional, but **concise**. Stay inside the reading budget above. Do not pad with generic filler.

{THOR_QUALITY_RULES}
{golden_section}OUTPUT FORMAT (required; use these exact ASCII delimiters, case-sensitive):
---LAB_START---
LAB_ID: {lid}
---MARKDOWN---
# Lab {lid}: {title}
...complete markdown following the structure...
---LAB_END---

Do not wrap the delimiters in code fences. No preamble before ---LAB_START---.
"""


def _sin_marcas(texto: str) -> str:
    """Texto comparable: sin markdown, sin espacios de más, en minúsculas."""
    limpio = re.sub(r"[*_`#>\[\]()]", " ", str(texto or ""))
    return " ".join(limpio.split()).strip().lower()


def asegurar_objetivo_declarado(markdown: str, lab_plan: dict, is_spanish: bool = True):
    """A5: deja el objetivo del temario en la guía, literal, como primer objetivo.

    El plan ya lo trae en ``objectives[0]`` y el prompt lo pide literal, pero el modelo
    lo reescribe: medido el 22/10/2026 sobre un curso real (``251128-python-intro``), el
    objetivo declarado no aparecía en la sección de objetivos de la guía generada.

    Se inserta de forma determinista **solo si falta**, para no duplicar cuando el
    modelo sí lo respetó. Si la guía no tiene sección de objetivos, no se inventa
    estructura: se deja como está y lo dirá la puerta.
    """
    objetivo = " ".join(str((lab_plan or {}).get("outline_objective") or "").split())
    if not objetivo:
        return markdown, False
    if _sin_marcas(objetivo) in _sin_marcas(markdown):
        return markdown, False

    separador = "\r\n" if "\r\n" in markdown else "\n"
    lineas = markdown.splitlines()
    titulos = ("Objetivos de Aprendizaje", "Learning Objectives")

    for indice, linea in enumerate(lineas):
        if not linea.strip().startswith("## "):
            continue
        if not any(titulo.lower() in linea.lower() for titulo in titulos):
            continue

        for posicion in range(indice + 1, min(indice + 10, len(lineas))):
            es_item = re.match(r"^\s*[-*]\s+", lineas[posicion])
            if es_item:
                lineas.insert(posicion, f"- [ ] {objetivo}")
                return separador.join(lineas), True
        lineas.insert(indice + 1, f"- [ ] {objetivo}")
        return separador.join(lineas), True

    return markdown, False


def _contrato_declarado(lab_plan: dict) -> str:
    """A5: lo que el instructor declaró en el temario, tal cual, para el prompt.

    El plan ya trae copiado el objetivo del temario en ``objectives[0]``; aquí se le
    recuerda al modelo que ese texto es el contrato aprobado y que no puede
    reescribirlo. Devuelve ``""`` cuando el temario no declaró nada, que es el caso
    mayoritario del corpus: el temario no gana campos obligatorios.
    """
    objetivo = lab_plan.get("outline_objective")
    descripcion = lab_plan.get("outline_description")
    if not objetivo and not descripcion:
        return ""
    lineas = [
        "CONTRACT - DECLARED BY THE INSTRUCTOR IN THE COURSE OUTLINE "
        "(deliver exactly this; copy the objective verbatim and do not reword or contradict it):"
    ]
    if objetivo:
        lineas.append(f"- Declared objective (verbatim): {objetivo}")
        lineas.append(
            "- The FIRST bullet of the objectives section MUST be exactly this text, "
            f"unchanged: `- [ ] {objetivo}`. Further objectives may be added after it."
        )
    if descripcion:
        lineas.append(f"- Declared description (verbatim): {descripcion}")
    return "\n".join(lineas) + "\n"


def _resumen_de_labs(lab_plans: List[Dict[str, Any]]) -> str:
    """Resumen de los laboratorios para el prompt, con los tópicos de su temario.

    Los tópicos llegan del outline a través del plan (``context_topics``). Son el
    ancla de materia: el laboratorio puede añadir procedimiento (comandos, pasos,
    comprobaciones), no materia nueva. Antes no se imprimían y la alineación
    dependía solo del ``scope`` y del texto de la teoría.

    La duración lleva su presupuesto de volumen (pasos y bloques que caben): el
    writer debe llenar el hueco, no desbordarlo.
    """
    labs_summary = []
    for lab in lab_plans:
        is_demo = is_demo_plan(lab)
        lab_title_formatted = ensure_demo_title(lab['lab_title']) if is_demo else lab['lab_title']
        demo_tag = " (TIPO: DEMOSTRACIÓN / DEMO DEL INSTRUCTOR)" if is_demo else ""
        topicos = [
            " ".join(str(t).split())
            for t in (lab.get('context_topics') or [])
            if str(t).strip()
        ]
        topicos_linea = (
            "\n- Lesson topics (the lab MUST exercise these; do not introduce subject "
            f"matter beyond them): {'; '.join(topicos[:12])}"
            if topicos
            else ""
        )
        presupuesto = presupuesto_de_duracion(
            lab.get('estimated_duration') or lab.get('duration_minutes')
        )
        presupuesto_linea = (
            f" (budget: up to {presupuesto['pasos_max']} action steps and "
            f"{presupuesto['bloques_max']} code blocks)"
            if presupuesto
            else ""
        )
        labs_summary.append(f"""
**Lab {lab['lab_id']}: {lab_title_formatted}**{demo_tag}
- Duration: {lab['estimated_duration']} minutes{presupuesto_linea}
- Complexity: {lab.get('complexity', 'medium')}
- Bloom Level: {lab['bloom_level']}
- Objectives: {', '.join(lab['objectives'])}
- Scope: {lab['scope']}
- Prerequisites: {', '.join(lab.get('prerequisites', []))}
- Technologies: {', '.join(lab.get('key_technologies', []))}{topicos_linea}
{_contrato_declarado(lab)}""")
    return "".join(labs_summary)


def generate_all_labs_batch(
    lab_plans: List[Dict[str, Any]],
    master_context: dict,
    model_provider: str = "bedrock",
    lesson_content: str = "",
    previous_lab_context: str = ""
) -> Dict[str, str]:
    """
    Generate ALL lab guides in a SINGLE API call for efficiency.
    
    Returns dict mapping lab_id to markdown content.
    """
    print(f"\n🚀 Generating {len(lab_plans)} labs in SINGLE API CALL...")
    lesson_context_section = _lesson_context_block(lesson_content)

    # Build comprehensive prompt for ALL labs
    labs_summary_text = _resumen_de_labs(lab_plans)

    if len(lab_plans) == 1:
        print("📎 Using compact single-lab prompt (smaller input, faster generation).")
        prompt = _compact_single_lab_prompt(
            lab_plans[0], master_context, lesson_context_section, labs_summary_text, previous_lab_context_section=previous_lab_context
        )
    else:
        prompt = f"""
You are an expert technical instructor creating detailed, professional laboratory guides.

LANGUAGE REQUIREMENT:
**GENERATE ALL LAB CONTENT IN: {master_context.get('target_language', 'English')}**

- ALL section titles MUST be in {master_context.get('target_language', 'English')}
- ALL instructions, explanations, descriptions must be in {master_context.get('target_language', 'English')}
- Code commands can remain in their original language (usually English)
- Technical terms may remain in English where appropriate

If generating in Spanish, use these EXACT H2 titles (no synonyms):
- "Metadatos" instead of "Metadata"
- "Descripción General" instead of "Overview"
- "Objetivos de Aprendizaje" instead of "Learning Objectives"
- "Prerrequisitos" instead of "Prerequisites" (NOT "Requisitos previos")
- "Entorno de Laboratorio" instead of "Lab Environment" (NOT "Entorno del laboratorio")
- "Instrucciones Paso a Paso" instead of "Step-by-Step Instructions" (NOT "Procedimiento paso a paso")
- "### Paso N:" instead of "### Step N:" (colon required)
- "Validación y Pruebas" instead of "Validation & Testing"
- "Solución de Problemas" instead of "Troubleshooting"
- "Limpieza" instead of "Cleanup"
- "Resumen" instead of "Summary"
- "Referencias Bibliográficas" instead of "Bibliographic References"
Only one H1 is allowed (the lab title). Nested sample documents must be ### or ####.

MASTER CONTEXT:
Overall Objectives: {', '.join(master_context.get('overall_objectives', []))}

Hardware Requirements:
{chr(10).join('- ' + req for req in master_context.get('hardware_requirements', []))}

Software Requirements:
{chr(10).join(f"- {sw['name']} ({sw['version']}): {sw['purpose']}" for sw in master_context.get('software_requirements', []))}

Special Considerations:
{chr(10).join('- ' + con for con in master_context.get('special_considerations', []))}

{f"USER ADDITIONAL REQUIREMENTS (CRITICAL - MUST BE INCORPORATED INTO ALL LABS):{chr(10)}{master_context.get('additional_requirements')}" if master_context.get('additional_requirements') else ""}

{lesson_context_section}

LABS TO GENERATE ({len(lab_plans)} total):
{chr(10).join(labs_summary)}

═══════════════════════════════════════════════════════════════════════════════
MANDATORY LAB GUIDE STRUCTURE SCHEMA (FOLLOW EXACTLY FOR EACH LAB)
═══════════════════════════════════════════════════════════════════════════════

Each lab MUST follow this EXACT structure with proper heading hierarchy:

```
# Lab [LAB_ID]: [Lab Title]

## Metadata

| Property | Value |
|----------|-------|
| **Duration** | XX minutes |
| **Complexity** | Beginner/Intermediate/Advanced |
| **Bloom Level** | [Level] |

## Overview

[2-3 sentences describing what this lab accomplishes]
[Explain the practical value and real-world relevance]
[FOR DEMOS ONLY: Include mandatory notice: > ℹ️ **Nota:** Esta práctica es una **Demostración realizada por el instructor**. El instructor ejecutará los pasos y comandos mientras los alumnos observan, toman notas y analizan el procedimiento, en lugar de realizarla individualmente.]

## Learning Objectives

By completing this lab, you will be able to:

- [ ] [Objective 1 - specific and measurable]
- [ ] [Objective 2 - specific and measurable]
- [ ] [Objective 3 - specific and measurable]

## Objetivo visual (THOR)

Brief diagram or screenshot summary of lab tasks; include placeholder path such as `../images/lab-visual.png`.

## Prerequisites

### Required Knowledge

- [Prior concept or skill 1]
- [Prior concept or skill 2]

### Required Access

- [Account, permission, or credential 1]

## Lab Environment

### Hardware Requirements

| Component | Specification |
|-----------|---------------|
| [Component] | [Spec] |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| [Software] | [X.Y.Z] | [Why needed] |

### Initial Setup

```bash
# Setup commands
```

## Step-by-Step Instructions

### Step 1: [Clear Action Title]

**Objective:** [What this step accomplishes]

**Instructions:**

1. [First action]
   
   ```bash
   [exact command]
   ```

2. [Second action]

**Expected Output:**

```
[What user should see]
```

**Verification:**

- [How to confirm success]

---

### Step 2: [Next Action Title]

[Same structure - Objective, Instructions, Expected Output, Verification]

---

[Continue for all steps needed]

## Validation & Testing

### Success Criteria

- [ ] [Criterion 1 - testable]
- [ ] [Criterion 2 - testable]

### Testing Procedure

1. [Test action]
   ```bash
   [test command]
   ```
   **Expected Result:** [result]

## Troubleshooting

### Issue 1: [Problem Description]

**Symptoms:**
- [What user observes]

**Cause:**
[Why it happens]

**Solution:**
```bash
[fix command]
```

---

### Issue 2: [Another Problem]

[Same structure]

## Cleanup

```bash
# Cleanup commands
```

> ⚠️ **Warning:** [Important notes]

## Summary

### What You Accomplished

- [Accomplishment 1]
- [Accomplishment 2]

### Key Takeaways

- [Concept learned]

### Next Steps

- [Follow-up recommendation]

## Additional Resources

- [Resource 1] - [Description]
```

═══════════════════════════════════════════════════════════════════════════════
CRITICAL FORMATTING RULES
═══════════════════════════════════════════════════════════════════════════════

**HEADING HIERARCHY (MANDATORY):**
- H1 (#): ONLY for lab title - ONE per lab
- H2 (##): Major sections
- H3 (###): Steps, subsections, issues
- NEVER skip heading levels (H1 → H3 is INVALID)

**REQUIRED SECTIONS (ALL MUST BE PRESENT FOR EACH LAB):**
1. Metadata (H2) - Table with Duration, Complexity, Bloom Level
2. Overview (H2)
3. Learning Objectives (H2) - With checkboxes
4. Prerequisites (H2)
5. Lab Environment (H2)
6. Step-by-Step Instructions (H2) - Steps as H3
7. Validation & Testing (H2)
8. Troubleshooting (H2) - At least 2 issues
9. Cleanup (H2)
10. Summary (H2)

**STEP STRUCTURE (EVERY STEP MUST HAVE):**
- Objective, Instructions, Expected Output, Verification
- Use `---` between steps

**CODE BLOCKS:**
- REAL, EXECUTABLE commands - NO placeholders like <filename>
- Always specify language (bash, python, yaml, etc.)

**DEMOS / DEMOSTRACIONES (INSTRUCTOR-LED ACTIVITIES):**
- For any lab marked as a Demo or containing 'Demo' in its title, this activity is an INSTRUCTOR-LED DEMONSTRATION conducted live by the instructor while students observe.
- The H1 title MUST contain the word 'Demo' (e.g. # Lab [LAB_ID]: Demo: [Title]).
- Under Overview (Descripción General), you MUST include the instructor notice callout:
  > ℹ️ **Nota:** Esta práctica es una **Demostración realizada por el instructor**. El instructor ejecutará los pasos y comandos mientras los alumnos observan, toman notas y analizan el procedimiento, en lugar de realizarla individualmente.
- All steps should be framed for the instructor to demonstrate clearly to the class.

**THOR QUALITY RULES (MANDATORY - informe de mejoras):**
1. TERMINOLOGÍA: Distinguish a temporary instruction in a chat from a persistent agent/assistant. Use 'instrucción', 'prompt' and 'mensaje de sistema' correctly (no son sinónimos).
2. VERSIONES EXACTAS: Every technology MUST declare an exact version (edition + architecture) and an official source URL. Never use 'latest/última versión/versión actual/1.x/>=', or unresolvable placeholders. If unconfirmed, use '[VERSIÓN POR VALIDAR]' / '[ENLACE OFICIAL]'.
3. LICENCIAS Y HERRAMIENTAS: Differentiate Microsoft 365 Copilot, Copilot Chat, Designer, Planner and similar tools, stating the license and configuration for each.
4. DURACIÓN: Keep each lab within the time and complexity defined by the syllabus; for a 90-minute seminar prioritize effective tool usage.
5. DEPENDENCIAS: Reduce auxiliary files/dependencies; embed in the prompts any information that does not require an external file. Provide controlled scenarios, inputs and sources so results are comparable.
6. VALIDACIÓN MEDIBLE: Define measurable criteria and sufficient evidence (command, file, output, screenshot). For Copilot/LLM steps, Expected output must be a bullet list of required elements or sections—never a verbatim paragraph the model might return; omit Expected output when Verification already lists those checks. Do NOT claim production-ready from five generic tests, vague success rates, or invented passwords/paths.
7. LIMITACIONES DE IA: In Validation & Testing include at least one adversarial case: nonexistent/contradictory information, missing evidence, or instructions embedded in documents (prompt injection).
8. PROMPTING: Evaluate precision, traceability, uncertainty, usefulness and human supervision; do NOT require exposing internal reasoning as a success criterion.
9. PEDAGOGÍA: Favor experimentation and reinforcement over documentation/captures.

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (USE DELIMITERS)
═══════════════════════════════════════════════════════════════════════════════

---LAB_START---
LAB_ID: [lab_id]
---MARKDOWN---
# Lab [lab_id]: [Full Title]

[Complete markdown following the schema above]

---LAB_END---

---LAB_START---
LAB_ID: [next_lab_id]
---MARKDOWN---
# Lab [next_lab_id]: [Next Lab Title]
...
---LAB_END---

IMPORTANT: Use the delimiter format exactly as shown. Do NOT use JSON format.
Generate ALL {len(lab_plans)} labs now:
"""
    
    try:
        if model_provider == "openai":
            secret_data = get_secret("aurora/openai-api-key")
            api_key = secret_data.get('api_key') or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                print("⚠️  OpenAI API key not found, falling back to Bedrock")
                model_provider = "bedrock"
            else:
                response_text = call_openai_agent(prompt, api_key, DEFAULT_OPENAI_MODEL)
        
        elif model_provider in ("google", "gemini"):
            google_key = get_google_api_key()
            if not google_key:
                print("⚠️  Google API key not found, falling back to Bedrock")
                model_provider = "bedrock"
            else:
                response_text = call_gemini_agent(prompt, google_key)

        if model_provider == "bedrock":
            response_text = call_bedrock_agent(prompt, DEFAULT_BEDROCK_MODEL)
        
        print("✅ AI response received, parsing with delimiters...")
        # Keep full model output for fallbacks (JSON branch mutates working copies)
        original_response_text = response_text
        response_text = _normalize_lab_delimiters(response_text)

        # Parse using delimiters instead of JSON
        labs_dict = {}

        # Split by lab sections
        lab_sections = response_text.split('---LAB_START---')
        
        for section in lab_sections[1:]:  # Skip first empty split
            if '---LAB_END---' not in section:
                continue
            
            # Extract lab_id and markdown
            try:
                header_part, rest = section.split('---MARKDOWN---', 1)
                markdown_part = rest.split('---LAB_END---')[0].strip()
                
                # Extract lab_id from header (tolerate spacing / markdown noise)
                for line in header_part.split('\n'):
                    raw_line = line.strip()
                    if raw_line.upper().startswith("LAB_ID:"):
                        parsed_id = raw_line.split(":", 1)[1].strip().strip("*`_ ")
                        if parsed_id and markdown_part.strip():
                            labs_dict[parsed_id] = markdown_part
                            print(f"  ✓ Lab {parsed_id}: {len(markdown_part)} characters")
                        break
            except Exception as e:
                print(f"  ⚠️  Failed to parse lab section: {e}")
                continue
        
        if not labs_dict:
            print("⚠️  No labs found in response, trying fallback JSON parsing...")
            # Fallback to JSON if delimiter format failed
            try:
                json_candidate = original_response_text
                if "```json" in json_candidate:
                    json_candidate = json_candidate.split("```json")[1].split("```")[0]
                elif "```" in json_candidate:
                    json_candidate = json_candidate.split("```")[1].split("```")[0]
                
                result = json.loads(json_candidate.strip())
                for lab_data in result.get('labs', []):
                    lab_id = lab_data['lab_id']
                    markdown = lab_data['markdown']
                    labs_dict[lab_id] = markdown
                    print(f"  ✓ Lab {lab_id}: {len(markdown)} characters (from JSON)")
            except Exception as fallback_error:
                print(f"⚠️  Fallback JSON parsing also failed: {fallback_error}")
                
                # Third fallback: If only ONE lab requested and response looks like markdown, use it directly
                if len(lab_plans) == 1:
                    print("🔄 Trying raw markdown fallback for single lab...")
                    raw_response = _strip_outer_markdown_fence(original_response_text)
                    # Delimiter/JSON failed; accept substantial markdown (incl. Spanish section titles)
                    if raw_response and _looks_like_lab_markdown(raw_response):
                        lab_id = lab_plans[0]['lab_id']
                        labs_dict[lab_id] = raw_response.strip()
                        print(
                            f"  ✓ Lab {lab_id}: {len(raw_response)} characters (from raw markdown)"
                        )
                    else:
                        raise ValueError("Could not parse labs from AI response in any format")
                else:
                    raise ValueError("Could not parse labs from AI response in any format")

        # Single-lab: delimiters often drift (extra prose, wrong LAB_ID line). Recover before return.
        if len(lab_plans) == 1:
            exp = lab_plans[0]["lab_id"]
            cur = (labs_dict.get(exp) or "").strip()
            if not cur:
                if len(labs_dict) == 1:
                    only_k, only_v = next(iter(labs_dict.items()))
                    only_v = (only_v or "").strip()
                    if only_v:
                        labs_dict = {exp: only_v}
                        print(
                            f"  ✓ Remapped single lab key {only_k!r} → {exp!r} ({len(only_v)} chars)"
                        )
                        cur = only_v
                if not (labs_dict.get(exp) or "").strip():
                    print("🔄 Single-lab: delimiter parse empty; trying raw markdown fallback...")
                    raw = _strip_outer_markdown_fence(original_response_text)
                    if raw and _looks_like_lab_markdown(raw):
                        labs_dict[exp] = raw.strip()
                        print(
                            f"  ✓ Lab {exp}: {len(raw)} characters (raw markdown fallback)"
                        )
                    elif raw:
                        print(
                            f"  ⚠️ Raw response {len(raw)} chars but heuristic failed; preview: {raw[:400]!r}"
                        )

        target_lang = master_context.get('target_language', 'English')
        is_spanish = 'spanish' in target_lang.lower() or 'español' in target_lang.lower() or 'es' in target_lang.lower()
        for lid in list(labs_dict.keys()):
            plan = next((p for p in lab_plans if p.get('lab_id') == lid), None)
            is_demo = is_demo_plan(plan) if plan else False
            labs_dict[lid] = _finalize_lab_markdown(labs_dict[lid], is_demo=is_demo, is_spanish=is_spanish)
            # A5: el objetivo que aprobó el instructor no se queda fuera de la guía porque
            # el modelo lo haya parafraseado. Se inserta solo si falta.
            if plan:
                labs_dict[lid], insertado = asegurar_objetivo_declarado(
                    labs_dict[lid], plan, is_spanish=is_spanish
                )
                if insertado:
                    print(f"  📌 A5: objetivo del temario insertado en la guía {lid}")

        print(f"✅ Successfully generated {len(labs_dict)} lab guides")
        return labs_dict
    
    except Exception as e:
        print(f"❌ Error generating batch labs: {e}")
        preview = locals().get("response_text")
        print(f"Response preview: {preview[:1000] if preview else 'N/A'}...")
        raise


def cargar_informes_previos(bucket: str, key: str) -> Dict[str, Any]:
    """Recupera los informes por laboratorio ya escritos en ejecuciones previas.

    Cada invocación del Writer procesa un único laboratorio, así que el
    artefacto se construye por acumulación. Un objeto ausente o ilegible no
    debe impedir guardar el informe del lote actual: se degrada a ``{}``.
    """
    try:
        cuerpo = s3_client.get_object(Bucket=bucket, Key=key)['Body'].read()
        previo = json.loads(cuerpo.decode('utf-8'))
    except ClientError as e:
        codigo = e.response.get('Error', {}).get('Code', '')
        if codigo not in ('NoSuchKey', '404'):
            print(f"⚠️  No se pudo leer el informe referencial previo: {e}")
        return {}
    except Exception as e:
        print(f"⚠️  Informe referencial previo ilegible, se regenera: {e}")
        return {}

    por_laboratorio = previo.get('por_laboratorio')
    return por_laboratorio if isinstance(por_laboratorio, dict) else {}


def guardar_informe_referencial(bucket: str, project_folder: str, informes: Dict[str, Any]) -> str:
    """Escribe el informe B1 de integridad referencial de los laboratorios generados.

    Se guarda junto a las validaciones de contenido (``{project_folder}/validation/``),
    en la misma convención que ``content_validator.save_validation_report``.

    El Writer procesa un laboratorio por invocación (lotes de 1 con
    ``MaxConcurrency: 1``), así que el informe se **acumula** sobre el que ya
    existe: sin esta fusión cada lote sobrescribía el anterior y el artefacto
    sólo conservaba el último laboratorio.
    """
    if not informes:
        return ""
    try:
        key = f"{project_folder}/validation/labs-referential-integrity.json"
        informes = {**cargar_informes_previos(bucket, key), **informes}
        total = sum(len(r.get("violaciones", [])) for r in informes.values())
        b2 = sum(
            1
            for r in informes.values()
            for v in r.get("violaciones", [])
            if v.get("verificacion") == "B2"
        )
        b6 = sum(
            1
            for r in informes.values()
            for v in r.get("violaciones", [])
            if v.get("verificacion") == "B6"
        )
        b5 = sum(
            1
            for r in informes.values()
            for v in r.get("violaciones", [])
            if v.get("verificacion") == "B5"
        )
        b3p = sum(
            1
            for r in informes.values()
            for v in r.get("violaciones", [])
            if v.get("verificacion") == "B3p"
        )
        altas = sum(
            1
            for r in informes.values()
            for v in r.get("violaciones", [])
            if v.get("confianza") == "alta"
        )
        marcados = sum(len(r.get("marcados", [])) for r in informes.values())
        payload = {
            "check": "B1+B2+B3p+B5+B6",
            "labs": len(informes),
            "total_violaciones": total,
            "total_b1": total - b2 - b3p - b5 - b6,
            "total_b2": b2,
            "total_b3p": b3p,
            "total_b5": b5,
            "total_b6": b6,
            "total_alta_confianza": altas,
            # Referentes que la guía deja **a la vista** del instructor
            # («[POR CONFIRMAR]»): son el nivel 3 de la regla, no una violación.
            # Se cuentan aparte para que el instructor sepa qué ficheros debe aportar.
            "total_marcados_por_confirmar": marcados,
            "total_menciones_posteriores": sum(
                len(r.get("menciones_posteriores", [])) for r in informes.values()
            ),
            "ok": total == 0,
            "ok_alta_confianza": altas == 0,
            "por_laboratorio": informes,
        }
        necesitan = []
        avisos = []
        for lab_id, reporte in informes.items():
            bloquean, advertencias = partir_hallazgos(reporte.get("violaciones"))
            estado = reporte.get("quality_status")
            if estado is None:
                estado = "needs_review" if bloquean else "passed"
            if estado == "needs_review" or bloquean:
                necesitan.append({"lab_id": lab_id, "findings": bloquean})
            elif advertencias or reporte.get("quality_warnings"):
                avisos.append({
                    "lab_id": lab_id,
                    "findings": advertencias or reporte.get("quality_warnings") or [],
                })
        payload["quality_status"] = "needs_review" if necesitan else "passed"
        payload["labs_needing_review"] = necesitan
        payload["quality_warnings"] = avisos
        if necesitan:
            print(
                f"🚫 QUALITY GATE: referential report {key} needs_review "
                f"({len(necesitan)} lab(s) with high-confidence findings)"
            )
        elif avisos:
            print(
                f"⚠️  QUALITY GATE: referential report {key} passed with "
                f"low-confidence warnings on {len(avisos)} lab(s)"
            )
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, indent=2, ensure_ascii=False),
            ContentType='application/json',
        )
        print(f"📝 Informe B1/B2 de integridad referencial guardado: {key}")
        return key
    except Exception as e:
        print(f"⚠️  No se pudo guardar el informe B1/B2 de integridad referencial: {e}")
        return ""


def guardar_informe_moneda(bucket: str, project_folder: str, informes: Dict[str, Any]) -> str:
    """Write the C6 Copilot-currency report under ``validation/``.

    Same accumulation rule as the referential report: one lab per invocation.
    """
    if not informes:
        return ""
    try:
        key = f"{project_folder}/validation/copilot-currency.json"
        fusionados = {**cargar_informes_previos(bucket, key), **informes}
        payload = construir_informe_moneda(fusionados)
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, indent=2, ensure_ascii=False),
            ContentType="application/json",
        )
        print(f"📝 Informe C6 de moneda Copilot guardado: {key}")
        return key
    except Exception as e:
        print(f"⚠️  No se pudo guardar el informe C6 de moneda Copilot: {e}")
        return ""


def lambda_handler(event, context):
    """
    Lambda handler for Lab Writer (Agent 2).
    
    Input event:
    {
        "course_bucket": "crewai-course-artifacts",
        "master_plan_key": "project/labguide/lab-master-plan.json",
        "project_folder": "251014-kubernetes-course",
        "model_provider": "bedrock"
    }
    
    Output:
    {
        "statusCode": 200,
        "lab_guides_generated": 15,
        "lab_guide_keys": ["project/labguide/lab-01-01-01-setup.md", ...],
        "project_folder": "251014-kubernetes-course",
        "bucket": "crewai-course-artifacts"
    }
    """
    
    print("\n" + "="*70)
    print("📝 LAB WRITER - AGENT 2: STEP-BY-STEP INSTRUCTIONS")
    print("="*70)
    
    try:
        # Full state from RegenerateInvalidLabs carries invalid_lab_ids instead of
        # lab_ids. A shaped batch payload already has lab_ids and is left as-is.
        event = normalizar_evento_writer(event)
        # Extract parameters
        course_bucket = event.get('course_bucket', 'crewai-course-artifacts')
        master_plan_key = event['master_plan_key']
        project_folder = event['project_folder']
        model_provider = event.get('model_provider', 'bedrock')
        
        # Support bedrock, openai, and google/gemini providers
        original_provider = event.get('model_provider', 'bedrock').lower()
        if original_provider in ('google', 'gemini', 'openai'):
            model_provider = original_provider
        else:
            model_provider = 'bedrock'
        
        lab_ids_to_process = event.get('lab_ids', [])  # NEW: For batch processing
        
        print(f"📦 Bucket: {course_bucket}")
        print(f"📋 Master Plan: {master_plan_key}")
        print(f"📁 Project: {project_folder}")
        print(f"🤖 Model: {model_provider}")
        if lab_ids_to_process:
            print(f"🎯 Batch Mode: Processing specific labs: {', '.join(lab_ids_to_process)}")
        else:
            print(f"🎯 Full Mode: Processing all labs")
        
        # Step 1: Load master plan
        master_plan = load_master_plan_from_s3(course_bucket, master_plan_key)
        
        lab_plans = master_plan.get('lab_plans', [])
        if not lab_plans:
            print("⚠️  No lab plans found in master plan!")
            raise ValueError("No lab plans found in master plan")
        
        # NEW: Filter to only process specified labs if batch mode
        if lab_ids_to_process:
            original_count = len(lab_plans)
            lab_plans = [lab for lab in lab_plans if lab['lab_id'] in lab_ids_to_process]
            print(f"📊 Filtered {original_count} labs → {len(lab_plans)} labs for this batch")
        
        # Extract language from metadata
        course_language = master_plan.get('metadata', {}).get('course_language', 'es')
        language_names = {
            'en': 'English',
            'es': 'Spanish (Español)',
            'fr': 'French (Français)',
            'de': 'German (Deutsch)',
            'pt': 'Portuguese (Português)',
            'it': 'Italian (Italiano)'
        }
        target_language = language_names.get(course_language, 'Spanish (Español)')
        
        print(f"\n🌐 Target Language: {target_language} ({course_language})")
        print(f"📊 Total labs to generate: {len(lab_plans)}\n")
        
        manual_text_s3_key = event.get('manual_text_s3_key')
        manual_reference_text = ''
        if manual_text_s3_key:
            try:
                man_obj = s3_client.get_object(Bucket=course_bucket, Key=manual_text_s3_key)
                manual_reference_text = man_obj['Body'].read().decode('utf-8')
                print(f"📚 Loaded manual reference text in Lab Writer ({len(manual_reference_text):,} chars)")
            except Exception as man_err:
                print(f"⚠️ Could not load manual reference text in lab writer: {man_err}")

        # Contexto para la verificación B1 (integridad referencial): el temario es la
        # fuente primaria. Sin él, la comprobación no puede distinguir un fichero
        # declarado de uno inventado, y marcaría todo como violación.
        outline_reference_text = ''
        outline_s3_key = event.get('outline_s3_key')
        if outline_s3_key:
            try:
                out_obj = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
                outline_reference_text = out_obj['Body'].read().decode('utf-8')
                print(f"📄 Loaded syllabus in Lab Writer ({len(outline_reference_text):,} chars)")
            except Exception as out_err:
                print(f"⚠️ Could not load syllabus in lab writer: {out_err}")
        else:
            print("⚠️  outline_s3_key not received: referential check B1 will run without the syllabus")

        referential_sources = outline_reference_text + "\n" + manual_reference_text

        # El plan es fuente para B1… pero solo para sus referentes VERIFICADOS.
        # A1 ya dejó por escrito qué referentes del plan no existen en ninguna fuente;
        # si se usasen como fuente, el laboratorio podría repetir el dato inventado y
        # B1 lo daría por bueno. Se excluyen únicamente los de **alta confianza** (los
        # que el curso dice aportar): los de baja son entregables o directorios que el
        # propio plan introduce legítimamente y deben seguir contando como fuente.
        plan_metadata = master_plan.get("metadata") or {}
        plan_trazable = {k: v for k, v in master_plan.items() if k != "metadata"}
        plan_trazable["metadata"] = {
            k: v for k, v in plan_metadata.items() if k != "referential_integrity"
        }
        referential_plan_text = flatten_to_text(plan_trazable)
        violaciones_a1 = [
            v
            for v in ((plan_metadata.get("referential_integrity") or {}).get("violaciones") or [])
            if isinstance(v, dict) and v.get("confianza", "alta") == "alta"
        ]
        for violacion in violaciones_a1:
            valor = violacion.get("valor")
            if valor:
                referential_plan_text = referential_plan_text.replace(valor, " ")
        if violaciones_a1:
            print(
                f"🔗 Se excluyen {len(violaciones_a1)} referente(s) del plan marcados por A1 "
                f"como aportados por el curso y no declarados: no cuentan como fuente para B1"
            )

        referential_reports: Dict[str, Any] = {}
        labs_needing_review: Dict[str, List[dict]] = {}
        labs_quality_warnings: Dict[str, List[dict]] = {}
        currency_reports: Dict[str, Any] = {}

        # Full-plan order: B2 (a later lab's output) depends on position.
        # A file created in an earlier lab is not delivered. Each practice runs alone.
        orden_labs = [
            p.get("lab_id") for p in master_plan.get("lab_plans", []) if p.get("lab_id")
        ]
        salidas_por_lab = salidas_de_laboratorios(master_plan)

        # Build master context for all labs (including language)
        additional_requirements = (
            event.get('additional_requirements')
            or master_plan.get('additional_requirements')
            or master_plan.get('metadata', {}).get('additional_requirements')
            or ''
        )
        if additional_requirements:
            print(f"📋 User Additional Requirements: {additional_requirements[:100]}...")

        master_context = {
            'hardware_requirements': master_plan.get('hardware_requirements', []),
            'software_requirements': master_plan.get('software_requirements', []),
            'special_considerations': master_plan.get('special_considerations', []),
            'overall_objectives': master_plan.get('overall_objectives', []),
            'target_language': target_language,  # NEW: Pass language to prompt
            'manual_reference_text': manual_reference_text,
            'additional_requirements': additional_requirements,
            'audience_profile': (master_plan.get('metadata') or {}).get('audience_profile'),
            # Raw syllabus. The prompt prints only the locked anchors, not this text.
            'syllabus_text': outline_reference_text,
        }
        
        # Step 2: Generate lab guides ONE AT A TIME for reliability
        # both GPT-5 and Bedrock handle single-lab requests reliably
        # GPT-5 sometimes skips labs in multi-lab requests
        labs_markdown = {}
        models_used: Dict[str, str] = {}
        placeholders: List[dict] = []
        failed_lab_ids: List[str] = []
        
        # Maps lab_id to its lesson content key
        lab_lesson_keys = event.get('lab_lesson_keys', {})

        for idx, lab_plan in enumerate(lab_plans, start=1):
            lab_id = lab_plan['lab_id']
            print(f"\n📦 Lab {idx}/{len(lab_plans)}: Generating {lab_id}...")

            # La corrección de integridad referencial y la de evidencia medible son
            # específicas del laboratorio en curso: no deben arrastrarse al siguiente.
            master_context.pop("referential_correction", None)
            master_context.pop("validation_evidence_correction", None)
            master_context.pop("currency_correction", None)
            master_context.pop("reading_budget_correction", None)

            # En actualización selectiva el lab pedido SE regenera, aunque exista:
            # el skip-if-exists solo aplica a la generación normal.
            en_actualizacion = (
                bool(event.get("update_mode"))
                or bool(event.get("force_regenerate"))
            )
            if _lab_skip_if_exists_enabled() and not en_actualizacion:
                existing_key = _find_existing_lab_guide_key(
                    course_bucket, project_folder, lab_id
                )
                if existing_key:
                    try:
                        body = s3_client.get_object(
                            Bucket=course_bucket, Key=existing_key
                        )["Body"].read().decode("utf-8")
                        if body.strip() and MARCA_PLACEHOLDER not in body:
                            labs_markdown[lab_id] = body
                            print(
                                f"  ⏭️  Skipping generation; using existing s3://{course_bucket}/{existing_key}"
                            )
                            continue
                        if body.strip() and MARCA_PLACEHOLDER in body:
                            print(
                                f"  🔁 Existing lab {lab_id} is a placeholder; regenerating"
                            )
                    except Exception as e:
                        print(f"⚠️  Could not read existing lab {existing_key}, regenerating: {e}")

            # Load specific lesson content if available
            lesson_content = ""
            if lab_id in lab_lesson_keys:
                lesson_key = lab_lesson_keys[lab_id]
                lesson_content = load_lesson_content(course_bucket, lesson_key)

            # Position in the full plan (not in this batch): B2 depends on it.
            # The previous lab is not loaded; this practice does not reuse its files.
            posicion = orden_labs.index(lab_id) if lab_id in orden_labs else 0
            previous_lab_context = ""

            last_error: Optional[Exception] = None
            _modelo_que_respondio["id"] = None
            for attempt in range(1, MAX_LAB_GENERATION_ATTEMPTS + 1):
                try:
                    batch_results = generate_all_labs_batch(
                        lab_plans=[lab_plan],
                        master_context=master_context,
                        model_provider=model_provider,
                        lesson_content=lesson_content,
                        previous_lab_context=previous_lab_context
                    )
                    if lab_id in batch_results and (batch_results[lab_id] or "").strip():
                        raw_guide = batch_results[lab_id]
                        # Run automated verification & refinement pass
                        verified_guide = _verify_and_refine_lab_guide(
                            raw_guide,
                            lab_plan,
                            master_context,
                            model_provider=model_provider
                        )
                        is_demo = is_demo_plan(lab_plan)
                        verified_guide = _finalize_lab_markdown(
                            verified_guide,
                            is_demo=is_demo,
                            is_spanish=course_language.startswith('es')
                        )

                        hallazgos_evidencia = hallazgos_validacion_no_medible(verified_guide)
                        if hallazgos_evidencia:
                            print(
                                f"  🔎 Validación medible de {lab_id}: "
                                f"{len(hallazgos_evidencia)} hallazgo(s)"
                            )
                            for h in hallazgos_evidencia[:8]:
                                print(f"     ⚠️  {h}")
                        if (
                            hallazgos_evidencia
                            and attempt < MAX_LAB_GENERATION_ATTEMPTS
                            and _reintento_validacion_medible_habilitado()
                        ):
                            master_context["validation_evidence_correction"] = (
                                mensaje_correccion_validacion(hallazgos_evidencia)
                            )
                            raise RuntimeError(
                                f"Measurable validation failed for {lab_id}: "
                                f"{len(hallazgos_evidencia)} finding(s)"
                            )

                        # B1/B2: every file or path must be declared in the syllabus, the manual
                        # or the plan, or created in a step of THIS lab. An earlier lab
                        # does not supply inputs. A later lab's output is still B2.
                        posteriores = {
                            otro: salidas_por_lab.get(otro) or []
                            for otro in orden_labs[posicion + 1:]
                        }

                        def _auditar(guia: str) -> dict:
                            return auditar_laboratorio(
                                guia,
                                fuentes=referential_sources,
                                plan=referential_plan_text,
                                creados_antes=None,
                                salidas_posteriores=posteriores,
                                referencias_posteriores=referencias_a_labs_posteriores(
                                    guia, posicion, orden_labs
                                ),
                                # B6: la duración que declara el propio laboratorio manda;
                                # si no la declara, se usa la del plan (coinciden en 176 de
                                # los 179 laboratorios que la declaran).
                                duracion_min=(
                                    duracion_declarada(guia)
                                    or lab_plan.get("estimated_duration")
                                    or lab_plan.get("duration_minutes")
                                ),
                                requisitos_texto=requisitos_declarados(
                                    master_context.get("software_requirements"),
                                    master_context.get("hardware_requirements"),
                                ),
                                expected_outcomes=lab_plan.get("expected_outcomes"),
                                # C2: lo que la petición declara del entorno (SO, shells
                                # y mandatos prohibidos) se audita contra el laboratorio.
                                entorno=entorno_de_peticion(
                                    master_context.get("additional_requirements") or ""
                                ),
                                # A2e reads the syllabus only. The manual is not a list of
                                # scenario entities. An earlier lab still does not supply inputs.
                                temario=outline_reference_text,
                            )

                        def _altas(informe: dict) -> list:
                            return [
                                v
                                for v in informe["violaciones"]
                                if v.get("confianza") == "alta"
                                and (
                                    v.get("verificacion") != "B6"
                                    or _reintento_duracion_habilitado()
                                )
                                and (
                                    v.get("verificacion") != "B5"
                                    or _reintento_requisitos_habilitado()
                                )
                                and (
                                    v.get("verificacion") != "B3p"
                                    or _reintento_entregables_habilitado()
                                )
                                and (
                                    v.get("verificacion") != "C2"
                                    or _reintento_entorno_habilitado()
                                )
                            ]

                        referential_report = _auditar(verified_guide)
                        altas = _altas(referential_report)
                        # The model gets the remaining attempts to drop an invented
                        # name or use a file the syllabus already delivers. The guide
                        # that ships still has to run alone, so any Excel, Word, .eml,
                        # CSV or SharePoint input that is still missing is inlined.
                        va_a_reintentar = (
                            bool(altas)
                            and attempt < MAX_LAB_GENERATION_ATTEMPTS
                            and _reintento_referencial_habilitado()
                        )
                        if not va_a_reintentar:
                            guia_anexada = anexar_entradas_no_entregadas(
                                verified_guide,
                                referential_report,
                                is_spanish=course_language.startswith("es"),
                            )
                            if guia_anexada != verified_guide:
                                verified_guide = guia_anexada
                                referential_report = _auditar(verified_guide)
                                altas = _altas(referential_report)
                                print(f"  📎 Anexo de datos ficticios añadido a {lab_id}")
                        referential_reports[lab_id] = referential_report
                        print(
                            f"  🔎 Integridad referencial y duración de {lab_id}: "
                            f"{len(referential_report['violaciones'])} hallazgo(s) "
                            f"({len(altas)} de alta confianza)"
                        )
                        for v in referential_report["violaciones"][:10]:
                            print(f"     ⚠️  {v['valor']} [{v.get('verificacion', 'B1')}]")
                        if referential_report.get("menciones_posteriores"):
                            print(
                                f"     ℹ️  {len(referential_report['menciones_posteriores'])} "
                                f"mencion(es) de hoja de ruta a laboratorios posteriores"
                            )

                        if va_a_reintentar:
                            # Reintento correctivo solo con lo que el curso dice aportar.
                            # El resto (ficheros creados por el propio laboratorio, del
                            # proyecto o salidas esperadas) queda solo registrado: la
                            # calibración mostró que reintentar sobre ellos borra
                            # entregables legítimos.
                            master_context["referential_correction"] = mensaje_de_correccion(
                                altas, "lab"
                            )
                            raise RuntimeError(
                                f"B1/B2/B6 check failed for {lab_id}: "
                                f"{len(altas)} high-confidence finding(s)"
                            )

                        # Reading budget: body prose and the fictitious annex are
                        # counted apart. While attempts remain, ask for a shorter
                        # draft with the actual counts. The last attempt records a
                        # medium finding and still ships the lab.
                        medida_lectura = medir_lectura(
                            verified_guide,
                            duracion_declarada(verified_guide)
                            or lab_plan.get("estimated_duration")
                            or lab_plan.get("duration_minutes"),
                        )
                        if medida_lectura.get("excede"):
                            print(
                                f"  🔎 Lectura de {lab_id}: "
                                f"{medida_lectura.get('palabras')} palabras "
                                f"(presupuesto {medida_lectura.get('palabras_max')}), "
                                f"anexo {medida_lectura.get('palabras_anexo')} "
                                f"(tope {medida_lectura.get('anexo_max')})"
                            )
                        if (
                            medida_lectura.get("excede")
                            and attempt < MAX_LAB_GENERATION_ATTEMPTS
                            and _reintento_lectura_habilitado()
                        ):
                            master_context["reading_budget_correction"] = mensaje_acortar(
                                medida_lectura,
                                en_espanol=course_language.startswith("es"),
                            )
                            raise RuntimeError(
                                f"Reading budget exceeded for {lab_id}: "
                                f"{medida_lectura.get('palabras')} words "
                                f"(max {medida_lectura.get('palabras_max')}), "
                                f"annex {medida_lectura.get('palabras_anexo')} "
                                f"(max {medida_lectura.get('anexo_max')})"
                            )
                        hallazgo_r1 = hallazgo_lectura(medida_lectura)
                        if hallazgo_r1:
                            referential_report.setdefault("violaciones", []).append(hallazgo_r1)

                        # C6: a Copilot feature, agent, or button must be in the
                        # verified catalog (or the uploaded manual or the syllabus).
                        # Unknown and deprecated names retry while attempts remain.
                        # The last attempt saves the lab and records a warning.
                        # CURRENCY_RETRY=0 only records them and does not retry.
                        # A surface the syllabus names is authorized. Deprecated
                        # catalog names are still findings, and they do not block
                        # delivery.
                        currency_report = auditar_superficies_copilot(
                            verified_guide,
                            manual="\n".join(
                                parte for parte in (
                                    master_context.get("manual_reference_text") or "",
                                    outline_reference_text or "",
                                ) if parte
                            ),
                        )
                        currency_reports[lab_id] = currency_report
                        bloqueos_moneda = [
                            h for h in currency_report.get("hallazgos") or []
                            if h.get("bloquea")
                        ]
                        if bloqueos_moneda:
                            print(
                                f"  🔎 Moneda Copilot de {lab_id}: "
                                f"{len(bloqueos_moneda)} bloqueo(s) "
                                f"(catálogo {currency_report.get('catalog_version')})"
                            )
                            for hallazgo in bloqueos_moneda[:10]:
                                print(
                                    f"     ⚠️  {hallazgo.get('nombre')} "
                                    f"[{hallazgo.get('tipo')}]"
                                )
                        if bloqueos_moneda and _reintento_moneda_habilitado():
                            master_context["currency_correction"] = (
                                mensaje_de_correccion_moneda(bloqueos_moneda)
                            )
                            if attempt < MAX_LAB_GENERATION_ATTEMPTS:
                                raise RuntimeError(
                                    f"C6 currency check failed for {lab_id}: "
                                    f"{len(bloqueos_moneda)} unresolved or deprecated "
                                    f"Copilot surface(s)"
                                )
                            for hallazgo in bloqueos_moneda:
                                referential_report.setdefault("violaciones", []).append(
                                    {
                                        "verificacion": "C6",
                                        "confianza": "media",
                                        "valor": (
                                            f"{hallazgo.get('nombre')} "
                                            f"[{hallazgo.get('tipo')}]"
                                        ),
                                    }
                                )
                            print(
                                f"  ⚠️  C6 de {lab_id}: último intento, se guarda "
                                f"el borrador con advertencia."
                            )

                        # Final text: high-confidence findings that survived the last
                        # retry (or were never retried, such as B3p) fail the gate.
                        # Low-confidence findings stay warnings. The draft is still
                        # saved so a reviewer can see it; delivery is not a pass.
                        # Files created here are not passed to the next lab: each
                        # practice stays self-contained (creados_antes=None).
                        objetivo_ausente = hallazgo_objetivo_ausente(verified_guide, lab_plan)
                        if objetivo_ausente:
                            referential_report.setdefault("violaciones", []).append(objetivo_ausente)
                        bloquean, advertencias = partir_hallazgos(
                            referential_report.get("violaciones")
                        )
                        referential_report["quality_status"] = (
                            "needs_review" if bloquean else "passed"
                        )
                        referential_report["quality_warnings"] = advertencias
                        _registrar_puerta_de_lab(lab_id, attempt, bloquean, advertencias)
                        if bloquean:
                            labs_needing_review[lab_id] = bloquean
                        elif advertencias:
                            labs_quality_warnings[lab_id] = advertencias
                        labs_markdown[lab_id] = verified_guide
                        models_used[lab_id] = modelo_que_produjo_el_lab() or model_provider
                        print(f"  ✅ Lab {lab_id} generated & verified (Demo={is_demo}) (attempt {attempt}/{MAX_LAB_GENERATION_ATTEMPTS})")
                        break
                    last_error = ValueError(f"Model returned no content for {lab_id}")
                    print(f"  ⚠️ Empty content for {lab_id} on attempt {attempt}/{MAX_LAB_GENERATION_ATTEMPTS}")
                except Exception as e:
                    last_error = e
                    print(
                        f"  ❌ Lab {lab_id} attempt {attempt}/{MAX_LAB_GENERATION_ATTEMPTS} failed: {e}"
                    )
                if attempt < MAX_LAB_GENERATION_ATTEMPTS:
                    print("  🔁 Retrying...")
                    if last_error is not None and _bedrock_error_is_transient(last_error):
                        _sleep_before_bedrock_retry(attempt - 1)

            if lab_id not in labs_markdown:
                motivo = f"Lab {lab_id} failed after {MAX_LAB_GENERATION_ATTEMPTS} attempts"
                if last_error:
                    motivo += f": {last_error}"
                print(f"  ⚠️  {motivo}. Shipping a placeholder.")
                labs_markdown[lab_id] = markdown_de_laboratorio_pendiente(
                    lab_id, lab_plan.get("lab_title") or lab_id, motivo
                )
                placeholders.append({"lab_id": lab_id, "reason": motivo[:500]})
                failed_lab_ids.append(lab_id)
                labs_quality_warnings[lab_id] = [
                    {
                        "verificacion": "PLACEHOLDER",
                        "confianza": "media",
                        "valor": motivo[:300],
                    }
                ]
        
        # Step 3: Save each lab guide to S3
        lab_guide_keys = []
        print(f"\n💾 Saving {len(labs_markdown)} lab guides to S3...")
        
        for lab_plan in lab_plans:
            lab_id = lab_plan['lab_id']
            is_demo = is_demo_plan(lab_plan)
            lab_title = ensure_demo_title(lab_plan['lab_title']) if is_demo else lab_plan['lab_title']
            
            if lab_id not in labs_markdown:
                print(f"  ⚠️  Lab {lab_id} not found in generated content, skipping")
                continue
            
            lab_key = _guardar_guia_con_reintento(
                course_bucket, project_folder, lab_id, lab_title, labs_markdown[lab_id]
            )
            if lab_key:
                lab_guide_keys.append(lab_key)
                print(f"  ✅ Saved lab {lab_id}")
            else:
                print(f"  ❌ Failed to save lab {lab_id} after retries")
                if lab_id not in failed_lab_ids:
                    failed_lab_ids.append(lab_id)
                labs_quality_warnings.setdefault(lab_id, []).append(
                    {
                        "verificacion": "S3",
                        "confianza": "media",
                        "valor": f"no se pudo guardar {lab_id} tras reintentos",
                    }
                )

        if len(lab_guide_keys) != len(lab_plans):
            print(
                f"  ⚠️  Expected {len(lab_plans)} lab files, saved {len(lab_guide_keys)}. "
                f"The course continues; failed ids: {failed_lab_ids}"
            )

        guardar_informe_referencial(course_bucket, project_folder, referential_reports)
        guardar_informe_moneda(course_bucket, project_folder, currency_reports)

        revisiones = [
            {"lab_id": lab_id, "findings": hallazgos}
            for lab_id, hallazgos in labs_needing_review.items()
        ]
        avisos = [
            {"lab_id": lab_id, "findings": hallazgos}
            for lab_id, hallazgos in labs_quality_warnings.items()
        ]
        quality_status = "needs_review" if revisiones else "passed"
        if placeholders or failed_lab_ids:
            quality_summary = resumir_hallazgos(revisiones)
            if quality_summary == "passed":
                quality_summary = (
                    "WARNINGS placeholders="
                    + ",".join(item["lab_id"] for item in placeholders)
                )
        else:
            quality_summary = resumir_hallazgos(revisiones)

        print(f"\n{'='*70}")
        if revisiones:
            print(
                f"🚫 LAB WRITING NEEDS REVIEW: {len(revisiones)}/{len(lab_plans)} "
                f"lab(s) keep high-confidence findings after the final retry. "
                f"The course is still delivered. {quality_summary}"
            )
        else:
            print(f"✅ LAB WRITING COMPLETED")
            if avisos:
                print(
                    f"   ⚠️  {len(avisos)} lab(s) with non-blocking warnings only"
                )
        print(f"   Generated: {len(lab_guide_keys)}/{len(lab_plans)} labs")
        print(f"   quality_status: {quality_status}")
        print(f"{'='*70}\n")

        return {
            'statusCode': 200,
            'lab_guides_generated': len(lab_guide_keys),
            'lab_guide_keys': lab_guide_keys,
            'project_folder': project_folder,
            'bucket': course_bucket,
            'model_provider': model_provider,
            'quality_status': quality_status,
            'quality_summary': quality_summary,
            'labs_needing_review': revisiones,
            'quality_warnings': avisos,
            'placeholders': placeholders,
            'failed_lab_ids': failed_lab_ids,
            'models_used': models_used,
        }
    
    except KeyError as e:
        print(f"❌ Missing required parameter: {e}")
        raise ValueError(f"Missing required parameter: {e}") from e

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        recuperado = _entregar_placeholders_tras_fallo(event, e)
        if recuperado:
            return recuperado
        raise
