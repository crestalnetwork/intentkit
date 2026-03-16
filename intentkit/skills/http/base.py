import ipaddress
from urllib.parse import urlparse

from langchain_core.tools import ToolException

from intentkit.skills.base import IntentKitSkill


def validate_url(url: str) -> None:
    """Validate that a URL does not target internal networks.

    Blocks:
    - Private/reserved IP ranges (127.x, 10.x, 172.16-31.x, 192.168.x, 169.254.x, etc.)
    - Single-segment hostnames (e.g. "redis", "postgres" — typically docker service names)

    Note: This only validates the URL string. DNS rebinding attacks (a public
    hostname resolving to a private IP at request time) are not caught here.

    Raises:
        ToolException: If the URL targets a blocked address.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ToolException(f"Invalid URL: {url}")

    # Strip trailing dot (FQDN notation) to prevent bypass via "localhost." etc.
    hostname = hostname.rstrip(".")

    # Block single-segment hostnames (docker service names like "redis", "db")
    if "." not in hostname:
        raise ToolException(
            f"Blocked request to single-segment hostname '{hostname}' "
            "(internal service names are not allowed)"
        )

    # Check if hostname is an IP address in a private/reserved range
    try:
        addr = ipaddress.ip_address(hostname)
        if (
            addr.is_private
            or addr.is_reserved
            or addr.is_loopback
            or addr.is_link_local
        ):
            raise ToolException(
                f"Blocked request to internal/reserved IP address: {hostname}"
            )
    except ValueError:
        # Not an IP literal — it's a domain name, which is fine
        pass


# Maximum response body size (1 MB) to prevent memory exhaustion from large responses
MAX_RESPONSE_SIZE = 1 * 1024 * 1024


def truncate_response(text: str) -> str:
    """Truncate response text if it exceeds MAX_RESPONSE_SIZE."""
    if len(text) > MAX_RESPONSE_SIZE:
        return text[:MAX_RESPONSE_SIZE] + "\n... [response truncated]"
    return text


class HttpBaseTool(IntentKitSkill):
    """Base class for HTTP client tools."""

    category: str = "http"
