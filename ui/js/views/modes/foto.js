import { createSlider } from "../components/slider.js";
import { renderToolGroups } from "../components/tool-grid.js";
import { createComingSoon } from "../components/coming-soon.js";
import { emit } from "../../controllers/bus.js";

const GROUPS = [
  {
    label: "Ajuste",
    tools: [
      { id: "recortar", icon: "crop", title: "Recortar / Rotar", sub: "Encadre y giro" },
      { id: "hsl", icon: "hsl", title: "HSL", sub: "Tono, saturación y luz" },
    ],
  },
  {
    label: "Look",
    tools: [
      { id: "filtros", icon: "filter", title: "Filtros", sub: "LUTs locales", v2: true },
      { id: "fondo", icon: "bg", title: "Fondo", sub: "Reemplazo local", v2: true },
      { id: "capas", icon: "layers", title: "Capas", sub: "Overlays y texto", v2: true },
    ],
  },
  {
    label: "IA",
    tools: [
      { id: "ia-foto", icon: "spark", title: "Generar fondo", sub: "Requiere FixPlus", remote: true },
    ],
  },
];

export function mountFoto(root) {
  const wrap = document.createElement("div");
  wrap.className = "stack";
  const grid = document.createElement("div");
  grid.className = "tool-groups";
  renderToolGroups(grid, GROUPS, (id) => emit("foto-tool", { tool: id }));

  const rotate = createSlider({
    label: "Rotar",
    min: -45,
    max: 45,
    onChange: (value) => emit("param", { mode: "foto", key: "rotate", value, commit: false }),
    onCommit: (value) => emit("param", { mode: "foto", key: "rotate", value, commit: true }),
  });
  const h = createSlider({
    label: "Tono",
    onChange: (value) => emit("param", { mode: "foto", key: "h", value, commit: false }),
    onCommit: (value) => emit("param", { mode: "foto", key: "h", value, commit: true }),
  });
  const s = createSlider({
    label: "Saturación",
    onChange: (value) => emit("param", { mode: "foto", key: "s", value, commit: false }),
    onCommit: (value) => emit("param", { mode: "foto", key: "s", value, commit: true }),
  });
  const l = createSlider({
    label: "Luz",
    onChange: (value) => emit("param", { mode: "foto", key: "l", value, commit: false }),
    onCommit: (value) => emit("param", { mode: "foto", key: "l", value, commit: true }),
  });

  const recortar = document.createElement("div");
  recortar.className = "stack";
  recortar.innerHTML = `<p class="muted">Arrastrá las esquinas en el lienzo para recortar. Doble clic en el slider vuelve a 0°.</p>`;
  recortar.append(rotate.el);

  const hsl = document.createElement("div");
  hsl.className = "stack";
  hsl.append(h.el, s.el, l.el);

  const soon = createComingSoon();
  wrap.append(grid, recortar, hsl, soon);
  root.replaceChildren(wrap);

  return {
    sync(state) {
      grid.querySelectorAll(".tool-card").forEach((card) => {
        card.classList.toggle("is-on", card.dataset.tool === state.foto.tool);
      });
      rotate.setValue(state.foto.rotate);
      h.setValue(state.foto.h);
      s.setValue(state.foto.s);
      l.setValue(state.foto.l);
      recortar.style.display = state.foto.tool === "recortar" ? "flex" : "none";
      hsl.style.display = state.foto.tool === "hsl" ? "flex" : "none";
      soon.style.display = ["filtros", "fondo", "capas"].includes(state.foto.tool) ? "block" : "none";
    },
  };
}
