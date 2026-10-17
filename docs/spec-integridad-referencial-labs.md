# Especificación: integridad referencial de los laboratorios

**Estado:** propuesta para revisión
**Fecha:** 16 de octubre de 2026
**Origen:** informe «Evaluación de calidad: contenido y laboratorios generados con THOR» (15/10/2026)
**Relacionado:** `docs/plan-implementacion-thor-requerimientos-abril.md`

---

## 1. Problema

El informe mide los laboratorios en 2,2/5 (corrección técnica 4,4/10, claridad 4,1/10) y un
retrabajo superior al 75 % de los laboratorios en 10 de 14 cursos. Al leer los comentarios de
los instructores, el patrón no es de redacción: **son fallos de consistencia entre cosas que
deberían concordar**.

| Comentario del instructor | Debe concordar con |
|---|---|
| «se inventaron datos del prospecto… que no estaban definidos en el temario» | el temario |
| «cambió el escenario de seis fondos a tres e inventó nombres, comisiones, benchmarks» | el temario |
| «cambió cifras entre prácticas» | las demás prácticas |
| «exigió archivos y salidas previas que no formaban parte del alcance» | su propia secuencia |
| «las duraciones declaradas sumaban correctamente 185 minutos, [pero] el volumen real de pasos era incompatible» | su propio presupuesto de tiempo |
| «Reemplacé versiones y builds históricos, rutas e interfaces rígidas» | el software vigente |
| «corregí duplicaciones, enlaces, estructura del README y Setup Guide» | los laboratorios |

Esta clase de defecto —«X debe concordar con Y y no concuerda»— es **verificable
mecánicamente**, a diferencia de «¿el laboratorio es bueno?». Esta especificación define esas
verificaciones.

## 2. Principio rector

1. **El temario es de solo lectura.** No se le añaden campos obligatorios: los temarios son
   desiguales en detalle y pedir más información no es viable. La IA puede completar lo que
   falta, pero **no puede cambiar** lo que el temario define.
2. **Tres niveles para toda afirmación concreta:**

   | Nivel | Regla | Ejemplo |
   |---|---|---|
   | **Declarado** en una fuente | se afirma | el temario nombra «Idea Coach» |
   | **Derivable / autocerrado** | se afirma | un fichero que el propio paso 2 crea y el paso 5 usa |
   | **No declarado ni derivable** | **no se afirma**: frase funcional o `[POR CONFIRMAR]` | el nombre exacto de un botón de Copilot, `Demanda_Historica.xlsx` |

3. **Los documentos adicionales siguen siendo opcionales** y no cambian el flujo de carga.
   Su presencia no es un requisito: solo **sube el techo de verificabilidad**. Sin ellos el
   sistema no falla, degrada. Mismo patrón que ya usa el manual: si no viene
   `manual_text_s3_key`, el Writer no emite sección de manual y continúa.
4. **La conducta por defecto ante un dato sin fuente es marcarlo, no inventarlo.**

## 3. Fuentes

| Id | Fuente | Obligatoria |
|---|---|---|
| S1 | Temario (`outline.yaml`) | sí |
| S2 | Manual de referencia (PDF extraído) | no |
| S3 | Documentación adicional | no |
| S4 | Plan maestro (`labguide/lab-master-plan.json`) | sí (se genera) |

S1–S3 son **entradas de solo lectura**. S4 es un artefacto generado: es el contrato interno
que consumen los laboratorios, el README y el Setup Guide.

## 4. Verificaciones

### Capa A — Fidelidad: el plan contra las fuentes

