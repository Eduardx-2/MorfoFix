from __future__ import annotations

import numpy as np

from morfofix_engine.face.landmark_map import EYES_L, EYES_R, JAW, synthetic_landmarks
from morfofix_engine.face.reshape import jaw_width_px, warped_landmarks


def _eye_area(lm: np.ndarray, w: int, h: int, idxs: tuple[int, ...]) -> float:
    xy = np.stack([lm[:, 0] * (w - 1), lm[:, 1] * (h - 1)], axis=1)
    pts = xy[list(idxs)]
    minx, miny = pts.min(axis=0)
    maxx, maxy = pts.max(axis=0)
    return float((maxx - minx) * (maxy - miny))


def test_jaw_slider() -> None:
    w, h = 400, 500
    lm = synthetic_landmarks(w, h)
    base = jaw_width_px(lm, w, h)
    assert abs(base - 266) < 8  # óvalo sintético ~266 px
    thin = warped_landmarks(lm, {"intensity_jaw": 0.5}, (w, h))
    fat = warped_landmarks(lm, {"intensity_jaw": -0.5}, (w, h))
    tw = jaw_width_px(thin, w, h)
    fw = jaw_width_px(fat, w, h)
    assert tw < base < fw
    assert abs(tw - 250) < 20
    assert abs(fw - 282) < 20


def test_eye_mouth_sliders() -> None:
    w, h = 400, 500
    lm = synthetic_landmarks(w, h)
    a0 = _eye_area(lm, w, h, EYES_L) + _eye_area(lm, w, h, EYES_R)
    big = warped_landmarks(lm, {"intensity_eyesize": 0.8}, (w, h))
    a1 = _eye_area(big, w, h, EYES_L) + _eye_area(big, w, h, EYES_R)
    assert a1 > a0
    from morfofix_engine.face.landmark_map import LIPS

    def _mouth_w(lm_):
        xy = np.stack([lm_[:, 0] * (w - 1), lm_[:, 1] * (h - 1)], axis=1)
        p = xy[list(LIPS)]
        return float(p[:, 0].max() - p[:, 0].min())

    assert _mouth_w(warped_landmarks(lm, {"intensity_mouthsize": 0.6}, (w, h))) > _mouth_w(lm)


def test_combined_and_lr() -> None:
    w, h = 400, 500
    lm = synthetic_landmarks(w, h)
    both = warped_landmarks(lm, {"intensity_jaw": 0.3, "intensity_eyesize": 0.2}, (w, h))
    assert not np.allclose(both[:, :2], lm[:, :2])
    left = warped_landmarks(lm, {"left_intensity_eyesize": 0.8}, (w, h))
    xy0 = np.stack([lm[:, 0] * (w - 1), lm[:, 1] * (h - 1)], axis=1)
    xyl = np.stack([left[:, 0] * (w - 1), left[:, 1] * (h - 1)], axis=1)
    d_l = np.linalg.norm(xyl[list(EYES_L)] - xy0[list(EYES_L)], axis=1).mean()
    d_r = np.linalg.norm(xyl[list(EYES_R)] - xy0[list(EYES_R)], axis=1).mean()
    assert d_l > d_r * 2
    assert len(JAW) > 0
