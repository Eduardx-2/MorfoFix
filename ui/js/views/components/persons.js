export function createPersons({ onChange } = {}) {
  const el = document.createElement("div");
  el.className = "persons";

  function set(state) {
    const bodies = Array.isArray(state.bodies) && state.bodies.length
      ? state.bodies
      : [{ id: 1 }];
    const active = state.cuerpo?.muscle?.person ?? 0;
    el.innerHTML = `
      <div class="persons-head">
        <span>Persona</span>
        <span class="muted">${bodies.length} detectada${bodies.length === 1 ? "" : "s"}</span>
      </div>
      <div class="persons-row">
        ${bodies.map((_, i) => `
          <button class="person-chip${i === active ? " is-on" : ""}" type="button" data-person="${i}">
            <span class="person-n">${i + 1}</span>
            Persona ${i + 1}
          </button>
        `).join("")}
      </div>
    `;
    el.querySelectorAll("[data-person]").forEach((btn) => {
      btn.addEventListener("click", () => onChange?.(Number(btn.dataset.person)));
    });
  }

  return { el, set };
}
