"use strict";

const T = {
  en: {
    photo: "Photo", dropMain: "Drop a raw file here, or click to choose one",
    dropSub: "3FR, FFF, ARW, DNG and other raws. TIFF, JPEG and PNG are read as sRGB.",
    fullRes: "Decode at full resolution (slower)",
    look: "Look", params: "Parameters", curves: "Channel curves",
    curvesHint: "Output per channel, both axes in sRGB encoding.",
    histogram: "Histogram", export: "Export", format: "Format", profile: "Colour space",
    hdr: "HDR (gain curve, BT.2100 PQ)", exportBtn: "Export full image",
    emptyTitle: "Open a photo to start",
    emptyBody: "Drop a raw file anywhere on this window. Changing the look re-renders the preview; Export renders the full image.",
    tagBase: "Base", tagLook: "Look", modeSplit: "Split", modeLook: "Look", modeBase: "Base",
    baseHint: "Base is the camera matrix only, with no look applied.",
    dropVeil: "Drop to open",
    "pl.camera": "Camera", "pl.studio": "Studio",
    "pd.camera": "In-camera colour, matched to the camera's own JPEG",
    "pd.studio": "Studio processor colour with calibrated curves",
    "na.core": "Needs the colour core (sealed build + key)",
    "scene.0044": "warm light scene",
    "st.black": "Black level", "st.wb": "White balance", "st.demosaic": "Demosaic",
    "st.matrix": "Camera matrix", "st.trim": "3×3 trim", "st.engine": "Colour engine",
    "st.curves": "Channel curves",
    "st.encode": "Encode",
    size: "Size", wb: "WB gains", black: "Black", white: "White", source: "Source",
    srcRaw: "raw (demosaiced here)", srcImg: "image, read as sRGB",
    decoding: "Decoding", rendering: "Rendering preview", exporting: "Rendering full image",
    opened: (n, s) => `Opened ${n} in ${s} s.`,
    rendered: (p, s) => `${p} look rendered in ${s} s.`,
    exported: (n, s) => `Exported ${n} in ${s} s.`,
    noCurves: "This parameter file has no channel curves.",
    failed: "Failed", serverDown: "The server is not responding. Check that python -m naturalcolor ui is still running.",
    probe: "sRGB 8-bit", keys: "Keys: 1–2 look · Y split · \\ look / base · E export",
    embedded: (p, f) => `Writes ${f} with the ${p} ICC profile embedded. The preview is always shown in sRGB.`,
    fmtJpg: "JPEG · 8-bit", fmtTif: "TIFF · 16-bit", fmtTif8: "TIFF · 8-bit",
    develop: "Capture settings", exposure: "Exposure", wbTitle: "White balance",
    temp: "Temperature", tint: "Tint", asShot: "As shot", wbPick: "Pick grey",
    tintGreen: "green", tintMagenta: "magenta",
    devHint: "Applied to the raw before the colour pipeline, as if set in the camera. Double-click a slider to reset it.",
    wbRawOnly: "White balance is set on the raw, so it needs a raw file. Exposure still applies.",
    picking: "Click a neutral grey or white area in the picture (Esc cancels).",
    picked: (k, n) => `White balance set from the picked area: ${k} K, tint ${n}.`,
    asShotWB: "As-shot WB", "st.exposure": "Exposure", shot: "as shot",
  },
  zh: {
    photo: "照片", dropMain: "把 RAW 文件拖到这里，或点击选择",
    dropSub: "支持 3FR、FFF、ARW、DNG 等 RAW；TIFF、JPEG、PNG 按 sRGB 读取。",
    fullRes: "全分辨率解码（较慢）",
    look: "观感", params: "参数", curves: "逐通道曲线",
    curvesHint: "各通道输出曲线，两轴均为 sRGB 编码。",
    histogram: "直方图", export: "导出", format: "格式", profile: "色彩空间",
    hdr: "HDR（增益曲线，BT.2100 PQ）", exportBtn: "导出全尺寸图像",
    emptyTitle: "打开一张照片开始",
    emptyBody: "把 RAW 文件拖到窗口任意位置。切换观感会重新渲染预览；导出时渲染全尺寸图像。",
    tagBase: "基础", tagLook: "观感", modeSplit: "对比", modeLook: "观感", modeBase: "基础",
    baseHint: "基础图只经过相机矩阵，未施加观感。",
    dropVeil: "松开以打开",
    "pl.camera": "相机", "pl.studio": "工作室",
    "pd.camera": "相机原生色彩，对齐机内 JPEG",
    "pd.studio": "工作室后期色彩，标定曲线",
    "na.core": "需要色彩核心（加密构建 + 密钥）",
    "scene.0044": "暖光场景",
    "st.black": "黑电平", "st.wb": "白平衡", "st.demosaic": "去马赛克",
    "st.matrix": "相机矩阵", "st.trim": "3×3 微调", "st.engine": "色彩引擎",
    "st.curves": "逐通道曲线",
    "st.encode": "输出编码",
    size: "尺寸", wb: "白平衡增益", black: "黑电平", white: "白电平", source: "来源",
    srcRaw: "RAW（本地去马赛克）", srcImg: "图像，按 sRGB 读取",
    decoding: "正在解码", rendering: "正在渲染预览", exporting: "正在渲染全尺寸图像",
    opened: (n, s) => `已打开 ${n}，用时 ${s} 秒。`,
    rendered: (p, s) => `${p}观感渲染完成，用时 ${s} 秒。`,
    exported: (n, s) => `已导出 ${n}，用时 ${s} 秒。`,
    noCurves: "该参数文件没有逐通道曲线。",
    failed: "失败", serverDown: "服务器没有响应，请确认 python -m naturalcolor ui 仍在运行。",
    probe: "sRGB 8 位", keys: "快捷键：1–2 观感 · Y 对比 · \\ 观感 / 基础 · E 导出",
    embedded: (p, f) => `导出 ${f}，内嵌 ${p} ICC 配置文件。预览始终以 sRGB 显示。`,
    fmtJpg: "JPEG · 8 位", fmtTif: "TIFF · 16 位", fmtTif8: "TIFF · 8 位",
    develop: "拍摄设置", exposure: "曝光", wbTitle: "白平衡",
    temp: "色温", tint: "色调", asShot: "原始设置", wbPick: "取灰点",
    tintGreen: "偏绿", tintMagenta: "偏品红",
    devHint: "作用在 RAW 上、色彩管线之前，等同于拍摄时在相机里设定。双击滑块可复位。",
    wbRawOnly: "白平衡作用在 RAW 数据上，只能用于 RAW 文件；曝光仍然可用。",
    picking: "点击画面中的中性灰或白色区域（Esc 取消）。",
    picked: (k, n) => `已按所选区域设定白平衡：${k} K，色调 ${n}。`,
    asShotWB: "拍摄白平衡", "st.exposure": "曝光", shot: "原始",
  },
};
const PROFILE_NAMES = { srgb: "sRGB", adobe: "Adobe RGB", p3: "Display P3", pq: "PQ" };
const ICC_NAMES = { srgb: "sRGB IEC61966-2.1", adobe: "Adobe RGB (1998)", p3: "Display P3", pq: "BT.2100 PQ" };
const STAGES = ["black", "wb", "demosaic", "matrix", "exposure", "trim", "engine", "curves", "encode"];

