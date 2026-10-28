# Relevo — trabajo autónomo de la noche del 23 al 24/10/2026

Este fichero es el punto de reanudación y, a la vez, el informe de la mañana. Se actualiza al
cerrar cada frente.

## Objetivo

Cerrar tres frentes con medición real (B6 accionable, informe para autores, `step_structure`) y
dejar un cuarto (triaje de A1) cerrado o con propuesta, sin tocar nada que dependa de una decisión
de producto.

## Reglas

1. Solo se commitea en verde: baterías de pruebas antes de cada commit.
2. Antes de creer, medir: cada afirmación lleva su artefacto en `prueba/` y su contexto.
3. Solo cambios aditivos o que exoneran. Nada que aumente el bloqueo ni que cambie el contrato del
   temario (A3).
4. Un frente, un commit, un push. Si un frente pasa de su tope, se para, se anota y se sigue.
5. Ante ambigüedad, opción conservadora y decisión anotada abajo. No se espera respuesta.
6. No se toca `main`, ni la capa PDF, ni el contrato de aprobación.

## Línea base (23/10/2026, 23:59)

| | |
|---|---|
| Rama | `testing` = `origin/testing`, árbol limpio |
| HEAD | `e8ba99d` (spec §27) |
| Desplegado | `StrandsLabWriter` y `StrandsLabPlanner`, `LastModified` 2026-10-23T23:15:03, `referent_check.py` idéntico (`sha256[:16] = f07f1d149e6b98d1`) |
| Pruebas | `test_referent_check.py`: 136/136 |
| Corpus | 164 proyectos, 1.196 laboratorios (población de §25) |
| A1 | 1.428 hallazgos; 43 de alta en 11 planes |
| B1 | 7 de alta (550 de baja) |
| B6 | 12 de alta |
| Bloqueantes | **19 en 19 laboratorios** |
| Exonerados por marcador | 20 |

Población por guías (§26, incluye el proyecto de Oracle sin `outline`): B6 13 y 21 bloqueantes.

## Fases

| # | Frente | Estado | Entregable |
|---|---|---|---|
| F0 | Estado base y relevo | **hecho** | este fichero + lista de los 19 |
| F1 | B6 accionable (`duracion_minima`) | **hecho** | campo, pruebas, 12/12 reales, deploy verificado, §28.1 |
| F2 | Informe para autores | **hecho** | `docs/informe-bloqueantes-2026-10-23.md` |
| F3 | `step_structure` | **hecho** | medición (6.715 avisos) y decisión de no tocar, §28.2 |
| F4 | Triaje de las 43 altas de A1 | **hecho** | 43/43 verdaderos positivos, §28.3 |
| F5 | Cierre | en curso | baterías, §28, relevo final, push |

## Decisión de diseño de F1

El campo será **`duracion_minima`**, no «duración sugerida»: es el mínimo con el que la duración
deja de ser contradictoria, calculado con los umbrales vigentes
(`ceil(max(pasos × 2,0, bloques × 0,75))`). No es una estimación realista y no debe leerse como tal:
en `260728-angular-essentials`/`06-00-02` da 14 minutos para un laboratorio que, leído, necesita
bastante más. El valor sirve para responder «¿por debajo de qué es imposible?», que es exactamente
la pregunta de B6.

El campo es **informativo**: no entra en `mensaje_de_correccion`. Si el Writer intentara «cambiar la
duración», no puede (viene del plan) y el reintento no convergería.

## Los 19 bloqueantes

> **Nota del 24/10.** Con la banda de §29, la regla marca 56 de duración y dos de estos doce pasan a
> «dentro». Esta tabla es el diagnóstico del 23/10, no una lista de tareas: el proyecto corrige la
> generación futura, no los cursos existentes.

