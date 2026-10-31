from __future__ import annotations

import numpy as np

from morfofix_engine.retouch.inpaint import inpaint
from morfofix_engine.retouch.skin import skin_retouch


def test_inpaint_line_on_gradient() -> None:
    w, h = 80, 40
    x = np.linspace(0, 255, w, dtype=np.float32)
    img = np.tile(x, (h, 1)).astype(np.uint8)
    img = np.stack([img, img, img], axis=-1)
    dirty = img.copy()
    dirty[18:22, 20:60] = 0
    mask = np.zeros((h, w), dtype=np.float32)
    mask[18:22, 20:60] = 1.0
    out = inpaint(dirty, mask, method="telea", radius=3)
    err = np.abs(out[19:21, 25:55].astype(np.int16) - img[19:21, 25:55].astype(np.int16)).mean()
    assert err < 4


def test_skin_identity() -> None:
    img = np.random.default_rng(3).integers(0, 255, (32, 32, 3), dtype=np.uint8)
    out = skin_retouch(img, smooth=0, sharpen=0)
    assert np.array_equal(out, img)


def test_skin_smooth_reduces_noise() -> None:
    rng = np.random.default_rng(4)
    base = np.full((64, 64, 3), 128, dtype=np.uint8)
    noisy = np.clip(base.astype(np.int16) + rng.normal(0, 25, base.shape), 0, 255).astype(np.uint8)
    out = skin_retouch(noisy, smooth=1.0, sharpen=0)
    assert noisy.std() > out.std()
