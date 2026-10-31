"""Decodificar JPG/PNG/WEBP/TIFF, aplicar orientación EXIF, BGR uint8."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

PREVIEW_MAX_SIDE = 1600


@dataclass
class ImageMeta:
    format: str
    orientation_applied: int
    has_alpha: bool
    icc: bool
    width: int
    height: int
    image_sha1: str
    source_name: str
    exif: bytes = b""
    icc_profile: bytes | None = None
    warnings: list[str] = field(default_factory=list)


def _pil_to_bgr(im: Image.Image) -> np.ndarray:
    if im.mode == "RGBA":
        arr = np.array(im)
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
    if im.mode == "LA":
        arr = np.array(im.convert("RGBA"))
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
    rgb = im.convert("RGB")
    arr = np.array(rgb)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def decode_image(data: bytes, source_name: str = "upload") -> tuple[np.ndarray, ImageMeta]:
    try:
        im = Image.open(BytesIO(data))
        if im.width * im.height > 100_000_000:
            raise ValueError("imagen supera 100 MP")
        im.load()
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("formato no decodificable") from exc
    fmt = (im.format or "UNKNOWN").upper()
    if fmt not in {"JPEG", "JPG", "PNG", "WEBP", "TIFF", "MPO"}:
        raise ValueError("formato no admitido; usar JPG, PNG, WEBP o TIFF")
    orientation = 1
    try:
        exif = im.getexif()
        orientation = int(exif.get(0x0112, 1) or 1)
    except Exception:  # noqa: BLE001
        orientation = 1
    icc_profile = im.info.get("icc_profile")
    icc = icc_profile is not None
    warnings = []
    has_alpha = im.mode in {"RGBA", "LA"} or (im.mode == "P" and "transparency" in im.info)
    im = ImageOps.exif_transpose(im)
    metadata = im.getexif()
    metadata[0x0112] = 1
    # Rebuilding the Exif object below prevents embedded thumbnail reuse.
    clean = Image.Exif()
    for key, value in metadata.items():
        if key not in {0x0201, 0x0202}:
            clean[key] = metadata.get_ifd(key) if key in {0x8825, 0x8769} else value
    if im.mode in {"I;16", "I;16B", "I;16L", "I", "F"}:
        arr = np.asarray(im).astype(np.float32)
        if im.mode != "F":
            arr = arr / 257.
        else:
            arr = arr*255 if arr.max()<=1 else arr
        im = Image.fromarray(np.clip(arr,0,255).astype(np.uint8)).convert("RGB")
        warnings.append("BIT_DEPTH_16_TO_8")
    if im.mode == "P" and has_alpha:
        im = im.convert("RGBA")
    bgr = _pil_to_bgr(im)
    h, w = bgr.shape[:2]
    sha1 = hashlib.sha1(data).hexdigest()
    meta = ImageMeta(
        format="JPEG" if fmt in {"JPG", "MPO"} else fmt,
        orientation_applied=orientation,
        has_alpha=has_alpha and (bgr.shape[2] == 4 if bgr.ndim == 3 else False),
        icc=icc,
        width=w,
        height=h,
        image_sha1=sha1,
        source_name=Path(source_name).name,
        exif=clean.tobytes(), icc_profile=icc_profile, warnings=warnings,
    )
    return bgr, meta


def load_path(path: Path) -> tuple[np.ndarray, ImageMeta]:
    data = path.read_bytes()
    return decode_image(data, source_name=path.name)


def make_preview(img: np.ndarray, max_side: int = PREVIEW_MAX_SIDE) -> np.ndarray:
    h, w = img.shape[:2]
    side = max(h, w)
    if side <= max_side:
        return img.copy()
    scale = max_side / side
    nw, nh = int(round(w * scale)), int(round(h * scale))
    return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
