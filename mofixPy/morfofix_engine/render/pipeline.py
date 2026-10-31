"""Declarative render: remove → geometry → retouch → one composed warp → protect."""
from dataclasses import dataclass, field, replace
import time
import cv2
import numpy as np
from morfofix_engine.core.edit_state import EditState
from morfofix_engine.core.errors import EngineError
from morfofix_engine.body.freeze import rasterize_strokes, freeze_mask_from_state
from morfofix_engine.core.state import BrushStroke
from morfofix_engine.face.reshape import controls_from_params
from morfofix_engine.face.landmark_map import FACE_OVAL, GROUPS
from morfofix_engine.photo.color import apply_hsl
from morfofix_engine.photo.geom import apply_geom
from morfofix_engine.retouch.effects import apply_retouch
from morfofix_engine.retouch.inpaint import inpaint
from morfofix_engine.warps.field import identity, compose, attenuate, to_maps, mls_backward_field, mesh_backward_field, radial_push
from morfofix_engine.warps.mesh import Stroke
from morfofix_engine.body.manual import manual_field
from morfofix_engine.body.arm import arm_manual_field, arm_manual_roi
from morfofix_engine.body.height import height_field
from morfofix_engine.body.slim import body_field
from morfofix_engine.body.protect import head_mask, composite_background
from morfofix_engine.body.muscle import apply_muscle


@dataclass
class RenderResult:
    image: np.ndarray
    warnings: list[str] = field(default_factory=list)
    timings: dict[str,float] = field(default_factory=dict)
    pose_available: bool = False


def _transform_landmarks_norm(lm, affine, src_wh, dst_wh):
    w0,h0=src_wh; w1,h1=dst_wh
    xy=lm[:,:2]*[max(w0-1,1),max(h0-1,1)]
    result=lm.copy()
    result[:,:2]=affine.apply_points(xy)/[max(w1-1,1),max(h1-1,1)]
    return result


def _strokes(items):
    return [BrushStroke(s.pts,s.radius,s.erase) for s in items]


def _prep_mask(mask, src_wh, affine, dst_wh):
    if mask is None:
        return None
    mask=np.asarray(mask,np.float32)
    if mask.ndim==3:
        mask=mask[:,:,0]
    src_w,src_h=src_wh
    w,h=dst_wh
    mask=cv2.resize(mask,(src_w,src_h))
    if affine is not None:
        mask=cv2.warpAffine(mask,affine.m,(w,h))
    return mask


def legacy_state(params):
    p=params.photo
    return EditState.model_validate({
        'face': {str(k):v for k,v in params.face.items()},
        'liquify':[{'pts':[s.p0,s.p1],'k':s.k,'r':s.r} for s in params.liquify],
        'freeze':{'strokes':[{'pts':s.pts,'radius':s.radius,'erase':s.erase} for s in params.freeze]},
        'remove':[{'strokes':[{'pts':s.pts,'radius':s.radius} for s in params.remove],'method':params.remove_method}] if params.remove else [],
        'retouch':params.retouch,
        'photo':{'crop':p.crop,'rotate_deg':p.rotate_deg,'flip_h':p.flip_h,'hsl':{'hue':p.hue,'saturation':p.saturation,'lightness':p.lightness}}})


