"""ROMO CAMBIOS — subida a Google Drive.

Cada render deja dos archivos en disco: `DM055 SV.mp4` (sin voz) y `DM055.mp4`
(listo para subir). Este módulo los manda a las dos carpetas del Drive de 5TB y,
solo para el que va con voz, escribe el link de descarga en la hoja de romocont.

Por qué una COLA en vez de subir dentro del render: una subida de 40 MB con la
Mac colgada del wifi puede tardar más que el propio render, y el lote no puede
quedarse esperando. La cola vive en disco (`upload_queue.json`), así que si la
app se cierra a mitad de una subida —o si no había internet— al abrirla de nuevo
sigue donde quedó en vez de perder el video en el limbo.

rclone es quien habla con Google: es un binario suelto (no necesita Homebrew,
que en esta Mac no sirve) y hace la subida reanudable.
"""

import json
import os
import re
import subprocess
import threading
import time
import urllib.request

import plataforma as plat

CONFIG_DIR = os.path.expanduser("~/.config/romocambios")
QUEUE_FILE = os.path.join(CONFIG_DIR, "upload_queue.json")
REMOTE = "romodrive"

# Cuánto esperar antes de reintentar, por número de intentos fallidos. El último
# valor se repite: nunca se abandona un archivo, solo se reintenta más despacio.
BACKOFF = [5, 20, 60, 300, 900]

_QUEUE = []
_LOCK = threading.RLock()
_WORKER = None
_STATE = {"subiendo": "", "pendientes": 0, "ultimo_error": ""}


# --------------------------------------------------------------------------- #
# rclone
# --------------------------------------------------------------------------- #

RCLONE = plat.binario("rclone")


def _run(args, timeout=None):
    return subprocess.run([RCLONE] + args, capture_output=True, text=True,
                          timeout=timeout, **plat.SILENCIO)


def remote_listo():
    """¿Está rclone instalado y con la cuenta de Google ya autorizada?"""
    if not RCLONE:
        return False
    try:
        r = _run(["listremotes"], timeout=15)
    except Exception:  # noqa: BLE001
        return False
    return f"{REMOTE}:" in r.stdout


def _spec(folder_id):
    """Remoto apuntando a UNA carpeta por su ID.

    Se pasa el id en la propia ruta (`remote,root_folder_id=...:`) y no en el
    config: así las dos carpetas usan la misma cuenta sin duplicar remotos, y
    cambiar de carpeta es cambiar un dato del config de la app, no reconfigurar
    rclone.
    """
    return f"{REMOTE},root_folder_id={folder_id}:"


def subir(local, folder_id, timeout=1800):
    """Sube (o reemplaza) un archivo en la carpeta y devuelve su ID de Drive.

    `copyto` con el nombre explícito evita el clásico de rclone de crear una
    carpeta con el nombre del archivo cuando el destino no existe. Si el archivo
    ya estaba y no cambió, rclone no vuelve a subirlo: por eso los retoques del
    panel de revisión no gastan datos de más.
    """
    if not RCLONE:
        raise RuntimeError("rclone no está instalado")
    if not os.path.isfile(local):
        raise RuntimeError(f"no existe el archivo {local}")
    nombre = os.path.basename(local)
    dest = _spec(folder_id) + nombre
    r = _run(["copyto", local, dest, "--drive-chunk-size", "16M",
              "--retries", "3", "--low-level-retries", "10"], timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "").strip()[-500:])
    return file_id(nombre, folder_id)


def file_id(nombre, folder_id, timeout=120):
    """ID de Drive de un archivo por nombre dentro de la carpeta."""
    r = _run(["lsf", _spec(folder_id), "--files-only", "--format", "ip",
              "--separator", "|"], timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "").strip()[-300:])
    for linea in r.stdout.splitlines():
        if "|" not in linea:
            continue
        fid, path = linea.split("|", 1)
        if path.strip() == nombre:
            return fid.strip()
    raise RuntimeError(f"subido pero no encontrado en la carpeta: {nombre}")


def link_descarga(fid):
    """Link que descarga el archivo de una, sin pasar por el visor de Drive."""
    return f"https://drive.google.com/uc?export=download&id={fid}"


# --------------------------------------------------------------------------- #
# Hoja de romocont
# --------------------------------------------------------------------------- #

def escribir_link(web_app_url, nombre_archivo, url, timeout=30):
    """Pega el link en la fila del video, cruzando por NOMBRE.

    Se cruza por nombre y no por id de fila porque el mismo Code.gs ya normaliza
    "RLL 004" y "RLL004" como el mismo video, y así funciona igual para las filas
    que el equipo agregó a mano en la hoja.
    """
    payload = json.dumps({
        "action": "nube",
        "items": [{"n": nombre_archivo, "u": url}],
    }).encode()
    req = urllib.request.Request(web_app_url, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))
    if not data.get("linked"):
        # No es un fallo de red: el video todavía no tiene fila (el registro va
        # por otro lado y puede llegar tarde). Se reintenta con la cola.
        raise RuntimeError(f"la hoja todavía no tiene la fila de {nombre_archivo}")
    return data


