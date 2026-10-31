"""Export PNG/JPEG/WEBP/TIFF a ruta absoluta."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tempfile

import cv2
import numpy as np
from PIL import Image


@dataclass
class ExportResult:
    path: str
    width: int
    height: int
    bytes: int
    ms: float


def export_image(
    img: np.ndarray,
    path: Path,
    *,
    fmt: str = "png",
    quality: int = 92,
    metadata=None,
    keep_metadata: bool = True,
    keep_gps: bool = False,
) -> ExportResult:
    if not 1 <= quality <= 100:
        raise ValueError("quality fuera de rango")
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("la ruta de export debe ser absoluta")
    if not path.parent.is_dir():
        raise ValueError("el directorio de destino no existe")
    fmt = fmt.lower()
    expected = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp", ".tif": "tiff", ".tiff": "tiff"}
    suf = path.suffix.lower()
    if suf not in expected or expected[suf] != fmt:
        raise ValueError("la extensión no coincide con el formato")
    if img.ndim == 3 and img.shape[2] == 4:
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))
    else:
        pil = Image.fromarray(cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2RGB))
    save_kw: dict = {}
    if fmt == "jpeg":
        pil = pil.convert("RGB")
        save_kw["quality"] = int(np.clip(quality, 1, 100))
        save_kw["subsampling"] = 0 if quality >= 95 else 2
    elif fmt == "png":
        save_kw["compress_level"] = 6
    elif fmt == "webp":
        save_kw["quality"] = int(np.clip(quality, 1, 100))
    if keep_metadata and metadata is not None:
        exif = Image.Exif()
        if metadata.exif:
            exif.load(metadata.exif)
        if not keep_gps:
            exif.pop(0x8825, None)
        exif.pop(0x0201, None)
        exif.pop(0x0202, None)
        exif[0x0112] = 1
        save_kw["exif"] = exif.tobytes()
        if metadata.icc_profile:
            save_kw["icc_profile"] = metadata.icc_profile
    t0 = __import__("time").perf_counter()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".morfofix-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            pil.save(stream, format=fmt.upper() if fmt != "jpeg" else "JPEG", **save_kw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    ms = (__import__("time").perf_counter() - t0) * 1000
    return ExportResult(
        path=str(path),
        width=pil.size[0],
        height=pil.size[1],
        bytes=path.stat().st_size,
        ms=ms,
    )
