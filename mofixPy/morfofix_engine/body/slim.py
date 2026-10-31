"""Pose-anchored contour controls. Strengths are MorfoFix design estimates."""
import numpy as np
from morfofix_engine.warps.mls import border_anchors
from morfofix_engine.warps.field import mls_backward_field, identity, compose, radial_push, local_scale, Field
from morfofix_engine.face.catalog import split_lr


def pose_zones(kp):
    shoulder = (kp[11,:2]+kp[12,:2])/2
    hip = (kp[23,:2]+kp[24,:2])/2
    return {"neck": (shoulder+kp[0,:2])/2,
            "waist": shoulder*.38+hip*.62, "belly": shoulder*.2+hip*.8,
            "chest": shoulder*.72+hip*.28}


def body_field(h, w, bodies, params, grid_step=8, warnings=None):
    extra = identity(h,w)
    src, dst = [border_anchors(h, w)], [border_anchors(h, w)]
    for index, values in params.items():
        body = bodies[int(index)]
        kp = body.keypoints
        zones = pose_zones(kp)
        shoulder = (kp[11,:2]+kp[12,:2])/2
        hip = (kp[23,:2]+kp[24,:2])/2
        factor = values.get("intensity_bodyslim", 1.)
        # Combine each global + anatomical side before clipping, as for face.
        effective={}
        for base in {split_lr(k)[0] for k in values}:
            from morfofix_engine.body.catalog import BODY_PARAMS
            spec=BODY_PARAMS.get(base)
            if spec and spec.lr:
                for side_name in ('left','right'):
                    effective[side_name+'_'+base]=float(np.clip(values.get(base,0)+values.get(side_name+'_'+base,0),-1,1))
            else:
                effective[base]=values.get(base,0)
        for raw, value in effective.items():
            name, side = split_lr(raw)
            short = name.removeprefix("intensity_bodyslim_")
            if not value or short == "intensity_bodyslim":
                continue
            torso_needed = short in {
                "waistthin", "bellythin", "hipplump", "shoulderbroad", "neckwidth",
                "hiplift", "shoulderrightangle", "breastenlarge", "chest",
            }
            if torso_needed and min(float(kp[i, 3]) for i in (11, 12, 23, 24)) < .5:
                if warnings is not None and "TORSO_UNAVAILABLE" not in warnings:
                    warnings.append("TORSO_UNAVAILABLE")
                continue
            value *= factor
            segments = []
            shoulder_width=max(np.linalg.norm((kp[11,:2]-kp[12,:2])*[w-1,h-1]),4)
            if short=='bellythin':
                extra=compose(local_scale(h,w,zones['belly']*[w-1,h-1],shoulder_width*.5,-.25*value),extra)
                continue
            if short in {'hiplift','shoulderrightangle','breastenlarge'}:
                if short=='hiplift':
                    points=[(kp[i,:2]+[0,.025])*[w-1,h-1] for i in ([23] if side=='left' else [24] if side=='right' else [23,24])]
                elif short=='shoulderrightangle':
                    points=[kp[i,:2]*[w-1,h-1] for i in ([11] if side=='left' else [12] if side=='right' else [11,12])]
                else:
                    left=(kp[11,:2]-kp[12,:2])*.22
                    points=[(zones['chest']+sign*left)*[w-1,h-1] for sign in ([1] if side=='left' else [-1] if side=='right' else [-1,1])]
                for center in points:
                    f=local_scale(h,w,center,shoulder_width*.35,.25*value) if short=='breastenlarge' else radial_push(h,w,center,(0,-.12*value*shoulder_width),shoulder_width*.4)
                    extra=compose(f,extra)
                continue
            if short in {'headsmall','neckswan'}:
                center=kp[:11,:2].mean(axis=0)*[w-1,h-1]
                radius=max(np.linalg.norm((kp[:11,:2]*[w-1,h-1])-center,axis=1).max()*1.6,shoulder_width*.3)
                f=local_scale(h,w,center,radius,-.18*value) if short=='headsmall' else radial_push(h,w,center,(0,-.18*value*shoulder_width),radius*1.8)
                if side:
                    gy,gx=np.indices((h,w),dtype=np.float32)
                    left=kp[11,0]>kp[12,0]
                    weight=np.clip(.5+(gx-center[0])/max(radius*.2,1)*(1 if (side=='left')==left else -1),0,1)
                    f=Field(f.dx*weight,f.dy*weight)
                extra=compose(f,extra)
                continue
            if short=='leglong':
                from morfofix_engine.body.height import height_field
                band=(float(np.clip(hip[1],0,.97)),float(np.clip(max(kp[27,1],kp[28,1]),.02,1)))
                if band[1]>band[0]+.02:
                    f=height_field(h,w,band,value,True)
                    _,xx=np.indices((h,w),dtype=np.float32)
                    center=(body.bbox[0]+body.bbox[2])*w/2
                    radius=max((body.bbox[2]-body.bbox[0])*w*.65,1)
                    weight=np.clip((1-np.abs(xx-center)/radius)/.2,0,1)
                    extra=compose(Field(f.dx*weight,f.dy*weight),extra)
                continue

            if short in {"waistthin", "bellythin", "hipplump", "shoulderbroad", "neckwidth"}:
                center = {"waistthin": zones["waist"], "bellythin": zones["belly"], "hipplump": hip,
                          "shoulderbroad": shoulder, "neckwidth": zones["neck"]}[short]
                span = np.linalg.norm(kp[11,:2]-kp[12,:2])
                vertical = np.array([0, max(np.linalg.norm(hip-shoulder)*.2, .02)])
                segments = [(center-vertical, center+vertical, span*(.12 if short=="neckwidth" else .35))]
            elif short.startswith("legthin") or short.startswith("armthin"):
                pairs = [(23,25,"leftthigh"),(25,27,"leftcalf"),(24,26,"rightthigh"),(26,28,"rightcalf")] if short.startswith("leg") else [(11,13,"leftupper"),(13,15,"leftforearm"),(12,14,"rightupper"),(14,16,"rightforearm")]
                for a,b,part in pairs:
                    if "_" in short and short.split("_",1)[1] != part:
                        continue
                    if side and not part.startswith(side):
                        continue
                    seg_px = float(np.hypot((kp[a,0]-kp[b,0])*(w-1), (kp[a,1]-kp[b,1])*(h-1)))
                    # Visibilidad baja o segmento escorzado (antebrazo hacia la cámara): no hay contorno que afinar.
                    if min(kp[a,3],kp[b,3]) < .3 or seg_px < .04*min(h,w):
                        if warnings is not None:
                            kind = "ARM_PART_SKIPPED" if short.startswith("armthin") else "LEG_PART_SKIPPED"
                            tag = f"{kind}:{part}"
                            if tag not in warnings:
                                warnings.append(tag)
                        continue
                    segments.append((kp[a,:2], kp[b,:2], np.linalg.norm(kp[a,:2]-kp[b,:2])*(.18 if "thigh" in part else .12)))
            limb = short.startswith("armthin") or short.startswith("legthin")
            # Extremidades: con .18 × medio ancho el brazo se movía 1-3 px al 100% (doc 23).
            strength = .12 if short in {"hipplump", "shoulderbroad"} else .25 if short=="bellythin" else .40 if short.startswith("armthin") else .30 if limb else .18
            anchor_k = 2.4 if limb else 1.6
            sign = -1 if short in {"hipplump", "shoulderbroad"} else 1
            for a,b,width in segments:
                axis = (b-a)*[w-1,h-1]
                normal = np.array([-axis[1],axis[0]])/max(np.linalg.norm(axis),1e-6)
                for t in np.linspace(.05,.95,12):
                    center = ((1-t)*a+t*b)*[w-1,h-1]
                    radius = max(width*w, 2)
                    # Scan the person's segmentation along the local normal.
                    if body.seg_mask is not None:
                        mask = body.seg_mask[..., 0] if body.seg_mask.ndim == 3 else body.seg_mask
                        steps = np.linspace(-radius*2, radius*2, 49)
                        samples = center[None,:]+steps[:,None]*normal
                        xx = np.clip(np.rint(samples[:,0]/max(w-1,1)*(mask.shape[1]-1)).astype(int),0,mask.shape[1]-1)
                        yy = np.clip(np.rint(samples[:,1]/max(h-1,1)*(mask.shape[0]-1)).astype(int),0,mask.shape[0]-1)
                        inside = steps[mask[yy,xx]>.5]
                        if len(inside)>1:
                            radius = max(min(abs(inside[0]),abs(inside[-1])),2)
                    src.append(center[None,:]); dst.append(center[None,:])
                    for direction in (-1,1):
                        if side and not (short.startswith('leg') or short.startswith('arm')):
                            left_direction=np.dot((kp[11,:2]-kp[12,:2])*[w-1,h-1],normal)
                            if (direction*left_direction>0)!=(side=='left'):
                                continue
                        p = center+direction*radius*normal
                        d = p-sign*value*strength*(p-center)*np.sin(np.pi*t)
                        src.append(p[None,:]); dst.append(d[None,:])
                        anchor = center+direction*radius*anchor_k*normal
                        src.append(anchor[None,:]); dst.append(anchor[None,:])
    return compose(extra,mls_backward_field(h,w,np.concatenate(src),np.concatenate(dst),grid_step=grid_step))