| Proyecto / laboratorio | Regla | Valor | Mínimo (B6) |
| `251209-copilot-365-4-h` / `03-00-01` | B1 | `Ventas_MultiRegional_2024.xlsx` | — |
| `251215-virtualizacion` / `02-00-01` | B6 | 15 min, 9 pasos, 36 bloques | 27 |
| `260225-DESSEGV` / `05-00-08` | B6 | 12 min, 7 pasos, 34 bloques | 26 |
| `260617-TPRACT-DES-COPCHAT` / `02-00-03` | B6 | 10 min, 6 pasos, 19 bloques | 15 |
| `260617-TPRACT-DES-COPCHAT` / `04-00-02` | B6 | 9 min, 5 pasos, 15 bloques | 12 |
| `260627-COP-CHAT-LEGAL` / `01-00-01` | B1 | `Lab02_Reporte_Automatizado.xlsx` | — |
| `260627-COP-CHAT-LEGAL` / `04-00-01` | B1 | `Lab04_Plan_Cierre_Fiscal.xlsx` | — |
| `260628-COP_CHAT_EHS-Priv` / `01-00-01` | B1 | `REFERENCIA-NORMAS-EHS.docx` | — |
| `260629-COP_CHAT_COMP_Priv` / `02-00-01` | B1 | `Lab02_Claves_Respuesta.pdf` | — |
| `260728-angular-essentials` / `06-00-01` | B6 | 12 min, 8 pasos, 27 bloques | 21 |
| `260728-angular-essentials` / `06-00-02` | B6 | 13 min, 7 pasos, 18 bloques | 14 |
| `260803-temario-vmware-vsphere-foundation` / `03-00-01` | B1 | `licenses.txt` | — |
| `260805-temario-agentes-microsoft-365-copilot` / `01-00-01` | B1 | `Datos_Financieros_Q4.xlsx` | — |
| `260924-Temario-fortinet-certified-fundamentals-cybersecurity` / `01-00-01` | B6 | 9 min, 6 pasos, 23 bloques | 18 |
| `…fortinet…` / `01-00-02` | B6 | 9 min, 7 pasos, 26 bloques | 20 |
| `…fortinet…` / `02-00-01` | B6 | 15 min, 9 pasos, 65 bloques | 49 |
| `…fortinet…` / `02-00-03` | B6 | 15 min, 8 pasos, 58 bloques | 44 |
| `…fortinet…` / `04-00-01` | B6 | 18 min, 11 pasos, 57 bloques | 43 |
| `261008-LFS158` / `01-00-01` | B6 | 5 min, 4 pasos, 31 bloques | 24 |

Lista completa con el párrafo exacto de cada hallazgo: `prueba/bloqueantes_27.md` (generada de
`ab1_final4.json`, no escrita a mano).

## Resultados de la noche

| Frente | Qué se midió | Resultado |
|---|---|---|
| F1 | `duracion_minima` sobre las 12 guías reales | 12/12 con el mínimo esperado; 137/137 pruebas |
| F1 | Despliegue | `LastModified` 2026-10-24T03:47:49, hash `44efcc5088167ec7`, 5/5 con el módulo descargado |
| F2 | Informe | 19 bloqueantes con párrafo, causa y mínimo; anexo con los 10 falsos negativos |
| F3 | `step_structure` | **6.715 avisos** (no 291) en 1.298 guías; 922 limpias; es plantilla, no contenido |
| F4 | Altas de A1 | 43/43 verdaderos positivos; 31 en `prerequisites`; 0 falsos positivos |

**F3 — corrección del registro.** La cifra de «291» era de una medición parcial. El validador exige
`**Objective:**`, `**Instructions:**` y `**Verification:**`; las guías usan `**Objetivo:**` (1.100) y
`**Verificación:**` (826), pero `**Instructions:**` solo en 39. Es un `WARNING` de un validador que
no está en el camino de generación: **no se toca**.

