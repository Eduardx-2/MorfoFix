import { icon } from "../icons.js";

export function toolCardHTML(tool) {
  const badge = tool.v2 ? `<span class="v2-badge">v2</span>` : "";
  const cls = [
    "tool-card",
    tool.remote ? "is-remote" : "",
    tool.wide ? "is-wide" : "",
  ].filter(Boolean).join(" ");
  const disabled = tool.remote || tool.disabled ? "disabled" : "";
  const title = tool.remote ? "Requiere FixPlus"
    : tool.disabled ? `${tool.title || ""}: todavía no está en el motor` : (tool.title || "");
  return `
    <button class="${cls}" type="button" data-tool="${tool.id}" ${disabled} title="${title}">
      ${icon(tool.icon)}
      <div>
        <h3>${tool.title}${badge}</h3>
        <p>${tool.sub}</p>
      </div>
    </button>`;
}

export function renderToolGroups(host, groups, onPick) {
  host.innerHTML = groups.map((group) => `
    <div class="tool-group">
      ${group.label ? `<div class="tool-group-label">${group.label}</div>` : ""}
      <div class="tool-grid">
        ${group.tools.map(toolCardHTML).join("")}
      </div>
    </div>
  `).join("");
  host.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-tool]");
    if (!btn || btn.disabled) return;
    onPick?.(btn.dataset.tool);
  });
}
