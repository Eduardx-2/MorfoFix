export function createSteps({ min = 0, max = 5, value = 3, originLabel = "Orig.", onChange } = {}) {
  const el = document.createElement("div");
  el.className = "steps";
  const buttons = [];
  for (let i = min; i <= max; i += 1) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "step";
    btn.dataset.value = String(i);
    btn.innerHTML = i === min
      ? `<span class="step-label">${originLabel}</span>`
      : `<span class="step-n">${i}</span>`;
    btn.addEventListener("click", () => {
      set(i);
      onChange?.(i);
    });
    el.append(btn);
    buttons.push(btn);
  }

  function set(next) {
    for (const btn of buttons) {
      btn.classList.toggle("is-on", Number(btn.dataset.value) === next);
    }
  }

  set(value);
  return { el, set };
}