def _render(session, *, state=None, target='preview', max_side=1600, interpolation=None, overlay=None):
    started=time.perf_counter()
    state=state if state is not None else legacy_state(session.params)
    warnings=list(session.meta.warnings)
    img=session.preview if target=='preview' else session.original
    if target=='preview' and max_side and max(img.shape[:2])>max_side:
        scale=max_side/max(img.shape[:2])
        img=cv2.resize(img,(max(1,round(img.shape[1]*scale)),max(1,round(img.shape[0]*scale))),interpolation=cv2.INTER_AREA)
    src_h,src_w=img.shape[:2]
    cache=getattr(getattr(session,'registry',None),'cache',None)
    prefix=[]
    remove_affine=None
    remove_h,remove_w=src_h,src_w
    photo=state.photo
    if state.remove and (photo.crop!=(0,0,1,1) or photo.rotate_deg or photo.flip_h):
        geometry_preview,remove_affine=apply_geom(img,photo.crop,photo.rotate_deg,photo.flip_h)
        remove_h,remove_w=geometry_preview.shape[:2]
        del geometry_preview
    for op in state.remove:
        prefix.append(op.model_dump())
        from morfofix_engine.inference.cache import InferenceCache
        key=InferenceCache.key(session.meta.image_sha1,str((src_h,src_w)),'remove-v1','',[photo.model_dump(),prefix])
        cached=cache.get(key) if cache else None
        if cached is not None:
            img=cached['image']
            continue
        mask=rasterize_strokes(_strokes(op.strokes),remove_h,remove_w)
        if remove_affine is not None:
            mask=cv2.warpAffine(mask,cv2.invertAffineTransform(remove_affine.m),(src_w,src_h),flags=cv2.INTER_NEAREST)

        img=inpaint(img,mask,method=op.method)
        if cache:
            cache.put_memory(key,image=img)
    p=state.photo
    affine=None
    if p.crop!=(0,0,1,1) or p.rotate_deg or p.flip_h:
        img,affine=apply_geom(img,p.crop,p.rotate_deg,p.flip_h)
    h,w=img.shape[:2]
    faces=list(session.faces or [])
    bodies=list(session.bodies or [])
    masks_resized={name:_prep_mask(m,(src_w,src_h),affine,(w,h)) for name,m in (session.masks or {}).items()}
    mask=masks_resized.get('person')
    if affine is not None:
        faces=[replace(f,landmarks=_transform_landmarks_norm(f.landmarks,affine,(src_w,src_h),(w,h))) for f in faces]
        # Derive head boxes from transformed points instead of stale original boxes.
        faces=[replace(f,bbox=(*f.landmarks[:,:2].min(axis=0),*f.landmarks[:,:2].max(axis=0))) for f in faces]
        transformed=[]
        for b in bodies:
            bm=cv2.resize(b.seg_mask,(src_w,src_h)) if b.seg_mask is not None else None
            if bm is not None:
                bm=cv2.warpAffine(bm,affine.m,(w,h))
            transformed.append(replace(b,keypoints=_transform_landmarks_norm(b.keypoints,affine,(src_w,src_h),(w,h)),seg_mask=bm))
        bodies=transformed
    # Free-angle rotations need reinference, provided by the session's app registry.
    if p.rotate_deg % 90 and getattr(session,'registry',None) is not None:
        from morfofix_engine.inference.face import detect_faces
        from morfofix_engine.inference.pose import detect_bodies
        if state.face or state.facelift or any(state.retouch.model_dump(exclude={'brush'}).values()):
            faces=detect_faces(img,session.registry)
        if state.body or state.muscle or (not faces and (state.face or state.facelift or any(state.retouch.model_dump(exclude={'brush'}).values()))):
            bodies=detect_bodies(img,session.registry)
        if not faces and bodies and (state.face or state.facelift or any(state.retouch.model_dump(exclude={'brush'}).values())):
            from morfofix_engine.inference.face import head_boxes_from_bodies
            faces=detect_faces(img,session.registry,head_boxes=head_boxes_from_bodies(bodies,h,w))
    body_params={}
    for index,values in state.body.items():
        if not any(values.values()):
            continue
        idx=int(index)
        kp=bodies[idx].keypoints if 0<=idx<len(bodies) else None
        if kp is None or getattr(kp,'shape',None)!=(33,4):
            warnings.append(f'NO_BODY:{idx}')
            continue
        body_params[index]=values
    if state.body and not bodies:
        warnings.append('POSE_UNAVAILABLE')
    for bucket,detected,code in ((state.face,faces,'NO_FACE'),(state.facelift,faces,'NO_FACE')):
        for index,values in bucket.items():
            if any(values.values()) and int(index)>=len(detected):
                raise EngineError(422,'no hay detección para ese índice',{'index':int(index)},code=code)
    if any(state.retouch.model_dump(exclude={'brush'}).values()):
        if not faces:
            vals=state.retouch.model_dump(exclude={'brush'})
            painted={k for k,v in state.retouch.brush.items() if v.strokes}
            if any(v for k,v in vals.items() if k not in painted and k!='degree_sharpen'):
                warnings.append('NO_FACE_RETOUCH')
        skin_mask=masks_resized.get('face_skin')
        img=apply_retouch(img,faces,state.retouch,skin_mask=skin_mask)
    img=apply_hsl(img,p.hsl.hue,p.hsl.saturation,p.hsl.lightness)
    muscle_mask=None
    if state.muscle:
        img,mf,mw,muscle_mask=apply_muscle(img,bodies,masks_resized,state.muscle)
        warnings.extend(mw)
    from morfofix_engine.face.lift import facelift_color, double_chin
    combined=identity(h,w)
    chin_fields=[]
    for index,values in state.face.items():
        if values.get('intensity_facedoublechin'):
            img,chin=double_chin(img,faces[int(index)],values['intensity_facedoublechin'])
            chin_fields.append(chin)
    for index,values in state.facelift.items():
        if any(values.values()):
            img=facelift_color(img,faces[int(index)],values)

    controls_src=[]; controls_dst=[]
    if any(any(v.values()) for v in state.face.values()):
        for i,f in enumerate(faces):
            values=state.face.get(str(i),{})
            if any(values.values()):
                src,dst,_=controls_from_params(f.landmarks,values,(w,h))
            else:
                src=f.landmarks[list(FACE_OVAL),:2]*[w-1,h-1]; dst=src.copy()
            controls_src.append(src); controls_dst.append(dst)
        if controls_src:
            combined=mls_backward_field(h,w,np.concatenate(controls_src),np.concatenate(controls_dst),grid_step=16 if target=="preview" and max(h,w)>1000 else 8)
    for chin in chin_fields:
        combined=compose(chin,combined)
    for index,values in state.facelift.items():
        if not any(values.values()):
            continue
        lm=faces[int(index)].landmarks
        regions={'eye_area':('EYES_L','EYES_R'),'brow_peak':('BROWS_L','BROWS_R'),'face_mid':('CHEEKS',),'contour':('JAWLINE',),'forehead':('FOREHEAD',),'mouth_area':('LIPS',)}
        for name,value in values.items():
            zone=name.removeprefix('intensity_facelift_')
            for group in regions.get(zone,()):
                points=lm[list(GROUPS[group]),:2]*[w-1,h-1]
                center=points.mean(axis=0)
                radius=max(np.linalg.norm(points-center,axis=1).max()*1.5,2)
                lift=radial_push(h,w,center,(0,-value*6*max(h,w)/1600),radius)
                combined=compose(lift,combined)
    if body_params:
        if any(bodies[int(i)].seg_mask is None for i,v in body_params.items() if any(v.values())):
            warnings.append('NO_PERSON_MASK')
        bf=body_field(h,w,bodies,body_params,grid_step=16 if target=="preview" and max(h,w)>1000 else 8,warnings=warnings)
        if state.body_options.head_protect:
            bf=attenuate(bf,head_mask(h,w,faces,bodies))
        combined=compose(bf,combined)
    if state.manual_shapes:
        combined=compose(manual_field(h,w,state.manual_shapes),combined)
    am=getattr(state.arm,'manual',None)
    # Trazos de brazo fijados (en orden) y después el trazo activo: así mover el editor
    # no arrastra lo ya aplicado. Python no guarda estado: todo viene en el EditState.
    arm_strokes=[s for s in (list(getattr(state.arm,'manual_strokes',[]) or [])+[am]) if s is not None and s.value]
    for s_arm in arm_strokes:
        combined=compose(arm_manual_field(h,w,s_arm),combined)
    if state.liquify:
        strokes=[Stroke(a,b,s.k,s.r) for s in state.liquify for a,b in zip(s.pts,s.pts[1:])]
        combined=compose(mesh_backward_field(h,w,strokes),combined)
    if state.height is not None and state.height.value:
        ht=state.height
        # band ya refleja y_start/y_end si vinieron (validador de Height).
        combined=compose(height_field(h,w,ht.band,ht.value,ht.keep_canvas),combined)
    if state.muscle and (np.any(mf.dx) or np.any(mf.dy)):
        if state.body_options.head_protect:
            mf=attenuate(mf,head_mask(h,w,faces,bodies))
        combined=compose(mf,combined)
    fz=state.freeze
    if fz.strokes or fz.rects or fz.invert:
        # Rasterizado con aspecto real; radio/feather relativos al lado menor.
        fm=freeze_mask_from_state(fz,combined.dx.shape[0],combined.dx.shape[1])
        combined=attenuate(combined,fm)
    interp=interpolation if interpolation is not None else (cv2.INTER_CUBIC if target=='export' else cv2.INTER_LINEAR)
    maps=to_maps(combined)
    warped=cv2.remap(img,*maps,interpolation=interp,borderMode=cv2.BORDER_REPLICATE)
    arm_protect=[s for s in arm_strokes if s.protect_bg]
    protect=state.body_options.bg_protect or bool(arm_protect)
    if protect:
        if mask is None:
            warnings.append('NO_BODY_MASK')
        elif np.any(combined.dx) or np.any(combined.dy):
            composited=composite_background(img,warped,mask,combined,cache=cache)
            if state.body_options.bg_protect:
                warped=composited
            else:
                roi=np.maximum.reduce([arm_manual_roi(h,w,s) for s in arm_protect])[...,None]
                warped=(warped*(1-roi)+composited*roi).astype(warped.dtype)
    if overlay:
        warped=warped.copy()
        if overlay in {'landmarks','pose'}:
            points=[f.landmarks for f in faces] if overlay=='landmarks' else [b.keypoints for b in bodies]
            for group in points:
                for x,y,*_ in group:
                    cv2.circle(warped,(round(x*(w-1)),round(y*(h-1))),1,(0,255,0),-1)
        elif overlay=='freeze' and (fz.strokes or fz.rects or fz.invert):
            visible=cv2.resize(fm,(warped.shape[1],warped.shape[0]))
            warped[:,:,:3]=np.clip(warped[:,:,:3]*(1-visible[...,None]*.4)+np.array([255,180,0])*visible[...,None]*.4,0,255).astype(np.uint8)
        elif overlay=='mesh':
            for y in range(0,warped.shape[0],32):
                cv2.polylines(warped,[np.stack(maps,axis=-1)[y,::8].astype(np.int32)],False,(0,255,0),1)
        elif overlay=='muscle' and muscle_mask is not None:
            visible=np.clip(muscle_mask,0,1)
            warped[:,:,:3]=np.clip(warped[:,:,:3]*(1-visible[...,None]*.4)+np.array([0,255,255])*visible[...,None]*.4,0,255).astype(np.uint8)
    return RenderResult(warped,warnings,{'total_ms':(time.perf_counter()-started)*1000},pose_available=bool(bodies))


