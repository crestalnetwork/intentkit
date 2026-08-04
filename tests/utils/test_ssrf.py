"""Tests for the shared SSRF guard."""

import socket
from unittest.mock import patch

import httpx
import pytest
import requests
from langchain_core.tools.base import ToolException

from intentkit.utils.ssrf import (
    httpx_request_guard,
    requests_redirect_guard,
    validate_fetch_url,
    validate_fetch_url_sync,
)

GUARD_SOCKET = "intentkit.utils.ssrf.socket.getaddrinfo"
PUBLIC_IP = "93.184.216.34"


def _addrinfo(*ips: str) -> list:
    """Build a getaddrinfo return value for the given addresses."""
    infos = []
    for ip in ips:
        if ":" in ip:
            infos.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, 0, 0, 0)))
        else:
            infos.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)))
    return infos


# --- Rejected on the URL string alone, before any lookup ---


@pytest.mark.parametrize(
    "url",
    [
        # RFC 1918 private
        "http://10.0.0.1/",
        "http://192.168.1.1/admin",
        "http://172.16.5.5/",
        # Loopback
        "http://127.0.0.1:8080/",
        "http://[::1]/",
        # Link-local, i.e. the AWS/GCP metadata endpoint
        "http://169.254.169.254/latest/meta-data/",
        # Azure wireserver — globally routable, so only the explicit deny catches it
        "http://168.63.129.16/metadata/instance",
        # Alibaba metadata, inside the CGNAT range
        "http://100.100.100.200/latest/meta-data/",
        # CGNAT and unspecified — only caught by the is_global check
        "http://100.64.0.1/",
        "http://0.0.0.0/",
        # Multicast is partly is_global=True, blocked explicitly
        "http://224.0.0.1/",
        "http://233.252.0.1/",
        # IPv6 unique local, link local, and IPv4-mapped loopback
        "http://[fd00::1]/",
        "http://[fe80::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[::FFFF:127.0.0.1]/",  # casing must not bypass the check
        # NAT64: a globally routable prefix wrapping an internal IPv4
        "http://[64:ff9b::7f00:1]/",  # -> 127.0.0.1
        "http://[64:ff9b::a00:5]/",  # -> 10.0.0.5
        "http://[64:ff9b::a9fe:a9fe]/",  # -> 169.254.169.254
        # Numeric-but-not-parsable host forms that resolvers accept
        "http://2130706433/",  # decimal 127.0.0.1
        "http://0x7f000001/",  # hex 127.0.0.1
        # Container service names
        "http://redis:6379/",
        "http://localhost/x",
        "http://localhost./x",  # FQDN trailing dot must not bypass the check
        # Metadata hostnames, including casing and trailing-dot variants
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://METADATA.GOOGLE.INTERNAL/",
        "http://metadata.google.internal./",
        # Non-fetchable schemes
        "gopher://example.com/",
        "ftp://example.com/x",
    ],
)
def test_blocked_without_a_lookup(url):
    """Every one of these is refused by the string check, costing no DNS."""
    with patch(GUARD_SOCKET) as resolve:
        with pytest.raises(ToolException, match="Blocked request"):
            validate_fetch_url_sync(url)
    resolve.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "file:///etc/passwd",  # every file:// path is hostless
        "http://:80/",
        # Malformed brackets: urlsplit defers the error to .hostname, and it
        # must surface as ToolException or a batch filter would die on it.
        "http://[invalid",
        "http://[::1",
        "http://[]/",
        "http://a[b]c/",
    ],
)
def test_unparsable_urls_raise_tool_exception(url):
    """Anything urlparse cannot turn into a host is invalid, not a crash."""
    with pytest.raises(ToolException, match="Invalid URL"):
        validate_fetch_url_sync(url)


def test_public_ip_literals_pass_without_a_lookup():
    """A literal is fully classified by its address; nothing to resolve."""
    with patch(GUARD_SOCKET) as resolve:
        validate_fetch_url_sync("http://8.8.8.8/dns")
        validate_fetch_url_sync("http://[2606:4700::1111]/")
        # NAT64 wrapping a public IPv4 is a legitimate way to reach it.
        validate_fetch_url_sync("http://[64:ff9b::808:808]/")  # -> 8.8.8.8
    resolve.assert_not_called()


