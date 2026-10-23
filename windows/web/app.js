const $ = (id) => document.getElementById(id);

const S = {
  config: {},
  clips: [],      // {video, name, duration, marker, type, cat, template, trimIn, trimOut}
  idx: 0,
  view: "load",
  poll: null,
  galleryFor: null,
  numeros: null,  // numeración por categoría, traída de romocont
};

const TYPES = { 1: "CORTE", 2: "METRICA", 3: "ARRASTRE", 4: "STEMS", 5: "CLASE" };

// --------------------------------------------------------------------------- //
// utilidades
// --------------------------------------------------------------------------- //

async function api(path, body) {
  const opt = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok || data.error) throw new Error(data.error || `Error ${r.status}`);
  return data;
}

let toastTimer;
function toast(msg, bad) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.toggle("bad", !!bad);
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), bad ? 7000 : 3000);
}

const fmt = (s) => `${Math.floor(s / 60)}:${(s % 60).toFixed(2).padStart(5, "0")}`;
const media = (p) => `/media?path=${encodeURIComponent(p)}`;

// El nombre del archivo sin la carpeta. Corta por los DOS separadores porque en
// Windows las rutas llegan con `\` y partiendo solo por `/` se mostraba la ruta
// entera como nombre del clip.
const soloNombre = (p) => (p || "").split(/[\\/]/).pop();

function setView(v) {
  S.view = v;
  ["load", "mark", "render", "review"].forEach((x) =>
    $("view-" + x).classList.toggle("hidden", x !== v));
  document.querySelectorAll(".step").forEach((b) =>
    b.classList.toggle("on", b.dataset.view === v));
  if (v === "mark") showClip(S.idx);
  if (v === "render" || v === "review") startPolling();
  else stopPolling();
  if (v === "review") renderReview();
}
document.querySelectorAll(".step").forEach((b) => {
  b.onclick = () => setView(b.dataset.view);
});

// --------------------------------------------------------------------------- //
// arranque + configuración
// --------------------------------------------------------------------------- //

async function boot() {
  const env = await api("/api/env");
  S.config = env.config;
  $("envPill").textContent = env.ok
    ? `ffmpeg listo · ${env.voices} voces`
    : "sin ffmpeg";
  $("envPill").className = "pill " + (env.ok ? "ok" : "bad");
  $("cfgUrl").value = env.config.web_app_url || "";
  $("cfgVo").value = env.config.vo_dir || "";
  $("cfgOut").value = env.config.out_dir || "";
  $("cfgTpl").value = env.config.tpl_dir || "";
  $("cfgFont").value = env.config.font || "";
  $("cfgEditor").value = env.config.editor || "";
  $("cfgRegistrar").checked = env.config.registrar !== false;
  $("cfgSubirDrive").checked = env.config.subir_drive !== false;
  pedirDm();
}

$("btnSettings").onclick = () => $("settings").classList.toggle("hidden");

document.querySelectorAll("[data-pick]").forEach((b) => {
  b.onclick = async () => {
    const { paths } = await api("/api/pick", { kind: "folder" });
    if (!paths.length) return;
    ({ vo: $("cfgVo"), out: $("cfgOut"), tpl: $("cfgTpl") })[b.dataset.pick].value = paths[0];
  };
});

$("cfgSave").onclick = async () => {
  S.config = {
    ...S.config,
    web_app_url: $("cfgUrl").value.trim(),
    vo_dir: $("cfgVo").value.trim(),
    out_dir: $("cfgOut").value.trim(),
    tpl_dir: $("cfgTpl").value.trim(),
    font: $("cfgFont").value.trim(),
    editor: $("cfgEditor").value,
    registrar: $("cfgRegistrar").checked,
    subir_drive: $("cfgSubirDrive").checked,
  };
  await api("/api/config", S.config);
  await boot();
  toast("Configuración guardada");
  $("settings").classList.add("hidden");
};

// --------------------------------------------------------------------------- //
// 1 · cargar
// --------------------------------------------------------------------------- //

// --------------------------------------------------------------------------- //
// numeración: la trae romocont, no se escribe a mano
// --------------------------------------------------------------------------- //

