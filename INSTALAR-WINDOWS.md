# 🪟 Instalar ROMO CAMBIOS en Windows

**Se hace una sola vez.** Después, abrir la app es un doble clic.

- ⏱️ **Tarda:** 15 minutos (casi todo es esperar descargas)
- 💻 **Necesitas:** Windows 10 u 11, internet, 1 GB libre
- 🔑 **No necesitas:** ser administrador ni saber programar

> **Lee esto antes de empezar:** Windows va a intentar bloquearte **dos veces**.
> Es normal y en este tutorial está exactamente qué botón apretar. No te asustes
> ni canceles: si cancelas, no se instala.

---

# PASO 1 · Bajar la app

### 1.1 — Descarga el ZIP

En la página del repo (esta misma), arriba a la derecha:

1. Botón verde **`Code`**
2. En el menú que se abre, hasta abajo: **`Download ZIP`**

Se baja un archivo llamado `romocambios-main.zip` a tu carpeta de **Descargas**.

### 1.2 — Extráelo (ojo con esto)

1. Abre tu carpeta de **Descargas**
2. **Clic derecho** sobre `romocambios-main.zip`
3. **`Extraer todo…`**
4. Botón **`Extraer`**

> ### ⚠️ El error más común de todos
>
> Si haces **doble clic** en el ZIP, Windows te muestra las carpetas de adentro y
> parece que ya está. **No está.** Eso es solo una vista previa y la app no
> funciona desde ahí.
>
> **Cómo saber si lo hiciste bien:** cuando termines tienes que ver una **carpeta
> amarilla** llamada `romocambios-main`, no un archivo con un cierre 🤐.

### 1.3 — Ponla en un lugar fijo

Mueve esa carpeta a la raíz de tu disco, o sea `C:\`. Que quede así:

```
C:\romocambios-main
```

**Por qué importa:** no la dejes en Descargas (algún día la borras sin querer) ni
dentro de **OneDrive** (OneDrive saca los archivos de tu PC para ahorrar espacio y
la app deja de encontrarlos).

---

# PASO 2 · Correr el instalador

### 2.1 — Ábrelo

1. Entra a la carpeta `C:\romocambios-main`
2. Entra a la carpeta **`windows`**
3. **Doble clic** en **`instalar-windows.bat`**

### 2.2 — 🛑 Aquí Windows te bloquea (primera vez)

Te va a salir una pantalla **azul** que dice *"Windows protegió su PC"*.

**Qué hacer:**

1. Clic en el texto pequeño **`Más información`**
2. Aparece abajo un botón nuevo: **`Ejecutar de todas formas`**
3. Clic ahí

> **¿Es un virus?** No. Windows desconfía de cualquier archivo bajado de internet
> que no haya pagado una firma digital (cuesta cientos de dólares al año). Ese
> mensaje sale igual con programas conocidos.

### 2.3 — Deja que trabaje

Se abre una **ventana negra** que va contando lo que hace. Va a tardar varios
minutos, sobre todo en el paso 2. **No la cierres.**

Va a ir mostrando:

```
  1/3  Python
  OK  Python 3.12.1

  2/3  ffmpeg
  Descargando ffmpeg (unos 100 MB, tarda un rato)...
  Descomprimiendo...
  OK  ffmpeg instalado
  OK  decodificadores de plantillas (libvpx) presentes

  3/3  Google Drive
  Conectar esta PC con el Drive de ROMO...? (s/n):
```

Todo se guarda en una carpeta oculta de tu usuario. **No toca nada del sistema**
y nunca te pide contraseña de administrador.

### 2.4 — Si te dice que falta Python

En el paso `1/3` puede decirte que no tienes Python. Te va a ofrecer instalarlo
solo: escribe **`s`** y Enter, y listo.

Si prefieres hacerlo a mano:

1. Entra a **<https://www.python.org/downloads/>**
2. Botón amarillo grande **`Download Python`**
3. Abre el archivo que se bajó
4. 🚨 **ANTES de darle Install:** marca la casilla de abajo que dice
   **`Add python.exe to PATH`**

   > Esta casilla es chiquita y está hasta abajo. **Si no la marcas, nada
   > funciona** y hay que desinstalar y volver a empezar. Es el segundo error
   > más común.

5. Botón **`Install Now`**
6. Cuando termine, **cierra la ventana negra** y vuelve a hacer doble clic en
   `instalar-windows.bat`

### 2.5 — Conectar el Google Drive

Al final te pregunta:

```
  Conectar esta PC con el Drive de ROMO...? (s/n):
