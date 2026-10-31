export function createToggle({ on = false, onChange } = {}) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = `toggle${on ? " is-on" : ""}`;
  el.setAttribute("role", "switch");
  el.setAttribute("aria-checked", String(on));
  el.addEventListener("click", () => {
    const next = !el.classList.contains("is-on");
    el.classList.toggle("is-on", next);
    el.setAttribute("aria-checked", String(next));
    onChange?.(next);
  });
  return {
    el,
    set(value) {
      el.classList.toggle("is-on", value);
      el.setAttribute("aria-checked", String(value));
    },
  };
}

export function createToggleRow({ title, subtitle, on = false, onChange } = {}) {
  const row = document.createElement("div");
  row.className = "toggle-row";
  const copy = document.createElement("div");
  copy.className = "copy";
  copy.innerHTML = `<h3>${title}</h3>${subtitle ? `<p>${subtitle}</p>` : ""}`;
  const toggle = createToggle({ on, onChange });
  row.append(copy, toggle.el);
  return {
    el: row,
    set: toggle.set,
  };
}
