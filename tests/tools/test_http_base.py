"""Tests for the shared HTTP tool helpers (SSRF guard, truncation)."""

import pytest
from langchain_core.tools import ToolException

from intentkit.tools.http.base import validate_url


def test_validate_url_allows_public_targets():
    """Public domains and globally routable IPs pass."""
    validate_url("https://example.com/page")
    validate_url("https://api.example.com/v1?x=1")
    validate_url("http://8.8.8.8/dns")
    validate_url("http://[2606:4700::1111]/")


@pytest.mark.parametrize(
    "url",
    [
        # RFC 1918 private
        "http://10.0.0.1/",
        "http://192.168.1.1/admin",
        # Loopback
        "http://127.0.0.1:8080/",
        "http://[::1]/",
        # Link-local (cloud metadata endpoint)
        "http://169.254.169.254/latest/meta-data/",
        # CGNAT and unspecified — only caught by the is_global check
        "http://100.64.0.1/",
        "http://0.0.0.0/",
        # Multicast is partly is_global=True, blocked explicitly
        "http://224.0.0.1/",
        "http://233.252.0.1/",
        # IPv6 unique local
        "http://[fd00::1]/",
    ],
)
def test_validate_url_blocks_internal_ips(url):
    """Private, reserved, special-use, and multicast IP literals are blocked."""
    with pytest.raises(ToolException, match="Blocked request"):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://redis:6379/",
        "http://localhost/x",
        "http://localhost./x",  # FQDN trailing dot must not bypass the check
    ],
)
def test_validate_url_blocks_single_segment_hostnames(url):
    """Docker service names and localhost are blocked."""
    with pytest.raises(ToolException, match="Blocked request|Invalid URL"):
        validate_url(url)


def test_validate_url_rejects_missing_hostname():
    """A URL without a hostname is invalid."""
    with pytest.raises(ToolException, match="Invalid URL"):
        validate_url("not-a-url")
