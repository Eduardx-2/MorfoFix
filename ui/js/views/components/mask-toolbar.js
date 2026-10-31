import { icon } from "../icons.js";
import { emit } from "../../controllers/bus.js";

export function mountMaskToolbar(host) {
  host.innerHTML = `
    <button type="button" data-mask-op="erase" title="Borrar: saca el músculo donde pases (por defecto el efecto cubre todo el cuerpo)">${icon("erase")}<span>Borrar</span></button>
    <button type="button" data-mask-op="add" title="Pintar: el músculo queda SOLO donde pintes">${icon("brush")}<span>Solo aquí</span></button>
    <div class="mask-size">
      <span>Tamaño</span>
      <input type="range" min="8" max="100" value="40" data-mask-size />
    </div>
    <button type="button" data-mask-view title="Ver máscara">${icon("eye")}<span>Ver</span></button>
    <button type="button" data-mask-invert title="Invertir">${icon("invert")}<span>Invertir</span></button>
    <button type="button" data-mask-clear title="Limpiar">${icon("trash")}<span>Limpiar</span></button>
  `;

  host.addEventListener("click", (event) => {
    const btn = event.target.closest("button");
    if (!btn) return;
    if (btn.dataset.maskOp) emit("muscle-mask", { key: "op", value: btn.dataset.maskOp });
    if ("maskView" in btn.dataset) emit("muscle-mask", { key: "showMask", toggle: true });
    if ("maskInvert" in btn.dataset) emit("muscle-mask", { key: "invert" });
    if ("maskClear" in btn.dataset) emit("muscle-mask", { key: "clear" });
  });
  host.querySelector("[data-mask-size]").addEventListener("input", (event) => {
    emit("muscle-mask", { key: "radius", value: Number(event.target.value), commit: false });
  });
  host.querySelector("[data-mask-size]").addEventListener("change", (event) => {
    emit("muscle-mask", { key: "radius", value: Number(event.target.value), commit: true });
  });

  return {
    sync(state) {
      const m = state.cuerpo?.muscle;
      const on = state.hasImage && state.mode === "cuerpo" && state.cuerpo.tool === "musculo";
      host.hidden = !on;
      if (!on || !m) return;
      host.querySelectorAll("[data-mask-op]").forEach((btn) => {
        btn.classList.toggle("is-on", btn.dataset.maskOp === (m.op || "erase"));
      });
      host.querySelector("[data-mask-view]").classList.toggle("is-on", Boolean(m.showMask));
      const size = host.querySelector("[data-mask-size]");
      if (Number(size.value) !== m.radius) size.value = String(m.radius ?? 40);
    },
  };
}
