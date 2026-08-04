from intentkit.tools.base import IntentKitTool

# Maximum response body size (1 MB) to prevent memory exhaustion from large responses
MAX_RESPONSE_SIZE = 1 * 1024 * 1024


def truncate_response(text: str) -> str:
    """Truncate response text if it exceeds MAX_RESPONSE_SIZE."""
    if len(text) > MAX_RESPONSE_SIZE:
        return text[:MAX_RESPONSE_SIZE] + "\n... [response truncated]"
    return text


class HttpBaseTool(IntentKitTool):
    """Base class for HTTP client tools."""

    category: str = "http"