const $ = (id) => document.getElementById(id);
const state = {
  lang: pickLang(), options: null, session: null,
  pipeline: "camera", params: null,
  info: {}, mode: "split", split: 50, seq: 0, busyTimer: 0,
  // capture settings, applied to the raw before the look; wb null = as shot
  dev: { ev: 0, wb: null }, picking: false, devTimer: 0,
};

function pickLang() {
  try { const s = localStorage.getItem("nc.lang"); if (s === "en" || s === "zh") return s; } catch (e) {}
  return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
}
const t = (k, ...a) => { const v = T[state.lang][k] ?? T.en[k] ?? k; return typeof v === "function" ? v(...a) : v; };

function applyLang() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $("langBtn").textContent = state.lang === "zh" ? "English" : "中文";
  if (state.options) { buildLooks(); buildParams(); }
  renderMeta(); renderStages(); renderExportNote(); syncDevelop();
}

// ---- api ------------------------------------------------------------------
async function api(path, opts = {}) {
  let r;
  try { r = await fetch(path, opts); } catch (e) { throw new Error(t("serverDown")); }
  if (!r.ok) {
    let msg = `${r.status}`;
    try { msg = (await r.json()).error || msg; } catch (e) {}
    throw new Error(msg);
  }
  return r;
}
const getJSON = async (p) => (await api(p)).json();
const postJSON = async (p, body) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function status(msg, err = false) { const s = $("status"); s.textContent = msg; s.classList.toggle("err", err); }
function busy(msg) {
  clearInterval(state.busyTimer);
  $("busy").hidden = !msg;
  $("busyText").textContent = msg ? msg + "…" : "";
  if (!msg) return;
  const t0 = performance.now();
  state.busyTimer = setInterval(() => {
    $("busyText").textContent = `${msg}… ${Math.round((performance.now() - t0) / 1000)} s`;
  }, 1000);
}

