import { store } from "../models/state.js";
import { api, listen } from "../models/api.js";
import { clamp, fileFormat } from "../models/utils.js";
import { applyHistoryFlags, brushToStroke, freezeRadius, fromEditState, normRect, uiRadius } from "../models/params.js";
import { emit, on } from "./bus.js";
import { mountShell } from "../views/shell.js";
import { mountCanvas } from "../views/canvas.js";
import { mountPanel } from "../views/panel.js";
import { bindShortcuts } from "./shortcuts.js";
import { bindRostro } from "./modes/rostro.js";
import { bindCuerpo } from "./modes/cuerpo.js";
import { bindRetoque } from "./modes/retoque.js";
import { bindFoto } from "./modes/foto.js";
import { loadCatalog } from "../models/catalog.js";
import { muscleRadius } from "../models/params.js";

const app = document.getElementById("app");
const fileInput = document.getElementById("file-open");

const shell = mountShell(app);
const canvas = mountCanvas(app);
const panel = mountPanel(app);

function sync() {
  const state = store.get();
  shell.sync(state);
  canvas.sync(state);
  panel.sync(state);
}

store.subscribe(sync);

function engineDown(showToast) {
  store.patch({
    engine: "down",
    toast: showToast ? "El motor local no responde" : store.get().toast,
  });
}

function isSuperseded(err) {
  const raw = typeof err === "string" ? err : JSON.stringify(err?.code || err?.message || err || "");
  return raw.includes("Superseded") || raw.includes("superado");
}

function isCancel(err) {
  return err?.code === "Invalid" && /cancelad/i.test(String(err?.message || ""));
}

function handleError(err, fallback = "No se pudo completar la acción") {
  if (isSuperseded(err) || isCancel(err)) return;
  if (err?.code === "EngineDown") {
    engineDown(true);
    return;
  }
  const packed = err?.message;
  const engineCode = Array.isArray(packed) ? packed[0] : null;
  const text = Array.isArray(packed) ? String(packed[1] || "") : String(packed || "");
  if (engineCode === "BAD_PARAM" || text.includes("BAD_PARAM")) {
    console.warn("BAD_PARAM", packed);
    store.patch({ engine: "ok", toast: "Algún valor quedó fuera de rango" });
    return;
  }
  const noFace = engineCode === "NO_FACE" || text.includes("NO_FACE");
  const noFront = engineCode === "NO_FRONTAL_BODY" || text.includes("NO_FRONTAL_BODY");
  const muscleMsg = noFront ? "necesito una foto frontal con el torso visible" : "";
  store.patch({
    engine: "ok",
    panelAlert: muscleMsg,
    toast: noFace ? "No se detectó cara en esta imagen" : (muscleMsg || text || fallback),
  });
}

function sendParams(commit, label = "Ajuste", opts = {}) {
  const state = store.get();
  if (!state.hasImage) return;
  if (state.engine === "down") return;
  store.patch({ engine: "processing" });
  const done = (res) => {
    if (res?.blob) applyPreviewBlob(res.blob);
    if (res?.history) applyHistoryFlags(store, res.history);
    store.patch({ engine: "ok", toast: "", panelAlert: "" });
  };
  const fail = (err) => handleError(err, "No se pudo aplicar el ajuste");
  if (commit) {
    api.setParamsDebounced.cancel();
    api.setParamsDebounced60.cancel();
    api.setParams(state, { interactive: false, commit: true, label }).then(done).catch(fail);
  } else if (opts.ms === 60) {
    api.setParamsDebounced.cancel();
    api.setParamsDebounced60(state, done, fail);
  } else {
    api.setParamsDebounced60.cancel();
    api.setParamsDebounced(state, done, fail);
  }
}

function applyPreviewBlob(blob, asOriginal = false) {
  const url = URL.createObjectURL(blob);
  const prev = store.get().previewUrl;
  const patch = { previewUrl: url, imageUrl: url };
  if (asOriginal) {
    const oldOrig = store.get().originalUrl;
    patch.originalUrl = URL.createObjectURL(blob);
    if (oldOrig && oldOrig.startsWith("blob:") && oldOrig !== prev) URL.revokeObjectURL(oldOrig);
  }
  store.patch(patch);
  if (prev && prev.startsWith("blob:") && prev !== store.get().originalUrl) URL.revokeObjectURL(prev);
}

