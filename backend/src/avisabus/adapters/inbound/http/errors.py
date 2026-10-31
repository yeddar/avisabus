"""Translate errors into RFC 9457 `application/problem+json` responses.

Responses never include tracebacks or internal details.
"""

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

PROBLEM_JSON = "application/problem+json"

_logger = structlog.get_logger(__name__)


def problem_response(status: HTTPStatus) -> JSONResponse:
    return JSONResponse(
        status_code=status.value,
        content={"type": "about:blank", "title": status.phrase, "status": status.value},
        media_type=PROBLEM_JSON,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Only the exception type is logged: messages and paths may carry identifiers.
    _logger.error("unhandled_exception", error_type=type(exc).__name__, method=request.method)
    return problem_response(HTTPStatus.INTERNAL_SERVER_ERROR)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Exception, handle_unexpected_error)
