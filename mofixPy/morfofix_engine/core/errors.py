"""Stable API v0 errors, safe to expose to the local client."""
from fastapi import HTTPException
from fastapi.responses import JSONResponse

CODES={400:"BAD_PARAM",401:"UNAUTHORIZED",404:"NO_SESSION",409:"STALE_REV",415:"UNSUPPORTED_IMAGE",422:"NO_FACE",503:"MODEL_MISSING",500:"INTERNAL",421:"BAD_PARAM"}


class EngineError(HTTPException):
    def __init__(self,status_code,message,extra=None,code=None):
        self.message=message
        self.extra=extra or {}
        self.code=code or CODES.get(status_code,"INTERNAL")
        super().__init__(status_code=status_code,detail=message)


def error_response(exc):
    return JSONResponse(status_code=exc.status_code,content={"error":{"code":exc.code,"message":exc.message,"detail":exc.extra}})
