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
