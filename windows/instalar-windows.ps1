# ROMO CAMBIOS - instalador de Windows.
# Deja lista la PC: Python, ffmpeg/ffprobe y (opcional) la conexion con el Drive
# de ROMO. Todo lo que baja va a %USERPROFILE%\.romocambios\bin, sin tocar el
# sistema ni pedir permisos de administrador.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # sin esto la barra de descarga lo hace lentisimo

$BIN = Join-Path $env:USERPROFILE ".romocambios\bin"
$TMP = Join-Path $env:USERPROFILE ".romocambios\tmp"

function Titulo($t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan }
function Ok($t)     { Write-Host "  OK  $t" -ForegroundColor Green }
function Malo($t)   { Write-Host "  X   $t" -ForegroundColor Red }

Write-Host "============================================" -ForegroundColor Magenta
Write-Host "   ROMO CAMBIOS  -  instalacion en Windows" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

New-Item -ItemType Directory -Force -Path $BIN, $TMP | Out-Null

# --------------------------------------------------------------------------- #
# 1. Python
# --------------------------------------------------------------------------- #
Titulo "1/3  Python"

$python = $null
foreach ($c in @("py", "python")) {
  $cmd = Get-Command $c -ErrorAction SilentlyContinue
  if ($cmd) {
    # La "python" de la Microsoft Store es un acceso directo falso que solo abre
    # la tienda: se reconoce porque vive en WindowsApps y no responde --version.
    if ($cmd.Source -like "*WindowsApps*") { continue }
    $python = $c
    break
  }
}

if ($python) {
  $v = & $python -c "import sys;print('.'.join(map(str,sys.version_info[:3])))" 2>$null
  Ok "Python $v"
}
else {
  Malo "No hay Python instalado."
  Write-Host ""
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "  Lo instalo ahora con winget? (s/n): " -NoNewline
    if ((Read-Host) -match '^[sSyY]') {
      winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
      Write-Host ""
      Write-Host "  Cierra esta ventana y vuelve a correr instalar-windows.bat" -ForegroundColor Yellow
      Write-Host "  (Windows necesita reabrir la consola para ver el Python nuevo)." -ForegroundColor Yellow
      exit 1
    }
  }
  Write-Host "  Instalalo desde https://www.python.org/downloads/" -ForegroundColor Yellow
  Write-Host "  IMPORTANTE: marca la casilla 'Add python.exe to PATH'." -ForegroundColor Yellow
  Write-Host "  Despues vuelve a correr instalar-windows.bat."
  exit 1
}

# --------------------------------------------------------------------------- #
# 2. ffmpeg / ffprobe
# --------------------------------------------------------------------------- #
Titulo "2/3  ffmpeg"

$ffmpeg = Join-Path $BIN "ffmpeg.exe"
$ffprobe = Join-Path $BIN "ffprobe.exe"

if ((Test-Path $ffmpeg) -and (Test-Path $ffprobe)) {
  Ok "ffmpeg ya estaba instalado"
}
else {
  Write-Host "  Descargando ffmpeg (unos 100 MB, tarda un rato)..."
  # Build "full" y no "essentials" a proposito: las plantillas son WebM con
  # canal alfa y hacen falta los decodificadores libvpx, que el essentials
  # puede no traer. Sin ellos las plantillas saldrian con fondo negro.
  $url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.zip"
  $zip = Join-Path $TMP "ffmpeg.zip"
  try {
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
  }
  catch {
    Malo "No se pudo descargar ffmpeg. Hay internet?"
    Write-Host "  $($_.Exception.Message)"
    exit 1
  }
  Write-Host "  Descomprimiendo..."
  $dst = Join-Path $TMP "ffmpeg"
  if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
  Expand-Archive -Path $zip -DestinationPath $dst -Force
  foreach ($n in @("ffmpeg.exe", "ffprobe.exe")) {
    $src = Get-ChildItem -Path $dst -Recurse -Filter $n | Select-Object -First 1
    if (-not $src) { Malo "El zip no traia $n"; exit 1 }
    Copy-Item $src.FullName (Join-Path $BIN $n) -Force
  }
  Remove-Item $TMP -Recurse -Force -ErrorAction SilentlyContinue
  Ok "ffmpeg instalado en $BIN"
}

# Comprobacion de verdad: que el binario corra y traiga lo que la app usa.
$decs = & $ffmpeg -v quiet -decoders 2>$null
if ($LASTEXITCODE -ne 0) {
  Malo "ffmpeg no arranca. Borra $BIN y vuelve a correr el instalador."
  exit 1
}
# `-not (... -match ...)` y no `-notmatch`: sobre una LISTA de líneas, -notmatch
# devuelve las que no coinciden (casi todas) y el if siempre daría verdadero.
if (-not ($decs -match "libvpx-vp9")) {
  Write-Host "  !  Este ffmpeg no trae libvpx-vp9." -ForegroundColor Yellow
  Write-Host "     La app va a funcionar igual, pero las plantillas animadas" -ForegroundColor Yellow
  Write-Host "     pueden salir con fondo negro. Avisale a Marlon." -ForegroundColor Yellow
}
else {
  Ok "decodificadores de plantillas (libvpx) presentes"
}

# --------------------------------------------------------------------------- #
# 3. Google Drive (opcional)
# --------------------------------------------------------------------------- #
Titulo "3/3  Google Drive"

$rclone = Join-Path $BIN "rclone.exe"

Write-Host "  Conectar esta PC con el Drive de ROMO para que los videos se"
Write-Host "  suban solos? (s/n): " -NoNewline
if ((Read-Host) -notmatch '^[sSyY]') {
  Write-Host "  Saltado. Puedes hacerlo despues volviendo a correr esto."
}
else {
  if (-not (Test-Path $rclone)) {
    Write-Host "  Descargando rclone..."
    New-Item -ItemType Directory -Force -Path $TMP | Out-Null
    $zip = Join-Path $TMP "rclone.zip"
    try {
      Invoke-WebRequest -Uri "https://downloads.rclone.org/rclone-current-windows-amd64.zip" `
        -OutFile $zip -UseBasicParsing
    }
    catch {
      Malo "No se pudo descargar rclone."
      exit 1
    }
    $dst = Join-Path $TMP "rclone"
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $dst -Force
    $src = Get-ChildItem -Path $dst -Recurse -Filter "rclone.exe" | Select-Object -First 1
    Copy-Item $src.FullName $rclone -Force
    Remove-Item $TMP -Recurse -Force -ErrorAction SilentlyContinue
    Ok "rclone instalado"
  }
  else { Ok "rclone ya estaba instalado" }

  $remotos = & $rclone listremotes 2>$null
  if ($remotos -match "^romodrive:") {
    Ok "esta PC ya estaba conectada a Drive"
    & $rclone about romodrive: 2>$null
  }
  else {
    Write-Host ""
    Write-Host "  Se va a abrir el navegador: entra con la cuenta de Google de" -ForegroundColor Yellow
    Write-Host "  ROMO y dale permiso. Es una sola vez." -ForegroundColor Yellow
    Write-Host ""
    & $rclone config create romodrive drive scope=drive
    if (& $rclone listremotes 2>$null | Select-String "^romodrive:") {
      Ok "conectado: los videos se subiran solos a Drive"
    }
    else {
      Malo "Quedo a medias: vuelve a correr este instalador."
    }
  }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Listo. Abre la app con  ROMO CAMBIOS.bat" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""
