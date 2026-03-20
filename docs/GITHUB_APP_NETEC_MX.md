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

Tras rotar la app o la llave, actualiza el secreto en Secrets Manager y redeploy si cambias `template.yaml`.
