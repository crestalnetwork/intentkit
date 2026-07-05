"""Toolset catalog metadata, declared in code by each toolset package.

A package under ``intentkit/tools/`` is a toolset category if and only if its
``__init__.py`` exposes a module-level ``toolset`` attribute holding a
:class:`ToolsetMeta`. Category-level display data lives here; per-tool display
data (name/title/description) lives on the ``IntentKitTool`` subclasses
themselves, except for MCP-backed categories whose tools are discovered live
from the remote server and therefore declare a fixed ``tools`` override.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolMeta:
    """Catalog entry for a tool without a backing class (MCP servers)."""

    title: str
    description: str
    team_only: bool = False


@dataclass(frozen=True)
class ToolsetMeta:
    """Category-level catalog metadata for one toolset package."""

    title: str
    """Display name shown in tool pickers and the LLM tool catalog."""

    description: str
    """One-line summary shown alongside the title."""

    tags: list[str] = field(default_factory=list)
    """Grouping tags; the first tag is the primary group in the LLM catalog."""

    web3: bool = False
    """Whether the tools operate on team wallets (selectable only when the
    agent's team owns at least one wallet; tools take a ``wallet_address``)."""

    icon: str | None = None
    """Icon URL path served by the API, e.g. ``/tools/erc20/erc20.svg``."""

    tools: dict[str, ToolMeta] | None = None
    """Explicit catalog override. When None (the default), the catalog is
    derived from the package's ``IntentKitTool`` subclasses."""
