from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from morfofix_engine.app import create_app
from morfofix_engine.face.landmark_map import synthetic_landmarks
from morfofix_engine.inference.face import Face

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"


@pytest.fixture
def app():
    return create_app(models_dir=MODELS)


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as client:
        yield client


@pytest.fixture
def synthetic_face() -> np.ndarray:
    return synthetic_landmarks(400, 500)


@pytest.fixture
def rgb_png(tmp_path: Path) -> Path:
    p = tmp_path / "plain.png"
    Image.fromarray(np.full((60, 80, 3), 120, dtype=np.uint8)).save(p)
    return p


def make_face(lm: np.ndarray, index: int = 0) -> Face:
    xs, ys = lm[:, 0], lm[:, 1]
    bbox = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
    return Face(index=index, bbox=bbox, score=1.0, landmarks=lm, euler=None)
