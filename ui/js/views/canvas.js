import { containRect } from "../models/utils.js";
import { emit } from "../controllers/bus.js";
import { createSeg } from "./components/seg.js";
import { createToggle } from "./components/toggle.js";
import { renderManipulator } from "./components/manipulator.js";
import {
  brushRadius, freezeRadius, freezeFeather, heightRange, heightDisplayY, heightSourceY, uiRadius,
  muscleRadius, heightMinGap,
} from "../models/params.js";
import { mountMaskToolbar } from "./components/mask-toolbar.js";
import { mountToolSheet } from "./components/tool-sheet.js";
import { muscleLabel } from "../models/catalog.js";
import { renderArmManipulator } from "./components/arm-manipulator.js";

const SVG_NS = "http://www.w3.org/2000/svg";

// Diámetro del cursor en px de pantalla = lo que realmente deforma/congela el motor.
export function brushDiameter(state, box) {
  const short = Math.max(1, Math.min(box.w, box.h));
  if (state.mode === "retoque") {
    return 2 * uiRadius(state.retoque.brush.radius, state.zoom) * Math.max(box.w, box.h);
  }
  if (state.mode === "cuerpo" && state.cuerpo.tool === "congelar") {
    return 2 * freezeRadius(state.cuerpo.freeze?.radius) * short;
  }
  if (state.mode === "cuerpo" && state.cuerpo.tool === "musculo") {
    return 2 * muscleRadius(state.cuerpo.muscle?.radius) * short;
  }
  return 2 * brushRadius(state.cuerpo.brush.radius) * short;
}

function muscleSvg(state, box) {
  const m = state.cuerpo.muscle || {};
  const short = Math.max(1, Math.min(box.w, box.h));
  const strokes = [...(m.strokes || [])];
  if (m.draft?.pts?.length) {
    strokes.push({ pts: m.draft.pts, radius: muscleRadius(m.radius), erase: m.draft.erase });
  }
  const parts = [];
  for (const st of strokes) {
    const color = st.erase ? "black" : "white";
    const r = (st.radius || muscleRadius(40)) * short;
    if (st.pts.length === 1) {
      parts.push(`<circle cx="${st.pts[0][0] * box.w}" cy="${st.pts[0][1] * box.h}" r="${r}" fill="${color}"/>`);
    } else {
      const pts = st.pts.map((p) => `${(p[0] * box.w).toFixed(1)},${(p[1] * box.h).toFixed(1)}`);
      parts.push(`<polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="${2 * r}" stroke-linecap="round" stroke-linejoin="round"/>`);
    }
  }
  return `
    <defs>
      <mask id="ms-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="${box.w}" height="${box.h}">
        <rect x="0" y="0" width="${box.w}" height="${box.h}" fill="black"/>
        ${parts.join("")}
      </mask>
    </defs>
    <rect class="ms-fill" x="0" y="0" width="${box.w}" height="${box.h}" mask="url(#ms-mask)"/>`;
}

