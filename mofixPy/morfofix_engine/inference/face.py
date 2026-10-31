"""MediaPipe IMAGE detection, <=2048 working copy, tile rescue and content cache."""
from dataclasses import dataclass
import hashlib
import cv2
import numpy as np
from morfofix_engine.inference.cache import InferenceCache


@dataclass(frozen=True)
class Face:
    index:int
    bbox:tuple[float,float,float,float]
    score:float
    landmarks:np.ndarray
    euler:tuple[float,float,float]|None=None


def euler_angles(matrix):
    # Remove scale and numerical shear before decomposing rotation.
    u,_,vh=np.linalg.svd(np.asarray(matrix)[:3,:3])
    r=u@vh
    if np.linalg.det(r)<0:
        u[:,-1]*=-1; r=u@vh
    pitch=np.arctan2(r[2,1],r[2,2])
    yaw=np.arctan2(-r[2,0],np.hypot(r[0,0],r[1,0]))
    roll=np.arctan2(r[1,0],r[0,0])
    return tuple(float(v) for v in np.rad2deg([yaw,pitch,roll]))


def _iou(a,b):
    x=max(0,min(a[2],b[2])-max(a[0],b[0])); y=max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=lambda p:max(0,p[2]-p[0])*max(0,p[3]-p[1])
    return x*y/max(area(a)+area(b)-x*y,1e-10)


def head_boxes_from_bodies(bodies,h,w,*,mult=2.0,min_vis=.5):
    """Recortes cuadrados de cabeza (px) guiados por pose: centro = media de nariz y orejas
    visibles (kp 0, 7, 8); medio lado = mult × distancia entre orejas (o 0.6 × hombros)."""
    boxes=[]
    for b in bodies or []:
        k=np.asarray(getattr(b,'keypoints',None) if not isinstance(b,np.ndarray) else b,np.float32)
        if k.shape!=(33,4):
            continue
        idx=[i for i in (0,7,8) if k[i,3]>=min_vis]
        if not idx:
            continue
        cx=float(np.mean(k[idx,0]))*w; cy=float(np.mean(k[idx,1]))*h
        ears=np.hypot((k[7,0]-k[8,0])*w,(k[7,1]-k[8,1])*h) if min(k[7,3],k[8,3])>=min_vis else 0.
        sh=np.hypot((k[11,0]-k[12,0])*w,(k[11,1]-k[12,1])*h) if min(k[11,3],k[12,3])>=min_vis else 0.
        half=max(mult*ears,.6*sh,24.)
        x0,y0=max(0,int(cx-half)),max(0,int(cy-half)); x1,y1=min(w,int(cx+half)),min(h,int(cy+half))
        if x1-x0>=32 and y1-y0>=32:
            boxes.append((x0,y0,x1,y1))
    return boxes


def detect_faces(img_bgr,registry,*,max_faces=5,min_det_conf=.6,small_face_rescue=True,head_boxes=None):
    path=registry.require('face_landmarker')
    cache=getattr(registry,'cache',None)
    model_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    key=InferenceCache.key(hashlib.sha1(img_bgr.tobytes()).hexdigest(),str(img_bgr.shape),'face',model_hash,[max_faces,min_det_conf,small_face_rescue,[list(map(int,b)) for b in (head_boxes or [])]])
    if cache:
        found=cache.get(key)
        if found is not None:
            return [Face(i,tuple(box),1.,lm,tuple(angles)) for i,(box,lm,angles) in enumerate(zip(found['boxes'],found['points'],found['angles']))]
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options as bo
    options=vision.FaceLandmarkerOptions(base_options=bo.BaseOptions(model_asset_path=str(path)),running_mode=vision.RunningMode.IMAGE,num_faces=max_faces,min_face_detection_confidence=min_det_conf,min_face_presence_confidence=.5,output_face_blendshapes=False,output_facial_transformation_matrixes=True)
    h,w=img_bgr.shape[:2]
    candidates=[]
    with vision.FaceLandmarker.create_from_options(options) as detector:
        def scan(x0,y0,x1,y1):
            patch=img_bgr[y0:y1,x0:x1,:3]
            ratio=min(1,2048/max(patch.shape[:2]))
            if ratio<1:
                patch=cv2.resize(patch,(max(1,round(patch.shape[1]*ratio)),max(1,round(patch.shape[0]*ratio))))
            image=mp.Image(image_format=mp.ImageFormat.SRGB,data=patch[:,:,::-1].copy())
            result=detector.detect(image)
            matrices=result.facial_transformation_matrixes
            for i,landmarks in enumerate(result.face_landmarks or []):
                pts=np.array([[p.x,p.y,p.z] for p in landmarks],np.float32)
                pts[:,0]=(pts[:,0]*(x1-x0)+x0)/w
                pts[:,1]=(pts[:,1]*(y1-y0)+y0)/h
                pts[:,2]*=(x1-x0)/w
                box=(*pts[:,:2].min(axis=0),*pts[:,:2].max(axis=0))
                angles=euler_angles(matrices[i]) if i<len(matrices) else (0.,0.,0.)
                candidates.append(Face(0,box,1.,pts,angles))
        scan(0,0,w,h)
        if small_face_rescue and len(candidates)<max_faces and min(h,w)>64:
            # Two tiles per axis, overlap 15% of full dimension.
            for x0,x1 in ((0,round(w*.575)),(round(w*.425),w)):
                for y0,y1 in ((0,round(h*.575)),(round(h*.425),h)):
                    scan(x0,y0,x1,y1)
        if head_boxes and len(candidates)<max_faces:
            # Rescate guiado por pose: en fotos de cuerpo entero la cara es chica y ni los
            # tiles de 57.5% la encuentran; un recorte centrado en la cabeza sí.
            for x0,y0,x1,y1 in head_boxes:
                scan(int(x0),int(y0),int(x1),int(y1))
    kept=[]
    for face in candidates:
        if all(_iou(face.bbox,other.bbox)<.4 for other in kept):
            kept.append(face)
    kept=sorted(kept[:max_faces],key=lambda f:f.bbox[0])
    result=[Face(i,f.bbox,f.score,f.landmarks,f.euler) for i,f in enumerate(kept)]
    if cache:
        cache.put(key,boxes=np.array([f.bbox for f in result]),points=np.array([f.landmarks for f in result]),angles=np.array([f.euler for f in result]))
    return result
