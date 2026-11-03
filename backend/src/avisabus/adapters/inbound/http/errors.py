"""Translate errors into RFC 9457 `application/problem+json` responses.

Responses never include tracebacks or internal details.
"""

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from avisabus.domain.errors import (
    LineNotAtStopError,
    NoActiveFeedError,
    ShapeNotFoundError,
    StopNotFoundError,
)

PROBLEM_JSON = "application/problem+json"
NO_STORE = "no-store"
STOP_NOT_FOUND_TYPE = "https://avisabus/problems/stop-not-found"
NETWORK_UNAVAILABLE_TYPE = "https://avisabus/problems/network-unavailable"
SHAPE_NOT_FOUND_TYPE = "https://avisabus/problems/shape-not-found"
LINE_NOT_AT_STOP_TYPE = "https://avisabus/problems/line-not-at-stop"

_logger = structlog.get_logger(__name__)


def problem_response(
    status: HTTPStatus, problem_type: str = "about:blank", headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status.value,
        content={"type": problem_type, "title": status.phrase, "status": status.value},
        media_type=PROBLEM_JSON,
        headers=headers,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Only the exception type is logged: messages and paths may carry identifiers.
    _logger.error("unhandled_exception", error_type=type(exc).__name__, method=request.method)
    return problem_response(HTTPStatus.INTERNAL_SERVER_ERROR)


async def handle_stop_not_found(_request: Request, _exc: Exception) -> JSONResponse:
    """Same body for a missing/invalid token and an unknown stop (stop_arrivals_api AC-02)."""
    return problem_response(HTTPStatus.NOT_FOUND, STOP_NOT_FOUND_TYPE, {"Cache-Control": NO_STORE})


async def handle_no_active_feed(_request: Request, _exc: Exception) -> JSONResponse:
    return problem_response(
        HTTPStatus.SERVICE_UNAVAILABLE, NETWORK_UNAVAILABLE_TYPE, {"Cache-Control": NO_STORE}
    )


async def handle_shape_not_found(_request: Request, _exc: Exception) -> JSONResponse:
    """position_estimation AC-15."""
    return problem_response(HTTPStatus.NOT_FOUND, SHAPE_NOT_FOUND_TYPE, {"Cache-Control": NO_STORE})


async def handle_line_not_at_stop(_request: Request, _exc: Exception) -> JSONResponse:
    """position_estimation AC-12."""
    return problem_response(
        HTTPStatus.NOT_FOUND, LINE_NOT_AT_STOP_TYPE, {"Cache-Control": NO_STORE}
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StopNotFoundError, handle_stop_not_found)
    app.add_exception_handler(NoActiveFeedError, handle_no_active_feed)
    app.add_exception_handler(ShapeNotFoundError, handle_shape_not_found)
    app.add_exception_handler(LineNotAtStopError, handle_line_not_at_stop)
    app.add_exception_handler(Exception, handle_unexpected_error)
