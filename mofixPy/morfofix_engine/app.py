"""Offline loopback API v0. All expensive work shares one executor."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import asyncio
import logging
import secrets
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from morfofix_engine import API_VERSION, __version__
from morfofix_engine.core.edit_state import EditState, Strict, Intensity
from morfofix_engine.core.errors import EngineError, error_response
from morfofix_engine.core.session import SessionStore
from morfofix_engine.core.scheduler import RenderScheduler
from morfofix_engine.inference.cache import InferenceCache
from morfofix_engine.inference.models import ModelRegistry
from morfofix_engine.inference.face import detect_faces
from morfofix_engine.inference.pose import detect_bodies
from morfofix_engine.inference.segment import person_mask, multiclass_masks
from morfofix_engine.face.landmark_map import GROUPS
from morfofix_engine.face.catalog import catalog_entries as face_catalog, is_face_param
from morfofix_engine.body.catalog import catalog_entries as body_catalog, BODY_ALIAS
from morfofix_engine.body.muscle_catalog import catalog_entries as muscle_catalog
from morfofix_engine.render.export import export_image
from morfofix_engine.render.pipeline import encode_jpeg, render
from morfofix_engine.retouch.catalog import catalog_entries as retouch_catalog


def _pose_parts(kp):
    vis = kp[:, 3]
    pair = lambda a, b: float(min(vis[a], vis[b])) >= .3
    return {
        'leftupper': pair(11, 13),
        'leftforearm': pair(13, 15),
        'rightupper': pair(12, 14),
        'rightforearm': pair(14, 16),
        'torso': float(min(vis[11], vis[12], vis[23], vis[24])) >= .5,
    }


class DetectBody(Strict):
    what: list[Literal['face','pose','person_mask']] = Field(default_factory=lambda:['face'])
    max_faces: int = Field(default=5,ge=1,le=12)
    max_people: int = Field(default=3,ge=1,le=12)


class ParamsBody(Strict):
    rev: int | None = Field(default=None,ge=0)
    name: str
    value: Intensity
    face: int = Field(default=0,ge=0)
    human: int = Field(default=0,ge=0)


class RenderBody(Strict):
    rev: int | None = Field(default=None,ge=0)
    state: EditState = Field(default_factory=EditState)
    target: Literal['preview','export'] = 'preview'
    max_side: int | None = Field(default=1600,ge=1,le=8192)
    format: Literal['jpeg'] = 'jpeg'
    quality: int = Field(default=85,ge=1,le=100)
    overlay: Literal['landmarks','pose','mesh','freeze','muscle'] | None = None


class ExportBody(Strict):
    path: str
    state: EditState | None = None
    format: Literal['png','jpeg','webp','tiff'] = 'png'
    quality: int = Field(default=92,ge=1,le=100)
    keep_metadata: bool = True
    keep_gps: bool = False


def create_app(*,models_dir:Path,cache_dir:Path|None=None,token:str|None=None,port:int|None=None,shutdown_callback=None):
    store=SessionStore()
    registry=ModelRegistry(models_dir)
    registry.cache=InferenceCache(cache_dir)
    scheduler=RenderScheduler()
    started=time.monotonic()
    @asynccontextmanager
    async def lifespan(app):
        yield
        await asyncio.to_thread(scheduler.close)
    app=FastAPI(title='MorfoFix engine',version=__version__,lifespan=lifespan)

    @app.middleware('http')
    async def guard(request,call_next):
        host=request.headers.get('host','')
        expected={f'127.0.0.1:{port}',f'localhost:{port}'} if port is not None else {'127.0.0.1','localhost','testserver'}
        if host not in expected:
            return error_response(EngineError(421,'Host no permitido'))
        if token is not None and not (request.method=='GET' and request.url.path=='/health'):
            supplied=request.headers.get('authorization','')
            if not secrets.compare_digest(supplied.encode(),('Bearer '+token).encode()):
                return error_response(EngineError(401,'token inválido'))
        try:
            return await call_next(request)
        except Exception:
            trace=uuid.uuid4().hex
            logging.getLogger('engine').exception('INTERNAL trace_id=%s',trace)
            return error_response(EngineError(500,'error interno',{'trace_id':trace}))

    @app.exception_handler(EngineError)
    async def engine_error(_,exc):
        return error_response(exc)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_,exc):
        return error_response(EngineError(exc.status_code,str(exc.detail),code='BAD_PARAM'))

    @app.exception_handler(RequestValidationError)
    async def invalid(_,exc):
        detail=[{'loc':list(e['loc']),'message':e['msg']} for e in exc.errors()]
        return error_response(EngineError(400,'parámetros inválidos',{'errors':detail}))

    @app.get('/health')
    async def health():
        return {'status':'ok','version':__version__,'api':API_VERSION,'uptime_s':round(time.monotonic()-started,3),'models':registry.health(),'sessions':len(store)}

    @app.post('/session')
    async def open_session(request:Request):
        if 'multipart/form-data' in request.headers.get('content-type',''):
            async with request.form(max_files=1,max_fields=2) as form:
                upload=form.get('file')
                if upload is None or not hasattr(upload,'read'):
                    raise EngineError(400,'hace falta path o file')
                source=await upload.read()
                name=upload.filename or 'upload'
        else:
            try:
                raw=await request.json()
            except ValueError as exc:
                raise EngineError(400,'JSON inválido') from exc
            if not isinstance(raw,dict) or not isinstance(raw.get('path'),str):
                raise EngineError(400,'hace falta path o file')
            source=Path(raw['path']); name=source.name
            if not source.is_absolute() or not source.is_file():
                raise EngineError(400,'ruta absoluta inexistente')
        try:
            sess=await scheduler.run(lambda:store.create(source,name=name))
        except (ValueError,OSError) as exc:
            raise EngineError(415,str(exc)) from exc
        sess.registry=registry
        m=sess.meta; ph,pw=sess.preview.shape[:2]
        return {'session_id':sess.id,'width':m.width,'height':m.height,'preview_width':pw,'preview_height':ph,'orientation_applied':m.orientation_applied,'format':m.format,'has_alpha':m.has_alpha,'icc':m.icc,'image_sha1':m.image_sha1,'warnings':m.warnings}

    @app.delete('/session/{sid}',status_code=204)
    async def delete_session(sid:str):
        store.drop(sid)
        return Response(status_code=204)

    @app.post('/session/{sid}/detect')
    async def detect(sid:str,body:DetectBody):
        sess=store.get(sid)
        def job():
            timings={}; out={'faces':[],'bodies':[],'masks':{},'timings_ms':timings}
            if 'face' in body.what:
                t=time.perf_counter(); faces=detect_faces(sess.original,registry,max_faces=body.max_faces)
                if not faces and registry.path_if_ok('pose_landmarker_full'):
                    # aquí Cuerpo entero la cara no aparece ni con tiles,reintente con recorte de cabeza por pose.
                    from morfofix_engine.inference.face import head_boxes_from_bodies
                    hb=head_boxes_from_bodies(detect_bodies(sess.original,registry,max_people=body.max_people),*sess.original.shape[:2])
                    if hb:
                        faces=detect_faces(sess.original,registry,max_faces=body.max_faces,head_boxes=hb)
                sess.faces=faces; timings['face']=(time.perf_counter()-t)*1000
                out['faces']=[{
                    'index':int(f.index),
                    'bbox':[float(x) for x in f.bbox],
                    'score':float(f.score),
                    'euler':None if f.euler is None else [float(x) for x in f.euler],
                    'n_points':int(len(f.landmarks)),
                } for f in faces]
            if 'pose' in body.what:
                t=time.perf_counter(); bodies=detect_bodies(sess.original,registry,max_people=body.max_people)
                sess.bodies=bodies; timings['pose']=(time.perf_counter()-t)*1000
                out['pose_available']=bool(bodies)
                out['bodies']=[{
                    'index':int(b.index),
                    'bbox':[float(x) for x in b.bbox],
                    'score':float(b.score),
                    'visible':{str(i):float(k[3]) for i,k in enumerate(b.keypoints)},
                    'parts':_pose_parts(b.keypoints),
                } for b in bodies]
            if 'person_mask' in body.what:
                t=time.perf_counter()
                mask=None
                if registry.path_if_ok('selfie_multiclass'):
                    sess.masks.update(multiclass_masks(sess.original,registry))
                    mask=sess.masks.get('person')
                else:
                    try:
                        mask=person_mask(sess.original,registry,model='pose')
                    except FileNotFoundError:
                        try:
                            mask=person_mask(sess.original,registry,model='selfie')
                        except (FileNotFoundError,RuntimeError):
                            mask=None
                if mask is None:
                    out['masks']['person']=False
                    out.setdefault('warnings',[]).append('NO_PERSON_MASK')
                else:
                    sess.masks['person']=mask
                    out['masks']['person']=True
                timings['person_mask']=(time.perf_counter()-t)*1000
            return out
        return await model_job(job)

    async def model_job(job):
        try:
            return await scheduler.run(job)
        except (FileNotFoundError,ImportError,RuntimeError,ValueError) as exc:
            raise EngineError(503,'modelo o runtime no disponible',{'reason':str(exc)}) from exc

    async def preview(sess,body):
        rev=body.rev if body.rev is not None else scheduler.latest.get(sess.id,-1)+1
        # Validate revision before storing compatibility state.
        if rev<=scheduler.latest.get(sess.id,-1):
            raise EngineError(409,'revisión superada')
        snapshot=body.state.model_copy(deep=True)
        sess.edit_state=snapshot
        def job():
            result=render(sess,state=snapshot,target=body.target,max_side=body.max_side,overlay=body.overlay)
            data=encode_jpeg(result.image,body.quality)
            return result,data
        try:
            result,data=await scheduler.submit(sess.id,rev,job)
        except (FileNotFoundError,ImportError) as exc:
            raise EngineError(503,'modelo no disponible') from exc
        return Response(data,media_type='image/jpeg',headers={
            'X-Rev':str(rev),
            'X-Render-Ms':f"{result.timings['total_ms']:.1f}",
            'X-Warnings':','.join(result.warnings),
            'X-Pose-Available':'true' if result.pose_available else 'false',
        })

    @app.post('/session/{sid}/render')
    async def do_render(sid:str,body:RenderBody|None=None):
        return await preview(store.get(sid),body or RenderBody())

    @app.post('/session/{sid}/params')
    async def params(sid:str,body:ParamsBody):
        sess=store.get(sid)
        raw=sess.edit_state.model_dump(by_alias=True)
        name=BODY_ALIAS.get(body.name,body.name)
        if name.startswith('degree_'):
            raw['retouch'][name]=body.value
        else:
            bucket='facelift' if 'facelift_' in name else 'face' if is_face_param(name) else 'body'
            index=str(body.human if bucket=='body' else body.face)
            raw[bucket].setdefault(index,{})[name]=body.value
        try:
            state=EditState.model_validate(raw)
        except ValueError as exc:
            raise EngineError(400,str(exc)) from exc
        return await preview(sess,RenderBody(state=state,rev=body.rev))

    @app.post('/session/{sid}/export')
    async def do_export(sid:str,body:ExportBody):
        sess=store.get(sid)
        snapshot=(body.state if body.state is not None else sess.edit_state).model_copy(deep=True)
        def job():
            result=render(sess,state=snapshot,target='export')
            info=export_image(result.image,Path(body.path),fmt=body.format,quality=body.quality,metadata=sess.meta,keep_metadata=body.keep_metadata,keep_gps=body.keep_gps)
            return {**vars(info),'warnings':result.warnings}
        try:
            return await scheduler.run(job)
        except (ValueError,OSError) as exc:
            raise EngineError(400,str(exc)) from exc

    @app.get('/session/{sid}/landmarks')
    async def landmarks(sid:str,face:int=0,space:Literal['preview','original']='preview'):
        sess=store.get(sid)
        if not sess.faces or face<0 or face>=len(sess.faces):
            raise EngineError(422,'no hay cara para ese índice')
        return {'face':face,'points':sess.faces[face].landmarks.tolist(),'groups':{k:list(v) for k,v in GROUPS.items()},'space':space}

    @app.get('/catalog')
    async def catalog():
        return {'params':face_catalog()+body_catalog()+retouch_catalog()+muscle_catalog()}

    @app.post('/shutdown')
    async def shutdown():
        if shutdown_callback:
            asyncio.get_running_loop().call_later(.05,shutdown_callback)
        return JSONResponse({'status':'bye'},status_code=202)

    app.state.store=store; app.state.registry=registry; app.state.scheduler=scheduler
    return app