function facesFromInfo(info) {
  const list = Array.isArray(info?.faces) ? info.faces : [];
  return list.map((face, i) => {
    const b = face.bbox || [];
    if (b.length === 4) {
      return { id: i + 1, x: b[0], y: b[1], w: Math.max(0.02, b[2] - b[0]), h: Math.max(0.02, b[3] - b[1]) };
    }
    return { id: i + 1, x: 0.31, y: 0.10, w: 0.38, h: 0.46 };
  });
}

async function afterOpen(info) {
  applyDocInfo(info);
  try {
    store.patch({ engine: "processing" });
    const preview = await api.preview();
    if (preview?.blob) applyPreviewBlob(preview.blob, true);
    store.patch({ engine: "ok", toast: "" });
  } catch (err) {
    handleError(err, "No se pudo generar la vista previa");
  }
}

async function applyHistory(info) {
  if (!info) return;
  if (info.state) fromEditState(store, info.state);
  applyHistoryFlags(store, info);
  store.patch({ dirty: true });
  try {
    const preview = await api.preview();
    if (preview?.blob) applyPreviewBlob(preview.blob);
    store.patch({ engine: "ok" });
  } catch (err) {
    handleError(err, "No se pudo generar la vista previa");
  }
}

bindRostro(store, sendParams);
bindCuerpo(store, sendParams);
bindRetoque(store, sendParams);
bindFoto(store, sendParams);
bindShortcuts(store);

on("open", async () => {
  if (api.isTauri()) {
    try {
      await api.openDialog();
    } catch (err) {
      handleError(err, "No se pudo abrir el archivo");
    }
    return;
  }
  fileInput.click();
});
on("open-file", ({ file }) => openFile(file));
on("open-recent", async ({ path }) => {
  if (!api.isTauri() || !path) return;
  try {
    await api.openPath(path);
  } catch (err) {
    handleError(err, "No se pudo abrir el archivo");
  }
});
on("recents-changed", () => {
  api.recents().then((items) => store.patch({ recents: items || [] })).catch(() => {});
});
fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (file) openFile(file);
  fileInput.value = "";
});

on("mode", ({ mode }) => {
  const s = store.get();
  if (!s.hasImage && mode !== "ajustes") return;
  const brush = (mode === "cuerpo" && s.cuerpo.tool === "adelgazar" && s.cuerpo.sub === "pincel")
    || (mode === "cuerpo" && s.cuerpo.tool === "congelar" && s.cuerpo.freeze?.mode !== "rect")
    || (mode === "cuerpo" && s.cuerpo.tool === "musculo")
    || (mode === "retoque" && s.retoque.tool === "pincel");
  store.patch({ mode, cursor: brush ? "brush" : "default" });
});