def encode_jpeg(img,quality=85):
    ok,buf=cv2.imencode('.jpg',img[:,:,:3],[cv2.IMWRITE_JPEG_QUALITY,int(quality)])
    if not ok:
        raise RuntimeError('encode jpeg')
    return buf.tobytes()


def render(session, *, state=None, target='preview', max_side=1600, interpolation=None, overlay=None):
    """Cache complete deterministic renders by state, geometry and inference content."""
    import hashlib
    from morfofix_engine.inference.cache import InferenceCache
    state=state if state is not None else legacy_state(session.params)
    cache=getattr(getattr(session,'registry',None),'cache',None)
    key=None
    if cache is not None:
        digest=hashlib.sha256()
        for face in session.faces or []:
            digest.update(face.landmarks.tobytes())
        for body in session.bodies or []:
            digest.update(body.keypoints.tobytes())
            if body.seg_mask is not None:
                digest.update(body.seg_mask.tobytes())
        for name,mask in sorted(session.masks.items()):
            digest.update(name.encode());digest.update(mask.tobytes())
        model_versions={k:(v.sha256,v.status) for k,v in session.registry.models.items()}
        key=InferenceCache.key(session.meta.image_sha1,digest.hexdigest(),'render-v1',model_versions,
            [state.model_dump(by_alias=True),target,max_side,interpolation,overlay])
        started=time.perf_counter()
        cached=cache.get(key)
        if cached is not None:
            return RenderResult(cached['image'],cached['warnings'].tolist(),{'total_ms':(time.perf_counter()-started)*1000,'cache_hit':1},pose_available=bool(session.bodies))
    result=_render(session,state=state,target=target,max_side=max_side,interpolation=interpolation,overlay=overlay)
    if cache is not None:
        cache.put_memory(key,image=result.image,warnings=np.array(result.warnings,dtype='U128'))
    return result