async function pedirDm() {
  $("dmInfo").textContent = "Consultando romocont…";
  try {
    const n = await api(`/api/numeros?url=${encodeURIComponent(S.config.web_app_url || "")}`);
    S.numeros = n;
    $("dmInfo").innerHTML = Object.keys(n).map((cat) => {
      const d = n[cat];
      return `<div>${cat} · último <b>${d.ultimo_nombre || "—"}</b> → siguiente <b>${d.nombre}</b></div>`;
    }).join("");
    // Repintar el nombre previsto del clip abierto, que depende de estos números.
    if (S.view === "mark") paintCat();
  } catch (e) {
    S.numeros = null;
    $("dmInfo").innerHTML =
      `<span style="color:#ff8a8a">No se pudo leer romocont: ${e.message}</span>`;
  }
}

$("btnNextDm").onclick = pedirDm;

/**
 * Reparte los nombres del lote. Cada categoría consume su propia serie, así que
 * un lote mezclado sale numerado en paralelo: DM055, ES147, DM056…
 */
function nombresDelLote() {
  const cursor = {};
  return S.clips.map((c) => {
    const d = S.numeros && S.numeros[c.cat];
    if (!d) return "";
    cursor[c.cat] = (cursor[c.cat] ?? d.n - 1) + 1;
    return `${d.prefijo}${String(cursor[c.cat]).padStart(3, "0")}`;
  });
}

$("btnPickVideos").onclick = async () => {
  const { paths, durations } = await api("/api/pick", { kind: "file" });
  paths.forEach((p) => {
    if (S.clips.some((c) => c.video === p)) return;
    S.clips.push({
      video: p, name: soloNombre(p), duration: durations[p] || 0,
      marker: null, type: "ARRASTRE", template: -1,
      // La categoría decide el prefijo del nombre y la fila en romocont.
      cat: "DEMOSTRATIVAS",
      // Recorte en tiempos del archivo original. trimOut null = hasta el final.
      trimIn: 0, trimOut: null,
    });
  });
  renderLoadList();
};

function renderLoadList() {
  const box = $("loadList");
  box.innerHTML = "";
  S.clips.forEach((c, i) => {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `<b>${i + 1}. ${c.name}</b><span>${c.duration ? fmt(c.duration) : ""}</span>`;
    const del = document.createElement("button");
    del.className = "mini ghost";
    del.textContent = "Quitar";
    del.onclick = () => { S.clips.splice(i, 1); renderLoadList(); };
    row.appendChild(del);
    box.appendChild(row);
  });
  $("btnToMark").disabled = !S.clips.length;
}

$("btnToMark").onclick = () => { S.idx = 0; setView("mark"); };

// --------------------------------------------------------------------------- //
// 2 · marcar
// --------------------------------------------------------------------------- //

function showClip(i) {
  if (!S.clips.length) return;
  S.idx = Math.max(0, Math.min(i, S.clips.length - 1));
  const c = S.clips[S.idx];
  $("markCount").textContent = `${S.idx + 1} / ${S.clips.length}`;
  $("markName").textContent = c.name;
  const v = $("mVideo");
  if (!v.src.includes(encodeURIComponent(c.video))) v.src = media(c.video);
  v.onloadedmetadata = () => {
    c.duration = v.duration;
    $("mSeek").max = v.duration;
    if (c.marker != null) v.currentTime = c.marker;
    // Repintar aquí también: al entrar al clip la duración todavía no se conocía
    // y el recorte se enseñaba como "completo (0:00.00)".
    paintTrim();
  };
  $("mSeek").value = c.marker ?? 0;
  setType(c.type);
  paintCat();
  paintTrim();
  paintMarker();
  renderStrip();
  $("tplChosen").textContent = c.template < 0
    ? "Plantilla: aleatoria" : `Plantilla fija: #${c.template + 1}`;
}

function paintMarker() {
  const c = S.clips[S.idx];
  const el = $("mMarker");
  if (c.marker == null) {
    el.textContent = "sin marcar";
    el.className = "marker-none";
  } else if (marcadorFuera(c)) {
    // Un cambio fuera del recorte no existe en el video final: hay que avisar
    // aquí y no dejar pasar al render.
    el.textContent = "⚠ el cambio quedó fuera del recorte";
    el.className = "marker-set";
  } else {
    el.textContent = "cambio en " + fmt(c.marker);
    el.className = "marker-set";
  }
  renderStrip();
}

const marcadorFuera = (c) =>
  c.marker != null && (c.marker < c.trimIn - 0.01 || c.marker > trimFin(c) + 0.01);

const mv = $("mVideo");
mv.addEventListener("timeupdate", () => {
  $("mTime").textContent = fmt(mv.currentTime || 0);
  $("mSeek").value = mv.currentTime || 0;
});
$("mSeek").oninput = () => { mv.currentTime = +$("mSeek").value; };

