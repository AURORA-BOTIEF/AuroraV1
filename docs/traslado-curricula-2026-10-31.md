# Traslado a currícula — hallazgos sin actedear de sistema (2026-10-31)

> Origen: `informe-bloqueantes-2026-10-23.md` (§27) + observación de producción (§42–§43).
> Este documento separa lo que **el sistema ya cierra** de lo que requiere **edición del material**
> y lo que pide una **decisión de negocio**. Los editores de currícula pueden trabajar con este
> texto: cada ítem trae qué escribir, no solo qué está mal.

---

## 0. Estado del sistema frente al informe del 23/10

| Hallazgo | Sistema (desde la noche del 23) | Qué queda |
|---|---|---|
| B6, duración imposible (12 + 10 del anexo) | **Cerrado de sistema**: banda 4/3 (§29) que ya marca los del anexo; **presupuesto de duración** en el Writer (§41) que hace que el laboratorio quepa o falle con los números a la vista; pre-flight (§30) que avisa **antes de generar** | Editar los temarios si se van a actualizar esos cursos (§2) |
| B1, ficheros sin declarar (7) | **Cerrado de sistema**: el Writer reintenta con B1 y el registrable queda en el informe (`validation/`); el hallazgo no desaparece sin el temario | Trasladar a currícula (§1) |
| Ficheros que el plan inventa (nuevo, 28/10) | **Registrado en informe** (`validation/referential-integrity.json`); el criterio "aparece en un lab y ningún paso lo crea" separa el riesgo | Decisión de negocio + más cursos para calibrar (§3) |
| Suelo de la banda en labs GUI (M365 Copilot) | Sin señal posible con el esquema actual | Que currícula declare la lista de actividades del temario (§4) |

**Regla de oro que no cambia:** el proyecto no corrige los cursos existentes. Las secciones §1–§3
solo aplican a los cursos que currícula vaya a actualizar o volver a generar.

---

## 1. B1 — declarar en el temario los ficheros que los laboratorios usan (7)

Corrección, curso por curso, con el texto sugerido para el temario (campo `files` / `fuentes` del
módulo o de la práctica, como el editor ya tiene):

| Curso / laboratorio | Fichero | Texto sugerido en el temario |
|---|---|---|
| `251209-copilot-365-4-h` / 03-00-01 | `Ventas_MultiRegional_2024.xlsx` | Material del curso (entrada): `Ventas_MultiRegional_2024.xlsx` — disponible en OneDrive del curso |
| `260627-COP-CHAT-LEGAL` / 01-00-01 | `Lab02_Reporte_Automatizado.xlsx` | Material del curso (entrada): `Lab02_Reporte_Automatizado.xlsx`, en OneDrive |
| `260627-COP-CHAT-LEGAL` / 04-00-01 | `Lab04_Plan_Cierre_Fiscal.xlsx` | Igual que el anterior, junto con los otros dos archivos de práctica |
| `260628-COP_CHAT_EHS-Priv` / 01-00-01 | `REFERENCIA-NORMAS-EHS.docx` | Material del curso: `REFERENCIA-NORMAS-EHS.docx` en carpeta `Lab01` (o marcar `[POR CONFIRMAR]` si lo aporta el instructor) |
| `260629-COP_CHAT_COMP_Priv` / 02-00-01 | `Lab02_Claves_Respuesta.pdf` | Material del **instructor** (rol explícito): `Lab02_Claves_Respuesta.pdf` |
| `260803-temario-vmware-vsphere-foundation` / 03-00-01 | `licenses.txt` | Material del instructor: `licenses.txt` (archivo de licencias) |
| `260805-temario-agentes-microsoft-365-copilot` / 01-00-01 | `Datos_Financieros_Q4.xlsx` | Material del curso (entrada): `Datos_Financieros_Q4.xlsx`, en OneDrive |

Con la declaración hecha, la próxima regeneración del curso sale sin el hallazgo (el Writer valida
B1 contra temario + manual y reintenta): no hace falta editar los laboratorios a mano.

---

## 2. B6 — duraciones que no caben en su hueco (t): actualizar el temario

Con la banda 4/3 como definición (§29) y presupuesto de duración en el Writer (§41), los remedios
aplicables a un curso que se vaya a **actualizar o regenerar** son dos: subir la duración del
laboratorio hasta su mínimo (o más) o reducir su alcance. Dejar la cifra significa que el sistema
recortará el laboratorio para que quepa (queda correcto en duración, más corto que el temario describía)
o fallará con «necesita al menos X, el hueco admite Y».

