export function createSeg({ items, value, full = false, onChange } = {}) {
  const el = document.createElement("div");
  el.className = `seg${full ? " is-full" : ""}`;
  el.setAttribute("role", "tablist");
  const buttons = items.map((item) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "seg-item";
    btn.dataset.value = item.value;
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      set(item.value);
      onChange?.(item.value);
    });
    el.append(btn);
    return btn;
  });

  function set(next) {
    for (const btn of buttons) {
      btn.classList.toggle("is-on", btn.dataset.value === next);
    }
  }

  set(value ?? items[0]?.value);
  return { el, set };
}
