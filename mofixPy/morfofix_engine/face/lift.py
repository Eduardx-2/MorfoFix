"""Facelift color companion and submental correction (own non-neural design)."""
import cv2
import numpy as np
from morfofix_engine.face.landmark_map import GROUPS, JAWLINE
from morfofix_engine.face.reshape import face_frame
from morfofix_engine.inference.segment import face_skin_polygon
from morfofix_engine.retouch.inpaint import inpaint

REGIONS={'eye_area':('EYES_L','EYES_R'),'brow_peak':('BROWS_L','BROWS_R'),'face_mid':('CHEEKS',),'contour':('JAWLINE',),'forehead':('FOREHEAD',),'mouth_area':('LIPS',)}


def facelift_color(img,face,params):
    h,w=img.shape[:2]
    y,x=np.indices((h,w),dtype=np.float32)
    mask=np.zeros((h,w),np.float32)
    for name,value in params.items():
        for group in REGIONS.get(name.removeprefix('intensity_facelift_'),()):
            p=face.landmarks[list(GROUPS[group]),:2]*[w-1,h-1]
            c=p.mean(axis=0);r=max(np.linalg.norm(p-c,axis=1).max()*1.5,2)
            mask=np.maximum(mask,abs(value)*np.maximum(0,1-np.hypot(x-c[0],y-c[1])/r)**2)
    mask*=face_skin_polygon(face.landmarks,h,w)
    color=img[:,:,:3].astype(np.float32)
    corrected=cv2.GaussianBlur(color,(0,0),1.5)
    corrected+=(255-corrected)*.03
    out=np.clip(color*(1-mask[...,None]*.4)+corrected*mask[...,None]*.4,0,255).astype(np.uint8)
    return np.dstack((out,img[:,:,3])) if img.shape[2]==4 else out


def double_chin(img,face,value):
    from morfofix_engine.warps.field import mls_backward_field
    from morfofix_engine.warps.mls import border_anchors
    h,w=img.shape[:2]
    xy=face.landmarks[:,:2]*[w-1,h-1]
    frame=face_frame(xy)
    jaw=xy[list(JAWLINE)]
    lower=jaw+.18*frame.half_len*frame.u
    anchors=border_anchors(h,w)
    src=np.concatenate((lower,jaw,anchors))
    dst=np.concatenate((lower-value*.12*frame.half_len*frame.u,jaw,anchors))
    f=mls_backward_field(h,w,src,dst)
    mask=np.zeros((h,w),np.float32)
    poly=np.concatenate((jaw,lower[::-1])).astype(np.int32)
    cv2.fillPoly(mask,[poly],1)
    mask=cv2.GaussianBlur(mask,(0,0),max(.5,.01*frame.half_len))
    fixed=inpaint(img,mask,method='telea',radius=5)
    mix=np.clip(abs(value)*mask,0,1)[...,None]
    result=np.clip(img*(1-mix)+fixed*mix,0,255).astype(np.uint8)
    return result,f