```

Escribe **`s`** y Enter.

Se abre tu **navegador** solo. Ahí:

1. Entra con la **cuenta de Google de ROMO** — 🚨 **no la tuya personal**
2. Dale **`Permitir`** / **`Allow`**
3. Cuando diga *"Success!"*, cierra esa pestaña y vuelve a la ventana negra

**Si no sabes la contraseña de la cuenta de ROMO:** escribe `n` y sigue. La app
funciona igual, solo que los videos no se suben solos a Drive y los tendrás que
pasar a mano. Pídele la contraseña a Marlon y después vuelve a correr
`instalar-windows.bat` para conectarlo.

### 2.6 — Terminó

Cuando veas esto ya está:

```
  ============================================
    Listo. Abre la app con  ROMO CAMBIOS.bat
  ============================================
```

Cierra la ventana negra.

---

# PASO 3 · Abrir la app

**Doble clic en `ROMO CAMBIOS.bat`** (está en la misma carpeta `windows`).

### 🛑 Aquí Windows te bloquea (segunda y última vez)

Misma pantalla azul de antes: **`Más información`** → **`Ejecutar de todas
formas`**. Solo pasa esta vez, después ya no molesta.

### Se abren dos cosas

| Qué | Para qué | ¿La cierro? |
|-----|----------|-------------|
| 🖤 Una **ventana negra** | Es el motor de la app | ❌ **NO.** Si la cierras se apaga todo. Déjala atrás, minimizada |
| 🌐 Tu **navegador** | Aquí trabajas | Aquí es donde haces todo |

Si el navegador no se abre solo, entra tú a: **<http://127.0.0.1:8777>**

### Para cerrar la app

Primero cierra la pestaña del navegador, después la ventana negra.

### 📌 Ponla en el escritorio (te lo recomiendo)

Para no andar buscando la carpeta cada vez:

1. **Clic derecho** en `ROMO CAMBIOS.bat`
2. **`Mostrar más opciones`** (en Windows 11)
3. **`Enviar a`** → **`Escritorio (crear acceso directo)`**

Ya tienes el ícono en el escritorio.

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

Busca aquí lo que te apareció:

| Lo que ves | Qué pasó | Solución |
|---|---|---|
| `No encontre Python` | Falta Python, o no marcaste la casilla del PATH | Reinstala Python marcando **`Add python.exe to PATH`** (paso 2.4) |
| `no encontré ffmpeg/ffprobe` | El instalador no llegó al final | Vuelve a correr `instalar-windows.bat` |
| `Address already in use` | Ya tenías la app abierta | Busca la otra ventana negra en la barra de tareas y ciérrala |
| La ventana negra **se cierra sola al instante** | Windows bloqueó el archivo | Clic derecho en el `.bat` → **`Propiedades`** → abajo marca **`Desbloquear`** → **`Aceptar`** |
| Se abre la **Tienda de Microsoft** al instalar | Es un Python falso que trae Windows | Instala el de python.org (paso 2.4) |
| El selector de archivos no aparece al darle "Cargar" | Se abrió **detrás** del navegador | Búscalo en la barra de tareas, abajo |
| Los videos salen con **fondo negro** donde va el texto | El ffmpeg se bajó incompleto | Borra la carpeta `.romocambios` de tu usuario y reinstala |
| No encuentro mis clips en el selector | Están en OneDrive y no en la PC | Sácalos de OneDrive a una carpeta normal |

### Si nada de esto sirve

Saca una **captura de la ventana negra completa** (con `Tecla Windows` +
`Shift` + `S`) y mándasela a Marlon. **El texto de esa ventana es lo que dice qué
pasó** — sin la captura nadie puede adivinar.

---

# 📖 Uso diario (cuando ya está instalada)

1. Doble clic en `ROMO CAMBIOS.bat` (o en el acceso directo del escritorio)
2. Trabajas en el navegador
3. Al terminar: cierras el navegador y la ventana negra

El instalador **no se vuelve a correr nunca**, salvo que quieras conectar el
Drive después.

---

# ❓ Preguntas

**¿Por qué no es una página web normal?**
Porque tiene que leer y escribir videos del disco de tu PC, y eso un sitio web no
puede hacerlo. Se ve como una página, pero está corriendo dentro de tu máquina.

**¿Puedo usarla sin internet?**
Sí para renderizar. No para la numeración automática ni para subir a Drive.

**¿Es igual que en la Mac?**
Idéntica: mismos pasos, mismos atajos de teclado, mismos videos de salida. Lo
único distinto es que en Windows los videos van por defecto a `Videos` en vez de
`Películas`, y que donde la Mac usa `⌘` tú usas `Ctrl`.
