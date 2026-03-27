# GitHub App (publicación de laboratorios)

THOR publica laboratorios en repositorios **públicos** de la organización **Netec-Mx** usando una GitHub App.

## App actual

- **Nombre:** NetecMxApp
- **Owner de repositorios:** `Netec-Mx` (organización)
- Credenciales locales de referencia: carpeta `GithubApp/` (ignorada por git; no commitear `.env` ni `.pem`)

## AWS Secrets Manager

- **Nombre del secreto:** `netec/github-app/aurora-publisher`
- **Formato JSON:**

```json
{
  "app_id": "<GitHub App ID (número)>",
  "installation_id": "<ID de la instalación en Netec-Mx>",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "org": "Netec-Mx"
}
```

### Dónde obtener cada valor

| Campo | Dónde |
|-------|--------|
| `app_id` | GitHub → Developer settings → GitHub Apps → *NetecMxApp* |
| `installation_id` | Netec-Mx → Settings → GitHub Apps → Configure → URL `.../installations/<installation_id>` |
| `private_key` | App settings → Generate a private key (`.pem`) |
| `org` | `Netec-Mx` |

## Lambda

- Función: `PublishLabsGithubFunction`
- Variables de entorno relevantes:
  - `GITHUB_APP_SECRET_NAME=netec/github-app/aurora-publisher`
  - `GITHUB_ORG=Netec-Mx`
  - `GITHUB_OWNER_TYPE=organization`
  - `CODE_OWNER_USERNAME=NetecGK`
- **Contenido sincronizado:** solo markdown de laboratorio (`CapituloXX/README.md`). No se suben imágenes de teoría.

## Flujo de publicación

1. La Lambda obtiene token de instalación de la App.
2. Crea (o reutiliza) el repositorio en `Netec-Mx` con visibilidad **pública**.
3. Sincroniza:
   - `README.md` raíz con índice completo de laboratorios y links por capítulo.
   - `.github/CODEOWNERS`.
   - `CapituloXX/README.md` (contenido de labs por capítulo).
4. Configura repositorio y ramas (`changes_course`, branch protections best-effort).
5. Intenta invitar al `instructor_github_user` como colaborador (no bloqueante).

## README raíz (índice de laboratorios)

El `README.md` raíz se genera automáticamente con:

- Título y descripción del `outline`.
- Sección **Lista de laboratorios** agrupada por capítulo.
- Links a cada laboratorio apuntando a su ancla dentro de `CapituloXX/README.md`.
- Si existen en el markdown de laboratorio, se incluyen:
  - `Descripción`
  - `Duración estimada`

## GitHub user del instructor (Cognito)

La UI del book editor guarda el GitHub username del usuario autenticado:

- Tabla DynamoDB: `UserInstructorGithub` (clave `userId`).
- Endpoints:
  - `GET /user-instructor-github`
  - `POST /user-instructor-github`

La publicación (`POST /publish-labs-github`) envía `instructor_github_user` en el body.

## Respuesta de la API (`POST /publish-labs-github`)

- `repository_url`: `https://github.com/Netec-Mx/<repo>`
- `repository_visibility`: `"public"`
- `chapters_synced`
- `collaborator_invite_ok` / `collaborator_invite_detail`
- `branch_protection_main_ok` / `branch_protection_changes_ok` y detalles
