# Informe para autores — 19 hallazgos bloqueantes

> **Nota del 24/10/2026.** Con la banda de duración de §29, la regla marca 56 laboratorios de
> duración (y 2 de estos 12 dejan de marcar). Este informe describe el estado del 23/10 y sirve como
> **diagnóstico del sistema**, no como una lista de tareas: el proyecto no corrige los cursos
> existentes, corrige la generación futura.

**Fecha:** 23/10/2026 · **Origen:** medición de §27 sobre 1.196 laboratorios reales
(`prueba/ab1_final4.json`) · **Generado de los datos, no redactado de memoria.**

## Qué es esto y qué significa «bloqueante»

La validación referencial revisa cada curso generado contra su temario y su manual. Un hallazgo
**bloqueante** impide aceptar el curso hasta corregirlo: no es un aviso de estilo. Hoy hay **19
hallazgos en 19 laboratorios**, de dos clases:

- **7 de contenido (B1):** el laboratorio usa un fichero que el temario no declara.
- **12 de duración (B6):** el temario asigna menos tiempo del que el laboratorio necesita.

Ninguno se arregla con una regla nueva: los 19 son defectos reales del material.

## B1 — el temario no declara ficheros que el laboratorio usa (7)

El alumno llega al paso que abre el fichero y no lo tiene. La corrección es **declararlo en el
temario** (o en el manual) o, si depende de una persona, **marcarlo** con `[POR CONFIRMAR]` junto a
su mención.

| Curso / laboratorio | Fichero | Dónde aparece | Qué hacer |
|---|---|---|---|
| `251209-copilot-365-4-h` / `03-00-01` | `Ventas_MultiRegional_2024.xlsx` | «Abra el archivo … desde OneDrive en Excel de escritorio» (Paso 1) | Declararlo como entrada del curso |
| `260627-COP-CHAT-LEGAL` / `01-00-01` | `Lab02_Reporte_Automatizado.xlsx` | «Asegúrate de tener el archivo … en tu OneDrive antes de la próxima sesión» | Declararlo (o marcarlo si lo aporta el instructor) |
| `260627-COP-CHAT-LEGAL` / `04-00-01` | `Lab04_Plan_Cierre_Fiscal.xlsx` | lista de «los tres archivos de práctica cargados en OneDrive» | Declararlo junto a los otros dos |
| `260628-COP_CHAT_EHS-Priv` / `01-00-01` | `REFERENCIA-NORMAS-EHS.docx` | «Verifica que puedes ver los siguientes archivos en la carpeta `Lab01`» | Declararlo; si lo aporta el instructor, marcarlo |
| `260629-COP_CHAT_COMP_Priv` / `02-00-01` | `Lab02_Claves_Respuesta.pdf` | «valores de referencia proporcionados por el instructor en el archivo …» | Declararlo como material del instructor |
| `260803-temario-vmware-vsphere-foundation` / `03-00-01` | `licenses.txt` | tabla: «Archivo de licencias — `licenses.txt` (proporcionado por el instructor)» | Declararlo en el temario |
| `260805-temario-agentes-microsoft-365-copilot` / `01-00-01` | `Datos_Financieros_Q4.xlsx` | solución de problemas: «subir el archivo directamente a OneDrive … y referenciarlo» | Declararlo como entrada del curso |

**Nota sobre `licenses.txt`:** «proporcionado por el instructor» describe una **entrada** (la regla
lo entiende así), y por eso B1 lo marca: el instructor lo aporta, pero el temario no lo declara. No
es un falso positivo; es una dependencia sin documentar.

## B6 — la duración no cabe (12)

La duración la escribe el temario y la guía la copia (A3 fuerza que coincidan). El laboratorio pide
más trabajo del que esa cifra admite. La columna **mínimo** es el valor a partir del cual la
duración deja de ser contradictoria con los umbrales vigentes
(`ceil(max(pasos × 2,0, bloques × 0,75))`); **no es una estimación realista**, es el suelo.

