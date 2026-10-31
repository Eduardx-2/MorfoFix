import { debounce } from "./utils.js";
import { toEditState, toEngineParams } from "./params.js";

const BASE = "http://127.0.0.1:8765";

function isTauri() {
  return Boolean(window.__TAURI_INTERNALS__ || window.__TAURI__);
}

function invoke(cmd, args) {
  const fn = window.__TAURI__?.core?.invoke;
  if (!fn) throw new Error("Tauri no disponible");
  return fn(cmd, args);
}

export function listen(event, handler) {
  const fn = window.__TAURI__?.event?.listen;
  if (!fn) return Promise.resolve(() => {});
  return fn(event, (e) => handler(e.payload));
}

async function request(path, options = {}) {
  if (isTauri()) {
    throw new Error("HTTP del motor no está permitido en desktop");
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), options.timeout ?? 4000);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const type = res.headers.get("content-type") || "";
    if (type.includes("application/json")) return res.json();
    return res;
  } finally {
    clearTimeout(timer);
  }
}

function blobFromInvoke(buf) {
  const data = buf instanceof ArrayBuffer ? buf : new Uint8Array(buf).buffer;
  return new Blob([data], { type: "image/jpeg" });
}

export const api = {
  base: BASE,
  isTauri,

  async health() {
    if (isTauri()) {
      const status = await invoke("engine_status");
      if (status?.state !== "ready") throw new Error("down");
      return status;
    }
    const data = await request("/health", { timeout: 1200 });
    return data || { ok: true };
  },

  async restart() {
    if (isTauri()) return invoke("engine_restart");
    return this.health();
  },

  async openDialog() {
    if (!isTauri()) return null;
    const path = await invoke("open_image_dialog");
    if (!path) return null;
    return invoke("doc_open", { path });
  },

  async openPath(path) {
    if (!isTauri() || !path) return null;
    return invoke("doc_open", { path });
  },

  async openSession(file) {
    if (isTauri()) {
      return invoke("doc_current");
    }
    const body = new FormData();
    body.append("file", file);
    return request("/session", { method: "POST", body, timeout: 15000 });
  },

  async preview() {
    if (!isTauri()) return null;
    const buf = await invoke("doc_preview");
    return { blob: blobFromInvoke(buf) };
  },

  async detect() {
    if (!isTauri()) return null;
    return invoke("doc_detect");
  },

  async catalog() {
    if (isTauri()) return invoke("engine_catalog");
    try {
      const data = await request("/catalog");
      if (Array.isArray(data)) return data;
      if (Array.isArray(data?.params)) return data.params;
      return [];
    } catch {
      return [];
    }
  },

  async setParams(state, { interactive = true, commit = false, label = "Ajuste" } = {}) {
    if (isTauri()) {
      const edit = toEditState(state);
      const overlay = state.cuerpo?.tool === "musculo" && state.cuerpo?.muscle?.showMask
        ? "muscle"
        : (state.landmarks ? "landmarks" : null);
      const buf = await invoke("edit_preview", { state: edit, interactive, overlay });
      let history = null;
      if (commit) history = await invoke("edit_commit", { state: edit, label });
      return { blob: blobFromInvoke(buf), history };
    }
    return request("/params", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toEngineParams(state)),
      timeout: 8000,
    });
  },

  async undo() {
    if (isTauri()) return invoke("history_undo");
    return null;
  },

  async redo() {
    if (isTauri()) return invoke("history_redo");
    return null;
  },

  async exportImage(format = "png") {
    if (isTauri()) {
      const path = await invoke("export_dialog", { format });
      if (!path) return null;
      return invoke("doc_export", {
        req: {
          path,
          format,
          quality: 92,
          keep_metadata: true,
          keep_gps: false,
        },
      });
    }
    return request("/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ format }),
      timeout: 20000,
    });
  },

  async current() {
    if (!isTauri()) return null;
    return invoke("doc_current");
  },

  async recents() {
    if (!isTauri()) return [];
    return invoke("recents_list");
  },

  async clearRecents() {
    if (!isTauri()) return;
    return invoke("recents_clear");
  },

  async about() {
    if (!isTauri()) return null;
    return invoke("about_info");
  },

  async autosaves() {
    if (!isTauri()) return [];
    return invoke("autosave_list");
  },

  async restoreAutosave(id) {
    if (!isTauri() || !id) return null;
    return invoke("autosave_restore", { id });
  },

  async discardAutosave(id) {
    if (!isTauri() || !id) return;
    return invoke("autosave_discard", { id });
  },
};

api.setParamsDebounced = debounce((state, onDone, onError) => {
  api.setParams(state, { interactive: true, commit: false }).then(onDone).catch(onError);
}, 16);

api.setParamsDebounced60 = debounce((state, onDone, onError) => {
  api.setParams(state, { interactive: true, commit: false }).then(onDone).catch(onError);
}, 60);