// ---- look + params --------------------------------------------------------
function buildLooks() {
  const box = $("looks"); box.textContent = "";
  for (const p of state.options.pipelines) {
    const na = state.options.unavailable[p];
    const b = document.createElement("button");
    b.type = "button"; b.className = "look"; b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", String(p === state.pipeline));
    b.disabled = !!na;
    b.innerHTML = `<span class="dot"></span><span class="look-name"></span><span class="look-desc"></span>`;
    b.querySelector(".look-name").textContent = t("pl." + p);
    b.querySelector(".look-desc").textContent = na ? t("na." + na) : t("pd." + p);
    b.addEventListener("click", () => setPipeline(p));
    box.appendChild(b);
  }
}



function lookRequest() {
  const q = { id: state.session.id, pipeline: state.pipeline, params: state.params,
              exposure: state.dev.ev, wb: state.dev.wb };
  return q;
}

function paramsFor(p) { return state.options.params.filter((x) => x.pipelines.includes(p)); }

function buildParams() {
  const sel = $("paramsSel"); sel.textContent = "";
  for (const x of paramsFor(state.pipeline)) {
    const o = document.createElement("option");
    o.value = x.name;
    const scene = T[state.lang]["scene." + x.scene];
    o.textContent = scene ? `${x.name} (${scene})` : x.name;
    sel.appendChild(o);
  }
  if (state.params) sel.value = state.params;
}

async function setPipeline(p) {
  if (p === state.pipeline) return;
  state.pipeline = p;
  const names = paramsFor(p).map((x) => x.name);
  if (!names.includes(state.params)) state.params = names.find((n) => n.includes("0125")) || names[0] || null;
  buildLooks(); buildParams();
  await loadParamsInfo(); renderLook();
}

async function loadParamsInfo() {
  const n = state.params;
  if (!n) { state.info = {}; drawCurves(); renderStages(); return; }
  if (!state.info[n]) {
    try { state.info[n] = await getJSON("/api/params/" + encodeURIComponent(n)); }
    catch (e) { status(e.message, true); return; }
  }
  drawCurves(); renderStages();
}

// ---- photo ----------------------------------------------------------------
// load: () => Promise<Response> returning a session payload
async function decode(load, keepDevelop = false) {
  busy(t("decoding")); status("");
  $("exportBtn").disabled = true;
  try {
    const s = await (await load()).json();
    if (!keepDevelop) state.dev = { ev: 0, wb: null };
    setPicking(false);
    showSession(s);
    await renderLook();
  } catch (e) {
    status(`${t("failed")}: ${e.message}`, true);
  } finally { busy(""); $("exportBtn").disabled = !state.session; }
}

