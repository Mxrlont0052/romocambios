"""Plantillas de texto de ROMO CAMBIOS.

Cada técnica de mezcla tiene su repertorio de 30 plantillas. Se arman combinando
5 ejes —tipografía, paleta, animación, posición y tamaño— con pasos coprimos, así
que las 30 son únicas y entre todas recorren las 6 tipografías, las 10 paletas,
las 8 animaciones, las 6 posiciones y los 3 tamaños. El repertorio de cada técnica
sale desfasado, así que CORTE no se ve igual que ARRASTRE.

Desde el 30-07-2026 estas plantillas están RETIRADAS del repertorio: el catálogo
son las animadas de Remotion. Se quedan aquí como red de emergencia, por si la
carpeta de plantillas animadas está vacía o mal apuntada (ver `pool_plantillas`
en server.py).

También se pueden sumar plantillas de video (fondo verde o con canal alfa)
dejándolas en la carpeta de plantillas configurada; ver `list_overlays`.
"""

import os

import plataforma as plat

VERSION = 4              # sube al cambiar diseños: invalida las miniaturas cacheadas
W, H = 1080, 1920

RED = "0xFF1E1E"
WHITE = "0xFFFFFF"
YELLOW = "0xFFE500"
CYAN = "0x23E5FF"
VIOLET = "0xB14BFF"

TECHNIQUES = {
    "CORTE": ("MEZCLA DE", "CORTE"),
    "METRICA": ("MEZCLA", "MÉTRICA"),
    "ARRASTRE": ("MEZCLA DE", "ARRASTRE"),
    "STEMS": ("MEZCLA CON", "STEMS"),
    "CLASE": ("CLASE DE DJ", "GRATIS"),
}

OVERLAY_EXTS = (".mov", ".webm", ".mp4", ".png")

SUP = "/System/Library/Fonts/Supplemental/"
WIN = "C:/Windows/Fonts/"

# (nombre, ruta, ancho medio por carácter en em — medido, no estimado)
# Las dos listas tienen las mismas 6 caras porque el ancho medido va atado a la
# posición: cambiar el orden cambiaría el diseño de las plantillas ya numeradas.
# Si una fuente no está instalada, `build` cae a la del sistema.
_FONTS_MAC = [
    ("Arial Black", SUP + "Arial Black.ttf", 0.779),
    ("Impact", SUP + "Impact.ttf", 0.525),
    ("Rounded", SUP + "Arial Rounded Bold.ttf", 0.712),
    ("Phosphate", SUP + "Phosphate.ttc", 0.589),
    # Arial Narrow Bold en lugar de Futura: la cara 0 del .ttc de Futura es la
    # Medium y se ve demasiado fina para un reel.
    ("Narrow", SUP + "Arial Narrow Bold.ttf", 0.584),
    ("Avenir Cond", "/System/Library/Fonts/Avenir Next Condensed.ttc", 0.538),
]

# Equivalentes de Windows, cara por cara. Phosphate y Avenir Condensed no
# existen ahí; las reemplazan Bahnschrift y su versión condensada, que son las
# dos caras estrechas que trae Windows de fábrica.
_FONTS_WIN = [
    ("Arial Black", WIN + "ariblk.ttf", 0.779),
    ("Impact", WIN + "impact.ttf", 0.525),
    ("Segoe Black", WIN + "seguibl.ttf", 0.712),
    ("Bahnschrift", WIN + "bahnschrift.ttf", 0.589),
    ("Arial Narrow", WIN + "arialnb.ttf", 0.584),
    ("Trebuchet", WIN + "trebucbd.ttf", 0.538),
]

FONTS = _FONTS_WIN if plat.WINDOWS else _FONTS_MAC

