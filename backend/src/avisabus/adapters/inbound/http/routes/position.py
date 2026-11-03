"""Estimated position endpoint (position_estimation design §3, "API", AC-09–AC-12)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from avisabus.adapters.inbound.http.container import PositionUseCases
from avisabus.adapters.inbound.http.errors import (
    LINE_NOT_AT_STOP_TYPE,
    NETWORK_UNAVAILABLE_TYPE,
    NO_STORE,
    STOP_NOT_FOUND_TYPE,
)
from avisabus.adapters.inbound.http.routes.stops import ProblemSchema, Token, VehicleSchema
from avisabus.application.get_vehicle_position import VehiclePosition
from avisabus.domain.models.position import PositionEstimate

router = APIRouter(tags=["position"])

COORDINATE_DECIMALS = 6


class PositionStopSchema(BaseModel):
    stop_id: str
    name: str = Field(description="Stop name as it comes in the GTFS.")
    lat: float
    lon: float


class PositionArrivalSchema(BaseModel):
    kind: Literal["MINUTES", "CLOCK_TIME"]
    minutes: int | None
    arrival_at: datetime
    destination: str = Field(
        description="GTFS headsign when the direction is resolved, otherwise the SAE text."
    )
    sae_destination: str | None = Field(
        description="Destination as given by the SAE; null when source is SCHEDULED."
    )


class NextStopSchema(BaseModel):
    stop_id: str
    name: str


class PositionSchema(BaseModel):
    lat: float = Field(description="Estimated latitude (6 decimals).")
    lon: float = Field(description="Estimated longitude (6 decimals).")
    bearing_deg: float | None = Field(description="Bearing of the shape segment, 0–360°.")
    distance_to_stop_m: int = Field(description="Along the shape up to the stop, in metres.")
    stops_away: int = Field(description="Stops before this one still ahead of the bus.")
    next_stop: NextStopSchema


_EXAMPLE: dict[str, Any] = {
    "stop": {
        "stop_id": "508",
        "name": "Parc de l'Oest - Enguera",
        "lat": 39.46794,
        "lon": -0.39568,
    },
    "line": "93",
    "direction_id": 0,
    "headsign": "Passeig Marítim - Hospital Malva-rosa",
    "source": "REALTIME",
    "status": "EN_ROUTE",
    "generated_at": "2026-11-04T07:40:00Z",
    "refresh_after_s": 20,
    "arrival": {
        "kind": "MINUTES",
        "minutes": 4,
        "arrival_at": "2026-11-04T07:44:00Z",
        "destination": "Passeig Marítim - Hospital Malva-rosa",
        "sae_destination": "Pass. Marítim",
    },
    "vehicle": {"trip_id": "93_994_561_488_2271_2_122", "service_date": "2026-11-04"},
    "shape_id": "994_488_2271",
    "position": {
        "lat": 39.4701,
        "lon": -0.3901,
        "bearing_deg": 245.0,
        "distance_to_stop_m": 850,
        "stops_away": 3,
        "next_stop": {"stop_id": "512", "name": "Av. del Cid - Nicasio Benlloch"},
    },
}


class VehiclePositionResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_EXAMPLE]})

    stop: PositionStopSchema
    line: str
    direction_id: int
    headsign: str = Field(description="Headsign of the line and direction at the stop.")
    source: Literal["REALTIME", "SCHEDULED"]
    status: Literal["EN_ROUTE", "AT_STOP", "NOT_STARTED", "NO_VEHICLE", "NO_ARRIVAL"]
    generated_at: datetime
    refresh_after_s: int = Field(description="Seconds after which the client should refresh.")
    arrival: PositionArrivalSchema | None = Field(
        description="First arrival of the line and direction; null with NO_ARRIVAL."
    )
    vehicle: VehicleSchema | None = Field(description="Trip paired with the arrival, if any.")
    shape_id: str | None = Field(
        description="Shape of the trip, or the representative one of the line and direction."
    )
    position: PositionSchema | None = Field(
        description="Estimated position; null with NO_ARRIVAL and NO_VEHICLE."
    )


_PROBLEMS: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ProblemSchema,
        "description": (
            "Missing or invalid token, or unknown stop (same body as the stop endpoints); or "
            "the line and direction do not serve the stop."
        ),
        "content": {
            "application/problem+json": {
                "examples": {
                    "stop-not-found": {
                        "value": {"type": STOP_NOT_FOUND_TYPE, "title": "Not Found", "status": 404}
                    },
                    "line-not-at-stop": {
                        "value": {
                            "type": LINE_NOT_AT_STOP_TYPE,
                            "title": "Not Found",
                            "status": 404,
                        }
                    },
                }
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


def _use_cases(request: Request) -> PositionUseCases:
    use_cases: PositionUseCases = request.app.state.position_use_cases
    return use_cases


UseCases = Annotated[PositionUseCases, Depends(_use_cases)]


@router.get(
    "/stops/{stop_id}/lines/{line}/position",
    response_model=VehiclePositionResponse,
    responses=_PROBLEMS,
)
async def get_vehicle_position(
    stop_id: str,
    line: str,
    direction_id: Annotated[int, Query(description="Direction of the line (0 or 1).")],
    response: Response,
    use_cases: UseCases,
    t: Token = None,
) -> VehiclePositionResponse:
    response.headers["Cache-Control"] = NO_STORE
    result = await use_cases.get_vehicle_position.execute(stop_id, t or "", line, direction_id)
    return _position_response(result)


def _position_response(result: VehiclePosition) -> VehiclePositionResponse:
    arrival = result.arrival
    vehicle = None if arrival is None else arrival.vehicle
    return VehiclePositionResponse(
        stop=PositionStopSchema(
            stop_id=result.stop.stop_id,
            name=result.stop.name,
            lat=result.stop.lat,
            lon=result.stop.lon,
        ),
        line=result.line,
        direction_id=result.direction_id,
        headsign=result.headsign,
        source=result.source.value,
        status=result.status.value,
        generated_at=result.generated_at,
        refresh_after_s=result.refresh_after_s,
        arrival=None
        if arrival is None
        else PositionArrivalSchema(
            kind=arrival.kind.value,
            minutes=arrival.minutes,
            arrival_at=arrival.arrival_at,
            destination=arrival.destination,
            sae_destination=arrival.sae_destination,
        ),
        vehicle=None
        if vehicle is None
        else VehicleSchema(trip_id=vehicle.trip_id, service_date=vehicle.service_date),
        shape_id=result.shape_id,
        position=None if result.estimate is None else _position(result.estimate),
    )


def _position(estimate: PositionEstimate) -> PositionSchema:
    return PositionSchema(
        lat=round(estimate.lat, COORDINATE_DECIMALS),
        lon=round(estimate.lon, COORDINATE_DECIMALS),
        bearing_deg=estimate.bearing_deg,
        distance_to_stop_m=round(estimate.distance_to_stop_m),
        stops_away=estimate.stops_away,
        next_stop=NextStopSchema(stop_id=estimate.next_stop.stop_id, name=estimate.next_stop.name),
    )
