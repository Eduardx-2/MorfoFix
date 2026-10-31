import { api } from "./api.js";
import { MUSCLE_ALIAS, muscleCanonical } from "./params.js";

export { MUSCLE_ALIAS, muscleCanonical };

const FALLBACK_MUSCLE = [
  { name: "full_body", label_es: "Cuerpo completo", tab: "Muscle", kind: "mode", order: 0 },
  { name: "abs", label_es: "Abdominales", tab: "Muscle", kind: "mode", order: 1 },
  { name: "ab_line", label_es: "Línea abdominal", tab: "Muscle", kind: "mode", order: 2 },
  { name: "chest", label_es: "Pectorales", tab: "Muscle", kind: "mode", order: 3 },
  { name: "bust", label_es: "Busto", tab: "Muscle", kind: "mode", order: 4 },
  { name: "arm", label_es: "Brazos", tab: "Muscle", kind: "mode", order: 5 },
  { name: "leg", label_es: "Piernas", tab: "Muscle", kind: "mode", order: 6 },
];

let cache = null;
let pending = null;

export async function loadCatalog() {
  if (cache) return cache;
  if (pending) return pending;
  pending = api.catalog().then((items) => {
    cache = Array.isArray(items) ? items : [];
    pending = null;
    return cache;
  }).catch(() => {
    pending = null;
    cache = [];
    return cache;
  });
  return pending;
}

export function catalogItems() {
  return cache || [];
}

export function muscleModes() {
  const items = (cache || []).filter((item) => item.tab === "Muscle" && item.kind === "mode");
  const list = items.length ? items : FALLBACK_MUSCLE;
  return [...list].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

export function muscleLabel(mode) {
  const id = muscleCanonical(mode);
  return muscleModes().find((item) => item.name === id)?.label_es || "Abdominales";
}
