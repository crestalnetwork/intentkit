"""Tests for the WeasyPrint URL fetcher SSRF guard in intentkit.utils.pdf."""

import socket
import sys
import types
from unittest.mock import MagicMock, patch

from intentkit.utils.pdf import (
    _BLOCKED_RESOURCE,
    _POST_TEMPLATE,
    _render_template,
    _safe_url_fetcher,
)

_GETADDRINFO = "intentkit.utils.ssrf.socket.getaddrinfo"


def _addrinfo(ip: str):
    """Build a minimal getaddrinfo-style result for a single address."""
    return [(None, None, None, "", (ip, 0))]


def test_blocks_non_http_scheme():
    """file:// and other non-HTTP schemes are rejected without a lookup."""
    assert _safe_url_fetcher("file:///etc/passwd") is _BLOCKED_RESOURCE


def test_blocks_loopback_host():
    with patch(_GETADDRINFO, return_value=_addrinfo("127.0.0.1")):
        assert _safe_url_fetcher("http://localhost/x.png") is _BLOCKED_RESOURCE


def test_blocks_link_local_metadata_host():
    """The cloud metadata address (169.254.169.254) must be blocked."""
    with patch(_GETADDRINFO, return_value=_addrinfo("169.254.169.254")):
        assert (
            _safe_url_fetcher("http://169.254.169.254/latest/meta-data/")
            is _BLOCKED_RESOURCE
        )


def test_blocks_private_host():
    with patch(_GETADDRINFO, return_value=_addrinfo("10.1.2.3")):
        assert _safe_url_fetcher("http://internal.svc/logo.png") is _BLOCKED_RESOURCE


def test_blocks_unresolvable_host():
    """Fail closed when DNS resolution raises."""
    with patch(_GETADDRINFO, side_effect=socket.gaierror):
        assert _safe_url_fetcher("http://nope.invalid/x.png") is _BLOCKED_RESOURCE


def test_allows_public_host():
    """A public address is allowed and delegates to WeasyPrint's fetcher.

    A stub weasyprint module is injected so the test does not require the
    native rendering libraries to be installed.
    """
    sentinel = {"string": b"img", "mime_type": "image/png"}
    fetch_mock = MagicMock(return_value=sentinel)
    fake_weasyprint = types.ModuleType("weasyprint")
    fake_weasyprint.default_url_fetcher = fetch_mock  # pyright: ignore[reportAttributeAccessIssue]
    with (
        patch(_GETADDRINFO, return_value=_addrinfo("93.184.216.34")),
        patch.dict(sys.modules, {"weasyprint": fake_weasyprint}),
    ):
        result = _safe_url_fetcher("https://cdn.example.com/cover.png")

    assert result is sentinel
    fetch_mock.assert_called_once()


def test_rendered_post_html_has_no_cover():
    """The exported PDF must not render a post cover image.

    Covers are list-only; even if a stray ``cover`` value is passed through, the
    template should ignore it and emit no cover ``<img>``.
    """
    html = _render_template(
        _POST_TEMPLATE,
        title="Hello World",
        content="<p>Body content</p>",
        agent_name="Agent",
        date="January 01, 2026",
        tags=["alpha"],
        cover="https://cdn.example.com/cover.png",
    )

    assert "post-cover" not in html
    assert "cover.png" not in html
    # The rest of the post still renders.
    assert "Hello World" in html
    assert "<p>Body content</p>" in html
    assert "alpha" in html
