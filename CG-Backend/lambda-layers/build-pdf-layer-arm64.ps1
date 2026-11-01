# Rebuild de la capa PDF (pdf-dependencies) para ARM64 sin Docker.
#
# Por qué: xhtml2pdf trae wheels nativos (Pillow, lxml, cryptography) que deben ser
# aarch64. `sam build` sin Docker produce x86_64, incompatible con Lambda arm64
# (error: "cannot import name '_imaging' from 'PIL'").
#
# Nota de dependencias: xhtml2pdf==0.2.15 exige reportlab<4.1. Las versiones de
# svglib >= 1.6.0 requieren reportlab>=4.4.3 (conflicto). svglib 1.4.0 es la última
# compatible y solo distribuye sdist, por eso se instala aparte y con --no-deps.
#
# Uso:  powershell -ExecutionPolicy Bypass -File build-pdf-layer-arm64.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Src = Join-Path $Root "pdf_layer"
$Out = Join-Path $Root "pdf_layer_arm64"
$Py = Join-Path $Out "python"
$Zip = Join-Path $Root "pdf_layer_arm64.zip"
$Bucket = "s3://crewai-course-artifacts/lambda-layers/pdf_layer_arm64.zip"

Write-Host "1/5 Limpiando build anterior..."
Remove-Item -Recurse -Force $Out -ErrorAction SilentlyContinue
Remove-Item -Force $Zip -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Py | Out-Null

Write-Host "2/5 Instalando svglib 1.4.0 (sdist, sin resolución de dependencias)..."
$tmp = Join-Path $Root "_svglib_tmp"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
python -m pip install setuptools wheel --upgrade -q
python -m pip download svglib==1.4.0 --no-deps --dest $tmp -q
$tarball = Get-ChildItem $tmp -Filter "svglib-*.tar.gz" | Select-Object -First 1
python -m pip install $tarball.FullName --target $Py --no-deps --no-build-isolation -q

Write-Host "3/5 Instalando dependencias ARM64 (manylinux2014_aarch64)..."
# Nota: boto3/botocore NO se incluyen (ya vienen en el runtime Lambda y agrandan la
# capa hasta exceder el límite de 250 MB en funciones con varias capas).
python -m pip install xhtml2pdf==0.2.15 `
    --python-version 3.12 --platform manylinux2014_aarch64 --implementation cp `
    --only-binary=:all: --target $Py --upgrade --no-deps -q

python -m pip install jinja2==3.1.3 markdown PyYAML pypdf reportlab==4.0.9 `
    pillow html5lib arabic-reshaper python-bidi pyhanko pyhanko-certvalidator `
    cssselect2 tinycss2 chardet lxml `
    --python-version 3.12 --platform manylinux2014_aarch64 --implementation cp `
    --only-binary=:all: --target $Py --upgrade

Write-Host "4/5 Verificando arquitectura y empaquetando..."
$so = Get-ChildItem (Join-Path $Py "PIL") -Filter "_imaging*.so" | Select-Object -First 1
if (-not $so -or $so.Name -notmatch "aarch64") {
    throw "La capa no quedó en aarch64. Se encontró: $($so.Name)"
}
Push-Location $Out
Compress-Archive -Path python -DestinationPath $Zip -Force
Pop-Location

Write-Host "5/5 Subiendo a S3..."
aws s3 cp $Zip $Bucket --region us-east-1

Write-Host "Listo. Ahora ejecuta: sam build && sam deploy"