on("view", ({ view }) => store.patch({ view }));
on("split", ({ value }) => store.patch({ split: clamp(value, 2, 98) }));
on("zoom", ({ delta }) => {
  const s = store.get();
  if (!s.hasImage) return;
  store.patch({ zoom: clamp(s.zoom + delta, 25, 400) });
});
on("undo", async () => {
  if (api.isTauri()) {
    try { await api.undo(); } catch { /* superseded */ }
    return;
  }
  store.undo();
});
on("redo", async () => {
  if (api.isTauri()) {
    try { await api.redo(); } catch { /* superseded */ }
    return;
  }
  store.redo();
});
on("reset-mode", () => {
  store.resetMode();
  sendParams(true, "Restablecer modo");
});
on("ajuste", ({ key, value }) => {
  store.get().ajustes[key] = value;
  store.emit();
});
on("retry-engine", () => {
  if (api.isTauri()) api.restart().then(() => ping(true)).catch(() => engineDown(true));
  else ping(true);
});
on("params-flush", () => sendParams(true));
on("restore-autosave", async () => {
  const id = store.get().pendingAutosave;
  if (!id) return;
  try {
    const info = await api.restoreAutosave(id);
    store.patch({ pendingAutosave: null, toast: "" });
    if (info) await afterOpen(info);
  } catch (err) {
    handleError(err, "No se pudo recuperar la edición");
  }
});
on("discard-autosave", async () => {
  const id = store.get().pendingAutosave;
  if (id) await api.discardAutosave(id).catch(() => {});
  store.patch({ pendingAutosave: null, toast: "" });
});
on("secondary", () => {
  const s = store.get();
  if (s.mode === "rostro") ping(true);
  if (s.mode === "cuerpo") {
    store.pushHistory();
    const tool = s.cuerpo.tool;
    if (tool === "congelar") {
      store.patchMode("cuerpo", {
        frozen: false, freezeStrokes: [], freezeRects: [], draftFreeze: null, draftRect: null,
        freeze: { ...s.cuerpo.freeze, invert: false },
      });
      sendParams(true, "Limpiar congelado");
    } else if (tool === "adelgazar" && s.cuerpo.sub === "manipulador") {
      store.patchMode("cuerpo", { manipStack: [], manipulator: { ...s.cuerpo.manipulator, amountW: 0, amountH: 0, dir: "" } });
      sendParams(true, "Resetear manipulador");
    } else if (tool === "brazo") {
      const arm = s.cuerpo.arm || {};
      store.patchMode("cuerpo", { arm: { ...arm, strokes: [], values: { ...(arm.values || {}), manual: 0 } } });
      sendParams(true, "Borrar trazos de brazo");
    } else if (tool === "altura") {
      store.patchMode("cuerpo", { heightLines: [0.48, 0.92] });
      sendParams(true, "Restablecer líneas");
    } else if (tool === "musculo") {
      store.patchMode("cuerpo", { muscle: { ...s.cuerpo.muscle, strokes: [], draft: null } });
      sendParams(true, "Limpiar máscara");
    } else {
      store.patchMode("cuerpo", { liquify: [], draftStroke: null });
      sendParams(true, "Borrar trazos");
    }
  }
  if (s.mode === "foto") {
    store.pushHistory();
    store.setParam("foto", "rotate", 0);
    sendParams(true, "Rotación");
  }
});

on("export", async () => {
  const s = store.get();
  if (!s.hasImage) return;
  try {
    if (api.isTauri()) {
      const res = await api.exportImage(s.format.toLowerCase() === "png" ? "png" : "jpg");
      if (res && res.path) {
        store.patch({ dirty: false, toast: `Guardado en ${res.path}` });
        return;
      }
      return;
    }
    if (s.engine === "ok" || s.engine === "processing") {
      const res = await api.exportImage(s.format.toLowerCase() === "png" ? "png" : "jpg");
      if (res && res.blob) {
        download(await res.blob(), exportName(s));
        store.patch({ dirty: false });
        return;
      }
    }
  } catch {
    /* fallback local solo fuera de Tauri */
  }
  if (!api.isTauri()) {
    downloadUrl(s.previewUrl, exportName(s));
    store.patch({ dirty: false });
  }
});

let panStart = null;
let paintKind = null;
let rectAnchor = null;

// Esquinas de los rectángulos de congelado: arrastrarlas redimensiona (ancla = esquina opuesta).
function rectHandleHit(event, rects) {
  const box = canvas.imageBox();
  const rect = app.querySelector(".canvas").getBoundingClientRect();
  const px = event.clientX - rect.left;
  const py = event.clientY - rect.top;
  for (let i = rects.length - 1; i >= 0; i -= 1) {
    const r = rects[i];
    const xs = [r.x, r.x + r.w];
    const ys = [r.y, r.y + r.h];
    for (let cx = 0; cx < 2; cx += 1) {
      for (let cy = 0; cy < 2; cy += 1) {
        const hx = box.x + xs[cx] * box.w;
        const hy = box.y + ys[cy] * box.h;
        if (Math.hypot(px - hx, py - hy) <= 12) {
          return { index: i, anchor: [xs[1 - cx], ys[1 - cy]] };
        }
      }
    }
  }
  return null;
}

function imagePoint(event) {
  const box = canvas.imageBox();
  const rect = event.currentTarget?.getBoundingClientRect?.()
    || app.querySelector(".canvas").getBoundingClientRect();
  const x = clamp((event.clientX - rect.left - box.x) / box.w, 0, 1);
  const y = clamp((event.clientY - rect.top - box.y) / box.h, 0, 1);
  return [x, y];
}

