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

---

## 14. Calibración ejecutada (16/10/2026): por qué A1/B1 **no** pasan a ERROR

Se ejecutó el punto 1 de §13 sobre el corpus real. La respuesta es que **la mayoría de lo que
marcan A1 y B1 no son defectos del curso: son artefactos del propio detector**. Por eso se
mantiene el modo reintento + registro y no se endurece.

### 14.1 Método

- **Censo** sobre `corpus_a1_b1.json` (164 proyectos, 1.244 laboratorios ya generados), aplicando
  el módulo desplegado. Artefacto auditado: los laboratorios y planes **reales** del bucket.
- **Revisión con contexto** de una muestra aleatoria (semilla fija 20261016) de **80 marcados**
  (60 de B1 + 20 de A1): para cada uno se trajo de S3 el laboratorio o el plan y se leyó ±300
  caracteres alrededor del referente. El valor suelto no basta para juzgar; el contexto sí.

### 14.2 Censo

| Métrica | Valor |
|---|---|
| Proyectos en el corpus | 164 (solo **1** con manual) |
| Laboratorios revisados | 1.244 |
| Referentes marcados | **6.567** (A1 1.773, B1 4.794) |
| Proyectos con ≥1 marcado | **160 / 164 (97,6 %)** |
| Laboratorios con ≥1 marcado | **847 / 1.244 (68,1 %)** |

Si A1/B1 fuesen ERROR hoy, **bloquearían el 97,6 % de los cursos reales**. Eso, por sí solo,
descarta el modo bloqueo con la heurística actual.

### 14.3 Revisión con contexto: 78 de 80 son falso positivo

| Origen | Revisados | Falso positivo | Real (fichero de entrada no aportado) |
|---|---|---|---|
| B1 (laboratorios) | 60 | **60** | 0 |
| A1 (plan) | 20 | **18** | 2 |
| **Total** | **80** | **78 (97,5 %)** | **2 (2,5 %)** |

Los 2 casos reales son de la clase que la verificación sí busca: un fichero de **entrada** que el
alumno debe aportar y que ninguna fuente declara (`perfiles_roles_planta.docx`, «disponible en
OneDrive»; `mensajes_bancarios.csv`, «archivo de entrada por defecto»).

### 14.4 Taxonomía del falso positivo (con ejemplo real verificado)

**① La extensión no está anclada a fin de palabra** (defecto del regex, reproducible sobre el
módulo desplegado). Cualquier expresión con puntos cuya última pieza empiece por una extensión
conocida genera un «fichero» que no existe:

| Texto real del laboratorio | Referente extraído |
|---|---|
| `df.shape[0]` | `df.sh` |
| `matplotlib.pyplot` | `matplotlib.py` |
| `kpis.show(truncate=False)` | `kpis.sh` |
| `X_val_prep.shape` | `X_val_prep.sh` |
| `robot.language-server.python` | `robot.language-server.py` |
| `transaction.state.log.replication.factor` | `transaction.state.log` |
| `parse.key=true` | `parse.key` |
| `hashlib.md5(...)` | `hashlib.md` |
| `Object.keys(...)` | `Object.key` |

**② Identificadores punteados y claves de configuración tratados como fichas.** `math.log`,
`android.util.Log`, `pyspark.sql`, `wwv_flow.show`, `process.env.DB`, `APEX_ESCAPE.HTML`,
`/_cat/count` (API de Elasticsearch), `/components/schemas/ErrorResponse` (fragmento OpenAPI),
`/subscriptions/…/resourceGroups/…` (ID de recurso de Azure). El `re.IGNORECASE` lo agrava:
`.Log`, `.Sh`, `.JSON` casan como extensiones.

**③ Rutas de sistema y de plataforma** que existen en el entorno: `/dev/null` (240 apariciones),
`/bin/bash`, `/etc/*`, `/usr/*`, `/var/*`, `/lib/systemd/*`, `/mnt/*`, `/data/data/…`, sitios de
SharePoint, propiedades de Kafka. Representan ≥25 % del total y **no son material del curso**.

**④ Creación no detectada.** El laboratorio sí crea el fichero, pero por una vía que la ventana de
contexto no ve: `tee`, redirección `>`, `BACKUP … TO DISK`, `--report`/`--output` de Robot,
`Out-File`, `SPOOL`, `hostPath: DirectoryOrCreate`, `initContainer … > /html/index.html`,
`adb pull`, o un listado de «evidencias esperadas». Además, la lista de verbos omite conjugaciones
y sinónimos frecuentes: **«guarde», «creado», «almacena», «conserva»** no están, así que pasos que
claramente crean el fichero no lo blanquean.

**⑤ Ausencia deliberada.** Hay referentes que el laboratorio menciona justamente para decir que
**no** existen: `archivo_inexistente.json` (fixture para probar el manejo de errores),
`tailwind.config.js` («sin archivo `tailwind.config.js` clásico»), `secretos.db` (ejemplo de
*ruta de ataque*).

### 14.5 Decisión

- **No se pasa a ERROR.** La precisión medida es ~2,5 %; el criterio de §13 (0 falsos positivos)
  queda muy lejos. A1/B1 siguen en **reintento correctivo + registro**.
- El censo mecánico (42,9 % de falso positivo *evidente*) es un **límite inferior**: la revisión
  con contexto, que es la medida válida, lo eleva al 97,5 %.

### 14.6 Correcciones necesarias antes de reconsiderar el bloqueo

Ninguna cambia el temario ni el flujo de carga. Todas con prueba de camino vivo (M1) y
declaración de artefacto y contexto (M2):

1. **Anclar la extensión** a un límite de palabra (fin de token: no seguida de letra), para que
   `df.shape` deje de producir `df.sh`.