| Curso / laboratorio | Declara hoy | Mínimo (pasos/bloques) | Duración sugerida |
|---|---|---|---|
| `251215-virtualizacion` / 02-00-01 | 15 | 27 (9/36) | **≥ 27** |
| `260225-DESSEGV` / 05-00-08 | 12 | 26 (7/34) | **≥ 26** |
| `260617-TPRACT-DES-COPCHAT` / 02-00-03 | 10 | 15 (6/19) | **≥ 15** (§41: 6 pasos, 19 bloques → 15) |
| `260617-TPRACT-DES-COPCHAT` / 04-00-02 | 9 | 12 (5/15) | **≥ 12** |
| `260728-angular-essentials` / 06-00-01 | 12 | 21 (8/27) | **≥ 21** |
| `260728-angular-essentials` / 06-00-02 | 13 | 14 (7/18) | **≥ 14** |
| `260924-Temario-fortinet…` / 01-00-01 | 9 | 18 (6/23) | **≥ 18** |
| `260924-Temario-fortinet…` / 01-00-02 | 9 | 20 (7/26) | **≥ 20** |
| `260924-Temario-fortinet…` / 02-00-01 | 15 | 49 (9/65) | **≥ 49** (instalación de Ubuntu Server) |
| `260924-Temario-fortinet…` / 02-00-03 | 15 | 44 (8/58) | **≥ 44** (VM Windows 11) |
| `260924-Temario-fortinet…` / 04-00-01 | 18 | 43 (11/57) | **≥ 43** |
| `261008-LFS158` / 01-00-01 | 5 | 24 (4/31) | **≥ 24** (arranque de clúster) |

**Anexo (10 que hoy marca la banda):** los del informe del 23/10 (`260225-DESSEGV` 05-00-01…09,
`261008-LFS158`/04-00-01, `260722-…K8s`/06-00-03, `260629-Temario-contenedores-Azure`/05-01-01) ya
entran en la banda (§29) con el mismo criterio: su duración declarada no cabe ni al ritmo mínimo.
Los mínimos van en el informe original y el conteo por módulo, cuando los editores abran esos
temarios, aplicará igual.

---

## 3. Nuevo caso de producción — ficheros que el plan inventa (SEM-M365)

`261027-SEM-M365-COP-CHAT-…-Priv`: 18 ficheros con nombre inventado por el **plan** y **15 que
aparecen de verdad en los laboratorios** como entradas que el estudiante abre (medición §43.4).

| Fichero | Dónde lo pide el lab (campo del plan) |
|---|---|
| `BancaMovil_Semana4.docx` | prerequisites del práctica 6 |
| `EBancaEmpresarial_Semana4.docx` | ídem |
| `AdopcionCanales_Semana4.docx` | ídem |
| `Reporte_Consolidado_Semana3.docx` / `_Semana4.docx` | prerequisites del práctica 10 |
| `Consolidado_Hitos_Compromisos.docx` | scope del práctica 7 |
| `Proyectos_CambiosPresupuestoRiesgos.xlsx` / `Matriz_Riesgos_Ejecutiva.docx` | scope del práctica 8 |
| `Informe_Direccion.docx` / `Informe_Operativo.docx` | scope del práctica 9 |
| `Mobile_Banking_Responses.xlsx` | scope del práctica 24 |
| `Banking_Sector_Outlook_2024.docx`, `Tech_Specs.docx`, `Commercial_Terms.docx`, `Security_Recs.docx` | scope del práctica 22 |
| `Reporte_Ejecutivo_TransformacionDigital.pptx` | expected_outcomes del práctica 10 |
| `POL-RRHH-2024-V2.pdf`, `Solution_Architecture_DigitalChannels_v3.docx` | special_considerations del temario |

**Qué hacer, dos alternativas:** (a) si esos ficheros deben existir, declararlos como material del
curso en el temario (y subirlos al repositorio del curso); (b) si el laboratorio los debe crear en
paso propio, retocar la mención del plan para que diga «se genera en el paso N». El criterio registrado
«aparece en un lab y ningún paso lo crea» es el que el sistema registraría; la dirección de la
regla (informativa hoy) depende de la decisión de negocio.

---

## 4. Decisión pedida a currícula (no a editores de temario)

1. **Lista de actividades del temario** (no solo duración total): es la única señal que permite
   comprobar el *suelo* de la banda en laboratorios GUI (M365 Copilot), donde no hay bloques shell.
   El generador ya la consumiría como hace con `lab_activities`.
2. **¿La regla de ficheros inventados pasa a bloqueante?** Hoy registra; la calibración necesita
   más cursos de producción. La decisión no urge, pero sirve para decidir qué medimos en el próximo
   informe.
3. **Estandarización**: vocabulario `[POR CONFIRMAR]` / `[POR VALIDAR]` y convención de prefijos de
   folder (`YYMMDD`) — cosmético, no urgente.

---
*Generado el 31/10/2026 desde `informe-bloqueantes-2026-10-23.md` y las mediciones §40–§44
(especificación `spec-integridad-referencial-labs.md`). Cada sección lleva el origen para reproducir.*