$("btnMark").onclick = () => {
  S.clips[S.idx].marker = Math.round(mv.currentTime * 100) / 100;
  paintMarker();
};
$("btnClearMark").onclick = () => { S.clips[S.idx].marker = null; paintMarker(); };

// --------------------------------------------------------------------------- //
// recorte del clip
// --------------------------------------------------------------------------- //

const MIN_CLIP = 1.5;   // menos de esto no da ni para la plantilla

const trimFin = (c) => (c.trimOut ?? c.duration ?? 0);

function paintTrim() {
  const c = S.clips[S.idx];
  const fin = trimFin(c);
  const recortado = c.trimIn > 0.01 || (c.trimOut != null && c.trimOut < c.duration - 0.01);
  const el = $("trimInfo");
  el.textContent = recortado
    ? `${fmt(c.trimIn)} → ${fmt(fin)}  ·  dura ${(fin - c.trimIn).toFixed(2)} s`
    : `completo (${fmt(c.duration || 0)})`;
  el.className = "note" + (recortado ? " trim-on" : "");
}

$("btnTrimIn").onclick = () => {
  const c = S.clips[S.idx];
  const t = Math.round(mv.currentTime * 100) / 100;
  if (trimFin(c) - t < MIN_CLIP) {
    return toast(`El inicio tiene que quedar al menos ${MIN_CLIP} s antes del final`, true);
  }
  c.trimIn = t;
  paintTrim();
  paintMarker();
};

$("btnTrimOut").onclick = () => {
  const c = S.clips[S.idx];
  const t = Math.round(mv.currentTime * 100) / 100;
  if (t - c.trimIn < MIN_CLIP) {
    return toast(`El final tiene que quedar al menos ${MIN_CLIP} s después del inicio`, true);
  }
  c.trimOut = t;
  paintTrim();
  paintMarker();
};

$("btnTrimClear").onclick = () => {
  const c = S.clips[S.idx];
  c.trimIn = 0;
  c.trimOut = null;
  paintTrim();
  paintMarker();
};

function setType(t) {
  S.clips[S.idx].type = t;
  document.querySelectorAll(".type").forEach((b) => b.classList.toggle("on", b.dataset.type === t));
}
document.querySelectorAll(".type").forEach((b) => { b.onclick = () => setType(b.dataset.type); });

// --- categoría: teclas Q W E, una fila física distinta de la de la técnica ---
const CATS = { q: "DEMOSTRATIVAS", w: "ESTUDIANTES", e: "RELLENO" };

function paintCat() {
  const c = S.clips[S.idx];
  document.querySelectorAll(".cat").forEach((b) =>
    b.classList.toggle("on", b.dataset.cat === c.cat));
  // Enseñar el nombre que le va a tocar: es lo que evita numerar mal sin darse
  // cuenta, porque cada categoría corre por su propia serie.
  const nombres = nombresDelLote();
  const n = nombres[S.idx];
  $("catNombre").innerHTML = n
    ? `Este video se va a llamar <b>${n}</b>`
    : `<span style="color:#ff8a8a">Sin numeración de romocont todavía</span>`;
  renderStrip();
}

function setCat(cat) {
  S.clips[S.idx].cat = cat;
  paintCat();
}
document.querySelectorAll(".cat").forEach((b) => { b.onclick = () => setCat(b.dataset.cat); });

$("btnPrev").onclick = () => showClip(S.idx - 1);
$("btnNext").onclick = () => showClip(S.idx + 1);

function renderStrip() {
  const box = $("markStrip");
  const nombres = nombresDelLote();
  box.innerHTML = "";
  S.clips.forEach((c, i) => {
    const el = document.createElement("i");
    el.textContent = i + 1;
    el.className = (c.marker != null ? "ok " : "") + (i === S.idx ? "cur" : "");
    el.title = [nombres[i] || c.name, c.cat,
                c.marker != null ? fmt(c.marker) : "sin marcar"].join(" · ");
    el.onclick = () => showClip(i);
    box.appendChild(el);
  });
}

document.addEventListener("keydown", (e) => {
  if (S.view !== "mark" || e.target.tagName === "INPUT") return;
  if (e.code === "Space") { e.preventDefault(); mv.paused ? mv.play() : mv.pause(); }
  else if (e.key.toLowerCase() === "m") $("btnMark").click();
  else if (e.key.toLowerCase() === "i") $("btnTrimIn").click();
  else if (e.key.toLowerCase() === "o") $("btnTrimOut").click();
  else if (CATS[e.key.toLowerCase()]) setCat(CATS[e.key.toLowerCase()]);
  else if (TYPES[e.key]) setType(TYPES[e.key]);
  else if (e.key === "ArrowLeft") { e.preventDefault(); mv.currentTime -= 1 / 30; }
  else if (e.key === "ArrowRight") { e.preventDefault(); mv.currentTime += 1 / 30; }
  else if (e.key === "Enter") $("btnNext").click();
});