function openFile(file) {
  if (!file) return;
  return decode(() => api("/api/open", {
    method: "POST", body: file,
    headers: { "X-Filename": encodeURIComponent(file.name), "X-Full": $("fullRes").checked ? "1" : "0" },
  }));
}

function reopen() {
  if (!state.session) return;
  return decode(() => postJSON("/api/reopen", { id: state.session.id, full: $("fullRes").checked }), true);
}

function showSession(s) {
  state.session = s;
  $("fileLabel").textContent = s.name;
  $("fullRes").checked = s.full;
  $("imgBefore").src = s.before;
  $("imgAfter").removeAttribute("src");
  $("empty").hidden = true; $("frame").hidden = false;
  renderMeta(); renderStages(); syncDevelop();
  status(t("opened", s.name, s.decode_s));
}

function renderMeta() {
  const dl = $("meta"), s = state.session;
  dl.hidden = !s; if (!s) return;
  const m = s.meta, rows = [[t("size"), `${m.width} × ${m.height}`], [t("source"), m.raw ? t("srcRaw") : t("srcImg")]];
  if (m.raw) {
    const g = m.wb[1] || 1;
    rows.push([t("wb"), `R ${(m.wb[0] / g).toFixed(3)}  B ${(m.wb[2] / g).toFixed(3)}`]);
    if (m.as_shot) rows.push([t("asShotWB"), `${m.as_shot.temp} K, ${t("tint")} ${signed(m.as_shot.tint, 0)}`]);
    rows.push([t("black"), m.black.map((v) => Math.round(v)).join(" / ")], [t("white"), String(Math.round(m.white))]);
  }
  dl.textContent = "";
  for (const [k, v] of rows) {
    const dt = document.createElement("dt"); dt.textContent = k;
    const dd = document.createElement("dd"); dd.textContent = v;
    dl.append(dt, dd);
  }
}

// ---- render ---------------------------------------------------------------
async function renderLook() {
  if (!state.session || !state.params) return;
  const seq = ++state.seq;
  busy(t("rendering"));
  try {
    const r = await postJSON("/api/render", lookRequest());
    const d = await r.json();
    if (seq !== state.seq) return;
    const img = $("imgAfter");
    img.onload = () => drawHist();
    img.src = d.after;
    $("imgBefore").src = d.before;        // the base follows the capture settings too
    state.lookSeconds = d.look_s;
    renderStages();
    status(t("rendered", t("pl." + state.pipeline), d.look_s));
  } catch (e) {
    if (seq === state.seq) status(`${t("failed")}: ${e.message}`, true);
  } finally { if (seq === state.seq) busy(""); }
}

function renderStages() {
  const ol = $("stages"); ol.textContent = "";
  const p = state.pipeline, info = state.info[state.params] || {}, s = state.session;
  const raw = s ? s.meta.raw : true;
  const hdr = $("hdr").checked;
  const prof = exportProfile();
  const on = {
    black: raw, wb: raw, demosaic: raw, matrix: raw, exposure: true,
    trim: !!info.trim,
    engine: p === "camera" && !!(info.tone || info.chroma),
    curves: !!(info.curves && info.curves.length),
    encode: true,
  };
  const detail = {};
  if (s && raw) {
    const g = s.meta.wb[1] || 1;
    detail.black = String(Math.round(s.meta.black.reduce((a, b) => a + b, 0) / s.meta.black.length));
    const wb = state.dev.wb || s.meta.as_shot;
    detail.wb = wb ? `${Math.round(wb.temp)} K ${signed(wb.tint, 0)}${state.dev.wb ? "" : " · " + t("shot")}`
                   : `R ${(s.meta.wb[0] / g).toFixed(2)} B ${(s.meta.wb[2] / g).toFixed(2)}`;
    detail.demosaic = `${s.decode_s} s`;
  }
  if (s) detail.exposure = `${signed((s.meta.baseline_ev || 0) + state.dev.ev, 2)} EV`;
  if (on.curves) detail.curves = "R G B";
  detail.encode = (hdr ? "HDR " : "") + PROFILE_NAMES[prof];
  for (const k of STAGES) {
    const li = document.createElement("li");
    li.className = "st" + (on[k] ? "" : " off");
    li.textContent = t("st." + k);
    const d = document.createElement("span"); d.className = "t"; d.textContent = on[k] ? (detail[k] || "") : "";
    li.appendChild(d);
    ol.appendChild(li);
  }
}

