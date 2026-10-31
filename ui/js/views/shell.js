import { icon } from "./icons.js";
import { emit } from "../controllers/bus.js";

const MODES = [
  { id: "rostro", icon: "face", label: "Rostro" },
  { id: "cuerpo", icon: "body", label: "Cuerpo" },
  { id: "retoque", icon: "retouch", label: "Retoque" },
  { id: "foto", icon: "photo", label: "Foto" },
];

export function mountShell(app) {
  const fileName = app.querySelector("[data-file-name]");
  const zoomVal = app.querySelector("[data-zoom]");
  const dims = app.querySelector("[data-dims]");
  const modeInfo = app.querySelector("[data-mode-info]");
  const undoBtn = app.querySelector("[data-undo]");
  const redoBtn = app.querySelector("[data-redo]");
  const exportBtn = app.querySelector("[data-export]");
  const zoomOut = app.querySelector("[data-zoom-out]");
  const zoomIn = app.querySelector("[data-zoom-in]");

  app.querySelector("[data-open]")?.addEventListener("click", () => emit("open"));
  exportBtn?.addEventListener("click", () => emit("export"));
  undoBtn?.addEventListener("click", () => emit("undo"));
  redoBtn?.addEventListener("click", () => emit("redo"));
  zoomOut?.addEventListener("click", () => emit("zoom", { delta: -10 }));
  zoomIn?.addEventListener("click", () => emit("zoom", { delta: 10 }));

  app.querySelectorAll("[data-mode-btn]").forEach((btn) => {
    btn.addEventListener("click", () => emit("mode", { mode: btn.dataset.modeBtn }));
  });

  app.querySelector("[data-retry]")?.addEventListener("click", () => emit("retry-engine"));

  return {
    sync(state) {
      app.dataset.hasImage = String(state.hasImage);
      app.dataset.dirty = String(state.dirty);
      app.dataset.mode = state.mode;
      app.dataset.tool = state.mode === "cuerpo" ? state.cuerpo.tool
        : state.mode === "retoque" ? state.retoque.tool
        : state.mode === "foto" ? state.foto.tool
        : "";
      app.dataset.view = state.view;
      app.dataset.engine = state.engine;
      app.dataset.cursor = state.cursor;

      document.title = state.hasImage ? `MorfoFix — ${state.fileName}` : "MorfoFix";
      fileName.textContent = state.hasImage ? state.fileName : "Sin imagen";
      zoomVal.textContent = `${state.zoom}%`;

      const mp = state.megapixels ? `${state.megapixels.toFixed(1)} MP` : "—";
      dims.textContent = state.hasImage
        ? `${state.width} × ${state.height} · ${mp} · ${state.format}`
        : "—";
      const modeLabel = MODES.find((m) => m.id === state.mode)?.label ?? "Ajustes";
      if (state.mode === "cuerpo" && state.cuerpo.tool === "musculo") {
        const m = state.cuerpo.muscle || {};
        const erased = (m.strokes || []).filter((s) => s.erase).length;
        const added = (m.strokes || []).length - erased;
        const mask = erased ? `Máscara: ${erased} trazo${erased === 1 ? "" : "s"} borrado${erased === 1 ? "" : "s"}`
          : added ? `Máscara: ${added} trazo${added === 1 ? "" : "s"}` : "Sin máscara";
        modeInfo.textContent = `Músculo · nivel ${m.level ?? 0} · ${mask}`;
      } else {
        modeInfo.textContent = `${state.zoom}% · ${modeLabel}`;
      }
      const chip = app.querySelector(".statusbar .chip");
      if (chip) {
        const label = state.engine === "ok" ? "Motor listo"
          : state.engine === "processing" ? "Motor ocupado"
          : "Motor caído";
        chip.textContent = `${label} · local`;
      }

      const canUndo = state.historyRemote ? state.canUndo : state.undo.length > 0;
      const canRedo = state.historyRemote ? state.canRedo : state.redo.length > 0;
      undoBtn.disabled = !canUndo;
      redoBtn.disabled = !canRedo;
      exportBtn.disabled = !state.hasImage;
      zoomOut.disabled = !state.hasImage;
      zoomIn.disabled = !state.hasImage;

      app.querySelectorAll("[data-mode-btn]").forEach((btn) => {
        btn.classList.toggle("is-on", btn.dataset.modeBtn === state.mode);
      });

      const toast = app.querySelector(".toast");
      toast.classList.toggle("is-on", Boolean(state.toast));
      app.querySelector(".toast-msg").textContent = state.toast;
    },
  };
}

export { MODES, icon };
