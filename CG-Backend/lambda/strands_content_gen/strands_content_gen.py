"""
Content Generation - OPTIMIZED FOR MODERN LLMs
===============================================
Generates ONE batch of lessons per invocation (max 5 lessons).
Step Functions handles parallelization with MaxConcurrency.

Modern LLMs (Sonnet 4.6, GPT-5) can easily handle 5+ lessons with rich content
and visual tags in a single API call, reducing cost and improving speed.

Expected event parameters:
    - module_number: int (which module to generate)
    - batch_start_idx: int (0-based index of first lesson in batch)
    - batch_end_idx: int (0-based index of last lesson + 1, Python slice style)
    - batch_index: int (1-based batch number for logging)
    - total_batches: int (total batches in this module, for logging)
    - course_bucket, outline_s3_key, project_folder: S3 paths
    - model_provider: 'bedrock' or 'openai'
"""

import os
import json
import random
import yaml
import boto3
import time
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure boto3 with extended timeouts for long-running LLM calls
boto_config = Config(
    read_timeout=600,  # 10 minutes read timeout
    connect_timeout=60,  # 1 minute connection timeout
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

# AWS Clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=boto_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration
DEFAULT_BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-6")
DEFAULT_OPENAI_MODEL = "gpt-5"
DEFAULT_REGION = "us-east-1"

# Application-level Bedrock retries (after boto retries) for transient errors
BEDROCK_APP_MAX_ATTEMPTS = max(1, int(os.getenv("BEDROCK_APP_MAX_ATTEMPTS", "5")))


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
    """Exponential backoff with jitter before retrying Bedrock (attempt_index 0-based)."""
    delay = min(cap, base * (2**attempt_index))
    jitter = random.uniform(0, min(8.0, delay * 0.25))
    total = delay + jitter
    print(f"⏳ Bedrock backoff: sleep {total:.1f}s before next attempt")
    time.sleep(total)


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        raise


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


def call_gemini(prompt: str, api_key: str, model_id: str = "gemini-3.5-flash") -> str:
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        raise


def count_existing_visuals(course_bucket: str, project_folder: str) -> int:
    """Count existing visual prompt files to determine global starting number."""
    try:
        prompts_prefix = f"{project_folder}/prompts/"
        response = s3_client.list_objects_v2(
            Bucket=course_bucket,
            Prefix=prompts_prefix
        )
        
        if 'Contents' not in response:
            return 0
        
        json_files = [obj for obj in response['Contents'] if obj['Key'].endswith('.json')]
        count = len(json_files)
        print(f"📊 Found {count} existing visual prompts in S3")
        return count
    except Exception as e:
        print(f"⚠️  Error counting visuals (assuming 0): {e}")
        return 0


def format_lesson_filename(module_num: int, lesson_index: int, lesson_title: str) -> str:
    """Format lesson filename."""
    safe_title = lesson_title.lower()
    safe_title = ''.join(c if c.isalnum() or c.isspace() else '' for c in safe_title)
    safe_title = '-'.join(safe_title.split())
    return f"module-{module_num}-lesson-{lesson_index + 1}-{safe_title}.md"
def calculate_target_words(lesson_data: dict, module_info: dict) -> int:
    """Calculate target word count for a lesson."""
    lesson_duration = lesson_data.get('duration_minutes', module_info.get('duration_minutes', 45))
    lesson_bloom = lesson_data.get('bloom_level', module_info.get('bloom_level', 'Understand'))
    
    # Handle compound bloom levels
    if '/' in lesson_bloom:
        bloom_parts = [b.strip() for b in lesson_bloom.split('/')]
        bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
        lesson_bloom = max(bloom_parts, key=lambda x: bloom_order.index(x) if x in bloom_order else 0)
    
    # Bloom multipliers
    bloom_multipliers = {
        'Remember': 1.0,
        'Understand': 1.1,
        'Apply': 1.2,
        'Analyze': 1.3,
        'Evaluate': 1.4,
        'Create': 1.5
    }
    
    bloom_mult = bloom_multipliers.get(lesson_bloom, 1.1)
    
    # Base calculation: 45 words per minute for deep, academic content (approx 200-250 words per 5 min topic)
    base_words = lesson_duration * 45
    base_words = int(base_words * bloom_mult)
    
    # Add for topics and labs
    topics_count = len(lesson_data.get('topics', []))
    labs_count = len(lesson_data.get('lab_activities', []))
    
    total_words = base_words + (topics_count * 80) + (labs_count * 120)
    
    # Bounds
    return max(1000, min(5000, total_words))


def is_spanish_course(course_data: dict) -> bool:
    """Spanish by default; English only when outline explicitly sets English."""
    language = str(course_data.get('language', '')).strip().lower()
    if not language:
        return True
    if language.startswith('en') or 'english' in language or 'inglés' in language or 'ingles' in language:
        return False
    return True


def is_lab_lesson(lesson: dict) -> bool:
    """Detect if a lesson is a lab / hands-on activity lesson."""
    if not isinstance(lesson, dict):
        return False
    lesson_type = str(lesson.get('type', '')).strip().lower()
    lesson_title = str(lesson.get('title', '')).strip()
    lesson_title_lower = lesson_title.lower()

    if lesson_type in ['lab', 'practice', 'activity', 'lab_activity', 'laboratorio', 'práctica', 'practica']:
        return True

    prefixes = ['laboratorio', 'lab:', 'lab ', 'práctica', 'practica', 'actividad práctica', 'actividad practica']
    for p in prefixes:
        if lesson_title_lower.startswith(p):
            return True

    if 'laboratorio:' in lesson_title_lower or 'laboratorio -' in lesson_title_lower:
        return True

    return False


def extract_outline_language(outline_data: dict) -> str:
    """
    Read course language from common outline shapes (course.language, root language, metadata).
    Returns raw string or '' if absent (caller uses Spanish-by-default policy).
    """
    if not outline_data or not isinstance(outline_data, dict):
        return ''
    for block in (outline_data.get('course'), outline_data.get('course_metadata')):
        if isinstance(block, dict):
            for key in ('language', 'lang', 'locale'):
                val = block.get(key)
                if val is not None and str(val).strip():
                    return str(val).strip()
    for key in ('language', 'lang', 'locale'):
        val = outline_data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ''


def build_course_context(course_data: dict, spanish_course: bool = False) -> str:
    """Build complete course outline context (Spanish or English headers to match output language)."""
    course_title = course_data.get('title', 'Course')
    modules = course_data.get('modules', [])
    if spanish_course:
        context_lines = [
            "════════════════════════════════════════════════════════════════════════",
            "TEMARIO COMPLETO DEL CURSO — RESPETA EXACTAMENTE ESTA ESTRUCTURA",
            "════════════════════════════════════════════════════════════════════════",
            f"Curso: {course_title}",
            f"Total de capítulos: {len(modules)}",
            "",
        ]
        module_term = "CAPÍTULO"
        lesson_term = "Lección"
    else:
        context_lines = [
            "════════════════════════════════════════════════════════════════════════",
            "COMPLETE COURSE OUTLINE - MUST REFERENCE THIS EXACT STRUCTURE",
            "════════════════════════════════════════════════════════════════════════",
            f"Course: {course_title}",
            f"Total Modules: {len(modules)}",
            "",
        ]
        module_term = "MODULE"
        lesson_term = "Lesson"

    for i, module in enumerate(modules, 1):
        context_lines.append(f"{module_term} {i}: {module.get('title', 'Untitled')}")
        lessons = module.get('lessons', [])
        for j, lesson in enumerate(lessons, 1):
            context_lines.append(f"  {lesson_term} {i}.{j}: {lesson.get('title', 'Untitled')}")

    context_lines.append("════════════════════════════════════════════════════════════════════════")

    return "\n".join(context_lines)


def generate_batch_single_call(
    module_number: int,
    batch_start_idx: int,
    batch_end_idx: int,
    module_data: dict,
    course_data: dict,
    model_provider: str = 'bedrock',
    openai_api_key: Optional[str] = None,
    starting_visual_number: int = 1,
    lesson_requirements: str = '',
    manual_reference_text: str = ''
) -> List[Dict[str, Any]]:
    """
    Generate a single batch of lessons (3 lessons max) in ONE LLM call.
    
    Returns:
        List of lesson dictionaries with content, metadata, etc.
    """
    
    module_title = module_data.get('title', 'Module')
    module_description = module_data.get('description', '')
    module_duration = module_data.get('duration_minutes', 45)
    module_bloom = module_data.get('bloom_level', 'Understand')
    lessons = module_data.get('lessons', [])
    
    # Extract the batch of lessons
    batch_lessons = lessons[batch_start_idx:batch_end_idx]
    num_lessons = len(batch_lessons)
    
    print(f"\n📚 Module {module_number}: {module_title}")
    print(f"📝 Generating batch: Lessons {batch_start_idx + 1}-{batch_end_idx} ({num_lessons} lessons)")
    
    # Build course context
    spanish_course = is_spanish_course(course_data)
    print(f"🌐 spanish_course={spanish_course} (outline language field={course_data.get('language', '')!r})")
    module_term = "Capítulo" if spanish_course else "Module"
    lesson_term = "Lección" if spanish_course else "Lesson"
    course_context = build_course_context(
        {
            'title': course_data.get('title', 'Course'),
            'modules': course_data.get('modules', []),
            'language': course_data.get('language', '')
        },
        spanish_course=spanish_course
    )

    dur_label = "Duración" if spanish_course else "Duration"
    min_label = "minutos" if spanish_course else "minutes"
    bloom_label = "Nivel Bloom" if spanish_course else "Bloom Level"
    target_label = "Extensión objetivo" if spanish_course else "Target Length"
    words_label = "palabras" if spanish_course else "words"
    topics_header = "Temas" if spanish_course else "Topics"
    labs_header = "Actividades de laboratorio" if spanish_course else "Lab Activities"
    none_placeholder = "      (No especificados)" if spanish_course else "      (None specified)"

    # Build lesson specifications
    lesson_specs = []
    for i, lesson in enumerate(batch_lessons, start=batch_start_idx):
        target_words = calculate_target_words(lesson, module_data)

        topics_list = lesson.get('topics', [])
        topics_formatted = []
        for t in topics_list:
            if isinstance(t, dict):
                t_title = t.get('title', 'Untitled')
                t_dur = t.get('duration_minutes', 0)
                topics_formatted.append(f"      - {t_title} ({dur_label}: {t_dur} {min_label})")
            else:
                topics_formatted.append(f"      - {str(t)}")
        topics_str = "\n".join(topics_formatted)

        lab_activities = lesson.get('lab_activities', [])
        labs_formatted = []
        for l in lab_activities:
            if isinstance(l, dict):
                l_title = l.get('title', 'Untitled')
                l_dur = l.get('duration_minutes', 0)
                labs_formatted.append(f"      - {l_title} ({dur_label}: {l_dur} {min_label})")
            else:
                labs_formatted.append(f"      - {str(l)}")
        labs_str = "\n".join(labs_formatted)

        l_is_lab = is_lab_lesson(lesson)
        if l_is_lab:
            l_title = lesson.get('title', 'Untitled')
            spec = f"""
    {lesson_term} {i + 1}: {l_title} (TIPO: LABORATORIO / ACTIVIDAD PRÁCTICA)
    {dur_label}: {lesson.get('duration_minutes', module_duration)} {min_label}
    *** INSTRUCCIÓN CRÍTICA DE NO DUPLICIDAD DE LABORATORIO ***
    Esta lección representa una actividad de laboratorio. La guía práctica detallada, código y comandos se generan en su GUÍA DE LABORATORIO DEDICADA.
    En el Libro de Teoría, esta lección debe ser ÚNICAMENTE UNA LECCIÓN DE REFERENCIA corta (~300-500 palabras) con la siguiente estructura exactas:
    1. # {module_number}.{i + 1}: {l_title}
    2. ## Objetivos de Aprendizaje
    3. ## Referencia a la Guía de Laboratorio (un bloque destacado indicando que los pasos guiados, comandos y solución de esta práctica se encuentran en la Guía de Laboratorio dedicada del Capítulo {module_number})
    4. ## Resumen de la Actividad Práctica (Contexto, requisitos previos y duración estimada)
    5. ## Referencias Bibliográficas (enlaces https válidos)
"""
        else:
            spec = f"""
    {lesson_term} {i + 1}: {lesson.get('title', 'Untitled')}
    {dur_label}: {lesson.get('duration_minutes', module_duration)} {min_label}
    {bloom_label}: {lesson.get('bloom_level', module_bloom)}
    {target_label}: ~{target_words} {words_label}
    {topics_header}:
{topics_str if topics_str else none_placeholder}
    {labs_header}:
{labs_str if labs_str else none_placeholder}
"""
        lesson_specs.append(spec)

    lessons_specification = "\n".join(lesson_specs)

    if lesson_requirements and lesson_requirements.strip():
        if spanish_course:
            additional_requirements_section = f"""
REQUISITOS ADICIONALES (INDICADOS POR EL USUARIO):
{lesson_requirements}
Intégralos en las lecciones sin contradecir el temario oficial.
"""
        else:
            additional_requirements_section = f"""
ADDITIONAL REQUIREMENTS (USER-SPECIFIED):
{lesson_requirements}
Please incorporate these additional requirements into the lesson content.
"""
    else:
        additional_requirements_section = ""

    role_line = (
        "Eres un educador técnico experto que redacta lecciones profesionales en ESPAÑOL para hispanohablantes."
        if spanish_course
        else "You are an expert technical educator creating lesson content for a professional course in ENGLISH."
    )

    language_directive = (
        """═══════════════════════════════════════════════════════════════════════════════
IDIOMA DE SALIDA (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════════════
- El curso está en **ESPAÑOL**. Todo el texto pedagógico (párrafos, listas, explicaciones, títulos H1–H3, tablas salvo identificadores técnicos) debe estar en **español** profesional.
- No escribas secciones narrativas completas en inglés. No mezcles idiomas en el cuerpo de la lección.
- Los bloques de código, comandos CLI, rutas y nombres de API pueden seguir la convención habitual (a menudo en inglés); el comentario y la explicación alrededor deben estar en español.
- Las descripciones dentro de las etiquetas [VISUAL: …] deben estar en **español**.
"""
        if spanish_course
        else """═══════════════════════════════════════════════════════════════════════════════
OUTPUT LANGUAGE (MANDATORY)
═══════════════════════════════════════════════════════════════════════════════
- The course is in **ENGLISH**. Write all pedagogical prose and headings in English.
- Code blocks and CLI may follow industry conventions.
"""
    )

    task_line = (
        f"TAREA: Genera el contenido completo y detallado de {num_lessons} lección(es) del {module_term} {module_number}."
        if spanish_course
        else f"TASK: Generate complete, detailed lesson content for {num_lessons} lesson(s) in {module_term} {module_number}."
    )
    module_header = (
        f"{module_term.upper()} {module_number}: {module_title}\nDescripción: {module_description}"
        if spanish_course
        else f"{module_term.upper()} {module_number}: {module_title}\nDescription: {module_description}"
    )
    lessons_header = "LECCIONES A GENERAR:" if spanish_course else "LESSONS TO GENERATE:"
    structure_title = (
        "ESQUEMA OBLIGATORIO DE CADA LECCIÓN (SIGUE AL PIE DE LA LETRA)"
        if spanish_course
        else "MANDATORY LESSON STRUCTURE SCHEMA (FOLLOW EXACTLY)"
    )

    schema_spanish = (
        "```\n"
        f"# {module_number}.N: [Título de la lección en español]\n\n"
        "## Objetivos de Aprendizaje\n\n"
        "Al finalizar esta lección, serás capaz de:\n\n"
        "- [Verbo Bloom] + [resultado medible 1]\n"
        "- [Verbo Bloom] + [resultado medible 2]\n"
        "- [Verbo Bloom] + [resultado medible 3]\n\n"
        "## Introducción\n\n"
        "[2–3 párrafos en español sobre el tema, importancia y qué se verá]\n\n"
        "## [Título del tema 1 según el YAML]\n\n"
        "### Visión General del Concepto\n\n"
        "[Explicación en español]\n\n"
        "### Detalles Técnicos\n\n"
        "[Profundización en español]\n\n"
        "### Aplicación Práctica\n\n"
        "[Ejemplo en español; código si aplica]\n\n"
        "[VISUAL: MM-LL-XXXX - descripción del diagrama en español]\n\n"
        "## [Más temas del YAML con el mismo patrón H2 + tres H3]\n\n"
        "## Resumen\n\n"
        "### Puntos Clave\n\n"
        "- [Punto 1 en español]\n"
        "- [Punto 2 en español]\n\n"
        "### Próximos Pasos\n\n"
        "[Texto en español]\n\n"
        "## Referencias Bibliográficas\n\n"
        "- [Descripción en español](https://url-real)\n"
        "```"
    )

    schema_english = (
        "```\n"
        f"# {module_number}.N: [Lesson title in English]\n\n"
        "## Learning Objectives\n\n"
        "By the end of this lesson, you will be able to:\n\n"
        "- [Bloom verb] + [measurable outcome 1]\n"
        "- [Bloom verb] + [measurable outcome 2]\n\n"
        "## Introduction\n\n"
        "[2–3 paragraphs in English]\n\n"
        "## [Topic title from YAML]\n\n"
        "### Concept Overview\n\n"
        "### Technical Details\n\n"
        "### Practical Application\n\n"
        "[VISUAL: MM-LL-XXXX - description in English]\n\n"
        "## Summary\n\n"
        "### Key Takeaways\n\n"
        "### Next Steps\n\n"
        "## Bibliographic References\n\n"
        "- [Description](https://real-url)\n"
        "```"
    )
    schema_block = schema_spanish if spanish_course else schema_english

    yaml_fidelity = (
        """═══════════════════════════════════════════════════════════════════════════════
FIDELIDAD A LOS TEMAS DEL YAML (CRÍTICO)
═══════════════════════════════════════════════════════════════════════════════
- Para cada lección, la sección de temas proviene del outline oficial.
- Debes cubrir **todos** los temas listados: un **H2 por tema** (después de Introducción) con título alineado al YAML.
- No omitas ni sustituyas temas; respeta el orden del outline.
"""
        if spanish_course
        else """═══════════════════════════════════════════════════════════════════════════════
YAML TOPIC FIDELITY (CRITICAL — THOR)
═══════════════════════════════════════════════════════════════════════════════
- For EACH lesson in this batch, the LESSONS TO GENERATE section lists **Topics** copied from the official YAML outline.
- You MUST cover **every** listed topic. Create **one H2 section per topic** (after Introduction) whose title matches or closely matches that topic's title from the YAML.
- Do not skip, rename arbitrarily, or substitute unrelated topics. Order topic sections in the same order as listed in the YAML for that lesson.
"""
    )

    visual_section = (
        """═══════════════════════════════════════════════════════════════════════════════
ENRIQUECIMIENTO VISUAL (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════════════
- No entregues solo texto continuo: incluye diagramas y visuales conceptuales.
- En cada sección de tema, incluye al menos una etiqueta [VISUAL: MM-LL-XXXX - …] en español.
"""
        if spanish_course
        else """═══════════════════════════════════════════════════════════════════════════════
VISUAL ENRICHMENT (MANDATORY — THOR)
═══════════════════════════════════════════════════════════════════════════════
- The material must NOT be plain walls of text: include conceptual diagrams and explanatory visuals.
- For EACH topic section, include at least one [VISUAL: MM-LL-XXXX - ...] tag describing a diagram, architecture figure, flowchart, or illustration that supports learning.
- Prefer diagrams and structured visuals where concepts allow.
"""
    )

    refs_section = (
        """═══════════════════════════════════════════════════════════════════════════════
REFERENCIAS BIBLIOGRÁFICAS — CALIDAD DE ENLACES
═══════════════════════════════════════════════════════════════════════════════
- Cada enlace externo debe ser **https://** y real (sin example.com).
- Un enlace markdown por viñeta: `- [Descripción](https://…)` en una sola línea.
"""
        if spanish_course
        else """═══════════════════════════════════════════════════════════════════════════════
REFERENCIAS BIBLIOGRÁFICAS — LINK QUALITY (THOR)
═══════════════════════════════════════════════════════════════════════════════
- Under "Bibliographic References", every external link MUST use **https://** with a real, reachable destination (no example.com placeholders).
- Format **each** resource as **one markdown link per bullet**, on a single line: `- [Clear description](https://domain/path)` (do NOT put bare URLs on a separate line under the title).
- Prefer official documentation, vendor docs, or primary sources; avoid aggregator pages when a primary URL exists.
"""
    )

    heading_rules = (
        """**JERARQUÍA DE ENCABEZADOS (OBLIGATORIO):**
- H1 (#): solo el título de la lección (uno por lección). Formato numérico `{module_number}.N: [Título]` sin prefijo "Lección".
- H2 (##): secciones principales en español.
- H3 (###): subsecciones.
- No saltes niveles (H1 → H3 inválido).

**SECCIONES OBLIGATORIAS:**
1. Objetivos de Aprendizaje (H2)
2. Introducción (H2)
3. Un H2 por cada tema del YAML con tres H3 (Visión General, Detalles Técnicos, Aplicación Práctica)
4. Resumen (H2) con Puntos Clave y Próximos Pasos (H3)
5. Referencias Bibliográficas (H2) con enlaces https válidos.

**NO incluyas sección de preguntas de repaso** (se genera aparte).
"""
        if spanish_course
        else """**HEADING HIERARCHY (MANDATORY):**
- H1 (#): ONLY for lesson title - ONE per lesson
- H2 (##): Major sections (Learning Objectives, Introduction, Topics, Summary, etc.)
- H3 (###): Subsections within H2 (Concept Overview, Technical Details, etc.)
- H4 (####): Details within H3 (if needed)
- NEVER skip heading levels (H1 → H3 is INVALID, must be H1 → H2 → H3)
- In H1 titles, use numeric format only: "{module_number}.N: [Title]" (do NOT prefix with "Lesson" or "Lección").

**REQUIRED SECTIONS (MUST INCLUDE - USE COURSE LANGUAGE FOR TITLES):**
1. Learning Objectives (H2) - 3-5 bullet points with Bloom verbs
2. Introduction (H2) - 2-3 paragraphs
3. At least ONE topic section (H2) with subsections (H3); one H2 per topic listed for that lesson in the outline.
4. Summary (H2) with Key Takeaways (H3)
5. Bibliographic References (H2) — required; use valid https links only.

**DO NOT INCLUDE Review Questions section - this will be handled separately.**
"""
    )

    bloom_block = (
        """**VERBOS DE LA TAXONOMÍA DE BLOOM (según nivel de la lección):**
- Recordar: Definir, Enumerar, Identificar, Nombrar
- Comprender: Describir, Explicar, Resumir, Interpretar
- Aplicar: Implementar, Ejecutar, Usar, Demostrar, Resolver
- Analizar: Comparar, Diferenciar, Examinar, Investigar
- Evaluar: Evaluar, Criticar, Juzgar, Justificar, Recomendar
- Crear: Diseñar, Desarrollar, Construir, Producir, Componer
"""
        if spanish_course
        else """**BLOOM'S TAXONOMY VERBS (USE BASED ON LESSON LEVEL):**
- Remember: Define, List, Identify, Name, Recall
- Understand: Describe, Explain, Summarize, Interpret
- Apply: Implement, Execute, Use, Demonstrate, Solve
- Analyze: Compare, Differentiate, Examine, Investigate
- Evaluate: Assess, Critique, Judge, Justify, Recommend
- Create: Design, Develop, Construct, Produce, Compose
"""
    )

    tables_code = (
        """**TABLAS (Markdown nativo):** no uses etiquetas VISUAL para tablas; formato estándar de tabla.

**BLOQUES DE CÓDIGO:** siempre con idioma (```python, ```bash, etc.). No uses VISUAL para código.

**ETIQUETAS VISUAL:**
- Formato: [VISUAL: MM-LL-XXXX - descripción en español]
- MM = módulo en 2 dígitos: {module_number:02d}
- LL = lección en 2 dígitos
- XXXX = contador global empezando en {starting_visual_number:04d}
"""
        if spanish_course
        else """**TABLES (USE NATIVE MARKDOWN):**
- DO NOT create visual tags for tables
- Use proper Markdown table formatting:
  | Column 1 | Column 2 | Column 3 |
  |----------|----------|----------|
  | Data 1   | Data 2   | Data 3   |

**CODE BLOCKS (ALWAYS SPECIFY LANGUAGE):**
- DO NOT create VISUAL tags for code, commands, or config files
- Use proper markdown code blocks:
  ```python
  def example():
      return "Hello"
  ```
  ```bash
  kubectl apply -f config.yaml
  ```
- Supported: python, javascript, java, bash, yaml, json, xml, terraform, etc.

**VISUAL TAGS (FOR DIAGRAMS/IMAGES ONLY):**
- Format: [VISUAL: MM-LL-XXXX - description]
- MM = Module number (2 digits): {module_number:02d}
- LL = Lesson number (2 digits, zero-padded)
- XXXX = Global counter starting at {starting_visual_number:04d}
- Description: 10-20 words describing the visual
- Examples:
  [VISUAL: {module_number:02d}-01-{starting_visual_number:04d} - Architecture diagram showing client-server communication flow]
  [VISUAL: {module_number:02d}-02-{(starting_visual_number+1):04d} - Flowchart of the authentication process]
"""
    )

    depth_pedagogy = (
        """**PROFUNDIDAD ACADÉMICA:** curso para profesionales; cada tema: Visión General → Detalles → Aplicación Práctica.

**CLARIDAD:** lenguaje sencillo, ejemplos concretos, analogías si ayudan, párrafos breves.
"""
        if spanish_course
        else """**ACADEMIC DEPTH:**
- This is an ACADEMIC COURSE for professionals
- Each topic MUST follow the structure: Concept Overview → Technical Details → Practical Application
- Match content depth to the Bloom level specified
- Target word count for each lesson as specified

**PEDAGOGICAL CLARITY (MANDATORY):**
- Write in simple, easy-to-understand language.
- Include concrete examples in each major topic.
- Include analogies when explaining abstract concepts.
- Prefer short paragraphs and clear transitions.
"""
    )

    output_tail = (
        """═══════════════════════════════════════════════════════════════════════════════
FORMATO DE SALIDA
═══════════════════════════════════════════════════════════════════════════════
Genera las lecciones separadas por este delimitador exacto:
═══════════════════════════════════════════════════════════════════════

Comienza a generar ahora:
"""
        if spanish_course
        else """═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Generate the lessons separated by this exact delimiter:
═══════════════════════════════════════════════════════════════════════

Begin generating now:
"""
    )

    terminology_note = (
        """
**TERMINOLOGÍA EN ESPAÑOL (OBLIGATORIO):** usa siempre "Capítulo" (nunca "Module"/"Módulo") y "Lección" (nunca "Lesson") en el texto generado.
"""
        if spanish_course
        else ""
    )

    structure_intro = (
        "Cada lección debe seguir esta estructura de encabezados."
        if spanish_course
        else "Each lesson MUST follow this exact heading hierarchy."
    )

    manual_alignment_directive = (
        f"""═══════════════════════════════════════════════════════════════════════════════
REGLA MANDATORIA DE ALINEACIÓN 100% AL MANUAL DE REFERENCIA
═══════════════════════════════════════════════════════════════════════════════
CRÍTICO: El contenido de todas las lecciones DEBE estar 100% estrictamente alineado con el manual de referencia proporcionado a continuación.
- Utiliza ÚNICAMENTE la terminología, conceptos, comandos, explicaciones y ejemplos del manual de referencia.
- NO agregues tecnologías, comandos ni procedimientos externos que no estén respaldados por el manual de referencia.
- Si hay discrepancias con el conocimiento general de la IA, el MANUAL DE REFERENCIA TIENE PRIORIDAD ABSOLUTA.

=== CONTENIDO DEL MANUAL DE REFERENCIA ===
{manual_reference_text[:14000]}
=== FIN DEL MANUAL DE REFERENCIA ===
"""
        if manual_reference_text and manual_reference_text.strip()
        else ""
    )

    prompt = f"""{role_line}

{language_directive}

{manual_alignment_directive}

{course_context}

{task_line}

{module_header}

{lessons_header}
{lessons_specification}
{additional_requirements_section}

═══════════════════════════════════════════════════════════════════════════════
{structure_title}
═══════════════════════════════════════════════════════════════════════════════

{structure_intro}
{terminology_note}

{schema_block}

{yaml_fidelity}

{visual_section}

{refs_section}

═══════════════════════════════════════════════════════════════════════════════
{"REGLAS DE FORMATO CRÍTICAS" if spanish_course else "CRITICAL FORMATTING RULES"}
═══════════════════════════════════════════════════════════════════════════════

{heading_rules}

{bloom_block}

{tables_code}

{depth_pedagogy}

{output_tail}
"""
    
    print(f"🤖 Calling {model_provider.upper()} API...")
    start_time = time.time()
    
    try:
        if model_provider == 'bedrock':
            response_text = call_bedrock(prompt)
        elif model_provider == 'openai':
            if not openai_api_key:
                raise ValueError("OpenAI API key required for openai provider")
            response_text = call_openai(prompt, openai_api_key)
        elif model_provider in ('google', 'gemini'):
            google_api_key = get_google_api_key()
            if not google_api_key:
                raise ValueError("Google API key required for google/gemini provider")
            response_text = call_gemini(prompt, google_api_key)
        else:
            raise ValueError(f"Unknown model provider: {model_provider}")
        
        elapsed = time.time() - start_time
        print(f"✅ API call completed in {elapsed:.1f}s")
        print(f"📄 Response length: {len(response_text):,} characters")
        
        # Parse the response into individual lessons
        parsed_lessons = parse_lessons_from_response(
            response_text=response_text,
            module_number=module_number,
            batch_lessons=batch_lessons,
            batch_start_idx=batch_start_idx,
            module_data=module_data
        )
        
        if len(parsed_lessons) != num_lessons:
            print(f"⚠️  Warning: Expected {num_lessons} lessons, got {len(parsed_lessons)}")
        
        return parsed_lessons
    
    except Exception as e:
        print(f"❌ Error generating batch: {str(e)}")
        raise


def call_bedrock(prompt: str, model_id: str = DEFAULT_BEDROCK_MODEL) -> str:
    """Call AWS Bedrock Claude API with app-level backoff on transient errors."""
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 32000,
        "temperature": 0.7,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    last_err: Optional[Exception] = None
    for attempt in range(1, BEDROCK_APP_MAX_ATTEMPTS + 1):
        try:
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            response_body = json.loads(response['body'].read())
            if 'content' in response_body and len(response_body['content']) > 0:
                return response_body['content'][0]['text']
            raise ValueError("No content in Bedrock response")
        except Exception as e:
            last_err = e
            print(f"Bedrock API Error (attempt {attempt}/{BEDROCK_APP_MAX_ATTEMPTS}): {str(e)}")
            if attempt < BEDROCK_APP_MAX_ATTEMPTS and _bedrock_error_is_transient(e):
                _sleep_before_bedrock_retry(attempt - 1)
                continue
            raise
    assert last_err is not None
    raise last_err


def call_openai(prompt: str, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> str:
    """Call OpenAI API using openai>=1.0.0 syntax with GPT-5 compatibility."""
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        # GPT-5 (o1 models) use max_completion_tokens and don't support temperature or system messages
        if model.startswith("o1-") or model == "gpt-5":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=32000
            )
        else:
            # GPT-4 and earlier models
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert technical educator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=32000,
                temperature=0.7
            )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        raise