function exportProfile() { return $("hdr").checked ? "pq" : $("profileSel").value; }

// Format select value -> /api/export {format, bits} and its i18n label.
const FORMATS = { jpg: ["jpg", 8, "fmtJpg"], tif: ["tif", 16, "fmtTif"], tif8: ["tif", 8, "fmtTif8"] };

function renderExportNote() {
  $("exportNote").textContent = t("embedded", ICC_NAMES[exportProfile()], t(FORMATS[$("fmtSel").value][2]));
}

// ---- capture settings -------------------------------------------------------
// Exposure and white balance act on the raw before the colour pipeline: the
// server scales the camera channels (render.develop), so the look sees them as
// part of the capture.  The temperature slider is linear in mireds.
const T_LO = 2000, T_HI = 12000;
const signed = (v, d) => (v > 0 ? "+" : v < 0 ? "\u2212" : "") + Math.abs(v).toFixed(d);
const tempToSlider = (k) => Math.round(1000 * (1e6 / T_LO - 1e6 / k) / (1e6 / T_LO - 1e6 / T_HI));
const sliderToTemp = (v) => 1e6 / (1e6 / T_LO - (v / 1000) * (1e6 / T_LO - 1e6 / T_HI));

function syncDevelop() {
  const s = state.session, shot = s && s.meta.as_shot, wb = state.dev.wb || shot;
  const canWB = !!shot;
  $("ev").value = state.dev.ev;
  $("evOut").textContent = `${signed(state.dev.ev, 2)} EV`;
  for (const id of ["temp", "tint", "wbShot", "wbPick"]) $(id).disabled = !canWB;
  $("ev").disabled = !s;
  $("devHint").textContent = s && !canWB ? t("wbRawOnly") : t("devHint");
  if (wb) {
    $("temp").value = tempToSlider(wb.temp); $("tint").value = Math.round(wb.tint);
    $("tempOut").textContent = `${Math.round(wb.temp)} K` + (state.dev.wb ? "" : ` · ${t("shot")}`);
    $("tintOut").textContent = signed(wb.tint, 0);
  } else { $("tempOut").textContent = "–"; $("tintOut").textContent = "–"; }
  $("wbShot").setAttribute("aria-pressed", String(canWB && !state.dev.wb));
}

// re-render shortly after the last slider movement; renderLook drops stale replies
function developChanged() {
  syncDevelop(); renderStages();
  clearTimeout(state.devTimer);
  state.devTimer = setTimeout(renderLook, 140);
}

function setWB(temp, tint) {
  state.dev.wb = { temp: Math.min(Math.max(temp, 1700), 25000), tint: Math.min(Math.max(tint, -150), 150) };
}

function setPicking(on) {
  state.picking = on && !!(state.session && state.session.meta.as_shot);
  $("wbPick").setAttribute("aria-pressed", String(state.picking));
  $("frame").classList.toggle("picking", state.picking);
  if (state.picking) status(t("picking"));
}

async function pickAt(e) {
  const r = $("frame").getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
  setPicking(false);
  if (x < 0 || x >= 1 || y < 0 || y >= 1) return;
  try {
    const d = await (await postJSON("/api/wb/pick", { id: state.session.id, x, y })).json();
    setWB(d.temp, d.tint);
    developChanged();
    status(t("picked", d.temp, signed(d.tint, 0)));
  } catch (err) { status(`${t("failed")}: ${err.message}`, true); }
}

