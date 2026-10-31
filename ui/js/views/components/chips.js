const LABELS = {
  MUSCLE_OVER_CLOTHES: "Sobre ropa",
  NO_BODY_SKIN_MASK: "Sin máscara de piel",
  NO_BODY_MASK: "Sin máscara de cuerpo",
  POSE_UNAVAILABLE: "Sin persona detectada: modos automáticos desactivados",
  TORSO_UNAVAILABLE: "Sin torso detectado",
  "MUSCLE_SKIPPED:NO_FRONTAL_BODY": "necesito una foto frontal con el torso visible",
  "MUSCLE_SKIPPED:NO_BODY": "no hay detección para esa persona",
  NO_FACE_RETOUCH: "No encontré la cara: Dientes e Iluminar no aplican (el pincel sí)",
  NO_PERSON_MASK: "Sin máscara de persona: contorno aproximado",
};

export function warningLabel(code) {
  if (!code) return "";
  if (code.startsWith("MUSCLE_PART_SKIPPED:")) return `Parte omitida (${code.split(":")[1]})`;
  if (code.startsWith("ARM_PART_SKIPPED:")) return `Brazo omitido (${code.split(":")[1]}: poco visible o hacia la cámara)`;
  if (code.startsWith("LEG_PART_SKIPPED:")) return `Pierna omitida (${code.split(":")[1]})`;
  if (code.startsWith("NO_BODY:")) return "Sin persona detectada";
  return LABELS[code] || code;
}

export function createChips() {
  const el = document.createElement("div");
  el.className = "chips";

  return {
    el,
    set(codes) {
      const list = (codes || []).filter(Boolean);
      el.hidden = !list.length;
      el.innerHTML = list.map((code) => `<span class="chip-warn">${warningLabel(code)}</span>`).join("");
    },
  };
}
