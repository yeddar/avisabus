"""Stop and arrivals endpoints (stop_arrivals_api design §3, "API")."""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from avisabus.adapters.inbound.http.container import StopUseCases
from avisabus.adapters.inbound.http.errors import (
    NETWORK_UNAVAILABLE_TYPE,
    NO_STORE,
    STOP_NOT_FOUND_TYPE,
)
from avisabus.domain.models.stop_arrivals import ArrivalView, StopArrivals, StopView

router = APIRouter(tags=["stops"])


class StopLineSchema(BaseModel):
    line: str
    direction_id: int
    headsign: str
    color: str
    text_color: str


class StopResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "stop_id": "508",
                    "name": "Parc de l'Oest - Enguera",
                    "lines": [
                        {
                            "line": "70",
                            "direction_id": 1,
                            "headsign": "Alboraia",
                            "color": "FE0000",
                            "text_color": "FFFFFF",
                        },
                        {
                            "line": "93",
                            "direction_id": 0,
                            "headsign": "Passeig Marítim - Hospital Malva-rosa",
                            "color": "FE0000",
                            "text_color": "FFFFFF",
                        },
                    ],
                }
            ]
        }
    )

    stop_id: str
    name: str = Field(description="Stop name as it comes in the GTFS.")
    lines: list[StopLineSchema] = Field(description="Lines serving the stop, in natural order.")


class VehicleSchema(BaseModel):
    trip_id: str
    service_date: date


class OccupancySchema(BaseModel):
    level: Literal["FREE", "MEDIUM", "FULL"]
    has_free_seats: bool
    free_seats: int


class ArrivalSchema(BaseModel):
    line: str
    destination: str = Field(
        description="GTFS headsign when the direction is resolved, otherwise the SAE text."
    )
    sae_destination: str | None = Field(
        description="Destination as given by the SAE; null when source is SCHEDULED."
    )
    direction_id: int | None
    in_network: bool
    kind: Literal["MINUTES", "CLOCK_TIME"]
    minutes: int | None
    arrival_at: datetime
    line_color: str | None
    line_text_color: str | None
    vehicle: VehicleSchema | None
    occupancy: OccupancySchema | None
    can_alert: bool


_ARRIVALS_EXAMPLE: dict[str, Any] = {
    "stop_id": "508",
    "source": "REALTIME",
    "generated_at": "2026-11-02T19:48:03Z",
    "refresh_after_s": 20,
    "arrivals": [
        {
            "line": "93",
            "destination": "Passeig Marítim - Hospital Malva-rosa",
            "sae_destination": "Pass. Marítim",
            "direction_id": 0,
            "in_network": True,
            "kind": "MINUTES",
            "minutes": 7,
            "arrival_at": "2026-11-02T19:55:03Z",
            "line_color": "FE0000",
            "line_text_color": "FFFFFF",
            "vehicle": {"trip_id": "93_994_561_488_2271_2_122", "service_date": "2026-11-02"},
            "occupancy": {"level": "MEDIUM", "has_free_seats": True, "free_seats": 6},
            "can_alert": True,
        },
        {
            "line": "N4",
            "destination": "Est.del Nord",
            "sae_destination": "Est.del Nord",
            "direction_id": None,
            "in_network": False,
            "kind": "CLOCK_TIME",
            "minutes": None,
            "arrival_at": "2026-11-02T21:41:00Z",
            "line_color": None,
            "line_text_color": None,
            "vehicle": None,
            "occupancy": None,
            "can_alert": False,
        },
    ],
}


class StopArrivalsResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_ARRIVALS_EXAMPLE]})

    stop_id: str
    source: Literal["REALTIME", "SCHEDULED"]
    generated_at: datetime
    refresh_after_s: int = Field(description="Seconds after which the client should refresh.")
    arrivals: list[ArrivalSchema] = Field(description="Sorted by arrival_at.")


class ProblemSchema(BaseModel):
    type: str
    title: str
    status: int


_PROBLEMS: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ProblemSchema,
        "description": "Missing or invalid token, or unknown stop (same body in every case).",
        "content": {
            "application/problem+json": {
                "example": {"type": STOP_NOT_FOUND_TYPE, "title": "Not Found", "status": 404}
            }
        },
    },
    503: {
        "model": ProblemSchema,
        "description": "No active GTFS feed.",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": NETWORK_UNAVAILABLE_TYPE,
                    "title": "Service Unavailable",
                    "status": 503,
                }
            }
        },
    },
}

Token = Annotated[
    str | None, Query(alias="t", description="Signed stop token of the QR (22 characters).")
]


def _use_cases(request: Request) -> StopUseCases:
    use_cases: StopUseCases = request.app.state.stop_use_cases
    return use_cases


UseCases = Annotated[StopUseCases, Depends(_use_cases)]


@router.get("/stops/{stop_id}", response_model=StopResponse, responses=_PROBLEMS)
async def get_stop(
    stop_id: str, response: Response, use_cases: UseCases, t: Token = None
) -> StopResponse:
    response.headers["Cache-Control"] = NO_STORE
    view = await use_cases.get_stop.execute(stop_id, t or "")
    return _stop_response(view)


@router.get("/stops/{stop_id}/arrivals", response_model=StopArrivalsResponse, responses=_PROBLEMS)
async def get_stop_arrivals(
    stop_id: str, response: Response, use_cases: UseCases, t: Token = None
) -> StopArrivalsResponse:
    response.headers["Cache-Control"] = NO_STORE
    result = await use_cases.get_stop_arrivals.execute(stop_id, t or "")
    return _arrivals_response(result)


def _stop_response(view: StopView) -> StopResponse:
    return StopResponse(
        stop_id=view.stop_id,
        name=view.name,
        lines=[
            StopLineSchema(
                line=d.line,
                direction_id=d.direction_id,
                headsign=d.headsign,
                color=d.color,
                text_color=d.text_color,
            )
            for d in view.lines
        ],
    )


def _arrivals_response(result: StopArrivals) -> StopArrivalsResponse:
    return StopArrivalsResponse(
        stop_id=result.stop_id,
        source=result.source.value,
        generated_at=result.generated_at,
        refresh_after_s=result.refresh_after_s,
        arrivals=[_arrival(a) for a in result.arrivals],
    )


def _arrival(arrival: ArrivalView) -> ArrivalSchema:
    occupancy = arrival.occupancy
    return ArrivalSchema(
        line=arrival.line,
        destination=arrival.destination,
        sae_destination=arrival.sae_destination,
        direction_id=arrival.direction_id,
        in_network=arrival.in_network,
        kind=arrival.kind.value,
        minutes=arrival.minutes,
        arrival_at=arrival.arrival_at,
        line_color=arrival.line_color,
        line_text_color=arrival.line_text_color,
        vehicle=None
        if arrival.vehicle is None
        else VehicleSchema(
            trip_id=arrival.vehicle.trip_id, service_date=arrival.vehicle.service_date
        ),
        occupancy=None
        if occupancy is None
        else OccupancySchema(
            level=occupancy.level.value,
            has_free_seats=occupancy.has_free_seats,
            free_seats=occupancy.free_seats,
        ),
        can_alert=arrival.can_alert,
    )
