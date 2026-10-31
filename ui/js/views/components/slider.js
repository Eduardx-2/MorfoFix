import { clamp, formatSigned } from "../../models/utils.js";

function fillStyle(el, value, min, max, bipolar) {
  const track = el.querySelector(".slider-track");
  const fill = el.querySelector(".slider-fill");
  const thumb = el.querySelector(".slider-thumb");
  const val = el.querySelector(".slider-val");
  const t = (value - min) / (max - min);
  thumb.style.left = `${t * 100}%`;
  if (bipolar) {
    const mid = 0.5;
    const from = Math.min(mid, t);
    const to = Math.max(mid, t);
    fill.style.left = `${from * 100}%`;
    fill.style.width = `${(to - from) * 100}%`;
  } else {
    fill.style.left = "0";
    fill.style.width = `${t * 100}%`;
  }
  if (bipolar) {
    val.textContent = formatSigned(value);
    val.classList.toggle("is-pos", value > 0);
  } else {
    val.textContent = String(value);
    val.classList.toggle("is-pos", false);
  }
  track.dataset.value = String(value);
}

export function createSlider({
  label,
  min = -100,
  max = 100,
  value = 0,
  bipolar = true,
  variant = "primary",
  scale = false,
  onChange,
  onCommit,
} = {}) {
  const el = document.createElement("div");
  el.className = `slider${variant === "secondary" ? " is-secondary" : ""}${bipolar ? "" : " is-uni"}`;
  el.innerHTML = `
    <div class="slider-head">
      <span class="slider-label">${label}</span>
      <span class="slider-val">0</span>
    </div>
    <div class="slider-hit" tabindex="0" role="slider" aria-label="${label}" aria-valuemin="${min}" aria-valuemax="${max}">
      <div class="slider-track">
        ${bipolar ? `<div class="slider-zero"></div>` : ""}
        <div class="slider-fill"></div>
        <div class="slider-thumb"></div>
      </div>
    </div>
    ${scale ? `<div class="slider-scale"><span>−100</span><span>0</span><span>+100</span></div>` : ""}
  `;

  const hit = el.querySelector(".slider-hit");
  let current = value;
  let dragging = false;
  let origin = value;

  const set = (next, commit = false) => {
    current = clamp(Math.round(next), min, max);
    fillStyle(el, current, min, max, bipolar);
    hit.setAttribute("aria-valuenow", String(current));
    onChange?.(current);
    if (commit) onCommit?.(current);
  };

  const fromEvent = (event) => {
    const rect = hit.getBoundingClientRect();
    const t = clamp((event.clientX - rect.left) / rect.width, 0, 1);
    return min + t * (max - min);
  };

  hit.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    dragging = true;
    origin = current;
    hit.setPointerCapture(event.pointerId);
    set(fromEvent(event));
  });
  hit.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    set(fromEvent(event));
  });
  hit.addEventListener("pointerup", (event) => {
    if (!dragging) return;
    dragging = false;
    const next = fromEvent(event);
    set(next, Math.round(next) !== origin);
  });
  hit.addEventListener("dblclick", () => set(0, true));
  hit.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 10 : 1;
    if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      event.preventDefault();
      set(current - step, true);
    }
    if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      event.preventDefault();
      set(current + step, true);
    }
    if (event.key === "Home") {
      event.preventDefault();
      set(0, true);
    }
  });

  set(value);

  return {
    el,
    setValue(next) {
      current = clamp(Math.round(next), min, max);
      fillStyle(el, current, min, max, bipolar);
    },
    getValue() {
      return current;
    },
    setDisabled(disabled) {
      el.classList.toggle("is-disabled", disabled);
    },
  };
}