on("canvas-down", ({ event }) => {
  const s = store.get();
  if (!s.hasImage) return;
  if (s.spaceDown) {
    panStart = { x: event.clientX, y: event.clientY, panX: s.panX, panY: s.panY };
    store.patch({ panning: true });
    return;
  }
  const pt = imagePoint(event);
  if (s.mode === "cuerpo" && s.cuerpo.tool === "adelgazar" && s.cuerpo.sub === "pincel") {
    paintKind = "liquify";
    store.patchMode("cuerpo", { draftStroke: { pts: [pt] } });
    return;
  }
  if (s.mode === "cuerpo" && s.cuerpo.tool === "musculo") {
    const m = s.cuerpo.muscle || {};
    const erase = m.op === "erase" || Boolean(event.altKey);
    paintKind = "muscle";
    store.pushHistory();
    store.patchMode("cuerpo", { muscle: { ...m, draft: { pts: [pt], erase } } });
    return;
  }
  if (s.mode === "cuerpo" && s.cuerpo.tool === "congelar") {
    const fz = s.cuerpo.freeze || {};
    // Alt (o el modo "Borrar") resta de la máscara en vez de sumar.
    const erase = fz.op === "erase" || Boolean(event.altKey);
    store.pushHistory();
    if (fz.mode === "rect") {
      const hit = rectHandleHit(event, s.cuerpo.freezeRects || []);
      if (hit) {
        paintKind = "freeze-resize";
        rectAnchor = hit.anchor;
        const rects = [...s.cuerpo.freezeRects];
        const [old] = rects.splice(hit.index, 1);
        store.patchMode("cuerpo", { freezeRects: rects, draftRect: { ...old }, frozen: true });
        return;
      }
      paintKind = "freeze-rect";
      rectAnchor = pt;
      store.patchMode("cuerpo", { frozen: true, draftRect: { ...normRect(pt, pt), erase } });
      return;
    }
    paintKind = "freeze";
    store.patchMode("cuerpo", { frozen: true, draftFreeze: { pts: [pt], erase } });
    return;
  }
  if (s.mode === "retoque" && s.retoque.tool === "pincel") {
    paintKind = "retouch";
    store.patchMode("retoque", { draftStroke: { pts: [pt] } });
    return;
  }
  if (s.mode === "foto" && s.foto.tool === "recortar") {
    paintKind = "crop";
    store.patchMode("foto", { cropStart: pt, crop: [pt[0], pt[1], pt[0], pt[1]] });
  }
});
on("canvas-move", ({ x, y, event }) => {
  const s = store.get();
  canvas.moveBrush(x, y, s);
  if (s.panning && panStart) {
    store.patch({
      panX: panStart.panX + (event.clientX - panStart.x),
      panY: panStart.panY + (event.clientY - panStart.y),
    });
    return;
  }
  if (!paintKind) return;
  const pt = imagePoint(event);
  if (paintKind === "liquify" && s.cuerpo.draftStroke) {
    s.cuerpo.draftStroke.pts.push(pt);
    store.emit();
    sendParams(false);
  } else if ((paintKind === "freeze-rect" || paintKind === "freeze-resize") && s.cuerpo.draftRect && rectAnchor) {
    store.patchMode("cuerpo", { draftRect: { ...normRect(rectAnchor, pt), erase: s.cuerpo.draftRect.erase } });
    sendParams(false);
  } else if (paintKind === "muscle" && s.cuerpo.muscle?.draft) {
    s.cuerpo.muscle.draft.pts.push(pt);
    store.emit();
    sendParams(false);
  } else if (paintKind === "freeze" && s.cuerpo.draftFreeze) {
    s.cuerpo.draftFreeze.pts.push(pt);
    store.emit();
    sendParams(false);
  } else if (paintKind === "retouch" && s.retoque.draftStroke) {
    s.retoque.draftStroke.pts.push(pt);
    store.emit();
    sendParams(false);
  } else if (paintKind === "crop" && s.foto.cropStart) {
    const a = s.foto.cropStart;
    store.patchMode("foto", {
      crop: [
        Math.min(a[0], pt[0]),
        Math.min(a[1], pt[1]),
        Math.max(a[0], pt[0]),
        Math.max(a[1], pt[1]),
      ],
    });
  }
});
on("canvas-up", () => {
  panStart = null;
  store.patch({ panning: false });
  const s = store.get();
  const kind = paintKind;
  paintKind = null;
  if (kind === "muscle") {
    const m = s.cuerpo.muscle || {};
    const draft = m.draft;
    if (draft?.pts?.length) {
      store.patchMode("cuerpo", {
        muscle: {
          ...m,
          strokes: [...(m.strokes || []), {
            pts: draft.pts,
            radius: muscleRadius(m.radius),
            erase: Boolean(draft.erase),
          }],
          draft: null,
        },
      });
      sendParams(true, draft.erase ? "Borrar máscara" : "Pintar máscara");
    }
    return;
  }
  if (kind === "liquify") {
    const draft = s.cuerpo.draftStroke;
    if (draft?.pts?.length) {
      const stroke = brushToStroke(
        s.cuerpo.brush.softness,
        s.cuerpo.brush.radius,
        s.cuerpo.brush.intensity,
        draft.pts,
      );
      store.patchMode("cuerpo", { liquify: [...(s.cuerpo.liquify || []), stroke], draftStroke: null });
      sendParams(true, "Pincel");
    }
    return;
  }
  if (kind === "freeze") {
    const draft = s.cuerpo.draftFreeze;
    if (draft?.pts?.length) {
      store.patchMode("cuerpo", {
        freezeStrokes: [...(s.cuerpo.freezeStrokes || []), {
          pts: draft.pts,
          radius: freezeRadius(s.cuerpo.freeze?.radius),
          erase: Boolean(draft.erase),
        }],
        draftFreeze: null,
        frozen: true,
      });
      sendParams(true, draft.erase ? "Descongelar zona" : "Congelar");
    }
    return;
  }
  if (kind === "freeze-rect" || kind === "freeze-resize") {
    const r = s.cuerpo.draftRect;
    rectAnchor = null;
    const ok = r && r.w >= 0.01 && r.h >= 0.01;
    store.patchMode("cuerpo", {
      freezeRects: ok ? [...(s.cuerpo.freezeRects || []), r] : (s.cuerpo.freezeRects || []),
      draftRect: null,
      frozen: true,
    });
    sendParams(true, kind === "freeze-resize" ? "Redimensionar zona" : "Congelar rectángulo");
    return;
  }
  if (kind === "retouch") {
    const draft = s.retoque.draftStroke;
    if (draft?.pts?.length) {
      store.patchMode("retoque", {
        strokes: [...(s.retoque.strokes || []), {
          pts: draft.pts,
          radius: uiRadius(s.retoque.brush.radius, s.zoom),
          erase: false,
        }],
        draftStroke: null,
      });
      sendParams(true, "Retoque");
    }
    return;
  }
  if (kind === "crop") {
    const c = s.foto.crop;
    const valid = Array.isArray(c) && (c[2] - c[0]) >= 0.02 && (c[3] - c[1]) >= 0.02;
    store.patchMode("foto", { cropStart: null, crop: valid ? c : [0, 0, 1, 1] });
    sendParams(true, "Recorte");
  }
});

