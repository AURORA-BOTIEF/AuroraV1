# Reporte de despliegues y actividades

Periodo revisado: 24 al 30 de abril de 2026

## Alcance y fuentes

Este reporte se construyó a partir de evidencia local del repositorio:

- Historial Git del periodo 2026-04-24 a 2026-04-30.
- Workflows de GitHub en `.github/workflows/`.
- Pipeline de frontend en `amplify.yml`.
- Configuracion y scripts de despliegue SAM en `CG-Backend/`.

No se encontraron en el repositorio logs remotos de ejecucion de GitHub Actions, Amplify o AWS SAM que permitan certificar una corrida concreta de despliegue en produccion durante la semana. Por eso, las conclusiones de este documento describen con precision la actividad implementada y la configuracion de despliegue observada, pero no sustituyen una auditoria sobre las consolas remotas.

## Resumen ejecutivo

Durante la ultima semana de abril hubo actividad relevante en la superficie de despliegue backend con AWS SAM y en funcionalidades que, al ser integradas en ramas con despliegue activo, habrian requerido publicacion de frontend y Lambdas. La evidencia mas clara de cambios de despliegue se concentra en dos commits que modificaron `CG-Backend/template.yaml` el 28 y 29 de abril.

En GitHub no hubo cambios a los workflows durante el periodo revisado. Los workflows actuales (`ci.yml` y `python-tests.yml`) se usan para CI y pruebas, no para despliegue directo. El frontend sigue el flujo de build definido en `amplify.yml`, por lo que el despliegue web depende de push hacia la rama conectada en Amplify, no de un workflow de GitHub Actions dedicado a deploy.

En SAM, el stack configurado sigue siendo `crewai-course-generator-stack` en `us-east-1`. Los scripts de despliegue locales confirman un modelo mixto: CloudFormation/SAM para infraestructura y, en varios casos, actualizacion manual del codigo de Lambdas empaquetadas para preservar dependencias.

## Actividades registradas por fecha

## Resumen tabular de actividades y horas estimadas

Estimacion referencial basada en el alcance tecnico observado en los commits, los componentes tocados y el tipo de despliegue requerido. La tabla se reorganiza para enfatizar las mejoras alineadas al documento [Plan THOR - Requerimientos Abril], diferenciando lo que cubre de forma directa un requerimiento explicito y lo que lo soporta de forma complementaria. No sustituye una hoja de tiempo operativa.

