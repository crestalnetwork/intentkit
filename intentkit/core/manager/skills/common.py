"""Common definitions for manager skills."""

from __future__ import annotations

from pydantic import BaseModel


class NoArgsSchema(BaseModel):
    """Empty schema for skills without arguments."""