function initDevelop() {
  $("ev").addEventListener("input", (e) => { state.dev.ev = Number(e.target.value); developChanged(); });
  $("temp").addEventListener("input", (e) => {
    setWB(sliderToTemp(Number(e.target.value)), Number($("tint").value)); developChanged();
  });
  $("tint").addEventListener("input", (e) => {
    setWB(sliderToTemp(Number($("temp").value)), Number(e.target.value)); developChanged();
  });
  $("ev").addEventListener("dblclick", () => { state.dev.ev = 0; developChanged(); });
  for (const id of ["temp", "tint"]) $(id).addEventListener("dblclick", () => { state.dev.wb = null; developChanged(); });
  $("wbShot").addEventListener("click", () => { state.dev.wb = null; developChanged(); });
  $("wbPick").addEventListener("click", () => setPicking(!state.picking));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && state.picking) { setPicking(false); status(""); } });
}

// ---- plots ----------------------------------------------------------------
const oetf = (v) => { v = Math.min(Math.max(v, 0), 1); return v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(v, 1 / 2.4) - 0.055; };

function drawCurves() {
  const svg = $("curves"), info = state.info[state.params];
  const NS = "http://www.w3.org/2000/svg";
  svg.textContent = "";
  const add = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); svg.appendChild(e); return e; };
  let grid = "";
  for (let i = 1; i < 4; i++) { const v = i * 50; grid += `M${v} 0V200M0 ${v}H200`; }
  add("path", { d: grid, class: "grid" });
  add("path", { d: "M0 200L200 0", class: "diag" });
  const path = (c) => c.x.map((x, i) => `${i ? "L" : "M"}${(oetf(x) * 200).toFixed(2)} ${(200 - oetf(c.y[i]) * 200).toFixed(2)}`).join("");
  if (info && info.tone) add("path", { d: path(info.tone), class: "c y" });
  (info && info.curves || []).forEach((c, i) => add("path", { d: path(c), class: "c " + "rgb"[i] }));

  const trim = $("trim"); trim.textContent = "";
  if (info && info.trim) {
    const cell = (txt, cls) => { const d = document.createElement("span"); d.className = cls; d.textContent = txt; trim.appendChild(d); };
    cell("", "h"); ["R", "G", "B"].forEach((c, i) => cell(c, "h v " + "rgb"[i]));
    info.trim.forEach((row, i) => { cell("RGB"[i], "h " + "rgb"[i]); row.forEach((v) => cell(v.toFixed(3), "v")); });
  }
}

// Decoded 8-bit pixels of a preview image at its natural size, dropped on each load.
const pixCache = new WeakMap();
function pixels(img) {
  if (!img.complete || !img.naturalWidth) return null;
  const hit = pixCache.get(img);
  if (hit) return hit;
  const w = img.naturalWidth, h = img.naturalHeight;
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  const entry = { w, h, data: ctx.getImageData(0, 0, w, h).data };
  pixCache.set(img, entry);
  return entry;
}

function drawHist() {
  const cv = $("hist"), ctx = cv.getContext("2d");
  const pix = pixels(state.mode === "before" ? $("imgBefore") : $("imgAfter"));
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (!pix) return;
  const px = pix.data, stride = 4 * Math.max(1, Math.floor(pix.w * pix.h / 250000));
  const N = 128, bins = [new Float32Array(N), new Float32Array(N), new Float32Array(N)];
  for (let i = 0; i < px.length; i += stride) for (let c = 0; c < 3; c++) bins[c][px[i + c] >> 1]++;
  let peak = 1;
  for (const b of bins) for (let i = 1; i < N - 1; i++) peak = Math.max(peak, b[i]);
  const css = getComputedStyle(document.documentElement);
  const cols = ["--ch-r", "--ch-g", "--ch-b"].map((v) => css.getPropertyValue(v).trim());
  ctx.globalCompositeOperation = "screen";
  bins.forEach((b, c) => {
    ctx.beginPath(); ctx.moveTo(0, cv.height);
    for (let i = 0; i < N; i++) ctx.lineTo((i + 0.5) * cv.width / N, cv.height - Math.min(1, Math.sqrt(b[i] / peak)) * (cv.height - 4));
    ctx.lineTo(cv.width, cv.height); ctx.closePath();
    ctx.fillStyle = cols[c]; ctx.globalAlpha = 0.75; ctx.fill();
  });
  ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
}