**F4 — las tres que parecían ruido.** `requirements.txt` («proveer un archivo … en el repositorio del
curso»), `docker-compose.yml` («el repositorio del curso contiene …») y
`data/raw/atenciones_historicas.csv` («archivo de entrada oficial») son material del curso que el
temario no declara. **43/43 son verdaderos positivos; A1 no se toca.**

**Producción.** No hubo ejecuciones de `StrandsLabWriter` ni de `StrandsLabPlanner` en las 8 horas
posteriores al despliegue: no hay tráfico que observar todavía. Queda pendiente para la primera
generación real.

**Fase 3.** Borrador de alcance en `docs/fase-3-borrador.md`: A2 no puede empezar sin decidir de
dónde sale la lista de entidades; B7 es autocontenido (Setup Guide contra laboratorios, con riesgo
de circularidad); B8 es un censo de marcadores más una decisión de vocabulario.

## Continuación — 24/10

**Decisión:** la duración del temario se garantiza, con banda 5/6–4/3 (60 → 50–80). **No se corrigen
los cursos existentes**: el corpus es banco de pruebas y los hallazgos son diagnóstico, no backlog.

**Implementado y desplegado:** B6 marca cuando `mínimo > 4/3 × declarada`, con `duracion_minima` y
`duracion_maxima` en el hallazgo y el techo en el mensaje de corrección. 140/140 pruebas; 12/12 + 3
guías reales; artefacto verificado (`17:40:45`, `62cf3cbe6e96a344`, 6/6). Spec §29.

**Medido:** 56 de 647 laboratorios con desviación alta (10 de los 12 anteriores + 46 nuevos), 230
dentro, 361 de desviación baja **no comprobable** (la carga es cota inferior: no prueba «sobra
tiempo»). Con los 7 B1, la regla marcaría 24 de 164 proyectos (14,6 %) frente a 12 (7,3 %).

**Lo que sigue:** el suelo de la banda necesita otra señal; el *pre-flight* del temario es la forma de
que el autor vea un hueco implausible antes de generar.

**Pre-flight (spec §30).** Implementado en el planificador: por módulo, presupuesto de práctica
(`duration × percent_practice`) contra el pedido declarado por las actividades y contra el tiempo por
laboratorio (suelo de 12 min, calibrado). Se guarda en `metadata.preflight_duracion` y **no bloquea**.
Medido sobre 165 temarios: 65 con aviso (39,4 %), y **5 de los 6** proyectos con B6 de alta quedan
avisados antes de generar. 145/145 pruebas (incluido el camino vivo del handler).

**A2 (spec §31).** El temario manda en las cantidades. En el **plan**: `reconciliar_cantidades` copia
la cifra del temario antes de auditar (determinista, como A3/A5) y `auditar_plan` verifica. En la
**guía**: `auditar_cantidades` con reintento. Medido: 146 hallazgos en la versión ingenua → 11 con
filtros de instrucciones/genericos → **2** con la regla de pluralidad; los 2 son el caso del informe
(`260915`: temario «seis fondos… Fondo A-F» con CIBEST CAPITAL, plan y guías «tres fondos»). En el
plan: **1 de 165**, corregido; **0 A2 restantes**. 156/156 pruebas y despliegue verificado
(`21:35:14`, `2fc2071e138bffc2`, 4/4).

**B8 (spec §33).** Censo: **160 marcadores en 56 formas** sobre 1.298 guías. La familia
`[X POR VALIDAR]` (63 de `[VERSIÓN POR VALIDAR]` en 23 guías, más `[VALIDAR CON FUENTE]`,
`[POR VALIDAR]`, `[X64/ARM64 POR VALIDAR]`) ya cuenta como marcador y exime el referente. De paso se
cerró un falso negativo del detector: `[NOMBRE DE TAREA DEPENDIENTE]` casaba dentro de
«DE**PENDIENTE**»; ahora la marca exige palabra completa. Medido: exonerados 20 → 21 (el nuevo es
`/labs/taskflow-app`, un directorio de trabajo), altas de B1 sin cambios (7). 158/158 y despliegue
verificado (`02:22:07`, `e6e8b71c57760da1`, 3/3).

