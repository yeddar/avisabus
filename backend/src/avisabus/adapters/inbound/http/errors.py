"""Translate errors into RFC 9457 `application/problem+json` responses.

Responses never include tracebacks or internal details.
"""

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from avisabus.domain.errors import (
    BusNotRequestableError,
    InvalidDeviceIdError,
    LineNotAtStopError,
    NoActiveFeedError,
    RateLimitedError,
    ShapeNotFoundError,
    StopNotFoundError,
)

PROBLEM_JSON = "application/problem+json"
NO_STORE = "no-store"
STOP_NOT_FOUND_TYPE = "https://avisabus/problems/stop-not-found"
NETWORK_UNAVAILABLE_TYPE = "https://avisabus/problems/network-unavailable"
SHAPE_NOT_FOUND_TYPE = "https://avisabus/problems/shape-not-found"
LINE_NOT_AT_STOP_TYPE = "https://avisabus/problems/line-not-at-stop"
INVALID_DEVICE_ID_TYPE = "https://avisabus/problems/invalid-device-id"
BUS_NOT_REQUESTABLE_TYPE = "https://avisabus/problems/bus-not-requestable"
RATE_LIMITED_TYPE = "https://avisabus/problems/rate-limited"

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


async def handle_invalid_device_id(_request: Request, _exc: Exception) -> JSONResponse:
    """realtime_events AC-04: missing or invalid `X-Device-Id`. The value is never echoed."""
    return problem_response(HTTPStatus.BAD_REQUEST, INVALID_DEVICE_ID_TYPE)


async def handle_bus_not_requestable(_request: Request, _exc: Exception) -> JSONResponse:
    """alert_create AC-03: no arrival of the stop is that bus with `can_alert`."""
    return problem_response(
        HTTPStatus.UNPROCESSABLE_ENTITY, BUS_NOT_REQUESTABLE_TYPE, {"Cache-Control": NO_STORE}
    )


async def handle_rate_limited(_request: Request, exc: Exception) -> JSONResponse:
    """alert_create AC-08: `Retry-After` in seconds."""
    retry_after = exc.retry_after_s if isinstance(exc, RateLimitedError) else 1
    return problem_response(
        HTTPStatus.TOO_MANY_REQUESTS,
        RATE_LIMITED_TYPE,
        {"Cache-Control": NO_STORE, "Retry-After": str(retry_after)},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InvalidDeviceIdError, handle_invalid_device_id)
    app.add_exception_handler(StopNotFoundError, handle_stop_not_found)
    app.add_exception_handler(NoActiveFeedError, handle_no_active_feed)
    app.add_exception_handler(ShapeNotFoundError, handle_shape_not_found)
    app.add_exception_handler(LineNotAtStopError, handle_line_not_at_stop)
    app.add_exception_handler(BusNotRequestableError, handle_bus_not_requestable)
    app.add_exception_handler(RateLimitedError, handle_rate_limited)
    app.add_exception_handler(Exception, handle_unexpected_error)
