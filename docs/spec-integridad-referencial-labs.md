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


## 22. Piloto sobre la salida real (22/10/2026): lo que la medición cambió

Hasta aquí todo estaba calibrado contra el **catálogo histórico**. Este apartado mide el sistema
sobre un curso **generado con el código actual**, de principio a fin, y anota lo que solo se ve
cuando la salida es nueva: tres defectos de pipeline, un artefacto que no se acumulaba y un canal
de avisos que no servía como señal.

### 22.1 El curso de prueba

| Dato | Valor |
|---|---|
| Proyecto | `261022-Prueba-PY-AUTOM-FICHEROS` |
| Temario | `prueba_python_ficheros.yaml` — 2 módulos, 4 lecciones, 2 laboratorios, 180 min |
| Tema | automatizar tareas repetitivas con Python: ficheros de texto y CSV |
| Salida | 4 lecciones (54 KiB), libro de 275 KiB, 11 imágenes, 2 guías de laboratorio |
| Ejecuciones | `course-gen-qa-thor-1792690652` (falló), `-1792691393` (reanudada, OK), `-1792693180` (regeneración saltada), `-1792693396` (lab 01 regenerado) |

El temario **no nombra ficheros**: es el caso mayoritario del catálogo y el que más presión pone
sobre el Writer.

### 22.2 Tres defectos de pipeline que solo aparecen al ejecutar

Ninguno se detectaba en las pruebas anteriores porque las tres rutas estaban cubiertas con eventos
sintéticos que traían los campos que en producción se perdían.

1. **`manual_text_s3_key` no se propagaba** (`CombineResultsAndBuildBook`,
   `CombineResultsAndBuildBookBoth`, `ResumePostTheoryBranch`), regresión introducida en `f8354a0`.
   La ejecución murió con `States.Runtime` **después** de pagar la teoría y las once imágenes: el
   `Pass` descartaba el campo y el estado siguiente lo necesitaba como entrada obligatoria.
2. **`manual_s3_keys` / `manual_text_s3_key` se perdían** en `PrepareNewCourseParams` y
   `PrepareRegenerationParams`. El modo `content_type='theory'` no podía arrancar: la entrada
   llegaba sin las claves que el escritor de lecciones exige.
3. **El artefacto referencial se sobrescribía** en `guardar_informe_referencial`. El Writer procesa
   **un laboratorio por invocación**, así que el curso de 2 laboratorios terminó con `labs: 1` y el
   informe del último laboratorio pisando al del primero. Ahora `cargar_informes_previos` lee el
   artefacto y fusiona por `por_laboratorio`. Es seguro porque el lote corre con
   `MaxConcurrency: 1`; con concurrencia habría carrera de lectura-modificación-escritura.

**Prueba nueva:** `test_state_machine.py`, **5/5**. No comprueba campos en el fuente: **simula el
grafo** por modo (`theory`, `labs`, `both` y reanudado desde teoría) y verifica que cada `Pass`
conserva los campos que el estado siguiente declara necesarios, más que el lote de laboratorios
sigue en `MaxConcurrency: 1`. Se comprobó **no vacua**: reintroducido el defecto 1 y el del modo
solo-teoría, la batería falla.

### 22.3 Qué midieron las verificaciones sobre esa salida

| Verificación | Lab 01 | Lab 02 | Lectura |
|---|---|---|---|
| **A1** (plan) | 1 referente, **0 de alta** (`/Documents/automatizacion-python`, baja) | — | el plan no inventó rutas |
| **B1** (referente inexistente) | 0 violaciones | 0 | 0 FP; tampoco hubo TP porque no había nada inventado |
| **B2** (cierre entre labs) | 2 menciones de baja (`siguiente laboratorio`, `próximo laboratorio`) | 0 | el lab 02 existe: clasificar como baja fue correcto |
| **B3p** (entregable declarado) | `declarados: 0` | `declarados: 0` | estructuralmente inaplicable: el plan no nombra ficheros |
| **B5** (requisitos) | 1 ampliación: `2 ghz`, hardware | 0 | el plan pide 1,5 GHz mínimo y la guía pone 2 GHz en la columna *Recomendado* |
| **B6** (duración) | `ok` (5 pasos, 31 bloques, 1,61 min/bloque) | `ok` (6 pasos) | 0 reintentos |
| **A3** (duración del temario) | `corregidos: []`, `suma_plan 100` vs 180 | | el temario declara 2 labs y el plan produce 2 |
| **Puerta** | 0 errores, **17 → 2** avisos | 0 errores, **20 → 2** avisos | `all_valid: true` |

El caso de B5 es el mejor argumento para la separación ampliación/contradicción de §18: `2 GHz` no
contradice al plan (que fija 1,5 GHz como mínimo), lo **amplía**. Con la regla anterior —que
comparaba contra el plan sin distinguir— habría disparado un reintento por un falso positivo.

El artefacto definitivo queda con `total_alta_confianza: 0`, `ok_alta_confianza: true` y
`ok: false`. **`ok` significa "cero hallazgos de cualquier tipo"**, no "curso defectuoso": para
monitorizar hay que leer `ok_alta_confianza`. El piloto deja `ok: false` por una ampliación de
baja confianza, que es exactamente lo que debe registrar sin bloquear.

### 22.4 El canal de avisos de la puerta era ruido

La puerta bloquea con tres reglas (§21), pero emite avisos. Sobre los dos laboratorios del piloto
salieron 37 avisos y **ninguno era un defecto**. Para saber si eso era mala suerte, se pasó el
validador actual sobre los **120 laboratorios más recientes** del catálogo (6/10 → 22/10):

```
labs con al menos un aviso: 120/120
avisos totales: 1657      errores totales: 0

step_structure           1459   (88,1 %)
code_block_language       119   ( 7,2 %)
vague_version              75   ( 4,5 %)
unmeasurable_validation     4   ( 0,2 %)
```

Cuatro familias, todas mecánicas:

1. **`step_structure`, 1.459 avisos.** La regla exigía `**Objective:**`, `**Instructions:**`,
   `**Verification:**`; el corpus escribe `**Objetivo:**`. Es un validador **ciego al idioma del
   curso** en un producto que genera en español. Además el corpus usa los dos estilos de negrita
   (`**Objetivo:**` y `**Objetivo**:`), y la comprobación solo aceptaba el primero.
2. **`code_block_language`, 119 avisos.** Contaba también las **vallas de cierre**, que por
   definición no llevan lenguaje: un bloque sin lenguaje se informaba como dos, y el mensaje decía
   59-81 bloques cuando el número real era la mitad.
3. **`vague_version`, 75 avisos.** El filtro aceptaba cualquier línea con `|`, así que marcaba
   «después de la última coma no hay valor» y las URL que acaban en `/latest/`.
4. **`unmeasurable_validation`, 4 avisos.** Marcaba prosa explicativa («esto funciona correctamente
   en Python en todos los sistemas operativos»).

Se corrigieron **1 y 2** (defectos: la etiqueta existe y el recuento es falso), con prueba de camino
vivo cada uno. Resultado sobre los mismos 120 laboratorios:

```
labs con al menos un aviso:  96/120   (antes 120/120)
avisos totales: 389                   (antes 1657, −77 %)
step_structure 291 · vague_version 75 · code_block_language 19 · unmeasurable_validation 4
```

Los **291** que quedan son otra cosa y **no se tocaron**: pasos con `**Objetivo:**` y una lista
numerada, sin etiqueta `**Instrucciones:**`. La lista numerada *es* la instrucción, así que el aviso
es formal, no de calidad. Decidir si esa etiqueta es obligatoria exige su propia medición; forzarla
ahora sería cambiar el estándar para que el aviso desaparezca, que es lo contrario de medir.

**3 y 4** siguen ahí, medidas y sin corregir: son problemas de contexto (una fila de tabla o una
URL no son un requisito de versión), no de expresión regular. Su corrección necesita acotar el
contexto y volver a medir; queda como trabajo con criterio propio.

Sobre el piloto, el efecto es el mismo: **17 → 2** y **20 → 2** avisos, y los 2 que quedan por
laboratorio son los 14 bloques de «salida esperada» (intencionales, sin lenguaje) y un
`vague_version`/`unmeasurable_validation` de la familia 3/4.

### 22.5 Lo que el piloto NO arregla: reproducibilidad

Con el **mismo plan**, el laboratorio 01 se generó dos veces. Resultado:

| | Ejecución 1 | Ejecución 2 |
|---|---|---|
| Pasos | 5 | 5 |
| Ficheros nombrados | `inventario_oficina.txt`, `inventario_oficina_backup.txt`, `leer_inventario.py`, `resumen_inventario.txt`, `inventario_oficina.txt.txt` | `inventario.txt`, `leer_inventario.py`, `registrar_ejecucion.py`, `resumen_inventario.txt` |
| En común | 2 de 5 | |

Dos hechos:

- **La fabricación está contenida, la estabilidad no.** B1 da 0 porque cada fichero que se nombra se
  crea dentro del laboratorio. Pero *cuál* se nombra lo decide el Writer en cada ejecución, porque
  el plan delegó el nombre en `[POR CONFIRMAR nombre definitivo del fichero de datos de entrada]`.
  El curso no es reproducible aunque sea íntegro.
- Apareció un nombre mal construido (`inventario_oficina.txt.txt`, `.txt.txt`), que no se repitió.
  Medido sobre el corpus: **1 laboratorio de 120** tiene extensión duplicada. No da para regla; sí
  para saber que existe y que no es sistémico.

La conclusión es de diseño, no de implementación: **la reproducibilidad no se arregla en el Writer,
se arregla en el temario**. Si el temario nombra los ficheros de trabajo, el plan los hereda, el
Writer no decide nada y el nombre es estable entre ejecuciones. Es el mismo argumento de §5 sobre el
temario como contrato, ahora con evidencia de salida: mientras el temario no nombre, cada
regeneración produce un curso distinto y correcto.

### 22.6 Decisión

1. Los interruptores siguen como en §18/§19: `REFERENTIAL_RETRY`, `DURATION_RETRY` y
   `REQUIREMENTS_RETRY` en `1`; `DELIVERABLES_RETRY` en `0`.
2. **A1/B1 no pasan a `ERROR`.** El criterio de §14 es 0 falsos positivos sobre N cursos reales y
   aquí hay 0 sobre 2 laboratorios: el numerador es bueno y la N todavía no.
3. **B3p no se puede evaluar** mientras el plan no nombre ficheros. Encender `DELIVERABLES_RETRY`
   antes de eso sería encender una regla que no corre.
4. `ok` en el artefacto referencial es «cero hallazgos»; el indicador operativo es
   `ok_alta_confianza`. Queda escrito para que nadie lea un `ok: false` como un curso defectuoso.

### 22.7 Reproducibilidad de este apartado

