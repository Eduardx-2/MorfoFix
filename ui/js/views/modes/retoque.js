import { createSlider } from "../components/slider.js";
import { renderToolGroups } from "../components/tool-grid.js";
import { createComingSoon } from "../components/coming-soon.js";
import { createChips } from "../components/chips.js";
import { emit } from "../../controllers/bus.js";

const GROUPS = [
  {
    label: "Clásico",
    tools: [
      { id: "dientes", icon: "teeth", title: "Blanquear dientes", sub: "Solo el interior de la boca" },
      { id: "iluminar", icon: "brighten", title: "Iluminar ojos", sub: "Ojos más claros y vivos" },
      { id: "pincel", icon: "heal", title: "Pincel suavizar", sub: "Suavizá la piel donde pintes" },
    ],
  },
  {
    label: "Estilo",
    tools: [
      { id: "maquillaje", icon: "makeup", title: "Maquillaje", sub: "Próximamente", v2: true, disabled: true },
      { id: "esculpir", icon: "sculpt", title: "Esculpir", sub: "Próximamente", v2: true, disabled: true },
      { id: "tono", icon: "tone", title: "Tono de piel", sub: "Próximamente", v2: true, disabled: true },
      { id: "glow", icon: "glow", title: "Glow", sub: "Próximamente", v2: true, disabled: true },
      { id: "ojos", icon: "eyes", title: "Ojos", sub: "Próximamente", v2: true, disabled: true },
    ],
  },
  {
    label: "IA",
    tools: [
      { id: "ia-retoque", icon: "spark", title: "Retoque IA", sub: "Requiere FixPlus", remote: true },
    ],
  },
];

export function mountRetoque(root) {
  const wrap = document.createElement("div");
  wrap.className = "stack";
  const grid = document.createElement("div");
  grid.className = "tool-groups";
  renderToolGroups(grid, GROUPS, (id) => emit("retoque-tool", { tool: id }));

  const teeth = createSlider({
    label: "Blanqueo",
    scale: true,
    onChange: (value) => emit("param", { mode: "retoque", key: "teeth", value, commit: false }),
    onCommit: (value) => emit("param", { mode: "retoque", key: "teeth", value, commit: true }),
  });
  const illuminate = createSlider({
    label: "Iluminar",
    scale: true,
    onChange: (value) => emit("param", { mode: "retoque", key: "illuminate", value, commit: false }),
    onCommit: (value) => emit("param", { mode: "retoque", key: "illuminate", value, commit: true }),
  });
  const radius = createSlider({
    label: "Radio",
    min: 0,
    max: 100,
    bipolar: false,
    value: 28,
    onChange: (value) => emit("retoque-brush", { key: "radius", value, commit: false }),
    onCommit: (value) => emit("retoque-brush", { key: "radius", value, commit: true }),
  });
  const intensity = createSlider({
    label: "Intensidad",
    min: 0,
    max: 100,
    bipolar: false,
    value: 50,
    onChange: (value) => emit("retoque-brush", { key: "intensity", value, commit: false }),
    onCommit: (value) => emit("retoque-brush", { key: "intensity", value, commit: true }),
  });

  const boxes = {
    dientes: document.createElement("div"),
    iluminar: document.createElement("div"),
    pincel: document.createElement("div"),
  };
  for (const box of Object.values(boxes)) box.className = "stack";
  boxes.dientes.append(teeth.el);
  boxes.iluminar.append(illuminate.el);
  boxes.pincel.append(radius.el, intensity.el);

  const soon = createComingSoon();
  const chips = createChips();
  wrap.append(grid, chips.el, ...Object.values(boxes), soon);
  root.replaceChildren(wrap);

  return {
    sync(state) {
      grid.querySelectorAll(".tool-card").forEach((card) => {
        card.classList.toggle("is-on", card.dataset.tool === state.retoque.tool);
      });
      chips.set((state.engineWarnings || []).filter((c) => c === "NO_FACE_RETOUCH"));
      teeth.setValue(state.retoque.teeth);
      illuminate.setValue(state.retoque.illuminate);
      radius.setValue(state.retoque.brush.radius);
      intensity.setValue(state.retoque.brush.intensity);
      for (const [id, box] of Object.entries(boxes)) {
        box.style.display = state.retoque.tool === id ? "flex" : "none";
      }
      soon.style.display = ["maquillaje", "esculpir", "tono", "glow", "ojos"].includes(state.retoque.tool)
        ? "block" : "none";
    },
  };
}