// ---- probe ----------------------------------------------------------------
// Reads the 8-bit sRGB preview under the pointer from both renders.
function probeAt(e) {
  const r = $("frame").getBoundingClientRect();
  const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
  if (fx < 0 || fx >= 1 || fy < 0 || fy >= 1) return hideProbe();
  $("probe").hidden = false;
  [["before", $("imgBefore")], ["after", $("imgAfter")]].forEach(([k, img]) => {
    const pix = pixels(img), row = $("probe-" + k);
    if (!pix) { row.hidden = true; return; }
    row.hidden = false;
    const i = 4 * (Math.floor(fy * pix.h) * pix.w + Math.floor(fx * pix.w));
    const [R, G, B] = [pix.data[i], pix.data[i + 1], pix.data[i + 2]];
    row.querySelector(".sw").style.background = `rgb(${R},${G},${B})`;
    row.querySelector(".pv").textContent = [R, G, B].map((v) => String(v).padStart(3, "\u2007")).join(" ");
  });
}
function hideProbe() { $("probe").hidden = true; }

// ---- compare --------------------------------------------------------------
function setSplit(v) {
  state.split = Math.min(100, Math.max(0, v));
  $("frame").style.setProperty("--split", state.split + "%");
  $("split").setAttribute("aria-valuenow", String(Math.round(state.split)));
}
function setMode(m) {
  state.mode = m; $("frame").dataset.mode = m;
  document.querySelectorAll("#modeSeg button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.mode === m)));
  drawHist();
}
function initCompare() {
  const frame = $("frame"), handle = $("split");
  let drag = false;
  const at = (e) => { const r = frame.getBoundingClientRect(); setSplit(((e.clientX - r.left) / r.width) * 100); };
  frame.addEventListener("pointerdown", (e) => {
    if (state.picking) { e.preventDefault(); pickAt(e); return; }
    if (state.mode !== "split") return;
    drag = true; frame.setPointerCapture(e.pointerId); at(e);
  });
  frame.addEventListener("pointermove", (e) => { if (drag) at(e); probeAt(e); });
  frame.addEventListener("pointerleave", hideProbe);
  frame.addEventListener("pointerup", () => { drag = false; });
  frame.addEventListener("pointercancel", () => { drag = false; });
  handle.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 10 : 2;
    if (e.key === "ArrowLeft") { setSplit(state.split - step); e.preventDefault(); }
    if (e.key === "ArrowRight") { setSplit(state.split + step); e.preventDefault(); }
    if (e.key === "Home") { setSplit(0); e.preventDefault(); }
    if (e.key === "End") { setSplit(100); e.preventDefault(); }
  });
  document.querySelectorAll("#modeSeg button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  setSplit(50); setMode("split");
}

// ---- export ---------------------------------------------------------------
// In the desktop app (pywebview) the file goes through the native save dialog
// and the server writes it to that path; in a browser it is a download.
const desktop = () => !!(window.pywebview && window.pywebview.api && window.pywebview.api.save_path);

async function exportToPath() {
  const hdr = $("hdr").checked;
  const [format, bits] = FORMATS[$("fmtSel").value];
  const stem = state.session.name.replace(/\.[^.]*$/, "");
  const dest = await window.pywebview.api.save_path(`${stem}_${state.pipeline}_${exportProfile()}.${format}`);
  if (!dest) return;                                 // dialog cancelled
  busy(t("exporting"));
  const token = await window.pywebview.api.token();
  const r = await api("/api/export", {
    method: "POST", headers: { "Content-Type": "application/json", "X-App-Token": token },
    body: JSON.stringify({ ...lookRequest(), profile: exportProfile(), hdr, format, bits, dest }),
  });
  const d = await r.json();
  status(t("exported", d.name, d.seconds));
}

