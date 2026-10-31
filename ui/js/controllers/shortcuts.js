import { emit } from "./bus.js";
import { clamp } from "../models/utils.js";

export function bindShortcuts(store) {
  window.addEventListener("keydown", (event) => {
    const meta = event.ctrlKey || event.metaKey;
    const tag = event.target.closest("input, textarea");
    if (tag) return;

    if (meta && event.key.toLowerCase() === "o") {
      event.preventDefault();
      emit("open");
    }
    if (meta && (event.key.toLowerCase() === "s" || event.key.toLowerCase() === "e")) {
      event.preventDefault();
      emit("export");
    }
    if (meta && event.key.toLowerCase() === "z") {
      event.preventDefault();
      emit(event.shiftKey ? "redo" : "undo");
    }
    if (meta && event.key.toLowerCase() === "y") {
      event.preventDefault();
      emit("redo");
    }
    if (event.key === "\\" && !meta) {
      event.preventDefault();
      const view = store.get().view === "antes" ? "despues" : "antes";
      emit("view", { view });
    }
    if (event.code === "Space") {
      event.preventDefault();
      store.patch({ spaceDown: true, cursor: "default" });
    }
    if (event.key === "[" || event.key === "]") {
      const s = store.get();
      const muscle = s.mode === "cuerpo" && s.cuerpo.tool === "musculo";
      const brush = s.mode === "retoque" ? s.retoque.brush
        : (s.mode === "cuerpo" && s.cuerpo.tool === "congelar") ? s.cuerpo.freeze
        : muscle ? s.cuerpo.muscle
        : s.cuerpo.brush;
      const next = clamp((brush.radius ?? 40) + (event.key === "]" ? 4 : -4), 0, 100);
      brush.radius = next;
      store.emit();
    }
    if (event.key.toLowerCase() === "m" && !meta) {
      const s = store.get();
      if (s.mode === "cuerpo" && s.cuerpo.tool === "musculo") {
        emit("muscle-mask", { key: "showMask", toggle: true });
      }
    }
    if (event.key.toLowerCase() === "f" && !meta) {
      const s = store.get();
      if (s.mode !== "cuerpo") return;
      // F activa la herramienta Congelar (antes creaba un rect fijo 0.22×0.18).
      store.patchMode("cuerpo", { tool: "congelar" });
      store.patch({ cursor: s.cuerpo.freeze?.mode === "rect" ? "default" : "brush" });
    }
    if ((event.key === "Escape" || event.key === "Enter") && !meta) {
      const s = store.get();
      if (s.mode === "cuerpo" && (s.cuerpo.tool === "altura" || s.cuerpo.tool === "brazo")) {
        event.preventDefault();
        emit("tool-sheet", { action: event.key === "Enter" ? "apply" : "cancel" });
      }
    }
    // Alt ya no borra todo el congelado al tocarlo (se disparaba con Alt+Tab):
    // ahora, mantenido mientras pintás, resta de la máscara (ver canvas-down).
  });

  window.addEventListener("keyup", (event) => {
    if (event.code === "Space") {
      const s = store.get();
      const brush = (s.mode === "cuerpo" && s.cuerpo.tool === "adelgazar" && s.cuerpo.sub === "pincel")
        || (s.mode === "cuerpo" && s.cuerpo.tool === "congelar")
        || (s.mode === "cuerpo" && s.cuerpo.tool === "musculo")
        || (s.mode === "retoque" && s.retoque.tool === "pincel");
      store.patch({ spaceDown: false, panning: false, cursor: brush ? "brush" : "default" });
    }
  });
}
