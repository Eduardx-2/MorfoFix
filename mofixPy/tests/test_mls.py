from __future__ import annotations

import numpy as np

from morfofix_engine.warps.mls import mls_points, mls_remap


def test_mls_identity() -> None:
    rng = np.random.default_rng(2)
    src = rng.uniform(10, 90, size=(12, 2))
    query = rng.uniform(0, 100, size=(30, 2))
    out = mls_points(query, src, src.copy())
    assert np.allclose(out, query, atol=1e-4)


def test_mls_interpolates_controls() -> None:
    src = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0], [10.0, 10.0]])
    dst = src + np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    out = mls_points(src, src, dst)
    assert np.allclose(out, dst, atol=1e-5)


def test_mls_remap_identity_image() -> None:
    img = np.arange(16 * 16 * 3, dtype=np.uint8).reshape(16, 16, 3)
    src = np.array([[0.0, 0.0], [15.0, 0.0], [0.0, 15.0], [15.0, 15.0], [7.0, 7.0]])
    out = mls_remap(img, src, src.copy(), grid_step=4)
    diff = np.abs(out.astype(np.int16) - img.astype(np.int16))
    assert int(diff.max()) <= 1
