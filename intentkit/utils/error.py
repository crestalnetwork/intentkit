import logging
from typing import Optional, Sequence

from fastapi.exceptions import RequestValidationError
from fastapi.utils import is_body_allowed_for_status_code
from langchain_core.tools.base import ToolException
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

logger = logging.getLogger(__name__)

# error messages in agent system message response


class RateLimitExceeded(Exception):
    """Rate limit exceeded"""

    def __init__(self, message: Optional[str] = "Rate limit exceeded"):
        self.message = message
        super().__init__(self.message)


class IntentKitAPIError(Exception):
    def __init__(self, status_code: int, key: str, message: str):
        self.key = key
        self.message = message
        self.status_code = status_code

    def __str__(self):
        return f"{self.key}: {self.message}"

    def __repr__(self):
        return f"IntentKitAPIError({self.key}, {self.message}, {self.status_code})"


async def intentkit_api_error_handler(
    request: Request, exc: IntentKitAPIError
) -> Response:
    if exc.status_code >= 500:
        logger.error(f"Internal Server Error for request {request.url}: {str(exc)}")
    else:
        logger.info(f"Bad Request for request {request.url}: {str(exc)}")
    return JSONResponse(
        {"error": exc.key, "msg": exc.message},
        status_code=exc.status_code,
    )


async def intentkit_other_error_handler(request: Request, exc: Exception) -> Response:
    logger.error(f"Internal Server Error for request {request.url}: {str(exc)}")
    return JSONResponse(
        {"error": "ServerError", "msg": "Internal Server Error"},
        status_code=500,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    if exc.status_code >= 500:
        logger.error(f"Internal Server Error for request {request.url}: {str(exc)}")
        return JSONResponse(
            {"error": "ServerError", "msg": "Internal Server Error"},
            status_code=exc.status_code,
            headers=headers,
        )
    logger.info(f"Bad Request for request {request.url}: {str(exc)}")
    return JSONResponse(
        {"error": "BadRequest", "msg": str(exc.detail)},
        status_code=exc.status_code,
        headers=headers,
    )


def format_validation_errors(errors: Sequence) -> str:
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
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    formatted_msg = format_validation_errors(exc.errors())
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "ValidationError", "msg": formatted_msg},
    )


class IntentKitLookUpError(LookupError):
    """Custom lookup error for IntentKit."""

    pass


class AgentError(Exception):
    """Custom exception for agent-related errors."""

    def __init__(self, agent_id: str, message: str | None = None):
        self.agent_id = agent_id
        if message is None:
            message = f"Agent error occurred for agent_id: {agent_id}"
        super().__init__(message)

    def __str__(self):
        return f"AgentError(agent_id={self.agent_id}): {super().__str__()}"


class SkillError(ToolException):
    """Custom exception for skill-related errors."""

    def __init__(self, agent_id: str, skill_name: str, message: str | None = None):
        self.agent_id = agent_id
        self.skill_name = skill_name
        if message is None:
            message = f"Skill error occurred for agent_id: {agent_id}, skill_name: {skill_name}"
        super().__init__(message)

    def __str__(self):
        return f"SkillError(agent_id={self.agent_id}, skill_name={self.skill_name}): {super().__str__()}"