async function openFile(file) {
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.onload = async () => {
    const prev = store.get();
    if (prev.imageUrl) URL.revokeObjectURL(prev.imageUrl);
    const format = fileFormat(file.name, file.type);
    store.patch({
      hasImage: true,
      fileName: file.name,
      dirty: false,
      width: img.naturalWidth,
      height: img.naturalHeight,
      format,
      megapixels: (img.naturalWidth * img.naturalHeight) / 1_000_000,
      imageUrl: url,
      originalUrl: url,
      previewUrl: url,
      zoom: 100,
      panX: 0,
      panY: 0,
      faces: [{ id: 1, x: 0.31, y: 0.10, w: 0.38, h: 0.46 }],
      activeFace: 0,
      mode: store.get().mode === "ajustes" ? "rostro" : store.get().mode,
      undo: [],
      redo: [],
    });
    try {
      store.patch({ engine: "processing" });
      const session = await api.openSession(file);
      const faces = Array.isArray(session?.faces) && session.faces.length
        ? session.faces
        : store.get().faces;
      store.patch({ engine: "ok", toast: "", faces });
    } catch {
      store.patch({ engine: store.get().engine === "ok" ? "ok" : "down" });
    }
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}

function exportName(state) {
  const base = state.fileName.replace(/\.[^.]+$/, "") || "morfofix";
  const ext = state.format === "PNG" ? "png" : "jpg";
  return `${base}-morfofix.${ext}`;
}

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  downloadUrl(url, name);
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function downloadUrl(url, name) {
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
}

function applyDocInfo(info) {
  if (!info) return;
  const faces = facesFromInfo(info);
  store.patch({
    hasImage: true,
    fileName: info.file_name || info.fileName || store.get().fileName,
    dirty: Boolean(info.dirty),
    width: info.width || 0,
    height: info.height || 0,
    format: (info.format || "").toUpperCase() || store.get().format,
    megapixels: ((info.width || 0) * (info.height || 0)) / 1_000_000,
    engine: "ok",
    toast: "",
    faces: faces.length ? faces : store.get().faces,
    bodies: Array.isArray(info.bodies) ? info.bodies : store.get().bodies,
    poseAvailable: typeof info.pose_available === "boolean"
      ? info.pose_available
      : (Array.isArray(info.bodies) ? info.bodies.length > 0 : store.get().poseAvailable),
    activeFace: 0,
    zoom: 100,
    panX: 0,
    panY: 0,
    canUndo: false,
    canRedo: false,
    historyRemote: api.isTauri(),
  });
}

listen("engine://state", (dto) => {
  const ready = dto?.state === "ready";
  store.patch({
    engine: ready ? "ok" : "down",
    toast: dto?.state === "down" ? (dto.reason || "El motor local no responde") : store.get().toast,
  });
});
listen("doc://opened", (info) => {
  applyDocInfo(info);
  api.preview().then((res) => {
    if (res?.blob) applyPreviewBlob(res.blob, true);
  }).catch(() => {});
  api.recents().then((items) => store.patch({ recents: items || [] })).catch(() => {});
});
listen("doc://dirty", (payload) => {
  store.patch({
    dirty: Boolean(payload?.dirty),
    fileName: payload?.file_name || store.get().fileName,
  });
});
listen("doc://closed", () => {
  store.closeImage();
});
listen("app://toast", (payload) => {
  store.patch({ toast: payload?.message || "" });
});
listen("preview://busy", (busy) => {
  if (busy) store.patch({ engine: "processing" });
});
listen("preview://meta", (payload) => {
  const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
  const patch = { engineWarnings: warnings };
  if (typeof payload?.pose_available === "boolean") patch.poseAvailable = payload.pose_available;
  if (warnings.includes("POSE_UNAVAILABLE")) patch.poseAvailable = false;
  store.patch(patch);
});
listen("history://changed", (info) => {
  applyHistory(info);
});
listen("menu://compare", () => {
  const view = store.get().view === "despues" ? "antes" : "despues";
  store.patch({ view });
});
listen("menu://zoom", (dir) => {
  if (dir === "in") emit("zoom", { delta: 10 });
  else if (dir === "out") emit("zoom", { delta: -10 });
  else if (dir === "fit") store.patch({ zoom: 100, panX: 0, panY: 0 });
});
listen("menu://landmarks", () => {
  const next = !store.get().landmarks;
  store.patch({ landmarks: next });
  sendParams(false);
});
listen("autosave://offer", (items) => {
  if (Array.isArray(items) && items[0]) {
    store.patch({
      pendingAutosave: items[0].id,
      toast: `Recuperar la edición de ${items[0].file_name || "foto"}`,
    });
  }
});

async function ping(user) {
  try {
    await api.health();
    if (store.get().engine === "down") store.patch({ engine: "ok", toast: "" });
  } catch {
    if (store.get().engine !== "down" || user) engineDown(user);
  }
}

if (api.isTauri()) {
  store.patch({ historyRemote: true });
  api.current().then(async (snap) => {
    if (snap?.info) await afterOpen(snap.info);
    if (snap?.history) applyHistoryFlags(store, snap.history);
    if (snap?.state) fromEditState(store, snap.state);
  }).catch(() => {});
  api.recents().then((items) => store.patch({ recents: items || [] })).catch(() => {});
}

app.querySelector(".toast")?.addEventListener("click", (event) => {
  if (event.target.closest("[data-retry]")) return;
  if (store.get().pendingAutosave) emit("restore-autosave");
});

ping(false);
setInterval(() => ping(false), 4000);
loadCatalog().then(() => store.emit()).catch(() => {});
sync();
