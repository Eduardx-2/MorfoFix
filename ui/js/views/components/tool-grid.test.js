import { test } from "node:test";
import assert from "node:assert/strict";
import { toolCardHTML } from "./tool-grid.js";

test("tarjeta deshabilitada avisa que no está en el motor", () => {
  const html = toolCardHTML({
    id: "presets", icon: "presets", title: "Presets", sub: "Próximamente", disabled: true,
  });
  assert.match(html, /disabled/);
  assert.match(html, /todavía no está en el motor/);
  assert.match(html, /Próximamente/);
});
