from pathlib import Path
import asyncio
import threading
import cv2
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pydantic import ValidationError
from morfofix_engine.app import create_app
from morfofix_engine.core.edit_state import EditState, Shape
from morfofix_engine.core.session import SessionStore
from morfofix_engine.core.scheduler import RenderScheduler
from morfofix_engine.core.errors import EngineError
from morfofix_engine.inference.cache import InferenceCache
from morfofix_engine.warps.field import Field, identity, compose, to_maps, attenuate, local_scale
from morfofix_engine.body.height import height_field
from morfofix_engine.body.manual import manual_field, SHAPES
from morfofix_engine.render.pipeline import render
from morfofix_engine.render.export import export_image
from morfofix_engine.io.load import load_path


@pytest.mark.parametrize('state',[
    {'schema':2}, {'wat':1}, {'face':{'-1':{'intensity_jaw':.2}}},
    {'face':{'0':{'intensity_jaw':1.01}}}, {'retouch':{'degree_sharpen':-1}},
    {'liquify':[{'pts':[[0,0],[2,1]],'k':.15,'r':.03}]},
    {'height':{'band':[.8,.2],'value':.1}}, {'photo':{'crop':[1,0,0,1]}},
    {'body':{'0':{'unknown':0}}}, {'facelift':{'0':{'intensity_jaw':.2}}},
    {'retouch':{'degree_sharpen':float('nan')}},
])
def test_reject_invalid_state(state):
    with pytest.raises(ValidationError):
        EditState.model_validate(state)


def test_compose_noncommuting():
    y,x=np.indices((20,30),dtype=np.float32)
    scale=Field(x*.2,y*.1)
    shift=Field(np.ones_like(x)*2,np.ones_like(y))
    result=compose(shift,scale)
    mx,my=to_maps(result)
    np.testing.assert_allclose(mx[2:-3,2:-3],(x+2)[2:-3,2:-3]*1.2,atol=.02)
    np.testing.assert_allclose(my[2:-3,2:-3],(y+1)[2:-3,2:-3]*1.1,atol=.02)
    assert not np.allclose(compose(scale,shift).dx,result.dx)


def test_freeze_attenuates_not_blends():
    f=local_scale(40,40,(20,20),15,.3)
    frozen=attenuate(f,np.ones((40,40)))
    assert not frozen.dx.any() and not frozen.dy.any()
    np.testing.assert_allclose(attenuate(f,np.full((40,40),.5)).dx,f.dx*.5)


@pytest.mark.parametrize('value',[-1,0,1])
def test_height_monotonic(value):
    f=height_field(100,50,(.3,.8),value)
    x,y=to_maps(f)
    assert y.shape[0]==round(100+50*.3*value)
    assert np.all(np.diff(y[:,0])>0)
    assert height_field(100,50,(.3,.8),value,True).dx.shape==(100,50)


@pytest.mark.parametrize('kind',sorted(SHAPES))
def test_manual_identity_and_locality(kind):
    raw={'type':kind,'cx':.5,'cy':.5,'w':.4,'h':.4,'value':0}
    f0=manual_field(60,80,[Shape(**raw)])
    assert not f0.dx.any() and not f0.dy.any()
    raw['value']=.8
    f=manual_field(60,80,[Shape(**raw)])
    assert np.max(np.abs(f.dx))+np.max(np.abs(f.dy))>0
    assert not f.dx[:5].any() and not f.dy[:5].any()
    if kind=='BreastEnlarge_Circle':
        assert f.dx[30,45]<0  # backward map: enlargement samples nearer center
    if kind=='BellyThin_Circle':
        assert f.dx[30,45]>0


def test_cache_disk_and_eviction(tmp_path):
    c=InferenceCache(tmp_path,max_bytes=16)
    key=c.key('image','geom','mask','model',{})
    c.put(key,mask=np.ones((3,3),np.float32))
    assert not c.ram
    np.testing.assert_equal(c.get(key)['mask'],1)
    result=c.get(key); result['mask'][:]=0
    assert c.get(key)['mask'].all()
    (tmp_path/f'{key}.npz').write_bytes(b'corrupt')
    assert c.get(key) is None


def test_complete_state_reset_and_single_remap(rgb_png,monkeypatch):
    sess=SessionStore().create(rgb_png)
    original=sess.original.copy()
    state=EditState.model_validate({'liquify':[{'pts':[[.4,.5],[.55,.5]],'k':.2,'r':.2}], 'height':{'band':[.3,.8],'value':.5}})
    out=render(sess,state=state).image
    assert out.shape[0]>original.shape[0]
    reset=render(sess,state=EditState()).image
    np.testing.assert_array_equal(reset,original)
    np.testing.assert_array_equal(sess.original,original)