2. **Excluir identificadores punteados y claves de configuración**: exigir extensión en minúscula
   en el original y descartar tokens que sean rutas de namespace (`a.b.c` sin `/` ni `\` y sin
   verbo de fichero alrededor) o propiedades (`clave=valor`).
3. **Neutralizar rutas de sistema y de plataforma** (lista de prefijos: `/etc/`, `/usr/`, `/dev/`,
   `/bin/`, `/var/`, `/lib/`, `/opt/`, `/mnt/`, `/data/`, `C:\Users\`, …) y rutas que no son
   locales (ID de recurso, ruta de API).
4. **Ampliar la detección de creación**: más verbos y conjugaciones, y aceptar el contexto de todo
   el paso (con las salvaguardas para que no quede vacua).
5. **Reconocer la mención de ausencia** («no existe», «sin archivo», «si falta»).

Mientras esas cinco correcciones no estén hechas y **re-medidas sobre el corpus con 0 falsos
positivos**, el bloqueo no aporta: cambiaría un aviso ignorable por un atasco en casi todos los
cursos.

## 15. Segunda calibración (19/10/2026): separar «entrada del curso» de «salida del laboratorio»

Las cinco correcciones de §14.6 se implementaron y se midieron. La reducción de ruido fue grande,
pero al revisar la muestra con contexto apareció un hecho que cambia el diseño: **la mayoría de lo
que queda no son datos inventados, son ficheros que el propio laboratorio crea o que pertenecen al
proyecto**. Un detector que no distingue «el curso aporta este fichero» de «el estudiante produce
este fichero» no puede bloquear, y tampoco debería reintentar sobre todo.

### 15.1 Correcciones añadidas en esta iteración

Ninguna toca el temario, el flujo de carga ni los documentos opcionales.

| # | Corrección | Qué falsos positivos elimina |
|---|---|---|
| 6 | **Neutralizar URIs de nube** (`gs://`, `s3://`, `dbfs:/`) antes de extraer rutas | rutas de almacenamiento que no son del alumno |
| 7 | **Marcadores de API/plataforma** (`/aws/`, `/_snapshot/`, `/_slm/`, `/_security/`, `/_ilm/`, `/_ingest/`, `/_nodes/`, `/actuator/`, `/users/v1/`, `/me/`, `/drive/`) | endpoints de Elasticsearch, Spring, VAmPI y Graph |
| 8 | **Creación por redirección u opción**: `>` / `>>` / `cat >` / `\| tee`, `--output`, `--log`, `--report`, `-OutFile`, `-DestinationPath`, `SPOOL`, `TO DISK`, `Expand-Archive`, `to_csv`, `makedirs`, `-out`, `-outform` | comandos que crean el fichero y se leían como «uso» |
| 9 | **Todas las apariciones** de un referente (`deduplicar=False` en la auditoría de laboratorio) | un fichero nombrado antes en una tabla y creado después |
| 10 | **Reglas estructurales**: árboles de entregables (`├──`), líneas de `import`/`require`/`href`/`Resource`, claves YAML al inicio de línea, andamiaje (`ng new`, `ng generate`, `dotnet new`, `git clone`…), citas (`[Fuente …]`), bloques de **salida esperada**, marcadores en mayúsculas con punto (`[PEGAR_AQUÍ_…XLSX]`), secuencias de escape (`\\nVariance`) | ficheros del proyecto, del andamiaje, de herramientas y listados de salida |
| 11 | **`expected_outcomes` nunca dispara reintento**: ese campo describe lo que el estudiante **produce** | entregables declarados como resultado |

### 15.2 Resultado sobre el corpus (164 proyectos, 1.244 laboratorios)

| Ámbito | Antes | Ahora | Variación |
|---|---:|---:|---:|
| Referentes marcados (A1+B1) | 6.567 | **1.878** | −71,4 % |
| A1 (plan) | 1.773 | 1.313 | −26 % |
| B1 (laboratorio) | 4.794 | **565** | −88 % |
| **Alta confianza** (dispara reintento) | 6.567 | **151** | **−97,7 %** |

El curso que **sí conserva el manual** —la única medición justa, porque el manual declara los
ficheros que el temario no nombra— mantiene sus **15 referentes A1**, de los cuales **4 son de alta
confianza**: los inventos reales siguen detectándose, no se han perdido verdaderos positivos.

### 15.3 La clase de alta confianza

`confianza = "alta"` significa: el contexto presenta el fichero como **aportado por el curso**
(«archivos de práctica proporcionados por el instructor», «cargados en OneDrive», «almacenados en
SharePoint», «el estudiante recibe el dataset», «descargados desde…», «asegúrate de tener…»,
«abre el archivo X»), **y** no hay un verbo de edición que indique que el fichero ya existe en el
proyecto («reemplace», «modifique», «actualice»).

Precisión medida sobre una muestra aleatoria de 25 A1 + 25 B1 de alta confianza, revisada con el
texto real de S3:

| Ámbito | Aciertos reales | Precisión |
|---|---:|---:|
| A1 alta | 19–21 de 25 | **≈ 80 %** |
| B1 alta | 5–6 de 25 | **≈ 20 %** |

Los falsos positivos residuales de A1 son casi todos entregables (`El producto final es…`,
`generados en este laboratorio`) y ya se excluyen. Los de B1 son ficheros del proyecto, artefactos
de herramientas y rutas de entorno: **no se pueden separar por el nombre del fichero**, hace falta
el contexto de conjunto (Fase 2).

### 15.4 Decisión

1. **A1 y B1 no pasan a `ERROR`.** El criterio era 0 falsos positivos sobre cursos reales y no se
   cumple.
2. El **reintento correctivo se limita a la clase de alta confianza** y el informe sigue
   registrando **todas** las violaciones, con su confianza, en
   `{project_folder}/validation/referential-integrity.json` y
   `{project_folder}/validation/labs-referential-integrity.json`.
3. El **mensaje correctivo es no destructivo**: pide marcar `[POR CONFIRMAR]`, definir el paso que
   crea el fichero o sustituirlo por una descripción funcional, y prohíbe explícitamente eliminar
   entregables del estudiante. Así, un falso positivo no puede borrar contenido legítimo.
4. Existe un **interruptor operativo** `REFERENTIAL_RETRY=0` que deja la verificación en solo
   registro, sin reintento ni cambio de contenido, sin necesidad de desplegar código.
5. El plan es fuente para B1 **solo para sus referentes verificados**: se excluyen los marcados por
   A1 como de alta confianza; los de baja confianza siguen contando como fuente porque son
   entregables o directorios que el plan introduce legítimamente.

### 15.5 Lo que no se puede resolver con nombres de fichero

La muestra lo deja claro. Para bajar de ≈ 80 % / ≈ 20 % a 0 falsos positivos hacen falta las
verificaciones de la Fase 2, que necesitan el **conjunto** de laboratorios y el contexto del curso:

- **B2** (referencias a laboratorios posteriores) y **B3** (ficheros creados en laboratorios
  anteriores) — hoy B1 solo ve un laboratorio aislado.
- **B5/B6** (duración y coherencia del conjunto).
- **C1** (liveness de enlaces) para las URL, hoy fuera de alcance.

### 15.6 Reproducibilidad

Las mediciones se ejecutan con el módulo real del planner (no con una copia):

- `medir_corpus.py` — recorre los 164 proyectos del bucket, separa con/sin manual y desglosa por
  confianza.
- `revisar_muestra.py` — muestra aleatoria de violaciones con el texto real alrededor.
- `revisar_alta.py` — lo mismo, restringido a la clase de alta confianza (la que dispara reintento).

Batería de pruebas: `CG-Backend/test_referent_check.py`, **49/49 en verde**, incluyendo caminos
vivos del planner y del writer, controles negativos e identidad byte a byte de las dos copias del
módulo.

---

## 16. Fase 2 (20/10/2026): B2 y el cierre entre laboratorios

### 16.1 Qué se añadió

Todo vive en `referent_check.py` (misma copia byte a byte en planner y writer) y se ejecuta en el
**Writer**, que es el único punto donde ya existen los laboratorios anteriores:

| Pieza | Qué hace |
|---|---|
| `referentes_creados(texto)` | Claves de los referentes que el texto **crea** (verbo, opción de salida, redirección, andamiaje). No legitima una mera mención. |
| `salidas_de_laboratorios(plan)` | `expected_outcomes` de cada laboratorio, extraídos como referentes. Es la definición de «salida» que usa B2. |
| `referencias_a_labs_posteriores(texto, posición, orden)` | Menciones explícitas a un laboratorio posterior, por número o como «siguiente/próxima práctica». |
| `auditar_laboratorio(..., creados_antes, salidas_posteriores, referencias_posteriores)` | B1 + B2 + B3c en una pasada, con el orden del plan y los referentes creados por los laboratorios previos. |
| `_referentes_creados_en_labs_anteriores(...)` (Writer) | Lee de S3 los laboratorios ya escritos. Es viable porque los lotes son secuenciales y de un laboratorio (`MaxConcurrency: 1`). |

Además:

- El **contexto se recorta al paso**. Antes, la ventana de ±260 caracteres cruzaba al paso siguiente
  y un «guarde el resultado» exculpaba un «abra el archivo» del paso actual: la comprobación se
  volvía vacua justo en los laboratorios con varios pasos. Es un requisito de B3c, porque
  `referentes_creados` hereda la misma detección de creación.
- Se corrigió un fallo latente: el Writer decidía la continuidad con `idx > 1` sobre la lista
  **filtrada por lote**. Como el lote trae un solo laboratorio, `idx` valía siempre 1 y
  `previous_lab_context` nunca se cargaba. Ahora la posición se calcula sobre el plan completo.

### 16.2 Nomenclatura

La tabla de §4 llama **B3** a «todo entregable declarado en el plan aparece producido en su
laboratorio». Lo implementado aquí es la **mitad entre laboratorios de B1**: un fichero creado en un
laboratorio anterior es legítimo en el actual. Para no colisionar, este documento llama:

- **B3c** (cierre) a lo implementado;
- **B3p** (producido) a lo de §4, que sigue pendiente.

### 16.3 Medición sobre el corpus real (169 proyectos, 1.236 laboratorios)

Medición con el **flujo de producción**: el plan se filtra como en el Writer (se quitan los
referentes que A1 marcó de alta), los laboratorios se recorren en el orden del plan y se acumulan
los creados. La columna «efecto de B3c» es el contrafactual sin `creados_antes`.

| Clase | Fase 1 | Fase 2 | Comentario |
|---|---|---|---|
| A1 marcados | 1.313 | 1.313 | sin cambios |
| B1 marcados | 565 | **601** | +74 por el recorte al paso; −38 que evita B3c |
| B1 de alta | 29 | **33** | el recorte añade 6; dos desaparecen |
| B2 marcados | — | **10** | dependencia de una salida posterior |
| B2 de alta | — | **0** | ninguno dispara reintento |
| Menciones de hoja de ruta | — | 858 | van aparte; no cuentan para `ok` |

La clase de reintento queda en **155** (122 de A1 + 33 de B1). B2 no aporta ninguno.

### 16.4 Lo que la medición desmiente

La hipótesis de §15.5 era que los falsos positivos residuales de B1 se resolverían con el contexto
del conjunto. **No es así.** B3c evita 38 marcas, pero **ninguna de alta confianza**: los 33 que
disparan reintento no los creó ningún laboratorio anterior. Al revisarlos, siguen siendo las mismas
tres familias:

- **artefactos de herramientas** (`product-list.component.ts`, `main-a1b2c3d4.js`, `plotly.js`,
  `todo.flaky.spec.ts`, `values.yaml`);
- **rutas de plataforma o de API** (`/Library/Android/...`, `/datastore/...`, `/products/p-1`,
  `/../etc/passwd`, `/auth/login`);
- **entregables con nombre propio** que el laboratorio produce con una frase que el extractor no
  reconoce como creación (`Lab04_Plan_Cierre_Fiscal.xlsx`).

Las dos primeras familias no se separan por contexto entre laboratorios: se separan **por
estructura** (prefijos de build, extensiones generadas, espacios de nombres de API). La tercera
necesita más verbos o más formas de nombrar un entregable. Es una corrección de extractor, no de
arquitectura.

### 16.5 Decisión

1. **B2 no dispara reintento.** De los 10 casos, la revisión manual da ~7 plausibles y 3 falsos
   positivos (`Node.js`, `/auth/login`, `values.yaml`). El criterio para pasar a `ERROR` es 0 falsos
   positivos sobre cursos reales, y no se cumple.
2. Las **menciones de hoja de ruta** no son violaciones: se guardan en
   `menciones_posteriores` dentro del mismo informe y no afectan a `ok`. Sin esa separación, B2
   habría añadido 858 «violaciones» que en su mayoría son frases pedagógicas normales.
3. **B3c se queda**: reduce ruido sin coste de precisión y deja el informe más cerca de la realidad
   del curso.
4. **A1 y B1 siguen sin ser `ERROR`.** Fase 2 no cambió la clase de reintento; solo la explicó
   mejor.
5. Lo que queda de la fase 2 original: **B5/B6** (duración y coherencia del conjunto), que viven en
   el planner, y **B3p** (entregable producido). La familia «artefacto de herramienta» merece una
   regla propia antes que B5/B6 si el objetivo es bajar los falsos positivos.

### 16.6 Reproducibilidad

- `medir_y_contexto.py` — mismo corpus, flujo de producción y volcado del contexto (±220
  caracteres) de cada B1 de alta confianza. Escribe `corpus.json` y `contexto_alta.txt`.
  **Sustituye** al `medir_corpus_fase2.py` de esta sección, que vivía en un directorio temporal
  que se vació; el «antes» se mide con `medir_antes.py`, que importa el módulo de `HEAD` y escribe
  `corpus_antes.json`. Así la comparación es sobre el mismo flujo, no sobre scripts distintos.
- `revisar_proyecto.py <proyecto>` — auditoría de un proyecto concreto; sirve para verificar un
  caso sin repetir el corpus.
- Batería: `CG-Backend/test_referent_check.py`, **62/62 en verde**, con caminos vivos nuevos:
  el Writer acepta un fichero creado en el laboratorio anterior (B3c), reintenta cuando el
  laboratorio depende de la salida de uno posterior (B2) y registra sin reintentar con
  `REFERENTIAL_RETRY=0`.


## 17. Fase 2.1 (21/10/2026): artefactos de herramienta y rutas relativas

### 17.1 El diagnóstico de §16.4 era incompleto

Se revisaron los 33 casos de alta confianza **con su contexto real** (±220 caracteres del
laboratorio escrito, no del prompt ni del fuente). El resultado desmintió la hipótesis de trabajo:
la mayoría no eran «artefactos de herramienta» sino **rutas relativas con directorio** que el
extractor no veía:

```
cat > assets/mock.json                 → no se extraía «assets/mock.json»
src/app/…/product-list.component.ts    → no se extraía la ruta
tests/e2e/todo.flaky.spec.ts           → ídem
```

La causa es concreta: `_FICHERO_RE` no admite `/` en el nombre y `_RUTA_UNIX_RE` exige `/` inicial.
Una ruta relativa con directorio no la capturaba ninguna regla. Consecuencia: **el paso que crea el
fichero era invisible**, y solo quedaba la mención posterior, que parecía un fichero inventado.

Es la diferencia entre medir el prompt y medir la salida: sobre el texto del plan el diagnóstico
«artefacto» era plausible; sobre el laboratorio generado, la causa dominante era otra.

### 17.2 Qué se añadió

1. **`_RUTA_RELATIVA_RE`** (dos o más segmentos y extensión) → tipo `ruta`. Es la corrección de
   causa raíz. También permite que un paso `ng generate component …` o `mkdir -p js assets` se
   relacione con la mención posterior del mismo fichero.
2. **`_es_artefacto_de_herramienta`**, aplicada en la extracción:
   - directorios de build (`dist/`, `build/`, `out/`, `target/`, `node_modules/`, `.angular/`,
     `.next/`, `.nuxt/`, `coverage/`, `__pycache__/`, `.venv/`, `.gradle/`, `vendor/`, `obj/`);
   - andamiaje de framework (`resources/js/`, `resources/css/`, `resources/views/`);
   - sufijos que añade un generador (`.component.ts`, `.service.ts`, `.module.ts`, `.spec.ts`,
     `.d.ts`, `.guard.ts`, `.directive.ts`, `.pipe.ts`, `.resolver.ts`, `.routes.ts`, `.g.dart`,
     `.generated.ts`, `.designer.cs`, `.pb.go`, `.pb.ts`, `.min.js`, `.min.css`, `.map`,
     `.report.json`, `.report.html`);
   - **logs y temporales** (`.log`, `.tmp`): los produce la ejecución, nunca los aporta el curso;
   - bundle con hash de contenido (`main-a1b2c3d4.js`);
   - bibliotecas citadas por su nombre de fichero (`plotly.js`, `Node.js`, `jquery.js`…);
   - ficheros de un chart de Helm (`Chart.yaml`, `values.yaml`, `chart.lock`);
   - traversal de directorios (`/../`).
3. **`_es_ejemplo`**: un nombre citado como ejemplo («ej: tests/Login.robot», «normalmente
   `src/router/index.ts`») no afirma que el curso lo aporte. Se mira solo lo inmediatamente
   anterior (40 caracteres) y, para las alternativas («`a` o `b`»), hasta 120 caracteres con la
   condición de que entre la marca y el nombre no haya un verbo de entrada: «por ejemplo, abra el
   archivo X» sigue contando como entrada.
4. **Retro-referencias de creación en pasado** («la copia que creaste en la configuración
   inicial», «el informe que generaste»): el fichero existe porque un paso anterior lo produjo.
5. **Rutas de plataforma**: se añaden `/Library/`, `/System/`, `/Applications/`, `/datastore/`,
   `/shared_prefs/` a los prefijos excluidos y `/products/` a los segmentos de API.
6. **Script con shebang**: un bloque que abre con `#!` define el script que nombra su comentario
   de cabecera (`# monitor_rebalance.sh`), aunque el laboratorio no use `cat >`.
7. **Clave de configuración YAML/INI** (`ssl.key: certs/es01.key`): el valor de una clave no es
   una entrada del curso.

### 17.3 Medición A/B sobre el mismo flujo y el mismo corpus

168 proyectos, 1.244 laboratorios, 1 con manual extraído. «Antes» = módulo de `HEAD` importado por
`medir_antes.py`; «después» = el módulo actual. Mismo corpus, misma iteración, mismo orden.

| Clase | Antes | Después |
|---|---|---|
| A1 marcados | 1.332 | 1.449 |
| A1 de alta | 122 | 119 |
| B1 marcados | 636 | 610 |
| **B1 de alta** | **34** | **17** |
| B2 marcados | 10 | 8 |
| B2 de alta | 0 | 0 |
| **Clase de reintento (alta)** | **156** | **136** |
| Menciones de hoja de ruta | 862 | 862 |

Lectura:

- **B1 de alta baja a la mitad** (34 → 17). La clase de reintento baja 20 marcas (−12,8 %).
- A1 **sube 117 marcas** porque ahora ve rutas relativas que antes no existían para el extractor;
  de alta baja 3. Es el efecto esperado: más cobertura, misma precisión.
- B1 total baja aunque se extraen más referentes: las exclusiones quitan más de lo que la nueva
  extracción añade. El recorte al paso y B3c siguen aplicándose.

### 17.4 Qué queda en los 17

Revisados uno a uno con contexto:

- **11 son señal correcta**: material que el laboratorio dice aportar y el temario no declara.
  `licenses.txt` («proporcionado por el instructor»), `Politica_Vacaciones.pdf` (SharePoint del
  curso), `M2_DatosAuditoria_Ficticios.docx` («preparado por el instructor»),
  `Ventas_MultiRegional_2024.xlsx` («repositorio del taller»), `/Modulo1/Normativos/…`,
  `BA_05-00-01_…docx` («carpeta de fuentes»), `lab_02_02_trend_analysis.ipynb` («notebook
  pre-estructurado»), `Lab02_Claves_Respuesta.pdf`, `REFERENCIA-NORMAS-EHS.docx`,
  `Lab04_Plan_Cierre_Fiscal.xlsx` y `Lab02_Reporte_Automatizado.xlsx` (entregable posterior citado
  al final del laboratorio 1 como si ya existiera).
  Es el hallazgo del informe: **el temario no declara los materiales**. No se exculpan: si se
  exculpa «lo proporciona el instructor», B1 deja de detectar el material inventado, porque el
  propio modelo puede escribir esa frase.
- **6 son residuales**: `politica_vacaciones_parte1.txt` y `…parte2.txt` (bloque que ilustra un
  «divídalo en secciones»), `C:\users.txt` y `./openai_key.txt` (entradas de un script de ejemplo),
  `D:\vcsa-ui-installer\win32\` (medio de instalación montado desde el ISO) y
  `Datos_Financieros_Q4.xlsx` («que está en mi OneDrive», nota de resolución de problemas).
  Los seis comparten que el fichero lo pone el **entorno o el alumno**, no el curso.

### 17.5 Decisión

1. **Se mantiene reintento + registro**, no bloqueo. Seis residuales sobre 1.244 laboratorios no
   cumplen el criterio de 0 falsos positivos, pero ya no son la familia dominante: 11 de 17 son
   señal que el informe pide corregir en el temario.
2. **No se exculpa «proporcionado por el instructor».** Es exactamente el dato que el informe
   señala como ausente en el temario.
3. La familia «entorno/medio de instalación» se abordará, si vuelve a aparecer, con el contexto de
   montaje (ISO, unidad virtual), no con una lista de rutas.
4. Siguiente: **B5/B6** (duración y coherencia del conjunto) en el planner y **B3p** (entregable
   declarado que aparece producido).

### 17.6 Reproducibilidad

- `medir_y_contexto.py`, `medir_antes.py`, `revisar_proyecto.py` y `corpus*.json` descritos en
  §16.6.
- Batería: **77/77 en verde**, con pruebas nuevas de camino vivo para: ruta relativa que se crea en
  el propio laboratorio, ruta relativa sin creación que sí se marca, artefactos de build con hash,
  sufijos generados, logs e informes de herramienta, andamiaje de Laravel, nombres de ejemplo
  (incluida la alternativa «`a` o `b`»), shebang y retro-referencia en pasado.
- Verificación puntual sobre el corpus: `260623-COP_CHAT_CONTR-Priv-` pasa de marcar
  `M1_Catalogo_Cuentas_TRABAJO.xlsx` a no marcar nada, y `260820-vue-intermedio` deja de marcar
  `src/router/index.ts`.



## 18. Fase 2.2 (21/10/2026): B6 (duración) y B5 (requisitos técnicos)

### 18.1 Dónde vive cada verificación: el plan no tiene pasos

§16.5 daba por supuesto que B5/B6 vivirían «en el planner». La comprobación del esquema real lo
desmiente: `lab_plans` trae `estimated_duration`, `objectives`, `scope` y `key_technologies`, pero
**no trae pasos**. Comprobar B6 en el planner sería comprobar una duración contra un plan de pasos
que no existe: una verificación vacua, justo lo que M1 prohíbe.

Las dos verificaciones se implementan en el **Writer**, que es el único artefacto donde conviven el
laboratorio escrito, sus pasos y los requisitos del plan:

| Verificación | Artefacto sobre el que corre | Contexto que necesita |
|---|---|---|
| **B6** | el laboratorio escrito | `estimated_duration` del plan, o la duración que el propio laboratorio declara |
| **B5** | el laboratorio escrito | `software_requirements` y `hardware_requirements` del plan |

Las dos son **deterministas y de stdlib**: no hay modelo en el bucle.

### 18.2 B6: duración declarada contra trabajo real

Unidad de medida robusta, medida en lugar de supuesta. Contar **líneas** dentro de bloques de código
infla la carga porque mezcla comandos con salidas (`1678` «comandos» en un laboratorio de 45 minutos
eran, en su mayoría, volcados de pantalla). La unidad que se usa es:

- **paso con acción**: un `### Paso` que contiene al menos un bloque de shell o de un lenguaje que el
  alumno escribe;
- **bloque de acción**: un bloque de shell o de un lenguaje de escritura. Los de salida (`text`,
  `log`, `diff`, `csv`) **no cuentan**: no cuestan tiempo de acción.

Un bloque de 40 líneas cuenta como uno: mide trabajo de ejecución, no de tecleo, y evita depender de
una estimación de velocidad de escritura.

Se marca cuando se incumplen **las dos** condiciones: `duración / pasos_con_acción < 2` **y**
`duración / bloques < 0,75` (un bloque cada 80 segundos). El doble umbral es lo que hace que la
señal sea limpia: la primera condición sola marca laboratorios cortos legítimos; la segunda sola,
laboratorios con muchos bloques pequeños.

Calibración sobre **1.294 laboratorios reales** (todos con plan; 1.259 con duración usable; 226 la
declaran en sus metadatos y 223 coinciden con el plan, el 98,7 %):

| | Valor |
|---|---|
| p05 de minutos por paso con acción | 2,5 |
| p05 de minutos por bloque | 0,4 |
| Marcados por la regla | **14 (1,08 %)** |

Los 14 se revisaron uno a uno; ninguno es un falso positivo:

- `260924-Temario-fortinet-…-cybersecurity` instala **Kali Linux en una máquina virtual** en 15
  minutos (8 pasos, 71 bloques: 12,6 s por bloque);
- `260728-angular-essentials` crea el proyecto con `ng new`, genera componentes y escribe **35 líneas
  de HTML y 77 de CSS** en 12 minutos;
- `261008-LFS158` declara 5 minutos para 4 pasos con acción y **31 bloques**;
- `260617-TPRACT-DES-COPCHAT` hace escribir ~150 líneas de Python en 10 minutos.

**Corrección: no destructiva y sin tocar la duración.** El mensaje pide reducir pasos de exploración
y bloques prescindibles, conservar **todos** los entregables y los pasos de verificación, y no
cambiar la duración del plan ni el número de laboratorio. La duración es contrato (A3 la suma); lo
que se corrige es el volumen.

### 18.3 B5: requisitos que el laboratorio exige y el plan no declara

Se comprueban tres familias —sistema operativo, herramienta con versión y magnitud de hardware— y
solo en **prosa**: una salida de `free -h` o un `docker run -m 4g` no es un requisito del alumno. La
ventana de decisión excluye, además, las especificaciones de la máquina virtual, el contenedor, la
PDB o la instancia del ejercicio, y las menciones ilustrativas o de interfaz.

La distinción que importa es entre dos cosas que la primera medición confundía:

- **Contradicción** (`confianza: alta`, reintenta): el plan declara un sistema operativo o una
  versión para una herramienta y el laboratorio dice **otro**.
- **Ampliación** (`confianza: baja`, solo registro): el laboratorio exige una magnitud o un sistema
  que el plan no menciona en absoluto.

Medición de la primera versión (comparación literal de la frase declarada): **74 laboratorios**
marcados y prácticamente todos de la sección de entorno del propio laboratorio — ruido. Se
corrigieron tres causas:

1. **Magnitud, no frase**: «Memoria: 16 GB» cubre «16 GB de RAM»; se compara número + unidad.
2. **Familias de sistema operativo**: pedir Ubuntu cuando el plan declara Linux **no** lo contradice,
   y Windows Server es Windows.
3. **Homónimos y etiquetas**: `IOS` a secas suele ser el IOS de Cisco, y «Tool Windows» es una
   etiqueta de interfaz, no un sistema operativo. La exclusión de menciones ilustrativas cubre
   además «un cliente ssh (como Putty o terminal de macOS/Linux)» y «`c:/...` (Windows) o `~/...`
   (macOS)».

Resultado sobre los mismos 1.294 laboratorios:

| Clase | Antes (literal) | Después |
|---|---|---|
| Contradicciones (alta, reintenta) | 20 con 3 falsos positivos | **0** |
| Ampliaciones (baja, solo registro) | — | **63 (4,87 %)**: 56 de hardware, 23 de sistema operativo |

Las tres contradicciones que quedaban eran todas falsas: dos alternativas ilustrativas y una
etiqueta de interfaz. Tras la corrección no queda **ninguna**, así que la clase de reintento de B5 no
tiene falsos positivos observados; aun así, al no haber tampoco ningún caso real, la clase está
**sin validar en producción**: su primer caso real hay que mirarlo antes de confiar en ella.

La ampliación es, en cambio, señal de plantilla: 56 de los 63 son laboratorios que piden una cantidad
de RAM, disco o núcleos que el plan no declara. No se reintenta porque la sección de entorno es
legítima en muchos contextos; se registra para medirla.

### 18.4 Interruptores y artefacto

| Interruptor | Efecto |
|---|---|
| `REFERENTIAL_RETRY=0` | B1/B2 quedan en solo registro |
| `DURATION_RETRY=0` | B6 queda en solo registro |
| `REQUIREMENTS_RETRY=0` | B5 (contradicciones) queda en solo registro |

`{project_folder}/validation/labs-referential-integrity.json` pasa a `check: "B1+B2+B5+B6"` e
incluye `total_b5`, `total_b6`, `total_alta_confianza` y `ok_alta_confianza`. `ok` sigue significando
«ninguna violación de ninguna clase»; `ok_alta_confianza` separa la clase que dispara reintento, para
que una ampliación de hardware no haga parecer roto un curso.

### 18.5 Decisión

1. **B6 se queda con reintento**: 14 casos en 1.294, los 14 revisados y ninguno falso. Cumple el
   criterio de «0 falsos positivos sobre cursos reales» que §14 exige para actuar.
2. **B5 no aporta casos de contradicción hoy.** Se deja en el código con `alta` porque la regla es
   inequívoca cuando aparece, pero no hay evidencia real que la respalde; la ampliación se registra
   con `baja` y no toca el contenido.
3. **La corrección de B6 no puede borrar entregables** ni cambiar la duración del plan: el mensaje lo
   prohíbe explícitamente, igual que en B1.
4. Siguiente: **B3p** (entregable declarado que aparece producido) y, después, la fase 3 (versiones
   y entidades con nombre) y **C1** (liveness de enlaces).

### 18.6 Reproducibilidad

- `calibrar_b6_plan.py` — distribución de unidades de trabajo y comparación del umbral simple con el
  doble.
- `calibrar_b5_unidades.py` y `calibrar_b5_tipos.py` — B5 por frase y por familias, con el contexto
  real de cada mención.
- `calibrar_b5b6_final.py` — **llama al módulo real** (`auditar_duracion`, `auditar_requisitos`) y
  reproduce las cifras de §18.2 y §18.3 sobre los 1.294 laboratorios.
- `ver_pasos.py` — volcado de los pasos y bloques de un laboratorio concreto (usado para revisar los
  14 de B6).
- Batería: **99/99 en verde**, con caminos vivos nuevos: el Writer reintenta por una duración
  imposible y por una contradicción de requisito, no reintenta por una ampliación de hardware, y
  ninguno de los dos reintentos ocurre con su interruptor apagado.

## 19. Fase 2.3 (21/10/2026): B3p, el entregable declarado que aparece producido

### 19.1 Qué se puede comprobar de verdad

`expected_outcomes` es **prosa**, no una lista de ficheros. En la muestra real conviven tres formas:

| Forma | Ejemplo | ¿Comprobable? |
|---|---|---|
| Nombra un fichero | «Archivo `data_transform.py` con al menos 6 funciones» | **sí**, determinista |
| Nombra un formato suelto | «Diagrama en formato `.drawio/.png`» | no: no hay nombre que buscar |
| Describe un resultado | «Scorecard funcional en Excel con 8 criterios ponderados» | no sin modelo (fase 3) |

B3p se limita a la primera forma. No es una limitación de implementación: cualquier otra exige
juzgar semántica, y eso pertenece a la fase 3 (entidades con nombre), no a un verificador
determinista.

### 19.2 Tres estados, no dos

La primera medición trataba «no lo veo crear» como «no lo produce» y marcaba el **50,5 %** de los
laboratorios (157 de 311). Al mirar los casos, la mitad eran frases de creación que el extractor no
reconoce — el mismo hueco que B1 documenta en §14. Se separan:

| Estado | Significado | Confianza |
|---|---|---|
| **Creado** | la detección de creación de B1 lo ve (`cat >`, andamiaje, opción de salida…) | — |
| **Mencionado, sin creación reconocida** | el nombre aparece en el texto; la frase no se reconoce | `baja` |
| **No mencionado** | el nombre no aparece ni una vez | `alta` |

Con esa separación, las menciones sin creación son **29 entregables en 12 laboratorios**: ruido de
extractor, se registra y no se reintenta.

### 19.3 Dos familias de falso positivo, corregidas antes de medir

1. **Alternativas** del plan: «Script de despliegue (`deploy.sh` o `deploy.ps1`)». Es **un**
   requisito, no dos. Se agrupan por el conector que hay entre los referentes (`o`, `u`, `/`); el
   grupo se satisface si se produce cualquiera.
2. **Entradas del curso**: «ejecutable con `robot --variable INPUT_FILE:orders.xlsx rpa.robot`» cita
   un fichero que el alumno **recibe**, no que produce. Una frase con marcadores de entrada
   (`entrada`, `input`, `--variable`, `proporcionad`, `recibida`) no declara entregables.

### 19.4 Medición sobre 1.294 laboratorios

| | Valor |
|---|---|
| Laboratorios con algún entregable nombrado | 311 |
| Entregables nombrados | 626 |
| Laboratorios con **omisión** (no mencionado) | **142 (11,0 %)** |
| Entregables omitidos | **211** |
| Entregables mencionados sin creación reconocida (baja) | 29 en 12 laboratorios |

Por extensión de lo omitido: `.py` 37, `.md` 29, `.docx` 29, `.txt` 17, `.png` 14, `.xlsx` 13,
`.json` 9, `.yaml` 8, `.sql` 8, `.ipynb` 7, `.pptx` 7.

Las dos familias de falso positivo que **quedan** y hay que resolver antes de encender el reintento:

- **salidas de herramienta** declaradas como entregable (`log.html`, `_web_verification.png`,
  capturas embebidas): el alumno no las produce a mano;
- **ficheros implícitos** (`README.md`): el plan los declara y el laboratorio los omite, pero no son
  el objeto de la práctica.

### 19.5 Decisión

1. **B3p se registra, no se reintenta**: `DELIVERABLES_RETRY` está **apagado por defecto** (al revés
   que B5/B6). El criterio es el de §14: 0 falsos positivos sobre cursos reales. Con 142 laboratorios
   y dos familias de FP sin resolver, no se cumple.
2. La omisión (alta) se informa como **alta** en el artefacto para poder medirla, pero no regenera.
   Así nadie paga una regeneración por un `README.md` implícito.
3. El mensaje correctivo, cuando se encienda, es **aditivo**: añade el paso que produce el entregable
   con el nombre exacto del plan y **no elimina** nada.
4. Para encenderlo: revisar los 211 omitidos, excluir las dos familias y volver a medir hasta 0 FP.

### 19.6 Reproducibilidad

- `calibrar_b3p.py` — primera pasada (50,5 % de ruido): enseñó que el detector de creación no basta.
- `calibrar_b3p_docs.py` — restringido a entregables documentales (40,1 %).
- `calibrar_b3p_split.py` — separa «no mencionado» de «mencionado sin creación».
- `ver_b3p.py` y `ver_b3p_frases.py` — contexto del laboratorio y frase del plan para cada caso.
- `calibrar_b3p_final.py` — **llama al módulo real** (`entregables_declarados`, `auditar_entregables`)
  y reproduce las cifras de §19.4.
- Batería: **99/99 en verde**, con caminos vivos nuevos: entregable declarado y no mencionado
  (alta), entregable creado (sin marca), entregable mencionado sin creación (baja), alternativa del
  plan y entrada del curso. El Writer no reintenta por defecto y sí con `DELIVERABLES_RETRY=1`.

## 20. Fase 3.1 (21/10/2026): A3, la duración que declara el temario

### 20.1 El contrato existe y se estaba perdiendo

Hasta aquí la duración del curso era «la que dijera el plan». No es así: el temario
**declara** la duración. En el 99 % de los temarios reales hay `course.total_duration_minutes`, y
cada `lab_activity` trae su `duration_minutes`:

```yaml
course:
  total_duration_minutes: 120
  modules:
    - title: Conmutación y Enrutamiento Básico
      lab_activities:
        - title: Inter-VLAN routing (router-on-a-stick) en Packet Tracer
          duration_minutes: 20
```

El planificador ya leía ese dato (`extract_all_labs` lo copia a `duration_minutes`), pero el
modelo podía reescribir `estimated_duration` en el plan y nadie lo contradecía. Es exactamente la
queja del informe: «si se indica en el temario que son 4 min debería aplicarse en consecuencia».

### 20.2 La corrección es determinista, no un reintento

`reconciliar_duraciones(plan, labs)` fija `estimated_duration` al valor del temario para cada
`lab_id` con contrato. No llama al modelo, no cuesta una regeneración y no puede inventar: si el
temario no declara la duración de un laboratorio, no se toca (`sin_contrato`).

Se ejecuta **antes de guardar** el plan, justo antes de la reauditoría de A1, para que lo que se
guarda —y lo que el Writer obedece— sea el contrato. `total_duration_minutes` se recalcula después,
así que el metadato y la suma quedan coherentes.

### 20.3 Medición sobre 164 proyectos con temario y plan

Con el extractor real (`extract_all_labs`), comparando en el mismo orden:

| Comprobación | Resultado |
|---|---|
| Proyectos cuyo plan **excede** el total del temario | **1** (180 vs 183 min, +1,7 %) |
| Proyectos con **número de prácticas** distinto | **10** |
| Pares temario/plan con **duración distinta** | **29 de 1.203 (2,4 %)** |

Los 29 se concentran en 9 proyectos y son desviaciones reales, no ruido:

- `260627-COP-CHAT-LEGAL`: temario 50/50/50/50 → plan 60/90/90/60 (inflado hasta +80 %);
- `260924-Temario-fortinet-…`: temario 18 → plan 40;
- `260226-Temario-desarrollo-con-oracle-apex`: temario 36/51/59/59/59 → plan 30 en todos;
- `260302 LINUX-ESSENTIALS LPI-010`: temario 168 → plan 252;
- los tres `…sql…snowflake`: temario 23/27/39/39 → plan 30.

Los 10 desajustes de número de prácticas son otra cosa: el plan agrupa actividades
(20 → 10, 15 → 7, 11 → 1). Es una decisión de alcance, no un error de dato, y recortar o duplicar
laboratorios no es determinista. Se **registra**, no se corrige.

### 20.4 Qué se guarda

- `metadata.duration_integrity` del plan: `suma_plan`, `total_curso`, `excede_total`,
  `labs_temario`, `labs_plan`, `faltan`, `sobran`, `ok`, `corregidos`, `con_contrato`,
  `sin_contrato`.
- `{project_folder}/validation/duration-integrity.json` con el mismo contenido, junto al informe
  de A1.

### 20.5 Decisión

1. **A3 se corrige, no se reintenta.** La duración del temario es un dato, no una opinión: se
   aplica. Es la primera verificación de la serie que pasa a corrección determinista en lugar de
   reintento correctivo.
2. **El número de prácticas se registra**, porque la corrección exigiría decidir alcance.
3. El `ok` de A3 queda en falso cuando el plan excede el curso o cuando faltan/sobran prácticas; hoy
   eso ocurre en 1 y 10 proyectos respectivamente, y se ve en el artefacto sin bloquear nada.
4. Siguiente: **A4** (los entregables del plan son los del temario) y **B4** (cifras y entidades
   estables entre laboratorios), que ya son semánticas y necesitan el mismo tratamiento de medición
   antes de actuar.

### 20.6 Reproducibilidad

- `calibrar_a3.py` — primera pasada con extracción propia (mostró el fallo: las actividades dentro
  de `lessons` no se contaban).
- `calibrar_a3_extractor.py` — **llama a `extract_all_labs`**, el extractor real, y compara en el
  mismo orden. Reproduce las cifras de §20.3.
- Batería: **107/107 en verde**, con siete pruebas nuevas de A3 y un camino vivo del planner: un
  temario de 18/22 minutos y un plan de 40/30 se guardan como 18/22, y
  `metadata.duration_integrity` recoge la corrección.

## 21. Fase 4 (22/10/2026): la puerta que por fin cierra

### 21.1 El diagnóstico

`ValidateLabContent` invocaba al validador con `fail_on_error: false`, guardaba
`$.lab_validation_result.all_valid` en el estado y **ningún `Choice` lo leía**. El paso siguiente
era siempre `InvokeLabGuideBuilder`, así que un laboratorio roto llegaba al libro del instructor
igual que uno bueno. Ese era el problema visible.

El problema real apareció al medirlo. Sobre los **1.294 laboratorios publicados**, con las reglas
tal como estaban:

| | Valor |
|---|---|
| Laboratorios inválidos | **849 (65,6 %)** |
| `heading_hierarchy` | 3.738 avisos en 550 laboratorios |
| `required_section` | 837 avisos en 501 laboratorios |
| `single_h1` | 620 avisos en 620 laboratorios |
| `lab_steps` | 426 avisos en 426 laboratorios |

Dos tercios del catálogo. Endurecer la puerta con esas reglas habría bloqueado cursos buenos, así
que lo primero no era cerrar la puerta: era comprobar **si medía el formato que THOR produce**.

### 21.2 Tres desalineaciones, cada una con su evidencia

1. **Un `#` dentro de un bloque de código no es un título.** `H1_PATTERN = ^# (.+)$` y
   `_get_all_headings` recorrían todas las líneas, incluidas las de una cerca de bash. En **620
   laboratorios** había algún `#` de comentario; en **602** el único H1 real era el título y el
   validador contaba dos o más. El 97 % de los errores de `single_h1` era esto.
2. **Los pasos viven en H2, H3 y H4, no solo en H3.** `LAB_STEP_PATTERN` exigía `^### (Step|Paso)
   N[:.]`. En el corpus hay 618 pasos en H2, 6.107 en H3 y **1.761 en H4**: 2.379 pasos invisibles.
   Además los nombres varían: `Paso A1:`, `Paso A-1:`, `Paso A.1 —`, `PASO 1 —`, `Fase 1:`,
   `Parte 1:`, `Ejercicio 1:`.
3. **Las secciones obligatorias son una plantilla, no un contrato.** 503 laboratorios no tienen
   alguna de las diez, casi siempre porque la titulan de otra forma: «Pasos del laboratorio»,
   «Validación del laboratorio», «Configuración del entorno de laboratorio». Un nombre distinto no
   es un laboratorio roto.

### 21.3 Qué se cambió

| Regla | Antes | Ahora |
|---|---|---|
| `single_h1` | cuentas los `#` de los bloques | solo encabezados fuera de cerca; **ERROR** si hay 0 o 2+ |
| `lab_steps` | `### Paso N:` | H2–H4, `Paso/Step/Fase/Parte/Ejercicio/Actividad/Etapa`, id `A1`, `A-1`, `1.2`, `PASO 1 —`; **ERROR** si no hay ninguno |
| `heading_hierarchy` | ERROR al saltar nivel | ERROR solo si no hay ningún encabezado; saltar nivel es **WARNING** |
| `required_section` | ERROR | **WARNING** |
| código, tablas, THOR | — | sin cambios |

El aislamiento de las cercas se hace en `_strip_fenced_code`, que vacía el contenido pero **conserva
las líneas**, para no desplazar los números de línea de los avisos.

### 21.4 Medición después

| | Antes | Después |
|---|---|---|
| Laboratorios inválidos | 849 (65,6 %) | **47 (3,6 %)** |
| `lab_steps` | 426 | **30** |
| `single_h1` | 620 | **18** |
| `required_section` | 501 | 0 (aviso) |
| `heading_hierarchy` | 550 | 0 como error (aviso) |

Los 47 que quedan son defectos reales, revisados uno a uno:

- **18** tienen más de un H1 de verdad, con títulos sueltos: `# Verificar estado del listener`,
  `# Terminal 1`, `# 1. Archivos de resultados`.
- **30** no tienen ningún encabezado de paso: sección «Instrucciones paso a paso» y después prosa.
  Pertenecen a generadores anteriores; el Writer actual emite `### Paso N:` siempre.

Y la comprobación que decide: los **40 laboratorios más recientes del catálogo pasan los 40**. El
formato que produce hoy el Writer no dispara ninguna regla de error.

### 21.5 El cierre en la máquina de estados

```
ValidateLabContent ──► CheckLabValidation ──► InvokeLabGuideBuilder   (todo válido)
                              │
                              └─ all_valid = false ──► NotifyFailure
```

- `ValidateLabContent` y `ValidateLabContentBoth` apuntan ahora a `CheckLabValidation`.
- El `Choice` exige `IsPresent` **y** `BooleanEquals: false`, así que el camino de `Catch` (el
  validador se cae) no bloquea nada: sin dato no hay veredicto.
- **Modo sombra**: si el evento trae `lab_validation_shadow`, la puerta registra y deja pasar. Sirve
  para volver atrás sin redeplegar la máquina.
- `fail_on_error` sigue en `false` a propósito: el validador responde 200 con `all_valid`, y quien
  decide es el `Choice`, no un código HTTP.

### 21.6 Decisión

1. **La puerta bloquea**, pero solo con tres reglas estructurales verificadas sobre el corpus:
   sin H1, con varios H1, o sin ningún paso. Todo lo demás es aviso.
2. **No se bloquea el libro de lecciones**: la medición y el cierre se hicieron sobre laboratorios,
   que es donde el informe sitúa el problema. Las lecciones siguen en modo informativo.
3. El criterio de §14 se cumple por construcción: las reglas que bloquean tienen 0 falsos positivos
   sobre 40 laboratorios recientes y 47 casos reales sobre el catálogo histórico.

### 21.7 Reproducibilidad

- `calibrar_puerta.py` — primera medición (65,6 %) y reglas que disparan.
- `medir_fps_puerta.py` — composición: 620 laboratorios con `#` en cerca, 602 con un solo H1 real;
  2.379 pasos en H2/H4.
- `ver_titulos_puerta.py` y `revisar_errores_puerta.py` — títulos reales de los marcados, para
  separar variante de nombre de ausencia real.
- `ver_formas_paso.py` — formas `Paso A1:`, `PASO 1 —`, `Paso A-1:`.
- `calibrar_puerta2.py` — medición final (47, 3,6 %) con el validador real.
- `puerta_salida_reciente.py` — 40/40 laboratorios recientes válidos.
- Batería: **11/11** en `test_content_validator.py`, con camino vivo del handler (200/400 y
  `all_valid`) y control del artefacto desplegado (`ValidateLabContent.Next`,
  `CheckLabValidation`, rama de bloqueo y modo sombra), más **107/107** en
  `test_referent_check.py`.





