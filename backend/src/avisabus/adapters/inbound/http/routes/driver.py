"""Driver endpoints: login, lines and departures, departure, position, state and end of the shift
(driver_session design §3).

Every endpoint but `POST /sessions` requires the bearer token of an open shift (AC-04). Every
response carries `Cache-Control: no-store` (AC-15): the application adds it with
`NoStoreMiddleware`, so validation errors get it too.
"""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from avisabus.adapters.inbound.http.container import DriverUseCases
from avisabus.adapters.inbound.http.driver_auth import current_session, driver_use_cases
from avisabus.adapters.inbound.http.errors import (
    DEPARTURE_TAKEN_TYPE,
    INVALID_DEPARTURE_TYPE,
    INVALID_DRIVER_CODE_TYPE,
    INVALID_SESSION_TYPE,
    NETWORK_UNAVAILABLE_TYPE,
    RATE_LIMITED_TYPE,
)
from avisabus.adapters.inbound.http.routes.alerts import UNKNOWN_CLIENT
from avisabus.adapters.inbound.http.routes.stops import ProblemSchema
from avisabus.application.driver_sessions import (
    DriverSessionState,
    ListDeparturesCommand,
    SelectDriverServiceCommand,
    StartDriverSessionCommand,
    UpdateDriverPositionCommand,
)
from avisabus.domain.models.driver import DriverService, DriverSession, GpsState

router = APIRouter(prefix="/driver", tags=["driver"])

UseCases = Annotated[DriverUseCases, Depends(driver_use_cases)]
CurrentSession = Annotated[DriverSession, Depends(current_session)]


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"code": "4821 0937"}]})

    code: str = Field(description="Access code: 8 digits; spaces are ignored.")


class StartSessionResponse(BaseModel):
    session_id: str = Field(description="Random UUID v4.")
    session_token: str = Field(description="Bearer token of the shift. It is only returned here.")
    idle_timeout_s: int = Field(description="Seconds without a position before the shift closes.")


class DirectionSchema(BaseModel):
    direction_id: int
    headsign: str


class LineSchema(BaseModel):
    line: str
    color: str
    text_color: str
    directions: list[DirectionSchema]


class LinesResponse(BaseModel):
    lines: list[LineSchema] = Field(description="Lines of the active network, in line order.")


class DepartureSchema(BaseModel):
    trip_id: str
    service_date: date = Field(description="Service day of the trip (may be yesterday).")
    departure_at: datetime = Field(description="Departure from the first stop.")
    first_stop_name: str
    headsign: str
    taken: bool = Field(description="Whether another open shift already drives it.")


class DeparturesResponse(BaseModel):
    departures: list[DepartureSchema] = Field(
        description="From 30 min before to 60 min after now, by time."
    )


class ServiceSchema(BaseModel):
    line: str
    direction_id: int
    trip_id: str
    service_date: date


class PositionRequest(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(ge=0, allow_inf_nan=False)
    recorded_at: AwareDatetime = Field(description="At most 30 s in the future.")


class UpcomingStopSchema(BaseModel):
    stop_id: str
    name: str
    stop_sequence: int
    distance_m: float = Field(description="Along the shape, from the bus.")


class SessionStateResponse(BaseModel):
    session_id: str
    service: ServiceSchema | None = Field(description="The chosen departure, if any.")
    gps: GpsState = Field(
        description="`WAITING` without a position; `STALE` if the last one is over 30 s old."
    )
    off_route: bool = Field(description="The last position is over 150 m from the shape.")
    finished: bool = Field(description="The trip has reached its last stop.")
    upcoming: list[UpcomingStopSchema] = Field(description="Next stops of the trip, up to 5.")


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


_INVALID_SESSION = _problem(
    401, "Unauthorized", INVALID_SESSION_TYPE, "Missing token, or not of an open shift."
)
_NO_NETWORK = _problem(503, "Service Unavailable", NETWORK_UNAVAILABLE_TYPE, "No active GTFS feed.")

_LOGIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _problem(
        401,
        "Unauthorized",
        INVALID_DRIVER_CODE_TYPE,
        "Unknown or revoked code (same body in every case).",
    ),
    429: {
        **_problem(
            429,
            "Too Many Requests",
            RATE_LIMITED_TYPE,
            "Too many failed attempts from the IP address.",
        ),
        "headers": {
            "Retry-After": {
                "description": "Seconds to wait before trying again.",
                "schema": {"type": "integer"},
            }
        },
    },
}

_SERVICE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _INVALID_SESSION,
    409: _problem(409, "Conflict", DEPARTURE_TAKEN_TYPE, "Another open shift already drives it."),
    422: {
        "description": "The departure is not among those offered (problem+json), or the body is "
        "invalid (FastAPI validation error, application/json).",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemSchema"},
                "example": {
                    "type": INVALID_DEPARTURE_TYPE,
                    "title": "Unprocessable Entity",
                    "status": 422,
                },
            },
            "application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}},
        },
    },
    503: _NO_NETWORK,
}