def test_latest_wins():
    async def scenario():
        scheduler=RenderScheduler(); entered=threading.Event(); release=threading.Event(); executed=[]
        def slow():
            entered.set(); release.wait(3); executed.append(1); return 1
        first=asyncio.create_task(scheduler.submit('s',1,slow))
        while not entered.is_set():
            await asyncio.sleep(.001)
        second=asyncio.create_task(scheduler.submit('s',2,lambda:executed.append(2)))
        await asyncio.sleep(0)
        third=asyncio.create_task(scheduler.submit('s',3,lambda:executed.append(3)))
        await asyncio.sleep(0)
        release.set()
        results=await asyncio.gather(first,second,third,return_exceptions=True)
        assert isinstance(results[0],EngineError) and results[0].code=='STALE_REV'
        assert isinstance(results[1],EngineError) and results[1].code=='STALE_REV'
        assert executed==[1,3]
        scheduler.close()
    asyncio.run(scenario())


def test_token_host_and_shutdown(tmp_path):
    app=create_app(models_dir=tmp_path,token='secret',port=7777)
    with TestClient(app,base_url='http://127.0.0.1:7777') as client:
        assert client.get('/health').status_code==200
        assert client.get('/catalog').status_code==401
        assert client.get('/catalog',headers={'Authorization':'Bearer secret'}).status_code==200
        assert client.get('/health',headers={'Host':'evil.example'}).status_code==421
        assert client.get('/health',headers={'Host':'127.0.0.1:9999'}).status_code==421
        response=client.options('/catalog',headers={'Origin':'https://evil.example'})
        assert 'access-control-allow-origin' not in response.headers
        assert client.post('/shutdown',headers={'Authorization':'Bearer secret'}).status_code==202


def test_revisions_and_export_state(client,rgb_png,tmp_path):
    sid=client.post('/session',json={'path':str(rgb_png)}).json()['session_id']
    request={'rev':3,'state':{'height':{'band':[.3,.8],'value':1}}}
    r=client.post(f'/session/{sid}/render',json=request)
    assert r.status_code==200 and r.headers['x-rev']=='3'
    assert client.post(f'/session/{sid}/render',json={'rev':2,'state':{}}).status_code==409
    destination=tmp_path/'reset.png'
    r=client.post(f'/session/{sid}/export',json={'state':{},'path':str(destination)})
    assert r.status_code==200 and r.json()['height']==60


def test_export_metadata_and_atomic_failure(tmp_path,monkeypatch):
    source=tmp_path/'source.jpg'
    exif=Image.Exif(); exif[274]=6; exif[315]='Test author'; exif[34853]={1:'N',2:(1.,2.,3.)}
    Image.new('RGB',(20,30),(90,80,70)).save(source,exif=exif,icc_profile=b'test-profile')
    image,metadata=load_path(source)
    output=tmp_path/'out.jpg'
    export_image(image,output,fmt='jpeg',metadata=metadata)
    with Image.open(output) as result:
        assert result.getexif()[274]==1
        assert result.getexif()[315]=='Test author'
        assert 34853 not in result.getexif()
        assert result.info['icc_profile']==b'test-profile'
    export_image(image,output,fmt='jpeg',metadata=metadata,keep_gps=True)
    with Image.open(output) as result:
        assert 34853 in result.getexif()
    before=output.read_bytes()
    def fail(*a,**kw):
        raise OSError('simulated full disk')
    monkeypatch.setattr(Image.Image,'save',fail)
    with pytest.raises(OSError):
        export_image(image,output,fmt='jpeg')
    assert output.read_bytes()==before
    assert not list(tmp_path.glob('.morfofix-*'))


def test_exemplar_preserves_unmasked():
    from morfofix_engine.retouch.exemplar import exemplar_inpaint
    y,x=np.indices((24,24)); image=np.stack([x*5,y*5,(x+y)*3],axis=-1).astype(np.uint8)
    mask=np.zeros((24,24),np.float32);mask[10:13,10:13]=1
    dirty=image.copy();dirty[mask>0]=0
    fixed=exemplar_inpaint(dirty,mask)
    np.testing.assert_array_equal(fixed[mask==0],image[mask==0])
    assert fixed[mask>0].mean()>0


