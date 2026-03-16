"""OpenGraph metadata fetcher utility."""

import logging
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LinkMeta(BaseModel):
    """OpenGraph link metadata."""

    title: str | None = None
    description: str | None = None
    image: str | None = None
    favicon: str | None = None


class _OGParser(HTMLParser):
    """Parse HTML for OpenGraph meta tags and favicon link tags."""

    def __init__(self) -> None:
        super().__init__()
        self.og: dict[str, str] = {}
        self.favicon: str | None = None
        self.title: str | None = None
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v for k, v in attrs if v is not None}

        if tag == "meta":
            prop = attr_dict.get("property", "")
            name = attr_dict.get("name", "")
            content = attr_dict.get("content", "")
            if prop in ("og:title", "og:description", "og:image"):
                self.og[prop] = content
            elif name in ("description",) and "og:description" not in self.og:
                self.og["og:description"] = content

        elif tag == "link":
            rel = attr_dict.get("rel", "")
            href = attr_dict.get("href")
            if href and ("icon" in rel):
                self.favicon = href

        elif tag == "title":
            self._in_title = True
            self._title_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_parts).strip()


async def fetch_link_meta(url: str) -> LinkMeta | None:
    """Fetch OpenGraph metadata from a URL.

    Args:
        url: The URL to fetch metadata from.

    Returns:
        LinkMeta with extracted metadata, or None on any error.
    """
    try:
        async with httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; IntentKit/1.0; +https://intentkit.io)"
                ),
            },
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            # Guard against oversized HTML responses
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > 20 * 1024 * 1024:
                return None

        parser = _OGParser()
        parser.feed(resp.text)

        origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # Resolve favicon
        favicon = parser.favicon
        if favicon:
            favicon = urljoin(url, favicon)
        else:
            favicon = f"{origin}/favicon.ico"

        # Resolve image
        image = parser.og.get("og:image")
        if image:
            image = urljoin(url, image)

        return LinkMeta(
            title=parser.og.get("og:title") or parser.title,
            description=parser.og.get("og:description"),
            image=image,
            favicon=favicon,
        )
    except Exception:
        logger.warning("Failed to fetch OpenGraph metadata for %s", url, exc_info=True)
        return None
