"""Head-field attenuation and inpainted background plate composition."""
import cv2
import numpy as np
from morfofix_engine.retouch.guided import refine_mask
from morfofix_engine.warps.field import to_maps


def head_mask(h,w,faces,bodies=()):
    y,x = np.indices((h,w),dtype=np.float32)
    result = np.zeros((h,w),np.float32)
    boxes = [f.bbox for f in faces]
    if not boxes:
        for b in bodies:
            p=b.keypoints[:11,:2]
            boxes.append((*p.min(axis=0),*p.max(axis=0)))
    for x0,y0,x1,y1 in boxes:
        cx,cy=(x0+x1)*w/2,(y0+y1)*h/2
        rx,ry=max((x1-x0)*w*.65,1),max((y1-y0)*h*.65,1)
        radius=np.hypot((x-cx)/rx,(y-cy)/ry)
        result=np.maximum(result,np.clip((1-radius)/.15,0,1))
    return result


def background_plate(img, mask):
    h,w=img.shape[:2]
    ratio=min(1,1024/max(h,w))
    size=(max(1,round(w*ratio)),max(1,round(h*ratio)))
    small=cv2.resize(img[:,:,:3],size,interpolation=cv2.INTER_AREA)
    m=cv2.resize(mask,size)
    r=max(1,round(12*ratio))
    hole=cv2.dilate((m>.05).astype(np.uint8),np.ones((2*r+1,2*r+1),np.uint8))
    if np.all(hole):
        return img.copy()
    plate=cv2.inpaint(small,hole,5,cv2.INPAINT_TELEA)
    plate=cv2.resize(plate,(w,h))
    full_hole=cv2.dilate((mask>.05).astype(np.uint8),np.ones((25,25),np.uint8))
    plate=np.where(full_hole[...,None]>0,plate,img[:,:,:3])
    if img.shape[2]==4:
        plate=np.dstack((plate,img[:,:,3]))
    return plate


def composite_background(img, warped, mask, field, cache=None):
    import hashlib
    from morfofix_engine.inference.cache import InferenceCache
    key=InferenceCache.key(hashlib.sha1(img.tobytes()).hexdigest(),str(img.shape),'background-v1','',hashlib.sha256(mask.tobytes()).hexdigest())
    cached=cache.get(key) if cache else None
    if cached is None:
        mask=refine_mask(img,mask)
        plate=background_plate(img,mask)
        if cache:
            cache.put_memory(key,mask=mask,plate=plate)
    else:
        mask,plate=cached['mask'],cached['plate']
    x,y=to_maps(field)
    moved=cv2.remap(mask,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    if plate.shape[:2]!=warped.shape[:2]:
        plate=cv2.resize(plate,(warped.shape[1],warped.shape[0]))
    return np.clip(warped.astype(np.float32)*moved[...,None]+plate*(1-moved[...,None]),0,255).astype(np.uint8)
