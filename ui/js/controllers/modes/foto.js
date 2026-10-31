import { on } from "../bus.js";
import { clamp } from "../../models/utils.js";

export function bindFoto(store, sendParams) {
  on("foto-tool", ({ tool }) => store.patchMode("foto", { tool }));
  on("param", ({ mode, key, value, commit }) => {
    if (mode !== "foto") return;
    if (commit) store.pushHistory();
    const max = key === "rotate" ? 45 : 100;
    store.setParam("foto", key, clamp(value, -max, max));
    sendParams(commit);
  });
}