// galería de plantillas
$("btnGallery").onclick = () => openGallery(S.clips[S.idx].type);
$("galClose").onclick = () => $("gallery").classList.add("hidden");

async function openGallery(tech) {
  S.galleryFor = tech;
  $("galTech").textContent = tech;
  $("gallery").classList.remove("hidden");
  const list = await api(`/api/templates?tech=${tech}`);
  const grid = $("galGrid");
  grid.innerHTML = "";
  const none = document.createElement("div");
  none.className = "galitem";
  none.innerHTML = `<p style="padding:28px 9px;text-align:center">Aleatoria<br>(recomendado)</p>`;
  none.onclick = () => chooseTemplate(-1);
  grid.appendChild(none);
  list.forEach((t) => {
    const el = document.createElement("div");
    el.className = "galitem" + (S.clips[S.idx].template === t.id ? " on" : "");
    // Las animadas usan ids negativos internos; enseñarlos como "#-99" no le
    // dice nada a nadie, así que se etiquetan por su nombre de archivo.
    const etiqueta = t.id < 0
      ? `Animada · ${t.desc.replace(/^overlay · /, "")}`
      : `#${t.id + 1} · ${t.desc}`;
    // Sin loading="lazy": dentro del modal el navegador no llega a disparar la
    // carga y las miniaturas se quedan en blanco.
    el.innerHTML = `<img src="/api/template-preview?tech=${tech}&id=${t.id}" alt="">
                    <p>${etiqueta}</p>`;
    el.onclick = () => chooseTemplate(t.id);
    grid.appendChild(el);
  });
}

function chooseTemplate(id) {
  S.clips[S.idx].template = id;
  $("tplChosen").textContent = id < 0 ? "Plantilla: aleatoria" : `Plantilla fija: #${id + 1}`;
  $("gallery").classList.add("hidden");
}

// --------------------------------------------------------------------------- //
// 3 · render
// --------------------------------------------------------------------------- //

$("btnToRender").onclick = async () => {
  const sin = S.clips.filter((c) => c.marker == null);
  if (sin.length) return toast(`Faltan ${sin.length} videos por marcar`, true);
  const fuera = S.clips.filter(marcadorFuera);
  if (fuera.length) {
    return toast(
      `${fuera.length} video(s) tienen el cambio fuera del recorte: ${fuera.map((c) => c.name).join(", ")}`,
      true);
  }
  if (!S.config.out_dir) return toast("Elige la carpeta de salida en ⚙︎", true);

  // La numeración viene de romocont. Sin ella no se puede numerar el lote ni
  // registrarlo, así que se vuelve a intentar antes de rendirse.
  if (!S.numeros) {
    toast("Consultando la numeración en romocont…");
    await pedirDm();
    if (!S.numeros) return toast("Sin numeración de romocont no se puede armar el lote", true);
  }
  if (!S.config.editor && $("cfgRegistrar").checked) {
    $("settings").classList.remove("hidden");
    return toast("Elige en ⚙︎ quién está editando: es lo que se manda a romocont", true);
  }

  const nombres = nombresDelLote();
  const items = S.clips.map((c, i) => ({
    video: c.video, marker: c.marker, type: c.type, categoria: c.cat,
    duration: c.duration, template: c.template,
    trim_in: c.trimIn || 0, trim_out: c.trimOut ?? 0,
    base_name: nombres[i],
  }));
  const opts = {
    effect: $("optEffect").value,
    intensity: +$("optIntensity").value || 1,
  };
  const voPref = $("optVoPref").value;
  await api("/api/config", { ...S.config, vo_prefer: voPref === "none" ? "auto" : voPref });
  if (voPref === "none") {
    await api("/api/config", { ...S.config, vo_dir: "", vo_prefer: "auto" });
  }
  await api("/api/batch/set", { items, opts });
  setView("render");
  renderQueue([]);
};

$("btnStart").onclick = async () => {
  try { await api("/api/batch/start", {}); toast("Render en marcha"); }
  catch (e) { toast(e.message, true); }
};
$("btnCancel").onclick = () => api("/api/batch/cancel", {});