| Curso / laboratorio | Declara | Pasos / bloques | Mínimo | Qué pide el laboratorio |
|---|---|---|---|---|
| `251215-virtualizacion` / `02-00-01` | 15 min | 9 / 36 | **27** | redes virtuales y snapshots de VMware |
| `260225-DESSEGV` / `05-00-08` | 12 min | 7 / 34 | **26** | VAmPI: explotar la amenaza, corregirla y verificar |
| `260617-TPRACT-DES-COPCHAT` / `02-00-03` | 10 min | 6 / 19 | **15** | mini proyecto de IMC con **6 commits** y diario de intervenciones |
| `260617-TPRACT-DES-COPCHAT` / `04-00-02` | 9 min | 5 / 15 | **12** | rúbrica de evaluación, `flake8` y `pylint` |
| `260728-angular-essentials` / `06-00-01` | 12 min | 8 / 27 | **21** | `ng new`, tres `ng generate`, dos plantillas y dos hojas de estilo |
| `260728-angular-essentials` / `06-00-02` | 13 min | 7 / 18 | **14** | componente hijo con `@Output` y tres compilaciones |
| `260924-Temario-fortinet…` / `01-00-01` | 9 min | 6 / 23 | **18** | verificación de requerimientos y configuración |
| `260924-Temario-fortinet…` / `01-00-02` | 9 min | 7 / 26 | **20** | creación de virtual switches LAN y WAN |
| `260924-Temario-fortinet…` / `02-00-01` | 15 min | 9 / 65 | **49** | instalación de Ubuntu Server 24.04 |
| `260924-Temario-fortinet…` / `02-00-03` | 15 min | 8 / 58 | **44** | VM Windows 11 cliente y pruebas |
| `260924-Temario-fortinet…` / `04-00-01` | 18 min | 11 / 57 | **43** | asignación de interfaces a LAN y WAN |
| `261008-LFS158` / `01-00-01` | 5 min | 4 / 31 | **24** | `minikube start` (arranque de clúster) y evidencias |

**Cómo corregir:** subir la duración del laboratorio en el temario hasta el mínimo (o más), o
reducir el alcance del laboratorio. Lo que no funciona es dejar la cifra: la guía la copiará y el
curso volverá a bloquearse.

## Anexo — 10 laboratorios que la regla no marca y también son imposibles

No bloquean porque `min/paso` queda justo en 2,0 y la regla exige que se crucen **los dos**
umbrales. Se leyeron uno a uno y son el mismo defecto:

| Curso / laboratorio | Declara | Pasos / bloques | Mínimo |
|---|---|---|---|
| `260225-DESSEGV` / `05-00-01` | 12 min | 6 / 38 | 29 |
| `260225-DESSEGV` / `05-00-02` | 12 min | 6 / 36 | 27 |
| `260225-DESSEGV` / `05-00-03` | 12 min | 6 / 38 | 29 |
| `260225-DESSEGV` / `05-00-05` | 12 min | 5 / 32 | 24 |
| `260225-DESSEGV` / `05-00-06` | 12 min | 5 / 29 | 22 |
| `260225-DESSEGV` / `05-00-07` | 12 min | 5 / 25 | 19 |
| `260225-DESSEGV` / `05-00-09` | 12 min | 6 / 42 | 32 |
| `261008-LFS158` / `04-00-01` | 10 min | 5 / 34 | 26 |
| `260722-Certified-Kubernetes-Administration` / `06-00-03` | 17 min | 7 / 51 | 39 |
| `260629-Temario-contenedores-Azure` / `05-01-01` | 21 min | 10 / 54 | 41 |

Se incluyen aquí porque comparten la causa —un módulo con muchos laboratorios y una cifra
constante— y conviene corregirlos en la misma pasada.

## Lo que no se cambió, y por qué

- **No se afloja el umbral de B6.** Aflojarlo habría dejado de marcar los 12 (o parte de ellos) sin
  que el material cambiara.
- **No se endurece.** Marcar los 10 del anexo añadiría ~10 bloqueantes más sin una decisión de
  producto sobre si la duración es presupuesto o estimación.
- **No se toca el planificador ni A3.** La duración viene del temario, que se aprueba antes de
  generar; cambiarla en el plan rompería ese contrato.

## Reproducibilidad

- Lista completa con el párrafo exacto: `prueba/bloqueantes_27.md`.
- Medición: `prueba/ab1_final4.json` (y su resumen en `prueba/ab1_final4.txt`).
- Mínimos verificados sobre las guías reales: `verificar_duracion_minima.py` (12/12).
- Perfil de los 10 del anexo: `prueba/frontera_perfil.txt`.
