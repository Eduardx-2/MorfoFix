from __future__ import annotations

import numpy as np

from morfofix_engine.warps.mesh import (
    GRID_N,
    Stroke,
    _aspect_offset,
    apply_stroke,
    apply_warp,
    base_grid,
    falloff_weight,
    inverse_map,
    sample_mesh,
)


def test_identity_no_strokes() -> None:
    img = np.random.default_rng(1).integers(0, 255, (64, 64, 3), dtype=np.uint8)
    out = apply_warp(img, [])
    assert np.array_equal(out, img)


def test_falloff_formula() -> None:
    k, R = 0.15, 0.03
    for r in (0.0, 0.01, 0.029, 0.03, 0.04):
        w = falloff_weight(r, k, R)
        if r >= R:
            assert w == 0.0
        else:
            expected = k * (1.0 - r / R) ** 2
            assert abs(w - expected) < 1e-9


def test_vertex_move_matches_formula() -> None:
    mesh = base_grid()
    p0 = (0.5, 0.5)
    p1 = (0.52, 0.5)
    k, R = 0.15, 0.03
    mid = GRID_N // 2
    v0 = mesh[mid, mid].copy()
    width = height = 1000
    r = float(_aspect_offset(np.array([v0[0] - p0[0]]), np.array([v0[1] - p0[1]]), width, height)[0])
    out = apply_stroke(mesh, Stroke(p0, p1, k, R), width, height)
    w = falloff_weight(r, k, R)
    got = out[mid, mid]
    expect = np.clip(v0 + np.array([p1[0] - p0[0], p1[1] - p0[1]]) * w, 0, 1)
    assert np.allclose(got, expect, atol=1e-9)


def test_outside_radius_static() -> None:
    mesh = base_grid()
    far = mesh[0, 0].copy()
    out = apply_stroke(mesh, Stroke((0.5, 0.5), (0.6, 0.5), 0.15, 0.03), 100, 100)
    assert np.allclose(out[0, 0], far)


def test_clamp_01() -> None:
    mesh = base_grid()
    out = apply_stroke(mesh, Stroke((0.0, 0.0), (-0.5, -0.5), 0.6, 0.5), 100, 100)
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_frozen_vertices_static() -> None:
    mesh = base_grid()
    frozen = np.zeros((GRID_N, GRID_N), dtype=np.float32)
    frozen[:, :] = 1.0
    out = apply_stroke(mesh, Stroke((0.5, 0.5), (0.7, 0.5), 0.3, 0.2), 100, 100, frozen=frozen)
    assert np.allclose(out, mesh)


def test_inverse_roundtrip() -> None:
    mesh = base_grid()
    mesh = apply_stroke(mesh, Stroke((0.4, 0.5), (0.45, 0.5), 0.15, 0.08), 1000, 1000)
    inv = inverse_map(mesh, iterations=20)
    # dest en grilla → src; forward(src) ≈ dest
    dest = base_grid()
    fwd = sample_mesh(mesh, inv)
    err = np.linalg.norm((fwd - dest) * 1000.0, axis=-1)  # px a 1000
    assert float(err.max()) < 0.5
