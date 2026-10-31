import { icon } from "../icons.js";
import { createSlider } from "../components/slider.js";
import { createSeg } from "../components/seg.js";
import { emit } from "../../controllers/bus.js";

const TABS = [
  { value: "cara", label: "Cara" },
  { value: "ojos", label: "Ojos" },
  { value: "labios", label: "Labios" },
  { value: "nariz", label: "Nariz" },
  { value: "cejas", label: "Cejas" },
];

export function mountRostro(root) {
  const sliders = {};
  const wrap = document.createElement("div");
  wrap.className = "stack";

  const nav = document.createElement("div");
  nav.className = "face-nav";
  nav.innerHTML = `
    <button class="icon-btn" data-act="prev" aria-label="Cara anterior">${icon("chevronL")}</button>
    <span data-face-label>Cara 1 de 1</span>
    <button class="icon-btn" data-act="next" aria-label="Cara siguiente">${icon("chevronR")}</button>
  `;
  nav.addEventListener("click", (event) => {
    const act = event.target.closest("[data-act]")?.dataset.act;
    if (act) emit("face-step", { dir: act === "next" ? 1 : -1 });
  });

  const warn = document.createElement("div");
  warn.className = "warn";
  warn.innerHTML = `${icon("warn")} <span>No se detectó ninguna cara. Los sliders quedan deshabilitados.</span>`;

  const tabs = createSeg({
    items: TABS,
    value: "cara",
    full: true,
    onChange: (value) => emit("rostro-tab", { tab: value }),
  });

  function addSlider(key, opts) {
    sliders[key] = createSlider({
      ...opts,
      onChange: (value) => emit("param", { mode: "rostro", key, value, commit: false }),
      onCommit: (value) => emit("param", { mode: "rostro", key, value, commit: true }),
    });
    return sliders[key];
  }

  const pages = {
    cara: document.createElement("div"),
    ojos: document.createElement("div"),
    labios: document.createElement("div"),
    nariz: document.createElement("div"),
    cejas: document.createElement("div"),
  };
  for (const page of Object.values(pages)) page.className = "stack";

  pages.cara.append(addSlider("jaw", { label: "Mandíbula", scale: true }).el);
  const more = document.createElement("div");
  more.className = "more";
  more.innerHTML = `<button class="more-sum" type="button">Más ajustes ${icon("chevronD")}</button>`;
  const moreBody = document.createElement("div");
  moreBody.className = "more-body";
  moreBody.append(
    addSlider("facewidth", { label: "Ancho de cara", variant: "secondary" }).el,
    addSlider("facev", { label: "Forma en V", variant: "secondary" }).el,
    addSlider("jawline", { label: "Línea de mandíbula", variant: "secondary" }).el,
  );
  more.append(moreBody);
  more.querySelector(".more-sum").addEventListener("click", () => emit("rostro-more"));
  pages.cara.append(more);

  pages.ojos.append(addSlider("eyesize", { label: "Tamaño de ojos", scale: true }).el);
  pages.labios.append(addSlider("mouthsize", { label: "Tamaño de labios", scale: true }).el);
  pages.nariz.append(addSlider("nose", { label: "Ancho de nariz", variant: "secondary" }).el);
  pages.cejas.append(addSlider("brows", { label: "Altura de cejas", variant: "secondary" }).el);

  wrap.append(nav, warn, tabs.el, ...Object.values(pages));
  root.replaceChildren(wrap);

  return {
    sync(state) {
      const n = state.faces.length;
      const i = state.activeFace + 1;
      nav.querySelector("[data-face-label]").textContent = n
        ? `Cara ${i} de ${n}`
        : "Cara 0 de 0";
      warn.style.display = n ? "none" : "flex";
      tabs.set(state.rostro.tab);
      more.classList.toggle("is-open", state.rostro.moreOpen);
      for (const [key, slider] of Object.entries(sliders)) {
        slider.setValue(state.rostro[key]);
        slider.setDisabled(!n);
      }
      for (const [name, page] of Object.entries(pages)) {
        page.style.display = state.rostro.tab === name ? "flex" : "none";
      }
    },
  };
}
