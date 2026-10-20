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