function startPolling() {
  if (S.poll) return;
  const tick = async () => {
    try {
      const b = await api("/api/batch");
      S.batch = b;
      if (S.view === "render") renderQueue(b.items);
      if (S.view === "review") renderReview(b.items);
      pintarDrive();
    } catch { /* el servidor puede estar ocupado */ }
  };
  tick();
  S.poll = setInterval(tick, 1200);
}
function stopPolling() { clearInterval(S.poll); S.poll = null; }

// Subida a Drive. Se consulta cada 4 ticks (~5 s) y no en cada uno: el estado
// pregunta por rclone y no vale la pena hacerlo 50 veces por minuto.
let _driveTick = 0;
async function pintarDrive() {
  const bar = $("driveBar");
  if (!bar) return;
  if (_driveTick++ % 4) return;
  let d;
  try { d = await api("/api/drive"); } catch { return; }
  if (!d.rclone) {
    bar.className = "note";
    bar.textContent = "⚠ Falta rclone: los videos no se están subiendo a Drive.";
    return;
  }
  if (!d.pendientes) {
    // Sin cola no hay nada que decir: la barra estorba en la vista de render.
    bar.className = "note hidden";
    bar.textContent = "";
    return;
  }
  const err = d.cola.find((t) => t.error);
  bar.className = "note";
  bar.textContent = "☁ Subiendo a Drive: " + d.pendientes + " archivo(s)" +
    (d.subiendo ? " · " + d.subiendo : "") +
    (err ? " · reintentando (" + err.error.slice(0, 80) + ")" : "") +
    " — no cierres la app hasta que termine.";
}

function renderQueue(items) {
  const box = $("renderList");
  box.innerHTML = "";
  (items || []).forEach((it) => {
    const row = document.createElement("div");
    row.className = "rrow";
    row.innerHTML = `
      <div class="top">
        <b>${it.base_name || it.name}</b>
        <span class="st ${it.state}">${it.state === "error" ? "error" : it.phase || it.state}</span>
      </div>
      <div class="bar"><i style="width:${it.progress || 0}%"></i></div>
      ${it.error ? `<p class="note" style="color:#ff8a8a">${it.error.slice(0, 200)}</p>` : ""}`;
    box.appendChild(row);
  });
}

$("btnToReview").onclick = () => setView("review");

// --------------------------------------------------------------------------- //
// 4 · revisar
// --------------------------------------------------------------------------- //

// Firma de lo que se ve en la fila: si cambia, hay que rehacerla. Sin esto, una
// fila creada mientras el video todavía renderizaba se queda con "sin render".
const sig = (it) => [it.state, it.sv, it.con_voz, it.vo_at, it.marker,
                     it.template, it.effect, it.warn, it.error,
                     it.registrado].join("|");

function renderReview(items) {
  const list = items || (S.batch && S.batch.items) || [];
  const box = $("reviewList");
  if (!box._sigs) box._sigs = {};

  // Se rehace entera solo si cambió la cantidad o el orden.
  const ids = list.map((i) => i.id).join(",");
  if (box._ids !== ids) {
    box._ids = ids;
    box._sigs = {};
    box.innerHTML = "";
    list.forEach((it) => {
      box._sigs[it.id] = sig(it);
      box.appendChild(reviewRow(it));
    });
    return;
  }
  list.forEach((it) => {
    if (box._sigs[it.id] === sig(it)) {
      const line = box.querySelector(`.rev[data-id="${CSS.escape(it.id)}"] .stateline`);
      if (line) line.textContent = it.state === "listo" ? "listo" : it.phase || it.state;
      return;
    }
    box._sigs[it.id] = sig(it);
    const old = box.querySelector(`.rev[data-id="${CSS.escape(it.id)}"]`);
    const fresh = reviewRow(it);
    if (old) old.replaceWith(fresh);
    else box.appendChild(fresh);
  });
}

// Plantillas por técnica, cacheadas: el desplegable de cada tarjeta las pide una
// sola vez por técnica en vez de una llamada por fila.
const TPL_CACHE = {};
async function plantillasDe(tech) {
  if (!TPL_CACHE[tech]) TPL_CACHE[tech] = api(`/api/templates?tech=${tech}`);
  try { return await TPL_CACHE[tech]; }
  catch (e) { delete TPL_CACHE[tech]; throw e; }
}
// Nombre limpio para el desplegable: "overlay · rmt_01.webm" → "rmt_01".
const nombrePlantilla = (t) =>
  (t.file ? t.file.split("/").pop() : (t.desc || ""))
    .replace(/^overlay · /, "")
    .replace(/\.(webm|mov|mp4|png|jpg)$/i, "") || `#${t.id}`;

