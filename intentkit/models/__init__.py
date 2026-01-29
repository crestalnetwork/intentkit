from __future__ import annotations

import importlib
import warnings
from typing import Any

_COMPAT_MODULES = {
    "base": "intentkit.config.base",
    "db": "intentkit.config.db",
    "db_mig": "intentkit.config.db_mig",
    "redis": "intentkit.config.redis",
}


def __getattr__(name: str) -> Any:
    if name in _COMPAT_MODULES:
        warnings.warn(
            f"intentkit.models.{name} is deprecated; use {_COMPAT_MODULES[name]}",
            DeprecationWarning,
            stacklevel=2,
        )
        return importlib.import_module(_COMPAT_MODULES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(_COMPAT_MODULES.keys()))


__all__ = list(_COMPAT_MODULES.keys())
