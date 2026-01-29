from __future__ import annotations

import importlib
import warnings
from typing import Any

_db = importlib.import_module("intentkit.config.db")

warnings.warn(
    "intentkit.models.db is deprecated; use intentkit.config.db",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    return getattr(_db, name)


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(dir(_db)))


__all__ = list(getattr(_db, "__all__", ()))
