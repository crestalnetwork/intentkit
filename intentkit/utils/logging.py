"""
Logging configuration module
"""

import json
import logging
from typing import Callable, Optional


class JsonFormatter(logging.Formatter):
    def __init__(
        self, filter_func: Optional[Callable[[logging.LogRecord], bool]] = None
    ):
        super().__init__()
        self.filter_func = filter_func

    def format(self, record):
        if self.filter_func and not self.filter_func(record):
            return ""

        log_obj = {
            "timestamp": self.formatTime(record),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # Include any extra attributes
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        elif record.__dict__.get("extra"):
            log_obj.update(record.__dict__["extra"])
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(env: str, debug: bool = False):
    """
    Setup global logging configuration.

    Args:
        env: Environment name ('local', 'prod', etc.)
        debug: Debug mode flag
    """

    if debug:
        # Set up logging configuration for local/debug
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
        # logging.getLogger("openai._base_client").setLevel(logging.INFO)
        # logging.getLogger("httpcore.http11").setLevel(logging.INFO)
        # logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
    else:
        # For non-local environments, use JSON format
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logging.basicConfig(level=logging.INFO, handlers=[handler])
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        # fastapi access log
        uvicorn_access = logging.getLogger("uvicorn.access")
        uvicorn_access.handlers = []  # Remove default handlers
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        uvicorn_access.addHandler(handler)
        uvicorn_access.setLevel(logging.WARNING)
        # telegram access log
        logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
