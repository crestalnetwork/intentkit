"""
Logging configuration module
"""

import json
import logging
from collections.abc import Callable
from typing import override


class JsonFormatter(logging.Formatter):
    def __init__(self, filter_func: Callable[[logging.LogRecord], bool] | None = None):
        super().__init__()
        self.filter_func = filter_func

    @override
    def format(self, record: logging.LogRecord) -> str:
        if self.filter_func and not self.filter_func(record):
            return ""

        log_obj = {
            "timestamp": self.formatTime(record),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        extra = record.__dict__.get("extra")
        if isinstance(extra, dict):
            log_obj.update(extra)
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(env: str, debug: bool = False) -> None:
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