**A2 v2 y B4 (spec §32): descartadas por medición.** Nombres propios: **1.246 guías, el 100 % con
candidatos, 14.670 nombres**; «no está en el temario» es casi todo (productos, encabezados, personas
de ejemplo). Estabilidad entre prácticas: **312 discrepancias en 99 proyectos** contra el temario y
**66 en 46** contra el plan; casi todas son recuentos legítimos («4 vs 9 diapositivas», «6 vs 18
meses»). Ninguna se despliega. A cambio, la prueba de camino vivo destapó un fallo de A2: el filtro
de instrucciones se comía el encabezado del paso; acotado a la frase, A2 pasa de 2 a 3 hallazgos
(los tres del caso real). 156/156 y despliegue verificado (`23:46:13`, `7ea6374c7505ec5d`, 3/3).

**B7 (spec §34).** El Setup Guide perdía lo que el curso necesita por dos causas deterministas:
`build_software` deduplicaba por **subcadena** («GitHub Copilot» caía por «git», «MongoDB Compass» por
«mongodb», «python-dotenv» por «python»): **65 de 172 planes** perdían software; y `build_accesses`
truncaba a 12 (**110 de 172** con más de 12). Arreglado: dedup por nombre exacto y sin tope. Medido:
software perdido **65 → 0**; accesos incompletos **110 → 1**, y ese uno es una deducción real. 161/161
y artefacto verificado (`SetupGuideBuilderFunction`, `03:09:40`).

**A6 (spec §35).** El temario es la fuente principal, no la única: petición (opcional) → plan →
laboratorios → Setup Guide. Hallazgo: el planificador extraía `context_topics` y los usaba en su
prompt, pero **no los guardaba** en el plan, y el writer no los imprimía. La alineación dependía del
`scope` y la teoría. Medición sobre 1.246 labs: cobertura mediana **70 %** (módulo) y **83 %**
(lección); **39 labs por debajo del 34 %** (3,1 %). Arreglo: `_heredar_del_temario` en el planificador
y `_resumen_de_labs` en el writer. 165/165 y artefactos verificados (`02:07:41`).

**A7 (spec §36).** La Setup Guide se genera después de los laboratorios (consume la matriz y la
preparación de los `lab-*.md`), pero ignoraba la petición del curso: **18 de 172 planes** traen
`additional_requirements` y la guía solo leía `software_requirements`. Ahora entra literal en el JSON
y en el PDF, solo si existe. La unión software plan ∪ herramientas de los laboratorios se midió y **no
se despliega**: el escáner no distingue host de invitado (`npm` dentro de un contenedor no exige Node).
167/167 y artefacto verificado (`02:32:37`).

**Cobertura de tópicos (spec §37).** Los 39 labs por debajo del 34 % no son 39 desalineados: 10 tienen
tópicos en inglés y laboratorio en español, y de los 29 restantes casi todos son labs de módulo cuyo
denominador son todos los tópicos del módulo (un lab no cubre ocho lecciones). **No se crea el
marcador**: sería ruido, como A2 v2 y B4. El arreglo de §35 se queda por diseño.

**Setup Guide en el flujo y auditoría posterior (spec §38–§39).** La guía ya no se invoca a mano:
`InvokeLabGuideBuilder → InvokeSetupGuide → InvokePostGenerationAudit → NotifyCompletion`, con
`Catch` a `NotifyCompletion` en los dos estados nuevos (un fallo no invalida un curso ya generado).
De paso, el ARN escrito a mano de `InvokeLabGuideBuilder` pasa a `${LabGuideBuilderArn}`. La auditoría
escribe `labguide/inputs-manifest.json` (SHA-256 de temario, manual, plan, laboratorios y guía) y
`labguide/enlaces.json`. C1 medido sobre 1.313 laboratorios: 5.150 enlaces públicos, 3.870 vivos, 831
muertos, 449 no verificables; el crudo era ruido (hosts internos, IPs privadas, plantillas,
namespaces). No bloquea: 831 candidatos serían un falso positivo masivo. 7/7 + 7/7 + 15/15 y
despliegue verificado (`03:23:49`).

