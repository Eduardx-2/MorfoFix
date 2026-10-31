export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function debounce(fn, ms) {
  let timer = 0;
  const wrapped = (...args) => {
    clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), ms);
  };
  wrapped.flush = (...args) => {
    clearTimeout(timer);
    fn(...args);
  };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

export function formatSigned(value) {
  if (value > 0) return `+${value}`;
  if (value < 0) return `−${Math.abs(value)}`;
  return "0";
}

export function containRect(boxW, boxH, imgW, imgH) {
  if (!imgW || !imgH) return { x: 0, y: 0, w: boxW, h: boxH, scale: 1 };
  const scale = Math.min(boxW / imgW, boxH / imgH);
  const w = imgW * scale;
  const h = imgH * scale;
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h, scale };
}

export function fileFormat(name, type) {
  const ext = (name.split(".").pop() || "").toUpperCase();
  if (["JPG", "JPEG", "PNG", "WEBP", "TIF", "TIFF"].includes(ext)) {
    return ext === "JPEG" ? "JPG" : ext;
  }
  if (type.includes("png")) return "PNG";
  if (type.includes("webp")) return "WEBP";
  if (type.includes("tiff")) return "TIFF";
  return "JPG";
}

export function snapshot(state) {
  return JSON.parse(JSON.stringify({
    rostro: state.rostro,
    cuerpo: state.cuerpo,
    retoque: state.retoque,
    foto: state.foto,
  }));
}

export function applySnapshot(state, snap) {
  Object.assign(state.rostro, snap.rostro);
  Object.assign(state.cuerpo, snap.cuerpo);
  Object.assign(state.retoque, snap.retoque);
  Object.assign(state.foto, snap.foto);
}
