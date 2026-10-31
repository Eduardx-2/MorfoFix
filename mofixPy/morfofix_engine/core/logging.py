"""Structured stderr logs; never log authentication headers or tokens."""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data={"time":datetime.now(timezone.utc).isoformat(),"level":record.levelname.lower(),"target":record.name,"message":record.getMessage()}
        if record.exc_info:
            data['exception']=self.formatException(record.exc_info)
        return json.dumps(data,ensure_ascii=False)


def setup_logging(level='info'):
    root=logging.getLogger()
    root.setLevel(getattr(logging,level.upper(),logging.INFO))
    handler=logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.handlers[:]=[handler]
    return logging.getLogger('morfofix')
