"""SSRF guard for code that fetches a caller-supplied URL.

A URL that reaches an outbound request having passed through an LLM is
attacker-influenceable: a user message, a prompt-injected page, or a
`Sitemap:` line in someone else's robots.txt can all steer the request at
the deployment's own network or at a cloud metadata endpoint. Everything
that turns such a URL into a request goes through :func:`validate_fetch_url`
first.

This lives in ``utils`` deliberately. The import contract is ``utils →
config → models → abstracts → clients → wallets → tools → core``, and fetch
sinks exist at nearly every one of those layers (``utils.opengraph``,
``clients.s3``, ``tools.*``, ``core.system_tools``); only the bottom layer
is importable from all of them.

Two checks, because either alone is bypassable:

* the URL string is classified — cheap, and it holds when DNS is hostile;
* the hostname is resolved and *every* returned address is classified, which
  is what stops a public name that answers with an internal address.

Redirects are a third way in, since a validated URL is only the first hop.
The preferred wiring is therefore an httpx client built with
:func:`httpx_request_guard` — httpx runs request hooks inside its redirect
loop, so one hook covers every hop and nothing has to be validated
separately. Call :func:`validate_fetch_url` directly only where the fetch
does not go through such a client: a hand-rolled redirect loop, a URL handed
to a third party to fetch, or a batch filtered before any client exists.
:func:`requests_redirect_guard` is the adapter for ``requests``, which
exposes no request-level hook.

**Raise or skip.** When the URL is the caller's own argument, let the
exception out — the caller asked for something that will not be done, and
saying so beats a confusing empty result. When it came from third-party
content (a sitemap entry, a batch built from someone else's page), catch it,
log, and move on: one hostile entry should not take down the whole run.
"""

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from langchain_core.tools.base import ToolException

__all__ = [
    "httpx_request_guard",
    "requests_redirect_guard",
    "validate_fetch_url",
    "validate_fetch_url_sync",
]

_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Metadata services that sit on a globally routable address, so the
# is_global test below cannot catch them. AWS/GCP (169.254.169.254) and
# Alibaba (100.100.100.200) need no entry here — both already fall outside
# the global space.
_BLOCKED_IPS = frozenset(
    {
        ipaddress.ip_address("168.63.129.16"),  # Azure wireserver
    }
)

# Metadata hostnames, blocked by name so a hijacked or decoy-answering
# resolver cannot talk us into one.
_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
    }
)

# NAT64 (RFC 6052) carries an IPv4 destination in the low 32 bits of this
# globally routable prefix, so on an IPv6-only network with NAT64 —
# increasingly the cloud default — 64:ff9b::7f00:1 reaches 127.0.0.1 while
# is_global reports True. The embedded address is what gets connected to, so
# that is what must be classified. RFC 8215's 64:ff9b:1::/48 needs no entry:
# ipaddress already reports it non-global.
_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def _reject_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Raise if ``addr`` is not a public, unicast destination.

    ``not is_global`` covers private, loopback, link-local (including the
    169.254.169.254 metadata endpoint), CGNAT and the other special-use
    ranges in one test; IPv4-mapped IPv6 (``::ffff:127.0.0.1``) is unwrapped
    by ipaddress itself. Multicast is tested separately because parts of it
    are is_global=True.
    """
    if isinstance(addr, ipaddress.IPv6Address) and addr in _NAT64_PREFIX:
        addr = ipaddress.ip_address(int(addr) & 0xFFFFFFFF)

    if not addr.is_global or addr.is_multicast or addr in _BLOCKED_IPS:
        raise ToolException(
            f"Blocked request to internal/reserved IP address: {addr.compressed}"
        )


def _classify_url(url: str) -> str | None:
    """Classify a URL string without resolving it.

    Returns the hostname still needing resolution, or None when the URL
    carried an IP literal that this call already classified.

    Raises:
        ToolException: If the URL targets a blocked address.
    """
    # Both calls can raise: urlsplit defers bracket validation to .hostname,
    # so "http://[::1" (unclosed) only fails on access. Callers filter on
    # ToolException, and a batch that skips bad entries must not die on one.
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ToolException(f"Invalid URL: {url}") from exc

    if not hostname:
        raise ToolException(f"Invalid URL: {url}")

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ToolException(
            f"Blocked request with unsupported scheme '{parsed.scheme}' "
            "(only http and https are allowed)"
        )

    # Strip trailing dot (FQDN notation) to prevent bypass via "localhost." etc.
    hostname = hostname.rstrip(".").lower()

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        pass  # Not an IP literal — fall through to the hostname rules.
    else:
        _reject_blocked_ip(addr)
        return None

    if hostname in _BLOCKED_HOSTNAMES:
        raise ToolException(f"Blocked request to metadata hostname '{hostname}'")

    # Single-segment names are container service names ("redis", "localhost").
    if "." not in hostname:
        raise ToolException(
            f"Blocked request to single-segment hostname '{hostname}' "
            "(internal service names are not allowed)"
        )

    return hostname


def validate_fetch_url_sync(url: str) -> None:
    """Classify a URL and every address its hostname resolves to.

    Resolving is what catches a public hostname pointed at an internal
    address, which the string check alone cannot see. Note that this narrows
    the window rather than closing it: the client resolves the name again
    when it connects, so a record that changes in between is still
    theoretically reachable. Pinning the checked address into the connection
    is the only complete answer and is not what this guard does.

    Blocking, because :mod:`socket` resolution is; use
    :func:`validate_fetch_url` from async code.

    Raises:
        ToolException: If the URL, or any address it resolves to, is blocked.
    """
    hostname = _classify_url(url)
    if hostname is None:
        return  # An IP literal, already classified.

    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, ValueError) as exc:
        raise ToolException(f"Could not resolve host '{hostname}'") from exc

    for info in infos:
        # sockaddr is (host, port) for IPv4 and (host, port, flow, scope) for
        # IPv6, where host may carry a "%scope" suffix that ip_address rejects.
        host = str(info[4][0]).partition("%")[0]
        _reject_blocked_ip(ipaddress.ip_address(host))


async def validate_fetch_url(url: str) -> None:
    """Async :func:`validate_fetch_url_sync`, resolving off the event loop."""
    await asyncio.to_thread(validate_fetch_url_sync, url)


async def httpx_request_guard(request: httpx.Request) -> None:
    """``httpx`` request event hook that classifies every outgoing request.

    Install via ``AsyncClient(event_hooks={"request": [httpx_request_guard]})``.
    httpx runs request hooks inside its redirect loop, so this covers the
    first hop and each subsequent one, and a client carrying it needs no
    separate up-front validation. The client's own ``max_redirects`` bounds
    the chain.
    """
    await validate_fetch_url(str(request.url))


def requests_redirect_guard(response: Any, *_args: Any, **_kwargs: Any) -> Any:
    """``requests`` response hook that classifies each redirect target.

    Install on the session (``session.hooks["response"].append(...)``). The
    hook runs on the 3xx response before requests follows it, so raising here
    means the next hop is never requested.

    requests exposes no request-level hook, so unlike
    :func:`httpx_request_guard` this cannot see the first hop — validate that
    one before handing the URL over.
    """
    if response.is_redirect:
        location = response.headers.get("location")
        if location:
            validate_fetch_url_sync(urljoin(str(response.url), location))
    return response
