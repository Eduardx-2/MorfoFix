#!/usr/bin/env python3
"""Explicit model download. Validate hash before replacing an existing model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def fetch(item,dest,*,record_hash=False):
    name=item['file']
    if Path(name).name!=name or not item['url'].startswith('https://'):
        raise ValueError('modelo requiere nombre local y URL HTTPS')
    expected=item.get('sha256')
    if not expected and not record_hash:
        raise ValueError('SHA256 no fijado; usar --record-hashes para una descarga inicial revisada')
    dest.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=dest,prefix='.model-',suffix='.tmp')
    try:
        digest=hashlib.sha256();size=0
        with os.fdopen(fd,'wb') as output,urllib.request.urlopen(item['url'],timeout=60) as response:
            while chunk:=response.read(1024*1024):
                digest.update(chunk);size+=len(chunk);output.write(chunk)
            output.flush();os.fsync(output.fileno())
        actual=digest.hexdigest()
        if expected and actual!=expected:
            raise ValueError(f'hash no coincide para {name}')
        os.replace(tmp,dest/name)
        return actual,size
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dest',type=Path,default=ROOT/'models')
    parser.add_argument('--manifest',type=Path,default=ROOT/'models'/'manifest.json')
    parser.add_argument('--only')
    parser.add_argument('--record-hashes',action='store_true',help='registrar el hash inicial; no equivale a verificar contra un hash independiente')
    args=parser.parse_args()
    spec=json.loads(args.manifest.read_text())
    keys=[args.only] if args.only else list(spec)
    for key in keys:
        if key not in spec:parser.error(f'modelo desconocido: {key}')
        item=spec[key]
        print(f'bajando {key}',file=sys.stderr)
        digest,size=fetch(item,args.dest,record_hash=args.record_hashes)
        item['sha256']=digest;item['bytes']=size
    if args.record_hashes:
        fd,tmp=tempfile.mkstemp(dir=args.manifest.parent,prefix='.manifest-',suffix='.tmp')
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(spec,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,args.manifest)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)


if __name__=='__main__':main()
