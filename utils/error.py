import logging

from fastapi.exceptions import RequestValidationError
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

logger = logging.getLogger(__name__)


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


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "BadRequest", "msg": str(exc.errors())},
    )