**Prueba real de punta a punta (spec §40).** Curso completo sobre `271027-prueba-a6-a7` (temario
Docker copiado de `260515-Docker-desde-cero`, sin manual) con la petición «Docker 24.0, Compose v2,
Ubuntu 24.04, sin Docker Desktop»: `prueba-a6-a7-1793118636` **SUCCEEDED** en ~20 min, 217 eventos,
25 tareas. A6: `context_topics` 4 y 4, cobertura **100 % y 82 %** (mediana del corpus 70 %). A7:
`additional_requirements` literal en plan y guía; Ubuntu 24.04 LTS, Docker Engine 24.0.9, Compose
2.24.5, nada pendiente; «Docker Desktop» solo como prohibición; «Compose v2» llega como requisito de
entorno (plugin 2.24.5), no como ejercicio, que el temario no pide. Flujo con `InvokeSetupGuide` e
`InvokePostGenerationAudit`; manifiesto 1/0/1/2/2. Único hallazgo: 2 «muertos» que eran la misma
plantilla `hub.docker.com/r/<usuario>/…` cortada por `<` y por `\`; `urls_de` la descarta ahora
(8/8) y, reauditado el proyecto con el código desplegado, **16 públicos, 15 vivos, 0 muertos, 1 no
verificable**. Los 4 `[POR CONFIRMAR]` están en hardware `recommended` (el temario no los declara):
previstos, no defecto. Duración 72/120 min, sin aviso de pre-flight.

**B6 como presupuesto (spec §41).** El negocio confirma que los tiempos del temario se cumplen. La
medición lo explicó: sobre 625 laboratorios comparables la carga mínima mediana es **0,57** de la
declarada (p90 1,30) y la prueba real del §40 había dado **1,15 y 0,96**: el Writer no se quedaba
corto, escribía pegado al techo (4/3) porque solo veía «Duration: N minutes». `presupuesto_de_duracion`
deriva de los ritmos de B6 cuántos pasos y bloques caben (36 min → máximo 18 y 48; objetivo 13 y 34)
y llega al plan, al prompt, al resumen y al reintento, que ahora apunta a la declarada. Repetida la
ejecución con la misma petición: ratio **0,92 y 0,79**, pasos 8 → 13 y 7 → 13, bloques 55 → 44 y 46 →
38, cobertura 100 % y 73 % (la caída es vocabulario del título, no contenido), sin reintentos. El
suelo sigue sin comprobarse: con el ritmo holgado marcaría el 55,7 % del corpus. 170/170 + 18/18 +
15/15 + 7/7 y despliegue verificado.

## Decisiones pendientes para la mañana

1. Los 7 B1 son defectos de **contenido**: el temario no declara ficheros que el laboratorio usa.
   Se corrigen en el temario, no con una regla. El informe de F2 los deja listos para trasladar.
2. Los 12 B6 tienen un mínimo calculado, pero la decisión de fondo sigue abierta: ¿la duración del
   temario es un **presupuesto** (el Writer debe acortar el laboratorio) o una **estimación**
   (entonces B6 no debería bloquear)? No se toca sin decisión.
3. Fase 3 (A2/B7/B8) sigue sin definir. Si sobra tiempo, se deja un borrador de alcance, no código.

## Cómo reanudar

1. Leer este fichero y la fase marcada «en curso».
2. Comprobar `git status`, `git log -3` y que `testing` = `origin/testing`.
3. Si hay una medición a medias, su artefacto está en `prueba/`.
4. Continuar por la primera fase «pendiente».
