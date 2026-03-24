# GitHub App (publicación de laboratorios)

THOR usa una **GitHub App** instalada en la organización **Netec-Mx** para crear repos privados, subir contenido y configurar ramas.

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
  "org": "Netec-Mx"
}
```

### Dónde obtener cada valor

| Campo | Dónde |
|-------|--------|
| `app_id` | GitHub → Developer settings → GitHub Apps → *tu app* → **App ID** |
| `installation_id` | Org **Netec-Mx** → **Settings** → **GitHub Apps** → *app* → **Configure**. El número al final de la URL: `.../installations/<installation_id>` |
| `private_key` | Misma app → **Generate a private key** (archivo `.pem`) |
| `org` | `Netec-Mx` |

## Lambda

- Función: `PublishLabsGithubFunction`
- Variables de entorno relevantes: `GITHUB_APP_SECRET_NAME`, `GITHUB_ORG`, `CODE_OWNER_USERNAME`
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

- `repository_visibility`: `"private"`.
- `instructors_team_slug_configured`: si hay equipo configurado en Lambda.
- `instructors_team_access_ok` / `instructors_team_access_detail`: resultado del acceso por equipo.
- `collaborator_invite_ok` / `collaborator_invite_detail`: resultado de la invitación individual.
