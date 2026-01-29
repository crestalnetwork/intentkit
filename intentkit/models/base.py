from __future__ import annotations

import warnings

from intentkit.config.base import Base

warnings.warn(
    "intentkit.models.base is deprecated; use intentkit.config.base",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Base"]