def parse_lessons_from_response(
    response_text: str,
    module_number: int,
    batch_lessons: List[dict],
    batch_start_idx: int,
    module_data: dict
) -> List[Dict[str, Any]]:
    """Parse LLM response into individual lesson objects."""
    
    # Split by delimiter
    delimiter = "═" * 71
    parts = response_text.split(delimiter)
    
    # Filter out empty parts
    lesson_contents = [part.strip() for part in parts if part.strip()]
    
    print(f"📝 Parsed {len(lesson_contents)} lesson(s) from response")
    
    parsed_lessons = []
    
    for i, content in enumerate(lesson_contents):
        if i >= len(batch_lessons):
            print(f"⚠️  Warning: More lessons in response than expected, truncating")
            break
        
        lesson_data = batch_lessons[i]
        lesson_index = batch_start_idx + i
        lesson_title = lesson_data.get('title', f'Lesson {lesson_index + 1}')
        
        # Calculate word count
        word_count = len(content.split())
        
        # Format filename
        filename = format_lesson_filename(module_number, lesson_index, lesson_title)
        
        parsed_lesson = {
            'module_number': module_number,
            'lesson_number': lesson_index + 1,
            'lesson_title': lesson_title,
            'filename': filename,
            'lesson_content': content,
            'word_count': word_count,
            'topics': lesson_data.get('topics', []),
            'bloom_level': lesson_data.get('bloom_level', module_data.get('bloom_level', 'Understand')),
            'duration_minutes': lesson_data.get('duration_minutes', module_data.get('duration_minutes', 45))
        }
        
        parsed_lessons.append(parsed_lesson)
        
        print(f"  ✅ Lesson {lesson_index + 1}: {lesson_title} ({word_count} words)")
    
    return parsed_lessons


