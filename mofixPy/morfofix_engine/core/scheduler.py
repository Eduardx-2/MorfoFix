"""Single worker, latest-wins previews per session; independent jobs serialize too."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from morfofix_engine.core.errors import EngineError


class RenderScheduler:
    def __init__(self):
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="morfofix-render")
        self.latest={}
        self.pending={}
        self.active=False

    async def submit(self,sid,rev,job):
        if rev <= self.latest.get(sid,-1):
            raise EngineError(409,"revisión superada")
        self.latest[sid]=rev
        future=asyncio.get_running_loop().create_future()
        if sid in self.pending:
            _,_,old=self.pending.pop(sid)
            if not old.done():
                old.set_exception(EngineError(409,"revisión superada"))
        self.pending[sid]=(rev,job,future)
        if not self.active:
            self.active=True
            asyncio.create_task(self._drain())
        return await future

    async def _drain(self):
        try:
            while self.pending:
                sid=next(iter(self.pending))
                rev,job,future=self.pending.pop(sid)
                if future.cancelled():
                    continue
                try:
                    result=await self.run(job)
                    if rev != self.latest[sid]:
                        raise EngineError(409,"revisión superada")
                    if not future.done():
                        future.set_result(result)
                except Exception as exc:
                    if not future.done():
                        future.set_exception(exc)
        finally:
            self.active=False

    async def run(self,job):
        return await asyncio.get_running_loop().run_in_executor(self.executor,job)

    def close(self):
        self.executor.shutdown(wait=True,cancel_futures=True)
