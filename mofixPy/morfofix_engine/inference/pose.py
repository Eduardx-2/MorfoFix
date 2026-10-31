"""Pose 33 keypoints + máscara opcional [RE contrato / MP mínimo]."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morfofix_engine.inference.models import ModelRegistry


@dataclass(frozen=True)
class Body:
    index: int
    bbox: tuple[float, float, float, float]
    score: float
    keypoints: np.ndarray  # (33, 4) x,y,z,visibility
    seg_mask: np.ndarray | None


def _as_2d_mask(m):
    m = np.asarray(m, dtype=np.float32)
    if m.ndim == 3 and m.shape[2] == 1:
        m = m[:, :, 0]
    if m.ndim != 2:
        raise ValueError(f"máscara de pose con forma inesperada {m.shape}")
    return m


def _detect_bodies(
    img_bgr: np.ndarray,
    registry: ModelRegistry,
    *,
    max_people: int = 3,
    min_det_conf: float = 0.6,
    with_mask: bool = True,
) -> list[Body]:
    path = registry.require("pose_landmarker_full")
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core import base_options as bo
    except ImportError as exc:
        raise RuntimeError("mediapipe no instalado") from exc

    options = vision.PoseLandmarkerOptions(
        base_options=bo.BaseOptions(model_asset_path=str(path)),
        running_mode=vision.RunningMode.IMAGE,
        num_poses=max_people,
        min_pose_detection_confidence=min_det_conf,
        output_segmentation_masks=with_mask,
    )
    rgb = img_bgr[:, :, :3][:, :, ::-1].copy()
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    h, w = rgb.shape[:2]
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp_image)
    bodies: list[Body] = []
    poses = result.pose_landmarks or []
    masks = result.segmentation_masks if with_mask else None
    for i, lm_list in enumerate(poses):
        kps = np.array(
            [[p.x, p.y, p.z, getattr(p, "visibility", 1.0)] for p in lm_list],
            dtype=np.float32,
        )
        vis = kps[:, 3] > 0.5
        use = kps[vis] if np.any(vis) else kps
        bbox = (
            float(use[:, 0].min()),
            float(use[:, 1].min()),
            float(use[:, 0].max()),
            float(use[:, 1].max()),
        )
        mask = None
        if masks is not None and i < len(masks):
            m = _as_2d_mask(masks[i].numpy_view())
            if m.shape[:2] != (h, w):
                import cv2

                m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
            mask = m
        bodies.append(Body(index=i, bbox=bbox, score=float(kps[:, 3].mean()), keypoints=kps, seg_mask=mask))
    return bodies


def detect_bodies(img_bgr, registry, *, max_people=3, min_det_conf=.6, with_mask=True):
    import hashlib
    from morfofix_engine.inference.cache import InferenceCache
    path=registry.require("pose_landmarker_full")
    cache=getattr(registry,"cache",None)
    key=InferenceCache.key(hashlib.sha1(img_bgr.tobytes()).hexdigest(),str(img_bgr.shape),"pose-v2",hashlib.sha256(path.read_bytes()).hexdigest(),[max_people,min_det_conf,with_mask])
    if cache:
        found=cache.get(key)
        if found is not None:
            out=[]
            for i,(box,score,points) in enumerate(zip(found['boxes'],found['scores'],found['points'])):
                mask=found.get(f"mask_{i}")
                out.append(Body(i,tuple(box),float(score),points,_as_2d_mask(mask) if mask is not None else None))
            return out
    import cv2
    h,w=img_bgr.shape[:2]
    ratio=min(1,2048/max(h,w))
    working=cv2.resize(img_bgr,(max(1,round(w*ratio)),max(1,round(h*ratio)))) if ratio<1 else img_bgr
    result=_detect_bodies(working,registry,max_people=max_people,min_det_conf=min_det_conf,with_mask=with_mask)
    if cache:
        arrays={'boxes':np.array([b.bbox for b in result]),'scores':np.array([b.score for b in result]),'points':np.array([b.keypoints for b in result])}
        arrays.update({f'mask_{i}':b.seg_mask for i,b in enumerate(result) if b.seg_mask is not None})
        cache.put(key,**arrays)
    return result
