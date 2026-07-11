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
    """Whether the toolset belongs to the web3/crypto domain (on-chain data,
    DeFi analytics, crypto markets, ...). Pickers group these under a
    "Web3 Tools" section shown only when the team owns a wallet. Purely a
    catalog/grouping flag; implies nothing about wallet usage at runtime."""

    wallet: bool = False
    """Whether the tools operate on team wallets: tools take a
    ``wallet_address``, selecting them requires the team to own at least one
    wallet, and the team's last wallet cannot be deleted while they are in
    use. Wallet toolsets are web3 by definition — ``__post_init__`` forces
    ``web3`` on, so metas set only ``wallet=True`` and every reader can
    trust ``web3`` alone for grouping."""

    icon: str | None = None
    """Icon URL path served by the API, e.g. ``/tools/erc20/erc20.svg``."""

    tools: dict[str, ToolMeta] | None = None
    """Explicit catalog override. When None (the default), the catalog is
    derived from the package's ``IntentKitTool`` subclasses."""

    def __post_init__(self) -> None:
        if self.wallet and not self.web3:
            # frozen dataclass: bypass the immutability guard for normalization
            object.__setattr__(self, "web3", True)
