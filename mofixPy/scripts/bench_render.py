#!/usr/bin/env python3
"""Offline synthetic benchmark; includes fresh renders and exact-state cache hits."""
import json
from pathlib import Path
import tempfile
import time
import platform
from statistics import median
import cv2
import numpy as np
from PIL import Image
from morfofix_engine.app import create_app
from morfofix_engine.core.edit_state import EditState
from morfofix_engine.face.landmark_map import synthetic_landmarks
from morfofix_engine.inference.face import Face
from morfofix_engine.inference.pose import Body
from morfofix_engine.inference.cache import InferenceCache
from morfofix_engine.render.pipeline import render


def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        y,x=np.indices((1600,1280))
        rgb=np.stack(((x%64)*4,(y%64)*4,((x+y)%64)*4),axis=-1).astype(np.uint8)
        path=root/'grid.png';Image.fromarray(rgb).save(path)
        app=create_app(models_dir=root)
        sess=app.state.store.create(path);sess.registry=app.state.registry
        lm=synthetic_landmarks();sess.faces=[Face(0,(.1,.05,.9,.9),1,lm)]
        kp=np.zeros((33,4),np.float32);kp[:,3]=1
        kp[:,:2]=(.5,.15)
        for i,xy in {11:(.65,.3),12:(.35,.3),23:(.6,.6),24:(.4,.6),27:(.6,.95),28:(.4,.95)}.items():kp[i,:2]=xy
        mask=np.zeros((1600,1280),np.float32);mask[400:1500,400:880]=1
        sess.bodies=[Body(0,(.3,.1,.7,.95),1,kp,mask)];sess.masks['person']=mask
        records={}
        for name,state in {
            'identity':{},
            'face':{'face':{'0':{'intensity_jaw':.4}}},
            'body_background':{'body':{'0':{'intensity_bodyslim_waistthin':.4}},'body_options':{'bg_protect':True}},
            'manual_liquify_height':{
                'manual_shapes':[{'type':'WaistThin_Rect','cx':.5,'cy':.6,'w':.4,'h':.2,'value':.5}],
                'liquify':[{'pts':[[.4,.4],[.45,.4]],'k':.15,'r':.1}],
                'height':{'band':[.5,.9],'value':.4}},
        }.items():
            parsed=EditState.model_validate(state)
            fresh_samples=[];cached_samples=[]
            for _ in range(3):
                sess.registry.cache=InferenceCache()
                t=time.perf_counter();first=render(sess,state=parsed);fresh_samples.append((time.perf_counter()-t)*1000)
                t=time.perf_counter();second=render(sess,state=parsed);cached_samples.append((time.perf_counter()-t)*1000)
            fresh=median(fresh_samples);cached=median(cached_samples)
            assert np.array_equal(first.image,second.image)
            records[name]={'fresh_ms':round(fresh,2),'cached_ms':round(cached,2),'output_shape':list(first.image.shape)}
        app.state.scheduler.close()
        print(json.dumps({'python':platform.python_version(),'opencv':cv2.__version__,'platform':platform.platform(),'input':[1600,1280],'samples':3,'statistic':'median','scenarios':records},indent=2))


if __name__=='__main__':main()
