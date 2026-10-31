"""Deterministic exemplar fill with confidence × isophote priority (Criminisi).

CPU implementation for small selections. Source patches never include the
original hole. Large selections should use Telea; this path bounds candidates.
"""
import cv2
import numpy as np


def exemplar_inpaint(img,mask,radius=3):
    original_hole=mask>.5
    if not original_hole.any():
        return img.copy()
    h,w=mask.shape
    r=min(radius,(h-1)//2,(w-1)//2)
    if r<1 or original_hole.all():
        raise ValueError('exemplar necesita píxeles fuente alrededor de la selección')
    side=2*r+1
    valid=cv2.dilate(original_hole.astype(np.uint8),np.ones((side,side),np.uint8))==0
    valid[:r]=False;valid[-r:]=False;valid[:,:r]=False;valid[:,-r:]=False
    candidates=np.argwhere(valid)
    if not len(candidates):
        raise ValueError('no hay parches fuente completos')
    candidates=candidates[::max(1,int(np.ceil(len(candidates)/2048)))]
    source=img[:,:,:3].astype(np.float32)
    out=source.copy(); hole=original_hole.copy(); confidence=(~hole).astype(np.float32)
    patches=np.stack([source[y-r:y+r+1,x-r:x+r+1] for y,x in candidates])
    while hole.any():
        boundary=hole & (cv2.dilate((~hole).astype(np.uint8),np.ones((3,3),np.uint8))>0)
        ys,xs=np.where(boundary)
        if not len(ys):
            raise ValueError('selección sin frontera utilizable')
        gray=cv2.cvtColor(out,cv2.COLOR_BGR2GRAY)
        gy,gx=np.gradient(gray); ny,nx=np.gradient(hole.astype(np.float32))
        scores=[]
        for y,x in zip(ys,xs):
            y0,y1=max(0,y-r),min(h,y+r+1);x0,x1=max(0,x-r),min(w,x+r+1)
            c=confidence[y0:y1,x0:x1].mean()
            data=abs(-gy[y,x]*nx[y,x]+gx[y,x]*ny[y,x])/255+1e-3
            scores.append(c*data)
        chosen=int(np.argmax(scores)); y,x=int(ys[chosen]),int(xs[chosen])
        y0,y1=max(0,y-r),min(h,y+r+1);x0,x1=max(0,x-r),min(w,x+r+1)
        target=out[y0:y1,x0:x1]; unknown=hole[y0:y1,x0:x1]
        subset=patches[:,y0-y+r:y1-y+r,x0-x+r:x1-x+r]
        known=(~unknown)[None,:,:,None]
        errors=((subset-target)**2*known).sum(axis=(1,2,3))
        best=subset[int(np.argmin(errors))]
        c=float(confidence[y0:y1,x0:x1].mean())
        target[unknown]=best[unknown]
        confidence[y0:y1,x0:x1][unknown]=c
        hole[y0:y1,x0:x1]=False
    bgr=np.clip(out,0,255).astype(np.uint8)
    return np.dstack((bgr,img[:,:,3])) if img.shape[2]==4 else bgr
