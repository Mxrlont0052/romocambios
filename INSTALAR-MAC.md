# 🍎 Instalar ROMO CAMBIOS en Mac

**Se hace una sola vez.** Después, abrir la app es un doble clic.

- ⏱️ **Tarda:** 10 minutos (casi todo es esperar descargas)
- 💻 **Necesitas:** macOS 12 o más nuevo, internet, 1 GB libre
- 🔑 **No necesitas:** saber programar

> **Lee esto antes de empezar:** macOS va a intentar bloquearte **dos veces**.
> Es normal y aquí está exactamente qué hacer. El truco siempre es el mismo:
> **clic derecho → Abrir**, nunca doble clic.

---

# PASO 1 · Bajar la app

### 1.1 — Descarga el ZIP

# ⬇️ **[BAJAR ROMO CAMBIOS](https://github.com/Mxrlont0052/romocambios/archive/refs/heads/main.zip)**

Clic en ese botón de arriba. Se baja `romocambios-main.zip` a tus **Descargas**.

<details>
<summary>Si el link no te funciona, ábrelo así</summary>

1. Ve a la **portada del repo**: <https://github.com/Mxrlont0052/romocambios>
   (si estás leyendo esto en GitHub, clic en **`romocambios`** arriba a la izquierda)
2. Botón verde **`Code`**, arriba a la derecha
3. En el menú que se abre, hasta abajo: **`Download ZIP`**

</details>

### 1.2 — Descomprímelo

Se baja a **Descargas**. Safari lo descomprime solo; si usas Chrome, haz doble
clic al ZIP.

Te queda una carpeta llamada `romocambios-main`.

### 1.3 — Ponla en un lugar fijo

Muévela a tus **Documentos**, por ejemplo:

```
~/Documentos/romocambios-main
```

**Por qué importa:** no la dejes en Descargas (algún día la borras sin querer) ni
dentro de **iCloud Drive** (iCloud saca los archivos de tu disco para ahorrar
espacio y la app deja de encontrarlos).

---

# PASO 2 · Correr el instalador

### 2.1 — 🛑 Ábrelo con clic derecho (no doble clic)

1. Entra a la carpeta `romocambios-main`
2. Entra a la carpeta **`mac`**
3. **Clic derecho** (o `Control` + clic) sobre **`instalar-mac.command`**
4. En el menú, **`Abrir`**
5. Sale una ventana avisando que es de un desarrollador no identificado:
   dale **`Abrir`** otra vez

> **¿Por qué clic derecho y no doble clic?** Con doble clic macOS lo bloquea sin
> darte opción. Con clic derecho → Abrir aparece el botón para dejarlo pasar. Es
> el mismo archivo, solo cambia cómo lo abres.
>
> **¿Es un virus?** No. macOS desconfía de cualquier archivo bajado de internet
> que no haya pagado la firma de Apple (cuesta $99 al año). Sale igual con
> programas conocidos.

**Si aun así no te deja:** ve a  **Ajustes del Sistema** → **Privacidad y
seguridad**, baja hasta abajo y vas a ver un mensaje sobre el archivo bloqueado
con un botón **`Abrir de todos modos`**.

### 2.2 — Deja que trabaje

Se abre la **Terminal** y va contando lo que hace. Tarda unos minutos, sobre todo
en el paso 2. **No la cierres.**

Va a ir mostrando:

```
  1/3  Python
  ✓ Python 3.9.6

  2/3  ffmpeg
  ▸ Descargando ffmpeg…
  ✓ ffmpeg instalado
  ✓ decodificadores de plantillas (libvpx) presentes

  3/3  Google Drive
  ¿Conectar esta Mac con el Drive de ROMO...? (s/n):
```

Todo se guarda en una carpeta oculta de tu usuario. **No toca nada del sistema.**

> **Si tienes Mac con chip M1/M2/M3:** puede pedirte instalar **Rosetta**. Dale
> que sí. Eso sí te va a pedir tu contraseña de la Mac — es normal, es de Apple,
> no del instalador.

### 2.3 — Conectar el Google Drive

Al final te pregunta:

```
  ¿Conectar esta Mac con el Drive de ROMO...? (s/n):
```

Escribe **`s`** y Enter.

Se abre tu **navegador** solo. Ahí:

1. Entra con la **cuenta de Google de ROMO** — 🚨 **no la tuya personal**
2. Dale **`Permitir`**
3. Cuando diga *"Success!"*, cierra esa pestaña y vuelve a la Terminal

