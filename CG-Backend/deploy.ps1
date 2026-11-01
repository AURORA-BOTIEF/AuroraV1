# Despliegue seguro de CG-Backend con reconstrucción automática de la capa PDF ARM64.
#
# Contexto (ver RUNBOOK-course-pipeline / nota de PdfLayer):
#   `sam build` sin Docker construye las capas para x86_64, pero las Lambdas son arm64.
#   La capa `pdf-dependencies` (xhtml2pdf/Pillow/lxml/cryptography) trae binarios nativos
#   y DEBE ser aarch64, por eso se publica como zip precompilado en S3.
#
# Este script detecta si `lambda-layers/pdf_layer/requirements.txt` cambió respecto al
# hash registrado. Si cambió (o no hay hash), reconstruye y sube la capa arm64 antes de
# desplegar. Así no hay que recordar ejecutar el build manualmente.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File deploy.ps1
#   powershell -ExecutionPolicy Bypass -File deploy.ps1 -ForceLayerRebuild
#   powershell -ExecutionPolicy Bypass -File deploy.ps1 -SkipDeploy   # solo reconstruir capa

param(
    [switch]$ForceLayerRebuild,
    [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Req = Join-Path $Root "lambda-layers\pdf_layer\requirements.txt"
$HashFile = Join-Path $Root "lambda-layers\.pdf_layer_requirements.sha256"
$LayerBuilder = Join-Path $Root "lambda-layers\build-pdf-layer-arm64.ps1"

function Get-RequirementsHash {
    (Get-FileHash $Req -Algorithm SHA256).Hash
}

$currentHash = Get-RequirementsHash
$recordedHash = if (Test-Path $HashFile) { (Get-Content $HashFile -Raw).Trim() } else { "" }

Write-Host "== CG-Backend deploy =="
Write-Host "requirements.txt hash: $currentHash"

$needsRebuild = $ForceLayerRebuild -or ($currentHash -ne $recordedHash)

if ($needsRebuild) {
    if ($ForceLayerRebuild) {
        Write-Host "-> Reconstruyendo capa PDF ARM64 (forzado)."
    } else {
        Write-Host "-> requirements.txt cambió. Reconstruyendo capa PDF ARM64."
    }
    & powershell -ExecutionPolicy Bypass -File $LayerBuilder
    if ($LASTEXITCODE -ne 0) { throw "Falló la construcción de la capa PDF ARM64." }
    Set-Content -Path $HashFile -Value $currentHash -NoNewline
    Write-Host "-> Hash de requirements.txt actualizado: $HashFile"
} else {
    Write-Host "-> requirements.txt sin cambios. Se reutiliza la capa publicada en S3."
}

if ($SkipDeploy) {
    Write-Host "SkipDeploy activo: no se ejecuta sam deploy."
    exit 0
}

Write-Host "-> sam build"
sam build
if ($LASTEXITCODE -ne 0) { throw "sam build falló." }

Write-Host "-> sam deploy"
sam deploy --no-confirm-changeset
if ($LASTEXITCODE -ne 0) { throw "sam deploy falló." }

Write-Host "Despliegue completado."
