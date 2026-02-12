"""
Logging configuration module.

This module must remain independent of intentkit.config to avoid circular imports.
The config module calls setup_logging() and passes env/release values directly.
"""

import datetime
import decimal
import json
import logging
from collections.abc import Callable
from typing import Any, override


class ContextFilter(logging.Filter):
    """Filter that adds env and release to all log records."""

    env: str
    release: str

    def __init__(self, env: str = "unknown", release: str = "unknown") -> None:
        super().__init__()
        self.env = env
        self.release = release

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Add env and release to the log record."""
        record.env = self.env  # type: ignore[attr-defined]
        record.release = self.release  # type: ignore[attr-defined]
        return True


class JsonEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles common non-serializable types."""

    @override
    def default(self, o: Any) -> Any:
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        if isinstance(o, datetime.date):
            return o.isoformat()
        if isinstance(o, datetime.time):
            return o.isoformat()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)


class JsonFormatter(logging.Formatter):
    filter_func: Callable[[logging.LogRecord], bool] | None

    def __init__(self, filter_func: Callable[[logging.LogRecord], bool] | None = None):
        super().__init__()
        self.filter_func = filter_func

    @override
    def format(self, record: logging.LogRecord) -> str:
        if self.filter_func and not self.filter_func(record):
            return ""

        log_obj = {
            "timestamp": self.formatTime(record),
            "env": getattr(record, "env", "unknown"),
            "release": getattr(record, "release", "unknown"),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Standard LogRecord attributes to ignore
        standard_attributes = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
            "taskName",
            "env",  # Added by ContextFilter
            "release",  # Added by ContextFilter
        }

        for key, value in record.__dict__.items():
            if key not in standard_attributes and not key.startswith("_"):
                log_obj[key] = value

        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, cls=JsonEncoder)


def setup_logging(env: str, debug: bool = False, release: str = "unknown") -> None:
    """
    Setup global logging configuration.

    This function is config-independent. The caller (e.g. Config.__init__)
    is responsible for passing the correct env and release values.

    Args:
        env: Environment name ('local', 'prod', etc.)
        debug: Debug mode flag
        release: Release/version identifier
    """

    # Create and add context filter to inject env and release
    context_filter = ContextFilter(env=env, release=release)

    if debug:
        # Set up logging configuration for local/debug
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(env)s - %(release)s - %(message)s"
            )
        )
        handler.addFilter(context_filter)
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[handler],
        )
        # logging.getLogger("openai._base_client").setLevel(logging.INFO)
        # logging.getLogger("httpcore.http11").setLevel(logging.INFO)
        # logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
    else:
        # For non-local environments, use JSON format
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.addFilter(context_filter)
        logging.basicConfig(level=logging.INFO, handlers=[handler])
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        # fastapi access log
        uvicorn_access = logging.getLogger("uvicorn.access")
        uvicorn_access.handlers = []  # Remove default handlers
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.addFilter(context_filter)
        uvicorn_access.addHandler(handler)
        uvicorn_access.setLevel(logging.WARNING)
        # telegram access log
        logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
