#!/usr/bin/env python3
"""ROMO CAMBIOS — servidor local (modo lote).

Sirve la app HTML en 127.0.0.1 y hace de puente con el ffmpeg nativo: marcado
manual de cada cambio, recorte del clip, render masivo con plantillas y efectos
rotativos, y un panel de revisión para retocar volúmenes y tiempos sin rehacer
todo. Al terminar cada video lo registra en la hoja de romocont.
"""

import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import templates as tpl  # noqa: E402
import drive  # noqa: E402
import plataforma as plat  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(ROOT)
CONFIG_DIR = os.path.expanduser("~/.config/romocambios")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
BATCH_FILE = os.path.join(CONFIG_DIR, "batch.json")

DEFAULT_FONT = plat.fuente_por_defecto()
DEFAULT_WEBAPP = (
    "https://script.google.com/macros/s/"
    "AKfycbxXMj7tetNujWtLkvyaFQfRJlJfn_MduZP6uDt24lzjznjlY8w0PQ4St1kOqt5Yx6Tb/exec"
)

# Carpetas del Drive de 5TB (ROMOCONT/). El con voz va a LISTOS y es el único que
# deja link en la hoja; el SV se guarda para reeditar y no se enlaza.
DRIVE_LISTOS = "1RkbNGYLg6RZaTDhCs7sxThXwMJc-T767"   # ROMOCONT/VIDEOS LISTOS PARA SUBIR
DRIVE_SINVOZ = "1EwH6F6YbSBHkoCqHfnp9jLI3nD79HN8L"   # ROMOCONT/VIDEOS SIN VOZ

W, H, FPS = 1080, 1920, 30
# .mpeg/.mpga entran porque las voces exportadas de IA suelen venir así (son mp3).
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
              ".mpeg", ".mpga", ".opus", ".aif", ".aiff")

# Audio (EBU R128). El lecho queda fuerte y la voz 4 LU por encima. -12 deja el
# headroom justo para que la voz encaje arriba sin que el limitador la aplaste.
# Volumen (Marlon, 23-10-2026): en CapCut les subía 300–400 % y esos videos quedaban
# en −7/−9 LUFS; el motor los sacaba en −12, o sea 3–5 dB más bajos. Ahora: se
# empareja todo a −12 y se empuja +EMPUJE_DB con un limitador. Marlon eligió la
# opción D: ≈ −6,7 LUFS (más fuerte que su ES 122 de CapCut, −7,0), sin saturar.
LUFS_BED = -12.0
EMPUJE_DB = 15.0
LUFS_VO = -8.0
VOZ_EMPUJE_DB = 10.0  # la voz choca con el techo de picos antes de llegar: se empuja y la ataja el limitador final
# Bajos: los teléfonos no reproducen por debajo de ~200 Hz; esa energía no se oye y
# le roba volumen a todo lo demás. Corte fuerte en 180 Hz (24 dB/oct), un poco
# menos de «retumbo» en 250 Hz y más presencia en 3 kHz.
HIGHPASS_HZ = 180      # fuera los bajos de la mezcla
DUCK_DB = -10.0         # cuánto baja la música mientras habla la voz
GUARD = 0.35           # margen para que la voz no pise el efecto


# --------------------------------------------------------------------------- #
# ffmpeg
# --------------------------------------------------------------------------- #

FFMPEG = plat.binario("ffmpeg")
FFPROBE = plat.binario("ffprobe")


def probe_duration(path):
    if not FFPROBE or not path:
        return 0.0
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=60, **plat.SILENCIO)
        return float(r.stdout.strip() or 0)
    except Exception:
        return 0.0


_SPAN_CACHE = {}


def speech_span(path):
    """(inicio, fin) de la parte que realmente suena del audio, en segundos.

    Las voces traen silencio al principio y al final; sin recortarlo el ducking
    baja la música antes de que empiece a hablar y la deja baja después.
    """
    if path in _SPAN_CACHE:
        return _SPAN_CACHE[path]
    dur = probe_duration(path)
    span = (0.0, dur)
    try:
        r = subprocess.run(
            [FFMPEG, "-v", "error", "-i", path, "-f", "s16le", "-ac", "1",
             "-ar", "8000", "-"], capture_output=True, timeout=120, **plat.SILENCIO)
        buf = r.stdout
        n = len(buf) // 2
        if n:
            import array
            a = array.array("h")
            a.frombytes(buf[:n * 2])
            peak = max((abs(v) for v in a), default=0)
            umbral = max(int(peak * 0.02), 120)      # ~-34 dB del pico
            first = next((i for i, v in enumerate(a) if abs(v) > umbral), None)
            if first is not None:
                last = n - next(i for i, v in enumerate(reversed(a)) if abs(v) > umbral)
                span = (max(first / 8000 - 0.05, 0.0), min(last / 8000 + 0.08, dur))
    except Exception:
        pass
    _SPAN_CACHE[path] = span
    return span


def has_audio(path):
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "a", "-show_entries",
             "stream=codec_type", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=60, **plat.SILENCIO)
        return "audio" in r.stdout
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Efecto del cambio
# --------------------------------------------------------------------------- #

# Tempo interno del efecto: se fija en 112 BPM, el tempo con el que se graban las
# demostrativas (antes se pedía el BPM en la UI y no servía de nada).
BEAT = 60.0 / 112.0

# Efectos del cambio, nueva generación (Marlon, 23-10-2026). Los 10 viejos (luces,
# temblor, discoteca…) se fueron: le parecían aburridos. Regla: luz que se siente
# real, pulsos cortos, blanco de base y color de acento, nunca tapar ni apagar al
# DJ, el golpe justo en la marca, y sigue todo el video después del cambio.
#
# Cada efecto tiene dos partes:
#  - la LUZ: una capa transparente hecha en Remotion (romo-reel/src/EfectoCambio.tsx)
#    en <plantillas>/EFECTOS/<nombre>_sNN.webm, 41 s, con el golpe en su segundo 1;
#  - lo que mueve el VIDEO (golpe de zoom, quemada de exposición, cortes de cámara),
#    que lo hace ffmpeg aquí abajo.
# El efecto de un video se guarda como "<nombre>:<semilla>" (p. ej. "camara:3") para
# que un retoque repita exactamente el mismo.
EFFECTS = ["golpe", "estrobo", "camara", "exposicion", "estrobo-color"]
NOMBRES_EFECTO = {"golpe": "Flash + golpe", "estrobo": "Estrobo", "camara": "Flash de cámara",
                  "exposicion": "Golpe de exposición", "estrobo-color": "Estrobo de color"}
EFECTO_SEMILLAS = 10
GOLPE_EF = 1.0   # la capa de luz trae el golpe en su segundo 1: arranca 1 s antes de la marca

# Margen que se le respeta al efecto para que la voz no pise el golpe. Es solo el
# ARRANQUE, no el efecto entero: si se protegiera todo el efecto sostenido no
# quedaría nunca hueco después del cambio y la voz solo podría ir al principio.
EFFECT_ONSET = 1.2


def effect_duration(*_):
    """Lo que hay que respetarle al efecto: su arranque, no toda su cola."""
    return EFFECT_ONSET


def partir_efecto(effect):
    """"camara:3" → ("camara", 3). Un nombre sin semilla → (nombre, None).
    Algo que no es un efecto nuevo (auto, o uno de los viejos) → (None, None)."""
    nombre, _, sem = str(effect or "").partition(":")
    if nombre not in EFFECTS:
        return None, None
    return nombre, (int(sem) if sem.isdigit() else None)


def _pulso(m, periodo, caida, var="t"):
    """Envolvente de pulsos que se repite desde el marcador hasta el final (con `mod`:
    el efecto puede durar 20 s y una lista de instantes se volvía interminable)."""
    return (f"max(1-mod({var}-{m:.3f},{periodo:.4f})/{caida:.3f},0)"
            f"*gte({var},{m:.3f})")


