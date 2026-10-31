import { createSlider } from "../components/slider.js";
import { createSeg } from "../components/seg.js";
import { createToggleRow } from "../components/toggle.js";
import { renderToolGroups } from "../components/tool-grid.js";
import { createSteps } from "../components/steps.js";
import { createPersons } from "../components/persons.js";
import { createModeCards } from "../components/mode-cards.js";
import { createAlert } from "../components/alert.js";
import { createChips } from "../components/chips.js";
import { createComingSoon } from "../components/coming-soon.js";
import { emit } from "../../controllers/bus.js";
import { poseIsAvailable, bodyParts } from "../../models/params.js";
import { icon } from "../icons.js";

const GROUPS = [
  {
    label: "Forma",
    tools: [
      { id: "adelgazar", icon: "slim", title: "Adelgazar manual", sub: "Pincel o manipulador" },
      { id: "altura", icon: "height", title: "Altura", sub: "Estirá o comprimí" },
      { id: "congelar", icon: "freeze", title: "Congelar", sub: "Protegé una zona" },
      { id: "auto", icon: "auto", title: "Auto cintura/cadera", sub: "Ajuste por pose" },
      { id: "brazo", icon: "arm", title: "Brazo", sub: "Superior, antebrazo o manual" },
      { id: "partes", icon: "parts", title: "Por partes", sub: "Próximamente", v2: true, disabled: true },
    ],
  },
  {
    label: "Estilo",
    tools: [
      { id: "musculo", icon: "muscle", title: "Músculo", sub: "Relieve local sobre la piel", v2: true },
      { id: "presets", icon: "presets", title: "Presets", sub: "Próximamente", v2: true, disabled: true },
      { id: "tatuaje", icon: "tattoo", title: "Tatuaje", sub: "Próximamente", v2: true, disabled: true },
    ],
  },
  {
    label: "IA",
    tools: [
      { id: "ia-cuerpo", icon: "spark", title: "Mejorar cuerpo", sub: "Requiere FixPlus", remote: true },
    ],
  },
];