# Paletas sacadas del perfil real de ROMO: (nombre, color línea 1, color línea 2,
# caja detrás de la línea 2, color del contorno)
PALETTES = [
    ("clásico", WHITE, RED, None, "black"),
    ("invertido", RED, WHITE, None, "black"),
    ("barra roja", WHITE, WHITE, RED, "black"),
    ("amarillo", YELLOW, WHITE, None, "black"),
    ("amarillo duro", YELLOW, YELLOW, None, "black"),
    ("cian y rojo", CYAN, RED, None, "black"),
    ("blanco y amarillo", WHITE, YELLOW, None, "black"),
    ("violeta", WHITE, VIOLET, None, "black"),
    ("panel oscuro", WHITE, RED, "black@0.5", "black"),
    ("todo blanco", WHITE, WHITE, None, "black"),
]

# Posiciones (alto de la línea 1 como fracción de la altura). Banda central: ni
# muy arriba ni muy abajo, calibrada con los reels que ya funcionan.
POSITIONS = [0.44, 0.48, 0.52, 0.56, 0.60, 0.64]

SIZES = [(104, 136), (118, 152), (132, 168)]

ANIMS = ["fade", "sube", "baja", "izquierda", "derecha", "parpadeo", "rebote", "máquina"]

PER_TECHNIQUE = 30
_OFFSET = {"CORTE": 0, "METRICA": 1, "ARRASTRE": 2, "STEMS": 3, "CLASE": 4}

DURATION = 4.0
IN_T = 0.38
OUT_T = 0.5
SAFE_W = W * 0.90
BORDER = 24
TYPE_STEP = 0.055           # velocidad de la animación "máquina"


def combo(technique, tpl_id):
    """Los 5 ejes de la plantilla `tpl_id` (0..29) de una técnica."""
    o = _OFFSET.get(technique.upper(), 0)
    i = tpl_id % PER_TECHNIQUE
    return {
        "font": FONTS[(i + o) % len(FONTS)],
        "palette": PALETTES[(i * 3 + o) % len(PALETTES)],
        "anim": ANIMS[(i * 3 + o) % len(ANIMS)],
        "pos": POSITIONS[(i * 5 + o) % len(POSITIONS)],
        "size": SIZES[(i * 2 + o) % len(SIZES)],
    }


def fit_size(word, cap, em):
    """Baja el tamaño si la palabra no cabe a lo ancho, según la tipografía."""
    if not word:
        return cap
    return max(40, int(min(cap, (SAFE_W - BORDER) / (em * len(word)))))


def text_width(word, size, em):
    return size * em * len(word)


def esc(s):
    return s.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def _fade_out():
    return f"if(lt(t,{DURATION - OUT_T}),1,({DURATION}-t)/{OUT_T})"


def _alpha(anim):
    fo = _fade_out()
    if anim == "parpadeo":
        return f"if(lt(t,0.10),1,if(lt(t,0.18),0,if(lt(t,0.28),1,if(lt(t,0.34),0,{fo}))))"
    if anim in ("sube", "baja", "izquierda", "derecha", "rebote", "máquina"):
        return f"min(min(t/0.16,1),{fo})"
    return f"min(min(t/{IN_T},1),{fo})"


def _x(anim, center_expr):
    if anim == "izquierda":
        return f"{center_expr}-300*(1-min(t/{IN_T},1))"
    if anim == "derecha":
        return f"{center_expr}+300*(1-min(t/{IN_T},1))"
    return center_expr


def _y(anim, y):
    y = int(y)
    if anim == "sube":
        return f"{y}+100*(1-min(t/{IN_T},1))"
    if anim == "baja":
        return f"{y}-100*(1-min(t/{IN_T},1))"
    if anim == "rebote":
        return f"{y}-80*exp(-6*t)*abs(sin(14*t))"
    return str(y)


def _drawtext(text, color, size, x, y, alpha, font_path, border_color, extra_enable=None):
    enable = extra_enable or f"lt(t,{DURATION})"
    return (
        f"drawtext=fontfile='{font_path}':text='{esc(text)}':fontcolor={color}:"
        f"fontsize={size}:x='{x}':y='{y}':borderw=12:bordercolor={border_color}@0.92:"
        f"shadowx=0:shadowy=6:shadowcolor=black@0.55:alpha='{alpha}':enable='{enable}'"
    )


