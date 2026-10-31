"""Local sidecar: ephemeral port, environment token, READY and stdin watchdog."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import threading
import uvicorn
from morfofix_engine import API_VERSION, __version__
from morfofix_engine.app import create_app
from morfofix_engine.core.logging import setup_logging


def main():
    parser=argparse.ArgumentParser(prog='morfofix_engine')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--token-env',default='MORFOFIX_TOKEN')
    parser.add_argument('--models-dir',type=Path,default=Path(__file__).resolve().parent.parent/'models')
    parser.add_argument('--cache-dir',type=Path,default=None)
    parser.add_argument('--log-level',default='info')
    args=parser.parse_args()
    if args.host not in {'127.0.0.1','localhost'}:
        parser.error('el motor solo escucha en 127.0.0.1')
    token=os.environ.get(args.token_env)
    if not token:
        parser.error('falta el token en la variable de entorno indicada')
    setup_logging(args.log_level)
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(('127.0.0.1',args.port)); sock.listen(128); sock.setblocking(False)
    port=sock.getsockname()[1]
    class Server(uvicorn.Server):
        async def startup(self,sockets=None):
            await super().startup(sockets=sockets)
            if self.started:
                print('MORFOFIX_READY '+json.dumps({'port':port,'pid':os.getpid(),'version':__version__,'api':API_VERSION}),flush=True)
    def stop():
        server.should_exit=True
    app=create_app(models_dir=args.models_dir,cache_dir=args.cache_dir,token=token,port=port,shutdown_callback=stop)
    server=Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level=args.log_level,access_log=False,log_config=None))
    def watchdog():
        try:
            while os.read(sys.stdin.fileno(),4096):
                pass
        finally:
            stop()
    threading.Thread(target=watchdog,daemon=True).start()
    try:
        asyncio.run(server.serve(sockets=[sock]))
    finally:
        sock.close()


if __name__=='__main__':
    main()
