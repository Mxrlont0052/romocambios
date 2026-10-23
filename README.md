# ROMO CAMBIOS

App del equipo de ROMO DJ Academy para sacar **videos de "cambios"** (demostrativas de DJ)
**en lote**. Cargas 20 clips de cámara, marcas a mano dónde está el cambio en cada uno, y
salen **2 videos por clip**:

- `DM055.mp4` — con plantilla animada, efecto en el cambio y **voz en off**.
- `DM055 SV.mp4` — idéntico pero **sin voz** (SV).

Cada video queda registrado solo en la hoja de ROMO CONT y subido al Drive de ROMO.

> 🔄 **Se actualiza sola.** Cada vez que la abres mira si hay una versión nueva aquí en GitHub y la baja (código, plantillas, efectos y voces). No tienes que volver a descargar nada. Si la instalaste antes del 23-10-2026, bájala **una última vez** con el botón de abajo.

---

## 👉 ¿Es tu primera vez? Empieza aquí

# ⬇️ **[BAJAR ROMO CAMBIOS](https://github.com/Mxrlont0052/romocambios/archive/refs/heads/main.zip)**

Y después abre la guía de **tu** computadora y síguela de arriba a abajo. Están
escritas paso a paso, con todo lo que vas a ver en cada momento.

### 🪟 **[→ INSTALAR EN WINDOWS](INSTALAR-WINDOWS.md)**

### 🍎 **[→ INSTALAR EN MAC](INSTALAR-MAC.md)**

Se instala **una sola vez** por computadora (unos 15 minutos). Después, abrir la
app es un doble clic.

> **Aviso para que no te asustes:** durante la instalación, Windows y macOS te
> van a decir que el programa "no es seguro" o "es de un desarrollador no
> identificado". Es normal en cualquier programa que no pagó una firma digital.
> En las guías está exactamente qué botón apretar.

---

## Qué hay en este repo

```
windows/     lo que abres en Windows  →  ROMO CAMBIOS.bat
mac/         lo que abres en Mac      →  ROMO CAMBIOS.command
plantillas/  las 46 plantillas animadas (las encuentra sola)
```

Las dos carpetas tienen **el mismo código** dentro de `web/`: lo único distinto son los
lanzadores y los instaladores. Descarga el ZIP completo y usa la carpeta que te toque.

---

## Cómo se usa

1. **Cargar** — eliges todos los clips de la tanda. Aquí se fijan los parámetros del lote:
   efecto, intensidad y voz en off. La numeración se consulta sola a la hoja del equipo.
2. **Marcar** — vas video por video poniendo **tú** el marcador del cambio. No hay detección
   automática. También eliges el tipo de mezcla, la categoría y, si hace falta, recortas el clip.
3. **Renderizar** — la cola procesa los videos uno por uno con su barra de progreso.
4. **Revisar** — cada video con su preview y sliders para volumen de música, volumen de voz,
   posición de la voz, momento del cambio y plantilla. Si solo tocas audio, el re-render tarda
   ~1 segundo; si mueves el marcador o la plantilla, se rehace el video.

### Atajos del paso 2

| Tecla | Qué hace |
|-------|----------|
| `espacio` | Reproducir / pausar |
| `M` | Marcar el cambio en el segundo actual |
| `1`–`5` | Tipo de mezcla (CORTE, MÉTRICA, ARRASTRE, STEMS, CLASE) |
| `Q` `W` `E` | Categoría (DEMOSTRATIVAS, ESTUDIANTES, RELLENO) |
| `I` `O` | Recortar inicio / final del clip |
| `←` `→` | Mover un frame atrás / adelante |
| `enter` | Siguiente video |

Las dos filas de teclas están separadas a propósito: los números nunca tocan la categoría,
así apretar `3` dos veces para corregir la técnica no puede cambiarte la categoría sin que lo veas.

### Numeración

Cada categoría lleva su propia serie y los nombres van **pegados y con 3 cifras**:

| Categoría | Prefijo | Ejemplo |
|-----------|---------|---------|
| DEMOSTRATIVAS | `DM` | `DM055` |
| ESTUDIANTES | `ES` | `ES160` |
| RELLENO | `RLL` | `RLL090` |

Nunca `DM 055` ni `DM55`.

---

## Preguntas frecuentes

**¿Se puede usar desde el navegador, sin instalar nada?**
No. La app tiene que leer y escribir archivos de video del disco de tu computadora, y eso
un sitio web no lo puede hacer. Por eso corre un servidor local: se ve como una página web,
pero está corriendo en tu máquina.

**¿Por qué hay una ventana negra / Terminal abierta?**
Es el motor de la app. Si la cierras, se apaga.

**¿Los videos se suben solos?**
Sí, si conectaste el Drive en el instalador. Van en una cola aparte, así que si se corta el
internet o cierras la app, al volver a abrirla sigue donde quedó.

**¿Me va a ensuciar la hoja del equipo mientras pruebo?**
En ⚙︎ puedes apagar *Registrar en la hoja* y *Subir a Drive*.

---

## Para desarrollar

El código está en `web/` (Python de la librería estándar + HTML/JS, sin dependencias).
Lo que cambia entre sistemas está aislado en **`web/plataforma.py`**: selector de archivos,
abrir el navegador, mostrar un archivo en el Finder/Explorador y encontrar los binarios.
El resto del código no sabe en qué sistema corre.

Al tocar `web/` hay que copiarlo a las dos carpetas; en el proyecto de Marlon eso lo hace
`./sincronizar-repo.sh`.
