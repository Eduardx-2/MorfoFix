import { emit } from "../../controllers/bus.js";
import { clamp } from "../../models/utils.js";

function deg(rad) {
  return rad * 180 / Math.PI;
}

function normAngle(a) {
  let n = a;
  while (n > 180) n -= 360;
  while (n < -180) n += 360;
  return n;
}

function localUV(px, py, box, m) {
  const s = Math.min(box.w, box.h);
  const cx = m.cx * box.w;
  const cy = m.cy * box.h;
  const th = (m.angle || 0) * Math.PI / 180;
  const c = Math.cos(th);
  const sn = Math.sin(th);
  const x = px - cx;
  const y = py - cy;
  return {
    u: c * x + sn * y,
    v: -sn * x + c * y,
    s,
    cx,
    cy,
  };
}

export function renderArmManipulator(root, state, box) {
  const show = state.hasImage && state.mode === "cuerpo" && state.cuerpo.tool === "brazo"
    && state.cuerpo.arm?.mode === "manual" && state.ajustes.showOverlays;
  if (!show) {
    root.hidden = true;
    return;
  }
  root.hidden = false;
  const m = state.cuerpo.arm?.manual;
  if (!m) {
    root.hidden = true;
    return;
  }
  const s = Math.min(box.w, box.h);
  const cx = m.cx * box.w;
  const cy = m.cy * box.h;
  const rx = Math.max(m.rx * s, 18);
  const ry = Math.max(m.ry * s, 18);
  const theta = m.angle || 0;
  let svg = root.querySelector("svg.arm-svg");
  if (!svg) {
    root.innerHTML = `
      <svg class="arm-svg">
        <g class="arm-g">
          <line class="arm-axis"/>
          <path class="arm-arc" data-side="-1"/>
          <path class="arm-arc" data-side="1"/>
          <circle class="arm-hit" data-kind="move" r="10" tabindex="0"/>
          <g class="arm-handle" data-kind="len" data-sign="-1"><circle r="14"/><path d="M-5 3 L0 -4 L5 3"/></g>
          <g class="arm-handle" data-kind="len" data-sign="1"><circle r="14"/><path d="M-5 -3 L0 4 L5 -3"/></g>
          <g class="arm-handle" data-kind="width" data-sign="-1"><circle r="14"/><path d="M3 -5 L-4 0 L3 5"/></g>
          <g class="arm-handle" data-kind="width" data-sign="1"><circle r="14"/><path d="M-3 -5 L4 0 L-3 5"/></g>
          <g class="arm-handle" data-kind="rot"><circle r="14"/><path d="M-4 0 A4 4 0 1 1 0 4"/></g>
        </g>
      </svg>`;
    svg = root.querySelector("svg.arm-svg");
    bindArm(svg);
  }
  svg.style.left = `${box.x}px`;
  svg.style.top = `${box.y}px`;
  svg.setAttribute("width", String(box.w));
  svg.setAttribute("height", String(box.h));
  svg.dataset.box = JSON.stringify(box);
  const g = svg.querySelector(".arm-g");
  g.setAttribute("transform", `rotate(${theta}, ${cx}, ${cy})`);
  const axis = g.querySelector(".arm-axis");
  axis.setAttribute("x1", String(cx));
  axis.setAttribute("y1", String(cy - ry));
  axis.setAttribute("x2", String(cx));
  axis.setAttribute("y2", String(cy + ry));
  const a35 = Math.PI / 5;
  g.querySelector('[data-side="-1"]').setAttribute(
    "d",
    `M ${cx - rx} ${cy} A ${rx} ${ry} 0 0 1 ${cx - rx * Math.cos(a35)} ${cy - ry * Math.sin(a35)}`,
  );
  g.querySelector('[data-side="1"]').setAttribute(
    "d",
    `M ${cx + rx} ${cy} A ${rx} ${ry} 0 0 1 ${cx + rx * Math.cos(a35)} ${cy + ry * Math.sin(a35)}`,
  );
  const hit = g.querySelector('[data-kind="move"]');
  hit.setAttribute("cx", String(cx));
  hit.setAttribute("cy", String(cy));
  g.querySelector('[data-kind="len"][data-sign="-1"]').setAttribute("transform", `translate(${cx}, ${cy - ry})`);
  g.querySelector('[data-kind="len"][data-sign="1"]').setAttribute("transform", `translate(${cx}, ${cy + ry})`);
  g.querySelector('[data-kind="width"][data-sign="-1"]').setAttribute("transform", `translate(${cx - rx}, ${cy})`);
  g.querySelector('[data-kind="width"][data-sign="1"]').setAttribute("transform", `translate(${cx + rx}, ${cy})`);
  g.querySelector('[data-kind="rot"]').setAttribute("transform", `translate(${cx + rx * 0.9}, ${cy + ry * 0.55})`);
}

function bindArm(svg) {
  let drag = null;
  let pending = null;
  let raf = 0;

  const toLocal = (event) => {
    const rect = svg.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  svg.addEventListener("pointerdown", (event) => {
    const el = event.target.closest("[data-kind]");
    if (!el) return;
    event.stopPropagation();
    event.preventDefault();
    svg.setPointerCapture(event.pointerId);
    const box = JSON.parse(svg.dataset.box || "{}");
    drag = { id: event.pointerId, kind: el.dataset.kind, box, origin: toLocal(event), shift: event.shiftKey };
    emit("arm-manip", { phase: "start", kind: drag.kind });
  });
  svg.addEventListener("pointermove", (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    pending = { ...drag, pt: toLocal(event), shift: event.shiftKey };
    if (!raf) {
      raf = requestAnimationFrame(() => {
        raf = 0;
        if (!pending) return;
        emit("arm-manip", { phase: "move", kind: pending.kind, pt: pending.pt, origin: pending.origin, box: pending.box, shift: pending.shift });
      });
    }
  });
  const end = (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    const kind = drag.kind;
    drag = null;
    pending = null;
    emit("arm-manip", { phase: "end", kind });
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  svg.querySelector('[data-kind="move"]').addEventListener("keydown", (event) => {
    emit("arm-manip", { phase: "key", key: event.key, shift: event.shiftKey, event });
  });
}

export { deg, normAngle, localUV, clamp };