function reviewRow(it) {
  const el = document.createElement("div");
  el.className = "rev";
  el.dataset.id = it.id;
  const main = it.con_voz || it.sv;

  el.innerHTML = `
    <div>
      ${main ? `<video controls playsinline preload="none" src="${media(main)}"></video>` : "<p class='note'>Sin render todavía</p>"}
      <p class="note stateline">${it.state === "listo" ? "listo" : it.phase || it.state}</p>
    </div>
    <div>
      <h3>${it.base_name || it.name} <span class="note">· ${it.categoria || ""} · ${it.type} · ${it.effect}${it.registrado ? " · registrado ✓" : ""}</span></h3>
      ${it.warn ? `<p class="warn">⚠ ${it.warn}</p>` : ""}
      ${it.error ? `<p class="err">${it.error.slice(0, 300)}</p>` : ""}
      <div class="ctrls">
        <label>Volumen de la música <span class="val" data-v="music">${it.music_gain.toFixed(1)} dB</span>
          <input type="range" data-k="music_gain" min="-12" max="6" step="0.5" value="${it.music_gain}">
        </label>
        <label>Volumen de la voz <span class="val" data-v="vo">${it.vo_gain.toFixed(1)} dB</span>
          <input type="range" data-k="vo_gain" min="-6" max="9" step="0.5" value="${it.vo_gain}">
        </label>
        <label>La voz entra en <span class="val" data-v="voat">${it.vo_at.toFixed(2)} s</span>
          <input type="range" data-k="vo_at" min="0" max="${Math.max(it.duration - it.vo_dur, 0).toFixed(2)}" step="0.05" value="${it.vo_at}">
        </label>
        <label>El cambio está en <span class="val" data-v="mk">${it.marker.toFixed(2)} s</span>
          <input type="range" data-k="marker" min="0" max="${it.duration.toFixed(2)}" step="0.05" value="${it.marker}">
        </label>
        <label class="tplpick">Plantilla
          <select data-a="tpl"><option value="${it.template}">Cargando plantillas…</option></select>
        </label>
        <div class="acts">
          <button class="mini" data-a="apply">Aplicar cambios</button>
          <button class="mini ghost" data-a="reveal">Ver en Finder</button>
        </div>
      </div>
    </div>`;

  const changes = {};
  el.querySelectorAll("input[type=range]").forEach((r) => {
    r.oninput = () => {
      const k = r.dataset.k;
      changes[k] = +r.value;
      const map = { music_gain: "music", vo_gain: "vo", vo_at: "voat", marker: "mk" };
      const out = el.querySelector(`[data-v="${map[k]}"]`);
      out.textContent = k.includes("gain") ? (+r.value).toFixed(1) + " dB" : (+r.value).toFixed(2) + " s";
    };
  });

  el.querySelector('[data-a="apply"]').onclick = async (ev) => {
    ev.target.disabled = true;
    try {
      const res = await api("/api/item/update", { id: it.id, ...changes, apply: true });
      toast(res.heavy ? "Rehaciendo el video completo…" : "Re-mezclando el audio…");
      $("reviewList").dataset.n = "";
    } catch (e) { toast(e.message, true); }
    finally { ev.target.disabled = false; }
  };
  el.querySelector('[data-a="reveal"]').onclick = () =>
    api("/api/reveal", { path: main || "" });
  const tplSel = el.querySelector('select[data-a="tpl"]');
  plantillasDe(it.type).then((list) => {
    const opts = ['<option value="-1">Aleatoria (que elija sola)</option>']
      .concat(list.map((t) => `<option value="${t.id}">${nombrePlantilla(t)}</option>`));
    tplSel.innerHTML = opts.join("");
    // Deja marcada la que tiene puesta ahora; si es una fija ya sorteada, sale
    // seleccionada sola. Si no coincide con ninguna (valor viejo), cae en Aleatoria.
    tplSel.value = String(it.template);
    if (tplSel.selectedIndex < 0) tplSel.value = "-1";
  }).catch(() => {
    tplSel.innerHTML = '<option value="-1">Aleatoria</option>';
  });
  tplSel.onchange = () => {
    changes.template = +tplSel.value;
    toast("Plantilla elegida; dale a «Aplicar cambios»");
  };
  return el;
}

boot().catch((e) => toast("No se pudo iniciar: " + e.message, true));
