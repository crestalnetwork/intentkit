import logging
from collections.abc import Iterator, Sequence
from typing import Any, override

from fastapi.exceptions import RequestValidationError
from fastapi.utils import is_body_allowed_for_status_code
from langchain_core.tools.base import ToolException
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT

logger = logging.getLogger(__name__)


def iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    """Yield ``exc`` and every exception chained beneath it, cycle-safe.

    Follows explicit ``__cause__`` (``raise ... from``), falling back to the
    implicit ``__context__`` unless suppressed (``raise ... from None``) —
    the same order Python's own traceback rendering uses. Walking the chain
    matters because SDKs wrap the telling error: openai/anthropic
    ``APIConnectionError`` carries the httpx error as ``__cause__``, and
    langchain-google-genai wraps 4xx ``ClientError`` into a
    ``ChatGoogleGenerativeAIError`` whose status code only survives on the
    cause.
    """
    cause: BaseException | None = exc
    seen: set[int] = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        yield cause
        nxt = cause.__cause__
        if nxt is None and not cause.__suppress_context__:
            nxt = cause.__context__
        cause = nxt


def http_status_candidates(exc: BaseException) -> tuple[Any, Any, Any]:
    """Duck-typed attributes that may carry an HTTP status on an SDK exception.

    One triple covers the openai, anthropic, openrouter, and google exception
    families: ``status_code`` (openai/anthropic/openrouter response errors),
    ``code`` (openai mid-stream errors, google ClientError), and
    ``response.status_code`` (httpx-style wrappers). Values are returned raw —
    they may be ``None``, ``int``, or ``str`` — callers filter and coerce.
    """
    return (
        getattr(exc, "status_code", None),
        getattr(exc, "code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    )


# Response bodies can be arbitrarily large (e.g. HTML error pages from an edge
# proxy); cap what we put into a single log line.
_PROVIDER_ERROR_BODY_LIMIT = 2000


def describe_provider_error(exc: Exception) -> str:
    """Extract provider HTTP error detail (status code + response body) for logs.

    SDK error classes (openrouter's OpenRouterError family, openai/anthropic
    APIStatusError, google's ClientError) carry the upstream status code and
    raw response body as attributes, but their ``str()`` is often just a terse
    message like "Provider returned error" — the root cause (e.g. the
    provider's own error text in OpenRouter's ``metadata.raw``) survives only
    in the body.

    Returns a single-line ``" | provider response: ..."`` suffix for the log
    line (newlines escaped so the body cannot masquerade as a traceback that
    follows it), or an empty string when nothing HTTP-shaped is found in the
    chain. The deepest chain entry with detail wins — it is closest to the
    wire, so a wrapper's generic ``code`` cannot mask the provider's real
    response. Never raises: it runs inside error handlers, where a formatting
    failure would swallow the original error.
    """
    try:
        found = ""
        for cause in iter_exception_chain(exc):
            status = None
            for candidate in http_status_candidates(cause):
                if candidate is not None:
                    status = candidate
                    break
            # SDK errors carry the raw body directly; httpx-style wrappers
            # only expose it via .response.text.
            body = getattr(cause, "body", None) or getattr(
                getattr(cause, "response", None), "text", None
            )
            if status is None and not body:
                continue
            detail = f" | provider response: type={type(cause).__name__}"
            if status is not None:
                if isinstance(status, str) and status.isdigit():
                    status = int(status)
                # openai puts non-HTTP error codes ("insufficient_quota") in
                # the same attribute; don't mislabel those as an HTTP status.
                label = "status" if isinstance(status, int) else "code"
                detail += f" {label}={status}"
            if body:
                body_text = str(body).replace("\r", "\\r").replace("\n", "\\n")
                if len(body_text) > _PROVIDER_ERROR_BODY_LIMIT:
                    body_text = (
                        body_text[:_PROVIDER_ERROR_BODY_LIMIT] + "...(truncated)"
                    )
                detail += f" body={body_text}"
            found = detail
        return found
    except Exception:
        return ""


# error messages in agent system message response


class RateLimitExceeded(Exception):
    """Rate limit exceeded"""

    message: str | None

    def __init__(self, message: str | None = "Rate limit exceeded"):
        self.message = message
        super().__init__(self.message)


class IntentKitAPIError(Exception):
    """All 3 parameters: status_code, key and message is required.
    The key is PascalCase string, to allow the frontend to test errors."""

    key: str
    message: str
    status_code: int

    def __init__(self, status_code: int, key: str, message: str):
        self.key = key
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    @override
    def __str__(self):
        return f"{self.key}: {self.message}"

    @override
    def __repr__(self):
        return f"IntentKitAPIError({self.key}, {self.message}, {self.status_code})"


async def intentkit_api_error_handler(
    request: Request, exc: IntentKitAPIError
) -> Response:
    if exc.status_code >= 500:
        logger.error("Internal Server Error for request %s: %s", request.url, exc)
    else:
        logger.info("Bad Request for request %s: %s", request.url, exc)
    return JSONResponse(
        {"error": exc.key, "msg": exc.message},
        status_code=exc.status_code,
    )


async def intentkit_other_error_handler(request: Request, exc: Exception) -> Response:
    logger.error("Internal Server Error for request %s: %s", request.url, exc)
    return JSONResponse(
        {"error": "ServerError", "msg": "Internal Server Error"},
        status_code=500,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    if exc.status_code >= 500:
        logger.error("Internal Server Error for request %s: %s", request.url, exc)
        return JSONResponse(
            {"error": "ServerError", "msg": "Internal Server Error"},
            status_code=exc.status_code,
            headers=headers,
        )
    logger.info("Bad Request for request %s: %s", request.url, exc)
    return JSONResponse(
        {"error": "BadRequest", "msg": str(exc.detail)},
        status_code=exc.status_code,
        headers=headers,
    )


def format_validation_errors(errors: Sequence[Any]) -> str:
    """Format validation errors into a more readable string."""
    formatted_errors = []

    for error in errors:
        loc = error.get("loc", [])
        msg = error.get("msg", "")
        error_type = error.get("type", "")

        # Build field path
        field_path = " -> ".join(str(part) for part in loc if part != "body")

        # Format the error message with type information
        if field_path:
            if error_type:
                formatted_error = f"Field '{field_path}' ({error_type}): {msg}"
            else:
                formatted_error = f"Field '{field_path}': {msg}"
        else:
            formatted_error = msg

        formatted_errors.append(formatted_error)

    return "; ".join(formatted_errors)


async def request_validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    formatted_msg = format_validation_errors(exc.errors())
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        content={"error": "ValidationError", "msg": formatted_msg},
    )


class IntentKitLookUpError(LookupError):
    """Custom lookup error for IntentKit."""

    pass


class AgentError(Exception):
    """Custom exception for agent-related errors."""

    agent_id: str

    def __init__(self, agent_id: str, message: str | None = None):
        self.agent_id = agent_id
        if message is None:
            message = f"Agent error occurred for agent_id: {agent_id}"
        super().__init__(message)

    @override
    def __str__(self):
        return f"AgentError(agent_id={self.agent_id}): {super().__str__()}"


class ToolError(ToolException):
    """Custom exception for tool-related errors."""

    agent_id: str
    tool_name: str

    def __init__(self, agent_id: str, tool_name: str, message: str | None = None):
        self.agent_id = agent_id
        self.tool_name = tool_name
        if message is None:
            message = (
                f"Tool error occurred for agent_id: {agent_id}, tool_name: {tool_name}"
            )
        super().__init__(message)

    @override
    def __str__(self):
        return f"ToolError(agent_id={self.agent_id}, tool_name={self.tool_name}): {super().__str__()}"
