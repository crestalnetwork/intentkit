"""
Logging configuration module
"""

import datetime
import decimal
import json
import logging
from collections.abc import Callable
from typing import Any, override

# Lazy import to avoid circular dependency
_config = None


def get_config():
    """Lazy import config to avoid circular dependency."""
    global _config
    if _config is None:
        from intentkit.config.config import config

        _config = config
    return _config


class ContextFilter(logging.Filter):
    """Filter that adds env and release to all log records."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Add env and release to the log record."""
        config = get_config()
        record.env = getattr(config, "env", "unknown")
        record.release = getattr(config, "release", "unknown")
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


def setup_logging(_env: str, debug: bool = False) -> None:
    """
    Setup global logging configuration.

    Args:
        _env: Environment name ('local', 'prod', etc.)
        debug: Debug mode flag
    """

    # Create and add context filter to inject env and release
    context_filter = ContextFilter()

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