def _cae(m, dura, var="t"):
    """1 en el marcador y cae a 0 en `dura` segundos."""
    return f"max(1-({var}-{m:.3f})/{dura:.3f},0)*gte({var},{m:.3f})"


# --- cortes de cámara: saltos de encuadre sin transición (Marlon: «exagerados,
# bruscos, nada de temblorcitos»; y que no sea siempre el mismo patrón) ---------

# Cuándo hay corte (segundos desde la marca, hasta `fin`).
def _ritmo(nombre, fin):
    B = BEAT
    if nombre == "disparos":      # Flash de cámara: los 3 disparos y uno cada 2 beats
        base = [0.0, 5 / FPS, 11 / FPS]
        return base + [2 * B * k for k in range(1, int(fin / (2 * B)) + 2)]
    if nombre == "beat":
        return [B * k for k in range(0, int(fin / B) + 2)]
    if nombre == "dos":
        return [2 * B * k for k in range(0, int(fin / (2 * B)) + 2)]
    if nombre == "contra":        # en la marca y después a contratiempo (beats 2 y 4)
        return [0.0] + [B * (2 * k + 1) for k in range(0, int(fin / (2 * B)) + 2)]
    if nombre == "doble":         # dos cortes pegados cada 2 beats
        return sorted(x for k in range(0, int(fin / (2 * B)) + 2) for x in (2 * B * k, 2 * B * k + 0.13))
    if nombre == "compas":        # ráfaga de 3 en el cambio y uno por compás
        return [0.0, B / 2, B] + [4 * B * k for k in range(1, int(fin / (4 * B)) + 2)]
    return []


RITMOS = ["beat", "dos", "contra", "doble", "compas"]
ENCUADRES = ["saltos", "dentro-fuera", "escalera", "lados", "vertical", "azar"]


