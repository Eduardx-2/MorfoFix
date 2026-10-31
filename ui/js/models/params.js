const FACE_MAP = [
  ["jaw", "intensity_jaw"],
  ["eyesize", "intensity_eyesize"],
  ["mouthsize", "intensity_mouthsize"],
  ["facewidth", "intensity_facewidth"],
  ["facev", "intensity_facev"],
  ["jawline", "intensity_jawline_1"],
  ["nose", "intensity_nosesize"],
  ["brows", "intensity_brownsize"],
];

const BODY_MAP = [
  ["waist", "intensity_bodyslim_waistthin"],
  ["hip", "intensity_bodyslim_hipplump"],
];

function nz(value) {
  const n = Number(value || 0);
  return Number.isFinite(n) ? n : 0;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function decimatePts(pts, minDist) {
  if (!pts || pts.length <= 1) return pts ? pts.map((p) => [p[0], p[1]]) : [];
  const last = pts[pts.length - 1];
  const out = [pts[0]];
  for (let i = 1; i < pts.length; i += 1) {
    const prev = out[out.length - 1];
    const dx = pts[i][0] - prev[0];
    const dy = pts[i][1] - prev[1];
    if (Math.hypot(dx, dy) >= minDist) out.push(pts[i]);
  }
  if (out[out.length - 1][0] !== last[0] || out[out.length - 1][1] !== last[1]) {
    out.push(last);
  }
  return out;
}

// Pincel de cuerpo (liquify). Antes: k = 0.15·int/50 (≤0.6) y r = 0.03·2^((rad−50)/25)/zoom,
// lo que daba ~1.6 px de empuje máximo en una foto de 1280 px: "no hace nada".
// Ahora r es fracción del LADO MENOR de la imagen (igual que el motor y el cursor)
// y k llega a ~1 (el centro del pincel arrastra la piel junto con el mouse).
export const BRUSH_R_MIN = 0.01;
export const BRUSH_R_MAX = 0.25;

export function brushRadius(radiusUi) {
  return clamp(BRUSH_R_MIN + (BRUSH_R_MAX - BRUSH_R_MIN) * nz(radiusUi) / 100, BRUSH_R_MIN, BRUSH_R_MAX);
}

export function brushK(softness, strengthUi) {
  const base = softness === "fuerte" ? 0.9 : 0.55;
  return clamp(base * (0.2 + 0.8 * nz(strengthUi) / 100), 0.02, 1);
}

export function brushToStroke(softness, radiusUi, strengthUi, pts) {
  const r = brushRadius(radiusUi);
  const k = brushK(softness, strengthUi);
  let points = decimatePts(pts, 0.15 * r);
  if (points.length === 1) points = [points[0], points[0]];
  return { pts: points, k, r };
}

// Congelar: radio hasta 0.5 del lado menor; feather hasta 0.15 del lado menor.
export function freezeRadius(radiusUi) {
  return clamp(0.01 + 0.49 * nz(radiusUi) / 100, 0.01, 0.5);
}

export function freezeFeather(featherUi) {
  return clamp(0.15 * nz(featherUi) / 100, 0, 0.25);
}

export function muscleRadius(radiusUi) {
  return clamp(nz(radiusUi) / 100 * 0.1, 0.01, 0.1);
}

export const MUSCLE_ALIAS = {
  body_muscle: "full_body",
  man_abs: "abs",
  woman_abs: "ab_line",
  man_chest: "chest",
  woman_chest: "bust",
  man_arm: "arm",
  woman_arm: "arm",
  man_leg: "leg",
  woman_leg: "leg",
};

export function muscleCanonical(mode) {
  return MUSCLE_ALIAS[mode] || mode || "abs";
}

export function poseIsAvailable(state) {
  if (typeof state?.poseAvailable === "boolean") return state.poseAvailable;
  return (state?.bodies || []).length > 0;
}

export function bodyParts(state, index = 0) {
  const b = (state?.bodies || [])[index];
  if (b?.parts) return b.parts;
  const vis = b?.visible || {};
  const v = (i) => Number(vis[i] ?? vis[String(i)] ?? 0);
  return {
    leftupper: Math.min(v(11), v(13)) >= 0.3,
    leftforearm: Math.min(v(13), v(15)) >= 0.3,
    rightupper: Math.min(v(12), v(14)) >= 0.3,
    rightforearm: Math.min(v(14), v(16)) >= 0.3,
    torso: Math.min(v(11), v(12), v(23), v(24)) >= 0.5,
  };
}

export function defaultMuscle() {
  return {
    // Músculo no viaja al motor hasta que el usuario abre la herramienta o toca un control.
    // Antes el nivel 3 por defecto se mandaba en TODOS los renders (también en Rostro/Retoque).
    enabled: false,
    person: 0,
    mode: "abs",
    level: 3,
    definition: 60,
    light: "auto",
    volume: true,
    gloss: false,
    strokes: [],
    draft: null,
    // Como FixPlus: el efecto cubre a la persona y lo primero es Borrar donde sobra.
    // "Pintar" sigue existiendo pero LIMITA el efecto a lo pintado (ver doc 23).
    op: "erase",
    radius: 40,
    showMask: false,
  };
}

export function muscleFromUi(muscle) {
  const m = muscle || defaultMuscle();
  if (!m.enabled) return {};
  const strokes = [...(m.strokes || [])].filter((s) => s?.pts?.length);
  if (m.draft?.pts?.length) {
    strokes.push({
      pts: m.draft.pts,
      radius: muscleRadius(m.radius),
      erase: Boolean(m.draft.erase),
    });
  }
  const strength = clamp(nz(m.level) / 5, 0, 1);
  if (!strength && !strokes.length) return {};
  return {
    [String(m.person || 0)]: {
      mode: muscleCanonical(m.mode || "abs"),
      strength,
      definition: clamp(nz(m.definition) / 100, 0, 1),
      warp: m.volume ? 0.3 : 0,
      light: m.light || "auto",
      gloss: m.gloss ? 0.15 : 0,
      brush: { strokes },
    },
  };
}

export function normRect(a, b) {
  const x = clamp(Math.min(a[0], b[0]), 0, 1);
  const y = clamp(Math.min(a[1], b[1]), 0, 1);
  return {
    x,
    y,
    w: clamp(Math.abs(b[0] - a[0]), 0.001, 1 - x || 0.001),
    h: clamp(Math.abs(b[1] - a[1]), 0.001, 1 - y || 0.001),
  };
}

export const HEIGHT_MIN_GAP = 0.02;

export function heightMinGap(boxH) {
  return Math.max(HEIGHT_MIN_GAP, 28 / Math.max(1, boxH));
}

// Altura: líneas del overlay → contrato {value, y_start, y_end} (0..1, imagen sin estirar).
export function heightRange(lines, minGap = HEIGHT_MIN_GAP) {
  const a = clamp(nz(lines?.[0] ?? 0.48), 0, 1);
  const b = clamp(nz(lines?.[1] ?? 0.92), 0, 1);
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  if (hi - lo >= minGap) return [lo, hi];
  return [lo, Math.min(1, lo + minGap)];
}

// Posición en pantalla (0..1 sobre la imagen ya estirada) de una y de la imagen original.
// Refleja height_field() con keep_canvas=false: banda escalada por (1 + 0.30·value).
export function heightDisplayY(y, range, value) {
  const [a, b] = range;
  const s = 1 + 0.3 * nz(value);
  const total = 1 + (b - a) * (s - 1);
  let out;
  if (y <= a) out = y;
  else if (y >= b) out = y + (b - a) * (s - 1);
  else out = a + (y - a) * s;
  return out / total;
}

export function heightSourceY(yDisp, range, value) {
  const [a, b] = range;
  const s = 1 + 0.3 * nz(value);
  const total = 1 + (b - a) * (s - 1);
  const yo = yDisp * total;
  const bOut = a + (b - a) * s;
  if (yo <= a) return clamp(yo, 0, 1);
  if (yo >= bOut) return clamp(yo - (b - a) * (s - 1), 0, 1);
  return clamp(a + (yo - a) / s, 0, 1);
}

// Solo retoque (radio relativo al lado mayor, histórico).
export function uiRadius(radiusUi, zoomPct) {
  const zoom = Math.max(nz(zoomPct) / 100, 1e-6);
  return clamp(0.03 * 2 ** ((nz(radiusUi) - 50) / 25) / zoom, 0.001, 0.5);
}

// Manipulador: las flechas ACUMULAN intensidad (amountW/amountH, −100..100).
// ← adelgaza (amountW < 0), → ensancha; ↑ alarga (amountH > 0), ↓ acorta.
// Motor: WaistThin_Rect value > 0 adelgaza; Stretch_Rect value > 0 comprime en alto.
// Antes value era fijo en ±0.08 (≈2 px) y las flechas solo agrandaban la caja.
export function manipulatorShapes(cuerpo) {
  const m = cuerpo?.manipulator;
  if (!m) return [];
  const base = {
    cx: clamp(nz(m.x) + nz(m.w) / 2, 0, 1),
    cy: clamp(nz(m.y) + nz(m.h) / 2, 0, 1),
    w: clamp(nz(m.w) || 0.24, 0.001, 1),
    h: clamp(nz(m.h) || 0.22, 0.001, 1),
    angle: nz(m.rot),
    feather: clamp(nz(m.edge) / 100, 0, 1),
    symmetric: m.symmetric !== false,
  };
  const out = [];
  const aw = clamp(nz(m.amountW), -100, 100);
  const ah = clamp(nz(m.amountH), -100, 100);
  if (aw) out.push({ type: "WaistThin_Rect", ...base, value: clamp(-aw / 100, -1, 1) });
  if (ah) out.push({ type: "Stretch_Rect", ...base, value: clamp(-ah / 100, -1, 1) });
  return out;
}

function shapesToManipulator(shapes, prev) {
  const m = { ...prev, amountW: 0, amountH: 0 };
  const list = Array.isArray(shapes) ? shapes : [];
  const first = list.find((s) => s && (s.type === "WaistThin_Rect" || s.type === "Stretch_Rect"));
  if (!first) return m;
  m.x = clamp(nz(first.cx) - nz(first.w) / 2, 0, 1);
  m.y = clamp(nz(first.cy) - nz(first.h) / 2, 0, 1);
  m.w = clamp(nz(first.w), 0.04, 1);
  m.h = clamp(nz(first.h), 0.04, 1);
  m.rot = nz(first.angle);
  m.symmetric = first.symmetric !== false;
  m.edge = Math.round(nz(first.feather) * 100);
  for (const s of list) {
    if (s?.type === "WaistThin_Rect") m.amountW = Math.round(-nz(s.value) * 100);
    if (s?.type === "Stretch_Rect") m.amountH = Math.round(-nz(s.value) * 100);
  }
  return m;
}

export function toEditState(state) {
  const idx = String(Math.max(0, state.activeFace));
  const faceParams = {};
  for (const [key, name] of FACE_MAP) {
    const v = nz(state.rostro[key]);
    if (v) faceParams[name] = v / 100;
  }
  const bodyParams = {};
  for (const [key, name] of BODY_MAP) {
    const v = nz(state.cuerpo[key]);
    if (v) bodyParams[name] = v / 100;
  }
  const armUi = state.cuerpo.arm || defaultArm();
  for (const [part, name] of Object.entries(ARM_BODY)) {
    const v = nz(armUi.values?.[part]);
    if (v) bodyParams[name] = v / 100;
  }
  const heightVal = nz(state.cuerpo.altura) / 100;
  const hRange = heightRange(state.cuerpo.heightLines);
  const liquify = [...(state.cuerpo.liquify || [])].filter((stroke) => stroke?.pts?.length >= 2);
  if (state.cuerpo.draftStroke?.pts?.length >= 1) {
    liquify.push(brushToStroke(
      state.cuerpo.brush.softness,
      state.cuerpo.brush.radius,
      state.cuerpo.brush.intensity,
      state.cuerpo.draftStroke.pts,
    ));
  }
  const fz = state.cuerpo.freeze || {};
  const freezeStrokes = [...(state.cuerpo.freezeStrokes || [])].filter((stroke) => stroke?.pts?.length);
  if (state.cuerpo.draftFreeze?.pts?.length) {
    freezeStrokes.push({
      pts: state.cuerpo.draftFreeze.pts,
      radius: freezeRadius(fz.radius),
      erase: Boolean(state.cuerpo.draftFreeze.erase),
    });
  }
  const freezeRects = [...(state.cuerpo.freezeRects || [])].filter((r) => r && r.w > 0 && r.h > 0);
  if (state.cuerpo.draftRect && state.cuerpo.draftRect.w > 0.002 && state.cuerpo.draftRect.h > 0.002) {
    freezeRects.push(state.cuerpo.draftRect);
  }
  // Formas ya fijadas (no siguen a la caja) + la forma activa del manipulador.
  const shapes = [...(state.cuerpo.manipStack || []), ...manipulatorShapes(state.cuerpo)];
  const retouchStrokes = [...(state.retoque.strokes || [])];
  if (state.retoque.draftStroke?.pts?.length) {
    retouchStrokes.push({
      pts: state.retoque.draftStroke.pts,
      radius: uiRadius(state.retoque.brush.radius, state.zoom),
      erase: false,
    });
  }
  const skinAmount = Math.max(
    0,
    retouchStrokes.length ? nz(state.retoque.brush.intensity) / 100 : 0,
  );
  const crop = Array.isArray(state.foto.crop) && state.foto.crop.length === 4
    ? state.foto.crop.map((n) => clamp(nz(n), 0, 1))
    : [0, 0, 1, 1];
  const ordered = crop[2] > crop[0] && crop[3] > crop[1] ? crop : [0, 0, 1, 1];
  return {
    schema: 1,
    face: Object.keys(faceParams).length ? { [idx]: faceParams } : {},
    facelift: {},
    body: Object.keys(bodyParams).length ? { "0": bodyParams } : {},
    body_options: {
      bg_protect: Boolean(state.cuerpo.protectBg),
      head_protect: true,
    },
    height: {
      value: heightVal,
      y_start: hRange[0],
      y_end: hRange[1],
    },
    liquify,
    manual_shapes: shapes,
    freeze: {
      strokes: freezeStrokes,
      rects: freezeRects,
      invert: Boolean(fz.invert) && (freezeStrokes.length > 0 || freezeRects.length > 0),
      feather: freezeFeather(fz.feather),
    },
    retouch: {
      degree_whiten_teeth: Math.max(0, nz(state.retoque.teeth) / 100),
      degree_brighten_eyes: Math.max(0, nz(state.retoque.illuminate) / 100),
      degree_skin_smooth: skinAmount,
      brush: retouchStrokes.length
        ? { degree_skin_smooth: { strokes: retouchStrokes } }
        : {},
    },
    remove: [],
    photo: {
      crop: ordered,
      rotate_deg: nz(state.foto.rotate),
      flip_h: false,
      hsl: {
        hue: nz(state.foto.h) / 100,
        saturation: nz(state.foto.s) / 100,
        lightness: nz(state.foto.l) / 100,
      },
    },
    muscle: muscleFromUi(state.cuerpo.muscle),
    arm: armFromUi(state.cuerpo.arm),
  };
}

export function defaultArm() {
  return {
    mode: "manual",
    values: { leftupper: 0, leftforearm: 0, rightupper: 0, rightforearm: 0, manual: 0 },
    manual: { cx: 0.5, cy: 0.45, rx: 0.06, ry: 0.14, angle: 0 },
    protectBg: true,
    touched: false,
    strokes: [],
  };
}

const ARM_BODY = {
  leftupper: "intensity_bodyslim_armthin_leftupper",
  leftforearm: "intensity_bodyslim_armthin_leftforearm",
  rightupper: "intensity_bodyslim_armthin_rightupper",
  rightforearm: "intensity_bodyslim_armthin_rightforearm",
};

export const ARM_MAX_STROKES = 32;

function armStrokeOut(s) {
  return {
    cx: s.cx, cy: s.cy, rx: s.rx, ry: s.ry,
    angle: s.angle || 0, value: clamp(nz(s.value), -1, 1),
    protect_bg: Boolean(s.protect_bg),
  };
}

// Fija el trazo activo del brazo (si tiene efecto) y deja el slider en 0.
// Devuelve null si no hay nada que fijar o si se llegó al límite.
export function commitArmStroke(arm) {
  const a = { ...defaultArm(), ...(arm || {}) };
  const v = nz(a.values?.manual);
  if (!v) return null;
  const strokes = [...(a.strokes || [])];
  if (strokes.length >= ARM_MAX_STROKES) return null;
  strokes.push({ ...a.manual, value: v / 100, protect_bg: Boolean(a.protectBg) });
  return { ...a, strokes, values: { ...a.values, manual: 0 }, touched: true };
}

export function armFromUi(arm) {
  const a = arm || defaultArm();
  const send = a.values?.manual || a.touched;
  const strokes = (a.strokes || []).filter((s) => nz(s.value)).map(armStrokeOut);
  const out = {
    manual: send
      ? {
        cx: a.manual.cx, cy: a.manual.cy, rx: a.manual.rx, ry: a.manual.ry,
        angle: a.manual.angle, value: (a.values?.manual || 0) / 100,
        protect_bg: Boolean(a.protectBg),
      }
      : null,
  };
  // Solo se manda si hay trazos: un Rust sin `manual_strokes` (deny_unknown_fields) rechazaría la clave.
  if (strokes.length) out.manual_strokes = strokes;
  return out;
}

export function fromEditState(store, edit) {
  if (!edit) return;
  const s = store.get();
  const keys = Object.keys(edit.face || {});
  const idx = keys.includes(String(s.activeFace)) ? String(s.activeFace) : (keys[0] || "0");
  const face = (edit.face && edit.face[idx]) || {};
  const rostro = { ...s.rostro };
  for (const [key, name] of FACE_MAP) {
    rostro[key] = Math.round(nz(face[name]) * 100);
  }
  const body = (edit.body && (edit.body["0"] || Object.values(edit.body)[0])) || {};
  const cuerpo = {
    ...s.cuerpo,
    brush: { ...s.cuerpo.brush },
    manipulator: { ...s.cuerpo.manipulator },
    freeze: { ...(s.cuerpo.freeze || {}) },
  };
  for (const [key, name] of BODY_MAP) {
    cuerpo[key] = Math.round(nz(body[name]) * 100);
  }
  cuerpo.altura = Math.round(nz(edit.height?.value) * 100);
  if (edit.height) {
    const ys = edit.height.y_start ?? edit.height.band?.[0] ?? 0.48;
    const ye = edit.height.y_end ?? edit.height.band?.[1] ?? 0.92;
    cuerpo.heightLines = [clamp(nz(ys), 0, 1), clamp(nz(ye), 0, 1)];
  }
  cuerpo.protectBg = Boolean(edit.body_options?.bg_protect);
  cuerpo.liquify = Array.isArray(edit.liquify) ? edit.liquify.map((stroke) => ({
    pts: stroke.pts || [],
    k: nz(stroke.k),
    r: nz(stroke.r),
  })) : [];
  cuerpo.draftStroke = null;
  const freezeStrokes = Array.isArray(edit.freeze?.strokes) ? edit.freeze.strokes.map((stroke) => ({
    pts: stroke.pts || [],
    radius: nz(stroke.radius),
    erase: Boolean(stroke.erase),
  })) : [];
  cuerpo.freezeStrokes = freezeStrokes;
  cuerpo.freezeRects = Array.isArray(edit.freeze?.rects) ? edit.freeze.rects.map((r) => ({
    x: nz(r.x), y: nz(r.y), w: nz(r.w), h: nz(r.h), erase: Boolean(r.erase),
  })) : [];
  cuerpo.draftFreeze = null;
  cuerpo.draftRect = null;
  cuerpo.frozen = freezeStrokes.length > 0 || cuerpo.freezeRects.length > 0;
  cuerpo.freeze.invert = Boolean(edit.freeze?.invert);
  if (edit.freeze && edit.freeze.feather !== undefined) {
    cuerpo.freeze.feather = Math.round(clamp(nz(edit.freeze.feather) / 0.15, 0, 1) * 100);
  }
  // Tras deshacer/rehacer o abrir: todas las formas quedan fijadas y la caja arranca en 0.
  cuerpo.manipStack = (Array.isArray(edit.manual_shapes) ? edit.manual_shapes : []).map((sh) => ({ ...sh }));
  cuerpo.manipulator = { ...shapesToManipulator([], cuerpo.manipulator) };
  cuerpo.muscle = { ...defaultMuscle(), ...(s.cuerpo.muscle || {}) };
  const muscleKeys = Object.keys(edit.muscle || {});
  const muscleIdx = muscleKeys.includes(String(cuerpo.muscle.person))
    ? String(cuerpo.muscle.person)
    : (muscleKeys[0] || "");
  const muscle = muscleIdx ? edit.muscle[muscleIdx] : null;
  cuerpo.muscle.enabled = Boolean(muscle);
  if (muscle) {
    cuerpo.muscle.person = Number(muscleIdx) || 0;
    cuerpo.muscle.mode = muscleCanonical(muscle.mode || cuerpo.muscle.mode);
    cuerpo.muscle.level = Math.round(nz(muscle.strength) * 5);
    cuerpo.muscle.definition = Math.round(nz(muscle.definition) * 100);
    cuerpo.muscle.light = muscle.light || "auto";
    cuerpo.muscle.volume = nz(muscle.warp) > 0;
    cuerpo.muscle.gloss = nz(muscle.gloss) > 0;
    cuerpo.muscle.strokes = Array.isArray(muscle.brush?.strokes) ? muscle.brush.strokes.map((stroke) => ({
      pts: stroke.pts || [],
      radius: nz(stroke.radius) || muscleRadius(40),
      erase: Boolean(stroke.erase),
    })) : [];
    cuerpo.muscle.draft = null;
  }
  const retoque = { ...s.retoque, brush: { ...s.retoque.brush } };
  retoque.teeth = Math.round(nz(edit.retouch?.degree_whiten_teeth) * 100);
  retoque.illuminate = Math.round(nz(edit.retouch?.degree_brighten_eyes) * 100);
  const mask = edit.retouch?.brush?.degree_skin_smooth;
  retoque.strokes = Array.isArray(mask?.strokes) ? mask.strokes.map((stroke) => ({
    pts: stroke.pts || [],
    radius: nz(stroke.radius),
    erase: Boolean(stroke.erase),
  })) : [];
  retoque.draftStroke = null;
  if (nz(edit.retouch?.degree_skin_smooth)) {
    retoque.brush.intensity = Math.round(nz(edit.retouch.degree_skin_smooth) * 100);
  }
  const foto = { ...s.foto };
  foto.rotate = nz(edit.photo?.rotate_deg);
  foto.h = Math.round(nz(edit.photo?.hsl?.hue) * 100);
  foto.s = Math.round(nz(edit.photo?.hsl?.saturation) * 100);
  foto.l = Math.round(nz(edit.photo?.hsl?.lightness) * 100);
  const crop = edit.photo?.crop;
  foto.crop = Array.isArray(crop) && crop.length === 4 ? crop : [0, 0, 1, 1];
  cuerpo.arm = { ...defaultArm(), ...(s.cuerpo.arm || {}) };
  cuerpo.arm.values = { ...defaultArm().values };
  cuerpo.arm.strokes = (Array.isArray(edit.arm?.manual_strokes) ? edit.arm.manual_strokes : []).map((st) => ({
    cx: nz(st.cx), cy: nz(st.cy), rx: nz(st.rx) || 0.06, ry: nz(st.ry) || 0.14, angle: nz(st.angle),
    value: nz(st.value), protect_bg: Boolean(st.protect_bg),
  }));
  if (edit.arm?.manual) {
    const am = edit.arm.manual;
    cuerpo.arm.mode = "manual";
    cuerpo.arm.touched = true;
    cuerpo.arm.manual = {
      cx: nz(am.cx), cy: nz(am.cy), rx: nz(am.rx) || 0.06, ry: nz(am.ry) || 0.14, angle: nz(am.angle),
    };
    cuerpo.arm.values.manual = Math.round(nz(am.value) * 100);
    cuerpo.arm.protectBg = Boolean(am.protect_bg);
  }
  const body0 = edit.body?.["0"] || {};
  for (const [part, name] of Object.entries(ARM_BODY)) {
    if (body0[name]) cuerpo.arm.values[part] = Math.round(nz(body0[name]) * 100);
  }
  store.patch({ rostro, cuerpo, retoque, foto });
}

export function applyHistoryFlags(store, info) {
  if (!info) return;
  store.patch({
    canUndo: Boolean(info.can_undo),
    canRedo: Boolean(info.can_redo),
    historyRemote: true,
  });
}

export function toEngineParams(state) {
  return {
    intensity_jaw: state.rostro.jaw / 100,
    intensity_eyesize: state.rostro.eyesize / 100,
    intensity_mouthsize: state.rostro.mouthsize / 100,
    intensity_facewidth: state.rostro.facewidth / 100,
    intensity_facev: state.rostro.facev / 100,
    intensity_jawline_1: state.rostro.jawline / 100,
    intensity_nose: state.rostro.nose / 100,
    intensity_brows: state.rostro.brows / 100,
    intensity_height: state.cuerpo.altura / 100,
    intensity_waist: state.cuerpo.waist / 100,
    intensity_hip: state.cuerpo.hip / 100,
    brush_radius: state.cuerpo.brush.radius,
    brush_strength: state.cuerpo.brush.intensity,
    brush_soft: state.cuerpo.brush.softness === "suave",
    protect_bg: state.cuerpo.protectBg,
    freeze: state.cuerpo.frozen,
    intensity_teeth: state.retoque.teeth / 100,
    intensity_brighten: state.retoque.illuminate / 100,
    hue: state.foto.h / 100,
    saturation: state.foto.s / 100,
    lightness: state.foto.l / 100,
    rotate: state.foto.rotate,
    face_index: Math.max(0, state.activeFace),
  };
}

export function defaultsFor(mode) {
  if (mode === "rostro") {
    return {
      tab: "cara",
      moreOpen: false,
      jaw: 0,
      eyesize: 0,
      mouthsize: 0,
      facewidth: 0,
      facev: 0,
      jawline: 0,
      nose: 0,
      brows: 0,
    };
  }
  if (mode === "cuerpo") {
    return {
      tool: "adelgazar",
      sub: "pincel",
      brush: { softness: "suave", radius: 36, intensity: 42 },
      altura: 0,
      waist: 0,
      hip: 0,
      protectBg: true,
      frozen: false,
      freezeStrokes: [],
      freezeRects: [],
      freeze: { mode: "pincel", op: "add", radius: 20, feather: 30, invert: false },
      liquify: [],
      draftStroke: null,
      draftFreeze: null,
      draftRect: null,
      heightLines: [0.48, 0.92],
      muscle: defaultMuscle(),
      arm: defaultArm(),
      // Caja por defecto más ancha que un torso típico: el efecto se desvanece hacia
      // los bordes de la caja, así que si la silueta queda afuera no se nota nada.
      manipStack: [],
      manipulator: {
        x: 0.3,
        y: 0.42,
        w: 0.4,
        h: 0.24,
        rot: 0,
        dir: "",
        symmetric: true,
        edge: 48,
        step: 10,
        amountW: 0,
        amountH: 0,
      },
    };
  }
  if (mode === "retoque") {
    return {
      tool: "dientes",
      teeth: 0,
      illuminate: 0,
      brush: { radius: 28, intensity: 50 },
      strokes: [],
      draftStroke: null,
    };
  }
  if (mode === "foto") {
    return {
      tool: "recortar",
      rotate: 0,
      h: 0,
      s: 0,
      l: 0,
      crop: [0, 0, 1, 1],
      cropStart: null,
    };
  }
  return {};
}