async function exportImage() {
  if (!state.session) return;
  const btn = $("exportBtn"); btn.disabled = true;
  if (desktop()) {
    try { await exportToPath(); }
    catch (e) { status(`${t("failed")}: ${e.message}`, true); }
    finally { busy(""); btn.disabled = !state.session; }
    return;
  }
  busy(t("exporting"));
  try {
    const hdr = $("hdr").checked;
    const [format, bits] = FORMATS[$("fmtSel").value];
    const r = await postJSON("/api/export", {
      ...lookRequest(), profile: exportProfile(), hdr, format, bits,
    });
    const blob = await r.blob();
    const name = (/filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "") || [])[1] || "export";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    status(t("exported", name, r.headers.get("X-Render-Seconds") || "?"));
  } catch (e) {
    status(`${t("failed")}: ${e.message}`, true);
  } finally { busy(""); btn.disabled = !state.session; }
}

// ---- keys -----------------------------------------------------------------
function initKeys() {
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
    if (e.target.closest("select, input, textarea, [role=slider]")) return;
    const pls = state.options ? state.options.pipelines : [];
    const n = Number(e.key);
    if (n >= 1 && n <= pls.length) {
      if (!state.options.unavailable[pls[n - 1]]) setPipeline(pls[n - 1]);
    } else if (e.key === "\\") {
      setMode(state.mode === "before" ? "after" : "before");
    } else if (e.key === "y" || e.key === "Y") {
      setMode("split");
    } else if ((e.key === "e" || e.key === "E") && !$("exportBtn").disabled) {
      exportImage();
    } else return;
    e.preventDefault();
  });
}

// ---- wiring ---------------------------------------------------------------
function initDrop() {
  const drop = $("drop"), input = $("fileInput"), veil = $("dropveil");
  input.addEventListener("change", () => { openFile(input.files[0]); input.value = ""; });
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  let depth = 0;
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
  window.addEventListener("dragenter", (e) => { if (!hasFiles(e)) return; depth++; veil.hidden = false; drop.classList.add("over"); });
  window.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; veil.hidden = true; drop.classList.remove("over"); } });
  window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault(); depth = 0; veil.hidden = true; drop.classList.remove("over");
    openFile(e.dataTransfer.files[0]);
  });
}

async function init() {
  initDrop(); initCompare(); initKeys(); initDevelop();
  // registered before renderLook sets img.onload, so the cache clears before drawHist reads it
  ["imgBefore", "imgAfter"].forEach((id) => $(id).addEventListener("load", (e) => pixCache.delete(e.target)));
  $("langBtn").addEventListener("click", () => {
    state.lang = state.lang === "zh" ? "en" : "zh";
    try { localStorage.setItem("nc.lang", state.lang); } catch (e) {}
    applyLang();
  });
  $("paramsSel").addEventListener("change", async (e) => { state.params = e.target.value; await loadParamsInfo(); renderLook(); });
  $("fullRes").addEventListener("change", reopen);
  const exportChanged = () => { $("profileSel").disabled = $("hdr").checked; renderStages(); renderExportNote(); };
  ["hdr", "profileSel", "fmtSel"].forEach((id) => $(id).addEventListener("change", exportChanged));
  $("exportBtn").addEventListener("click", exportImage);
  applyLang();
  try {
    state.options = await getJSON("/api/options");
    state.params = paramsFor(state.pipeline).map((x) => x.name).find((n) => n.includes("0125")) || null;
    buildLooks(); buildParams();
    await loadParamsInfo();
    if (state.options.initial) await decode(() => api("/api/session/" + state.options.initial));
  } catch (e) { status(e.message, true); }
}
init();