def _encuadre(nombre, i, o, rng):
    """Encuadre del corte número i: (zoom, x 0–1, y 0–1, ángulo en grados).
    `o` desplaza el patrón según la semilla para que dos semillas no arranquen igual."""
    if nombre == "saltos":
        return ([1.38, 1.52, 1.66][(i + o) % 3], [0.3, 0.5, 0.7][(2 * i + o) % 3],
                [0.3, 0.5, 0.7][(i + 1 + o) % 3], [-3.4, 0.0, 3.4][(i + o) % 3])
    if nombre == "dentro-fuera":  # cerrado ↔ abierto (el primero, el del golpe, cerrado)
        if i % 2:
            return (1.0, 0.5, 0.5, 0.0)
        k = i // 2 + o
        return (1.6, [0.35, 0.65][k % 2], [0.35, 0.6][(k // 2) % 2], [3.4, -3.4][k % 2])
    if nombre == "escalera":      # cada corte más cerca y vuelve a empezar
        return (1.15 + 0.15 * ((i + o) % 4), 0.5, 0.45, [2.0, -2.0][(i + o) % 2])
    if nombre == "lados":         # izquierda ↔ derecha, inclinado al revés del lado
        izq = (i + o) % 2 == 0
        return (1.5, 0.25 if izq else 0.75, 0.5, 3.4 if izq else -3.4)
    if nombre == "vertical":      # arriba ↔ abajo
        arriba = (i + o) % 2 == 0
        return (1.5, 0.5, 0.28 if arriba else 0.72, [2.0, -2.0][(i // 2 + o) % 2])
    # azar fijo por semilla
    return (rng.choice([1.35, 1.45, 1.55, 1.7]), rng.choice([0.3, 0.4, 0.5, 0.6, 0.7]),
            rng.choice([0.3, 0.45, 0.6, 0.7]), rng.choice([-3.4, -2.0, 0.0, 2.0, 3.4]))


def cortes_de(nombre, semilla):
    """(ritmo, encuadre, desplazamiento) de los cortes de un efecto, o None si no lleva.
    - Flash de cámara: siempre, al ritmo de sus disparos.
    - Golpe de exposición: siempre (la semilla 0, la aprobada: cada beat y «saltos»).
    - Flash + golpe, Estrobo y Estrobo de color: solo las semillas 3, 6 y 9.
    Cada combinación cambia ritmo y encuadre para que no se repita el patrón."""
    k = EFFECTS.index(nombre)
    if nombre == "camara":
        return ("disparos", ENCUADRES[semilla % len(ENCUADRES)], semilla)
    if nombre == "exposicion":
        if semilla == 0:
            return ("beat", "saltos", 0)
        return (RITMOS[(2 * semilla + 1) % len(RITMOS)], ENCUADRES[(semilla + 1) % len(ENCUADRES)], semilla)
    if semilla and semilla % 3 == 0:
        n = semilla // 3
        return (RITMOS[(n + k) % len(RITMOS)], ENCUADRES[(2 * n + k) % len(ENCUADRES)], semilla)
    return None


def _escalones(tiempos, valores, var, inicial):
    """Valor que salta en cada instante (sin suavizar): v0 + Σ (vi − vi−1)·[t ≥ ti]."""
    partes, prev = [f"{inicial:.4f}"], inicial
    for t, v in zip(tiempos, valores):
        if abs(v - prev) > 1e-6:
            partes.append(f"{v - prev:+.4f}*gte({var},{t:.3f})")
        prev = v
    return "+".join(partes).replace("+-", "-")


# Golpe de zoom de cada efecto: (en la marca, en cada beat). Se multiplica con los cortes.
PUNCH = {"golpe": (0.14, 0.035), "estrobo": (0.04, 0.0), "camara": (0.06, 0.0),
         "exposicion": (0.10, 0.02), "estrobo-color": (0.04, 0.0)}


def build_effect(marker, style, duration, intensity):
    """Filtros que mueven el VIDEO para el efecto `style` ("nombre:semilla"): quemada
    de exposición, rotación y zoom (golpe + cortes). La luz va aparte, como capa."""
    nombre, semilla = partir_efecto(style)
    if not nombre:
        return []
    semilla = semilla or 0
    m, i = float(marker), float(intensity)
    d = max(float(duration), m + 0.5)
    out = []
    if nombre == "exposicion":
        # la imagen se «quema» de luz en el cambio y late suave por beat
        out.append(f"eq=eval=frame:brightness='{0.42 * i:.3f}*({_cae(m, 0.45)})+{0.10 * i:.3f}*({_pulso(m, BEAT, 0.14)})'"
                   f":contrast='1+{0.35 * i:.3f}*({_cae(m, 0.45)})':saturation='1-0.3*({_cae(m, 0.45)})'")
    corte = cortes_de(nombre, semilla)
    tiempos, encuadres = [], []
    if corte:
        ritmo, patron, o = corte
        rng = random.Random(semilla * 31 + EFFECTS.index(nombre))
        tiempos = [m + x for x in _ritmo(ritmo, d - m) if m + x < d]
        encuadres = [_encuadre(patron, k, o, rng) for k in range(len(tiempos))]
    tz = f"(on/{FPS})"
    if encuadres and any(abs(e[3]) > 0 for e in encuadres):
        ang = _escalones(tiempos, [e[3] * 3.14159 / 180 for e in encuadres], "t", 0.0)
        out.append(f"rotate=a='{ang}':fillcolor=black")
    a, b = PUNCH[nombre]
    punch = f"(1+{a * i:.3f}*({_cae(m, 0.28, tz)})+{b * i:.3f}*({_pulso(m, BEAT, 0.16, tz)}))"
    zc = _escalones(tiempos, [e[0] for e in encuadres], tz, 1.0) if encuadres else "1"
    xc = _escalones(tiempos, [e[1] for e in encuadres], tz, 0.5) if encuadres else "0.5"
    yc = _escalones(tiempos, [e[2] for e in encuadres], tz, 0.5) if encuadres else "0.5"
    out.append(f"zoompan=z='({zc})*{punch}':d=1:x='(iw-iw/zoom)*({xc})':y='(ih-ih/zoom)*({yc})':s={W}x{H}:fps={FPS}")
    return out


def efecto_archivo(cfg, effect):
    """La capa de luz del efecto ("nombre:semilla"), si está en la carpeta."""
    nombre, semilla = partir_efecto(effect)
    if not nombre:
        return ""
    ruta = os.path.join(cfg.get("tpl_dir") or "", "EFECTOS", f"{nombre}_s{(semilla or 0):02d}.webm")
    return ruta if os.path.isfile(ruta) else ""


# --------------------------------------------------------------------------- #
# Voz en off: dónde cabe sin pisar el cambio
# --------------------------------------------------------------------------- #

def place_vo(duration, marker, eff_dur, vo_dur, prefer="auto"):
    """Elige el segundo donde arranca la voz. Devuelve (t, aviso)."""
    blocked_a = max(marker - GUARD, 0.0)
    blocked_b = min(marker + eff_dur + GUARD, duration)

    start_t = 0.15
    start_ok = start_t + vo_dur <= blocked_a

    # Hueco de atrás: lo ideal es pegada al final, pero si no llega, sirve
    # cualquier arranque después del efecto que quepa antes de que acabe el clip.
    end_t = max(duration - vo_dur - 0.15, 0.0)
    if end_t < blocked_b:
        end_t = blocked_b
    end_ok = end_t >= blocked_b and end_t + vo_dur <= duration

    opts = []
    if start_ok:
        opts.append(("start", start_t))
    if end_ok:
        opts.append(("end", end_t))

    if prefer == "start" and start_ok:
        return start_t, ""
    if prefer == "end" and end_ok:
        return end_t, ""
    if opts:
        return random.choice(opts)[1], ""

    # No cabe entera en ningún hueco: usa el hueco más grande.
    gap_start = blocked_a
    gap_end = duration - blocked_b
    if gap_start >= gap_end and gap_start > 0.4:
        return max(blocked_a - vo_dur - 0.05, 0.0), (
            f"La voz ({vo_dur:.1f}s) no cabe antes del cambio; se corrió lo que se pudo.")
    if gap_end > 0.4:
        return blocked_b, (
            f"La voz ({vo_dur:.1f}s) no cabe después del cambio; puede pisar el final.")
    return 0.15, "El clip es muy corto para la voz sin pisar el cambio."


# --------------------------------------------------------------------------- #
# Cadenas de filtros
# --------------------------------------------------------------------------- #

def base_chain(item):
    return [
        f"scale={W}:{H}:force_original_aspect_ratio=increase",
        f"crop={W}:{H}", "setsar=1", f"fps={FPS}",
    ] + build_effect(item["marker"], item["effect"], item["duration"],
                     item["intensity"])


def build_vf(item, cfg):
    return ",".join(base_chain(item)
                    + [tpl.build(item["type"], item["template"],
                                 cfg.get("font") or DEFAULT_FONT)])


def overlay_file(item, cfg):
    """Ruta del overlay si la plantilla elegida es un archivo (id <= -100)."""
    if item["template"] is None or item["template"] > -100:
        return ""
    files = tpl.list_overlays(cfg.get("tpl_dir"), item.get("tpl_carpeta") or item["type"])
    k = -100 - item["template"]
    return files[k] if 0 <= k < len(files) else ""


def has_alpha(path):
    """¿El overlay ya trae canal alfa? Si no, se le quita el verde con colorkey.

    En WebM el alfa de VP8/VP9 va en una pista aparte y `pix_fmt` sigue diciendo
    yuv420p: hay que mirar la etiqueta `alpha_mode` del contenedor.
    """
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=pix_fmt:stream_tags=alpha_mode", "-of", "default=nw=1",
             path],
            capture_output=True, text=True, timeout=30, **plat.SILENCIO)
        out = r.stdout.lower()
        if "alpha_mode=1" in out:
            return True
        pf = ""
        for line in out.splitlines():
            if line.startswith("pix_fmt="):
                pf = line.split("=", 1)[1].strip()
        return pf.startswith(("yuva", "rgba", "argb", "abgr", "bgra", "gbrap"))
    except Exception:
        return False


_DECODERS = None


def tiene_decoder(nombre):
    """¿Este ffmpeg trae el decodificador? Se pregunta una vez y se recuerda.

    El ffmpeg de la Mac va bundleado y se sabe qué trae, pero en Windows lo baja
    el instalador y el equipo podría tener otro en el PATH. Sin esta comprobación
    un build sin libvpx no daría "fondo negro" sino que reventaría el render
    entero con «Unknown decoder».
    """
    global _DECODERS
    if _DECODERS is None:
        try:
            r = subprocess.run([FFMPEG, "-v", "quiet", "-decoders"],
                               capture_output=True, text=True, timeout=30,
                               **plat.SILENCIO)
            _DECODERS = r.stdout
        except Exception:
            _DECODERS = ""
    return f" {nombre} " in _DECODERS


def overlay_decoder(path):
    """El alfa de un WebM VP8/VP9 solo lo saca el decodificador de libvpx; el
    decodificador por defecto de ffmpeg devuelve el fondo en negro."""
    if not path.lower().endswith(".webm"):
        return []
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=codec_name", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30, **plat.SILENCIO)
        codec = r.stdout.strip()
        if codec in ("vp9", "vp8"):
            dec = "libvpx-vp9" if codec == "vp9" else "libvpx"
            if tiene_decoder(dec):
                return ["-c:v", dec]
    except Exception:
        pass
    return []


TPL_DUR = 4.0          # cuánto dura la plantilla sobre el video
TPL_FADE = 0.45        # desvanecido de salida


def _capa_efecto(item, k_ef, entrada):
    """Pega la capa de luz del efecto (entrada nº k_ef) 1 s antes de la marca, para
    que su golpe caiga en el cambio; si la marca está antes del segundo 1 se le
    recorta el comienzo. Se escala (viene a media resolución) y se corta con el clip."""
    ini = float(item["marker"]) - GOLPE_EF
    corte = f"trim=start={-ini:.3f}," if ini < 0 else ""
    return (f"[{k_ef}:v]scale={W}:{H},format=yuva420p,{corte}setpts=PTS-STARTPTS+{max(ini, 0.0):.3f}/TB[ef];"
            f"[{entrada}][ef]overlay=0:0:eof_action=pass[conluz];")


def build_graph(item, cfg, ov_path, ef_path):
    """filter_complex completo: el clip con su efecto, la capa de luz encima y la
    plantilla encima de todo (el texto siempre se lee por encima de la luz)."""
    k_ef = 2 if ov_path else 1
    g = f"[0:v]{','.join(base_chain(item))}[base];"
    entrada = "base"
    if ef_path:
        g += _capa_efecto(item, k_ef, entrada)
        entrada = "conluz"
    if ov_path:
        return g + build_overlay_complex(item, ov_path, entrada)
    return g + f"[{entrada}]{tpl.build(item['type'], item['template'], cfg.get('font') or DEFAULT_FONT)}[v]"


def build_overlay_complex(item, ov_path, entrada=None):
    """filter_complex para plantillas de video: croma o alfa + superposición.
    Con `entrada` solo devuelve la parte de la plantilla, encima de esa etiqueta.

    Las plantillas de Remotion duran solo la animación (2 s). Aquí se congela el
    último frame hasta los 4 s y se las desvanece al final, así se comportan
    igual que las plantillas de texto.
    """
    key = "" if has_alpha(ov_path) else "colorkey=0x00D400:0.32:0.12,"
    ov_dur = probe_duration(ov_path)

    # Si la plantilla es más corta que los 4 s, se congela su último frame. Ojo:
    # `tpad` clona los frames repitiendo el timestamp, así que hay que regenerar
    # los tiempos con `setpts` o el overlay se queda pegado en su último instante.
    hold = ""
    if 0 < ov_dur < TPL_DUR - 0.05:
        hold = (f"tpad=stop_mode=clone:stop_duration={TPL_DUR - ov_dur:.2f},"
                f"setpts=N/{FPS}/TB,"
                f"fade=t=out:st={TPL_DUR - TPL_FADE:.2f}:d={TPL_FADE}:alpha=1,")
    plantilla = (
        f"[1:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"{key}format=yuva420p,{hold}setpts=PTS-STARTPTS[ov];"
        f"[{entrada or 'base'}][ov]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:"
        f"eof_action=pass:shortest=0[v]"
    )
    if entrada:
        return plantilla
    return f"[0:v]{','.join(base_chain(item))}[base];" + plantilla


def build_af_bed(gain_db=0.0):
    """Audio del video: fuera los bajos, volumen al máximo razonable."""
    af = [
        f"highpass=f={HIGHPASS_HZ}:poles=2", f"highpass=f={HIGHPASS_HZ}:poles=2",
        "equalizer=f=250:t=q:w=1:g=-3", "equalizer=f=3000:t=q:w=1:g=3",
        f"loudnorm=I={LUFS_BED}:TP=-1.0:LRA=11",
        "aresample=48000",
        f"volume={EMPUJE_DB + gain_db:.2f}dB",
        "alimiter=limit=0.89:attack=3:release=60:level=disabled",
    ]
    return ",".join(af)


def duck_expr(a, b):
    """Curva de volumen de la música: baja DUCK_DB mientras habla la voz, con
    rampas cortas para que no se oiga el escalón."""
    lo = 10 ** (DUCK_DB / 20.0)
    up, down = 0.15, 0.30
    return (
        f"if(lt(t,{a:.3f}),1,"
        f"if(lt(t,{a + up:.3f}),1-{1 - lo:.4f}*(t-{a:.3f})/{up},"
        f"if(lt(t,{b:.3f}),{lo:.4f},"
        f"if(lt(t,{b + down:.3f}),{lo:.4f}+{1 - lo:.4f}*(t-{b:.3f})/{down},1))))"
    )


def build_mix(vo_at, music_gain_db, vo_gain_db, total_dur, vo_dur, span=None):
    """Mezcla la voz sobre el audio ya normalizado del SV.

    Notas ganadas a golpes:
    - Las voces llegan muy bajas (-25/-30 LUFS) y con muchísimo rango dinámico.
      `loudnorm` solo no las levanta: choca contra el techo de picos y se queda
      20 dB por debajo del objetivo. Hay que densificarlas primero con
      `speechnorm` + `compand` y recién ahí normalizar.
    - El ducking va por curva de volumen explícita y no por `sidechaincompress`:
      sabemos exactamente cuándo habla la voz, y aquel filtro además cortaba la
      música al terminar la cadena lateral.
    - Nada de `atrim` después de `loudnorm`: desplaza los timestamps y se come
      la pista.
    """
    delay = int(max(vo_at, 0) * 1000)
    a, b = vo_at, vo_at + vo_dur
    # El recorte del silencio va primero de todo, con los timestamps reseteados.
    trim = ""
    if span and (span[0] > 0.01 or span[1] < vo_dur - 0.01):
        trim = f"atrim=start={span[0]:.3f}:end={span[1]:.3f},asetpts=PTS-STARTPTS,"
    vo_pre = (
        trim +
        "highpass=f=150,"
        "speechnorm=e=50:r=0.001:l=1,"
        "compand=attacks=0.002:decays=0.12:points=-60/-24|-30/-9|-12/-4|0/-2,"
        "alimiter=limit=0.89:level=disabled,"
        f"loudnorm=I={LUFS_VO}:TP=-1.0"
    )
    return (
        f"[0:a]volume='{duck_expr(a, b)}':eval=frame,"
        f"volume={music_gain_db:.2f}dB,aresample=48000[bed];"
        f"[1:a]{vo_pre},volume={VOZ_EMPUJE_DB + vo_gain_db:.2f}dB,"
        f"adelay={delay}:all=1,apad=whole_dur={total_dur:.3f},aresample=48000[vo];"
        f"[bed][vo]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.84:attack=3:release=60:level=disabled[a]"
    )


# --------------------------------------------------------------------------- #
# Lote
# --------------------------------------------------------------------------- #

BATCH = {"items": [], "running": False, "cancel": False}
LOCK = threading.Lock()


def save_batch():
    """Guarda el lote en disco para que las marcas sobrevivan a un reinicio.

    Se llama en los puntos con estado estable (lote cargado, retoque aplicado,
    render terminado), nunca en cada tick de progreso, para no machacar el disco.
    Un fallo al guardar jamás debe tumbar el render, por eso va todo en try.
    """
    try:
        with LOCK:
            items = [dict(it) for it in BATCH["items"]]
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = BATCH_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False)
        os.replace(tmp, BATCH_FILE)
    except Exception:  # noqa: BLE001
        pass


def load_batch():
    """Restaura el lote guardado al arrancar. Deja el motor en reposo."""
    try:
        with open(BATCH_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        return
    items = data.get("items") if isinstance(data, dict) else None
    if not items:
        return
    # Un render a medias (proceso muerto) se deja re-aplicable; lo terminado se
    # respeta tal cual para no volver a subir ni re-registrar nada.
    for it in items:
        if it.get("state") not in ("listo", "error"):
            it["state"] = "listo" if (it.get("con_voz") or it.get("sv")) else "pendiente"
    BATCH["items"] = items
    BATCH["running"] = False
    BATCH["cancel"] = False


def new_item(video, marker, mtype, opts):
    return {
        "id": os.path.basename(video) + "|" + str(int(time.time() * 1000) % 100000),
        "video": video,
        "name": os.path.basename(video),
        "marker": float(marker),
        "type": mtype,
        "categoria": "DEMOSTRATIVAS",
        "duration": 0.0,
        # Recorte del clip. `trim_in` es el segundo del ARCHIVO donde empieza el
        # video final y `trim_len` cuánto dura. Todo lo demás (marcador, efecto,
        # voz) trabaja ya sobre el clip recortado: el marcador se rebasa una sola
        # vez al armar el lote, así ninguna otra parte tiene que saber del recorte.
        "trim_in": 0.0,
        "trim_len": 0.0,      # 0 = hasta el final del archivo
        "template": -1,
        "effect": opts.get("effect", "auto"),
        "intensity": float(opts.get("intensity", 1.0)),
        "vo": "",
        "vo_at": 0.0,
        "vo_dur": 0.0,
        "music_gain": 0.0,
        "vo_gain": 0.0,
        "base_name": "",
        "registrado": False,
        "state": "pendiente",
        "progress": 0,
        "phase": "",
        "warn": "",
        "error": "",
        "sv": "",
        "con_voz": "",
    }


def run_ffmpeg(args, item, total, phase, base, span):
    cmd = [FFMPEG, "-y", "-progress", "pipe:1", "-nostats"] + args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, **plat.SILENCIO)
    for line in proc.stdout:
        if line.startswith("out_time_ms=") and total > 0:
            try:
                done = int(line.split("=")[1]) / 1_000_000
                with LOCK:
                    item["progress"] = round(base + min(done / total, 1.0) * span)
                    item["phase"] = phase
            except ValueError:
                pass
    err = proc.stderr.read()
    proc.wait()
    return proc.returncode, err


def recorte_args(item):
    """Opciones de entrada de ffmpeg para el recorte del clip.

    Van SIEMPRE inmediatamente antes del `-i` del video, nunca antes del `-i` de
    la plantilla. `-ss` antes de la entrada busca rápido y, como aquí se
    recodifica, además queda exacto al frame.
    """
    args = []
    if item.get("trim_in", 0) > 0.001:
        args += ["-ss", f"{item['trim_in']:.3f}"]
    if item.get("trim_len", 0) > 0.001:
        args += ["-t", f"{item['trim_len']:.3f}"]
    return args


def pool_plantillas(cfg, tecnica):
    """Ids de plantilla elegibles para esta técnica.

    El repertorio son las **animadas de Remotion** que haya en la carpeta de
    plantillas. Las de texto que dibuja ffmpeg (`templates.py`) siguen en el
    código pero solo como red de emergencia: si la carpeta está vacía o mal
    apuntada, mejor sacar el video con una plantilla sosa que no sacarlo.
    """
    n = len(tpl.list_overlays(cfg.get("tpl_dir"), tecnica))
    if n:
        return [-100 - k for k in range(n)]
    return list(range(tpl.PER_TECHNIQUE))


USADAS_FILE = os.path.join(CONFIG_DIR, "usadas.json")
_USADAS_LOCK = threading.Lock()


def carpeta_plantillas(cfg, item):
    """De qué carpeta sale la plantilla: los RLL (un profe tocando) usan PROFES
    si existe; todo lo demás, la carpeta de su técnica."""
    if ((item.get("categoria") or "").upper() == "RELLENO"
            and tpl.list_overlays(cfg.get("tpl_dir"), "PROFES")):
        return "PROFES"
    return item["type"]


def _direccion(nombre):
    """Dirección de una rmn_ (rmn_d3_s07.webm → 3). Las rmt_ no tienen."""
    m = re.match(r"rmn_d(\d+)_", os.path.basename(nombre).lower())
    return int(m.group(1)) if m else None


def _leer_usadas(cfg):
    if cfg.get("usadas_leer"):
        return cfg["usadas_leer"]() or []
    try:
        with open(cfg.get("usadas_path") or USADAS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _guardar_usadas(cfg, lista):
    if cfg.get("usadas_guardar"):
        cfg["usadas_guardar"](lista)
        return
    ruta = cfg.get("usadas_path") or USADAS_FILE
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w") as f:
            json.dump(lista, f)
    except Exception:
        pass


def elegir_plantilla(cfg, carpeta):
    """Id de plantilla para un video nuevo, sin repetir (Marlon, 23-10-2026).

    En vez de azar puro: se recuerda qué plantillas salieron (de todas las
    carpetas, las más nuevas al final) y se elige entre las que hace más tiempo
    no salen, nunca de la misma dirección que los 2 videos anteriores.
    """
    files = tpl.list_overlays(cfg.get("tpl_dir"), carpeta)
    if not files:
        return random.choice(pool_plantillas(cfg, carpeta))
    with _USADAS_LOCK:
        usadas = _leer_usadas(cfg)
        claves = [f"{carpeta}/{os.path.basename(f)}" for f in files]
        plantillas = [u for u in usadas if not u.startswith(("EF/", "VOZ/"))]
        evitar = {_direccion(u) for u in plantillas[-2:]} - {None}
        cand = [k for k in claves if _direccion(k) not in evitar] or claves
        # cuanto más atrás en la lista (o si nunca salió), mejor
        hace = {k: (usadas.index(k) if k in usadas else -1) for k in cand}
        menor = min(hace.values())
        elegida = random.choice([k for k in cand if hace[k] == menor])
        usadas = [u for u in usadas if u != elegida] + [elegida]
        _guardar_usadas(cfg, usadas[-500:])
    return -100 - claves.index(elegida)


def elegir_voz(cfg, voices):
    """Voz en off sin repetir (Marlon, 23-10-2026: 9 voces de «clase de DJ gratis
    para Quito»): la que hace más tiempo no sale. Los nombres van numerados para
    que, en orden, nunca suene la misma persona dos veces seguidas."""
    with _USADAS_LOCK:
        usadas = _leer_usadas(cfg)
        vz = [u[4:] for u in usadas if u.startswith("VOZ/")]
        nombres = [os.path.basename(v) for v in voices]
        hace = {n: (vz.index(n) if n in vz else -1) for n in nombres}
        menor = min(hace.values())
        elegida = sorted(n for n in nombres if hace[n] == menor)[0]
        usadas = [u for u in usadas if u != "VOZ/" + elegida] + ["VOZ/" + elegida]
        _guardar_usadas(cfg, usadas[-500:])
    return voices[nombres.index(elegida)]


def elegir_efecto(cfg, pedido):
    """"nombre:semilla" para un video. Si ya trae semilla (un retoque) se respeta;
    si trae solo el nombre se elige la semilla; si es «auto» o uno de los viejos, se
    elige efecto y semilla. Rotación como la de plantillas: la combinación que hace
    más tiempo no sale y nunca el mismo efecto que el video anterior."""
    nombre, semilla = partir_efecto(pedido)
    if nombre and semilla is not None:
        return f"{nombre}:{semilla}"
    nombres = [nombre] if nombre else EFFECTS
    carpeta = os.path.join(cfg.get("tpl_dir") or "", "EFECTOS")
    hay = [f"{n}:{s}" for n in nombres for s in range(EFECTO_SEMILLAS)
           if os.path.isfile(os.path.join(carpeta, f"{n}_s{s:02d}.webm"))]
    if not hay:   # sin carpeta de efectos: igual sale el movimiento de video (sin la luz)
        return f"{nombre or random.choice(EFFECTS)}:0"
    with _USADAS_LOCK:
        usadas = _leer_usadas(cfg)
        efs = [u[3:] for u in usadas if u.startswith("EF/")]
        evitar = {efs[-1].split(":")[0]} if efs and not nombre else set()
        cand = [h for h in hay if h.split(":")[0] not in evitar] or hay
        hace = {h: (efs.index(h) if h in efs else -1) for h in cand}
        menor = min(hace.values())
        elegido = random.choice([h for h in cand if hace[h] == menor])
        usadas = [u for u in usadas if u != "EF/" + elegido] + ["EF/" + elegido]
        _guardar_usadas(cfg, usadas[-500:])
    return elegido


def render_item(item, cfg, voices, full=True):
    """Renderiza SV (si `full`) y la versión con voz."""
    out_dir = cfg.get("out_dir") or plat.carpeta_videos()
    os.makedirs(out_dir, exist_ok=True)
    base = item["base_name"] or os.path.splitext(item["name"])[0]
    sv_path = os.path.join(out_dir, f"{base} SV.mp4")
    voz_path = os.path.join(out_dir, f"{base}.mp4")

    item["duration"] = item["duration"] or probe_duration(item["video"])
    eff_dur = effect_duration()

    item["effect"] = elegir_efecto(cfg, item["effect"])
    if item["template"] in (-1, None):
        # -1/None = aleatoria. Un template None llegaba cuando el panel mandaba un
        # número inválido (NaN → null): ahora se trata como aleatoria en vez de
        # reventar más abajo al comparar None > -100.
        # Solo entran las plantillas animadas de la carpeta (ids
        # <= -100): las de texto que dibujaba ffmpeg quedaron retiradas del
        # sorteo por decisión de Marlon (29-07-2026), se veían genéricas al lado
        # de las de Remotion.
        item["tpl_carpeta"] = carpeta_plantillas(cfg, item)
        item["template"] = elegir_plantilla(cfg, item["tpl_carpeta"])

    if full:
        with LOCK:
            item.update(state="render", phase="Video + plantilla", progress=1)
        ov = overlay_file(item, cfg)
        # El recorte va como opción de ENTRADA y solo delante del clip: así el
        # descarte ocurre antes de los filtros y el resto de la cadena ve un video
        # que empieza en 0. Se usa `-t` (duración) y no `-to` (instante), que junto
        # a `-ss` de entrada es ambiguo según la versión de ffmpeg. La plantilla no
        # se recorta: sus `-ss`/`-t` no deben tocarla.
        rec = recorte_args(item)
        ef = efecto_archivo(cfg, item["effect"])
        # `0:a:0?` y no `0:a?`: los iPhone nuevos meten una 2ª pista de audio
        # espacial en `apple_apac`, un códec que ffmpeg NO decodifica. Con
        # `0:a?` se mapeaban todas y el render reventaba entero; se toma solo
        # la 1ª pista (el AAC estéreo normal). El `?` la hace opcional.
        args = rec + ["-i", item["video"]]
        if ov:
            args += overlay_decoder(ov) + ["-i", ov]
        if ef:
            args += overlay_decoder(ef) + ["-i", ef]
        args += ["-filter_complex", build_graph(item, cfg, ov, ef), "-map", "[v]", "-map", "0:a:0?"]
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                 "-pix_fmt", "yuv420p"]
        if has_audio(item["video"]):
            args += ["-af", build_af_bed(), "-c:a", "aac", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += ["-movflags", "+faststart", sv_path]
        code, err = run_ffmpeg(args, item, item["duration"], "Video + plantilla", 1, 72)
        if code != 0:
            with LOCK:
                item.update(state="error", error=err[-1200:])
            return
        item["sv"] = sv_path

    if not item["sv"] or not os.path.isfile(item["sv"]):
        with LOCK:
            item.update(state="error", error="Falta el SV; hay que rehacer el render completo.")
        return

    # --- voz en off ---
    if not item["vo"] and voices:
        item["vo"] = elegir_voz(cfg, voices)
    if item["vo"]:
        # vo_dur = lo que realmente suena, no el largo del archivo: así el
        # ducking y la colocación no cuentan el silencio de los extremos.
        span = speech_span(item["vo"])
        item["vo_span"] = span
        item["vo_dur"] = round(span[1] - span[0], 3)
        if not item.get("vo_locked"):
            t, warn = place_vo(item["duration"], item["marker"], eff_dur,
                               item["vo_dur"], cfg.get("vo_prefer", "auto"))
            item["vo_at"], item["warn"] = t, warn
        with LOCK:
            item.update(phase="Mezclando voz", progress=76)
        code, err = run_ffmpeg(
            ["-i", item["sv"], "-i", item["vo"],
             "-filter_complex", build_mix(item["vo_at"], item["music_gain"],
                                          item["vo_gain"], item["duration"],
                                          item["vo_dur"], item.get("vo_span")),
             "-map", "0:v", "-c:v", "copy", "-map", "[a]",
             "-c:a", "aac", "-b:a", "192k", "-ac", "2",
             "-movflags", "+faststart", voz_path],
            item, item["duration"], "Mezclando voz", 76, 22)
        if code != 0:
            with LOCK:
                item.update(state="error", error=err[-1200:])
            return
        item["con_voz"] = voz_path

    with LOCK:
        item.update(state="listo", progress=100, phase="Listo", error="")

    registrar_en_romocont(item, cfg)
    subir_a_drive(item, cfg)


def es_del_catalogo(item):
    """¿El nombre lleva la nomenclatura de SU categoría (DM055, ES146, RLL400)?

    Si el lote salió con el nombre del archivo de cámara no es un video del
    catálogo: ni se registra en la hoja ni se sube al Drive del equipo.
    """
    nombre = (item.get("base_name") or "").strip()
    categoria = (item.get("categoria") or "DEMOSTRATIVAS").upper()
    prefijo = CATEGORIAS.get(categoria, ("", ""))[0]
    if not prefijo:
        return False
    return bool(re.match(rf"^{prefijo}\s*\d+$", nombre, re.I))


def subir_a_drive(item, cfg):
    """Manda los dos archivos a sus carpetas del Drive.

    Solo encola: la subida corre aparte para que el lote siga renderizando. El
    link a la hoja lo escribe la cola cuando el archivo ya está arriba de verdad
    —nunca antes—, así el ⬇ del dashboard jamás apunta a algo que no existe.
    """
    if not cfg.get("subir_drive", True):
        return
    if not es_del_catalogo(item):
        return
    if not drive.RCLONE:
        with LOCK:
            item["warn"] = ((item.get("warn") or "") +
                            " No se subió a Drive: falta rclone.").strip()
        return
    sinvoz, listos = cfg.get("drive_sinvoz", ""), cfg.get("drive_listos", "")
    if item.get("sv") and sinvoz:
        drive.encolar(item["sv"], sinvoz)
    if item.get("con_voz") and listos:
        drive.encolar(item["con_voz"], listos, enlazar=True,
                      web_app_url=cfg.get("web_app_url", ""))


def registrar_en_romocont(item, cfg):
    """Da de alta el video en la hoja del equipo, una sola vez.

    El candado `registrado` importa: el panel de revisión vuelve a llamar al
    render cada vez que se retoca un volumen, y sin él saldría una fila nueva en
    la hoja por cada retoque.
    """
    if item.get("registrado"):
        return
    if not cfg.get("registrar", True):
        return
    nombre = (item.get("base_name") or "").strip()
    categoria = (item.get("categoria") or "DEMOSTRATIVAS").upper()
    if not es_del_catalogo(item):
        return
    editor = cfg.get("editor") or ""
    if not editor:
        with LOCK:
            item["warn"] = ((item.get("warn") or "") +
                            " No se registró en romocont: falta elegir quién edita en ⚙︎.").strip()
        return
    try:
        # DESCRIPCION queda vacía: es para el texto que Lizy publica en TikTok
        # (con eso Peter sabe de qué video vino un lead). Marlon, 12-10-2026.
        register_dm(cfg.get("web_app_url", ""), nombre, editor, categoria)
        with LOCK:
            item["registrado"] = True
    except Exception as exc:  # noqa: BLE001
        with LOCK:
            item["warn"] = ((item.get("warn") or "") +
                            f" No se pudo registrar en romocont: {exc}").strip()


def batch_worker(only_ids=None, full=True):
    cfg = load_config()
    voices = list_voices(cfg.get("vo_dir", ""))
    BATCH["running"] = True
    BATCH["cancel"] = False
    try:
        for it in list(BATCH["items"]):
            if BATCH["cancel"]:
                break
            if only_ids and it["id"] not in only_ids:
                continue
            if not only_ids and it["state"] == "listo":
                continue
            try:
                render_item(it, cfg, voices, full=full)
            except Exception as exc:  # noqa: BLE001
                with LOCK:
                    it.update(state="error", error=str(exc))
            save_batch()  # cada video terminado queda a salvo en disco
    finally:
        BATCH["running"] = False
        save_batch()


# --------------------------------------------------------------------------- #
# Config / voces / Sheet / macOS
# --------------------------------------------------------------------------- #

def plantillas_incluidas():
    """Carpeta `plantillas/` que viene con la app, si la hay.

    En el repo del equipo las 46 plantillas van al lado de `mac/` y `windows/`,
    así que la app las encuentra sola y nadie tiene que configurar nada la
    primera vez. En la copia de Marlon no existe y el valor queda vacío, que es
    lo que había antes.
    """
    for d in (os.path.join(PROJECT, "plantillas"),
              os.path.join(os.path.dirname(PROJECT), "plantillas")):
        if os.path.isdir(d):
            return os.path.abspath(d)
    return ""


def load_config():
    cfg = {}
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    except Exception:
        pass
    cfg.setdefault("web_app_url", DEFAULT_WEBAPP)
    cfg.setdefault("font", DEFAULT_FONT)
    cfg.setdefault("vo_dir", "")
    cfg.setdefault("tpl_dir", plantillas_incluidas())
    cfg.setdefault("out_dir", os.path.join(plat.carpeta_videos(), "VIDEOS ROMO", "MDT"))
    cfg.setdefault("vo_prefer", "auto")
    cfg.setdefault("editor", "")
    # Registrar en la hoja del equipo es una escritura de verdad en un sitio
    # compartido, así que se puede apagar para hacer pruebas sin ensuciarla.
    cfg.setdefault("registrar", True)
    # Subir a Drive es independiente de registrar en la hoja: se puede querer el
    # respaldo en la nube sin tocar la hoja del equipo (y al revés).
    cfg.setdefault("subir_drive", True)
    cfg.setdefault("drive_listos", DRIVE_LISTOS)
    cfg.setdefault("drive_sinvoz", DRIVE_SINVOZ)
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def list_voices(d):
    if not d or not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.lower().endswith(AUDIO_EXTS) and not f.startswith("."))


EDITORES = ["DANIEL", "TIPAN", "MARLONT"]

# Nombre legible de cada técnica. Ya NO se escribe en la hoja de romocont
# (antes iba a DESCRIPCION y le quitaba el lugar a la descripción publicada).
TECNICA_TEXTO = {
    "CORTE": "MEZCLA DE CORTE",
    "METRICA": "MEZCLA MÉTRICA",
    "ARRASTRE": "MEZCLA DE ARRASTRE",
    "STEMS": "MEZCLA CON STEMS",
    "CLASE": "CLASE DE DJ GRATIS",
}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_romocont():
    """Fecha con el formato que ya usa la hoja: «30 de julio 2026»."""
    t = time.localtime()
    return f"{t.tm_mday} de {MESES[t.tm_mon - 1]} {t.tm_year}"


# Categorías que maneja la app, con el prefijo que ESCRIBE y el patrón con el que
# LEE los que ya están en la hoja. No son lo mismo a propósito: RELLENO tiene una
# fila antigua escrita «RL» entre 80 «RLL», y si el patrón no la aceptara podría
# saltarse el número más alto y repetir uno.
CATEGORIAS = {
    "DEMOSTRATIVAS": ("DM", r"^DM\s*0*(\d+)"),
    "ESTUDIANTES": ("ES", r"^ES\s*0*(\d+)"),
    "RELLENO": ("RLL", r"^RLL?\s*0*(\d+)"),
}


def nombre_video(prefijo, n):
    """«DM055»: pegado y siempre con 3 cifras. Regla de Marlon (30-07-2026).

    En la hoja hay filas viejas escritas «DM 032» y otras «DM031»; de aquí en
    adelante todo sale pegado. La lectura del último número no se entera de esto
    porque el patrón admite el espacio.
    """
    return f"{prefijo}{n:03d}"


def dm_nombre(n):
    """Atajo para DEMOSTRATIVAS, que es el caso de siempre."""
    return nombre_video("DM", n)


def numeros_libres(url):
    """El último número usado y el siguiente libre, POR CATEGORÍA.

    Cada categoría lleva su propia serie en la hoja (DM va por 54 mientras ES va
    por 146), así que un lote mezclado consume dos series a la vez y no se puede
    numerar con un solo contador.
    """
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode())
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))
    filas = data if isinstance(data, list) else []

    salida = {}
    for cat, (prefijo, patron) in CATEGORIAS.items():
        pat = re.compile(patron, re.I)
        top = 0
        for v in filas:
            nombre = (v.get("nombre") or "").strip().upper()
            m = pat.match(nombre)
            # Solo cuenta si el nombre lleva el prefijo de ESTA categoría: hay
            # filas con la categoría puesta y el nombre en otro formato, y
            # contarlas mezclaría series.
            if m:
                top = max(top, int(m.group(1)))
        salida[cat] = {
            "prefijo": prefijo,
            "ultimo": top,
            "ultimo_nombre": nombre_video(prefijo, top) if top else "",
            "n": top + 1,
            "nombre": nombre_video(prefijo, top + 1),
        }
    return salida


