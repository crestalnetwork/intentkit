from __future__ import annotations

import importlib
import warnings
from typing import Any

_db_mig = importlib.import_module("intentkit.config.db_mig")

warnings.warn(
    "intentkit.models.db_mig is deprecated; use intentkit.config.db_mig",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    return getattr(_db_mig, name)


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(dir(_db_mig)))


__all__ = list(getattr(_db_mig, "__all__", ()))
