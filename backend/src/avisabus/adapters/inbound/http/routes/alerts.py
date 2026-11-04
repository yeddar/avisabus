"""Stop request endpoints: `POST /alerts` and `GET /alerts/mine` (alert_create design §3, "API").

The device is the `X-Device-Id` header, hashed by `device_hash_from_header` (never stored nor
logged in clear). Every response of `/alerts` carries `Cache-Control: no-store` (AC-14): the
application adds it with `NoStoreMiddleware`, so validation errors get it too.
"""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from avisabus.adapters.inbound.http.container import AlertUseCases
from avisabus.adapters.inbound.http.device import device_hash_from_header
from avisabus.adapters.inbound.http.errors import (
    BUS_NOT_REQUESTABLE_TYPE,
    INVALID_DEVICE_ID_TYPE,
    NETWORK_UNAVAILABLE_TYPE,
    RATE_LIMITED_TYPE,
    STOP_NOT_FOUND_TYPE,
)
from avisabus.adapters.inbound.http.routes.stops import ProblemSchema
from avisabus.application.create_alert import CreateAlertCommand
from avisabus.domain.models.alert import Alert, AlertStatus, Need, canonical_needs

router = APIRouter(tags=["alerts"])

UNKNOWN_CLIENT = "unknown"
"""Rate-limit address when the server does not know the client's (never in practice)."""

_ALERT_EXAMPLE: dict[str, Any] = {
    "alert_id": "6f1c0d6e-3b9a-4c2e-9f4d-2a7b8c9d0e1f",
    "stop_id": "508",
    "stop_name": "Parc de l'Oest - Enguera",
    "line": "93",
    "direction_id": 0,
    "destination": "Passeig Marítim - Hospital Malva-rosa",
    "trip_id": "38_1054_561_2229_487_4_001",
    "service_date": "2026-11-04",
    "needs": ["RAMP", "VISUAL"],
    "status": "PENDING_DRIVER",
    "created_at": "2026-11-04T07:40:00Z",
    "expires_at": "2026-11-04T08:10:00Z",
}


class CreateAlertRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "stop_id": "508",
                    "token": "q8Zt3kLm0PaX1vB7cD2eFg",
                    "line": "93",
                    "direction_id": 0,
                    "trip_id": "38_1054_561_2229_487_4_001",
                    "service_date": "2026-11-04",
                    "needs": ["RAMP", "VISUAL"],
                }
            ]
        }
    )

    stop_id: str
    token: str = Field(description="Signed stop token of the QR (22 characters).")
    line: str
    direction_id: int
    trip_id: str = Field(description="`vehicle.trip_id` of the chosen arrival.")
    service_date: date = Field(description="`vehicle.service_date` of the chosen arrival.")
    needs: list[Need] = Field(description="Distinct needs, possibly none (AC-06).")

    @field_validator("needs")
    @classmethod
    def _distinct(cls, needs: list[Need]) -> list[Need]:
        canonical_needs(needs)  # ValueError (→ 422) when one is repeated
        return needs


class AlertSchema(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_ALERT_EXAMPLE]})

    alert_id: str = Field(description="Random UUID v4.")
    stop_id: str
    stop_name: str
    line: str
    direction_id: int
    destination: str = Field(description="Destination of the chosen arrival.")
    trip_id: str
    service_date: date
    needs: list[Need] = Field(description="In canonical order: RAMP, EXTRA_TIME, SEAT, VISUAL.")
    status: AlertStatus
    created_at: datetime
    expires_at: datetime = Field(description="created_at + 30 min.")


class MyAlertsResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"alerts": [_ALERT_EXAMPLE]}]})

    alerts: list[AlertSchema] = Field(description="Active alerts of the device, by created_at.")


def _problem(status: int, title: str, problem_type: str, description: str) -> dict[str, Any]:
    return {
        "model": ProblemSchema,
        "description": description,
        "content": {
            "application/problem+json": {
                "example": {"type": problem_type, "title": title, "status": status}
            }
        },
    }


_INVALID_DEVICE = _problem(
    400, "Bad Request", INVALID_DEVICE_ID_TYPE, "Missing or invalid X-Device-Id header."
)

_POST_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "model": AlertSchema,
        "description": "The device already had an active alert at that stop and line: that one, "
        "unchanged.",
    },
    400: _INVALID_DEVICE,
    404: _problem(
        404,
        "Not Found",
        STOP_NOT_FOUND_TYPE,
        "Missing or invalid token, or unknown stop (same body in every case).",
    ),
    422: {
        "description": "The bus is not among the stop's arrivals that admit a request "
        "(problem+json), or the body is invalid (FastAPI validation error, application/json).",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemSchema"},
                "example": {
                    "type": BUS_NOT_REQUESTABLE_TYPE,
                    "title": "Unprocessable Entity",
                    "status": 422,
                },
            },
            "application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}},
        },
    },
    429: {
        **_problem(
            429,
            "Too Many Requests",
            RATE_LIMITED_TYPE,
            "Too many requests from the device or the IP address.",
        ),
        "headers": {
            "Retry-After": {
                "description": "Seconds to wait before trying again.",
                "schema": {"type": "integer"},
            }
        },
    },
    503: _problem(503, "Service Unavailable", NETWORK_UNAVAILABLE_TYPE, "No active GTFS feed."),
}


def _use_cases(request: Request) -> AlertUseCases:
    use_cases: AlertUseCases = request.app.state.alert_use_cases
    return use_cases


UseCases = Annotated[AlertUseCases, Depends(_use_cases)]
DeviceHash = Annotated[str, Depends(device_hash_from_header)]


@router.post(
    "/alerts",
    status_code=201,
    response_model=AlertSchema,
    responses=_POST_RESPONSES,
    response_description="Alert created.",
)
async def create_alert(
    body: CreateAlertRequest,
    request: Request,
    response: Response,
    use_cases: UseCases,
    device_hash: DeviceHash,
) -> AlertSchema:
    result = await use_cases.create_alert.execute(
        CreateAlertCommand(
            device_hash=device_hash,
            client_ip=request.client.host if request.client is not None else UNKNOWN_CLIENT,
            stop_id=body.stop_id,
            token=body.token,
            line=body.line,
            direction_id=body.direction_id,
            trip_id=body.trip_id,
            service_date=body.service_date,
            needs=canonical_needs(body.needs),
        )
    )
    if not result.created:
        response.status_code = 200
    return _alert_schema(result.alert)


@router.get("/alerts/mine", response_model=MyAlertsResponse, responses={400: _INVALID_DEVICE})
async def my_alerts(use_cases: UseCases, device_hash: DeviceHash) -> MyAlertsResponse:
    alerts = await use_cases.list_my_alerts.execute(device_hash)
    return MyAlertsResponse(alerts=[_alert_schema(alert) for alert in alerts])


def _alert_schema(alert: Alert) -> AlertSchema:
    """Same fields as `alert_payload` (events and `alerts.snapshot`)."""
    return AlertSchema(
        alert_id=alert.alert_id,
        stop_id=alert.stop_id,
        stop_name=alert.stop_name,
        line=alert.line,
        direction_id=alert.direction_id,
        destination=alert.destination,
        trip_id=alert.trip_id,
        service_date=alert.service_date,
        needs=list(alert.needs),
        status=alert.status,
        created_at=alert.created_at,
        expires_at=alert.expires_at,
    )