def synthetic_body():
    from morfofix_engine.inference.pose import Body
    kp=np.full((33,4),.5,np.float32);kp[:,2]=0;kp[:,3]=1
    coords={0:(.5,.12),11:(.65,.3),12:(.35,.3),13:(.72,.45),14:(.28,.45),15:(.75,.6),16:(.25,.6),23:(.6,.6),24:(.4,.6),25:(.6,.77),26:(.4,.77),27:(.6,.95),28:(.4,.95)}
    for i,xy in coords.items():kp[i,:2]=xy
    for i in range(1,11):kp[i,:2]=(.5+(i%2-.5)*.1,.1+(i//2)*.01)
    return Body(0,(.2,.05,.8,.98),1.,kp,None)


def test_all_body_catalog_effects_are_finite():
    from morfofix_engine.body.slim import body_field
    from morfofix_engine.body.catalog import BODY_PARAMS
    body=synthetic_body()
    for name,spec in BODY_PARAMS.items():
        if spec.status!='ready' or name=='intensity_bodyslim':continue
        for value in (-.8,.8):
            f=body_field(120,100,[body],{'0':{name:value}})
            assert np.isfinite(f.dx).all() and np.isfinite(f.dy).all(),name
            assert max(np.max(np.abs(f.dx)),np.max(np.abs(f.dy)))>.01,name


def test_all_face_catalog_controls_are_finite(synthetic_face):
    from morfofix_engine.face.landmark_map import SLIDER_TO_GROUP
    from morfofix_engine.face.reshape import controls_from_params
    for name in SLIDER_TO_GROUP:
        src,dst,n=controls_from_params(synthetic_face,{name:.8},(400,500))
        assert np.isfinite(dst).all(),name
        assert n>0,name


def test_left_global_clamp(synthetic_face):
    from morfofix_engine.face.reshape import controls_from_params
    a=controls_from_params(synthetic_face,{'intensity_eyesize':.8,'left_intensity_eyesize':.8},(400,500))
    b=controls_from_params(synthetic_face,{'left_intensity_eyesize':1.,'right_intensity_eyesize':.8},(400,500))
    np.testing.assert_allclose(a[0],b[0]);np.testing.assert_allclose(a[1],b[1])


def test_one_image_remap_and_retouch_alpha(tmp_path,synthetic_face,monkeypatch):
    from morfofix_engine.inference.face import Face
    from morfofix_engine.retouch.effects import apply_retouch
    from morfofix_engine.core.edit_state import Retouch
    rng=np.random.default_rng(23)
    rgba=rng.integers(40,200,(100,80,4),dtype=np.uint8)
    path=tmp_path/'rgba.png';Image.fromarray(rgba).save(path)
    sess=SessionStore().create(path)
    face=Face(0,(.1,.1,.9,.9),1,synthetic_face)
    sess.faces=[face]
    for name in Retouch.model_fields:
        if name=='brush':continue
        result=apply_retouch(sess.original,[face],Retouch(**{name:.5}))
        np.testing.assert_array_equal(result[:,:,3],sess.original[:,:,3])
        assert result.dtype==np.uint8
    image_remaps=[]; original_remap=cv2.remap
    def wrapped(image,*args,**kwargs):
        if image.ndim==3 and image.shape[2]>=3:image_remaps.append(image.shape)
        return original_remap(image,*args,**kwargs)
    monkeypatch.setattr(cv2,'remap',wrapped)
    state=EditState.model_validate({'face':{'0':{'intensity_jaw':.4}},'manual_shapes':[{'type':'WaistThin_Rect','cx':.5,'cy':.7,'w':.4,'h':.3,'value':.4}],'liquify':[{'pts':[[.2,.2],[.3,.3]],'k':.2,'r':.1}]})
    render(sess,state=state)
    assert len(image_remaps)==1


def test_guided_mask_and_background_preserve_far_pixels():
    from morfofix_engine.retouch.guided import guided_filter
    from morfofix_engine.body.protect import background_plate
    rng=np.random.default_rng(4);img=rng.integers(0,255,(80,100,3),dtype=np.uint8)
    mask=np.zeros((80,100),np.float32);mask[30:50,40:60]=1
    guided=guided_filter(img.astype(np.float32)/255,mask)
    assert np.isfinite(guided).all()
    plate=background_plate(img,mask)
    np.testing.assert_array_equal(plate[:10],img[:10])


def test_render_cache_and_remove_prefix(tmp_path,rgb_png):
    app=create_app(models_dir=tmp_path,cache_dir=tmp_path/'cache')
    sess=app.state.store.create(rgb_png);sess.registry=app.state.registry
    state=EditState.model_validate({'remove':[{'strokes':[{'pts':[[.5,.5]],'radius':.02}]}]})
    first=render(sess,state=state);second=render(sess,state=state)
    np.testing.assert_array_equal(first.image,second.image)
    assert second.timings['cache_hit']==1
    assert len(sess.registry.cache.ram)>=2
    app.state.scheduler.close()


def test_16_bit_and_transparent_palette(tmp_path):
    path=tmp_path/'16.png'
    Image.fromarray(np.array([[0,32768,65535]],np.uint16)).save(path)
    image,meta=load_path(path)
    assert image[0,:,0].tolist()==[0,127,255]
    assert 'BIT_DEPTH_16_TO_8' in meta.warnings
    palette=Image.new('P',(4,4),0);palette.putpalette([255,0,0]*256)
    path=tmp_path/'palette.png';palette.save(path,transparency=0)
    image,meta=load_path(path)
    assert meta.has_alpha and not image[:,:,3].any()


def test_orthogonal_geometry_exact():
    from morfofix_engine.photo.geom import apply_geom
    img=np.arange(3*4*3,dtype=np.uint8).reshape(3,4,3)
    for k in (1,2,3):
        result,affine=apply_geom(img,(0,0,1,1),k*90,False)
        np.testing.assert_array_equal(result,np.rot90(img,k))
        x,y=affine.apply_points(np.array([[0,0]]))[0].astype(int)
        np.testing.assert_array_equal(result[y,x],img[0,0])
    cropped,_=apply_geom(img,(.999,.999,1,1),0,False)
    assert cropped.shape==(1,1,3)


def test_body_waist_narrows_silhouette():
    from dataclasses import replace
    from morfofix_engine.body.slim import body_field
    body=synthetic_body()
    mask=np.zeros((200,150),np.float32);mask[45:185,45:105]=1
    body=replace(body,seg_mask=mask)
    f=body_field(200,150,[body],{'0':{'intensity_bodyslim_waistthin':.8}})
    warped=cv2.remap(mask,*to_maps(f),cv2.INTER_LINEAR)
    row=round((.3*.38+.6*.62)*199)
    assert np.count_nonzero(warped[row]>.5)<np.count_nonzero(mask[row]>.5)


def test_format_and_image_limit(tmp_path,monkeypatch):
    from morfofix_engine.io.load import decode_image
    from io import BytesIO
    b=BytesIO();Image.new('RGB',(2,2)).save(b,format='GIF')
    with pytest.raises(ValueError):decode_image(b.getvalue())
    class Huge:
        width=10001;height=10000
        def load(self):raise AssertionError('must reject before allocation')
    monkeypatch.setattr(Image,'open',lambda _:Huge())
    with pytest.raises(ValueError):decode_image(b'anything')


def test_bad_model_hash_is_structured_503(tmp_path,rgb_png):
    import json
    (tmp_path/'face.task').write_bytes(b'not a model')
    (tmp_path/'manifest.json').write_text(json.dumps({'face_landmarker':{'file':'face.task','sha256':'0'*64}}))
    app=create_app(models_dir=tmp_path)
    with TestClient(app) as client:
        sid=client.post('/session',json={'path':str(rgb_png)}).json()['session_id']
        response=client.post(f'/session/{sid}/detect',json={'what':['face']})
        assert response.status_code==503 and response.json()['error']['code']=='MODEL_MISSING'


def test_full_document_fixture_roundtrip():
    import json
    path=Path(__file__).parent/'fixtures'/'edit_state.json'
    state=EditState.model_validate_json(path.read_text())
    assert EditState.model_validate_json(state.model_dump_json(by_alias=True))==state


def test_multipart_upload(client,rgb_png):
    with rgb_png.open('rb') as image:
        response=client.post('/session',files={'file':('photo.png',image,'image/png')})
    assert response.status_code==200
    assert response.json()['width']==80


def test_remove_coordinates_follow_crop(tmp_path):
    img=np.full((100,100,3),120,np.uint8);img[48:53,73:78]=0
    path=tmp_path/'spot.png';Image.fromarray(img).save(path)
    sess=SessionStore().create(path)
    # Right half is cropped; x=.5 in the crop corresponds to x=.75 original.
    state=EditState.model_validate({'photo':{'crop':[.5,0,1,1]},'remove':[{'strokes':[{'pts':[[.5,.5]],'radius':.04}]}]})
    result=render(sess,state=state).image
    assert result[50,25].mean()>100


def test_background_plate_reused_across_body_states(tmp_path,rgb_png,monkeypatch):
    from morfofix_engine.body import protect
    app=create_app(models_dir=tmp_path)
    sess=app.state.store.create(rgb_png);sess.registry=app.state.registry
    sess.bodies=[synthetic_body()]
    mask=np.zeros((60,80),np.float32);mask[15:55,25:55]=1
    sess.masks['person']=mask
    calls=[];original=protect.background_plate
    def counted(*args):
        calls.append(1);return original(*args)
    monkeypatch.setattr(protect,'background_plate',counted)
    for value in (.2,.4):
        state=EditState.model_validate({'body':{'0':{'intensity_bodyslim_waistthin':value}},'body_options':{'bg_protect':True}})
        render(sess,state=state)
    assert len(calls)==1
    app.state.scheduler.close()