_POSITION_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _INVALID_SESSION,
    422: {
        "description": "`recorded_at` is more than 30 s in the future (problem+json), or the "
        "body is invalid (FastAPI validation error, application/json).",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemSchema"},
                "example": {
                    "type": "about:blank",
                    "title": "Unprocessable Entity",
                    "status": 422,
                },
            },
            "application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}},
        },
    },
}


@router.post(
    "/sessions",
    status_code=201,
    response_model=StartSessionResponse,
    responses=_LOGIN_RESPONSES,
    response_description="Shift started. An open shift of the code is closed first.",
)
async def start_session(
    body: StartSessionRequest, request: Request, use_cases: UseCases
) -> StartSessionResponse:
    started = await use_cases.start_session.execute(
        StartDriverSessionCommand(
            code=body.code,
            client_ip=request.client.host if request.client is not None else UNKNOWN_CLIENT,
        )
    )
    return StartSessionResponse(
        session_id=started.session_id,
        session_token=started.session_token,
        idle_timeout_s=started.idle_timeout_s,
    )


@router.get(
    "/lines", response_model=LinesResponse, responses={401: _INVALID_SESSION, 503: _NO_NETWORK}
)
async def lines(_session: CurrentSession, use_cases: UseCases) -> LinesResponse:
    views = await use_cases.list_lines.execute()
    return LinesResponse(
        lines=[
            LineSchema(
                line=view.line,
                color=view.color,
                text_color=view.text_color,
                directions=[
                    DirectionSchema(direction_id=d.direction_id, headsign=d.headsign)
                    for d in view.directions
                ],
            )
            for view in views
        ]
    )


@router.get(
    "/departures",
    response_model=DeparturesResponse,
    responses={401: _INVALID_SESSION, 503: _NO_NETWORK},
)
async def departures(
    line: Annotated[str, Query()],
    direction_id: Annotated[int, Query()],
    session: CurrentSession,
    use_cases: UseCases,
) -> DeparturesResponse:
    options = await use_cases.list_departures.execute(
        ListDeparturesCommand(session=session, line=line, direction_id=direction_id)
    )
    return DeparturesResponse(
        departures=[
            DepartureSchema(
                trip_id=option.trip_id,
                service_date=option.service_date,
                departure_at=option.departure_at,
                first_stop_name=option.first_stop_name,
                headsign=option.headsign,
                taken=option.taken,
            )
            for option in options
        ]
    )


@router.put(
    "/sessions/current/service",
    response_model=SessionStateResponse,
    responses=_SERVICE_RESPONSES,
    response_description="Departure chosen; the state of the shift.",
)
async def select_service(
    body: ServiceSchema, session: CurrentSession, use_cases: UseCases
) -> SessionStateResponse:
    state = await use_cases.select_service.execute(
        SelectDriverServiceCommand(
            session=session,
            service=DriverService(
                line=body.line,
                direction_id=body.direction_id,
                trip_id=body.trip_id,
                service_date=body.service_date,
            ),
        )
    )
    return _state_schema(state)


@router.put(
    "/sessions/current/position",
    status_code=204,
    response_class=Response,
    responses=_POSITION_RESPONSES,
    response_description="Accepted (a position older than the stored one is discarded).",
)
async def update_position(
    body: PositionRequest, session: CurrentSession, use_cases: UseCases
) -> Response:
    await use_cases.update_position.execute(
        UpdateDriverPositionCommand(
            session=session,
            lat=body.lat,
            lon=body.lon,
            accuracy_m=body.accuracy_m,
            recorded_at=body.recorded_at,
        )
    )
    return Response(status_code=204)


@router.get(
    "/sessions/current",
    response_model=SessionStateResponse,
    responses={401: _INVALID_SESSION},
)
async def get_session(session: CurrentSession, use_cases: UseCases) -> SessionStateResponse:
    return _state_schema(await use_cases.get_session.execute(session))


@router.delete(
    "/sessions/current",
    status_code=204,
    response_class=Response,
    responses={401: _INVALID_SESSION},
    response_description="Shift ended and deleted with its position.",
)
async def end_session(session: CurrentSession, use_cases: UseCases) -> Response:
    await use_cases.end_session.execute(session)
    return Response(status_code=204)


def _state_schema(state: DriverSessionState) -> SessionStateResponse:
    service = state.service
    progress = state.progress
    return SessionStateResponse(
        session_id=state.session_id,
        service=(
            None
            if service is None
            else ServiceSchema(
                line=service.line,
                direction_id=service.direction_id,
                trip_id=service.trip_id,
                service_date=service.service_date,
            )
        ),
        gps=progress.gps,
        off_route=progress.off_route,
        finished=progress.finished,
        upcoming=[
            UpcomingStopSchema(
                stop_id=stop.stop_id,
                name=stop.name,
                stop_sequence=stop.stop_sequence,
                distance_m=stop.distance_m,
            )
            for stop in progress.upcoming
        ],
    )
