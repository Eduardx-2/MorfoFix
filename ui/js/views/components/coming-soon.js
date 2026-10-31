export function createComingSoon(text = "Todavía no está en este motor. La tarjeta queda para cuando se active.") {
  const el = document.createElement("p");
  el.className = "muted coming-soon";
  el.textContent = text;
  return el;
}
