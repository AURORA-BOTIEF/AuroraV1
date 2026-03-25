# GitHub App (publicación de laboratorios)

THOR usa una **GitHub App** para crear repos **privados**, subir contenido y (si el plan de GitHub lo permite) configurar protección de ramas.

Hay dos modos de propietario del repositorio:

| Modo | Variable `GITHUB_OWNER_TYPE` | Dónde viven los repos | Asientos de org |
|------|------------------------------|------------------------|-----------------|
| **Organización** | `organization` (por defecto) | `github.com/Netec-Mx/...` | Sí: miembros de org / colaboradores pueden chocar con **seat_limit** |
| **Cuenta personal** | `personal` | `github.com/MiUsuarioServicio/...` | No aplica modelo de asientos de **organización**; los **colaboradores** en repos privados de usuario suelen encajar en el plan **gratuito** de GitHub (sin contratar Team/Enterprise) |

## App actual

- **Nombre:** NetecMxApp (propiedad / uso en org Netec-Mx)
- **Organización:** `Netec-Mx`
- Credenciales locales de referencia: carpeta `GithubApp/` (ignorada por git; no commitear `.env` ni `.pem`)

## AWS Secrets Manager

- **Nombre del secreto:** `netec/github-app/aurora-publisher`
- **Formato JSON:**

```json
{
  "app_id": "<GitHub App ID (número)>",
  "installation_id": "<ID de la instalación en la org (número en la URL)>",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "org": "Netec-Mx",
  "personal_access_token": "<solo en modo personal: PAT de la cuenta dueña>"
}
```

El campo **`org` en el JSON** es en realidad el **login del propietario** en GitHub: nombre de la **organización** (modo org) o el **username** de la cuenta personal (modo `personal`). Debe coincidir con la cuenta donde instalaste la App.

### `personal_access_token` (modo `GITHUB_OWNER_TYPE=personal`)

GitHub **no** permite usar el token de **instalación** de la App para `POST /user/repos` (crear repositorio en cuenta de usuario). La API responde **403** `Resource not accessible by integration`. Por eso, en modo personal hay que añadir al JSON un **Personal Access Token** de la misma cuenta que `org` (ej. NetecGk), **solo** para crear el repositorio; el resto de la publicación sigue usando el token de instalación de la App.

- **Classic PAT:** scope **`repo`** (o al menos creación de repos privados).
- **Fine-grained:** cuenta dueña, permisos de repositorio **Contents** y **Administration** (lectura/escritura) en “All repositories” o en los que vaya a crear Aurora.

Opcional: variable de entorno **`GITHUB_PERSONAL_ACCESS_TOKEN`** en la Lambda (menos recomendable que el secreto).

### Dónde obtener cada valor

| Campo | Dónde |
|-------|--------|
| `app_id` | GitHub → Developer settings → GitHub Apps → *tu app* → **App ID** |
| `installation_id` | **Organización:** Org → **Settings** → **GitHub Apps** → *app* → **Configure** → URL `.../installations/<installation_id>`. **Usuario:** *tu perfil* → **Settings** → **Applications** → **GitHub Apps** → *Configure* en la app (mismo patrón de URL). |
| `private_key` | Misma app → **Generate a private key** (archivo `.pem`) |
| `org` | Login del dueño de los repos: `Netec-Mx` **o** el username personal (ej. `NetecLabsService`) |

## Lambda

- Función: `PublishLabsGithubFunction`
- Variables de entorno relevantes: `GITHUB_APP_SECRET_NAME`, `GITHUB_ORG` (login del propietario), **`GITHUB_OWNER_TYPE`** (`organization` \| `personal`), `CODE_OWNER_USERNAME`
- **Contenido:** solo se suben los markdown de laboratorio por capítulo (`CapituloXX/README.md`). **No** se sincroniza la carpeta `images/` ni archivos de imágenes de teoría.

### GitHub user del instructor (Cognito)

La UI del book editor guarda el **GitHub username** del usuario que inició sesión en DynamoDB:

- Tabla: **`UserInstructorGithub`** (clave `userId`: email del *id token* de Cognito, o `sub` si no hay email).
- **`GET /user-instructor-github`** — header `Authorization: Bearer <Cognito id token>`. Respuesta: `githubUserId`, `updatedAt`.
- **`POST /user-instructor-github`** — mismo header; cuerpo JSON: `{ "githubUserId": "NetecGK" }` (sin `@`).

Al abrir el editor en modo lab, el campo se rellena solo si ya existe un registro para ese usuario. La publicación (`POST /publish-labs-github`) envía `instructor_github_user` en el body; no consulta Dynamo por curso.

> La tabla legada **`CourseInstructorGithub`** puede seguir existiendo en la cuenta por compatibilidad con despliegues anteriores; el flujo actual usa **`UserInstructorGithub`**.

Tras rotar la app o la llave, actualiza el secreto en Secrets Manager y redeploy si cambias `template.yaml`.

---

## Modo “cuenta regular” / sin GitHub Team (recomendado si no hay asientos de org)