**Si no sabes la contraseña de la cuenta de ROMO:** escribe `n` y sigue. La app
funciona igual, solo que los videos no se suben solos a Drive. Pídele la
contraseña a Marlon y después vuelve a correr `instalar-mac.command`.

### 2.4 — Terminó

Cuando veas esto ya está:

```
  ════════════════════════════════════════════
    Listo. Abre la app con  «ROMO CAMBIOS.command»
  ════════════════════════════════════════════
```

Cierra la Terminal.

---

# PASO 3 · Abrir la app

**Clic derecho → `Abrir`** sobre **`ROMO CAMBIOS.command`** (en la misma carpeta
`mac`). Otra vez **`Abrir`** en el aviso.

Solo la primera vez es con clic derecho. De ahí en adelante ya puedes darle doble
clic normal.

### Se abren dos cosas

| Qué | Para qué | ¿La cierro? |
|-----|----------|-------------|
| ⬛ Una ventana de **Terminal** | Es el motor de la app | ❌ **NO.** Si la cierras se apaga todo. Déjala atrás |
| 🌐 Tu **navegador** | Aquí trabajas | Aquí es donde haces todo |

Si el navegador no se abre solo, entra tú a: **<http://127.0.0.1:8777>**

### Para cerrar la app

Primero cierra la pestaña del navegador, después la Terminal.

### 📌 Ponla en el Dock (te lo recomiendo)

Arrastra `ROMO CAMBIOS.command` a la parte **derecha** del Dock, del lado de la
Papelera. Ya la tienes ahí siempre.

---

# PASO 4 · Configurarla la primera vez

Ya con la app abierta, arriba a la derecha está el engranaje **⚙︎**. Ábrelo y
llena esto:

| Campo | Qué poner |
|-------|-----------|
| **Editor** | Tu nombre: `DANIEL`, `TIPAN` o `MARLONT` |
| **Carpeta de salida** | Dónde quieres que caigan los videos terminados |
| **Voces en off** | La carpeta donde tengas los audios de voz |
| **Plantillas de video** | ✅ **Ya viene puesta, no la toques** |

Las 46 plantillas animadas vienen dentro del ZIP y la app las encuentra sola.

> **El campo Editor importa:** es el nombre que queda registrado en la hoja del
> equipo como quien hizo cada video.

---

# 🆘 Si algo sale mal

| Lo que ves | Qué pasó | Solución |
|---|---|---|
| macOS no deja abrir nada | Gatekeeper | **Clic derecho → Abrir**, nunca doble clic (paso 2.1) |
| `no encontré ffmpeg/ffprobe` | El instalador no llegó al final | Vuelve a correr `instalar-mac.command` |
| `Address already in use` | Ya tenías la app abierta | Cierra la otra Terminal |
| `permission denied` al abrir | El archivo perdió el permiso | Abre Terminal y pega: `chmod +x "` arrastra el archivo `"` y Enter |
| El selector de archivos no aparece al darle "Cargar" | Se abrió **detrás** del navegador | `⌘` + `Tab` hasta encontrarlo |
| Los videos salen con **fondo negro** donde va el texto | El ffmpeg se bajó incompleto | Borra la carpeta `.romocambios` de tu usuario y reinstala |
| No encuentro mis clips en el selector | Están en iCloud y no en el disco | Sácalos de iCloud Drive a una carpeta normal |

### Si nada de esto sirve

Saca una **captura de la Terminal completa** (con `⌘` + `Shift` + `4`) y
mándasela a Marlon. **El texto de esa ventana es lo que dice qué pasó** — sin la
captura nadie puede adivinar.

---

# 📖 Uso diario (cuando ya está instalada)

1. Doble clic en `ROMO CAMBIOS.command` (o en el ícono del Dock)
2. Trabajas en el navegador
3. Al terminar: cierras el navegador y la Terminal

El instalador **no se vuelve a correr nunca**, salvo que quieras conectar el
Drive después.

---

# ❓ Preguntas

**¿Por qué no es una página web normal?**
Porque tiene que leer y escribir videos del disco de tu Mac, y eso un sitio web no
puede hacerlo. Se ve como una página, pero está corriendo dentro de tu máquina.

**¿Puedo usarla sin internet?**
Sí para renderizar. No para la numeración automática ni para subir a Drive.

**¿Es igual que en Windows?**
Idéntica: mismos pasos, mismos atajos, mismos videos de salida.
