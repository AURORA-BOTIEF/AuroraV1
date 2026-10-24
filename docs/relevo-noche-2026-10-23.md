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