Si **no** van a comprar asientos en la organización **Netec-Mx**:

1. **Crear una cuenta de GitHub personal** dedicada (p. ej. `NetecLabsBot` o similar), solo para automatización — idealmente con MFA gestionado por la empresa.
2. **Crear la GitHub App** (o reutilizar la existente) y **instalarla en esa cuenta de usuario** (“Only select repositories” o “All repositories”, según política).
3. En **Secrets Manager**, poner en el JSON:
   - `"org": "<username_de_esa_cuenta>"` (mismo valor que el login).
   - `"installation_id"`: el de la instalación **en el usuario**, no en la org.
4. En Lambda / `template.yaml`:
   - `GITHUB_OWNER_TYPE=personal`
   - `GITHUB_ORG=<mismo_username>` (debe coincidir con `org` del secreto).
   - Dejar **`GITHUB_INSTRUCTORS_TEAM_SLUG` vacío** (los equipos solo existen en organizaciones).
5. Genera un **PAT** en la cuenta del bot (`Settings → Developer settings → Personal access tokens`), con permisos suficientes para **crear repos privados**, y guárdalo en el secreto como **`personal_access_token`** (ver arriba).
6. Los **instructores** siguen publicando desde THOR con su `instructor_github_user`; la Lambda los invita como **colaboradores** con permiso **push** al repo privado bajo esa cuenta personal. En planes gratuitos de usuario suele bastar sin el modelo de “seats” de org (sujeto a políticas actuales de GitHub).
7. **Protección de ramas** (PR obligatorios, code owners, etc.): en cuentas personales **Free**, GitHub a menudo **rechaza** reglas avanzadas. La Lambda las aplica en modo **best-effort**: si fallan, el repo **sí se publica**; revisa en la respuesta `branch_protection_*_ok` / `*_detail` y en logs.

**Limitaciones del modo personal:** el nombre del repo será `github.com/<usuario>/<curso>`, no bajo la marca `Netec-Mx` en la URL. Si hace falta marca corporativa sin org de pago, alternativas son repo **público** bajo usuario u org gratuita con límites que GitHub imponga.

---

## Acceso de instructores a repositorios privados

Los repos de laboratorio son **privados**. Si al abrir el enlace en el navegador aparece **404** en GitHub, en la práctica significa *“no tienes permiso”* (GitHub oculta repos privados a quien no es miembro o colaborador).

### Qué hace Aurora hoy

1. **Invitación individual** — Tras publicar, la Lambda intenta dar permiso **push** al usuario indicado en `instructor_github_user` (API *Add collaborator*). Si la org no tiene **asientos** para colaboradores externos, GitHub responde **422 `seat_limit`**: hay que **contratar más asientos** o dar acceso por **otra vía** (abajo).
2. **Equipo de la organización (recomendado)** — Variable de entorno **`GITHUB_INSTRUCTORS_TEAM_SLUG`** en `PublishLabsGithubFunction` (p. ej. `aurora-lab-instructors`). Tras crear/actualizar el repo, la Lambda otorga al equipo permiso **push** sobre ese repositorio. Los instructores deben ser **miembros de la organización Netec-Mx** y pertenecer a ese equipo (Settings → Teams). Así evitas depender solo de “colaborador externo” por curso.
3. **Invitaciones por correo** — Si GitHub envía invitación al colaborador, debe **aceptarla** en el enlace del email antes de poder ver el repo.

### Checklist operativo (Netec-Mx)

| Paso | Acción |
|------|--------|
| 1 | Crear en la org un equipo, p. ej. **Aurora Lab Instructors** (slug visible en la URL del equipo). |
| 2 | Añadir al equipo los **usuarios GitHub** de los instructores (deben ser miembros de la org o invitados como miembros, no solo colaboradores externos mal configurados). |
| 3 | En la **GitHub App** (NetecMxApp), revisar permisos de instalación: **Repository administration** (lectura/escritura) u otros que permitan gestionar acceso de equipos al repositorio. Si falla el PUT al equipo, revisar logs de la Lambda y el JSON de error de GitHub. |
| 4 | Poner el slug del equipo en **`GITHUB_INSTRUCTORS_TEAM_SLUG`** (`template.yaml` o override en consola) y redeploy SAM. |
| 5 | Opcional: aumentar **asientos** en facturación de GitHub si seguís usando invitaciones directas como colaborador. |

### Respuesta de la API (`POST /publish-labs-github`)

- `repository_owner`, `repository_owner_type`: login y `organization` \| `personal`.
- `repository_visibility`: `"private"`.
- `branch_protection_main_ok` / `branch_protection_changes_ok` y `*_detail`: si GitHub aceptó la protección de ramas.
- `instructors_team_slug_configured`: si hay equipo configurado en Lambda (solo aplica a org).
- `instructors_team_access_ok` / `instructors_team_access_detail`: resultado del acceso por equipo (en modo `personal` suele ser `null`).
- `collaborator_invite_ok` / `collaborator_invite_detail`: resultado de la invitación individual.