# --------------------------------------------------------------------------- #
# Cola
# --------------------------------------------------------------------------- #

def _cargar():
    global _QUEUE
    try:
        with open(QUEUE_FILE) as f:
            _QUEUE = json.load(f)
    except Exception:  # noqa: BLE001
        _QUEUE = []


def _guardar():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = QUEUE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_QUEUE, f, indent=2, ensure_ascii=False)
    os.replace(tmp, QUEUE_FILE)  # atómico: nunca queda una cola a medio escribir


def encolar(local, folder_id, enlazar=False, nombre="", web_app_url=""):
    """Agrega un archivo a la cola. `enlazar` = además escribir el link en la hoja."""
    if not local or not folder_id:
        return
    with _LOCK:
        for t in _QUEUE:
            if t["local"] == local and t["folder"] == folder_id:
                return  # ya está en cola (retoque del panel de revisión)
        _QUEUE.append({
            "local": local,
            "folder": folder_id,
            "enlazar": bool(enlazar),
            "nombre": nombre or os.path.basename(local),
            "web_app_url": web_app_url,
            "intentos": 0,
            "proximo": 0.0,
            "error": "",
            "fid": "",
        })
        _guardar()
    arrancar()


def _procesar(t):
    if not t.get("fid"):
        t["fid"] = subir(t["local"], t["folder"])
    if t.get("enlazar") and t.get("web_app_url"):
        escribir_link(t["web_app_url"], os.path.basename(t["local"]),
                      link_descarga(t["fid"]))


def _loop():
    while True:
        with _LOCK:
            ahora = time.time()
            tarea = next((t for t in _QUEUE if t["proximo"] <= ahora), None)
            _STATE["pendientes"] = len(_QUEUE)
            if tarea is None:
                if not _QUEUE:
                    _STATE["subiendo"] = ""
                    break
            else:
                _STATE["subiendo"] = os.path.basename(tarea["local"])
        if tarea is None:
            time.sleep(3)
            continue
        try:
            _procesar(tarea)
            with _LOCK:
                _QUEUE.remove(tarea)
                tarea_err = ""
                _guardar()
        except Exception as exc:  # noqa: BLE001
            tarea_err = str(exc)
            with _LOCK:
                tarea["intentos"] += 1
                tarea["error"] = tarea_err[-300:]
                espera = BACKOFF[min(tarea["intentos"] - 1, len(BACKOFF) - 1)]
                tarea["proximo"] = time.time() + espera
                _STATE["ultimo_error"] = f"{tarea['nombre']}: {tarea['error']}"
                _guardar()
        with _LOCK:
            _STATE["pendientes"] = len(_QUEUE)
            _STATE["subiendo"] = ""


def arrancar():
    """Levanta el worker si no está corriendo. Idempotente."""
    global _WORKER
    with _LOCK:
        if _WORKER is not None and _WORKER.is_alive():
            return
        if not _QUEUE:
            return
        _WORKER = threading.Thread(target=_loop, daemon=True)
        _WORKER.start()


def iniciar():
    """Al abrir la app: recupera la cola de la sesión anterior y sigue."""
    _cargar()
    with _LOCK:
        # Un archivo borrado a mano entre sesiones bloquearía la cola para siempre.
        vivos = [t for t in _QUEUE if os.path.isfile(t["local"])]
        if len(vivos) != len(_QUEUE):
            _QUEUE[:] = vivos
            _guardar()
        _STATE["pendientes"] = len(_QUEUE)
    arrancar()


def reintentar_ya():
    """Borra las esperas de backoff y despierta al worker."""
    with _LOCK:
        for t in _QUEUE:
            t["proximo"] = 0.0
        _guardar()
    arrancar()


def estado():
    with _LOCK:
        return {
            "rclone": bool(RCLONE),
            "conectado": remote_listo() if RCLONE else False,
            "pendientes": len(_QUEUE),
            "subiendo": _STATE["subiendo"],
            "ultimo_error": _STATE["ultimo_error"],
            "cola": [{"nombre": t["nombre"], "intentos": t["intentos"],
                      "error": t["error"]} for t in _QUEUE[:20]],
        }


def id_de_carpeta(texto):
    """Saca el ID de una carpeta de Drive de lo que sea que peguen.

    Vale el link completo (`.../folders/1AbC...?usp=sharing`) o el ID pelado: el
    equipo pega links, no ids.
    """
    texto = (texto or "").strip()
    if not texto:
        return ""
    m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", texto)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", texto)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", texto):
        return texto
    return ""
