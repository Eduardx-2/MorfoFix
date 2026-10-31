import { test } from "node:test";
import assert from "node:assert/strict";
import { ARM_MAX_STROKES, armFromUi, commitArmStroke, defaultArm, defaultsFor, fromEditState, toEditState } from "./params.js";

function stateOf(cuerpo) {
  return {
    activeFace: 0,
    rostro: defaultsFor("rostro"),
    cuerpo: { ...defaultsFor("cuerpo"), ...cuerpo },
    retoque: defaultsFor("retoque"),
    foto: defaultsFor("foto"),
  };
}

test("armFromUi no manda manual_strokes si no hay trazos (compat con Rust viejo)", () => {
  const out = armFromUi({ ...defaultArm(), touched: true, values: { ...defaultArm().values, manual: 40 } });
  assert.equal("manual_strokes" in out, false);
  assert.equal(out.manual.value, 0.4);
});

test("commitArmStroke fija el trazo y deja el slider en 0", () => {
  const arm = { ...defaultArm(), touched: true, values: { ...defaultArm().values, manual: 70 } };
  const next = commitArmStroke(arm);
  assert.equal(next.values.manual, 0);
  assert.equal(next.strokes.length, 1);
  assert.equal(next.strokes[0].value, 0.7);
  const out = armFromUi({ ...next, manual: { ...next.manual, cx: 0.9 } });
  assert.equal(out.manual_strokes[0].cx, 0.5);
  assert.equal(out.manual.value, 0);
  assert.equal(commitArmStroke(next), null);
});

test("commitArmStroke respeta el límite", () => {
  const strokes = Array.from({ length: ARM_MAX_STROKES }, () => ({ cx: .5, cy: .5, rx: .06, ry: .14, angle: 0, value: .1 }));
  assert.equal(commitArmStroke({ ...defaultArm(), strokes, values: { ...defaultArm().values, manual: 10 } }), null);
});

test("manipulador: formas fijadas + activa, y fromEditState las deja fijadas", () => {
  const st = stateOf({ manipStack: [{ type: "WaistThin_Rect", cx: .3, cy: .5, w: .2, h: .2, angle: 0, feather: .2, symmetric: true, value: .4 }] });
  st.cuerpo.manipulator = { ...st.cuerpo.manipulator, amountW: -30 };
  const edit = toEditState(st);
  assert.equal(edit.manual_shapes.length, 2);
  const store = { get: () => st, patch(p) { Object.assign(st, p); } };
  fromEditState(store, edit);
  assert.equal(st.cuerpo.manipStack.length, 2);
  assert.equal(st.cuerpo.manipulator.amountW, 0);
  assert.equal(toEditState(st).manual_shapes.length, 2);
});

test("fromEditState recupera trazos de brazo", () => {
  const st = stateOf({});
  const store = { get: () => st, patch(p) { Object.assign(st, p); } };
  fromEditState(store, { schema: 1, arm: { manual_strokes: [{ cx: .2, cy: .3, rx: .05, ry: .1, angle: 5, value: .6 }], manual: { cx: .7, cy: .5, rx: .06, ry: .14, value: 0 } } });
  assert.equal(st.cuerpo.arm.strokes.length, 1);
  assert.equal(toEditState(st).arm.manual_strokes[0].value, .6);
});
