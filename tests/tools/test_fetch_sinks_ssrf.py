"""The SSRF guard is actually wired into every tool that fetches a URL.

tests/utils/test_ssrf.py covers the guard itself; these tests cover the call
sites, and assert that a blocked target reaches no socket. The `no_egress`
fixture is the point: it fails the test if a connection is ever opened, so a
sink that merely *reports* an error after connecting cannot pass.
"""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.clients.s3 import download_image_bytes
from intentkit.tools.http.get import HttpGet
from intentkit.tools.image.base import ImageBaseTool
from intentkit.tools.venice_image.utils import fetch_image_as_bytes
from intentkit.tools.web_scraper.utils import scrape_and_index_urls
from intentkit.tools.web_scraper.website_indexer import WebsiteIndexer
from intentkit.utils.opengraph import fetch_link_meta

INTERNAL_URL = "http://127.0.0.1:8899"
METADATA_URL = "http://169.254.169.254"
BLOCKED_URLS = [INTERNAL_URL, METADATA_URL]


@pytest.fixture(autouse=True)
def no_egress():
    """Fail the test if anything actually opens a connection."""
    with patch(
        "httpx.AsyncHTTPTransport.handle_async_request",
        side_effect=AssertionError("connection attempted"),
    ):
        yield


# --- web_scraper: the sinks named in the advisory ---


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_website_indexer_rejects_internal_base_url(url):
    """The advisory's own reproduction: indexing an internal base_url."""
    with pytest.raises(ToolException, match="Blocked request"):
        await WebsiteIndexer()._arun(base_url=url)


@pytest.mark.asyncio
async def test_robots_fetch_is_guarded():
    """The robots.txt sink refuses an internal target on its own."""
    with pytest.raises(ToolException, match="Blocked request"):
        await WebsiteIndexer()._get_robots_txt(INTERNAL_URL)


@pytest.mark.asyncio
async def test_sitemap_fetch_skips_internal_target():
    """A sitemap URL is somebody else's content, so it is skipped, not raised.

    robots.txt on a public site can list `Sitemap: http://169.254.169.254/`,
    which must not take the run down with it.
    """
    assert await WebsiteIndexer()._fetch_sitemap_content(METADATA_URL) == ""


@pytest.mark.asyncio
async def test_scrape_and_index_filters_internal_urls():
    """Blocked URLs drop out before the loader is ever constructed."""
    with patch(
        "langchain_community.document_loaders.WebBaseLoader",
        side_effect=AssertionError("loader constructed"),
    ):
        result = await scrape_and_index_urls(
            [*BLOCKED_URLS, "http://10.0.0.5/admin", "http://redis:6379/"],
            "agent-test",
            vector_manager=None,  # pyright: ignore[reportArgumentType] - unreached
        )

    assert result == (0, False, [])


@pytest.mark.asyncio
async def test_scrape_and_index_keeps_public_urls():
    """A blocked entry does not discard the public ones alongside it."""
    seen: list[str] = []

    async def fake_validate(url: str) -> None:
        if "127.0.0.1" in url:
            raise ToolException("Blocked request to internal/reserved IP address")
        seen.append(url)

    with (
        patch("intentkit.tools.web_scraper.utils.validate_fetch_url", fake_validate),
        patch(
            "langchain_community.document_loaders.WebBaseLoader",
            side_effect=RuntimeError("stop before network"),
        ),
    ):
        await scrape_and_index_urls(
            [INTERNAL_URL, "https://example.com/a"],
            "agent-test",
            vector_manager=AsyncMock(get_content_size=AsyncMock(return_value=0)),
        )

    assert seen == ["https://example.com/a"]


# --- sinks the advisory did not name ---


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_venice_image_fetch_is_guarded(url):
    """Image enhance/upscale take a URL argument and fetch it server-side."""
    with pytest.raises(ToolException, match="Blocked request"):
        await fetch_image_as_bytes(url)


class _StubImageTool(ImageBaseTool):
    """Concrete stand-in — every real image tool inherits the same sink."""

    name: str = "stub_image"
    category: str = "image"

    def has_native_key(self) -> bool:
        return False

    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        raise NotImplementedError


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_image_tool_input_download_is_guarded(url):
    """`images` is a tool argument on the shared image base class."""
    with pytest.raises(ToolException, match="Blocked request"):
        await _StubImageTool.model_construct()._download_images([url])


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_http_tool_is_guarded(url):
    """http_get takes a bare URL — the most direct sink of all."""
    with pytest.raises(ToolException, match="Blocked request"):
        await HttpGet()._arun(url=url)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_store_image_download_is_guarded(url):
    """store_image fetches an LLM-supplied URL before uploading it to S3."""
    with pytest.raises(ToolException, match="Blocked request"):
        await download_image_bytes(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_opengraph_fetch_is_guarded(url):
    """create_activity resolves link previews server-side.

    fetch_link_meta swallows its own errors and returns None, so the proof
    that nothing was fetched is `no_egress` not firing.
    """
    assert await fetch_link_meta(url) is None
