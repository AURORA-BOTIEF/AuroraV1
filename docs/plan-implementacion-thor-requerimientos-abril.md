# Plan THOR – Requerimientos Abril

Seguimiento de la implementación en Aurora (`CG-Backend`) según el informe **Thor Requerimientos Abril** (plataforma THOR 260415).

**Leyenda:** `[x]` cubierto en código/backend · `[ ]` falta, pendiente operativo o decisión pendiente.

## 1. Aumentado / libro

- [x] Prompts + validación: fidelidad al YAML por lección (`strands_content_gen.py`)
- [x] Validación de URLs en Recursos adicionales (`book_builder.py`): GET + caché; enlaces no alcanzables **omitidos** (sin marca “no verificado”); presupuesto acotado por lección
- [x] Referencias bibliográficas al **final de cada capítulo** en el libro ensamblado (`book_builder.py`)
- [x] Enriquecimiento visual obligatorio por tema en prompts (`strands_content_gen.py`)
- [ ] Validador automático post-generación: comprobar que **cada topic YAML** tiene su H2 en el MD de la lección

## 2. Infográfico / PPT – contenido

- [x] Resolución ampliada de imágenes (`s3://`, rutas relativas bajo `project_folder`, HTTPS-S3) (`html_to_ppt_converter.py`)
- [x] Negritas sin `**` en texto PPT (`_normalize_ppt_plain_text`)
- [x] Código: continuación sin texto literal `truncated` en slide (`html_first_generator.py`)
- [ ] Eliminar por completo truncamiento por límites (sigue siendo posible con layouts restrictivos; revisar límites/`split` en otro ciclo)
- [x] Regla de español en generación de slides teóricos (`html_first_generator.py`)
- [ ] **Tablas en PPT:** diseño menos básico (objetos tabla con estilo en `python-pptx`; hoy no hay pipeline dedicado en `html_to_ppt_converter.py`)
- [x] Tipografías estándar (`PT_*`) en títulos de slide normales, capítulo y lección

## 3. Estructura de navegación PPT

- [x] Orden por módulo: Resumen → Laboratorios → Referencias (`_emit_module_end_slides`)
- [x] Sin slide de logo Netec al cierre de módulo (sustituido por referencias cuando aplica)
- [ ] Slide **Referencias Bibliográficas** vacío con texto placeholder si no hay entradas (opcional según negocio)

## 4. Tipografías

- [x] Constantes `PT_*` y títulos de desarrollo a 40 pt donde aplica (`html_to_ppt_converter.py`)
- [x] Título de laboratorio ~50 pt en HTML (`.lab-intro-title`)
- [ ] Unificar tamaños en **todas** las plantillas especiales (portada/agenda/grupos vs slides de contenido)

## 5. Slide de laboratorio

- [x] Texto de planteamiento + placeholder / URL opcional (`create_lab_slides_from_content`)
- [ ] Pasar **URL real de GitHub Pages** desde el flujo de publicación hasta la Lambda (`github_pages_url` / metadata por lab)

## 6. Menos slides / densidad

- [x] Sin logo grande de cierre por módulo en el flujo actual
- [x] Parámetro `course_duration_hours` en API de infográfico (`infographic_generator.py`)
- [ ] **Frontend / orquestación:** enviar `course_duration_hours` desde la UI o Step Functions

## 7. Laboratorios GitHub

- [x] Prompt de alineación temario en planner (`strands_lab_planner.py`)
- [x] Sección **Objetivo visual** en plantilla de writer (`strands_lab_writer.py`)
- [ ] Subida de **imágenes** de labs al repo según necesidad pedagógica (`docs/GITHUB_APP_NETEC_MX.md`: hoy suele ser markdown-only)

## 8. QA / despliegue

- [x] `sam build` en `CG-Backend/` OK (última ejecución exitosa)
- [ ] Prueba manual curso corto + largo (contenido real + PPT descargado)
- [ ] `sam deploy` con perfil Netec (`AGENTS.md`) cuando corresponda la ventana

## 9. Decisiones de negocio / PDF

- [ ] Confirmar con stakeholders si **Referencias** globales al final del curso deben deduplicarse respecto a referencias por capítulo (el PDF lista ambos bloques)

---

### Referencias de código principales

| Área | Archivos |
|------|-----------|
| Libro / refs por capítulo | `lambda/book_builder.py` |
| Generación teoría | `lambda/strands_content_gen/strands_content_gen.py` |
| Orden slides + labs | `lambda/strands_infographic_generator/html_first_generator.py` |
| Infográfico API | `lambda/strands_infographic_generator/infographic_generator.py` |
| PPT desde HTML | `lambda/ppt_merger/html_to_ppt_converter.py` |
| Planner labs | `lambda/strands_lab_planner/strands_lab_planner.py` |
| Writer labs | `lambda/strands_lab_writer/strands_lab_writer.py` |
