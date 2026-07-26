"""The toolset catalog endpoint feeds the frontends' tool picker.

Frontends hardcode their own form fields, so this endpoint (plus
``/metadata/llms``) is the only runtime data they need to render one.

The catalog's *shape* is covered by tests/core/test_tool_registry.py; what is
specific to the endpoint is that it serves the availability-filtered view, its
icons are usable as URLs, and it is cacheable.
"""

import json
from unittest.mock import patch

import pytest

from app.common.metadata import get_tools


async def _catalog() -> dict:
    response = await get_tools()
    return json.loads(bytes(response.body))


@pytest.mark.asyncio
async def test_serves_the_availability_filtered_catalog():
    """The endpoint must serve available_only=True, not the full catalog.

    Patching the registry call is the only way to tell the two apart: in a dev
    checkout every toolset happens to be available, so comparing live output
    against get_tool_catalog() would pass either way.
    """
    sentinel = {"only_when_filtered": {"title": "X", "description": "", "tools": {}}}
    with patch(
        "app.common.metadata.get_tool_catalog", return_value=sentinel
    ) as mock_catalog:
        body = await _catalog()

    mock_catalog.assert_called_once_with(available_only=True)
    assert body == sentinel


@pytest.mark.asyncio
async def test_icons_are_ready_to_use_as_urls():
    """`x-icon` is served as-is by GET /tools/{category}/{name}.{ext}."""
    catalog = await _catalog()

    # Not every category declares one; those that do must be usable unchanged.
    for entry in catalog.values():
        icon = entry.get("x-icon")
        if icon is not None:
            assert icon.startswith("/tools/")


@pytest.mark.asyncio
async def test_response_is_cacheable():
    """The catalog is built from code and lru_cached, so it is fixed for the
    lifetime of the deployment."""
    response = await get_tools()
    assert "max-age=3600" in response.headers["cache-control"]
