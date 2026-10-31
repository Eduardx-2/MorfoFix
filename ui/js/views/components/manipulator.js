import { emit } from "../../controllers/bus.js";

let drag = null;
let lastBox = { x: 0, y: 0, w: 1, h: 1 };

function boxRef() {
  return lastBox;
}

function ensureDom(root) {
  if (root.querySelector(".manipulator")) return;
  root.innerHTML = `
    <div class="manipulator">
      <button class="m-btn m-l" data-dir="w-" title="Adelgazar">←</button>
      <button class="m-btn m-r" data-dir="w+" title="Ensanchar">→</button>
      <button class="m-btn m-t" data-dir="h-" title="Alargar">↑</button>
      <button class="m-btn m-b" data-dir="h+" title="Acortar">↓</button>
      <button class="m-btn m-c" title="Mover zona"></button>
      <button class="m-btn m-rot" data-dir="rot" title="Rotar">⟳</button>
      <div class="m-size" title="Redimensionar caja"></div>
    </div>
    <div class="canvas-tag" data-manip-tag></div>
  `;
  const el = root.querySelector(".manipulator");
  el.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".m-btn:not(.m-c)")) return;
    e.stopPropagation();
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY, kind: e.target.closest(".m-size") ? "size" : "move" };
    emit("manipulator-drag", { phase: "start", kind: drag.kind });
  });
  el.addEventListener("pointermove", (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    const b = boxRef();
    emit("manipulator-drag", { phase: "move", kind: drag.kind, dx: (e.clientX - drag.x) / b.w, dy: (e.clientY - drag.y) / b.h });
    drag.x = e.clientX;
    drag.y = e.clientY;
  });
  const end = (e) => {
    if (drag && e.pointerId === drag.id) {
      const kind = drag.kind;
      drag = null;
      emit("manipulator-drag", { phase: "end", kind });
    }
  };
  el.addEventListener("pointerup", end);
  el.addEventListener("pointercancel", end);
  el.addEventListener("lostpointercapture", end);
  root.querySelectorAll(".m-btn[data-dir]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      emit("manipulator", { action: btn.dataset.dir });
    });
  });
}

export function renderManipulator(root, state, box) {
  lastBox = box;
  const m = state.cuerpo.manipulator;
  const show = state.hasImage
    && state.mode === "cuerpo"
    && state.cuerpo.tool === "adelgazar"
    && state.cuerpo.sub === "manipulador"
    && state.ajustes.showOverlays;

  if (!show) {
    root.innerHTML = "";
    return;
  }

  ensureDom(root);
  const left = box.x + m.x * box.w;
  const top = box.y + m.y * box.h;
  const w = m.w * box.w;
  const h = m.h * box.h;
  const el = root.querySelector(".manipulator");
  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
  el.style.width = `${w}px`;
  el.style.height = `${h}px`;
  el.style.transform = `rotate(${m.rot}deg)`;
  el.style.transformOrigin = "center";
  el.querySelector(".m-l").classList.toggle("is-on", (m.amountW || 0) < 0);
  el.querySelector(".m-r").classList.toggle("is-on", (m.amountW || 0) > 0);
  el.querySelector(".m-t").classList.toggle("is-on", (m.amountH || 0) > 0);
  el.querySelector(".m-b").classList.toggle("is-on", (m.amountH || 0) < 0);
  const tag = root.querySelector("[data-manip-tag]");
  tag.style.left = `${left + w / 2}px`;
  tag.style.top = `${top}px`;
  // Muestra la intensidad ACUMULADA que se manda al motor (antes mostraba el paso).
  const fmt = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v || 0))}`;
  tag.textContent = `Ancho ${fmt(m.amountW)} · Alto ${fmt(m.amountH)}`;
}
