"""Own non-neural blemish and wrinkle reductions within explicit skin ROIs."""
import cv2
import numpy as np


def remove_blemishes(img,mask,amount=1):
    gray=cv2.cvtColor(img[:,:,:3],cv2.COLOR_BGR2GRAY).astype(np.float32)
    dog=cv2.GaussianBlur(gray,(0,0),1)-cv2.GaussianBlur(gray,(0,0),4)
    samples=dog[mask>.5]
    if not len(samples):
        return img
    threshold=min(-3.,float(samples.mean()-1.5*samples.std()))
    spots=((dog<threshold)&(mask>.5)).astype(np.uint8)
    count,labels,stats,_=cv2.connectedComponentsWithStats(spots)
    holes=np.zeros_like(spots)
    for label in range(1,count):
        _,_,w,h,area=stats[label]
        if 2<=w<=12 and 2<=h<=12 and area>=3:
            holes[labels==label]=1
    from morfofix_engine.retouch.inpaint import inpaint
    fixed=inpaint(img,holes.astype(np.float32))
    return np.clip(img.astype(np.float32)*(1-amount)+fixed*amount,0,255).astype(np.uint8)


def reduce_wrinkles(img,mask,amount=1):
    bgr=img[:,:,:3].astype(np.float32)
    low=cv2.GaussianBlur(bgr,(0,0),2)
    high=bgr-low
    corrected=low+high*(1-.6*amount*mask[...,None])
    result=np.clip(corrected,0,255).astype(np.uint8)
    return np.dstack((result,img[:,:,3])) if img.shape[2]==4 else result
