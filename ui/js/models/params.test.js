import { test } from "node:test";
import assert from "node:assert/strict";
import {
  HEIGHT_MIN_GAP, heightRange, muscleCanonical, toEditState, fromEditState,
  defaultMuscle, defaultArm, defaultsFor,
} from "./params.js";

function storeOf(cuerpo) {
  const state = {
    activeFace: 0,
    rostro: defaultsFor("rostro"),
    cuerpo: { ...defaultsFor("cuerpo"), ...cuerpo },
    retoque: defaultsFor("retoque"),
    foto: defaultsFor("foto"),
  };
  return {
    get: () => state,
    patch(partial) { Object.assign(state, partial); },
  };
}

test("heightRange ordena y respeta el gap mínimo", () => {
  assert.deepEqual(heightRange([0.92, 0.48]), [0.48, 0.92]);
  const tight = heightRange([0.5, 0.5]);
  assert.ok(tight[1] - tight[0] >= HEIGHT_MIN_GAP - 1e-9);
});

test("toEditState manda height aunque el valor sea 0", () => {
  const state = storeOf({ altura: 0, heightLines: [0.4, 0.7] }).get();
  const edit = toEditState(state);
  assert.equal(edit.height.value, 0);
  assert.equal(edit.height.y_start, 0.4);
  assert.equal(edit.height.y_end, 0.7);
  assert.equal(edit.height.band, undefined);
});

test("toEditState arma arm.manual y alias de músculo", () => {
  const state = storeOf({
    arm: { ...defaultArm(), touched: true, values: { ...defaultArm().values, manual: 40 } },
    muscle: { ...defaultMuscle(), enabled: true, mode: "man_abs", level: 3 },
  }).get();
  const edit = toEditState(state);
  assert.equal(edit.arm.manual.value, 0.4);
  assert.equal(edit.muscle["0"].mode, "abs");
});

test("fromEditState mapea ids viejos de músculo", () => {
  const store = storeOf({ muscle: defaultMuscle() });
  fromEditState(store, {
    schema: 1,
    muscle: { "0": { mode: "woman_arm", strength: 0.6, definition: 0.5, warp: 0.3, light: "auto", gloss: 0, brush: { strokes: [] } } },
    arm: { manual: { cx: 0.3, cy: 0.4, rx: 0.05, ry: 0.12, angle: 10, value: 0.2, protect_bg: true } },
    height: { value: 0, y_start: 0.2, y_end: 0.8 },
  });
  assert.equal(store.get().cuerpo.muscle.mode, "arm");
  assert.equal(store.get().cuerpo.arm.mode, "manual");
  assert.equal(store.get().cuerpo.heightLines[0], 0.2);
});

test("muscleCanonical cubre los alias", () => {
  assert.equal(muscleCanonical("body_muscle"), "full_body");
  assert.equal(muscleCanonical("woman_chest"), "bust");
});

test("Músculo no viaja al motor si el usuario no lo activó", () => {
  const edit = toEditState(storeOf({}).get());
  assert.deepEqual(edit.muscle, {});
  const on = toEditState(storeOf({ muscle: { ...defaultMuscle(), enabled: true } }).get());
  assert.equal(on.muscle["0"].strength, 0.6);
});

test("fromEditState marca Músculo activo solo si el estado lo trae", () => {
  const store = storeOf({ muscle: { ...defaultMuscle(), enabled: true } });
  fromEditState(store, { schema: 1 });
  assert.equal(store.get().cuerpo.muscle.enabled, false);
  fromEditState(store, { schema: 1, muscle: { "0": { mode: "abs", strength: 0.4 } } });
  assert.equal(store.get().cuerpo.muscle.enabled, true);
  assert.equal(store.get().cuerpo.muscle.level, 2);
});
