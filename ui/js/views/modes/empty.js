export function mountEmpty(root) {
  root.innerHTML = `
    <p class="muted">Sin imagen abierta</p>
    <div class="skeleton">
      <div class="sk lg"></div>
      <div class="sk md"></div>
      <div class="sk"></div>
      <div class="sk sm"></div>
    </div>
  `;
  return { sync() {} };
}