def test_ambiguous_numeric_hosts_are_judged_by_what_resolves():
    """Forms like 0177.0.0.1 mean different addresses to different resolvers.

    Guessing would diverge from the client, which resolves the same string
    again at connect time. Classifying the resolver's own answer is what
    keeps the two in agreement, whichever way libc reads it.
    """
    with patch(GUARD_SOCKET, return_value=_addrinfo("127.0.0.1")):
        with pytest.raises(ToolException, match="127.0.0.1"):
            validate_fetch_url_sync("http://0177.0.0.1/")

    with patch(GUARD_SOCKET, return_value=_addrinfo("177.0.0.1")):
        validate_fetch_url_sync("http://0177.0.0.1/")


# --- Resolve, then classify every answer ---


def test_resolved_public_address_passes():
    """A hostname resolving only to public addresses is allowed."""
    with patch(GUARD_SOCKET, return_value=_addrinfo(PUBLIC_IP)) as resolve:
        validate_fetch_url_sync("https://example.com/page")
        validate_fetch_url_sync("https://api.example.com/v1?x=1")
    assert resolve.call_count == 2


def test_blocks_hostname_resolving_to_internal_address():
    """The rebinding case: a public name answering with a private address."""
    with patch(GUARD_SOCKET, return_value=_addrinfo("127.0.0.1")):
        with pytest.raises(ToolException, match="127.0.0.1"):
            validate_fetch_url_sync("https://rebind.example.com/")


def test_blocks_when_any_resolved_address_is_internal():
    """One internal address among several public ones is still a block."""
    with patch(GUARD_SOCKET, return_value=_addrinfo("8.8.8.8", "169.254.169.254")):
        with pytest.raises(ToolException, match="169.254.169.254"):
            validate_fetch_url_sync("https://mixed.example.com/")


def test_handles_ipv6_scope_suffix():
    """An IPv6 sockaddr may carry a %scope suffix that ip_address rejects."""
    with patch(GUARD_SOCKET, return_value=_addrinfo("fe80::1%eth0")):
        with pytest.raises(ToolException, match="Blocked request"):
            validate_fetch_url_sync("https://scoped.example.com/")


@pytest.mark.parametrize("failure", [socket.gaierror("nope"), UnicodeError, ValueError])
def test_unresolvable_host_is_rejected(failure):
    """Resolution failure fails closed rather than falling through to a request."""
    with patch(GUARD_SOCKET, side_effect=failure):
        with pytest.raises(ToolException, match="Could not resolve host"):
            validate_fetch_url_sync("https://no-such-host.example.com/")


@pytest.mark.asyncio
async def test_async_wrapper_matches_sync():
    """The async entry point applies the same rules off the event loop."""
    with patch(GUARD_SOCKET, return_value=_addrinfo(PUBLIC_IP)):
        await validate_fetch_url("https://example.com/")
    with patch(GUARD_SOCKET, return_value=_addrinfo("10.0.0.5")):
        with pytest.raises(ToolException, match="10.0.0.5"):
            await validate_fetch_url("https://example.com/")


# --- Per-hop guards ---


@pytest.mark.asyncio
async def test_httpx_guard_checks_every_request():
    """httpx runs request hooks per hop, so this covers the first one too."""
    with patch(GUARD_SOCKET, return_value=_addrinfo(PUBLIC_IP)):
        await httpx_request_guard(httpx.Request("GET", "https://example.com/ok"))

    with pytest.raises(ToolException, match="Blocked request"):
        await httpx_request_guard(httpx.Request("GET", "http://10.0.0.1/steal"))


def _requests_response(location: str | None) -> requests.Response:
    response = requests.Response()
    response.status_code = 302 if location else 200
    response.url = "https://example.com/start"
    if location:
        response.headers["Location"] = location
    return response


def test_requests_guard_blocks_internal_redirect():
    """A public page redirecting inward is stopped before the next hop."""
    with pytest.raises(ToolException, match="Blocked request"):
        requests_redirect_guard(_requests_response("http://169.254.169.254/"))


def test_requests_guard_resolves_relative_location():
    """A relative Location is resolved against the current URL, then checked."""
    with patch(GUARD_SOCKET, return_value=_addrinfo(PUBLIC_IP)) as resolve:
        requests_redirect_guard(_requests_response("/next-page"))
    resolve.assert_called_once()


def test_requests_guard_passes_through_non_redirects():
    """A normal response is returned untouched and triggers no lookup."""
    response = _requests_response(None)
    with patch(GUARD_SOCKET) as resolve:
        assert requests_redirect_guard(response) is response
    resolve.assert_not_called()
