export function createAlert() {
  const el = document.createElement("div");
  el.className = "panel-alert";
  el.hidden = true;

  return {
    el,
    set(message) {
      if (!message) {
        el.hidden = true;
        el.textContent = "";
        return;
      }
      el.hidden = false;
      el.textContent = message;
    },
  };
}
