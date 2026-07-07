"""Filter unavailable toolsets out of the tool catalog.

The team agent-manager relies on ``get_tools_hierarchical_text`` to advertise
tools to the LLM. Categories whose system config (API keys, etc.) is not
configured should never appear, otherwise the LLM picks tools that will never
run.
"""

from __future__ import annotations

import importlib

import pytest

from intentkit.core.agent import tool_registry


def test_unavailable_category_excluded_from_hierarchical_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Categories whose available() returns False are dropped from the listing."""
    firecrawl_module = importlib.import_module("intentkit.tools.firecrawl")
    monkeypatch.setattr(firecrawl_module, "available", lambda: False)

    text = tool_registry.get_tools_hierarchical_text()
    assert "**firecrawl**" not in text


def test_http_category_always_present() -> None:
    """The http category has no system-config gate, so it must always appear."""
    text = tool_registry.get_tools_hierarchical_text()
    assert "**http**" in text
