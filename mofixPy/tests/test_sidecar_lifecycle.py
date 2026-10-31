"""Real loopback process tests: READY is usable, auth, shutdown, parent pipe EOF."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import httpx
import pytest


@pytest.mark.parametrize('closing',['http','stdin'])
def test_sidecar_lifecycle(closing,tmp_path):
    root=Path(__file__).resolve().parents[1]
    env=dict(os.environ,MORFOFIX_TOKEN='test-only-secret')
    with (tmp_path/'stderr.log').open('w+') as error:
        process=subprocess.Popen([sys.executable,'-m','morfofix_engine','--port','0','--models-dir',str(tmp_path)],cwd=root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error,text=True)
        lines=queue.Queue()
        def read():
            for line in process.stdout:
                lines.put(line)
        threading.Thread(target=read,daemon=True).start()
        try:
            line=lines.get(timeout=10)
            assert line.startswith('MORFOFIX_READY ')
            info=json.loads(line.split(' ',1)[1]);assert info['pid']==process.pid
            assert 'test-only-secret' not in line
            url=f"http://127.0.0.1:{info['port']}"
            with httpx.Client(base_url=url,trust_env=False,timeout=3) as client:
                assert client.get('/health').status_code==200
                assert client.get('/catalog').status_code==401
                if closing=='http':
                    assert client.post('/shutdown',headers={'Authorization':'Bearer test-only-secret'}).status_code==202
                else:
                    process.stdin.close()
            assert process.wait(timeout=4)==0
            error.seek(0)
            assert 'test-only-secret' not in error.read()
        finally:
            if process.poll() is None:
                process.kill();process.wait()
            if process.stdin and not process.stdin.closed:process.stdin.close()
            if process.stdout:process.stdout.close()