def build(technique, tpl_id, fallback_font=""):
    """Cadena de filtros ffmpeg de la plantilla (se concatena con coma)."""
    tech = technique.upper()
    line1, line2 = TECHNIQUES.get(tech, ("MEZCLA", "DJ"))
    c = combo(tech, tpl_id)
    fname, fpath, em = c["font"]
    if not os.path.isfile(fpath) and fallback_font:
        fpath, em = fallback_font, 0.78
    _, c1, c2, box, border = c["palette"]
    anim = c["anim"]
    cap1, cap2 = c["size"]
    f1 = fit_size(line1, cap1, em)
    f2 = fit_size(line2, cap2, em)
    y1 = H * c["pos"]
    y2 = y1 + f1 * 1.02
    # La ruta va DENTRO de un filtro: hay que escaparle la `:` (y en Windows,
    # además, pasar las `\` a `/`, que ffmpeg acepta igual).
    fpath_esc = plat.ruta_filtro(fpath)
    alpha = _alpha(anim)
    parts = []

    if box:
        if box == RED:
            bw = int(min(W * 0.97, text_width(line2, f2, em) + 76))
            parts.append(
                f"drawbox=x=(iw-{bw})/2:y={int(y2 + f2 * 0.02)}:w={bw}:h={int(f2 * 1.04)}:"
                f"color={RED}@0.92:t=fill:enable='lt(t,{DURATION})'")
        else:
            # El panel se ciñe al texto más ancho en vez de cruzar toda la pantalla:
            # una banda de borde a borde se ve plana encima del video.
            top = int(y1 - f1 * 0.16)
            bw = int(min(W * 0.97, max(text_width(line1, f1, em),
                                       text_width(line2, f2, em)) + 90))
            parts.append(
                f"drawbox=x=(iw-{bw})/2:y={top}:w={bw}:h={int((y2 + f2 * 1.10) - top)}:"
                f"color={box}:t=fill:enable='lt(t,{DURATION})'")

    parts.append(_drawtext(line1, c1, f1, _x(anim, "(w-text_w)/2"), _y(anim, y1),
                           alpha, fpath_esc, border))

    if anim == "máquina":
        # Revelado letra a letra: se ancla a la izquierda del texto final para que
        # crezca como una máquina de escribir y no desde el centro.
        x0 = int((W - text_width(line2, f2, em)) / 2)
        n = len(line2)
        for k in range(1, n):
            a, b = k * TYPE_STEP, (k + 1) * TYPE_STEP
            parts.append(_drawtext(line2[:k], c2 if box != RED else WHITE, f2, x0,
                                   int(y2), "1", fpath_esc, border,
                                   extra_enable=f"between(t,{a:.3f},{b:.3f})"))
        parts.append(_drawtext(line2, c2 if box != RED else WHITE, f2, x0, int(y2),
                               _fade_out(), fpath_esc, border,
                               extra_enable=f"between(t,{n * TYPE_STEP:.3f},{DURATION})"))
    else:
        parts.append(_drawtext(line2, c2 if box != RED else WHITE, f2,
                               _x(anim, "(w-text_w)/2"), _y(anim, y2),
                               alpha, fpath_esc, border))
    return ",".join(parts)


def describe(technique, tpl_id):
    c = combo(technique.upper(), tpl_id)
    pos = c["pos"]
    zona = "alta" if pos <= 0.48 else "media" if pos <= 0.58 else "baja"
    tam = "S" if c["size"][1] <= 136 else "M" if c["size"][1] <= 152 else "L"
    return f"{c['font'][0]} · {c['palette'][0]} · {c['anim']} · {zona} {tam}"


def list_overlays(dirpath, technique):
    """Plantillas de video/imagen que Marlon deje en <dir>/<TECNICA>/."""
    if not dirpath:
        return []
    d = os.path.join(dirpath, technique.upper())
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f) for f in os.listdir(d)
        if f.lower().endswith(OVERLAY_EXTS) and not f.startswith(".")
    )
