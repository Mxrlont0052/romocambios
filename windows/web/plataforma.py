"""ROMO CAMBIOS — lo poco que cambia entre macOS y Windows.

La app es la misma en los dos sistemas: un servidor local que llama a ffmpeg.
Lo único que cambia es lo que ocurre FUERA de Python —elegir archivos, abrir el
navegador, mostrar un archivo en el Finder/Explorador, encontrar los binarios—
y está todo junto aquí para que el resto del código no tenga un `if windows` en
cada esquina.

Windows no tiene `osascript` ni `open`: el selector de archivos se pide con un
script de PowerShell (`selector.ps1`) y lo demás sale de `os.startfile` y
`explorer`.
"""

import os
import subprocess
import sys

WINDOWS = os.name == "nt"
ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(ROOT)
HOME = os.path.expanduser("~")

# En Windows los procesos hijos abrirían una ventana de consola negra cada vez
# que corre ffmpeg. Con esto quedan invisibles.
SILENCIO = {"creationflags": 0x08000000} if WINDOWS else {}


# --------------------------------------------------------------------------- #
# Binarios (ffmpeg, ffprobe, rclone)
# --------------------------------------------------------------------------- #

def binario(nombre, extra=()):
    """Ruta al ejecutable, o "" si no está.

    Se busca primero lo que venga con la app y lo que dejó el instalador, y solo
    al final el PATH: así la app usa siempre el ffmpeg que conoce, aunque el
    equipo tenga otro instalado por su cuenta.
    """
    exe = nombre + ".exe" if WINDOWS else nombre
    cands = [
        os.path.join(PROJECT, "bin", exe),                 # repo: mac/bin, windows/bin
        os.path.join(PROJECT, "src-tauri", "resources", exe),
        os.path.join(HOME, ".romocambios", "bin", exe),    # lo que baja el instalador
    ]
    cands += [os.path.join(d, exe) for d in extra]
    if not WINDOWS:
        cands += [f"/opt/homebrew/bin/{exe}", f"/usr/local/bin/{exe}"]
    for c in cands:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    from shutil import which
    return which(nombre) or ""


# --------------------------------------------------------------------------- #
# Carpetas y fuentes
# --------------------------------------------------------------------------- #

def carpeta_videos():
    """Dónde guarda videos el sistema: ~/Videos en Windows, ~/Movies en macOS."""
    return os.path.join(HOME, "Videos" if WINDOWS else "Movies")


# Fuente de respaldo para las plantillas de texto (las que dibuja ffmpeg). Es
# solo la red de emergencia: el repertorio real son los .webm de Remotion.
if WINDOWS:
    _FUENTES = [
        r"C:\Windows\Fonts\ariblk.ttf",     # Arial Black
        r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
    ]
else:
    _FUENTES = [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]


def fuente_por_defecto():
    for f in _FUENTES:
        if os.path.isfile(f):
            return f
    return _FUENTES[0]


def ruta_filtro(p):
    """Ruta lista para meterla dentro de un filtro de ffmpeg (drawtext, etc.).

    El filtergraph usa `:` como separador y `\\` como escape, así que una ruta de
    Windows (`C:\\Windows\\Fonts\\ariblk.ttf`) lo rompe dos veces. Se pasan las
    barras a `/` —ffmpeg las acepta igual en Windows— y se escapa la `:` de la
    unidad.
    """
    return (p or "").replace("\\", "/").replace(":", r"\:")


# --------------------------------------------------------------------------- #
# Diálogos del sistema
# --------------------------------------------------------------------------- #

def _elegir_windows(kind):
    ps = os.path.join(ROOT, "selector.ps1")
    exe = "powershell.exe"
    for c in (r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",):
        if os.path.isfile(c):
            exe = c
    # -STA: los diálogos de Windows Forms no abren en el modo por defecto de
    # PowerShell 7. -NoProfile para que el perfil del usuario no imprima nada
    # que se cuele entre las rutas.
    r = subprocess.run(
        [exe, "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
         "-File", ps, "-Modo", "folder" if kind == "folder" else "files"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        **SILENCIO)
    if r.returncode != 0:
        return []
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def _elegir_mac(kind):
    if kind == "folder":
        script = ['set p to POSIX path of (choose folder with prompt "Elige la carpeta")',
                  'return p']
    else:
        script = [
            'set fs to choose file with prompt "Elige los videos de los cambios" '
            'with multiple selections allowed of type {"mp4","mov","m4v","avi","mkv"}',
            'set o to ""',
            'repeat with f in fs',
            'set o to o & POSIX path of f & linefeed',
            'end repeat',
            'return o',
        ]
    r = subprocess.run(["osascript"] + sum([["-e", s] for s in script], []),
                       capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def elegir(kind):
    """Diálogo nativo para elegir archivos ("files") o una carpeta ("folder").

    Hace falta un diálogo del sistema y no el `<input type=file>` del navegador
    porque la app necesita la RUTA real en disco para pasársela a ffmpeg, y el
    navegador nunca la entrega.
    """
    return _elegir_windows(kind) if WINDOWS else _elegir_mac(kind)


def abrir_url(url):
    if WINDOWS:
        os.startfile(url)  # noqa: S606
    else:
        subprocess.Popen(["open", url])


def revelar(path):
    """Muestra el archivo en el Explorador (Windows) o el Finder (macOS)."""
    if not path:
        return
    if WINDOWS:
        # explorer devuelve código 1 aunque funcione: no hay que mirar el status.
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        subprocess.Popen(["open", "-R", path])


def aviso_sin_ffmpeg():
    exe = "instalar-windows.bat" if WINDOWS else "instalar-mac.command"
    return ("ERROR: no encontré ffmpeg/ffprobe.\n"
            f"Corre {exe} una vez para instalarlos.")


def comprobar_python():
    """La app usa solo la librería estándar, pero necesita Python 3.8 o más."""
    if sys.version_info < (3, 8):
        print("ERROR: hace falta Python 3.8 o más nuevo.", file=sys.stderr)
        sys.exit(1)
