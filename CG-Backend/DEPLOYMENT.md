# Runbook de despliegue — CG-Backend (Aurora / Thor)

## Comando oficial

```powershell
powershell -ExecutionPolicy Bypass -File deploy.ps1
```

Este script:
1. Detecta si `lambda-layers/pdf_layer/requirements.txt` cambió (hash SHA256).
2. Si cambió, reconstruye y publica la capa **PDF arm64** antes de desplegar.
3. Ejecuta `sam build` y `sam deploy --no-confirm-changeset` con el perfil `Netec`.

Opciones:
- `-ForceLayerRebuild` — reconstruye la capa aunque el hash no haya cambiado.
- `-SkipDeploy` — solo reconstruye la capa, sin desplegar.

## Regla crítica: arquitectura de la capa PDF

Las Lambdas de PdfLayer (`SetupGuideBuilderFunction`, `BookToPdfFunction`) son **arm64**.
`sam build` **sin Docker** descarga wheels **x86_64**, incompatibles con arm64:
síntoma en runtime → `UnboundLocalError`/`ImportError: cannot import name '_imaging' from 'PIL'`.

Por eso `PdfLayer` en `template.yaml` usa un **zip precompilado**:

```yaml
PdfLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    ContentUri: s3://crewai-course-artifacts/lambda-layers/pdf_layer_arm64.zip
    CompatibleArchitectures: [arm64]
```

### Si agregas una dependencia PDF

1. Añádela a `lambda-layers/pdf_layer/requirements.txt`
   (ojo con los binarios nativos: deben existir wheels `manylinux2014_aarch64`).
2. Ejecuta `deploy.ps1` (detecta el cambio de hash y reconstruye solo).
   Manualmente: `build-pdf-layer-arm64.ps1` y luego `sam build && sam deploy`.

### Si actualizas la capa PPT

`PPTLayer` sigue usando `ContentUri: ./lambda-layers/ppt_layer/` con BuildMethod, que
también produce x86_64. Si aparecen errores de importación nativa (Pillow) en
`StrandsPptMerger`/`ExportPptFunction`, aplicar el mismo patrón arm64.

## Nota sobre dependencias

- `boto3`/`botocore` **no** se incluyen en la capa: ya vienen en el runtime y su inclusión
  excede el límite de 250 MB por función (código + capas).
- `xhtml2pdf==0.2.15` exige `reportlab<4.1`; por eso se fija `svglib==1.4.0`
  (versiones ≥ 1.6 requieren `reportlab>=4.4.3`, que entra en conflicto).

## Verificación post-despliegue

```bash
# Capa PDF
aws lambda get-function-configuration --function-name SetupGuideBuilderFunction \
  --region us-east-1 --query "Layers[0].Arn" --output text

# Smoke test
aws lambda invoke --function-name SetupGuideBuilderFunction --region us-east-1 \
  --payload '{"project_folder":"<carpeta-proyecto>"}' \
  --cli-binary-format raw-in-base64-out out.json
```

## Por qué no se usa `sam build --use-container`

Requiere Docker en ejecución; no está disponible en todos los entornos de desarrollo del
equipo. El pipeline descrito (pip `--platform manylinux2014_aarch64` + zip en S3) no
depende de Docker.
