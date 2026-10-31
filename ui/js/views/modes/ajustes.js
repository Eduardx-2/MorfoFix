import { createToggleRow } from "../components/toggle.js";
import { emit } from "../../controllers/bus.js";
import { api } from "../../models/api.js";

export function mountAjustes(root) {
  const wrap = document.createElement("div");
  wrap.className = "stack";
  const shortcuts = createToggleRow({
    title: "Mostrar atajos",
    subtitle: "Hint inferior del lienzo",
    on: true,
    onChange: (value) => emit("ajuste", { key: "showShortcuts", value }),
  });
  const overlays = createToggleRow({
    title: "Mostrar overlays",
    subtitle: "Badges, malla y máscaras",
    on: true,
    onChange: (value) => emit("ajuste", { key: "showOverlays", value }),
  });
  wrap.append(shortcuts.el, overlays.el);

  const recentsBox = document.createElement("div");
  recentsBox.className = "stack";
  const recentsTitle = document.createElement("h3");
  recentsTitle.textContent = "Recientes";
  recentsBox.append(recentsTitle);
  const recentsList = document.createElement("div");
  recentsList.className = "stack";
  recentsBox.append(recentsList);
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "btn btn-ghost";
  clear.textContent = "Vaciar recientes";
  clear.addEventListener("click", async () => {
    await api.clearRecents().catch(() => {});
    emit("recents-changed");
  });
  recentsBox.append(clear);
  wrap.append(recentsBox);

  const about = document.createElement("p");
  about.className = "muted";
  about.textContent = "MorfoFix es 100 % local. No hay cuentas, nube ni telemetría.";
  wrap.append(about);

  if (api.isTauri()) {
    api.about().then((info) => {
      if (!info) return;
      const engine = info.engine || {};
      about.textContent = `MorfoFix ${info.app_version || ""} · motor ${engine.version || "—"} · ${engine.state || ""}`;
    }).catch(() => {});
  }

  root.replaceChildren(wrap);
  return {
    sync(state) {
      shortcuts.set(state.ajustes.showShortcuts);
      overlays.set(state.ajustes.showOverlays);
      recentsList.replaceChildren();
      const items = state.recents || [];
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Todavía no hay fotos recientes.";
        recentsList.append(empty);
      } else {
        for (const item of items) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "btn btn-ghost";
          btn.textContent = item.file_name || item.path;
          btn.addEventListener("click", () => emit("open-recent", { path: item.path }));
          recentsList.append(btn);
        }
      }
    },
  };
}
