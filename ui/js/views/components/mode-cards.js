import { muscleModes } from "../../models/catalog.js";
import { icon } from "../icons.js";

const ICONS = {
  full_body: "muscle",
  abs: "abs",
  ab_line: "abline",
  chest: "chest",
  bust: "bust",
  arm: "arm",
  leg: "leg",
};

export function createModeCards({ onChange } = {}) {
  const el = document.createElement("div");
  el.className = "mode-cards";

  function set(active) {
    const modes = muscleModes();
    const full = modes.filter((m) => m.name === "full_body");
    const rest = modes.filter((m) => m.name !== "full_body");
    el.innerHTML = `
      <div class="mode-group">
        <div class="mode-group-label">7 modos</div>
        <div class="mode-row is-all">
          ${full.map((m) => card(m, active)).join("")}
        </div>
        <div class="mode-row is-3">
          ${rest.map((m) => card(m, active)).join("")}
        </div>
      </div>
    `;
    el.querySelectorAll("[data-mode]").forEach((btn) => {
      btn.addEventListener("click", () => onChange?.(btn.dataset.mode));
    });
  }

  function card(m, active) {
    return `
      <button class="mcard${m.name === active ? " is-on" : ""}" type="button" data-mode="${m.name}">
        ${icon(ICONS[m.name] || "muscle")}
        <span>${m.label_es}</span>
      </button>`;
  }

  set("abs");
  return { el, set };
}
