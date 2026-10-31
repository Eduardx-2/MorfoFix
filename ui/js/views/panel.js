import { mountRostro } from "./modes/rostro.js";
import { mountCuerpo } from "./modes/cuerpo.js";
import { mountRetoque } from "./modes/retoque.js";
import { mountFoto } from "./modes/foto.js";
import { mountAjustes } from "./modes/ajustes.js";
import { mountEmpty } from "./modes/empty.js";
import { emit } from "../controllers/bus.js";
import { muscleLabel } from "../models/catalog.js";
import { icon } from "./icons.js";

const TITLES = {
  rostro: ["Rostro", {
    cara: "Cara",
    ojos: "Ojos",
    labios: "Labios",
    nariz: "Nariz",
    cejas: "Cejas",
  }],
  cuerpo: ["Cuerpo", {
    adelgazar: "Adelgazar manual",
    altura: "Altura",
    congelar: "Congelar",
    auto: "Auto cintura/cadera",
    brazo: "Brazo",
    partes: "Por partes",
    musculo: "Procedural local: se aplica sobre la piel detectada",
    presets: "Looks locales",
    tatuaje: "Capa local",
  }],
  retoque: ["Retoque", {
    dientes: "Blanquear dientes",
    iluminar: "Iluminar",
    pincel: "Pincel de retoque/quitar",
    maquillaje: "Maquillaje",
    esculpir: "Esculpir",
    tono: "Tono de piel",
    glow: "Glow",
    ojos: "Ojos",
  }],
  foto: ["Foto", {
    recortar: "Recortar / Rotar",
    hsl: "HSL",
    filtros: "Filtros",
    fondo: "Fondo",
    capas: "Capas",
  }],
  ajustes: ["Ajustes", { default: "Preferencias locales" }],
};

const SECONDARY = {
  rostro: "Detectar caras",
  cuerpo: "Limpiar trazo",
  retoque: "Limpiar pincel",
  foto: "Restablecer recorte",
  ajustes: "",
};

export function mountPanel(root) {
  const title = root.querySelector("[data-panel-title]");
  const sub = root.querySelector("[data-panel-sub]");
  const back = root.querySelector("[data-panel-back]");
  const body = root.querySelector(".panel-body");
  const secondary = root.querySelector("[data-secondary]");
  const reset = root.querySelector("[data-reset]");
  back?.addEventListener("click", () => emit("panel-back"));
  if (back && !back.innerHTML) back.innerHTML = `${icon("chevronL")} Cuerpo`;

  const hosts = {
    empty: document.createElement("div"),
    rostro: document.createElement("div"),
    cuerpo: document.createElement("div"),
    retoque: document.createElement("div"),
    foto: document.createElement("div"),
    ajustes: document.createElement("div"),
  };
  for (const el of Object.values(hosts)) {
    el.className = "stack";
    body.append(el);
  }

  const views = {
    empty: mountEmpty(hosts.empty),
    rostro: mountRostro(hosts.rostro),
    cuerpo: mountCuerpo(hosts.cuerpo),
    retoque: mountRetoque(hosts.retoque),
    foto: mountFoto(hosts.foto),
    ajustes: mountAjustes(hosts.ajustes),
  };

  reset.addEventListener("click", () => emit("reset-mode"));
  secondary.addEventListener("click", () => emit("secondary"));

  return {
    sync(state) {
      const mode = state.hasImage ? state.mode : "empty";
      for (const [key, el] of Object.entries(hosts)) {
        el.style.display = key === mode ? "flex" : "none";
      }
      if (mode === "empty") {
        title.textContent = "Sin imagen abierta";
        sub.textContent = "Abrí un JPG, PNG, WEBP o TIFF";
        if (back) back.hidden = true;
        reset.disabled = true;
        secondary.disabled = true;
        secondary.textContent = "—";
        views.empty.sync(state);
        return;
      }
      const [head, map] = TITLES[state.mode];
      const key = state.mode === "rostro" ? state.rostro.tab
        : state.mode === "cuerpo" ? state.cuerpo.tool
        : state.mode === "retoque" ? state.retoque.tool
        : state.mode === "foto" ? state.foto.tool
        : "default";
      const drill = state.mode === "cuerpo" && ["musculo", "partes", "presets", "tatuaje"].includes(key);
      if (back) {
        back.hidden = !drill;
        back.innerHTML = `${icon("chevronL")} ${head} / ${key === "musculo" ? "Músculo" : (map[key] || "")}`;
      }
      title.textContent = drill && key === "musculo" ? "Músculo" : head;
      sub.textContent = key === "musculo"
        ? `${map.musculo} · ${muscleLabel(state.cuerpo.muscle?.mode)}`
        : (map[key] || "");
      reset.disabled = state.mode === "ajustes";
      let label = SECONDARY[state.mode];
      if (state.mode === "cuerpo") {
        const t = state.cuerpo.tool;
        label = t === "congelar" ? "Limpiar congelado"
          : t === "altura" ? "Restablecer líneas"
          : t === "adelgazar" && state.cuerpo.sub === "manipulador" ? "Resetear manipulador"
          : t === "adelgazar" ? "Borrar trazos"
          : t === "musculo" ? ""
          : t === "brazo" ? ""
          : "";
      }
      secondary.disabled = !label;
      secondary.textContent = label || "—";
      views[state.mode]?.sync(state);
    },
  };
}