function freezeSvg(state, box) {
  const c = state.cuerpo;
  const fz = c.freeze || {};
  const short = Math.max(1, Math.min(box.w, box.h));
  const inv = Boolean(fz.invert);
  const on = inv ? "black" : "white";
  const off = inv ? "white" : "black";
  const strokes = [...(c.freezeStrokes || [])];
  if (c.draftFreeze?.pts?.length) {
    strokes.push({ pts: c.draftFreeze.pts, radius: freezeRadius(fz.radius), erase: c.draftFreeze.erase });
  }
  const rects = [...(c.freezeRects || [])];
  if (c.draftRect) rects.push(c.draftRect);
  const parts = [];
  for (const st of strokes) {
    const color = st.erase ? off : on;
    const r = st.radius * short;
    const pts = st.pts.map((p) => `${(p[0] * box.w).toFixed(1)},${(p[1] * box.h).toFixed(1)}`);
    if (st.pts.length === 1) {
      parts.push(`<circle cx="${st.pts[0][0] * box.w}" cy="${st.pts[0][1] * box.h}" r="${r}" fill="${color}"/>`);
    } else {
      parts.push(`<polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="${2 * r}" stroke-linecap="round" stroke-linejoin="round"/>`);
    }
  }
  for (const r of rects) {
    parts.push(`<rect x="${r.x * box.w}" y="${r.y * box.h}" width="${r.w * box.w}" height="${r.h * box.h}" fill="${r.erase ? off : on}"/>`);
  }
  const blur = freezeFeather(fz.feather) * short / 2;
  const outlines = rects.map((r) => {
    const x = r.x * box.w; const y = r.y * box.h; const w = r.w * box.w; const h = r.h * box.h;
    const corners = [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]
      .map(([cx, cy]) => `<rect class="fz-handle" x="${cx - 5}" y="${cy - 5}" width="10" height="10"/>`).join("");
    return `<rect class="fz-outline${r.erase ? " is-erase" : ""}" x="${x}" y="${y}" width="${w}" height="${h}"/>${fz.mode === "rect" ? corners : ""}`;
  }).join("");
  return `
    <defs>
      <filter id="fz-blur" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${blur.toFixed(2)}"/></filter>
      <mask id="fz-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="${box.w}" height="${box.h}">
        <rect x="0" y="0" width="${box.w}" height="${box.h}" fill="${off}"/>
        <g ${blur > 0.3 ? 'filter="url(#fz-blur)"' : ""}>${parts.join("")}</g>
      </mask>
    </defs>
    <rect class="fz-fill" x="0" y="0" width="${box.w}" height="${box.h}" mask="url(#fz-mask)"/>
    ${outlines}`;
}

const HINTS = {
  rostro: `Espacio mano · <kbd>\\</kbd> antes/después · sliders ±1 / Shift ±10`,
  cuerpo: `<kbd>[</kbd> <kbd>]</kbd> radio · <kbd>F</kbd> congelar · <kbd>Alt</kbd>+arrastrar resta`,
  retoque: `Arrastrá el pincel sobre la zona · <kbd>[</kbd> <kbd>]</kbd> radio`,
  foto: `Ctrl + rueda zoom · arrastrá para recortar`,
  ajustes: `Todo corre en local, sin conexión`,
};

