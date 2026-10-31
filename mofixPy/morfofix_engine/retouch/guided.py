"""Gray-guide edge-preserving filter, implemented with OpenCV box filters."""
import cv2
import numpy as np


def guided_filter(guide, source, radius=4, eps=.02**2):
    guide = guide.astype(np.float32)
    source = source.astype(np.float32)
    if guide.ndim == 3:
        guide = cv2.cvtColor(guide[:,:,:3], cv2.COLOR_BGR2GRAY)
    size = (2*int(radius)+1,)*2
    box = lambda x: cv2.boxFilter(x, -1, size, borderType=cv2.BORDER_REFLECT)
    mean_i = box(guide)
    var = box(guide*guide)-mean_i*mean_i
    def channel(p):
        mean_p = box(p)
        cov = box(guide*p)-mean_i*mean_p
        a = cov/(var+eps)
        b = mean_p-a*mean_i
        return box(a)*guide+box(b)
    if source.ndim == 2:
        return channel(source)
    return np.stack([channel(source[:,:,i]) for i in range(source.shape[2])], axis=-1)


def refine_mask(image, mask):
    h,w = image.shape[:2]
    mask = cv2.resize(mask.astype(np.float32), (w,h))
    return np.clip(guided_filter(image[:,:,:3].astype(np.float32)/255, mask, max(2,round(.006*min(h,w)))),0,1)
