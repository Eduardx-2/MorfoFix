import { on } from "../bus.js";
import { clamp } from "../../models/utils.js";
import { api } from "../../models/api.js";
import { HEIGHT_MIN_GAP, ARM_MAX_STROKES, commitArmStroke, defaultArm, poseIsAvailable, bodyParts, manipulatorShapes } from "../../models/params.js";

function clone(v) {
  return JSON.parse(JSON.stringify(v));
}

function armFromBbox(state) {
  const b = (state.bodies || [])[0]?.bbox;
  if (Array.isArray(b) && b.length === 4) {
    return {
      cx: clamp((b[0] + b[2]) / 2 - (b[2] - b[0]) * 0.18, 0, 1),
      cy: clamp(b[1] + (b[3] - b[1]) * 0.32, 0, 1),
      rx: 0.06,
      ry: 0.14,
      angle: -12,
    };
  }
  return { cx: 0.5, cy: 0.45, rx: 0.06, ry: 0.14, angle: 0 };
}

export function bindCuerpo(store, sendParams) {
  let toolSnap = null;
  let armAngle0 = 0;
  let armPtr0 = null;

  // Patrón "trazos fijados" (doc 23): antes de mover/rotar/escalar un editor que ya tiene
  // efecto, ese efecto se fija en la lista y el editor vuelve a 0. Así mover no arrastra lo aplicado.
  function fixArmStroke(label = "Fijar trazo de brazo") {
    const arm = store.get().cuerpo.arm;
    if (!arm?.values?.manual) return false;
    const next = commitArmStroke(arm);
    if (!next) {
      store.patch({ toast: `Llegaste al límite de ${ARM_MAX_STROKES} trazos de brazo. Deshacé o borrá alguno.` });
      return false;
    }
    store.patchMode("cuerpo", { arm: next });
    sendParams(true, label);
    return true;
  }
  function fixManipShape() {
    const c = store.get().cuerpo;
    const active = manipulatorShapes(c);
    if (!active.length) return false;
    const stack = [...(c.manipStack || []), ...active];
    if (stack.length > 64) {
      store.patch({ toast: "Llegaste al límite de formas del manipulador. Deshacé o reseteá." });
      return false;
    }
    store.patchMode("cuerpo", { manipStack: stack, manipulator: { ...c.manipulator, amountW: 0, amountH: 0, dir: "" } });
    sendParams(true, "Fijar manipulador");
    return true;
  }

  on("cuerpo-tool", ({ tool }) => {
    const s = store.get();
    const cursor = tool === "adelgazar" && s.cuerpo.sub === "pincel" ? "brush"
      : tool === "congelar" ? (s.cuerpo.freeze?.mode === "rect" ? "default" : "brush")
      : tool === "musculo" ? "brush"
      : "default";
    store.patchMode("cuerpo", { tool });
    store.patch({ cursor, panelAlert: "" });
    const c = store.get().cuerpo;
    if (tool === "altura") {
      toolSnap = { altura: c.altura, heightLines: [...(c.heightLines || [0.48, 0.92])] };
    } else if (tool === "brazo") {
      const pose = poseIsAvailable(store.get());
      const parts = bodyParts(store.get());
      const arm = { ...defaultArm(), ...(c.arm || {}) };
      if (!pose || (arm.mode !== "manual" && parts[arm.mode] === false)) arm.mode = "manual";
      if (arm.mode === "manual" && !arm.touched) arm.manual = armFromBbox(store.get());
      store.patchMode("cuerpo", { arm });
      toolSnap = { arm: clone(arm) };
    } else {
      toolSnap = null;
    }
    if (tool === "musculo" && !c.muscle?.enabled) {
      c.muscle = { ...(c.muscle || {}), enabled: true };
    }
    if (tool === "musculo" || tool === "brazo") {
      const apply = () => { if (tool === "musculo") sendParams(true, "Músculo"); };
      if (api.isTauri()) {
        api.detect().then((resp) => {
          if (resp?.bodies) {
            store.patch({
              bodies: resp.bodies,
              poseAvailable: Boolean(resp.pose_available ?? resp.bodies.length),
            });
          }
          apply();
        }).catch(apply);
      } else apply();
    }
  });
  on("panel-back", () => {
    if (store.get().mode !== "cuerpo") return;
    store.patchMode("cuerpo", { tool: "adelgazar" });
    store.patch({ cursor: store.get().cuerpo.sub === "pincel" ? "brush" : "default", panelAlert: "" });
  });
  on("muscle-field", ({ key, value, commit }) => {
    const c = store.get().cuerpo;
    if (commit) store.pushHistory();
    c.muscle = { ...(c.muscle || {}), [key]: value, enabled: true };
    store.state.dirty = true;
    store.emit();
    sendParams(Boolean(commit), "Músculo");
  });
  on("muscle-mask", ({ key, value, toggle, commit }) => {
    const c = store.get().cuerpo;
    const m = { ...(c.muscle || {}), enabled: true };
    if (key === "clear") {
      store.pushHistory();
      m.strokes = [];
      m.draft = null;
      c.muscle = m;
      store.state.dirty = true;
      store.emit();
      sendParams(true, "Limpiar máscara");
      return;
    }
    if (key === "invert") {
      store.pushHistory();
      m.strokes = (m.strokes || []).map((s) => ({ ...s, erase: !s.erase }));
      c.muscle = m;
      store.state.dirty = true;
      store.emit();
      sendParams(true, "Invertir máscara");
      return;
    }
    if (key === "showMask") {
      m.showMask = toggle ? !m.showMask : Boolean(value);
      c.muscle = m;
      store.emit();
      sendParams(false);
      return;
    }
    if (commit) store.pushHistory();
    m[key] = value;
    c.muscle = m;
    store.state.dirty = true;
    store.emit();
    if (key !== "op" && key !== "radius") sendParams(Boolean(commit));
    else if (key === "radius" && commit) store.emit();
  });
  on("cuerpo-sub", ({ sub }) => {
    store.patchMode("cuerpo", { sub });
    store.patch({ cursor: sub === "pincel" ? "brush" : "default" });
    // El overlay del manipulador aparece: re-render para que preview y overlay coincidan.
    sendParams(false);
  });
  on("freeze-field", ({ key, value, commit }) => {
    const c = store.get().cuerpo;
    if (commit) store.pushHistory();
    c.freeze = { ...(c.freeze || {}), [key]: value };
    store.state.dirty = true;
    if (key === "mode") store.state.cursor = value === "rect" ? "default" : "brush";
    store.emit();
    // radio/modo/operación solo afectan trazos nuevos; invertir y feather re-renderizan.
    if (key === "invert" || key === "feather") sendParams(Boolean(commit), "Congelar");
  });
  on("height-line", ({ index, value, commit, gap }) => {
    const c = store.get().cuerpo;
    if (commit === "start") {
      store.pushHistory();
      return;
    }
    const minGap = gap || HEIGHT_MIN_GAP;
    const lines = [...(c.heightLines || [0.48, 0.92])];
    if (value !== undefined) {
      if (index === 0) lines[0] = clamp(value, 0, lines[1] - minGap);
      else lines[1] = clamp(value, lines[0] + minGap, 1);
    }
    store.patchMode("cuerpo", { heightLines: lines });
    if (commit) sendParams(true, "Línea de altura");
    else if (c.altura) sendParams(false, "Línea de altura", { ms: 60 });
  });
  on("tool-sheet", ({ action }) => {
    const s = store.get();
    const tool = s.cuerpo.tool;
    if (tool !== "altura" && tool !== "brazo") return;
    if (action === "cancel") {
      if (tool === "altura" && toolSnap) {
        store.patchMode("cuerpo", { altura: toolSnap.altura, heightLines: toolSnap.heightLines, tool: "adelgazar" });
        sendParams(true, "Cancelar altura");
      } else if (tool === "brazo" && toolSnap?.arm) {
        store.patchMode("cuerpo", { arm: toolSnap.arm, tool: "adelgazar" });
        sendParams(true, "Cancelar brazo");
      } else {
        store.patchMode("cuerpo", { tool: "adelgazar" });
      }
      store.patch({ cursor: "default" });
      toolSnap = null;
      return;
    }
    if (action === "apply") {
      let changed = true;
      if (tool === "altura" && toolSnap) {
        const lines = s.cuerpo.heightLines || [];
        changed = s.cuerpo.altura !== toolSnap.altura
          || lines[0] !== toolSnap.heightLines[0]
          || lines[1] !== toolSnap.heightLines[1];
      } else if (tool === "brazo" && toolSnap?.arm) {
        // ✓ fija el trazo activo (slider a 0) antes de cerrar.
        const next = commitArmStroke(s.cuerpo.arm);
        if (next) store.patchMode("cuerpo", { arm: next });
        changed = JSON.stringify(store.get().cuerpo.arm) !== JSON.stringify(toolSnap.arm);
      }
      store.patchMode("cuerpo", { tool: "adelgazar" });
      store.patch({ cursor: "default" });
      if (changed) sendParams(true, tool === "brazo" ? "Brazo" : "Altura");
      toolSnap = null;
    }
  });
  on("arm-mode", ({ mode }) => {
    const c = store.get().cuerpo;
    const arm = { ...defaultArm(), ...(c.arm || {}), mode };
    if (mode === "manual" && !arm.touched) arm.manual = armFromBbox(store.get());
    store.patchMode("cuerpo", { arm });
    sendParams(false);
  });
  on("arm-protect", ({ value }) => {
    const c = store.get().cuerpo;
    const arm = { ...defaultArm(), ...(c.arm || {}) };
    if (arm.mode === "manual") {
      arm.protectBg = Boolean(value);
      arm.touched = true;
      store.patchMode("cuerpo", { arm });
    } else {
      store.patchMode("cuerpo", { protectBg: Boolean(value) });
    }
    sendParams(true, "Fondo");
  });
  on("arm-manip", ({ phase, kind, pt, origin, box, shift, key, event }) => {
    const c = store.get().cuerpo;
    const arm = { ...defaultArm(), ...(c.arm || {}) };
    const m = { ...arm.manual };
    const s = Math.min(box?.w || 1, box?.h || 1);
    if (phase === "start") {
      store.pushHistory();
      fixArmStroke();
      armAngle0 = m.angle || 0;
      armPtr0 = null;
      return;
    }
    if (phase === "key") {
      if (event) event.preventDefault();
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "[", "]", "+", "=", "-"].includes(key) && fixArmStroke()) {
        Object.assign(arm, store.get().cuerpo.arm);
      }
      const step = shift ? 0.05 : 0.005;
      if (key === "ArrowLeft") m.cx -= step;
      else if (key === "ArrowRight") m.cx += step;
      else if (key === "ArrowUp") m.cy -= step;
      else if (key === "ArrowDown") m.cy += step;
      else if (key === "[") m.angle -= 5;
      else if (key === "]") m.angle += 5;
      else if (key === "+" || key === "=") { m.rx *= 1.05; m.ry *= 1.05; }
      else if (key === "-") { m.rx *= 0.95; m.ry *= 0.95; }
      else return;
      m.cx = clamp(m.cx, 0, 1);
      m.cy = clamp(m.cy, 0, 1);
      m.rx = clamp(m.rx, 0.01, 0.5);
      m.ry = clamp(m.ry, 0.01, 0.5);
      m.angle = ((m.angle + 180) % 360 + 360) % 360 - 180;
      arm.manual = m;
      arm.touched = true;
      store.patchMode("cuerpo", { arm });
      if (arm.values.manual) sendParams(false, "Brazo manual", { ms: 60 });
      return;
    }
    if (phase === "move" && pt && origin && box) {
      const minRx = Math.max(0.01, 18 / s);
      const minRy = Math.max(0.01, 18 / s);
      if (kind === "move") {
        m.cx = clamp(m.cx + (pt.x - origin.x) / box.w, 0, 1);
        m.cy = clamp(m.cy + (pt.y - origin.y) / box.h, 0, 1);
        origin.x = pt.x;
        origin.y = pt.y;
      } else if (kind === "len") {
        const th = (m.angle || 0) * Math.PI / 180;
        const cth = Math.cos(th);
        const sth = Math.sin(th);
        const vx = pt.x - m.cx * box.w;
        const vy = pt.y - m.cy * box.h;
        const v = -sth * vx + cth * vy;
        m.ry = clamp(Math.abs(v) / s, minRy, 0.5);
      } else if (kind === "width") {
        const th = (m.angle || 0) * Math.PI / 180;
        const cth = Math.cos(th);
        const sth = Math.sin(th);
        const vx = pt.x - m.cx * box.w;
        const vy = pt.y - m.cy * box.h;
        const u = cth * vx + sth * vy;
        m.rx = clamp(Math.abs(u) / s, minRx, 0.5);
      } else if (kind === "rot") {
        const cx = m.cx * box.w;
        const cy = m.cy * box.h;
        const angNow = Math.atan2(pt.y - cy, pt.x - cx);
        if (armPtr0 == null) armPtr0 = angNow;
        let ang = armAngle0 + (angNow - armPtr0) * 180 / Math.PI;
        if (shift) ang = Math.round(ang / 15) * 15;
        while (ang > 180) ang -= 360;
        while (ang < -180) ang += 360;
        m.angle = ang;
      }
      arm.manual = m;
      arm.touched = true;
      store.patchMode("cuerpo", { arm });
      if (arm.values.manual) sendParams(false, "Brazo manual", { ms: 60 });
      return;
    }
    if (phase === "end") {
      // Con el slider en 0 mover el editor no cambia la foto: no se crea un paso de historial vacío.
      if (store.get().cuerpo.arm?.values?.manual) sendParams(true, "Brazo manual");
    }
  });
  on("cuerpo-soft", ({ softness }) => {
    store.get().cuerpo.brush.softness = softness;
    store.emit();
    sendParams(true);
  });
  on("brush", ({ key, value, commit }) => {
    if (commit) store.pushHistory();
    store.get().cuerpo.brush[key] = clamp(value, 0, 100);
    store.state.dirty = true;
    store.emit();
    sendParams(commit);
  });
  on("protect-bg", ({ value }) => {
    store.patchMode("cuerpo", { protectBg: value });
    if (value && api.isTauri()) api.detect().catch(() => {});
    sendParams(true, "Fondo");
  });
  on("manip-field", ({ key, value, commit }) => {
    if (commit) store.pushHistory();
    store.get().cuerpo.manipulator[key] = value;
    store.state.dirty = true;
    store.emit();
    sendParams(Boolean(commit));
  });
  on("manipulator-drag", ({ phase, kind = "move", dx = 0, dy = 0 }) => {
    if (phase === "start") {
      store.pushHistory();
      fixManipShape();
      return;
    }
    const m = store.get().cuerpo.manipulator;
    if (phase === "move") {
      if (kind === "size") {
        // Esquina inferior derecha: redimensiona la caja (la intensidad no cambia).
        m.w = clamp(m.w + dx, 0.04, 1 - m.x);
        m.h = clamp(m.h + dy, 0.04, 1 - m.y);
      } else {
        m.x = clamp(m.x + dx, 0, 1 - m.w);
        m.y = clamp(m.y + dy, 0, 1 - m.h);
      }
      store.state.dirty = true;
      store.emit();
      sendParams(false);
      return;
    }
    if (phase === "end" && manipulatorShapes(store.get().cuerpo).length) {
      sendParams(true, kind === "size" ? "Redimensionar manipulador" : "Mover manipulador");
    }
  });
  on("manipulator", ({ action }) => {
    if (action === "move") return;
    const m = store.get().cuerpo.manipulator;
    const step = m.step || 10;
    store.pushHistory();
    // Las flechas ACUMULAN intensidad (antes cambiaban el tamaño de la caja y el
    // valor enviado quedaba fijo en ±0.08 → la foto no cambiaba).
    if (action === "w+" || action === "w-") {
      m.dir = action;
      m.amountW = clamp((m.amountW || 0) + (action === "w+" ? step : -step), -100, 100);
    } else if (action === "h+" || action === "h-") {
      // ↑ (h-) alarga, ↓ (h+) acorta.
      m.dir = action;
      m.amountH = clamp((m.amountH || 0) + (action === "h-" ? step : -step), -100, 100);
    } else if (action === "rot") {
      m.rot = (m.rot + 8) % 360;
    }
    store.state.dirty = true;
    store.emit();
    sendParams(true, "Manipulador");
  });
  on("param", ({ mode, key, value, commit, sheet }) => {
    if (mode !== "cuerpo") return;
    if (key === "armValue") {
      const c = store.get().cuerpo;
      const arm = { ...defaultArm(), ...(c.arm || {}) };
      const slot = arm.mode || "manual";
      if (commit) store.pushHistory();
      arm.values = { ...arm.values, [slot]: clamp(value, -100, 100) };
      if (slot === "manual") arm.touched = true;
      store.patchMode("cuerpo", { arm });
      sendParams(Boolean(commit), "Brazo", { ms: commit ? 0 : 60 });
      return;
    }
    if (commit) store.pushHistory();
    store.setParam("cuerpo", key, clamp(value, -100, 100));
    const slow = key === "altura" || sheet;
    sendParams(commit, key === "altura" ? "Altura" : "Ajuste", { ms: commit ? 0 : (slow ? 60 : 16) });
  });
}