def lambda_handler(event, context):
    """
    AWS Lambda handler - SIMPLIFIED SINGLE-BATCH VERSION
    
    Generates ONE batch of lessons per invocation (max 3 lessons).
    Step Functions handles parallelization with MaxConcurrency.
    """
    
    try:
        print("=" * 70)
        print("CONTENT GENERATION LAMBDA - SINGLE BATCH MODE")
        print("=" * 70)
        
        # Debug: Print full event
        print(f"\n📥 Received event:")
        print(json.dumps(event, indent=2, default=str))
        
        # Extract batch parameters
        module_num = event.get('module_number')
        batch_start_idx = event.get('batch_start_idx', 0)
        batch_end_idx = event.get('batch_end_idx')
        batch_index = event.get('batch_index', 1)
        total_batches = event.get('total_batches', 1)
        
        model_provider = event.get('model_provider', 'bedrock').lower()
        
        # S3 configuration
        outline_s3_key = event.get('outline_s3_key')
        course_bucket = event.get('course_bucket')
        project_folder = event.get('project_folder')
        
        if not all([module_num, outline_s3_key, course_bucket, project_folder]):
            raise ValueError("Missing required parameters: module_number, outline_s3_key, course_bucket, project_folder")
        
        module_num = int(module_num)
        batch_start_idx = int(batch_start_idx)
        
        print(f"\n📋 Batch Info:")
        print(f"  Module: {module_num}")
        print(f"  Batch: {batch_index}/{total_batches}")
        print(f"  Lessons: {batch_start_idx + 1}-{batch_end_idx if batch_end_idx else 'all'}")
        print(f"  Model: {model_provider}")
        print(f"  Outline: s3://{course_bucket}/{outline_s3_key}")
        
        # Load outline from S3
        print(f"\n📥 Loading outline from S3...")
        outline_obj = s3_client.get_object(Bucket=course_bucket, Key=outline_s3_key)
        outline_content = outline_obj['Body'].read().decode('utf-8')
        outline_data = yaml.safe_load(outline_content)
        
        # Support both 'course' and 'course_metadata' keys
        course_info = outline_data.get('course', outline_data.get('course_metadata', {}))
        # Get modules from course structure (support both nested and flat formats)
        course_data = outline_data.get('course', outline_data)
        modules = course_data.get('modules', [])
        
        # Validate module
        if module_num > len(modules) or module_num < 1:
            raise ValueError(f"Module {module_num} not found (outline has {len(modules)} modules)")
        
        module_data = modules[module_num - 1]
        module_lessons = module_data.get('lessons', [])
        
        # If batch_end_idx not specified, generate all lessons
        if batch_end_idx is None:
            batch_end_idx = len(module_lessons)
        else:
            batch_end_idx = int(batch_end_idx)
        
        # Validate batch range
        if batch_start_idx >= len(module_lessons) or batch_end_idx > len(module_lessons):
            raise ValueError(f"Invalid batch range [{batch_start_idx}:{batch_end_idx}] for module with {len(module_lessons)} lessons")
        
        # Get OpenAI key if needed
        openai_api_key = None
        if model_provider == 'openai':
            try:
                secret = get_secret("aurora/openai-api-key")
                openai_api_key = secret.get('api_key')
            except Exception as e:
                print(f"⚠️  Could not get OpenAI key: {e}")
                openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Count existing visuals to determine global starting number
        print(f"\n📊 Counting existing visual prompts...")
        starting_visual_number = count_existing_visuals(course_bucket, project_folder) + 1
        print(f"✅ Starting visual number for this batch: {starting_visual_number:04d}")
        
        # Get lesson requirements if provided
        lesson_requirements = event.get('lesson_requirements', '')
        if lesson_requirements:
            print(f"📝 Additional lesson requirements: {lesson_requirements[:100]}...")

        # Load manual reference text if manual_text_s3_key is present
        manual_text_s3_key = event.get('manual_text_s3_key')
        manual_reference_text = ''
        if manual_text_s3_key:
            try:
                print(f"📥 Loading manual reference text: s3://{course_bucket}/{manual_text_s3_key}")
                man_obj = s3_client.get_object(Bucket=course_bucket, Key=manual_text_s3_key)
                manual_reference_text = man_obj['Body'].read().decode('utf-8')
                print(f"✅ Loaded {len(manual_reference_text):,} characters of manual reference text.")
            except Exception as man_err:
                print(f"⚠️ Could not load manual reference text from S3: {man_err}")
            
        # ------------------------------------------------------------------
        # IDEMPOTENCY CHECK: Skip generation if lessons already exist
        # ------------------------------------------------------------------
        force_regenerate = event.get('force_regenerate', False)
        
        if not force_regenerate:
            try:
                all_lessons_exist = True
                existing_lesson_keys = []
                existing_total_words = 0
                
                # Predict filenames for this batch
                current_batch_lessons = module_lessons[batch_start_idx:batch_end_idx]
                
                for i, lesson_data in enumerate(current_batch_lessons):
                    lesson_idx = batch_start_idx + i
                    title = lesson_data.get('title', f'Lesson {lesson_idx + 1}')
                    filename = format_lesson_filename(module_num, lesson_idx, title)
                    key = f"{project_folder}/lessons/{filename}"
                    
                    try:
                        s3_client.head_object(Bucket=course_bucket, Key=key)
                        print(f"⏩ Lesson already exists: {key}")
                        existing_lesson_keys.append({
                            "s3_key": key,
                            "module_number": module_num,
                            "lesson_number": lesson_idx + 1,
                            "lesson_title": title
                        })
                        # Estimate words (optional, or read object if needed, but 0 is fine for resume)
                        existing_total_words += 1000 
                    except:
                        all_lessons_exist = False
                        break
                
                if all_lessons_exist and len(existing_lesson_keys) == len(current_batch_lessons):
                    print(f"\n{'='*70}")
                    print(f"⏩ SMART RESUME: All {len(existing_lesson_keys)} lessons in batch already exist.")
                    print(f"{'='*70}")
                    return {
                        'statusCode': 200,
                        'message': f'Batch {batch_index}/{total_batches} skipped (already exists)',
                        'lesson_keys': existing_lesson_keys,
                        'bucket': course_bucket,
                        'project_folder': project_folder,
                        'module_number': module_num,
                        'batch_index': batch_index,
                        'total_batches': total_batches,
                        'lessons_generated': 0,
                        'total_words': existing_total_words,
                        'model_provider': model_provider,
                        'skipped': True
                    }
            except Exception as e:
                print(f"⚠️  Idempotency check failed: {e} (proceeding with generation)")
        else:
            print(f"⚠️  Force regenerate requested: Skipping idempotency check.")
            
        # ------------------------------------------------------------------
        # GENERATE THIS BATCH
        # ------------------------------------------------------------------
        print(f"\n{'='*70}")
        print(f"📚 GENERATING MODULE {module_num} - BATCH {batch_index}/{total_batches}")
        print(f"{'='*70}")
        
        outline_lang_raw = extract_outline_language(outline_data)
        print(f"🌐 Outline language raw: {outline_lang_raw!r}")

        generated_lessons = generate_batch_single_call(
            module_number=module_num,
            batch_start_idx=batch_start_idx,
            batch_end_idx=batch_end_idx,
            module_data=module_data,
            course_data={
                'title': course_info.get('title', course_data.get('title', 'Course')),
                'modules': modules,
                'language': outline_lang_raw,
            },
            model_provider=model_provider,
            openai_api_key=openai_api_key,
            starting_visual_number=starting_visual_number,
            lesson_requirements=lesson_requirements,
            manual_reference_text=manual_reference_text
        )
        
        # Save lessons to S3
        print(f"\n💾 Saving {len(generated_lessons)} lesson(s) to S3...")
        
        lesson_keys = []
        total_words = 0
        
        for lesson in generated_lessons:
            lesson_key = f"{project_folder}/lessons/{lesson['filename']}"
            
            s3_client.put_object(
                Bucket=course_bucket,
                Key=lesson_key,
                Body=lesson['lesson_content'].encode('utf-8'),
                ContentType='text/markdown'
            )
            
            print(f"  ✅ Saved: {lesson_key}")
            
            # Build structured lesson info for VisualPlanner (OPTIMIZED: batch processing)
            lesson_keys.append({
                "s3_key": lesson_key,
                "module_number": lesson['module_number'],
                "lesson_number": lesson['lesson_number'],
                "lesson_title": lesson['lesson_title']
            })
            
            total_words += lesson['word_count']
        
        # Return success response
        print(f"\n{'='*70}")
        print(f"✅ BATCH COMPLETE: Generated {len(generated_lessons)} lesson(s)")
        print(f"📊 Total words: {total_words:,}")
        print(f"{'='*70}")
        
        return {
            'statusCode': 200,
            'message': f'Batch {batch_index}/{total_batches} completed successfully',
            'lesson_keys': lesson_keys,  # Required by Step Functions
            'bucket': course_bucket,
            'project_folder': project_folder,
            'module_number': module_num,
            'batch_index': batch_index,
            'total_batches': total_batches,
            'lessons_generated': len(generated_lessons),
            'total_words': total_words,
            'model_provider': model_provider
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'error': str(e),
            'errorType': type(e).__name__
        }