Los guiones viven en el espacio de análisis (`…\Temp\opencode\thor_manual\`), igual que los de
§14/§21, y no se versionan:

- `medir_prueba.py` — descarga el plan, los dos informes y las guías; cuenta laboratorios, ficheros
  y hallazgos.
- `revalidar_piloto.py` — invoca el `ContentValidator` **desplegado** sobre las guías del piloto y
  lee los informes resultantes (es la medición de la tabla de §22.3, no una copia local).
- `medir_avisos_puerta.py` — avisos por regla sobre los 120 laboratorios más recientes.
- `diagnostico_etiquetas.py`, `diagnostico_instrucciones.py` — qué etiquetas tienen realmente los
  pasos marcados, para separar variante de formato de ausencia real.
- `medir_extension_duplicada.py` — nombres con extensión duplicada en la salida real.
- `historial_ejecucion.py` — historial de una ejecución de Step Functions (recibe el nombre por
  argumento).

Baterías al cerrar este apartado: `test_content_validator.py` **15/15**, `test_referent_check.py`
**108/108**, `test_state_machine.py` **5/5**.




## 23. El temario como contrato (22/10/2026): lo que el instructor declara, el plan lo copia

§22 dejó una conclusión incómoda: la reproducibilidad no se arregla en el Writer, se arregla en el
temario. Este apartado ataca esa raíz, y al medirla apareció algo más simple y más grave que la
reproducibilidad: **el planificador no leía del temario lo que el temario sí declara**.

### 23.1 Medición sobre el corpus (179 temarios, 1.279 laboratorios)

Se pasó `extract_all_labs` (la función real del planner, no una copia) sobre los 179 temarios de S3 y
se contó qué declara cada laboratorio:

| Campo del temario | Laboratorios que lo declaran | ¿Llegaba al modelo? |
|---|---|---|
| `lab_title` | 1.279 (100 %) | Sí, y se sobrescribe con el del temario |
| `duration_minutes` | 1.279 (100 %) | Sí (A3 lo fija) |
| `description` | 972 (76 %) | **No** |
| `objective` | 857 (67 %) | **No** |
| `objectives` (plural) | 0 (0 %) | — |
| `activities` | 0 (0 %) | — |

El resumen que el planner enviaba al modelo por lote (`labs_summary`) contenía **solo** `lab_id`,
módulo/lección, título, duración, nivel de Bloom y temas de contexto. Ni `objective` ni
`description`, que son justo los dos campos donde el instructor escribe qué debe hacer el
laboratorio. Consecuencia medible: para los 792 laboratorios con declaración específica (excluidos
159 de plantilla, es decir, textos repetidos ≥3 veces en su propio curso), la cobertura media de las
palabras del temario en el texto del plan era **57 %**, y solo el **2 %** llegaba al 90 % de
cobertura. La cola no era cosmética: 59 laboratorios quedaban por debajo del 30 %, y en los casos
revisados uno a uno el plan no parafraseaba el objetivo, hacía otra tarea (p. ej. el temario pide
«crear informe final con insights usando información de la Web» y el plan describe generar borradores
en Word).

Nota de método: las declaraciones **de plantilla** («Aplicar los conceptos del módulo a un caso
real») no son contrato, porque no dicen nada que copiar; en esas, derivar es correcto. La
clasificación se hizo por repetición dentro del mismo curso (≥3 laboratorios con el mismo texto), no
por una lista de frases.

### 23.2 Decisión: copiar lo declarado, complementar lo demás

Se mantiene la regla del proyecto —el temario **no** gana campos obligatorios, y la IA **no** cambia
lo que el temario define— con tres niveles explícitos:

1. **Declarado**: `lab_title`, `duration_minutes`, `objective` y `description` se copian literalmente.
   Es corrección determinista, no reintento.
2. **Derivable**: lo que el temario no dice (alcance, artefactos, pasos) lo decide el planificador y
   se conserva. Si el modelo añade objetivos, se quedan **detrás** del declarado.
3. **No declarado**: los 422 laboratorios sin `objective` siguen exactamente como antes. A5 no
   inventa contrato donde no lo hay.

### 23.3 Qué se implementó

| Pieza | Dónde | Qué hace |
|---|---|---|
| A5 en el prompt | `strands_lab_planner.py`, `labs_summary` | Entrega al modelo `DECLARED OBJECTIVE` y `DECLARED DESCRIPTION` literales, con la regla «cópialo, no lo reformules» |
| `reconciliar_contrato` | `referent_check.py` (copia idéntica en planner y writer) | Pone el objetivo declarado en `objectives[0]`, guarda `outline_objective` y `outline_description` |
| `auditar_contrato` (A5) | `referent_check.py` | Post-condición sobre el plan final: título, duración, `objectives[0]` y descripción |
| Artefacto | `validation/contract-integrity.json` + `metadata.contract_integrity` | Deja el contrato inspeccionable por laboratorio |
| Bloque de contrato | `strands_lab_writer.py`, `_contrato_declarado` | El Writer ve lo que escribió el instructor, no solo la paráfrasis del plan |
| `asegurar_objetivo_declarado` | `strands_lab_writer.py` | Si el modelo reescribe el objetivo, se inserta el declarado como primer ítem (solo si falta) |

`auditar_contrato` es una **post-condición**, no una medida de calidad: como la reconciliación es
determinista, en planes nuevos debe dar siempre `ok: true`. Si aparece un conflicto, el fallo está en
la reconciliación (por ejemplo, un `lab_id` que no cuadra con el temario), no en el modelo. La
evidencia de que sirve es la medición de 23.4, no su propio `ok`.

### 23.4 Medición sobre la salida real

**Curso real con declaración en los 4 laboratorios** (`251128-python-intro/outline/python_intro.yaml`):

| | Objetivos literales | Descripciones literales | Cobertura del vocabulario declarado |
|---|---|---|---|
| Plan guardado antes de A5 | 0/4 | 0/4 | 52 % |
| Planner desplegado, ejecución 1 | **4/4** | **4/4** | 83 % |
| Planner desplegado, ejecución 2 | **4/4** | **4/4** | 94 % |

Las dos ejecuciones dan `contract_integrity.ok: true`, `con_declaracion: 4`, `labs: 4`,
`conflictos: []`. La parte determinista (el texto declarado) es idéntica entre ejecuciones; lo que
varía es solo el complemento del modelo (83 % vs 94 %).

**Camino completo hasta la guía** (`261022-A5-medida-2`, lab 01-00-01, mismo plan, antes y después):

| | Objetivo declarado en la guía | Posición |
|---|---|---|
| Guía generada antes del arreglo | 0 ocurrencias | — |
| Guía regenerada después | 1 ocurrencia, literal | Primera viñeta |

Antes, el plan ya traía el objetivo correcto en `objectives[0]` y el modelo lo reescribía igualmente:
la fidelidad del plan no basta, el Writer también tiene que verse obligado.

### 23.5 Pruebas (camino vivo, no búsqueda de texto)

`test_referent_check.py`: **117/117** (9 nuevas).

- `test_el_planner_copia_al_plan_el_objetivo_del_temario` — ejecuta `lambda_handler` con temario y
  respuesta del modelo simuladas; el plan guardado lleva el objetivo literal y el informe cuadra.
- `test_el_contrato_no_obliga_al_temario_a_declarar_nada` — sin `objective`/`description` el plan no
  cambia y `con_declaracion` es 0.
- `test_el_contrato_detecta_un_objetivo_reescrito` — el auditor ve el defecto previo (no es vacuo).
- `test_reconciliar_contrato_deja_el_plan_auditable` — reconciliar + auditar componen.
- `test_el_planificador_entrega_al_modelo_lo_que_declara_el_temario` — ejecuta
  `generate_lab_master_plan` con el cliente Bedrock sustituido y comprueba el **prompt construido**.
- `test_el_writer_recibe_el_contrato_declarado_en_el_temario` y
  `test_el_writer_no_inventa_contrato_si_el_temario_no_declaro` — el prompt del Writer (constructor
  compacto, el que usa el handler con un laboratorio por invocación).
- `test_la_guia_recibe_el_objetivo_del_temario_si_el_modelo_lo_reescribe` — ejecuta
  `generate_all_labs_batch` con respuesta simulada que parafrasea y comprueba la guía devuelta: una
  sola ocurrencia y en primera posición.
- `test_asegurar_objetivo_declarado_no_duplica_ni_inventa` — idempotencia y caso sin contrato.

No vacuidad comprobada desactivando `reconciliar_contrato` en el planner: el test del handler falla,
el objetivo del temario no llega al plan y el auditor reporta 2 conflictos (objetivo y descripción).

### 23.6 Límites y decisiones abiertas

1. **A5 no arregla los 422 laboratorios sin declaración** (33 %). Ahí el contrato es el título, y el
   título no basta para que dos ejecuciones coincidan (§22.5). Ese frente sigue abierto: o el
   instructor nombra los ficheros (sin obligación), o el plan los fija una sola vez y el Writer los
   copia.
2. **A5 no juzga la calidad del complemento.** Si el modelo añade objetivos que contradicen el
   declarado, A5 no lo detecta: `objectives[0]` está bien y el resto no se compara. Detectar
   contradicción semántica exige otra regla y otra medición.
3. **El `objective` de 159 laboratorios es plantilla.** Copiarlo literal sería ruido; hoy se copia
   igual (es lo declarado) y no se distingue en el informe. Si molesta en la salida, la mejora es
   marcar la plantilla en el artefacto, no dejar de copiarla.
4. **La inserción en la guía es aditiva.** No borra ni reordena lo que escribió el modelo; solo añade
   la viñeta que falta. Si el modelo ya la respetó, no toca nada.

### 23.7 Reproducibilidad de este apartado

- `medir_contrato_temario.py` — qué declara cada laboratorio del corpus y cuánto se reproduce.
- `medir_fuga_clases.py` — cobertura del vocabulario declarado, separando plantilla de específico.
- `medir_a5.py` — antes/después por curso: literalidad del objetivo y la descripción, cobertura.
- `invocar_planner.py` — ejecuta el planner desplegado sobre un temario real en una carpeta de
  medición (`261022-A5-medida-1`, `-2`).

Baterías al cerrar el apartado: `test_referent_check.py` **117/117**,
`test_content_validator.py` **15/15**, `test_state_machine.py` **5/5**, `test_manual_context.py`
**17/17**.

## 24. La medida sobre 1.196 laboratorios reales (22/10/2026): el bloqueo ya está puesto y no
cumple el criterio

El criterio que nos dimos para subir una regla a `ERROR` era explícito: **0 falsos positivos sobre
N cursos reales**. Hasta ahora N eran 2 laboratorios del piloto. Aquí se mide sobre todo el corpus
entregado, y el resultado obliga a reencuadrar la pregunta: no se trata de encender un bloqueo que
hoy no existe, sino de decidir si se apaga o se estrecha el que ya está en producción.

### 24.1 Qué se midió y sobre qué

| | Artefacto | Contexto |
|---|---|---|
| **A1** | `labguide/lab-master-plan.json` de 165 proyectos | `fuentes` = texto del temario + manual, tal como los arma el planner |
| **B1/B2/B5/B6/B3p** | las 1.196 guías `labguide/lab-*.md` de 164 proyectos | reconstruido igual que el Writer: `fuentes` = temario + manual; `plan` = `flatten_to_text` del plan; `creados_antes` acumulado en el orden del plan; `salidas_posteriores`; `duración` declarada en la guía o, si no, la del plan; `requisitos` del plan; `expected_outcomes` |

Las funciones que se ejecutan son **las del repositorio desplegado** (`auditar_plan`,
`auditar_laboratorio` de `referent_check.py`), no una reimplementación. Las guías son las
entregadas: laboratorios generados **antes** de que B1/B2/B6 existieran, así que esta medida
estima lo que el validador habría marcado, sin que el bucle de reintento haya influido en el texto.

### 24.2 A1 sobre el plan

| | Hallazgos | Alta confianza | Baja confianza |
|---|---|---|---|
| 165 planes | 1.432 | **119** | 1.313 |

Los 119 de alta están en **32 de 165 planes** (19 %). Campos donde aparecen: `lab_plans[].scope`
(53), `lab_plans[].prerequisites[]` (33), `special_considerations[]` (26),
`software_requirements[].installation_notes` (7). Por extensión dominan los datos que el curso
debería aportar: `.xlsx` 33, `.csv` 15, `.docx` 14, `.pdf` 8.

Y A1 **no bloquea nada**: `auditar_y_corregir_plan` reintenta como mucho 2 veces y si quedan altas
solo las registra (líneas 1043-1074 del planner, sin `raise`). Los 119 quedan escritos en
`metadata.referential_integrity` y ahí muere su efecto, salvo que el Writer los use para *excluir*
esos referentes del texto del plan.

### 24.3 B1/B2/B5/B6 sobre las guías

| Regla | Alta | Baja | ¿Tumba la ejecución hoy? |
|---|---|---|---|
| B1 | **14** | 543 | Sí |
| B2 | 0 | 8 | Sí |
| B5 | 0 | 47 | Sí |
| B6 | **14** | — | Sí |
| B3p | 212 | 29 | No (`DELIVERABLES_RETRY=0`) |

**28 hallazgos de alta en 28 laboratorios** de 1.196 (2,3 %). Los 240 «de alta» del cómputo global
incluyen los 212 de B3p, que no bloquean.

### 24.4 Lo que significa hoy un hallazgo de alta (reencuadre)

La configuración desplegada no tiene ninguna de las variables de reintento, así que aplican los
valores por defecto (`strands_lab_writer`, líneas 59-135; comprobado con
`get_function_configuration` sobre la Lambda desplegada):

- `REFERENTIAL_RETRY=1`, `DURATION_RETRY=1`, `REQUIREMENTS_RETRY=1` → B1/B2/B6/B5 de alta entran en
  el reintento correctivo.
- `DELIVERABLES_RETRY=0` → B3p de alta solo se registra.
- `MAX_LAB_GENERATION_ATTEMPTS=3` → si el hallazgo persiste, `raise RuntimeError` (línea 2433).
- El `Retry` de `GenerateLabBatch` solo cubre errores transitorios de Lambda, así que un
  `RuntimeError` **no se reintenta**: `Catch: States.ALL` → `LabBatchFailState`, que es un estado
  `Fail` del `Map`. El `except` del handler vuelve a lanzar (`raise`), no lo traga en un
  `statusCode: 500`.
- `ProcessLabBatchesInParallel` no tiene `Retry`; su `Catch` va a `NotifyFailure`.

Consecuencia: **un hallazgo de alta de B1/B2/B5/B6 que aguante tres intentos tumba la ejecución
entera y el curso no se entrega.** La exposición medida es de 2,3 % por laboratorio, es decir en
torno al 17 % por curso de 8 laboratorios (1 − (1 − 28/1196)^8), suponiendo que el corpus viejo sea
representativo de lo que genera el Writer actual.

No es un riesgo hipotético, pero tampoco ha matado ningún curso todavía: de las 28 ejecuciones
fallidas de `CourseGeneratorStateMachine` en 120 días, ninguna tiene causa
`LabBatchGenerationFailed` (son errores de JSONPath de la máquina de estados, límite de tamaño de
payload y un `int('all')`). B1 lleva desplegado horas, así que ese «no ha pasado» no es evidencia
de nada.

### 24.5 Revisión a mano: los falsos positivos existen

Se revisó uno a uno el contexto de las 14 de B1 y se inspeccionaron las 14 de B6 (ficheros:
`revision_b1_altas.txt`, `ab1_corpus.txt`).

**B1, 14 hallazgos, 4 falsos positivos (29 %):**

| Hallazgo | Veredicto | Por qué |
|---|---|---|
| `251209-copilot-365-4-h` `Ventas_MultiRegional_2024.xlsx` | real | «Descargue el archivo de ejemplo … desde el repositorio del taller» y ningún sitio lo aporta |
| `260129-IA-GEN-ESS-V2` `politica_vacaciones_parte1.txt` y `parte2.txt` | **falso** | son los nombres de ejemplo de un bloque de código que ilustra cómo trocear un documento; el alumno los crea |
| `260527-COP-CHAT-IT-Priv` `C:\users.txt` | **falso** | está dentro de un guion de PowerShell que el alumno debe **revisar** (`Get-Content "C:\users.txt"`), no ejecutar |
| `260528-IA-GEN-INTE` `./openai_key.txt` | **falso** | está en el *docstring* de un ejemplo de uso (`docker secret create openai_api_key ./openai_key.txt`) |
| los 10 restantes (`REFERENCIA-NORMAS-EHS.docx`, `Lab02_Claves_Respuesta.pdf`, `BA_05-00-01_*`, `Politica_Vacaciones.pdf`, `Datos_Financieros_Q4.xlsx`…) | reales | son ficheros que el instructor debe colocar en SharePoint/OneDrive y que ni el temario ni el plan declaran |

Nótese que varios de los reales ya llevan en la guía un marcador semántico —«El instructor debe
confirmar que la carpeta de fuentes contiene…»— que ninguna regla reconoce.

**B6, 14 hallazgos:** el motivo siempre es la duración declarada contra el trabajo real
(«15 minutos para 9 pasos con acción y 65 bloques»). La mayoría son reales (instalar Ubuntu Server
con 65 bloques en 15 minutos), pero hay al menos uno falso por lectura parcial:
`260924-Temario-fortinet-…` lab `02-00-02` declara «15 minutos (creación VM) + 35–45 minutos
(instalación OS) + 15 minutos (post-instalación)» y `duracion_declarada` se queda con el **primer**
número, 15, cuando el laboratorio declara entre 65 y 75. Y hay casos limítrofes: `06-00-02` de
`260728-angular-essentials` cruza los **dos** umbrales por poco (1,9 min/paso y 0,72 min/bloque).

**El criterio de 0 falsos positivos no se cumple**, ni en B1 (29 %) ni en B6.

### 24.6 Los mecanismos, en el código

1. **La ventana de contexto no es la frase.** `_contexto_de` recorta a los límites del *paso*, y
   cuando el texto no tiene encabezados `###` —un campo del plan, o una sección de la guía— el
   «paso» es todo el bloque y la ventana son ±260 caracteres (`_VENTANA_CONTEXTO`). En
   `politica_vacaciones_parte1.txt` basta un «Abre el PDF» a media distancia para que el listado de
   nombres de ejemplo pase por entrada aportada por el curso.
2. **Un bloque de código de ejemplo no es una entrada.** El docstring de `obtener_docker_secret` y
   el guion que el alumno revisa cuentan como referencias de fichero.
3. **A1 no tiene la puerta que B1 sí tiene.** B1 descarta primero con `_es_creacion` (línea 1420):
   verbo de creación, `_MARCAS_CREACION` (`--output`, `cat >`, `archivos generados`, `mkdir`…), el
   andamiaje (`ng new`, `git clone`…), árboles de directorios, importaciones y citas. A1 decide con
   `_es_entrada` a secas (línea 816) y no consulta ninguna marca de creación, aunque su propio
   comentario de `_MARCAS_ENTRADA` dice que «casi todos los falsos positivos» están en contextos de
   creación.
   - Lectura a mano de los 119 de A1: **43 falsos positivos (36 %)**, casi todos de esa clase
     («se guardará en», «se exporta a», «archivos de salida», «generado por el script», «producir un
     documento», «se desarrollará»…): directorios de trabajo, ficheros que el laboratorio exporta y
     módulos que el alumno escribe.
   - Aplicando `_es_creacion` —la del propio repositorio— a esos mismos 119, exoneraría 74 (62 %).
     Ese 62 % **no** es la tasa de falsos positivos: sobre texto de plan sin estructura de pasos la
     ventana es tan ancha que `_es_creacion` exculpa también cosas que sí se aportan («se
     proporcionan 2-3 archivos CSV de ejemplo»). Sirve como cota superior, no como medida.
4. **`duracion_declarada` toma el primer número.** `_DURACION_LAB_RE` no distingue una duración
   total de un desglose.

### 24.7 La corrección que el Writer prescribe no converge

`mensaje_de_correccion` (línea 1547) instruye, para un referente que el curso debe aportar: «escribe
«[POR CONFIRMAR]» junto a su mención». El docstring del módulo dice lo mismo: un referente no
declarado ni derivable «debe omitirse o marcarse con un marcador visible (`[POR CONFIRMAR]` y
similares)».

**Ninguna regla reconoce ese marcador.** `grep` de `POR CONFIRMAR` en `referent_check.py` solo
aparece en el docstring y en las tres instrucciones de corrección.

Se aplicó la corrección al pie de la letra (insertar el marcador tras cada mención) y se volvió a
auditar con `auditar_laboratorio` y el mismo contexto (`probar_convergencia.py`): en los cuatro
casos probados —incluido el verdadero positivo `Ventas_MultiRegional_2024.xlsx`— el hallazgo
**persiste** con la misma confianza. Es decir, el camino que la propia instrucción señala como
canónico no limpia la comprobación: el reintento gasta sus tres intentos y el curso cae. Solo
convergen las otras dos salidas de la instrucción (añadir el paso que lo crea, o sustituirlo por
una descripción sin nombre de fichero).

### 24.8 Decisión

1. **No se sube ninguna regla a `ERROR`.** El criterio de 0 falsos positivos no se cumple: 29 % en
   B1 sobre 14 hallazgos revisados uno a uno, y al menos 1 en B6.
2. **No se apaga el bloqueo que ya está puesto** (B1/B2/B5/B6 con reintento y `raise`): 24 de los 28
   hallazgos son defectos reales y son exactamente el fallo que el informe del instructor describe.
   Apagarlo perdería esos 24.
3. **Se estrecha antes de endurecer**, por orden de coste/beneficio:
   a. Reconocer `[POR CONFIRMAR]` (y «el instructor debe confirmar») como exoneración → hace
      converger el reintento y da contenido real al nivel 3 de la regla de tres niveles. Sin esto,
      cualquier referencia legítima que el curso deba aportar puede matar el curso.
   b. Exigir que la señal de entrada esté **en la frase del referente**, no en ±260 caracteres, y
      exonerar los referentes que solo aparecen dentro de un bloque de código de ejemplo.
   c. Dar a A1 la puerta de `_es_creacion` que ya tiene B1 y recortar su ventana a la frase.
   d. `duracion_declarada`: tomar el **mayor** de los números declarados, para no leer un desglose
      como si fuera el total.

   → Implementado y medido en **§25**. Dos de estos puntos cambiaron al medirlos: (b) no se resolvió
   recortando la frase sino comprobando que la prosa mencione el referente, y (c) no recorta la
   ventana de A1 (el falso positivo venía de la puerta de creación, no del tamaño). Ver §25.2.
4. **B3p sigue en registro** (`DELIVERABLES_RETRY=0`): 212 altas en 1.196 laboratorios es la clase
   más ruidosa y no hay evidencia de que sean defecto.
5. **El efecto cascada existe y está medido.** A1 marca un referente de alta, el Writer lo
   **borra** del texto del plan (líneas 2189-2208) y entonces B1 lo marca en la guía: el referente
   deja de contar como declarado precisamente porque A1 dijo que el curso debe aportarlo. Se midió
   reconstruyendo ese borrado (`medir_ab1_vivo.py`: recalcula A1 sobre cada plan, aplica el mismo
   `.replace` y vuelve a auditar las 1.196 guías).

   | | Sin borrado de A1 | Con borrado de A1 |
   |---|---|---|
   | B1 alta | 14 | **17** |
   | B1 baja | 543 | 552 |
   | Altas bloqueantes | 28 | **31** |
   | Laboratorios afectados | 28 | 29 |
   | Proyectos afectados | — | 17 |

   Las **3 que solo aparecen por la cascada** (`diferenciar_ab1.py`):

   - `260627-COP-CHAT-LEGAL` lab `04-00-01` → `Lab04_Plan_Cierre_Fiscal.xlsx`
   - `260803-temario-vmware-vsphere-foundation` lab `03-00-01` → `licenses.txt`
   - `260818-fundamentos-finops` lab `02-00-02` → `lab_02_02_trend_analysis.ipynb`

   Las tres son **verdaderos positivos de A1** (ficheros que el curso debe aportar y no están en el
   temario) y a la vez **verdaderos positivos de B1** (la guía los usa como entrada). El borrado
   los convierte en bloqueantes que el reintento no puede arreglar borrando: la guía necesita el
   fichero. Es decir, la cascada no inventa hallazgos falsos; **duplica la sanción sobre el mismo
   defecto real** y, al hacerlo, obliga al modelo a quitar de la guía una referencia legítima. Es
   una razón más para que la exoneración por marcador (`[POR CONFIRMAR]`) exista: es la salida
   correcta para este caso.

### 24.9 Reproducibilidad de este apartado

- `medir_a1_corpus.py` — A1 sobre los 165 planes guardados; `prueba/a1_corpus.txt`.
- `clasificar_a1_corpus.py` — los 119 de alta con su ventana de contexto; `prueba/a1_altas_contexto.json`.
- `medir_fp_a1.py` — cuántos de esos 119 exonera `_es_creacion`; `prueba/a1_falsos_positivos.txt`.
- `medir_ab1_corpus.py` — B1/B2/B3p/B5/B6 sobre las 1.196 guías; `prueba/ab1_corpus.txt`.
- `medir_ab1_vivo.py` — lo mismo con el borrado de A1 aplicado (efecto cascada);
  `diferenciar_ab1.py` — las 3 altas que solo aparecen por la cascada.
- `revisar_b1_altas.py` y `revisar_b6.py` — contexto ancho de los hallazgos concretos revisados.
- `probar_convergencia.py` — ¿limpia `[POR CONFIRMAR]` el hallazgo?
- `buscar_fallos_produccion.py` y `detalle_fallos.py` — ninguna ejecución fallida con causa
  `LabBatchGenerationFailed`.

## 25. Los estrechamientos de 24.8, implementados y medidos (23/10/2026)

La §24 cerró con «estrechar antes de endurecer». Esto es lo que se implementó, cómo se verificó
—siempre por el camino vivo, nunca buscando texto en el fuente— y qué pasó al volver a medir
sobre el **mismo** corpus.

### 25.1 Qué se cambió

| Estrechamiento | Dónde | Qué hace ahora |
|---|---|---|
| (a) marcador visible | `marcas_de_confirmacion` | `[POR CONFIRMAR]` —o «el instructor debe confirmar», «solicítalos a tu instructor», «confirmado por el instructor»— junto a la mención, o en el párrafo que la introduce, **exime** el referente y lo devuelve en `marcados` |
| (b) bloques de código | `_bloques_cercados`, `_texto_sin_bloques`, `_aparece_en_prosa` | la señal de entrada se busca en prosa y, si el nombre **solo** aparece dentro de un bloque de código, no puede ser de alta |
| (c) A1 | `auditar_plan` | consulta `_es_creacion` y el marcador antes de decidir la confianza |
| (d) duración | `_DURACION_LAB_RE`, `duracion_declarada` | acepta `**Duración estimada**`, `Duración total:` y toma el **mayor** de un desglose |

El informe al instructor gana `total_marcados_por_confirmar` y cada laboratorio gana `marcados`:
un referente señalado no es un defecto oculto, es trabajo que alguien tiene que hacer.

### 25.2 Tres correcciones que hizo la propia medición

Las tres van contra hipótesis de la §24, no contra el código:

1. **La ventana de A1 no se recorta.** El falso positivo de A1 no venía del tamaño de la ventana
   sino de que A1 no consultaba la puerta de creación. Recortar a la frase habría perdido
   verdaderos positivos del tipo «los estudiantes deben tener acceso a `M1_Catalogo_Cuentas.xlsx`
   en la carpeta compartida», que no lleva verbo de entrada.
2. **«En prosa» no basta; la prosa tiene que hablar del referente.** En el falso positivo de
   `politica_vacaciones_parte1.txt` el verbo («Abre el PDF») estaba en prosa, a 60 caracteres.
   Lo que lo distingue es que el nombre **solo** vive dentro del bloque: la prosa no lo menciona.
   Eso es lo que se comprueba con `_aparece_en_prosa`.
3. **El emparejamiento de cercas estaba mal.** ` ```.*?``` ` cerraba la cerca huérfana que el
   modelo abrió para citar un enunciado con la siguiente ` ```powershell `, y el script quedaba
   «en prosa»: así sobrevivía `C:\users.txt` en `260527-COP-CHAT-IT-Priv`. Ahora se respeta
   Markdown (un cierre no lleva lenguaje).

Y dos falsos positivos del **propio detector de marcadores**, encontrados revisando las 70
exoneraciones de la primera pasada:

- `"a confirmar"` casaba dentro de «par**a confirmar**»: cualquier «ejecuta esto para confirmar
  que…» exoneraba el párrafo entero. Se eliminó.
- `[COMPLETAR]` es un hueco de plantilla que rellena el alumno, no una marca para el instructor.
  Se acotó a `CONFIRMAR`/`PENDIENTE`.

Tras acotarlo, las exoneraciones pasan de 70 a **16** y las 16 son legítimas (§25.5).

### 25.3 La medición

Mismo corpus, mismas funciones, mismo borrado de A1 en el plan (el camino vivo):

| | §24 (antes) | §25 (después) | |
|---|---|---|---|
| A1 hallazgos | 1.432 | **1.432** | no se pierde ninguno |
| A1 de alta | 119 en 32 planes | **45 en 13 planes** | −62 % |
| A1 de baja | 1.313 | **1.387** | los 74 bajan, no desaparecen |
| B1 de alta | 17 | **8** | |
| B1 de baja | 552 | 550 | |
| B6 de alta | 14 | **12** | |
| **Altas bloqueantes** | **31** | **20** | −35 % |
| Laboratorios afectados | 29 | **20** | |
| Proyectos afectados | 17 | **12** | |
| Exonerados por marcador | 0 | **16** | |

Es decir: **1,7 % de los laboratorios** (20 de 1.196) sigue teniendo un hallazgo que puede tumbar
el curso, frente al 2,6 % de antes. Con la cuenta de siempre —8 laboratorios por curso y
dependencia ingenua—, del ≈19 % por curso al ≈13 %.

### 25.4 Los 20 que quedan, leídos uno a uno

**B1 (8).** Siete son defectos reales, y son exactamente el fallo que describe el informe del
instructor: el laboratorio usa un fichero que el curso debe aportar y el temario no declara —
`Ventas_MultiRegional_2024.xlsx` («Abra el archivo … desde OneDrive»),
`Lab02_Reporte_Automatizado.xlsx` («Asegúrate de tener … en tu OneDrive»),
`Lab04_Plan_Cierre_Fiscal.xlsx` (lista de los tres ficheros cargados en OneDrive),
`REFERENCIA-NORMAS-EHS.docx` («Verifica que puedes ver los siguientes archivos»),
`Lab02_Claves_Respuesta.pdf` («valores de referencia proporcionados por el instructor»),
`licenses.txt` («proporcionado por el instructor»),
`Datos_Financieros_Q4.xlsx` («subir el archivo … y referenciarlo»).
El octavo, `/Modulo1/Normativos/LSS_Cuotas_IMSS_2024_Ficticio.pdf`, ya lleva un nivel 3 escrito
en prosa que el vocabulario no reconoce: «**Nota para el instructor:** … verificar que el sitio de
SharePoint contenga…». Es el candidato inmediato, y es una decisión de vocabulario, no de regla.

Los falsos positivos que la revisión a mano había identificado **ya no están**: `C:\users.txt`
(script que el alumno revisa), `politica_vacaciones_parte1/2.txt` (listado de ejemplo) y
`./openai_key.txt` (*docstring* de uso).

**B6 (12).** Ocho son imposibles por simple lectura: instalar Ubuntu Server 24.04 en 15 minutos
con 65 bloques (fortinet `02-00-01`), 5 minutos con 31 bloques (`261008-LFS158`), snapshots de
VMware en 15 con 36 bloques (`251215-virtualizacion`), etc. Los otros cuatro caen en la **banda
marginal** donde el umbral ya no distingue: 1,5–1,9 min/paso y 0,53–0,72 min/bloque
(`260617-TPRACT-DES-COPCHAT` ×2, `260728-angular-essentials` ×2). No se tocan sin etiqueta: son
el siguiente frente, y la pregunta no es el umbral sino si B6 debe bloquear en la banda.

### 25.5 Los 16 exonerados por marcador, revisados

Cuatro clases, todas con el mismo significado —«esto lo tiene que poner alguien, y la guía lo
dice»—, y ninguna oculta un defecto que el instructor no vaya a ver:

- `260629-COP_CHAT_COMP_Priv` `07-00-01` (7 ficheros): «Estos archivos deben estar disponibles en
  el sitio de SharePoint del curso antes de iniciar. **Solicítalos a tu instructor** si no los
  localizas.» Entre ellos `Politica_Vacaciones.pdf`, que la revisión a mano de §24.5 había
  marcado como falso positivo.
- `260628-COP_CHAT_EHS-Priv` (4): tabla de requisitos con «✅ **Confirmado por el instructor**» y
  «✅ Preparado por el instructor» en la fila del fichero.
- `261012-COP-ABAST-FINAN-LD-Priv` (3): «**El instructor debe confirmar** que la carpeta de fuentes
  contiene los siguientes archivos ficticios y anonimizados:» sobre la tabla de ficheros.
- `260917-IA-Generativa-Usuarios-Finales-M365-C` (2): «**el instructor debe confirmar**» en la
  tabla de archivos que hay que descargar antes del laboratorio.

### 25.6 La corrección prescrita ahora converge

La §24.7 midió que el camino que el propio Writer prescribe —escribir `[POR CONFIRMAR]` junto a la
mención— **no** limpiaba el hallazgo, y el reintento acababa en `RuntimeError`. Ahora sí: el
marcador exime el referente, el laboratorio queda sin altas y el reintento cierra. Las dos
instrucciones llevan el mismo criterio por primera vez: `mensaje_de_correccion` pide el marcador y
`marcas_de_confirmacion` lo reconoce.

### 25.7 Lo que sigue

1. **B6 en la banda marginal** (4 de 12): o se etiqueta a mano para decidir si son defecto, o se
   deja de bloquear en la banda y solo se registra.
2. **Nivel 3 escrito en prosa** («Nota para el instructor», «verificar que el sitio contenga»):
   añadirlo al vocabulario quitaría 1 de los 8 B1. Es un cambio de lista, con prueba de camino
   vivo y medición.
3. **A1 sigue sin bloquear y le quedan falsos positivos**: de los 45 de alta, `/_prometheus/metrics`
   (una ruta de API de Couchbase) o `P11_Clasificacion_Demanda_SOLUCION.xlsx` (un ejemplo de
   nomenclatura) no son entradas. A1 los registra y no los usa para tumbar nada, que es su sitio.
4. **B3p sigue en registro** (212 altas): sin evidencia de que sean defecto.
5. **El efecto cascada no se volvió a contrastar** con/sin borrado tras el estrechamiento; los
   tres casos de §24.8 siguen en la lista y siguen siendo defectos reales por sí mismos.

### 25.8 Reproducibilidad de este apartado

Además de lo de §24.9:

- `medir_ab1_vivo.py` — versión con `marcados`; salida en `prueba/ab1_final3.txt`.
- `ver_users_txt.py` — el caso `C:\users.txt`: apariciones, si están en bloque y qué decide cada
  función.
- `medir_marcados.py` y `prueba/marcados.json` — la primera pasada de revisión de exoneraciones
  (la que descubrió las 70 y los dos falsos positivos del detector).
- `verificar_desplegado.py` — descarga el artefacto de cada Lambda y comprueba que lleva
  los símbolos nuevos y que las dos copias desplegadas de `referent_check.py` son idénticas.
- `probar_desplegado.py` — importa el `referent_check.py` **descargado de la Lambda** y ejecuta
  los cuatro estrechamientos: 6/6.
- Pruebas de camino vivo en `test_referent_check.py` (128 en total): `test_el_marcador_por_confirmar_exime_el_referente`,
  `test_el_marcador_de_la_introduccion_exime_las_filas_de_la_tabla`,
  `test_un_nombre_que_solo_vive_en_un_bloque_de_codigo_no_es_entrada`,
  `test_un_fichero_nombrado_en_prosa_sigue_siendo_entrada`,
  `test_la_duracion_estimada_del_metadato_se_lee`,
  `test_la_duracion_de_un_desglose_toma_el_mayor`,
  `test_b6_no_marca_un_laboratorio_con_duracion_compuesta`,
  `test_un_listado_de_python_no_es_un_marcador`,
  `test_una_cerca_huerfana_no_saca_el_codigo_del_bloque`,
  `test_para_confirmar_no_es_un_marcador`,
  `test_una_plantilla_completar_no_exime`.

## 26. B6 en la banda marginal: los casos leídos y el umbral medido (23/10/2026)

§25.7 dejó abierto un frente: 4 de los 12 laboratorios que B6 marcaba estaban en una «banda
marginal» —1,5–1,9 min/paso y 0,53–0,72 min/bloque— donde, se dijo, el umbral ya no distingue.
La pregunta no era el número sino la política: ¿B6 debe bloquear en esa banda o solo registrar?
Este apartado lee los cuatro enteros, encuentra un decimotercero que §25 no podía ver, mide dónde
cae el umbral en el corpus y cierra la decisión.

### 26.1 Los cuatro, leídos

| Laboratorio | Declara | Pasos | Bloques | min/paso | min/bloque | Qué pide de verdad |
|---|---|---|---|---|---|---|
| `260617-TPRACT-DES-COPCHAT` / `02-00-03` | 10 min | 6 | 19 | 1,67 | 0,53 | mini proyecto de IMC con Copilot, **un commit por paso** (6), diario de intervenciones con una entrada por paso, `pylint` y README |
| `260617-TPRACT-DES-COPCHAT` / `04-00-02` | 9 min | 5 | 15 | 1,80 | 0,60 | dos ficheros, prompt estructurado, `flake8` **y** `pylint`, informe de evidencias y **rúbrica de evaluación** con tabla de niveles |
| `260728-angular-essentials` / `06-00-01` | 12 min | 8 | 27 | 1,50 | 0,44 | `ng new` (instala `node_modules`), `ng serve`, tres `ng generate`, dos plantillas HTML, dos hojas de estilo y el `AppComponent` |
| `260728-angular-essentials` / `06-00-02` | 13 min | 7 | 18 | 1,90 | 0,72 | componente hijo con `@Output`, dos componentes con sus plantillas y tres comprobaciones de compilación |

Los cuatro son **imposibles**, y no por el ritmo: por el trabajo. En el primero, solo el diario con
una entrada por paso y los seis commits no caben en 10 minutos. En el segundo, la rúbrica de
evaluación es una página y los dos linters se ejecutan dos veces. En los dos de Angular, la
instalación inicial de `ng new` consume por sí sola 1–3 minutos y después hay que escribir dos
plantillas y dos hojas de estilo completas.

La etiqueta anterior —«marginal»— era de ritmo, no de contenido: se puso mirando 1,5–1,9 min/paso
sin leer los pasos. Leídos, son 4/4 verdaderos positivos.

### 26.2 El decimotercero: el que §25 no podía ver

`251031-oracle19c-recovery-tuning-01` / `01-04-01`, 15 minutos, 8 pasos y 25 bloques
(1,9 min/paso, 0,60 min/bloque): pide escribir **ocho documentos** con heredoc —árbol de decisión,
dos scripts de runbook, checklist pre/post, calendario de simulacros, contactos y escalaciones,
preguntas tipo OCP, script de generación de reporte e índice maestro— y validarlos. Imposible.

§25 no lo contó porque su inventario exigía `outline.json` y ese proyecto no lo tiene; el barrido
por guías sí lo ve. La consecuencia es de **población, no de medida**: el total de §25 (20
bloqueantes en 1.196 laboratorios) sigue siendo cierto para la población que midió; sobre la
población por guías son **21 en 21 laboratorios** (1.196 + las 52 guías de esos 6 proyectos sin
`outline`, ≈1,7 %). B6 pasa de 12 a **13**.

### 26.3 De dónde sale la duración: del plan, no de la guía

| Laboratorio | Declarada en la guía | `plan.estimated_duration` | `plan.duration_minutes` |
|---|---|---|---|
| `260617` / `02-00-03` | 10 | 10 | ausente |
| `260617` / `04-00-02` | 9 | 9 | ausente |
| `260728` / `06-00-01` | 12 | 12 | ausente |
| `260728` / `06-00-02` | 13 | 13 | ausente |

La guía no estima: copia el único campo que el plan escribe, `estimated_duration`; `duration_minutes`
no aparece en ninguno de los 13 planes (el camino vivo lo consulta como respaldo y aquí nunca se
usa). Y no son cuatro: **los 13 marcados** tienen la duración de la guía igual a `estimated_duration`.

El patrón se ve mejor en un módulo entero: los nueve laboratorios del módulo 05 de `260225-DESSEGV`
(`05-00-01` … `05-00-09`) declaran **12 minutos todos**, con cargas que van de 22 a 42 bloques. Eso
no es una estimación: es una constante por módulo.

Conclusión: el defecto nace en el **planificador**, el Writer lo copia y B6 lo detecta aguas
abajo. La corrección de fondo es estimar por carga (pasos × bloques), y es trabajo del
planificador, no de la regla.

### 26.4 Dónde cae el umbral en la distribución

Población: **647 laboratorios comparables** (proyecto con plan, guía, al menos 3 pasos con acción,
al menos 1 bloque y duración). Los otros 549 no son «limpios»: B6 no se pronuncia sin datos.

| min/paso | Laboratorios |
|---|---|
| < 1,0 | 0 |
| 1,0 – 1,5 | 3 |
| 1,5 – 2,0 | 12 |
| 2,0 – 3,0 | 30 |
| 3,0 – 5,0 | 124 |
| ≥ 5,0 | 478 |

| min/bloque | Laboratorios |
|---|---|
| < 0,25 | 2 |
| 0,25 – 0,5 | 38 |
| 0,5 – 0,75 | 75 |
| 0,75 – 1,0 | 93 |
| 1,0 – 1,5 | 140 |
| 1,5 – 2,5 | 154 |
| ≥ 2,5 | 145 |

- **15 de 647 (2,3 %) están por debajo de 2,0 min/paso**; 478 (74 %) están en 5 o más. El umbral de
  2,0 está en el percentil 97,7: no está en una pendiente, está en el extremo de la cola.
- 115 (17,8 %) están por debajo de 0,75 min/bloque. Si B6 mirara solo esa razón marcaría 115: la
  **conjunción** es lo que lo hace usable, porque un laboratorio hecho de muchos comandos triviales
  por paso tiene una razón baja sin ser imposible. La unidad que lleva la señal es el paso; el
  bloque filtra.
- Marca **13 (2,0 %)**.

Y un hallazgo incómodo: **B6 se queda corto**. Hay 16 laboratorios sin marcar con
min/bloque < 1,0 y 2,0 ≤ min/paso < 2,5; **10 de ellos con min/bloque < 0,5**, peor que varios de
los marcados: `260225-DESSEGV` / `05-00-09` (12 min, 6 pasos, 42 bloques: 2,0 min/paso y
0,29 min/bloque, 17 s por bloque), `260722-Certified-Kubernetes-Administration` / `06-00-03`
(17 min, 51 bloques), `260629-Temario-contenedores-Azure` / `05-01-01` (21 min, 54 bloques).
Escapan porque **2,0 no es menor que 2,0**. Son falsos negativos de frontera, no falsos positivos.

### 26.5 Decisión: el umbral no se toca

1. **Cero falsos positivos sobre los 13.** Los cuatro de 26.1 y el de 26.2 se leyeron enteros; los
   ocho restantes ya se habían leído en §25.4. El criterio de 0 FP sobre N reales se cumple, y B6
   ya bloquea: la pregunta era si dejaba de hacerlo.
2. **Aflojar habría perdido verdaderos positivos.** Dejar de bloquear en la banda (o subir los
   umbrales) habría dejado B6 en 9, los bloqueantes en 17, y habría dejado sin marcar los 10 casos
   de 26.4, que son peores que los que se habrían liberado.
3. **Endurecer no es gratis.** Pasar la conjunción a disyunción, o subir min/paso a 2,5, añadiría
   unos 10 bloqueantes (21 → ~31) sin una decisión de producto, y va contra «estrechar antes de
   endurecer».

Se mantienen `_MINUTOS_POR_PASO_ACCION = 2.0` y `_MINUTOS_POR_BLOQUE = 0.75`. La banda no era de
ruido: era de defectos reales con un ritmo menos extremo. El falso negativo de frontera queda
documentado como conocido; corregirlo exigirá aceptar más bloqueo, y eso es una decisión explícita.

### 26.6 Pruebas que fijan los dos lados

`_lab_tipo_angular(duracion)` reproduce la forma del caso real —8 pasos, 27 bloques, `ng new` +
tres `ng generate` + plantillas y estilos— y dos pruebas la usan con distinta duración:

- `test_b6_marca_el_caso_angular_de_12_minutos`: 1,5 min/paso y 0,44 min/bloque → marca, con
  confianza alta.
- `test_b6_no_marca_el_mismo_caso_angular_con_45_minutos`: 5,62 y 1,67 → no marca.

Mover cualquiera de los dos umbrales rompe uno de los dos lados. `test_referent_check.py`:
**130/130**.

### 26.7 Lo que sigue

1. **El planificador**: estimar por carga (pasos × bloques) en vez de por módulo. Es la raíz de
   26.3 y quitaría de golpe la mayor parte de los 13.
2. **El falso negativo de frontera** de 26.4: decidir si 2,0 exacto debe marcar. Requiere aceptar
   más bloqueo.
3. Sin cambios, el resto de §25.7.

### 26.8 Reproducibilidad de este apartado

- `revisar_b6_marginal.py` → `prueba/b6_marginal.txt`: los cuatro laboratorios paso a paso.
- `medir_b6_umbral.py` → `prueba/b6_umbral.txt`: duración de guía y de plan de los cuatro, y la
  distribución sobre los 647 comparables.
- `listar_b6_marcados.py` → `prueba/b6_marcados.txt`: los 13, con la duración de cada fuente.
- `ver_oracle_010401.py`: el decimotercero, paso a paso.
- `test_referent_check.py`: 130/130, incluidas las dos de 26.6.

## 27. Tres estrechamientos más y el falso negativo de B6, medidos (23/10/2026)

§26 cerró B6 con una decisión y dejó una lista de frentes. Este apartado ataca los estrechamientos
que no endurecen nada —nivel 3 escrito en prosa y dos falsos positivos de A1—, lee los diez
laboratorios que B6 **no** marca y decide qué hacer con ellos.

### 27.1 Qué se cambió

| Estrechamiento | Dónde | Qué hace ahora |
|---|---|---|
| (e) nivel 3 en prosa | `_NOTA_INSTRUCTOR_RE`, `_VERIFICACION_PRESENCIA_RE`, `marcas_de_confirmacion` | una **nota a quien imparte** que pide verificar que el material está en un sitio, carpeta o repositorio exime el referente y lo devuelve en `marcados` |
| (f) lista de ejemplos | `_EJEMPLO_PARENTESIS_RE`, `_es_ejemplo` | en «(ej. 'X_BASE.xlsx', 'X_SOLUCION.xlsx')» el segundo nombre también es nomenclatura: el paréntesis **abre** con «ej.» o «ej:» |
| (g) endpoint de métricas | `_SEGMENTOS_API` | `/_prometheus/metrics` es una URL de servicio, no un fichero del curso |

Los tres son de la misma familia que §25: quitan ruido sin dejar pasar un defecto, y ninguno cambia
lo que bloquea.

### 27.2 Los controles negativos, que son la mitad de la regla

El marcador (e) **no** es «nota para el instructor» a secas. Una nota que solo declara una entrada
(«el alumno trabajará con `X`») seguiría ocultando un defecto real, así que se exige que la misma
prosa pida **verificar la presencia** en un sitio, carpeta o repositorio. Tres pruebas fijan los
tres lados:

- la nota del caso real (pide verificar que SharePoint contenga los archivos) **exime**;
- la nota que solo describe el uso de un fichero **no** exime (B1 se mantiene);
- la nota en otro párrafo **no** exime (el ámbito es el párrafo del referente, no la página).

El marcador (f) tenía un riesgo que la primera versión no acotaba: `ej\s*\.?` casaba con
«(ejercicio 3: `Datos_Privados_Q3.xlsx`)» y habría exonerado una entrada real. Se exige el punto
(«ej.») o el separador («ej:»), y una prueba lo fija.

### 27.3 La medición

Mismo corpus, misma población y mismo borrado de A1 en el plan (el camino vivo):

| | §25 (antes) | §27 (después) | |
|---|---|---|---|
| A1 hallazgos | 1.432 | **1.428** | −4: los cuatro son falsos positivos |
| A1 de alta | 45 en 13 planes | **43 en 11 planes** | −2 |
| A1 de baja | 1.387 | **1.385** | −2 |
| B1 de alta | 8 | **7** | la nota de nivel 3 |
| B1 de baja | 550 | **544** | −6 |
| B6 de alta | 12 | **12** | sin cambios |
| **Altas bloqueantes** | **20 en 20 laboratorios** | **19 en 19 laboratorios** | −1 |
| Exonerados por marcador | 16 | **20** | +4 |

La población es la de §25 (proyectos con `outline`, plan y guías). La población por guías de §26
suma un laboratorio más —el proyecto de Oracle sin `outline`—: allí B6 son 13 y las bloqueantes 21;
aquí no entra porque §27 no lo toca.

No se compararon totales: se comparó **hallazgo a hallazgo** contra el volcado de §25
(`a1_corpus.json` y `ab1_vivo.json`). En A1 desaparecen 4 y aparecen 0; en B desaparecen 7 y
aparecen 0. Los 11 son falsos positivos:

- A1: `P11_Clasificacion_Demanda_SOLUCION.xlsx` (alta) y `/_prometheus/metrics` (alta) son los dos
  que se buscaban; `books_static.csv` (baja) estaba en «(ej: api_weather.json, books_static.csv)», y
  `/Documents/automatizacion-python` (baja) en «(p. ej. `C:\Users\<usuario>\Documents\…`)».
- B1: seis en el laboratorio de nóminas —los tres normativos que se marcaban por ruta (uno de alta)
  y por nombre (tres de baja)—; el cuarto, `LFT_Vigente_Ficticio.pdf`, no llegaba a marcarse. Los
  cuatro pasan a `marcados` (16 → 20). El séptimo es `lesson/SqlInjection.lesson` (baja) en
  `260225-DESSEGV`/`03-00-03`, dentro de «(ej: `/WebGoat/start.mvc#lesson/SqlInjection.lesson`)».

### 27.4 El falso negativo de frontera, leído

§26.4 dejó 10 laboratorios con menos de 0,5 min/bloque que B6 no marca porque `2,0` no es menor que
`2,0`. Leídos los diez, **todos son imposibles**:

| Laboratorio | Declara | Pasos / bloques | Qué pide |
|---|---|---|---|
| `260225-DESSEGV` / `05-00-01` | 12 min | 6 / 38 | VAmPI *mass assignment*: explotar, leer el código vulnerable, escribir un DTO y verificar |
| `260225-DESSEGV` / `05-00-02` | 12 min | 6 / 36 | crAPI BOLA: `git clone` + `docker compose`, explotar, servidor Flask y reporte |
| `260225-DESSEGV` / `05-00-03` | 12 min | 6 / 38 | middleware de logging, tocar endpoints, repetir los ataques y generar reporte |
| `260225-DESSEGV` / `05-00-05` | 12 min | 5 / 32 | crAPI fuga de datos: script, `venv`, corrección y reporte comparativo |
| `260225-DESSEGV` / `05-00-06` | 12 min | 5 / 29 | crear tres versiones de API, gateway Nginx, explotar BOLA y reportar |
| `260225-DESSEGV` / `05-00-07` | 12 min | 5 / 25 | fuerza bruta, Flask-Limiter con Redis, validar y documentar |
| `260225-DESSEGV` / `05-00-09` | 12 min | 6 / 42 | headers de seguridad, CORS, OWASP ZAP en daemon, Dockerfile seguro y rebuild |
| `261008-LFS158` / `04-00-01` | 10 min | 5 / 34 | explorar la API de Kubernetes, manifiesto del namespace y documento de análisis |
| `260722-Certified-Kubernetes-Administration` / `06-00-03` | 17 min | 7 / 51 | minikube de tres nodos, DNS entre namespaces y CoreDNS en CrashLoop |
| `260629-Temario-contenedores-Azure` / `05-01-01` | 21 min | 10 / 54 | RBAC en AKS, Defender for Containers y ACR en 21 minutos |

Siete de los diez son el **mismo módulo** de `260225-DESSEGV`, todos con 12 minutos: la misma
constante por módulo que §26.3, ahora vista desde el lado de los falsos negativos.

Son **falsos negativos**, no falsos positivos. Y la decisión es **no endurecer**: pasar la
conjunción a disyunción —o añadir un umbral de min/bloque— metería ~10 bloqueantes más (19 → ~29)
sin una decisión de producto, y la dirección acordada es estrechar antes de endurecer. Queda
documentado con la lista leída: si se corrige, será con un cambio explícito y medido, no de paso.

### 27.5 Pruebas y despliegue

`test_referent_check.py`: **136/136**. Nuevas: las tres del marcador (e), la de la lista de ejemplos
(f), la del control «ejercicio», la del endpoint (g) y las dos de B6 de §26.6.

Despliegue verificado **sobre el artefacto de la Lambda**, no sobre el fuente: `StrandsLabWriter` y
`StrandsLabPlanner` con `LastModified` 2026-10-23T23:15:03, los cinco símbolos nuevos presentes y
las dos copias de `referent_check.py` idénticas (`sha256[:16] = f07f1d149e6b98d1`). El módulo
descargado de la Lambda ejecuta los cinco casos: 5/5.

### 27.6 Lo que sigue

1. **El planificador**: estimar por carga en vez de por módulo (§26.3). Es la raíz de los 12 de B6
   y de los 10 de §27.4.
2. **La cascada, medida.** Con el borrado de A1 en el plan (el camino vivo) hay **7 B1 de alta y 19
   bloqueantes**; sin el borrado, **5 y 17**. La diferencia son 6 referentes que solo aparecen con
   el borrado —2 de alta, `Lab04_Plan_Cierre_Fiscal.xlsx` y `licenses.txt`, y 4 de baja— y
   **ninguno** que solo aparezca sin él. El borrado no crea el defecto: deja de taparlo. El plan
   declaraba esos ficheros en falso y B1 los saca a la luz. Se mantiene.
3. Sin cambios: el resto de §25.7 (`step_structure`, Fase 3, C1, manifiesto de entradas).

### 27.7 Reproducibilidad de este apartado

- `medir_ab1_vivo4.py` → `prueba/ab1_final4.txt` y `ab1_final4.json`: la medición completa.
- `comparar_a1.py`: A1 antes/después sobre la misma población, hallazgo a hallazgo.
- `dif_b.py`: la diferencia de B, hallazgo a hallazgo.
- `medir_cascada.py` con `AB1_SIN_BORRADO=1` → `prueba/ab1_cascada.txt`: la cascada de §27.6.
- `perfilar_frontera.py` → `prueba/frontera_perfil.txt`: los diez de §27.4, paso a paso.
- `probar_estrechamientos3.py`: los cinco casos del marcador y de los ejemplos, aislados.
- `verificar_desplegado27.py` y `probar_desplegado27.py`: el artefacto de la Lambda.
- `test_referent_check.py`: 136/136.

## 28. Lo que cerró la noche del 23 al 24/10 (24/10/2026)

Tres frentes y un triaje, todos medidos sobre la salida real. El plan y el estado de cada uno
quedaron en `docs/relevo-noche-2026-10-23.md`.

### 28.1 B6 dice el mínimo de duración

El hallazgo de B6 ya no solo dice «12 minutos para 8 pasos y 27 bloques»: añade
`duracion_minima = ceil(max(pasos × 2,0, bloques × 0,75))`, el valor a partir del cual la duración
deja de ser contradictoria. Es **informativo**: no entra en `mensaje_de_correccion` (hay una prueba
que lo fija), porque la duración viene del plan y pedirle al Writer que la cambie no convergería.

Se llama **mínima** y no «sugerida» a propósito: en `260728-angular-essentials`/`06-00-02` da 14
minutos para un laboratorio que, leído, necesita bastante más. Responde «¿por debajo de qué es
imposible?», que es la pregunta de B6, no «¿cuánto tarda?».

| Laboratorio | Declara | Mínimo |
|---|---|---|
| `260924-…fortinet…` / `02-00-01` | 15 | **49** |
| `260924-…fortinet…` / `02-00-03` | 15 | **44** |
| `251215-virtualizacion` / `02-00-01` | 15 | **27** |
| `260728-angular-essentials` / `06-00-01` | 12 | **21** |
| `261008-LFS158` / `01-00-01` | 5 | **24** |
| `260617-TPRACT-DES-COPCHAT` / `04-00-02` | 9 | **12** |

Verificado sobre las **12 guías reales**, no sobre el sintético: `12/12` con el mínimo esperado
(`prueba/duracion_minima.txt`). Pruebas: **137/137**. Despliegue verificado sobre el artefacto de la
Lambda: `LastModified` 2026-10-24T03:47:49, las dos copias de `referent_check.py` idénticas
(`sha256[:16] = 44efcc5088167ec7`) y el módulo descargado ejecuta los cinco casos de §27 y §28 (5/5).

Queda anotada una inconsistencia que no se toca: el mensaje de corrección pide «3 minutos por paso y
1 por bloque», mientras la regla marca por debajo de 2,0 y 0,75. El margen parece deliberado —pedir
más de lo mínimo para que el reintento converja—, y moverlo exigiría medir reintentos reales.

### 28.2 `step_structure`: no son 291, son 6.715, y no son contenido

La cifra que arrastraba la lista de pendientes era de una medición parcial. Sobre **1.298 guías**,
`ContentValidator.validate_lab` emite **6.715 avisos** `step_structure`; 922 guías no tienen
ninguno y el resto reparte hasta 141.

El patrón no es un defecto de las guías: el validador exige `**Objective:**`, `**Instructions:**` y
`**Verification:**` en cada paso. Las guías usan `**Objetivo:**` en 1.100 casos y `**Verificación:**`
en 826, pero `**Instructions:**` solo en 39: el Writer no emite esa etiqueta, escribe la instrucción
como prosa numerada con bloques.

Es un `WARNING` de un validador que **no está en el camino de generación** (el Writer valida con
`referent_check`), así que no bloquea ni dispara reintentos. **Decisión: no se toca.** Si algún día
entra en el pipeline, el arreglo es alinear la etiqueta o aceptar la forma en español —no relajar la
comprobación sin medir qué deja pasar.

### 28.3 Las 43 altas de A1: no hay ruido que quitar

Se agruparon por campo: 31 en `prerequisites`, 2 en `scope`, 9 en `special_considerations` y 1 en
`software_requirements[].installation_notes`. Las tres que parecían artefactos de proyecto se
leyeron:

- `requirements.txt` — «Proveer un archivo requirements.txt con versiones fijadas en el repositorio
  del curso»: es material del curso que el temario no declara.
- `docker-compose.yml` — «El repositorio del curso contiene docker-compose.yml, configuraciones de
  Logstash…»: lo mismo.
- `data/raw/atenciones_historicas.csv` — «Archivo de entrada oficial… los participantes no deben
  sobrescribirlo»: es el dataset de entrada, el caso más claro de todos.

**43/43 son verdaderos positivos**: el plan pide material que el temario no declara. No hay patrón
que estrechar, y por tanto **no se cambia A1**. La causa es la misma que la de los 7 B1 de §27: el
temario no declara su material. A1 lo detecta antes de que exista la guía, que es su sitio.

### 28.4 Informe para autores

`docs/informe-bloqueantes-2026-10-23.md`: los 19 bloqueantes con su párrafo exacto, por qué son
reales y, en B6, el mínimo de duración; más un anexo con los 10 laboratorios que la regla no marca y
también son imposibles. Generado de `ab1_final4.json`, no redactado de memoria.

### 28.5 Lo que sigue

1. **La decisión de producto**: ¿la duración del temario es un presupuesto (el Writer acorta el
   laboratorio) o una estimación (entonces B6 no debería bloquear)? Los 12 B6 ya llevan el mínimo;
   falta decidir qué se hace con él.
2. **Los temarios**: 19 bloqueantes y 43 altas de A1 son, en el fondo, el mismo defecto de contenido.
   El informe de 28.4 es el traspaso.
3. **Fase 3 (A2/B7/B8)**: sigue sin definir; necesita su propia spec.
4. Sin cambios: C1 de enlaces y manifiesto de entradas con hash.

## 29. La duración se garantiza: la banda (24/10/2026)

Decisión de producto del 24/10/2026: **la duración del temario se debe garantizar**. Se admiten
desviaciones, pero no exageradas; el ejemplo que la define es un laboratorio declarado en 60 minutos
que en la realidad puede durar 50, 70 o como máximo 80. Y el enfoque del proyecto queda explícito:
**no se corrigen los cursos existentes**; se corrige el sistema para que las generaciones futuras y
las actualizaciones salgan mejor.

### 29.1 La regla

La franja se define sobre la duración declarada: **suelo 5/6** y **techo 4/3** (60 → 50 y 80). El
tiempo real se estima por carga con los ritmos mínimos que ya usaba B6:
`mínimo = max(pasos × 2,0, bloques × 0,75)`. La desviación es un hecho cuando **ni con esos ritmos
el trabajo cabe en el techo**: `mínimo > 4/3 × declarada`.

| | Antes (§28) | Ahora |
|---|---|---|
| Condición | `min/paso < 2,0` **y** `min/bloque < 0,75` | `mínimo > 4/3 × declarada` |
| Campo del hallazgo | `duracion_minima` | `duracion_minima` y `duracion_maxima` |
| Mensaje de corrección | «3 min por paso y 1 por bloque» | «debe caber en el techo» |

**El suelo no se comprueba, y es una decisión medida, no un olvido.** La carga es una **cota
inferior** del tiempo: sirve para demostrar «no cabe», pero no «sobra». Aplicar el suelo marcaría
**361 de 647** laboratorios, casi todos sesiones largas con pocos bloques —288 minutos declarados con
6 pasos y 13 bloques, 216 con 7 y 11—, donde la carga no demuestra nada. Queda documentado hasta que
exista otra señal (la lista de actividades del temario, por ejemplo).

### 29.2 La medición

| Clase | Laboratorios | % de 647 |
|---|---|---|
| Desviación alta (no cabe ni en el mejor caso) | **56** | 8,7 % |
| Dentro de la franja | 230 | 35,5 % |
| Desviación baja (no comprobable) | 361 | 55,8 % |

De los 12 que marcaba §28, **10 siguen marcando y 2 pasan a «dentro»**: `04-00-02` (mínimo 12, techo
12) y `06-00-02` (mínimo 14, techo 17). Los **46 nuevos** son el tipo de caso que §26.4 había
identificado como falso negativo: muchos bloques y pocos minutos. Tres leídos:

- `260430-Linux-2h`/`01-00-01`: 30 min, 71 bloques (`cd`, `mkdir`, `touch`, `rm`; pasos de 9 a 15
  bloques) → mínimo 54, techo 40.
- `260313-python-moderno-automatizacion`/`04-00-01`: 25 min, 68 bloques y cinco módulos escritos →
  mínimo 51, techo 33.
- `261008-LFS158`/`03-00-01`: 10 min, 21 bloques con `docker build`, `docker run` y una matriz de
  análisis → mínimo 16, techo 13.

Los 56 están en 18 proyectos. Sumando los 7 B1, la regla marcaría **24 de los 164 proyectos
(14,6 %)**, frente a 12 (7,3 %) antes. Ese número **no es una lista de tareas**: es la medida de cómo
se comporta la regla sobre el corpus, que aquí es banco de pruebas.

### 29.3 Qué significa para el sistema

En una generación futura, un laboratorio que no quepa en su franja dispara el reintento: el Writer
recorta pasos y bloques hasta caber. Si no lo consigue, el curso falla con los dos números en el
mensaje —«necesita al menos X, el hueco admite Y»—, que es la señal correcta para el temario.

El precio es explícito: **un laboratorio que se recorta para caber pierde profundidad**. Cuando el
hueco es absurdo (5 minutos para 31 bloques), el sistema entregará un laboratorio pequeño y correcto
en duración, no el laboratorio que el temario describía. La alternativa —generar el laboratorio
imposible— es peor: el alumno no puede terminarlo. La corrección de fondo sigue estando en el
temario, y el informe de §28.4 es el diagnóstico, no el traspaso.

### 29.4 Verificación

- `test_referent_check.py`: **140/140**. Nuevas: la franja admite 60 declarados con 75 de trabajo y
  marca con 81; `06-00-02` (13 declarados, 14 de mínimo, 17 de techo) no marca; el mensaje da el
  techo y prohíbe cambiar la duración.
- Sobre guías reales: los **12** de §27 reclasificados como predijo la medición (10 alta, 2 dentro) y
  **3** de los 46 nuevos, con sus bloques leídos (`15/15`).
- Despliegue verificado sobre el artefacto de la Lambda: `LastModified` 2026-10-24T17:40:45, copias
  idénticas (`sha256[:16] = 62cf3cbe6e96a344`) y el módulo descargado ejecuta la banda y los
  estrechamientos de §27 (**6/6**).

### 29.5 Lo que sigue

1. **El suelo de la franja** necesita una señal que no sea la carga (lista de actividades del
   temario). Hoy no se comprueba y está medido por qué.
2. **El pre-flight del temario**: avisar antes de generar cuando el hueco por práctica es
   implausible. Es la única forma de que el autor lo vea antes del fallo.
3. Sin cambios: Fase 3 (A2/B7/B8), C1 y el manifiesto de entradas.

## 30. Pre-flight de duración: el temario avisa antes de generar (24/10/2026)

B6 habla cuando la guía ya existe. El pre-flight habla **antes**: con el temario y el plan en la
mano, sin pasos ni bloques. No sustituye a B6; cubre el tramo en el que todavía se puede corregir el
temario sin haber gastado ocho generaciones.

### 30.1 Qué comprueba

Por cada módulo del temario, con los laboratorios que el plan deriva de él:

- `presupuesto_practica = duration_minutes × percent_practice / 100`.
- `por_laboratorio = presupuesto_practica / número de laboratorios del módulo`.
- `pedido_actividades`: la suma de las duraciones **declaradas** por las actividades de laboratorio.

Dos señales, ambas con los números a la vista:

| Señal | Cuándo | Qué dice |
|---|---|---|
| `sobre_comprometido` | `pedido_actividades > presupuesto_practica` | el temario pide más laboratorio del que presupuesta |
| `poco_tiempo` | `por_laboratorio < 12` | el hueco por laboratorio no da para una práctica |

Dos decisiones que hicieron falta para que la medida fuera honesta:

1. **Solo se suma lo que el temario declara.** La primera versión sumaba 30 minutos por defecto a las
   actividades sin duración (el mismo defecto que usa el planificador) y fabricaba sobre-compromisos
   que no estaban escritos: 68 proyectos avisados en vez de 65.
2. **El suelo de 12 no separa perfecto.** Calibrado sobre 156 proyectos: con 12 minutos habría
   avisado en 4 de los 5 proyectos que luego tienen un B6 de alta, con 13 avisos en proyectos sin B6.
   Por eso es un **aviso**, no un error.

El resultado se guarda en `metadata.preflight_duracion` del plan y se imprime en el log. **No bloquea
la generación**: el temario es el contrato y corregirlo no es una decisión del generador.

### 30.2 La medición

Sobre 165 proyectos con laboratorios y temario:

| | |
|---|---|
| Proyectos con algún aviso | **65 (39,4 %)** |
| Señales `sobre_comprometido` | 177 módulos |
| Señales `poco_tiempo` | 49 módulos |
| Proyectos con B6 de alta que quedan avisados | **5 de 6** |

Los tres avisos más claros:

- `260225-DESSEGV`, módulo 5: 9 actividades de 12 min (108) contra 85,5 de presupuesto → **9,5 min por
  laboratorio**. Es el origen de los nueve laboratorios de 12 minutos de §26.
- `260502-FOR-LOG-Priv`, módulo 1: 8 laboratorios, 96 min pedidos contra 63 de presupuesto →
  **7,9 min por laboratorio**.
- `261005-Custom-MS-4004-2`, módulo 1: 12 laboratorios, 97 contra 95 → **7,9 min por laboratorio**.

El único proyecto con B6 de alta que no queda avisado es `251215-virtualizacion`: su temario sí
presupuesta tiempo suficiente, y el defecto está en el laboratorio que el Writer escribió con 36
bloques para 15 minutos. Es exactamente la clase de defecto que solo B6 puede ver.

### 30.3 Qué no hace

- **No bloquea**: avisa. Un temario con 39 % de inconsistencias no puede detener la generación sin
  una decisión de producto.
- **No corrige el temario**: no puede, es el documento aprobado. El aviso es para quien lo edita.
- **No sustituye a B6**: sin pasos ni bloques no sabe si el laboratorio cabe; solo si el temario
  tiene tiempo para intentarlo.

### 30.4 Verificación

- `test_referent_check.py`: **145/145**. Nuevas: el caso de 9 × 12 contra 85,5 (dos señales), el
  temario consistente, el módulo sin laboratorios, el módulo sin porcentaje de práctica y el **camino
  vivo**: el handler real guarda el aviso en `metadata.preflight_duracion`.
- Despliegue verificado sobre el artefacto de la Lambda: `LastModified` 2026-10-24T18:52:44, copias
  idénticas (`sha256[:16] = 4fb79a323d2d8322`), el handler del planificador lleva la llamada y el
  módulo descargado ejecuta el pre-flight y la banda de §29 (**3/3**).

### 30.5 Lo que sigue

1. **Decidir si el pre-flight debe llegar al autor antes de aprobar el temario**, no solo al log de
   generación. Es la diferencia entre «avisar» y «evitar».
2. **B8**: censo de marcadores y decisión de vocabulario.
3. Sin cambios: el suelo de la banda de §29 y Fase 3 (A2/B7/B8).

## 31. A2: el temario manda en las cantidades (24/10/2026)

El informe del instructor describe dos fallos que ninguna regla cubría: «cambió el escenario de
**seis fondos a tres**» y «sustituyó **CIBEST CAPITAL** por Northstar Digital». Este apartado ataca el
primero. Y lo hace en el plano donde nace: el **plan**, no la guía.

### 31.1 Qué se hizo

| Dónde | Qué |
|---|---|
| `auditar_plan` (planificador) | añade violaciones `A2` cuando el plan cambia una cantidad del temario; el mensaje de corrección las separa de A1 |
| `reconciliar_cantidades` (planificador) | **copia** del temario la cifra desviada antes de auditar: `«tres fondos» → «6 fondos»`. Como A3 con la duración y A5 con el objetivo, no depende de que el modelo acierte |
| `auditar_cantidades` (Writer) | segunda línea: si la guía cambia la cifra, `A2` con confianza alta y reintento |

La extracción compara **cifra + sustantivo** en prosa (nunca dentro de bloques de código) y solo
cuando el sustantivo es el mismo en el temario y en el artefacto. El temario es la fuente; si no
declara la cantidad, no se comprueba nada.

### 31.2 Los filtros, y por qué están (medidos)

La primera versión era ingenua y produjo **146 hallazgos**. Leídos, casi todos eran ruido de tres
clases:

1. **Palabras función y unidades** como sustantivo («dos con», «30 min»).
2. **Cantidades dentro de instrucciones**: «documenta 3 escenarios», «anticipa al menos 10
   escenarios», «cree una tabla con diez mensajes». No describen el escenario: lo mandan.
3. **Contenedores genéricos** con otro sentido: «escenario», «idea», «etapa», «enfoque».

Con esos filtros, 146 → **11**. Al leerlos, apareció la pauta que faltaba: **9 de los 11 tenían un
«1» a un lado** («1 idea» en el temario frente a «tres ideas» en la guía), que es otro referente, no
un cambio de escenario. Se exige **pluralidad a pluralidad** (`min(esperado, obtenido) ≥ 2`):

| Versión | Hallazgos en guías |
|---|---|
| Ingenua | 146 |
| Con función/unidades + instrucciones + genéricos | 11 |
| \+ pluralidad (regla final) | **2** |

Y los 2 son el caso real. En el plan: **1 de 165 planes**, la misma course, en
`lab_plans[0].scope`.

### 31.3 El caso real, verificado en el temario

`260915-Custom-MS-4019-ESP-CC-LD-Priv`:

- **Temario:** «…en el contexto de CIBEST CAPITAL… una revisión interna de **seis fondos
  multiactivo** ficticios… archivos con seis fondos denominados **Fondo A-F**».
- **Plan:** «Los estudiantes trabajarán con un conjunto de datos simulados de **tres fondos**
  (Fondo A, B y C)».
- **Guías 02-00-01 y 02-00-02:** «análisis comparativo de **tres fondos**».

Es exactamente la queja del informe, y el desvío está en el plan. Con A2 el plan se **corrige a 6
antes** de la auditoría (`reconciliar_cantidades`), y las guías se comprueban después como segunda
línea. Tras reconciliar los 165 planes, **quedan 0 A2**.

### 31.4 Límites, explícitos

- **Solo cantidades.** Los **nombres** («CIBEST CAPITAL» → «Northstar Digital») son A2 v2 y necesitan
  su propia medición: hay nombres de producto y encabezados que se confunden con entidades.
- **Solo pluralidad a pluralidad.** Un cambio de «1» a «N» no se marca; medido: 9 de 11 eran ruido de
  ese tipo.
- **Solo prosa.** Una cifra dentro de un bloque de código o de una salida no es una afirmación.
- **Lista de genéricos basada en evidencia.** Puede crecer; cada entrada nueva debe venir de un
  hallazgo leído, no de una intuición.

### 31.5 Verificación

- `test_referent_check.py`: **156/156**. Nuevas: la guía que cambia la cifra, la misma cantidad en
  palabra o dígito, los sustantivos de estructura, el bloque de código, la fuente que no declara, el
  singular frente a lista, el plan que desvía, el plan correcto y la reconciliación (unidad y **camino
  vivo del planificador**, que guarda `quantity_integrity` y el `scope` ya corregido).
- Corpus: 2 en guías, 1 en planes, 1 corrección, 0 restantes.
- Despliegue verificado sobre el artefacto de la Lambda: `LastModified` 2026-10-24T21:35:14, copias
  idénticas (`sha256[:16] = 2fc2071e138bffc2`), el planificador lleva la reconciliación y
  `quantity_integrity`, y el módulo descargado ejecuta los cuatro casos (**4/4**).

### 31.6 Lo que sigue

1. **A2 v2: nombres propios** que no aparecen en el temario ni en el manual, con los filtros de A1
   (productos conocidos, encabezados, código). Medir antes de bloquear.
2. **B4: estabilidad entre laboratorios** — la misma entidad o cifra no cambia de una práctica a otra.
3. El mapa de conformidad de §30.2 queda con una fila menos pendiente: entidades y cantidades ya
   tienen regla para las cantidades.

## 32. A2 v2 y B4: dos reglas descartadas por medición (24/10/2026)

Después de A2 v1 (§31), quedaban dos quejas del informe: los **nombres** («CIBEST CAPITAL» →
«Northstar Digital») y la **estabilidad de cifras entre prácticas**. Las dos se implementaron hasta
poder medirlas y las dos se descartaron: no separan señal de ruido. El trabajo dejó, eso sí, un
arreglo real en A2.

### 32.1 A2 v2 (nombres propios): no viable

La hipótesis: si un nombre de la guía no aparece en el temario, es inventado. La extracción
—secuencias de dos o más palabras capitalizadas, en prosa, sin encabezados ni bloques— se midió
sobre el corpus:

| | |
|---|---|
| Guías | 1.246 |
| Guías con algún candidato | **1.246 (100 %)** |
| Nombres distintos | **14.670** |
| Apariciones | **43.129** |

Los más frecuentes no son entidades inventadas: «Salida Esperada» (1.299), «Nivel Bloom» (779),
«Microsoft Edge» (539), «Intel Core» (523), «Copilot Studio» (404), «Carlos Mendoza» (140). La razón
es estructural: **el temario describe un curso y la guía es el curso**. La guía nombra herramientas,
productos, personas de ejemplo y encabezados que el temario no tiene por qué nombrar. «No está en el
temario» es casi todo.

**No se implementa.** Cazar una sustitución de nombre exige que alguien declare la lista de entidades
del escenario, o un modelo semántico. No es una regla que podamos inventar.

### 32.2 B4 (estabilidad entre prácticas): no viable con recuentos de superficie

La idea: si un laboratorio dice «seis fondos» y otro «tres», al menos uno está mal. Se probaron los
dos ámbitos posibles:

| Comparación | Discrepancias | Proyectos afectados |
|---|---|---|
| Contra el temario (sustantivos que no declara) | **312** | 99 de 164 |
| Contra el plan (sustantivos que el plan declara) | **66** | 46 de 169 |

Los casos son, casi todos, recuentos que **varían legítimamente** por laboratorio: «secciones» 8 y 4
(dos documentos distintos), «meses» 6 y 18 (dos ventanas de datos), «personas» 5 y 50 (un dataset de
50 frente a cinco usuarios), «imágenes» 8, 15 y 3, «aplicaciones» 25, 45 y 10.

El problema es el mismo que en A2 v1: **el sustantivo no distingue un parámetro del escenario de un
recuento de la práctica**. Sin un modelo que declare qué cifras son del escenario, la regla marca
entre el 27 % y el 60 % de los cursos.

**No se implementa.** Se llegó a cablear en el Writer y se revirtió antes de desplegar: sus 312
discrepancias habrían llenado el registro de ruido. La función y sus pruebas no se quedan en el
código; el resultado se documenta aquí.

### 32.3 El arreglo que sí salió de aquí

La prueba de camino vivo del Writer con dos guías (6 y 3 fondos) destapó un fallo de A2: el filtro de
instrucciones miraba 110 caracteres hacia atrás y **se comía el encabezado del paso**. En «### Paso
1: Revisar\nEl escenario tiene seis fondos», el verbo «Revisar» convertía la frase siguiente en
instrucción y la cantidad se descartaba: un falso negativo silencioso.

Ahora la ventana se corta en el inicio de la frase (salto de línea, punto o dos puntos). Efecto
medido: A2 pasa de **2 a 3** hallazgos en guías, y el tercero es el mismo caso real
(`260915`/`03-00-02`, «tres fondos» frente a los seis del temario). Los tres son verdaderos
positivos.

### 32.4 El mapa de conformidad

| Lo que declara el temario | Comprobación | Estado |
|---|---|---|
| Número de prácticas y su duración | A3 + B6 (banda 4/3) | cubierto |
| Objetivo y descripción de cada práctica | A5 | cubierto |
| Entregables | A4 + B3p | cubierto |
| Ficheros y material | A1 / B1 | cubierto |
| Requisitos técnicos | B5 | cubierto |
| **Cantidades** | **A2** (plan y guía) | **cubierto** |
| Nombres de entidades | — | **no viable sin lista declarada** |
| Estabilidad de cifras entre prácticas | — | **no viable con recuentos de superficie** |

### 32.5 Verificación

- `test_referent_check.py`: **156/156** (se retiraron las 5 pruebas de B4 al retirar la regla).
- Corpus con el filtro corregido: A2 en guías **3/3 verdaderos positivos**; plan sin cambios desde
  §31.
- Despliegue verificado sobre el artefacto de la Lambda: `LastModified` 2026-10-24T23:46:13, copias
  idénticas (`sha256[:16] = 7ea6374c7505ec5d`), y el módulo descargado ejecuta el caso con encabezado
  delante, el de instrucción y la reconciliación del plan (**3/3**).

### 32.6 Lo que sigue

1. **B7 (Setup Guide ↔ laboratorios)** y **B8 (marcadores)**: los dos frentes que quedan de Fase 3.
2. **Nombres y estabilidad** solo si el negocio decide que el temario declare el escenario (lista de
   entidades y cifras). Es una decisión de producto; la regla no puede sustituirla.
3. El resto de §25.7: C1, manifiesto de entradas y observación en producción.
