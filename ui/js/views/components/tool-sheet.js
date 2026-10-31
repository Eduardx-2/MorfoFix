import { createSlider } from "./slider.js";
import { emit } from "../../controllers/bus.js";

export function mountToolSheet(host) {
  host.classList.add("tool-sheet");
  host.innerHTML = `
    <div class="tool-sheet-slider" data-sheet-slider></div>
    <div class="tool-sheet-bar">
      <button type="button" class="tool-sheet-x" data-sheet-cancel title="Cancelar">✕</button>
      <div class="tool-sheet-mid">
        <span data-sheet-title>Altura</span>
        <button type="button" class="tool-sheet-help" data-sheet-help title="Ayuda">?</button>
      </div>
      <button type="button" class="tool-sheet-ok" data-sheet-apply title="Aplicar">✓</button>
    </div>
    <div class="tool-sheet-pop" data-sheet-pop hidden></div>
  `;
  const sliderHost = host.querySelector("[data-sheet-slider]");
  const pop = host.querySelector("[data-sheet-pop]");
  const titleEl = host.querySelector("[data-sheet-title]");
  let key = "altura";
  let help = "";

  const slider = createSlider({
    label: "",
    min: -100,
    max: 100,
    value: 0,
    scale: true,
    onChange: (value) => emit("param", { mode: "cuerpo", key, value, commit: false, sheet: true }),
    onCommit: (value) => emit("param", { mode: "cuerpo", key, value, commit: true, sheet: true }),
  });
  sliderHost.append(slider.el);

  host.querySelector("[data-sheet-cancel]").addEventListener("click", () => emit("tool-sheet", { action: "cancel" }));
  host.querySelector("[data-sheet-apply]").addEventListener("click", () => emit("tool-sheet", { action: "apply" }));
  host.querySelector("[data-sheet-help]").addEventListener("click", (event) => {
    event.stopPropagation();
    pop.hidden = !pop.hidden;
  });
  document.addEventListener("click", (event) => {
    if (!pop.hidden && !host.contains(event.target)) pop.hidden = true;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !pop.hidden) pop.hidden = true;
  });

  return {
    sync(state, opts = {}) {
      const on = Boolean(opts.on);
      host.hidden = !on;
      if (!on) {
        pop.hidden = true;
        return;
      }
      key = opts.key || "altura";
      help = opts.help || "";
      titleEl.textContent = opts.title || "Altura";
      pop.textContent = help;
      slider.setValue(opts.value ?? 0);
    },
  };
}
