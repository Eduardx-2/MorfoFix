import { on } from "../bus.js";
import { clamp } from "../../models/utils.js";

export function bindRostro(store, sendParams) {
  on("rostro-tab", ({ tab }) => store.patchMode("rostro", { tab }));
  on("rostro-more", () => {
    store.patchMode("rostro", { moreOpen: !store.get().rostro.moreOpen });
  });
  on("face-step", ({ dir }) => {
    const s = store.get();
    if (!s.faces.length) return;
    store.patch({ activeFace: (s.activeFace + dir + s.faces.length) % s.faces.length });
    sendParams(true);
  });
  on("face-select", ({ index }) => {
    store.patch({ activeFace: index });
    sendParams(true);
  });
  on("param", ({ mode, key, value, commit }) => {
    if (mode !== "rostro") return;
    if (commit) store.pushHistory();
    store.setParam("rostro", key, clamp(value, -100, 100));
    sendParams(commit);
  });
}
