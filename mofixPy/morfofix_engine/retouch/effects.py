"""Landmark-local retouch; own formulas, preserving alpha and unaffected pixels."""
import cv2
import numpy as np
from morfofix_engine.face.landmark_map import GROUPS
from morfofix_engine.inference.segment import face_skin_polygon
from morfofix_engine.retouch.guided import guided_filter
from morfofix_engine.body.freeze import rasterize_strokes
from morfofix_engine.core.state import BrushStroke


def polygon_mask(lm, indices, h, w):
    mask=np.zeros((h,w),np.float32)
    p=(lm[list(indices),:2]*[w-1,h-1]).astype(np.int32)
    cv2.fillConvexPoly(mask,cv2.convexHull(p),1)
    return mask


def apply_retouch(img, faces, settings, skin_mask=None):
    h,w=img.shape[:2]
    original=img[:,:,:3].astype(np.float32)/255
    out=original.copy()
    skin=np.zeros((h,w),np.float32)
    teeth=skin.copy(); eyes=skin.copy(); iris=skin.copy(); circles=skin.copy()
    for face in faces:
        lm=face.landmarks
        skin=np.maximum(skin,face_skin_polygon(lm,h,w))
        teeth=np.maximum(teeth,polygon_mask(lm,GROUPS['LIPS_INNER'],h,w))
        for side in ('L','R'):
            eye=polygon_mask(lm,GROUPS['EYES_'+side],h,w)
            eyes=np.maximum(eyes,eye)
            if len(lm)>=478:
                center=lm[473 if side=='L' else 468,:2]*[w-1,h-1]
                points=lm[list(GROUPS['IRIS_'+side])[1:],:2]*[w-1,h-1]
                radius=max(1,float(np.linalg.norm(points-center,axis=1).mean()))
                cv2.circle(iris,tuple(np.rint(center).astype(int)),round(radius),1,-1)
            p=lm[list(GROUPS['EYES_'+side]),:2]*[w-1,h-1]
            center=p.mean(axis=0); size=np.ptp(p,axis=0)
            cv2.ellipse(circles,(round(center[0]),round(center[1]+size[1])),(max(1,round(size[0]/2)),max(1,round(size[1]))),0,0,360,1,-1)
    if skin_mask is not None:
        skin *= np.clip(skin_mask,0,1)
    skin=np.clip(cv2.GaussianBlur(skin,(0,0),max(.5,.002*min(h,w))),0,1)
    def mask_for(name, base):
        if name in settings.brush:
            strokes=[BrushStroke(s.pts,s.radius,s.erase) for s in settings.brush[name].strokes]
            if strokes:
                # Con pincel manda lo pintado: antes era base*trazos y, sin cara detectada
                # (fotos de cuerpo entero), base=0 y el pincel no hacía nada.
                return rasterize_strokes(strokes,h,w)
            return base
        return base
    def blend(name, processed, base):
        nonlocal out
        amount=getattr(settings,name)
        if amount:
            mask=mask_for(name,base)[...,None]*amount
            out=out*(1-mask)+processed*mask
    radius=max(2,round(.006*min(h,w)))
    if settings.degree_skin_smooth:
        smooth=guided_filter(original,original,radius)
        gray=cv2.cvtColor(original,cv2.COLOR_BGR2GRAY)
        var=cv2.boxFilter(gray*gray,-1,(5,5))-cv2.boxFilter(gray,-1,(5,5))**2
        k=.02**2/(var+.02**2)
        # Preserve high frequencies where local detail is significant.
        detail=original-cv2.GaussianBlur(original,(0,0),1.5)
        blend('degree_skin_smooth',np.clip(smooth+detail*(1-k[...,None]),0,1),skin)
    lab=cv2.cvtColor(out,cv2.COLOR_BGR2LAB)
    white=lab.copy(); white[:,:,0]+=(100-white[:,:,0])*.15
    blend('degree_whiten_skin',cv2.cvtColor(white,cv2.COLOR_LAB2BGR),skin)
    for name,amount in [('degree_skin_details',.6),('degree_skin_texture',.3),('degree_sharpen',.71)]:
        detail=out-cv2.GaussianBlur(out,(0,0),1.5)
        blend(name,np.clip(out+amount*detail,0,1),np.ones((h,w),np.float32) if name=='degree_sharpen' else skin)
    matte=cv2.cvtColor(out,cv2.COLOR_BGR2LAB); matte[:,:,0]-=np.maximum(matte[:,:,0]-75,0)*.25
    blend('degree_skin_matte',cv2.cvtColor(matte,cv2.COLOR_LAB2BGR),skin)
    if np.any(teeth):
        lab=cv2.cvtColor(out,cv2.COLOR_BGR2LAB)
        hsv=cv2.cvtColor(out,cv2.COLOR_BGR2HSV)
        threshold=np.percentile(lab[:,:,0][teeth>.5],40)
        tooth=teeth*(lab[:,:,0]>threshold)*(hsv[:,:,1]<.45)
        corrected=lab.copy()
        mini=cv2.resize(hsv[:,:,1],(100,100))
        if np.mean(mini<=.1)<=.5:
            corrected[:,:,2]-=np.maximum(corrected[:,:,2],0)*.6
        corrected[:,:,0]+=(100-corrected[:,:,0])*.12
        blend('degree_whiten_teeth',cv2.cvtColor(corrected,cv2.COLOR_LAB2BGR),tooth)
    lab=cv2.cvtColor(out,cv2.COLOR_BGR2LAB)
    bright=lab.copy(); bright[:,:,0]+=(100-bright[:,:,0])*.25
    blend('degree_brighten_eyes',cv2.cvtColor(bright,cv2.COLOR_LAB2BGR),eyes)
    blend('degree_whiten_eyes',cv2.cvtColor(bright,cv2.COLOR_LAB2BGR),eyes*(1-iris))
    hsv=cv2.cvtColor(out,cv2.COLOR_BGR2HSV)
    red=((hsv[:,:,0]<20)|(hsv[:,:,0]>340)).astype(np.float32)
    hsv[:,:,1]*=(1-red*.8)
    blend('degree_remove_eye_redness',cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR),eyes*(1-iris))
    if np.any(skin>.5):
        lab=cv2.cvtColor(out,cv2.COLOR_BGR2LAB)
        reference=float(np.median(lab[:,:,0][skin>.5]))
        lab[:,:,0]+=np.maximum(reference-lab[:,:,0],0)*.6
        blend('degree_dark_circles',cv2.cvtColor(lab,cv2.COLOR_LAB2BGR),circles*skin)
    from morfofix_engine.retouch.blemish import remove_blemishes, reduce_wrinkles
    if settings.degree_remove_blemishes:
        current=np.clip(out*255,0,255).astype(np.uint8)
        out=remove_blemishes(current,mask_for('degree_remove_blemishes',skin),settings.degree_remove_blemishes).astype(np.float32)/255
    if settings.degree_wrinkles:
        roi=np.zeros((h,w),np.float32)
        for face in faces:
            roi=np.maximum(roi,polygon_mask(face.landmarks,GROUPS['FOREHEAD'],h,w))
        roi=np.maximum(roi,circles)*skin
        current=np.clip(out*255,0,255).astype(np.uint8)
        out=reduce_wrinkles(current,mask_for('degree_wrinkles',roi),settings.degree_wrinkles).astype(np.float32)/255
    bgr=np.clip(np.rint(out*255),0,255).astype(np.uint8)
    return np.dstack((bgr,img[:,:,3])) if img.shape[2]==4 else bgr
