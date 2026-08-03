#!/bin/bash
# ROMO CAMBIOS - instalador de macOS. Doble clic. Se corre UNA vez por Mac.
# Deja lista la Mac: ffmpeg/ffprobe y (opcional) la conexión con el Drive de ROMO.
# Todo va a ~/.romocambios/bin: no toca el sistema ni pide contraseña.
cd "$(dirname "$0")" || exit 1

BIN="$HOME/.romocambios/bin"
TMP="$HOME/.romocambios/tmp"
mkdir -p "$BIN"

echo "════════════════════════════════════════════"
echo "   ROMO CAMBIOS  ·  instalación en macOS"
echo "════════════════════════════════════════════"

fin() { echo; echo "Puedes cerrar esta ventana."; read -r; }

# --------------------------------------------------------------------------- #
# 1. Python
# --------------------------------------------------------------------------- #
echo
echo "  1/3  Python"
if ! /usr/bin/env python3 -c 'import sys; sys.exit(sys.version_info < (3,8))' 2>/dev/null; then
  echo "  ✗ Falta Python 3. Instala las Herramientas de Línea de Comandos:"
  echo "      xcode-select --install"
  fin; exit 1
fi
echo "  ✓ Python $(/usr/bin/env python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"

# --------------------------------------------------------------------------- #
# 2. ffmpeg
# --------------------------------------------------------------------------- #
echo
echo "  2/3  ffmpeg"

# Si el repo trae los binarios (carpeta bin/ al lado), no hay nada que bajar.
if [ -x "bin/ffmpeg" ] && [ -x "bin/ffprobe" ]; then
  echo "  ✓ ffmpeg viene con la app"
elif [ -x "$BIN/ffmpeg" ] && [ -x "$BIN/ffprobe" ]; then
  echo "  ✓ ffmpeg ya estaba instalado"
else
  # Los builds de evermeet.cx son x86_64. En una Mac con chip M funcionan por
  # Rosetta, así que hay que asegurarse de que Rosetta esté.
  if [ "$(uname -m)" = "arm64" ] && ! /usr/bin/pgrep -q oahd; then
    echo "  ▸ Instalando Rosetta (lo pide el ffmpeg)…"
    softwareupdate --install-rosetta --agree-to-license || {
      echo "  ✗ No se pudo instalar Rosetta."; fin; exit 1; }
  fi
  mkdir -p "$TMP"
  for n in ffmpeg ffprobe; do
    echo "  ▸ Descargando $n…"
    # --http1.1: el curl de macOS viejo se atraganta con el HTTP/2 de las descargas.
    curl -fL --http1.1 -o "$TMP/$n.zip" \
      "https://evermeet.cx/ffmpeg/getrelease/$n/zip" || {
        echo "  ✗ No se pudo descargar $n. ¿Hay internet?"; fin; exit 1; }
    /usr/bin/unzip -o -q "$TMP/$n.zip" -d "$TMP"
    cp "$TMP/$n" "$BIN/$n"
    # Sin esto macOS bloquea el binario por venir de internet (Gatekeeper).
    xattr -d com.apple.quarantine "$BIN/$n" 2>/dev/null
    chmod +x "$BIN/$n"
  done
  rm -rf "$TMP"
  echo "  ✓ ffmpeg instalado en $BIN"
fi

FF="$BIN/ffmpeg"
[ -x "bin/ffmpeg" ] && FF="./bin/ffmpeg"
if ! "$FF" -v quiet -decoders 2>/dev/null | grep -q libvpx-vp9; then
  echo "  ! Este ffmpeg no trae libvpx-vp9: las plantillas animadas pueden salir"
  echo "    con fondo negro. Avísale a Marlon."
else
  echo "  ✓ decodificadores de plantillas (libvpx) presentes"
fi

# --------------------------------------------------------------------------- #
# 3. Google Drive (opcional)
# --------------------------------------------------------------------------- #
echo
echo "  3/3  Google Drive"
RCLONE="$BIN/rclone"

printf "  ¿Conectar esta Mac con el Drive de ROMO para que los videos se suban solos? (s/n): "
read -r resp
if [ "$resp" != "s" ] && [ "$resp" != "S" ]; then
  echo "  Saltado. Puedes hacerlo después volviendo a correr esto."
  fin; exit 0
fi

if [ ! -x "$RCLONE" ]; then
  echo "  ▸ Descargando rclone…"
  mkdir -p "$TMP"
  ARCH=amd64
  [ "$(uname -m)" = "arm64" ] && ARCH=arm64
  curl -fL --http1.1 -o "$TMP/rclone.zip" \
    "https://downloads.rclone.org/rclone-current-osx-$ARCH.zip" || {
      echo "  ✗ No se pudo descargar rclone."; fin; exit 1; }
  /usr/bin/unzip -o -q "$TMP/rclone.zip" -d "$TMP"
  cp "$TMP"/rclone-v*/rclone "$RCLONE"
  xattr -d com.apple.quarantine "$RCLONE" 2>/dev/null
  chmod +x "$RCLONE"
  rm -rf "$TMP"
  echo "  ✓ rclone instalado"
else
  echo "  ✓ rclone ya estaba instalado"
fi

if "$RCLONE" listremotes 2>/dev/null | grep -q "^romodrive:"; then
  echo "  ✓ esta Mac ya estaba conectada a Drive"
  "$RCLONE" about romodrive: 2>/dev/null
else
  echo
  echo "  ▸ Se abre el navegador: entra con la cuenta de Google de ROMO y dale"
  echo "    permiso. Es una sola vez."
  echo
  "$RCLONE" config create romodrive drive scope=drive
  if "$RCLONE" listremotes 2>/dev/null | grep -q "^romodrive:"; then
    echo "  ✓ conectado: los videos se subirán solos a Drive"
  else
    echo "  ✗ Quedó a medias: vuelve a correr este instalador."
  fi
fi

echo
echo "════════════════════════════════════════════"
echo "  Listo. Abre la app con  «ROMO CAMBIOS.command»"
echo "════════════════════════════════════════════"
fin
