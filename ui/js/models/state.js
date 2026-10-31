import { defaultsFor } from "./params.js";
import { applySnapshot, snapshot } from "./utils.js";

const MAX_HISTORY = 40;

function initialState() {
  return {
    hasImage: false,
    fileName: "",
    dirty: false,
    width: 0,
    height: 0,
    format: "",
    megapixels: 0,
    imageUrl: "",
    originalUrl: "",
    previewUrl: "",
    zoom: 100,
    panX: 0,
    panY: 0,
    mode: "rostro",
    view: "despues",
    split: 50,
    engine: "down",
    spaceDown: false,
    panning: false,
    faces: [],
    bodies: [],
    poseAvailable: false,
    activeFace: 0,
    panelAlert: "",
    engineWarnings: [],
    landmarks: false,
    canUndo: false,
    canRedo: false,
    historyRemote: false,
    pendingAutosave: null,
    recents: [],
    cursor: "default",
    toast: "",
    rostro: defaultsFor("rostro"),
    cuerpo: defaultsFor("cuerpo"),
    retoque: defaultsFor("retoque"),
    foto: defaultsFor("foto"),
    ajustes: {
      showShortcuts: true,
      showOverlays: true,
    },
    undo: [],
    redo: [],
  };
}

class Store {
  constructor() {
    this.state = initialState();
    this.listeners = new Set();
  }

  get() {
    return this.state;
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  emit() {
    for (const fn of this.listeners) fn(this.state);
  }

  patch(partial) {
    Object.assign(this.state, partial);
    this.emit();
  }

  patchMode(mode, partial) {
    Object.assign(this.state[mode], partial);
    this.state.dirty = this.state.hasImage;
    this.emit();
  }

  setParam(mode, key, value) {
    this.state[mode][key] = value;
    this.state.dirty = this.state.hasImage;
    this.emit();
  }

  pushHistory() {
    this.state.undo.push(snapshot(this.state));
    if (this.state.undo.length > MAX_HISTORY) this.state.undo.shift();
    this.state.redo = [];
  }

  undo() {
    if (!this.state.undo.length) return;
    this.state.redo.push(snapshot(this.state));
    applySnapshot(this.state, this.state.undo.pop());
    this.emit();
  }

  redo() {
    if (!this.state.redo.length) return;
    this.state.undo.push(snapshot(this.state));
    applySnapshot(this.state, this.state.redo.pop());
    this.emit();
  }

  resetMode() {
    const mode = this.state.mode;
    if (!["rostro", "cuerpo", "retoque", "foto"].includes(mode)) return;
    this.pushHistory();
    const keep = {};
    if (mode === "rostro") {
      keep.tab = this.state.rostro.tab;
      keep.moreOpen = this.state.rostro.moreOpen;
    }
    if (mode === "cuerpo") {
      keep.tool = this.state.cuerpo.tool;
      keep.sub = this.state.cuerpo.sub;
      keep.protectBg = this.state.cuerpo.protectBg;
      keep.manipulator = this.state.cuerpo.manipulator;
    }
    if (mode === "retoque") keep.tool = this.state.retoque.tool;
    if (mode === "foto") keep.tool = this.state.foto.tool;
    Object.assign(this.state[mode], defaultsFor(mode), keep);
    this.state.dirty = true;
    this.emit();
  }

  closeImage() {
    if (this.state.imageUrl) URL.revokeObjectURL(this.state.imageUrl);
    if (this.state.originalUrl && this.state.originalUrl !== this.state.imageUrl) {
      URL.revokeObjectURL(this.state.originalUrl);
    }
    this.state = initialState();
    this.emit();
  }
}

export const store = new Store();
