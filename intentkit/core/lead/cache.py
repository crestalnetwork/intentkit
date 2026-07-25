"""Lead agent cache management.

The storage and the pure dictionary bookkeeping live in ``intentkit.core.caches``
so that lookup-only callers (``core.chat``) can reach them without importing the
lead package. This module stays as the lead-facing name for those helpers.
"""

from __future__ import annotations

from intentkit.core.caches import (
    any_lead_executor,
    cleanup_cache,
    invalidate_lead_cache,
    lead_agents,
    lead_cache_key,
    lead_cache_prefix,
    lead_cached_at,
    lead_executors,
)

__all__ = [
    "any_lead_executor",
    "cleanup_cache",
    "invalidate_lead_cache",
    "lead_agents",
    "lead_cache_key",
    "lead_cache_prefix",
    "lead_cached_at",
    "lead_executors",
]