export function mountCanvas(root) {
  const canvas = root.querySelector(".canvas");
  const stage = root.querySelector(".stage");
  const imgAfter = root.querySelector(".photo-after");
  const imgBefore = root.querySelector(".photo-before");
  const overlays = root.querySelector(".overlays");
  const freezeEl = root.querySelector("[data-freeze]");
  const manipRoot = root.querySelector("[data-manip]");
  const badgeRoot = root.querySelector("[data-badges]");
  const tagEl = root.querySelector("[data-tag]");
  const splitBar = root.querySelector(".split-bar");
  const hint = root.querySelector(".hint");
  const brush = root.querySelector(".brush-cursor");
  const dropzone = root.querySelector(".dropzone");
  const toolbarHost = root.querySelector("[data-toolbar]");
  const extraHost = root.querySelector("[data-toolbar-extra]");
  const maskHost = root.querySelector("[data-mask-tb]");
  const maskTb = maskHost ? mountMaskToolbar(maskHost) : null;
  const sheetHost = root.querySelector("[data-tool-sheet]");
  const sheet = sheetHost ? mountToolSheet(sheetHost) : null;
  const armRoot = document.createElement("div");
  overlays.append(armRoot);

  // Overlay de congelado (máscara real: trazos + rects + borrar + invertir + feather).
  const freezeLayer = document.createElementNS(SVG_NS, "svg");
  freezeLayer.classList.add("freeze-svg");
  overlays.prepend(freezeLayer);
  const muscleLayer = document.createElementNS(SVG_NS, "svg");
  muscleLayer.classList.add("muscle-svg");
  overlays.prepend(muscleLayer);
  const heightLayer = document.createElementNS(SVG_NS, "svg");
  heightLayer.classList.add("height-svg");
  overlays.prepend(heightLayer);
  let lastState = null;
  let hDrag = null;
  let hPending = null;
  let hRaf = 0;

  function heightToSrc(clientY) {
    const box = imageBox();
    const rect = canvas.getBoundingClientRect();
    const yDisp = Math.min(1, Math.max(0, (clientY - rect.top - box.y) / Math.max(1, box.h)));
    const s = lastState;
    const range = heightRange(s.cuerpo.heightLines, heightMinGap(box.h));
    return heightSourceY(yDisp, range, shownHeightValue(range, s.cuerpo.altura));
  }

  function ensureHeightSvg() {
    if (heightLayer.dataset.ready) return;
    heightLayer.innerHTML = `
      <rect class="h-band" hidden="true"/>
      ${[0, 1].map((i) => `
        <g class="h-line" data-i="${i}" tabindex="0" role="slider" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
          <line class="h-stroke"/>
          <rect class="h-hit"/>
          <g class="h-handle">
            <circle r="15"/>
            <path d="M-5 -3 L0 -8 L5 -3"/>
            <path d="M-5 3 L0 8 L5 3"/>
          </g>
        </g>`).join("")}`;
    heightLayer.dataset.ready = "1";
  }

  heightLayer.addEventListener("pointerdown", (event) => {
    const g = event.target.closest(".h-line");
    if (!g || !lastState) return;
    event.stopPropagation();
    event.preventDefault();
    heightLayer.setPointerCapture(event.pointerId);
    hDrag = { id: event.pointerId, index: Number(g.dataset.i) };
    emit("height-line", { index: hDrag.index, commit: "start", gap: heightMinGap(imageBox().h) });
  });
  heightLayer.addEventListener("pointermove", (event) => {
    if (!hDrag || hDrag.id !== event.pointerId || !lastState) return;
    hPending = { index: hDrag.index, clientY: event.clientY };
    if (!hRaf) {
      hRaf = requestAnimationFrame(() => {
        hRaf = 0;
        if (!hPending || !lastState) return;
        const box = imageBox();
        emit("height-line", {
          index: hPending.index,
          value: heightToSrc(hPending.clientY),
          commit: false,
          gap: heightMinGap(box.h),
        });
      });
    }
  });
  const endHeight = (event) => {
    if (!hDrag || hDrag.id !== event.pointerId) return;
    const index = hDrag.index;
    hDrag = null;
    hPending = null;
    if (lastState) {
      emit("height-line", {
        index,
        value: heightToSrc(event.clientY),
        commit: true,
        gap: heightMinGap(imageBox().h),
      });
    }
  };
  heightLayer.addEventListener("pointerup", endHeight);
  heightLayer.addEventListener("pointercancel", endHeight);
  heightLayer.addEventListener("keydown", (event) => {
    const g = event.target.closest(".h-line");
    if (!g || !lastState) return;
    const step = event.shiftKey ? 0.05 : 0.005;
    const i = Number(g.dataset.i);
    const lines = [...(lastState.cuerpo.heightLines || [0.48, 0.92])];
    if (event.key === "ArrowUp") lines[i] -= step;
    else if (event.key === "ArrowDown") lines[i] += step;
    else return;
    event.preventDefault();
    emit("height-line", { index: i, value: lines[i], commit: false, gap: heightMinGap(imageBox().h) });
  });
  heightLayer.addEventListener("keyup", (event) => {
    const g = event.target.closest(".h-line");
    if (!g) return;
    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      emit("height-line", { index: Number(g.dataset.i), commit: true, gap: heightMinGap(imageBox().h) });
    }
  });

  const viewSeg = createSeg({
    items: [
      { value: "antes", label: "Antes" },
      { value: "despues", label: "Después" },
      { value: "dividido", label: "Dividido" },
    ],
    value: "despues",
    onChange: (value) => emit("view", { view: value }),
  });
  toolbarHost.prepend(viewSeg.el);

  const protect = createToggle({
    on: true,
    onChange: (value) => emit("protect-bg", { value }),
  });
  root.querySelector("[data-protect-toggle]").replaceWith(protect.el);
  protect.el.dataset.protectToggle = "";

  const drop = (on) => dropzone.classList.toggle("is-over", on);
  canvas.addEventListener("dragover", (event) => {
    event.preventDefault();
    drop(true);
  });
  canvas.addEventListener("dragleave", () => drop(false));
  canvas.addEventListener("drop", (event) => {
    event.preventDefault();
    drop(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) emit("open-file", { file });
  });
  dropzone.querySelector("[data-open]")?.addEventListener("click", () => emit("open"));

  splitBar.addEventListener("pointerdown", (event) => {
    splitBar.setPointerCapture(event.pointerId);
  });
  splitBar.addEventListener("pointermove", (event) => {
    if (!splitBar.hasPointerCapture(event.pointerId)) return;
    const rect = canvas.getBoundingClientRect();
    emit("split", { value: ((event.clientX - rect.left) / rect.width) * 100 });
  });

  canvas.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".toolbar, .hint, .protect-float, .split-bar, .m-btn, .face-badge, .manipulator, .h-line, .mask-tb, .tool-sheet, .height-svg, .arm-svg")) return;
    // Captura: el trazo se cierra aunque el mouse se suelte fuera del lienzo.
    try { canvas.setPointerCapture(event.pointerId); } catch { /* sin captura */ }
    emit("canvas-down", { event });
  });
  canvas.addEventListener("pointermove", (event) => {
    const rect = canvas.getBoundingClientRect();
    emit("canvas-move", {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
      event,
    });
  });
  canvas.addEventListener("pointerup", (event) => emit("canvas-up", { event }));
  canvas.addEventListener("wheel", (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    emit("zoom", { delta: event.deltaY > 0 ? -10 : 10 });
  }, { passive: false });

  // Al llegar una preview nueva cambia el tamaño mostrado (p.ej. Altura agranda el lienzo):
  // re-sincronizamos los overlays con la caja real de la imagen.
  imgAfter.addEventListener("load", () => { if (lastState) api.sync(lastState); });
  imgBefore.addEventListener("load", () => { if (lastState) api.sync(lastState); });

  function shownHeightValue(range, altura) {
    const aw = imgAfter.naturalWidth; const ah = imgAfter.naturalHeight;
    const bw = imgBefore.naturalWidth; const bh = imgBefore.naturalHeight;
    if (aw > 1 && bw > 1 && range[1] - range[0] > 0.001) {
      const total = (ah / aw) / (bh / bw);
      return Math.max(-1, Math.min(1, (total - 1) / (range[1] - range[0]) / 0.3));
    }
    return (altura || 0) / 100;
  }

  function imageBox() {
    const canvasRect = canvas.getBoundingClientRect();
    const imgRect = imgAfter.getBoundingClientRect();
    if (imgRect.width > 1) {
      return {
        x: imgRect.left - canvasRect.left,
        y: imgRect.top - canvasRect.top,
        w: imgRect.width,
        h: imgRect.height,
      };
    }
    return containRect(canvasRect.width, canvasRect.height, imgAfter.naturalWidth || 1, imgAfter.naturalHeight || 1);
  }

  const api = {
    sync(state) {
      lastState = state;
      viewSeg.set(state.view);
      protect.set(state.cuerpo.protectBg);
      hint.style.display = state.hasImage && state.ajustes.showShortcuts ? "flex" : "none";
      hint.innerHTML = state.mode === "cuerpo" && state.cuerpo.tool === "musculo"
        ? `Pintá para sumar zona · <kbd>Alt</kbd> borrar · <kbd>[</kbd> <kbd>]</kbd> tamaño · <kbd>M</kbd> máscara`
        : (HINTS[state.mode] || HINTS.rostro);
      maskTb?.sync(state);
      const tool = state.cuerpo?.tool;
      sheet?.sync(state, {
        on: state.hasImage && state.mode === "cuerpo" && (tool === "altura" || tool === "brazo"),
        title: tool === "brazo" ? "Brazo" : "Altura",
        key: tool === "brazo" ? "armValue" : "altura",
        value: tool === "brazo"
          ? (state.cuerpo.arm?.values?.[state.cuerpo.arm?.mode] ?? 0)
          : (state.cuerpo.altura ?? 0),
        help: tool === "brazo"
          ? "Manual: mové el punto para ubicar la zona, estirá con ⌃ ⌄, ensanchá con ‹ › y girá con ⟳. El slider adelgaza o ensancha solo dentro de esa zona."
          : "Arrastrá las dos líneas para elegir la zona que se estira. Solo cambia lo que queda entre las líneas.",
      });
      extraHost.innerHTML = "";

      if (state.hasImage) {
        if (imgAfter.src !== state.previewUrl) imgAfter.src = state.previewUrl;
        if (imgBefore.src !== state.originalUrl) imgBefore.src = state.originalUrl;
        const z = state.zoom / 100;
        stage.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${z})`;
      }

      const pct = state.split;
      splitBar.style.left = `${pct}%`;
      imgBefore.style.clipPath = state.view === "dividido"
        ? `inset(0 ${100 - pct}% 0 0)`
        : "";

      canvas.classList.toggle("is-panning", state.spaceDown);
      canvas.classList.toggle("is-drag", state.panning);

      const box = imageBox();
      badgeRoot.innerHTML = "";
      if (state.hasImage && state.mode === "cuerpo" && state.cuerpo.tool === "musculo") {
        const badge = document.createElement("div");
        badge.className = "face-badge is-on";
        badge.style.left = `${box.x + box.w / 2}px`;
        badge.style.top = `${box.y + 18}px`;
        const n = (state.cuerpo.muscle?.person ?? 0) + 1;
        badge.innerHTML = `<span class="chip">${n}</span> Persona ${n}`;
        badgeRoot.append(badge);
        if ((state.cuerpo.muscle?.strokes || []).length || state.cuerpo.muscle?.draft) {
          const tag = document.createElement("div");
          tag.className = "mask-chip";
          tag.style.left = `${box.x + box.w * 0.32}px`;
          tag.style.top = `${box.y + box.h * 0.38}px`;
          tag.textContent = `Máscara · ${muscleLabel(state.cuerpo.muscle?.mode)}`;
          badgeRoot.append(tag);
        }
      }
      if (state.hasImage && state.mode === "rostro" && state.ajustes.showOverlays) {
        state.faces.forEach((face, i) => {
          const badge = document.createElement("button");
          badge.type = "button";
          badge.className = `face-badge${i === state.activeFace ? " is-on" : ""}`;
          badge.style.left = `${box.x + (face.x + face.w / 2) * box.w}px`;
          badge.style.top = `${box.y + face.y * box.h}px`;
          badge.innerHTML = `<span class="chip">${i + 1}</span> Cara ${i + 1}`;
          badge.addEventListener("click", () => emit("face-select", { index: i }));
          badgeRoot.append(badge);
        });
      }

      const crop = state.foto.crop;
      const cropOn = state.hasImage && state.mode === "foto" && state.foto.tool === "recortar"
        && Array.isArray(crop) && (crop[0] > 0.001 || crop[1] > 0.001 || crop[2] < 0.999 || crop[3] < 0.999);
      if (cropOn && state.ajustes.showOverlays) {
        freezeEl.style.display = "block";
        freezeEl.style.left = `${box.x + crop[0] * box.w}px`;
        freezeEl.style.top = `${box.y + crop[1] * box.h}px`;
        freezeEl.style.width = `${Math.max(4, (crop[2] - crop[0]) * box.w)}px`;
        freezeEl.style.height = `${Math.max(4, (crop[3] - crop[1]) * box.h)}px`;
        tagEl.style.display = "flex";
        tagEl.style.left = `${box.x + ((crop[0] + crop[2]) / 2) * box.w}px`;
        tagEl.style.top = `${box.y + crop[1] * box.h}px`;
        tagEl.textContent = "Recorte";
      } else {
        freezeEl.style.display = "none";
        if (state.mode !== "cuerpo" || state.cuerpo.sub !== "manipulador") {
          tagEl.style.display = "none";
        }
      }

      renderManipulator(manipRoot, state, box);
      renderArmManipulator(armRoot, state, box);

      const c = state.cuerpo;
      const showFreeze = state.hasImage && state.mode === "cuerpo" && c.tool === "congelar"
        && state.ajustes.showOverlays
        && ((c.freezeStrokes || []).length || (c.freezeRects || []).length || c.draftFreeze || c.draftRect || c.freeze?.invert);
      if (showFreeze) {
        freezeLayer.style.display = "block";
        freezeLayer.style.left = `${box.x}px`;
        freezeLayer.style.top = `${box.y}px`;
        freezeLayer.setAttribute("width", String(box.w));
        freezeLayer.setAttribute("height", String(box.h));
        freezeLayer.innerHTML = freezeSvg(state, box);
      } else {
        freezeLayer.style.display = "none";
        freezeLayer.innerHTML = "";
      }

      const showMuscleMask = state.hasImage && state.mode === "cuerpo" && c.tool === "musculo"
        && state.ajustes.showOverlays
        && (c.muscle?.showMask || (c.muscle?.strokes || []).length || c.muscle?.draft);
      if (showMuscleMask) {
        muscleLayer.style.display = "block";
        muscleLayer.style.left = `${box.x}px`;
        muscleLayer.style.top = `${box.y}px`;
        muscleLayer.setAttribute("width", String(box.w));
        muscleLayer.setAttribute("height", String(box.h));
        muscleLayer.innerHTML = muscleSvg(state, box);
      } else {
        muscleLayer.style.display = "none";
        muscleLayer.innerHTML = "";
      }

      const showLines = state.hasImage && state.mode === "cuerpo" && c.tool === "altura" && state.ajustes.showOverlays;
      if (showLines) {
        ensureHeightSvg();
        const range = heightRange(c.heightLines, heightMinGap(box.h));
        const v = shownHeightValue(range, c.altura);
        const y0 = heightDisplayY(range[0], range, v) * box.h;
        const y1 = heightDisplayY(range[1], range, v) * box.h;
        heightLayer.style.display = "block";
        heightLayer.style.left = `${box.x}px`;
        heightLayer.style.top = `${box.y}px`;
        heightLayer.setAttribute("width", String(box.w));
        heightLayer.setAttribute("height", String(box.h));
        const band = heightLayer.querySelector(".h-band");
        if (hDrag) {
          band.removeAttribute("hidden");
          band.setAttribute("x", "0");
          band.setAttribute("y", String(Math.min(y0, y1)));
          band.setAttribute("width", String(box.w));
          band.setAttribute("height", String(Math.abs(y1 - y0)));
        } else {
          band.setAttribute("hidden", "true");
        }
        [y0, y1].forEach((y, i) => {
          const g = heightLayer.querySelector(`.h-line[data-i="${i}"]`);
          const line = g.querySelector(".h-stroke");
          const hit = g.querySelector(".h-hit");
          const handle = g.querySelector(".h-handle");
          line.setAttribute("x1", "0");
          line.setAttribute("y1", String(y));
          line.setAttribute("x2", String(box.w));
          line.setAttribute("y2", String(y));
          hit.setAttribute("x", "0");
          hit.setAttribute("y", String(y - 12));
          hit.setAttribute("width", String(box.w));
          hit.setAttribute("height", "24");
          handle.setAttribute("transform", `translate(${box.w / 2}, ${y})`);
          g.setAttribute("aria-valuenow", String(Math.round((i ? range[1] : range[0]) * 100)));
        });
      } else {
        heightLayer.style.display = "none";
      }

      const brushOn = state.cursor === "brush";
      brush.style.display = brushOn ? "block" : "none";
      const d = brushDiameter(state, box);
      brush.style.width = `${Math.max(8, d)}px`;
      brush.style.height = `${Math.max(8, d)}px`;
    },
    moveBrush(x, y, state) {
      const d = state ? brushDiameter(state, imageBox()) : 8;
      brush.style.left = `${x}px`;
      brush.style.top = `${y}px`;
      brush.style.width = `${Math.max(8, d)}px`;
      brush.style.height = `${Math.max(8, d)}px`;
      brush.style.transform = "translate(-50%, -50%)";
    },
    imageBox,
  };
  return api;
}
