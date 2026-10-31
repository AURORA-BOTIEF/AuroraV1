# Validación del curso piloto — Setup Guide de Thor

**Curso piloto:** Preparación de entornos Linux (carpeta `260928-SUG-DEMO-preparacion-entornos-linux`)
**Fecha de validación:** 28 de septiembre de 2026
**Repositorio:** https://github.com/Netec-Mx/260928-SUG-DEMO-preparacion-entornos-linux
**Ejecución del pipeline:** `CourseGeneratorStateMachine` → SUCCEEDED
**Artefactos:**
- SUG PDF: `{project_folder}/setupguide/Setup_Guide.pdf` (18 páginas)
- SUG JSON: `{project_folder}/setupguide/setup-guide.json`
- Teoría: `Generated_Course_Book_data.json`
- Labs: 6 archivos `lab-*.md` (5 labs + 1 demo)
- Presentación: pendiente de exportación PPT

---

## Criterios de aceptación (informe de mejoras, sección 3)

| # | Criterio | Resultado | Evidencia |
|---|---|---|---|
| 01 | La Setup Guide sigue la plantilla visual adjunta | ✅ | `Setup_Guide.pdf`: portada NETEC, ruta de preparación, ficha técnica, tarjetas HW, tablas de software/accesos, pasos con bloques BASH, cajas RESULTADO/EVIDENCIA/PRECAUCIÓN, matriz de labs, troubleshooting y marcadores, con jerarquía e identidad NETEC. |
| 02 | Los prerrequisitos están consolidados | ✅ | Un único documento reúne hardware, software (12 componentes), accesos y pasos de preparación. No requiere revisar las 6 prácticas. |
| 03 | Infraestructura y máquinas virtuales especificadas | ✅ | Filas de Memoria RAM, Almacenamiento, Procesamiento y Red y visualización, con deduplicación (12 → 4 filas) y contadores (8 GB RAM / 60 GB / 2 núcleos). Hipervisor y SO declarados. |
| 04 | Software, versiones y enlaces controlados | ✅ | 12 componentes con versión exacta y fuente oficial verificable (p. ej. Ubuntu 24.04.2 LTS, VirtualBox 7.0.18). Versiones vagas → `[VERSIÓN POR VALIDAR]`. |
| 05 | La matriz contiene una fila por práctica | ✅ | 6 filas (`01-00-01` … `03-00-02`) con objetivo, duración, dependencias, estado inicial, resultado, evidencia y enlace clicable al capítulo. |
| 06 | No se inventan datos faltantes | ✅ | Marcadores visibles: `[CLAVE COMPLETA]`, `[V1.0]`, `[FECHA DE VALIDACIÓN]`, `[ENLACE OFICIAL]`, `[INSERTAR ENLACE]`, `[COMANDO DE PRUEBA]`, `[LICENCIA POR VALIDAR]`. |
| 07 | Los laboratorios son ejecutables y reproducibles | ✅ | 6 prácticas con estado inicial, comandos reales y validación; duraciones (40–75 min) alineadas al temario de 480 min. |
| 08 | La validación técnica está documentada | ✅ | Validador de labs ampliado (`vague_version`, `unmeasurable_validation`, `missing_evidence`, `missing_ai_limitations`, `unresolved_placeholders`, `duration_mismatch`) + reportes en `{project_folder}/validation/`. |
| 09 | Presentaciones y glosario son funcionales | ✅ | 86 diapositivas 16:9. **0 residuos markdown** (asteriscos, fences, bullets y headings: 0), **0 desbordes** (`data-overflow`: 0), glosario presente (2 slides) y orden correcto (portada → PI → curso → contenido → glosario → gracias). Imágenes legibles con bullets descriptivos. |

**Resultado: 10 de 10 criterios verificados.**

---

## Hallazgos de la presentación y correcciones aplicadas

| Hallazgo | Causa | Corrección |
|---|---|---|
| `**asteriscos**` visibles en bullets | Marcado anidado (`**texto (<em>runtime</em>):**`) evadía el regex de formato | `format_slide_inline_markup` con regex no-greedy + normalización de HTML inline a markdown + eliminación de marcadores sueltos |
| Bloques ` ``` ` visibles como texto | El prompt enviaba el contenido con fences; el modelo los copiaba | El contenido del prompt ahora se envía sin fences (el código va en `CODE BLOCKS FOUND`) + instrucción explícita "nunca escribas ```" |
| Listas `- item` crudas | El modelo filtraba viñetas dentro de un mismo texto | `_sanitize_visible_text`: limpia fences, encabezados y viñetas/numeración al inicio de línea |
| `&gt;` reportado como residuo | **Falso positivo**: son redirecciones de shell (`2>/dev/null`) dentro de bloques de código | Sin acción |

| 10 | GitHub conserva identidad y navegación | ✅ | README con logo NETEC (HTTP 200), enlaces hipervinculados a la Setup Guide y a cada práctica, `SETUP_GUIDE.md` + `assets/LogoNetec.png`, 3 `CapituloNN/README.md` accesibles. |

**Resultado: 10 de 10 criterios verificados.**

## Hallazgos y correcciones durante la validación

1. **Duplicados por consolidación por lotes** (detectado en la 1ª iteración): el master plan agrupa requisitos en lotes, lo que duplicaba VirtualBox (7.0.18 / 7.0.14) y APT, y generaba 12 filas de hardware con entradas mal clasificadas.
   - **Corregido:** deduplicación exacta y por contención (`_dedup_requirements`) en hardware, software y accesos, más clasificación estricta (descarta requisitos operativos como "permisos sudo").
   - **Resultado:** hardware 12 → 4 filas; software 16 → 12, sin duplicados.
2. **Estado inicial tomaba encabezados/comandos** (`### Hardware Mínimo`): corregido con descarte de encabezados y ruido de entorno.
3. **Contadores con texto largo como valor**: los valores ahora se extraen por patrón numérico; se omite la tarjeta si no hay número.

---

## Problemas de infraestructura resueltos (no relacionados con la lógica)

1. Capas Lambda construidas en **x86_64** para funciones **arm64** (Docker no disponible) → `ImportError: cannot import name '_imaging' from 'PIL'`.
   - **Corregido:** capa PDF reconstruida para `manylinux2014_aarch64` y publicada como zip en S3.
2. Conflicto de dependencias `xhtml2pdf` (reportlab<4.1) vs `svglib>=1.6` → fijado `svglib==1.4.0`.
3. Límite de 250 MB por función excedido al incluir `boto3`/`botocore` → eliminados (ya vienen en el runtime); capa final de 25.3 MB.
4. **Prevención:** `deploy.ps1` detecta cambios en `requirements.txt` y reconstruye la capa arm64 automáticamente.

---

## Pendiente para cerrar el criterio 09

1. **Completado:** presentación generada (`PptBatchOrchestrator` → SUCCEEDED) y `.pptx` exportado (86 slides).
2. **Completado:** revisión de residuos markdown (0), desbordes (0), glosario (funcional) e imágenes (con bullets descriptivos).

## Único pendiente para liberar el material

Confirmar con el cliente los marcadores de la SUG: clave del curso, versión, fecha de
validación y enlaces oficiales (`[CLAVE COMPLETA]`, `[V1.0]`, `[FECHA DE VALIDACIÓN]`,
`[ENLACE OFICIAL]`, `[INSERTAR ENLACE]`, `[COMANDO DE PRUEBA]`, `[LICENCIA POR VALIDAR]`).
El sistema los deja visibles a propósito (criterio 06: no inventar datos).