| Fecha | Alineacion THOR | Requerimiento THOR relacionado | Mejora implementada | Como aporta al requerimiento | Componentes impactados | Horas estimadas |
| --- | --- | --- | --- | --- | --- | ---: |
| 2026-04-28 | Complementaria | 1. Aumentado / libro - enriquecimiento visual obligatorio por tema | Integracion de OpenAI GPT Image 2 en `ImagesGen` | Amplia las opciones de generacion visual del sistema y mejora la calidad potencial de imagenes usadas en contenidos y artefactos del curso. | `CG-Backend/lambda/images_gen/images_gen.py`, `CG-Backend/template.yaml` | 5.5 |
| 2026-04-28 | Complementaria | 1. Aumentado / libro - enriquecimiento visual obligatorio por tema | Selector de modelo de imagen en la UI | Hace operable desde frontend la eleccion entre velocidad, costo y calidad visual para la generacion del curso. | `src/components/GeneradorCursos.jsx` | 1 |
| 2026-04-28 | Complementaria | Soporte operativo transversal al flujo THOR | Ajuste de etiqueta de GPT Image 2 | Reduce exposicion de detalles sensibles en UI y limpia la experiencia operativa del generador. | `src/components/GeneradorCursos.jsx` | 0.5 |
| 2026-04-29 | Directa | 2. Infografico / PPT - contenido | Estabilizacion de capas en `ExportPptFunction` | Elimina el conflicto con `lxml` en la exportacion PPT y deja mas estable la funcion encargada de generar el entregable requerido. | `CG-Backend/template.yaml` | 2.5 |
| 2026-04-29 | Directa | 1. Aumentado / libro - validacion de URLs en Recursos adicionales | Recoleccion automatica de URLs por modulo | Consolida URLs desde contenido y referencias, evita duplicados y prepara la base para recursos y referencias confiables por capitulo. | `CG-Backend/lambda/book_builder.py` | 1.5 |
| 2026-04-29 | Directa | 1. Aumentado / libro - referencias bibliograficas al final de cada capitulo | Extraccion y sanitizacion de bibliografia y URLs | Parsea secciones Bibliografia/Referencias, valida enlaces y sanea recursos antes de ensamblarlos en el libro. | `CG-Backend/lambda/book_builder.py` | 2 |
| 2026-04-29 | Complementaria | 3. Estructura de navegacion PPT - orden por modulo: Resumen -> Laboratorios -> Referencias | Resumen automatico por capitulo | Refuerza la estructura pedagogica del modulo y prepara mejor el material para la narrativa de cierre y continuidad del curso. | `CG-Backend/lambda/book_builder.py` | 1.5 |
| 2026-04-29 | Directa | 1. Aumentado / libro - referencias bibliograficas al final de cada capitulo | Propagacion de `ref_urls` e hipervinculos al editor | Mantiene las referencias a nivel de leccion para edicion y reutilizacion posterior en libro, editor y salidas derivadas. | `CG-Backend/lambda/book_builder.py`, `src/components/BookEditor.jsx` | 1 |
| 2026-04-30 | Directa | 1. Aumentado / libro + 2. Infografico / PPT - contenido | Refactor de extraccion bibliografica multinivel | Centraliza la deteccion de secciones de bibliografia/referencias en espanol e ingles para reutilizar la logica entre libro, PPT e infograficos. | `CG-Backend/lambda/strands_infographic_generator/html_first_generator.py`, `CG-Backend/lambda/book_builder.py` | 2.5 |
| 2026-04-30 | Directa | 1. Aumentado / libro + 2. Infografico / PPT - contenido + 3. Estructura de navegacion PPT | Recoleccion unificada de referencias por capitulo | Integra URLs del modulo, referencias explicitas en markdown y `ref_urls` extraidas para alimentar las salidas de PPT, infograficos y otros artefactos. | `CG-Backend/lambda/strands_infographic_generator/html_first_generator.py`, `CG-Backend/lambda/ppt_merger/html_to_ppt_styled.py` | 2 |
| 2026-04-30 | Complementaria | 2. Infografico / PPT - contenido | Normalizacion de titulos de modulo a capitulo | Mejora la consistencia editorial y visual de la salida PPT con terminologia mas uniforme entre capitulos y secciones. | `CG-Backend/lambda/strands_infographic_generator/html_first_generator.py`, `CG-Backend/lambda/ppt_merger/html_to_ppt_styled.py` | 1 |
|  |  |  | **Total estimado** |  |  | **21** |

### 28 de abril de 2026

**Commit 6a0cefc**

Se integro OpenAI GPT Image 2 en el flujo de `ImagesGen` y se agrego selector en la interfaz de `GeneradorCursos`.

Impacto de despliegue:

- Se actualizo `CG-Backend/template.yaml`.
- El cambio implica despliegue backend para exponer configuracion nueva de Lambda y permisos asociados.
- El cambio en `src/components/GeneradorCursos.jsx` tambien implica rebuild y redeploy de frontend si esa rama esta conectada a Amplify.

Lectura operativa:

- Esta fue la principal actividad de backend/SAM del 28 de abril.
- La funcionalidad agregada modifica la superficie de integracion con servicios externos, por lo que no es solo un cambio interno de codigo.

**Commit c375146**

Se corrigio la etiqueta mostrada en UI para GPT Image 2 sin exponer detalles de clave API al usuario.

Impacto de despliegue:

- Cambio de frontend solamente.
- Si hubo push a la rama conectada en Amplify, este ajuste debio entrar en el siguiente despliegue web.

### 29 de abril de 2026

**Commit 9cd9b1e**

Se actualizo la capa usada por la exportacion a PPT y se mejoro la recoleccion de URLs.

Impacto de despliegue:

- `CG-Backend/template.yaml` volvio a cambiar.
- El mensaje del commit documenta que se removio `StrandsAgentsLayer` de la Lambda de exportacion PPT para evitar conflictos con `lxml`.
- Este es un ajuste claramente orientado a estabilizar el despliegue/ejecucion de la funcion de exportacion.

Lectura operativa:

- Fue una actividad de hardening del backend desplegable.
- Reduce riesgo de fallas por dependencias incompatibles en una Lambda ya expuesta a uso funcional.

**Commit c7cda41**

Se agregaron recursos mediante URLs, resumen de capitulo e hipervinculos en editor.

Impacto de despliegue:

- Afecta `book_builder`, `strands_content_gen`, `BookEditor.jsx` y documentacion.
- Requiere despliegue backend y frontend para que los cambios queden disponibles extremo a extremo.

### 30 de abril de 2026

**Commit 0a63c8e**

Se refactorizo el manejo de bibliografia en multiples modulos.

Impacto de despliegue:

- Cambios en Lambdas, generacion PPT, generacion de infograficos y esquemas.
- Aunque no modifica `template.yaml`, si demanda despliegue del codigo de funciones afectadas para que el comportamiento nuevo llegue al entorno activo.

## Revision de GitHub y Amplify

### Estado observado

- `.github/workflows/ci.yml` ejecuta pruebas generales y publica artefactos de testing.
- `.github/workflows/python-tests.yml` ejecuta pruebas Python del generador PPT y publica un artefacto `.pptx` de muestra.
- `amplify.yml` define el build del frontend (`npm ci` o `npm install`, luego `CI=false npm run build`) y publica `dist/`.

### Hallazgos de la semana

- No hubo commits sobre `.github/workflows/` ni `amplify.yml` entre el 24 y el 30 de abril.
- Por tanto, no se observa actividad de ajuste al pipeline GitHub/Amplify en esa semana.
- La actividad relacionada con GitHub fue indirecta: cualquier push de cambios de frontend hacia la rama conectada en Amplify habria disparado el build definido en `amplify.yml`.

### Conclusion de GH

Durante la ultima semana de abril no hubo cambios en automatizacion de deploy via GitHub. El esquema vigente sigue siendo:

- GitHub Actions para CI y artefactos de prueba.
- Amplify para despliegue frontend disparado por push.

## Revision de AWS SAM

### Estado observado

- `CG-Backend/samconfig.toml` mantiene el despliegue sobre `crewai-course-generator-stack` en `us-east-1`.
- `CG-Backend/template.yaml` define Lambdas, capas y recursos del backend.
- Los scripts `deploy-with-dependencies.sh` y `deploy-ppt-system.sh` confirman que el proceso real de despliegue es mas que un `sam deploy` simple.

### Actividad de la semana

- Hubo dos cambios directos a `template.yaml` durante el periodo revisado: 28 y 29 de abril.
- El 28 de abril se introdujo soporte para OpenAI GPT Image 2 y permisos/configuracion asociados.
- El 29 de abril se ajusto la Lambda de exportacion PPT para evitar conflictos por capas y dependencias.

### Observaciones operativas

- `deploy-with-dependencies.sh` advierte que un `sam deploy` aislado puede sobreescribir funciones sin incluir correctamente dependencias externas, y por eso fuerza un segundo paso de rebuild y redeploy selectivo de Lambdas.
- `deploy-ppt-system.sh` hace `sam build`, `sam deploy` y luego actualizaciones manuales de codigo Lambda con `aws lambda update-function-code`.
- Esto indica que el backend no opera con un flujo SAM completamente estandarizado de un solo paso; existe una capa operativa adicional para asegurar empaquetado correcto.

### Conclusion de SAM

La ultima semana de abril si tuvo actividad real sobre la superficie de despliegue SAM. Los cambios mas relevantes fueron:

- habilitacion de una nueva capacidad de generacion de imagenes en backend;
- ajuste de capas/dependencias para exportacion PPT;
- despliegues de codigo requeridos por refactors funcionales del 29 y 30 de abril.

## Riesgos y observaciones

1. No hay evidencia local de ejecuciones remotas exitosas o fallidas de GitHub Actions, Amplify o `sam deploy`; el reporte se basa en commits y configuracion versionada.
2. Los workflows de GitHub encontrados no despliegan directamente a AWS ni frontend; si se esperaba deploy desde GitHub Actions, hoy no esta implementado en el repositorio.
3. Los scripts SAM dependen de pasos manuales o semimanuales adicionales para preservar dependencias, lo que aumenta complejidad operativa.
4. Las instrucciones del repositorio indican uso del perfil AWS `Netec`, pero los scripts revisados no lo fuerzan explicitamente con `--profile Netec`; actualmente dependen del entorno.

## Conclusiones finales

La actividad de la ultima semana de abril se concentro en backend y en funcionalidades que requerian despliegue coordinado entre frontend y Lambdas. En GitHub/Amplify no hubo cambios de pipeline; el comportamiento de despliegue se mantuvo estable y dependiente de push a la rama conectada. En AWS SAM si hubo cambios concretos de infraestructura/aplicacion desplegable, especialmente el 28 y 29 de abril, con foco en generacion de imagenes y estabilidad de la exportacion a PPT.

Si necesitas convertir este reporte en un formato ejecutivo para estatus o para auditoria interna, el siguiente paso natural es cruzarlo con:

- historial de ejecuciones de GitHub Actions;
- historial de deploys en Amplify;
- CloudFormation events y actualizaciones Lambda en AWS.