def register_dm(url, nombre, creador, categoria="DEMOSTRATIVAS", descripcion=""):
    """Inserta el video en la hoja de romocont como PENDIENTE.

    Las columnas van en el orden que espera `Code.gs`; `link` lo llena después
    nube-sync y `tanda` la pone el equipo a mano, así que se dejan vacías.
    """
    payload = json.dumps({
        "action": "insert",
        "video": {
            "id": f"v{int(time.time() * 1000)}",
            "fecha": fecha_romocont(),
            "categoria": categoria,
            "nombre": nombre,
            "estado": "PENDIENTE",
            "creador": (creador or "").upper(),
            "descripcion": descripcion,
        },
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))


def pick(kind):
    """Diálogo nativo del sistema. Ver `plataforma.elegir`."""
    return plat.elegir(kind)


def template_preview(technique, tpl_id, cfg):
    """PNG de la plantilla sobre un fondo neutro, para la galería."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    out = os.path.join(CACHE_DIR, f"tpl_v{tpl.VERSION}_{technique}_{tpl_id}.jpg")
    if os.path.isfile(out):
        return out

    # Plantillas de video (Remotion o croma): se saca un frame del propio archivo
    # sobre el fondo neutro. Sin esto la galería les ponía la miniatura de una
    # plantilla de texto cualquiera, porque el id negativo daba la vuelta al
    # calcular el módulo.
    if tpl_id <= -100:
        files = tpl.list_overlays(cfg.get("tpl_dir"), technique)
        k = -100 - tpl_id
        if not (0 <= k < len(files)):
            return ""
        ov = files[k]
        key = "" if has_alpha(ov) else "colorkey=0x00D400:0.32:0.12,"
        # El salto al frame representativo va con `-ss` de entrada y NO con
        # `select`: `select` descarta frames sin tocar los timestamps, así que
        # cuando el overlay pide su primer frame todavía no ha llegado ninguno y
        # la miniatura salía siendo el fondo pelado (todas idénticas, 2 KB).
        # `-ss` sí adelanta el decodificador; el `setpts` lo realinea con el fondo.
        ss = min(1.8, max(probe_duration(ov) * 0.45, 0.1))
        subprocess.run(
            [FFMPEG, "-y", "-f", "lavfi", "-i",
             f"color=c=0x1b1420:s={W}x{H}:d=4:r=25"]
            + overlay_decoder(ov) + ["-ss", f"{ss:.2f}", "-i", ov, "-filter_complex",
             f"[1:v]{key}format=yuva420p,setpts=PTS-STARTPTS[ov];"
             f"[0:v][ov]overlay=eof_action=pass:shortest=1,scale=420:-2",
             "-frames:v", "1", "-update", "1", "-q:v", "4", out],
            capture_output=True, text=True, **plat.SILENCIO)
        return out if os.path.isfile(out) else ""

    # El frame se toma a 1.5 s, cuando la plantilla ya terminó de entrar. Va con
    # `select` y no con `-ss` porque `-ss` reinicia el reloj del filtro y las
    # animaciones con fade saldrían invisibles (alpha 0).
    vf = ("select='gte(t,1.5)',"
          + tpl.build(technique, tpl_id, cfg.get("font") or DEFAULT_FONT)
          + ",scale=420:-2")
    subprocess.run(
        [FFMPEG, "-y", "-f", "lavfi", "-i",
         f"color=c=0x1b1420:s={W}x{H}:d=4:r=25", "-frames:v", "1",
         "-vf", vf, "-update", "1", "-q:v", "4", out],
        capture_output=True, text=True, **plat.SILENCIO)
    return out if os.path.isfile(out) else ""


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

class Handler(BaseHTTPRequestHandler):
    server_version = "ROMOCAMBIOS"

    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def send_file(self, path, ctype):
        try:
            size = os.path.getsize(path)
        except OSError:
            self.send_error(404)
            return
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
                code = 206
        length = max(end - start + 1, 0)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(262144, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    # --- GET ---
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        cfg = load_config()

        if p == "/api/env":
            self.send_json({
                "ok": bool(FFMPEG and FFPROBE),
                "ffmpeg": FFMPEG,
                "config": cfg,
                "voices": len(list_voices(cfg.get("vo_dir", ""))),
                "effects": EFFECTS,
                "editores": EDITORES,
                "categorias": {k: v[0] for k, v in CATEGORIAS.items()},
                "per_technique": tpl.PER_TECHNIQUE,
            })
        elif p == "/api/templates":
            tech = (q.get("tech") or ["ARRASTRE"])[0].upper()
            animadas = [
                {"id": -100 - k, "desc": "overlay · " + os.path.basename(f), "file": f}
                for k, f in enumerate(tpl.list_overlays(cfg.get("tpl_dir"), tech))
            ]
            # Si hay animadas, la galería enseña SOLO esas: mezclarlas con las de
            # texto obligaba a bucear hasta el final de la lista para encontrar
            # la buena. Las de texto solo aparecen si no hay ninguna animada.
            if animadas:
                self.send_json(animadas)
            else:
                self.send_json([
                    {"id": i, "desc": tpl.describe(tech, i)}
                    for i in range(tpl.PER_TECHNIQUE)
                ])
        elif p == "/api/template-preview":
            tech = (q.get("tech") or ["ARRASTRE"])[0].upper()
            tid = int((q.get("id") or ["0"])[0])
            path = template_preview(tech, tid, cfg)
            if path:
                self.send_file(path, "image/jpeg")
            else:
                self.send_error(404)
        elif p == "/api/batch":
            with LOCK:
                self.send_json({"running": BATCH["running"], "items": BATCH["items"]})
        elif p == "/api/drive":
            self.send_json(drive.estado())
        elif p == "/api/numeros":
            try:
                url = (q.get("url") or [cfg.get("web_app_url", "")])[0]
                self.send_json(numeros_libres(url or cfg.get("web_app_url", "")))
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)
        elif p == "/media":
            path = (q.get("path") or [""])[0]
            if not os.path.isfile(path):
                self.send_error(404)
                return
            ext = os.path.splitext(path)[1].lower()
            ctype = ("video/mp4" if ext in (".mp4", ".m4v")
                     else "video/quicktime" if ext == ".mov"
                     else "audio/mpeg" if ext == ".mp3"
                     else "application/octet-stream")
            self.send_file(path, ctype)
        elif p in ("/", "/index.html"):
            self.send_file(os.path.join(ROOT, "index.html"), "text/html; charset=utf-8")
        elif p in ("/app.js", "/styles.css"):
            ctype = "text/javascript" if p.endswith(".js") else "text/css"
            self.send_file(os.path.join(ROOT, p.lstrip("/")), f"{ctype}; charset=utf-8")
        else:
            self.send_error(404)

    # --- POST ---
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        body = self.read_json()

        if p == "/api/pick":
            paths = pick(body.get("kind", "file"))
            self.send_json({"paths": paths,
                            "durations": {x: probe_duration(x) for x in paths}
                            if body.get("kind") != "folder" else {}})
        elif p == "/api/config":
            # Se mezcla sobre lo guardado en vez de reemplazar: la UI no manda
            # las claves que no sabe editar (ids de carpetas de Drive) y con un
            # reemplazo se perderían en el primer cambio de ⚙︎.
            cfg = load_config()
            cfg.update(body or {})
            for k in ("drive_listos", "drive_sinvoz"):
                if body.get(k):
                    cfg[k] = drive.id_de_carpeta(body[k]) or cfg[k]
            save_config(cfg)
            self.send_json({"ok": True, "config": cfg})
        elif p == "/api/drive/retry":
            # Reintento manual: la cola espera su backoff y con esto arranca ya.
            drive.reintentar_ya()
            self.send_json(drive.estado())
        elif p == "/api/batch/set":
            # Reemplaza la cola con lo marcado en la UI.
            opts = body.get("opts", {})
            items = []
            for it in body.get("items", []):
                item = new_item(it["video"], it["marker"], it["type"], opts)
                completa = it.get("duration") or probe_duration(it["video"])

                # El recorte llega en tiempos del archivo original; el marcador
                # también. Aquí se rebasa TODO al clip recortado y de aquí en
                # adelante nadie más vuelve a pensar en el recorte.
                t_in = max(float(it.get("trim_in") or 0.0), 0.0)
                t_out = float(it.get("trim_out") or 0.0) or completa
                t_out = min(max(t_out, t_in + 0.5), completa)
                item["trim_in"] = round(t_in, 3)
                item["trim_len"] = round(t_out - t_in, 3) if (t_in > 0 or t_out < completa - 0.01) else 0.0
                item["duration"] = round(t_out - t_in, 3)
                # El marcador cae dentro del recorte por construcción en la UI,
                # pero si alguien manda uno de fuera se pega al borde en vez de
                # generar un efecto en un instante que ya no existe.
                item["marker"] = min(max(float(it["marker"]) - t_in, 0.0), item["duration"])

                item["base_name"] = it.get("base_name", "")
                cat = (it.get("categoria") or "DEMOSTRATIVAS").upper()
                item["categoria"] = cat if cat in CATEGORIAS else "DEMOSTRATIVAS"
                item["template"] = int(it.get("template", -1))
                items.append(item)
            with LOCK:
                BATCH["items"] = items
            save_batch()
            self.send_json({"ok": True, "n": len(items)})
        elif p == "/api/batch/start":
            if BATCH["running"]:
                self.send_json({"error": "Ya hay un lote corriendo"}, 409)
                return
            threading.Thread(target=batch_worker, daemon=True).start()
            self.send_json({"ok": True})
        elif p == "/api/batch/cancel":
            BATCH["cancel"] = True
            self.send_json({"ok": True})
        elif p == "/api/item/update":
            """Retoques del panel de revisión; re-renderiza solo lo necesario."""
            with LOCK:
                item = next((x for x in BATCH["items"] if x["id"] == body.get("id")), None)
            if not item:
                self.send_json({"error": "No encontré ese video en el lote"}, 404)
                return
            heavy = False
            for k in ("marker", "template", "effect", "intensity"):
                if k in body and body[k] != item[k]:
                    item[k] = body[k]
                    heavy = True
            for k in ("music_gain", "vo_gain", "vo_at", "vo"):
                if k in body and body[k] != item[k]:
                    item[k] = body[k]
                    if k in ("vo_at", "vo"):
                        item["vo_locked"] = True
                        item["vo_dur"] = probe_duration(item["vo"]) if k == "vo" else item["vo_dur"]
            if body.get("apply"):
                item["state"] = "pendiente"
                threading.Thread(target=batch_worker,
                                 kwargs={"only_ids": [item["id"]], "full": heavy},
                                 daemon=True).start()
            save_batch()
            self.send_json({"ok": True, "heavy": heavy})
        elif p == "/api/register":
            try:
                register_dm(body["url"], body["nombre"], body.get("creador", ""),
                            body.get("categoria", "DEMOSTRATIVAS"))
                self.send_json({"ok": True})
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)
        elif p == "/api/reveal":
            plat.revelar(body.get("path", ""))
            self.send_json({"ok": True})
        else:
            self.send_error(404)


def main():
    plat.comprobar_python()
    if not FFMPEG or not FFPROBE:
        print(plat.aviso_sin_ffmpeg(), file=sys.stderr)
        sys.exit(1)
    port = int(os.environ.get("ROMOCAMBIOS_PORT") or os.environ.get("PORT") or "8777")
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    # Restaura el lote de la sesión anterior: las marcas no se pierden al reiniciar.
    load_batch()
    # Retoma las subidas que quedaron a medias en la sesión anterior.
    drive.iniciar()
    url = f"http://127.0.0.1:{port}/"
    print(f"ROMO CAMBIOS  →  {url}")
    if os.environ.get("ROMOCAMBIOS_OPEN", "1" if sys.stdout.isatty() else "0") == "1":
        plat.abrir_url(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrado.")


if __name__ == "__main__":
    main()
