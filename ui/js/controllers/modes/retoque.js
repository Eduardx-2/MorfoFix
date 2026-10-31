import { on } from "../bus.js";
import { clamp } from "../../models/utils.js";

export function bindRetoque(store, sendParams) {
  on("retoque-tool", ({ tool }) => {
    store.patchMode("retoque", { tool });
    store.patch({ cursor: tool === "pincel" ? "brush" : "default" });
  });
  on("retoque-brush", ({ key, value, commit }) => {
    if (commit) store.pushHistory();
    store.get().retoque.brush[key] = clamp(value, 0, 100);
    store.state.dirty = true;
    store.emit();
    sendParams(commit);
  });
  on("param", ({ mode, key, value, commit }) => {
    if (mode !== "retoque") return;
    if (commit) store.pushHistory();
    store.setParam("retoque", key, clamp(value, -100, 100));
    sendParams(commit);
  });
}