export function mountCuerpo(root) {
  const sliders = {};
  const wrap = document.createElement("div");
  wrap.className = "stack";

  const grid = document.createElement("div");
  grid.className = "tool-groups";
  renderToolGroups(grid, GROUPS, (id) => emit("cuerpo-tool", { tool: id }));

  const sub = createSeg({
    items: [
      { value: "pincel", label: "Pincel" },
      { value: "manipulador", label: "Manipulador" },
    ],
    value: "pincel",
    full: true,
    onChange: (value) => emit("cuerpo-sub", { sub: value }),
  });

  const softness = createSeg({
    items: [
      { value: "suave", label: "Suave" },
      { value: "fuerte", label: "Fuerte" },
    ],
    value: "suave",
    full: true,
    onChange: (value) => emit("cuerpo-soft", { softness: value }),
  });

  function add(key, target, opts, path = "cuerpo") {
    sliders[key] = createSlider({
      ...opts,
      onChange: (value) => emit("param", { mode: path, key, value, commit: false }),
      onCommit: (value) => emit("param", { mode: path, key, value, commit: true }),
    });
    return sliders[key];
  }

  const brushBox = document.createElement("div");
  brushBox.className = "stack";
  const radius = createSlider({
    label: "Radio",
    min: 0,
    max: 100,
    bipolar: false,
    value: 36,
    onChange: (value) => emit("brush", { key: "radius", value, commit: false }),
    onCommit: (value) => emit("brush", { key: "radius", value, commit: true }),
  });
  const intensity = createSlider({
    label: "Intensidad",
    min: 0,
    max: 100,
    bipolar: false,
    value: 42,
    onChange: (value) => emit("brush", { key: "intensity", value, commit: false }),
    onCommit: (value) => emit("brush", { key: "intensity", value, commit: true }),
  });
  sliders.radius = radius;
  sliders.intensity = intensity;
  brushBox.append(softness.el, radius.el, intensity.el);

  const manBox = document.createElement("div");
  manBox.className = "stack";
  const edge = createSlider({
    label: "Suavidad del borde",
    min: 0,
    max: 100,
    bipolar: false,
    variant: "secondary",
    value: 48,
    onChange: (value) => emit("manip-field", { key: "edge", value }),
    onCommit: (value) => emit("manip-field", { key: "edge", value, commit: true }),
  });
  const step = createSlider({
    label: "Paso por clic",
    min: 1,
    max: 25,
    bipolar: false,
    variant: "secondary",
    value: 10,
    onChange: (value) => emit("manip-field", { key: "step", value }),
    onCommit: (value) => emit("manip-field", { key: "step", value, commit: true }),
  });
  sliders.edge = edge;
  sliders.step = step;
  const symmetric = createToggleRow({
    title: "Simétrico",
    subtitle: "Aplicá el mismo paso a ambos lados",
    on: true,
    onChange: (value) => emit("manip-field", { key: "symmetric", value, commit: true }),
  });
  const manInfo = document.createElement("p");
  manInfo.className = "muted";
  manInfo.dataset.manipInfo = "";
  manBox.append(manInfo, edge.el, step.el, symmetric.el);

  const alturaBox = document.createElement("div");
  alturaBox.className = "stack";
  const heightHint = document.createElement("p");
  heightHint.className = "muted";
  heightHint.textContent = "Arrastrá las dos líneas sobre la foto. El slider de abajo elige cuánto se estira la zona.";
  alturaBox.append(heightHint);

  const ARM_MODES = [
    { id: "leftupper", label: "Sup (I)" },
    { id: "leftforearm", label: "Ant (I)" },
    { id: "rightupper", label: "Sup (D)" },
    { id: "rightforearm", label: "Ant (D)" },
    { id: "manual", label: "Manual", icon: "hand" },
  ];
  const armBox = document.createElement("div");
  armBox.className = "stack arm-panel";
  const armProtect = createToggleRow({
    title: "Protección de fondo",
    subtitle: "No deformar lo que no es cuerpo",
    on: true,
    onChange: (value) => emit("arm-protect", { value }),
  });
  const armModes = document.createElement("div");
  armModes.className = "arm-modes";
  armModes.setAttribute("role", "radiogroup");
  armModes.innerHTML = ARM_MODES.map((m) => `
    ${m.id === "manual" ? `<span class="arm-sep"></span>` : ""}
    <button class="arm-mode" type="button" role="radio" data-arm-mode="${m.id}" title="">
      ${m.icon ? icon(m.icon) : ""}
      <span>${m.label}</span>
      <i class="arm-dot" hidden></i>
    </button>
  `).join("");
  armModes.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-arm-mode]");
    if (!btn || btn.getAttribute("aria-disabled") === "true") return;
    emit("arm-mode", { mode: btn.dataset.armMode });
  });
  const armHint = document.createElement("p");
  armHint.className = "muted";
  armBox.append(armProtect.el, armModes, armHint);

  const freezeBox = document.createElement("div");
  freezeBox.className = "stack";
  const freezeMode = createSeg({
    items: [
      { value: "pincel", label: "Pincel" },
      { value: "rect", label: "Rectángulo" },
    ],
    value: "pincel",
    full: true,
    onChange: (value) => emit("freeze-field", { key: "mode", value }),
  });
  const freezeOp = createSeg({
    items: [
      { value: "add", label: "Agregar" },
      { value: "erase", label: "Borrar" },
    ],
    value: "add",
    full: true,
    onChange: (value) => emit("freeze-field", { key: "op", value }),
  });
  const freezeRadiusSl = createSlider({
    label: "Radio (% lado menor)",
    min: 0,
    max: 100,
    bipolar: false,
    value: 20,
    onChange: (value) => emit("freeze-field", { key: "radius", value }),
    onCommit: (value) => emit("freeze-field", { key: "radius", value }),
  });
  const freezeFeatherSl = createSlider({
    label: "Difuminado del borde",
    min: 0,
    max: 100,
    bipolar: false,
    variant: "secondary",
    value: 30,
    onChange: (value) => emit("freeze-field", { key: "feather", value }),
    onCommit: (value) => emit("freeze-field", { key: "feather", value, commit: true }),
  });
  const freezeInvert = createToggleRow({
    title: "Invertir",
    subtitle: "Congelá todo menos lo marcado",
    on: false,
    onChange: (value) => emit("freeze-field", { key: "invert", value, commit: true }),
  });
  const freezeClear = document.createElement("button");
  freezeClear.type = "button";
  freezeClear.className = "btn";
  freezeClear.textContent = "Limpiar zonas";
  freezeClear.addEventListener("click", () => emit("secondary"));
  const freezeHint = document.createElement("p");
  freezeHint.className = "muted";
  freezeHint.innerHTML = `Sumá varias zonas. <kbd>Alt</kbd> + arrastrar resta. En rectángulo, arrastrá una esquina para redimensionar.`;
  freezeBox.append(freezeMode.el, freezeOp.el, freezeRadiusSl.el, freezeFeatherSl.el, freezeInvert.el, freezeClear, freezeHint);

  const autoBox = document.createElement("div");
  autoBox.className = "stack";
  autoBox.append(
    add("waist", autoBox, { label: "Cintura", scale: true }).el,
    add("hip", autoBox, { label: "Cadera", scale: true }).el,
  );

  const protect = createToggleRow({
    title: "Protección de fondo",
    subtitle: "No deformar lo que no es cuerpo",
    on: true,
    onChange: (value) => emit("protect-bg", { value }),
  });

  const muscleBox = document.createElement("div");
  muscleBox.className = "stack muscle-panel";
  const persons = createPersons({
    onChange: (person) => emit("muscle-field", { key: "person", value: person, commit: true }),
  });
  const modes = createModeCards({
    onChange: (mode) => emit("muscle-field", { key: "mode", value: mode, commit: true }),
  });
  const steps = createSteps({
    value: 3,
    onChange: (level) => emit("muscle-field", { key: "level", value: level, commit: true }),
  });
  const stepMeta = document.createElement("div");
  stepMeta.className = "steps-meta";
  stepMeta.innerHTML = `<span>Original</span><span class="steps-count"></span><span>Máximo</span>`;
  const definition = createSlider({
    label: "Definición",
    min: 0,
    max: 100,
    bipolar: false,
    value: 60,
    onChange: (value) => emit("muscle-field", { key: "definition", value, commit: false }),
    onCommit: (value) => emit("muscle-field", { key: "definition", value, commit: true }),
  });
  const light = createSeg({
    items: [
      { value: "auto", label: "Auto" },
      { value: "top", label: "Arriba" },
      { value: "left", label: "Izq." },
      { value: "right", label: "Der." },
    ],
    value: "auto",
    full: true,
    onChange: (value) => emit("muscle-field", { key: "light", value, commit: true }),
  });
  const volume = createToggleRow({
    title: "Volumen",
    subtitle: "Deforma levemente el contorno",
    on: true,
    onChange: (value) => emit("muscle-field", { key: "volume", value, commit: true }),
  });
  const gloss = createToggleRow({
    title: "Piel brillante",
    subtitle: "Reflejo especular suave",
    on: false,
    onChange: (value) => emit("muscle-field", { key: "gloss", value, commit: true }),
  });
  const muscleAlert = createAlert();
  const muscleChips = createChips();
  muscleBox.append(
    persons.el,
    modes.el,
    muscleAlert.el,
    muscleChips.el,
    stepMeta,
    steps.el,
    definition.el,
    light.el,
    volume.el,
    gloss.el,
  );

  const soonBox = document.createElement("div");
  soonBox.className = "stack";
  soonBox.append(createComingSoon());

  // Avisos del motor también fuera de Músculo (antes Forma/Brazo fallaban en silencio).
  const formChips = createChips();
  wrap.append(grid, formChips.el, sub.el, brushBox, manBox, alturaBox, freezeBox, autoBox, armBox, muscleBox, soonBox, protect.el);
  root.replaceChildren(wrap);

  return {
    sync(state) {
      const tool = state.cuerpo.tool;
      grid.querySelectorAll(".tool-card").forEach((card) => {
        card.classList.toggle("is-on", card.dataset.tool === tool);
      });
      const drill = tool === "musculo";
      grid.style.display = drill ? "none" : "flex";
      muscleBox.style.display = drill ? "flex" : "none";
      soonBox.style.display = ["partes", "presets", "tatuaje"].includes(tool) ? "flex" : "none";
      const m = state.cuerpo.muscle || {};
      formChips.set(drill ? [] : (state.engineWarnings || []).filter((c) => /^(ARM_PART_SKIPPED|LEG_PART_SKIPPED|NO_BODY|POSE_UNAVAILABLE|NO_PERSON_MASK|NO_BODY_MASK)/.test(c)));
      if (drill) {
        persons.set(state);
        modes.set(m.mode || "abs");
        steps.set(m.level ?? 3);
        stepMeta.querySelector(".steps-count").textContent = `${m.level ?? 3} de 5`;
        definition.setValue(m.definition ?? 60);
        light.set(m.light || "auto");
        volume.set(Boolean(m.volume));
        gloss.set(Boolean(m.gloss));
        muscleAlert.set(state.panelAlert || "");
        muscleChips.set(state.engineWarnings || []);
      }
      sub.set(state.cuerpo.sub);
      softness.set(state.cuerpo.brush.softness);
      radius.setValue(state.cuerpo.brush.radius);
      intensity.setValue(state.cuerpo.brush.intensity);
      edge.setValue(state.cuerpo.manipulator.edge);
      step.setValue(state.cuerpo.manipulator.step);
      symmetric.set(state.cuerpo.manipulator.symmetric);
      sliders.altura?.setValue(state.cuerpo.altura);
      const fz = state.cuerpo.freeze || {};
      freezeMode.set(fz.mode || "pincel");
      freezeOp.set(fz.op || "add");
      freezeRadiusSl.setValue(fz.radius ?? 20);
      freezeFeatherSl.setValue(fz.feather ?? 30);
      freezeInvert.set(Boolean(fz.invert));
      freezeRadiusSl.el.style.display = fz.mode === "rect" ? "none" : "";
      const man = state.cuerpo.manipulator;
      const aw = Math.round(man.amountW || 0);
      const ah = Math.round(man.amountH || 0);
      manInfo.textContent = `Ancho ${aw > 0 ? "+" : ""}${aw} · Alto ${ah > 0 ? "+" : ""}${ah}  (← adelgaza, → ensancha, ↑ alarga, ↓ acorta; arrastrá la esquina para cambiar el tamaño de la caja)`;
      sliders.waist?.setValue(state.cuerpo.waist);
      sliders.hip?.setValue(state.cuerpo.hip);
      protect.set(state.cuerpo.protectBg);
      const pose = poseIsAvailable(state);
      const parts = bodyParts(state);
      sliders.waist?.setDisabled(!pose || parts.torso === false);
      sliders.hip?.setDisabled(!pose || parts.torso === false);
      grid.querySelectorAll(".tool-card").forEach((card) => {
        if (card.dataset.tool === "auto" || card.dataset.tool === "partes") {
          card.disabled = !pose;
          card.title = pose ? card.querySelector("h3")?.childNodes[0]?.textContent || "" : "Necesita una persona detectada. Usá Adelgazar manual.";
        }
      });

      const arm = state.cuerpo.arm || {};
      const armMode = arm.mode || "manual";
      armProtect.set(armMode === "manual" ? Boolean(arm.protectBg) : Boolean(state.cuerpo.protectBg));
      const noMask = (state.engineWarnings || []).includes("NO_BODY_MASK");
      const armSub = armProtect.el.querySelector("p");
      if (armSub) {
        armSub.textContent = noMask
          ? "No hay máscara de persona: se aplica sin protección"
          : "No deformar lo que no es cuerpo";
      }
      armModes.querySelectorAll("[data-arm-mode]").forEach((btn) => {
        const id = btn.dataset.armMode;
        const autoOff = id !== "manual" && (!pose || parts[id] === false);
        btn.classList.toggle("is-on", id === armMode);
        btn.setAttribute("aria-checked", id === armMode ? "true" : "false");
        btn.setAttribute("aria-disabled", autoOff ? "true" : "false");
        btn.title = autoOff
          ? (pose ? "No detectamos el brazo en la foto. Usá Manual." : "No detectamos una persona. Usá Manual.")
          : "";
        const dot = btn.querySelector(".arm-dot");
        if (dot) dot.hidden = !arm.values?.[id];
      });
      const nFixed = (arm.strokes || []).length;
      const fixedTxt = armMode === "manual"
        ? (nFixed ? ` ${nFixed} trazo${nFixed === 1 ? "" : "s"} fijado${nFixed === 1 ? "" : "s"}: mover el editor ya no los cambia.` : " Al mover el editor, el efecto actual queda fijado.")
        : "";
      armHint.textContent = (pose ? "I / D = lado de la persona." : "Sin persona: usá Manual.") + fixedTxt;

      const showSub = tool === "adelgazar";
      sub.el.style.display = showSub ? "flex" : "none";
      brushBox.style.display = showSub && state.cuerpo.sub === "pincel" ? "flex" : "none";
      manBox.style.display = showSub && state.cuerpo.sub === "manipulador" ? "flex" : "none";
      alturaBox.style.display = tool === "altura" ? "flex" : "none";
      freezeBox.style.display = tool === "congelar" ? "flex" : "none";
      autoBox.style.display = tool === "auto" ? "flex" : "none";
      armBox.style.display = tool === "brazo" ? "flex" : "none";
      protect.el.style.display = drill || tool === "altura" || tool === "brazo" ? "none" : "flex";
    },
  };
}
