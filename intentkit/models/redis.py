from __future__ import annotations

import importlib
import warnings
from typing import Any

_redis = importlib.import_module("intentkit.config.redis")

warnings.warn(
    "intentkit.models.redis is deprecated; use intentkit.config.redis",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    return getattr(_redis, name)


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(dir(_redis)))


__all__ = list(getattr(_redis, "__all__", ()))