| Id | Qué comprueba | Evidencia del informe |
|---|---|---|
| **A1** | Todo *referente* del plan (rutas, ficheros con extensión, nombres propios, versiones, cifras y umbrales) existe en S1–S3, o está clasificado como derivable | `Demanda_Historica.xlsx`, `C:\Forecasting_Logistica\` y cuatro nombres de entregable aparecen **0 veces** en temario y manual, y sí en `special_considerations` del plan |
| **A2** | Las cantidades y los nombres de entidades no contradicen al temario | «cambió el escenario de **seis fondos a tres** e inventó nombres»; «sustituyó CIBEST CAPITAL por Northstar Digital» |
| **A3** | Σ duración de laboratorios ≤ duración declarada del curso, y el número de laboratorios es compatible con el formato | «una conferencia de 2 horas… se generaron más de 10 prácticas»; «si se indica en el temario que son 4 min debería aplicarse en consecuencia» |
| **A4** | Los entregables declarados por práctica son los del temario y no se inventan nombres | «cuatro nombres de entregable» fabricados por el planner |

### Capa B — Clausura: los laboratorios contra el plan y entre sí

| Id | Qué comprueba | Evidencia del informe |
|---|---|---|
| **B1** | Todo fichero, ruta o recurso **referenciado** en un laboratorio existe en S1–S3 o fue **creado antes** (mismo laboratorio o uno anterior) | «exigió archivos, carpetas de SharePoint y salidas previas que no formaban parte del alcance» |
| **B2** | Ningún laboratorio depende de salidas de un laboratorio **posterior** | «creó dependencias entre laboratorios»; «dependencias artificiales entre capítulos» |
| **B3** | Todo entregable declarado en el plan aparece **producido** en su laboratorio | «omitió elementos requeridos como Idea Coach, Corporate Comms Crafter… y la presentación ejecutiva» |
| **B4** | Las cifras y entidades se mantienen estables **entre** laboratorios | «cambió cifras entre prácticas» |
| **B5** | Ninguna versión, sistema operativo o requisito de hardware aparece en un laboratorio si no está en `software_requirements` / `hardware_requirements` del plan | «eliminé requisitos técnicos innecesarios de Windows, hardware, versiones específicas, PowerShell y carpetas locales» |
| **B6** | La duración declarada es compatible con el **número y tipo de pasos** | «las duraciones declaradas sumaban correctamente 185 minutos, el volumen real de pasos era incompatible» |
| **B7** | El Setup Guide y los laboratorios concuerdan **en ambos sentidos**: todo prerequisito que un laboratorio asume está en el Setup Guide, y todo lo del Setup Guide está justificado por el plan o los laboratorios | «corregí duplicaciones, enlaces, estructura del README y Setup Guide» |
| **B8** | Todo específico no declarado va marcado con `[POR CONFIRMAR]`, y el marcador **cuenta como señal de revisión** | hoy el prompt emite `[VERSIÓN POR VALIDAR]` y `validate_placeholders` lo reporta como INFO, de modo que la propia regla se anula |

### Capa C — Residual (el mundo)

| Id | Qué comprueba | Tratamiento |
|---|---|---|
| **C1** | Enlaces vivos | comprobación HTTP; se reporta, no bloquea |
| **C2** | Vigencia de nombres de interfaz o experiencia | **no verificable**; cae en la regla del nivel 3: no se afirma el específico |

C2 es el único caso que se beneficiaría de S2/S3. Sin ellos no hay comprobación: hay
degradación a frase funcional.

## 5. Severidad

| Severidad | Verificaciones | Consecuencia |
|---|---|---|
| **ERROR** (bloquea y reintenta) | A1, A2, A3, A4, B1, B2, B3, B5, B6 | el arreglo es determinista y no necesita a nadie; se reintenta el paso, no todo el curso |
| **ERROR si la entidad está declarada en S1; MARCADOR si no** | B4 | — |
| **MARCADOR** (no bloquea, se reporta) | B7, B8, C1, C2 | aparece en el informe de revisión, que es el artefacto que lee quien ya edita el curso |

Ninguna de estas verificaciones exige cambios en el temario, ni entradas nuevas obligatorias,
ni regeneración del curso.

## 6. Estado actual: por qué hoy no puede funcionar

La puerta existe (`lambda/content_validator`), pero hay tres obstáculos estructurales:

1. **No tiene contexto.**
   `def validate_lab(self, content: str)` recibe **solo el texto del laboratorio**. No ve el
   plan, ni el temario, ni el manual, ni los demás laboratorios. B2, B4 y B7 son **imposibles**
   con esa firma.

2. **Valida cada fichero aislado.**
   El handler recorre `content_keys` y llama a `validate_lab(content)` por fichero, así que
   ninguna propiedad del **conjunto** puede comprobarse.

3. **El veredicto no lo consume nadie.**
   El State Machine marca `"Comment": "Validate lab content against schema (non-blocking)"` y
   `"fail_on_error": false`; guarda `all_valid` en `$.lab_validation_result` y **ningún `Choice`
   lo lee** (verificado: no hay referencias a `lab_validation_result` fuera del propio
   `ResultPath`). Además, de las cinco comprobaciones THOR actuales **ninguna es ERROR — dos
   son WARNING (`vague_version`, `unmeasurable_validation`/`missing_evidence`) y tres son INFO
   (`missing_ai_limitations`, `unresolved_placeholders`, `duration_mismatch`)—, y `all_valid`
   se calcula contando solo los ERROR. Aunque el veredicto se consumiera, esas comprobaciones no
   podrían cambiarlo.

4. **La comprobación de duración es inoperante.**
   `validate_duration_consistency` extrae la duración declarada y la compara con el número de
   **palabras** con una banda de 20–160 palabras/minuto. Para un laboratorio de 185 minutos eso
   admite de 3.700 a 30.200 palabras: cualquier cosa pasa.

## 7. Cambios necesarios

1. **Contexto explícito.** El validador debe recibir S1–S4 y el conjunto de laboratorios, no
   solo el texto de cada fichero.
2. **Validación del conjunto**, además de la de cada fichero.
3. **Veredicto consumido.** Un `Choice` que decida sobre `all_valid`. El reintento debe ser
   **del laboratorio que falla**, no del curso completo.
4. **Dónde corre cada cosa:**
   - Las verificaciones evaluables **por laboratorio** (B1, B3, B5, B6, B8) se ejecutan
     **dentro de `StrandsLabWriter`**, que ya tiene un bucle de reintento
     (`MAX_LAB_GENERATION_ATTEMPTS`, 3 intentos).
   - Las verificaciones del **plan** (A1–A4) se ejecutan **dentro de `StrandsLabPlanner`**,
     antes de guardar el plan.
   - Las verificaciones del **conjunto** (B2, B4, B7) se ejecutan en el validador, que ya
     recorre todos los laboratorios.
5. **Disciplina de método**, para no repetir el error detectado el 16/10/2026:
   - **M1**: toda verificación nueva debe traer una prueba que **ejecute el camino vivo**, no
     que busque texto en el código fuente. (La prueba que sólo comprobaba
     `"select_manual_context(" in codigo` pasaba con la llamada en código muerto.)
   - **M2**: toda verificación debe declarar sobre qué artefacto corre y con qué contexto. Si
     no puede ejecutarse con el contexto disponible, no es una verificación: es un deseo.

## 8. Qué no cubre

- **Vigencia de interfaces** (C2): necesita S2/S3 o una fuente externa; sin ella, la regla es no
  afirmar el específico.
- **Calidad pedagógica** (¿el ejercicio es útil?, ¿el nivel Bloom es el adecuado?): no es
  verificable mecánicamente. Para eso está la revisión del instructor.
- **Enlaces** (C1): se comprueban, pero su vigencia es del mundo y cambia con el tiempo; por eso
  se reportan y no bloquean.

## 9. Fases

| Fase | Contenido | Por qué primero |
|---|---|---|
| 1 | Contexto en el validador + nivel 3 + A1 + B1 | mayor evidencia del informe y menor coste; A1 es una búsqueda, ya validada manualmente |
| 2 | B2, B3, B5, B6 | cierran «archivos que no existen», «entregables omitidos», «requisitos inventados» y «tiempos imposibles» |
| 3 | A2, A3, A4, B4, B7, B8 | requieren la lista de entidades y tocar el Setup Guide |
| 4 | C1 | independiente; solo enlaces |

## 10. Cómo se mide el éxito

Sobre la **salida generada**, no sobre el prompt, y con **n>1 ejecución por laboratorio** (el
16/10/2026 dos ejecuciones del mismo laboratorio coincidieron solo en un 8,6 %: la varianza
supera al efecto, así que una sola ejecución no prueba nada).

| Métrica | Objetivo |
|---|---|
| Referentes no rastreables por laboratorio | 0 |
| Duraciones declaradas incompatibles con el volumen de pasos | 0 |
| Referencias hacia delante entre laboratorios | 0 |
| Específicos sin fuente sin marcar | 0 |
| Porcentaje de laboratorios modificado por el instructor | bajar del 75 % al 25 % |

---

## Anexo: base de evidencia

- Informe: 18 evaluaciones, 15 cursos, 5 instructores; 14 cursos válidos (Vue Intermedio son
  pruebas del formulario). Laboratorios 2,2/5; corrección técnica 4,4/10; claridad 4,1/10;
  retrabajo >75 % en 10 de 14.
- Medición del 16/10/2026 sobre un curso real (manual de 231.744 caracteres): el plan generado
  contiene `Demanda_Historica.xlsx`, `C:\Forecasting_Logistica\` y `Practica1_MAPE_SKU.xlsx`,
  que aparecen **0 veces** en el temario y **0 veces** en el manual. Los laboratorios generados
  los reproducen fielmente.
- El Setup Guide ya usa la disciplina correcta (`[POR CONFIRMAR]`, `placeholders_count`), pero
  **consolida desde el plan**: es coherente con unos laboratorios que reproducen el mismo dato
  fabricado. La coherencia por consolidación no repara una fuente mala.

---

## 11. Fase 1: lo realmente implementado (16/10/2026)

Módulo `referent_check.py` (biblioteca estándar, determinista, sin dependencias), replicado
byte a byte en `strands_lab_planner/` y `strands_lab_writer/` como ya se hace con
`manual_context.py`.

**Alcance acotado a propósito: solo referentes de fichero (rutas y nombres con extensión).**
Las URL se neutralizan antes de extraer (su cola se confundía con una ruta local y producía
falsos positivos); una URL inventada se combate comprobando que esté viva, así que pertenece a
C1. Las versiones y las entidades con nombre llegan en la fase 3: exigen la lista de entidades
que A2/A3 construyen.

| Verificación | Dónde corre | Qué hace |
|---|---|---|
| A1 | `strands_lab_planner` (camino vivo, antes de guardar) | todo referente de fichero del plan debe estar en temario + manual; si no, reintento correctivo y, si persiste, queda en `metadata.referential_integrity` y en `validation/referential-integrity.json` |
| B1 | `strands_lab_writer` (dentro del bucle de reintentos que ya existía) | todo referente del laboratorio debe estar en las fuentes, en el plan **verificado**, o crearse en un paso anterior; si no, reintento correctivo |

**Prerrequisito corregido:** el temario y el manual **no llegaban** al Writer. `LabBatchExpander`
no los recibía y no los añadía al lote, así que la verificación B1 era imposible y el manual solo
llegaba por el atajo de `additional_requirements` del plan (recortado y mal etiquetado). Ahora la
máquina de estados se los pasa y el expansor los reenvía en cada lote.

**Composición de las dos capas:** el plan es fuente para B1, pero solo para sus referentes
verificados. Los que A1 marcó como no declarados se excluyen del texto del plan antes de usarlo
como fuente; de lo contrario el laboratorio repetiría el dato inventado y B1 lo daría por bueno.

**Modo de aplicación:** reintento correctivo automático y registro, **no bloqueo**. Es
deliberado: bloquear con una heurística nueva y sin datos de precisión es lo que dejó la puerta
actual en «no bloquea nada». El criterio para pasar a ERROR es tener **0 falsos positivos** sobre
varias ejecuciones reales.

**Medición real de precisión** (plan y laboratorios ya generados del 16/10/2026, manual de
231.744 caracteres):

| Verificación | Resultado |
|---|---|
| A1 sobre el plan real | 21 referentes de fichero, **8 marcados y los 8 verificados uno a uno** como ausentes del temario y del manual (0 falsos positivos) |
| B1 sobre los dos laboratorios reales | 12 referentes reconocidos, **0 violaciones** (0 falsos positivos) |

Pruebas: `CG-Backend/test_referent_check.py` (23 pruebas). Incluyen el **camino vivo**: el
expansor ejecutado con S3 simulado (la prueba que habría cazado la falta de propagación), el
prompt compacto real y el handler completo del Writer con reintento correctivo observable.

---

## 12. Evidencia de fabricación: experimento natural (16/10/2026)

El mismo curso (`outline-forecasting-aplicado-logistica`) existe en el bucket generado dos veces,
en dos ejecuciones distintas. Cada ejecución inventa su propio juego de ficheros y carpetas, y
**ninguno de los dos aparece en el temario (14.044 caracteres) ni en el manual (231.744)**:

| Generación 260806 | Generación 261015 |
|---|---|
| `Practica1_Demanda_SKU.xlsx` | `Practica1_MAPE_SKU.xlsx` |
| `Practica2_Demanda_Cruda.csv` | `Demanda_Historica.xlsx` |
| `Practica2_Catalogo_Productos.xlsx` | `Catalogo_Productos.xlsx` |
| `Practica3_Dashboard_Monitoreo.pbix` | `Inventario_Bodega.xlsx` |
| `C:\ForecLog\Practicas\P1\` … `P4\` | `C:\Forecasting_Logistica\` |

**Nombres de fichero en común entre las dos ejecuciones: 0.** Es un experimento natural: la
varianza demuestra que el dato no se deriva de las fuentes, se inventa. Y explica por sí solo por
qué el instructor tiene que corregir más del 75 % de los laboratorios: cada curso llega con una
ficción administrativa distinta.

## 13. Calibración obligatoria antes de bloquear

Medición sobre las 169 carpetas de curso del bucket: **solo 1 conserva el manual** extraído
(`manuals/extracted_manual_text.txt`). Es decir, el caso normal en producción es **temario sin
manual**, y en ese régimen el modelo *tiene* que nombrar ficheros que nadie declara si el
ejercicio los necesita.

Consecuencia práctica: con A1/B1 en modo informe el coste es aceptable; **en modo bloqueo, A1
dispararía en casi todos los cursos** (en la muestra sin manual: 1.758 referentes marcados en 125
de 163 proyectos; B1, 4.794 en 124 de 1.240 laboratorios), y buena parte podría ser legítima a
juicio del instructor. Por eso:

1. Antes de endurecer, hay que revisar una muestra de esas violaciones y separar «inventado» de
   «razonable pero no declarado».
2. La regla de tres niveles ya da la salida correcta para el caso legítimo: describir el fichero
   funcionalmente o marcarlo `[POR CONFIRMAR]`, en vez de bautizarlo. El reintento correctivo
   aplica exactamente eso.
3. La decisión de pasar a ERROR sigue siendo **0 falsos positivos sobre ejecuciones reales**, no
   una fecha.


