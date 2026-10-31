"""Máscara de persona (pose o selfie) y fallback de piel por polígono FACE_OVAL."""

from __future__ import annotations

from typing import Literal

import cv2
import numpy as np

from morfofix_engine.face.landmark_map import FACE_OVAL, BROWS_L, BROWS_R, EYES_L, EYES_R, LIPS
from morfofix_engine.inference.models import ModelRegistry
from morfofix_engine.inference.pose import detect_bodies
from morfofix_engine.retouch.guided import refine_mask


def person_mask(
    img_bgr: np.ndarray,
    registry: ModelRegistry,
    *,
    model: Literal["selfie", "pose"] = "pose",
) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    if model == "pose":
        bodies = detect_bodies(img_bgr, registry, with_mask=True)
        acc = np.zeros((h, w), dtype=np.float32)
        for b in bodies:
            if b.seg_mask is not None:
                acc = np.maximum(acc, b.seg_mask.astype(np.float32))
        if acc.max() > 0:
            return refine_mask(img_bgr, acc)
        raise FileNotFoundError("pose_mask")
    path = registry.require("selfie_segmenter")
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core import base_options as bo
    except ImportError as exc:
        raise RuntimeError("mediapipe no instalado") from exc
    options = vision.ImageSegmenterOptions(
        base_options=bo.BaseOptions(model_asset_path=str(path)),
        running_mode=vision.RunningMode.IMAGE,
        output_category_mask=False,
        output_confidence_masks=True,
    )
    rgb = img_bgr[:, :, :3][:, :, ::-1].copy()
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    with vision.ImageSegmenter.create_from_options(options) as seg:
        result = seg.segment(mp_image)
    # confianza de persona: suele ser el canal 1
    masks = result.confidence_masks
    m = np.asarray(masks[-1].numpy_view(), dtype=np.float32)
    if m.shape[:2] != (h, w):
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
    return refine_mask(img_bgr, m)


def face_skin_polygon(lm_norm: np.ndarray, h: int, w: int) -> np.ndarray:
    """Fallback [RE]: polígono FACE_OVAL menos ojos/labios/cejas."""
    mask = np.zeros((h, w), dtype=np.uint8)

    def _poly(indices: tuple[int, ...]) -> np.ndarray:
        pts = np.stack(
            [
                lm_norm[list(indices), 0] * (w - 1),
                lm_norm[list(indices), 1] * (h - 1),
            ],
            axis=1,
        ).astype(np.int32)
        return pts

    cv2.fillConvexPoly(mask, cv2.convexHull(_poly(FACE_OVAL)), 255)
    for g in (EYES_L, EYES_R, LIPS, BROWS_L, BROWS_R):
        hull = cv2.convexHull(_poly(g))
        cv2.fillConvexPoly(mask, hull, 0)
    return mask.astype(np.float32) / 255.0


def multiclass_masks(img_bgr, registry):
    """Official classes: background, hair, body-skin, face-skin, clothes, others."""
    import hashlib
    from morfofix_engine.inference.cache import InferenceCache
    path=registry.require('selfie_multiclass')
    cache=getattr(registry,'cache',None)
    key=InferenceCache.key(hashlib.sha1(img_bgr.tobytes()).hexdigest(),str(img_bgr.shape),'multiclass',hashlib.sha256(path.read_bytes()).hexdigest(),{})
    if cache:
        found=cache.get(key)
        if found is not None:
            return found
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options as bo
    options=vision.ImageSegmenterOptions(base_options=bo.BaseOptions(model_asset_path=str(path)),running_mode=vision.RunningMode.IMAGE,output_category_mask=False,output_confidence_masks=True)
    h,w=img_bgr.shape[:2]
    ratio=min(1,2048/max(h,w))
    small=cv2.resize(img_bgr[:,:,:3],(max(1,round(w*ratio)),max(1,round(h*ratio)))) if ratio<1 else img_bgr[:,:,:3]
    with vision.ImageSegmenter.create_from_options(options) as seg:
        result=seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB,data=small[:,:,::-1].copy()))
        masks=[np.array(m.numpy_view(),copy=True,dtype=np.float32) for m in result.confidence_masks]
    if len(masks)!=6:
        raise ValueError('el modelo multiclass debe devolver seis clases')
    out={name:refine_mask(img_bgr,masks[i]) for i,name in enumerate(('background','hair','body_skin','face_skin','clothes','others'))}
    out['person']=1-out['background']
    if cache:
        cache.put(key,**out)
    return out
