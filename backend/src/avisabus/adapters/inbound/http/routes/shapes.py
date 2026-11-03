"""Shape endpoint for the map (position_estimation design §3, AC-13–AC-15).

Shapes only change with the feed, so they are cacheable for a day, with an `ETag` built from the
active feed version (AC-14).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from avisabus.adapters.inbound.http.container import PositionUseCases
from avisabus.adapters.inbound.http.errors import NETWORK_UNAVAILABLE_TYPE, SHAPE_NOT_FOUND_TYPE
from avisabus.adapters.inbound.http.routes.stops import ProblemSchema
from avisabus.domain.models.position import ShapeView

router = APIRouter(tags=["shapes"])

SHAPE_CACHE_CONTROL = "public, max-age=86400"


class ShapeStopSchema(BaseModel):
    stop_id: str
    name: str = Field(description="Stop name as it comes in the GTFS.")
    lat: float
    lon: float
    sequence: int = Field(description="stop_sequence of the trip.")


class ShapeResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "shape_id": "994_488_2271",
                    "line": "93",
                    "color": "FE0000",
                    "coordinates": [[-0.3318, 39.4474], [-0.3319, 39.4475]],
                    "stops": [
                        {
                            "stop_id": "488",
                            "name": "Av. del Cid - Ricardo Micó",
                            "lat": 39.46913,
                            "lon": -0.40362,
                            "sequence": 1,
                        }
                    ],
                }
            ]
        }
    )

    shape_id: str
    line: str
    color: str | None = Field(description="Line color, hexadecimal without '#'.")
    coordinates: list[tuple[float, float]] = Field(
        description="Points of the shape in order, as GeoJSON positions [lon, lat]."
    )
    stops: list[ShapeStopSchema] = Field(
        description="Stops of the most frequent trip with this shape, in order."
    )


_RESPONSES: dict[int | str, dict[str, Any]] = {
    304: {"description": "Not modified: `If-None-Match` has the current `ETag`."},
    404: {
        "model": ProblemSchema,
        "description": "The shape does not exist in the active feed.",
        "content": {
            "application/problem+json": {
                "example": {"type": SHAPE_NOT_FOUND_TYPE, "title": "Not Found", "status": 404}
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


@router.get("/shapes/{shape_id}", response_model=ShapeResponse, responses=_RESPONSES)
async def get_shape(
    shape_id: str,
    response: Response,
    use_cases: UseCases,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Any:
    view = await use_cases.get_shape.execute(shape_id)
    headers = {"ETag": shape_etag(view), "Cache-Control": SHAPE_CACHE_CONTROL}
    if etag_matches(if_none_match, headers["ETag"]):
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return _shape_response(view)


def shape_etag(view: ShapeView) -> str:
    return f'"{view.feed_version_id}-{view.shape_id}"'


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """`If-None-Match` (RFC 9110 §13.1.2, weak comparison): `*` or a list of entity tags."""
    if if_none_match is None:
        return False
    for candidate in if_none_match.split(","):
        tag = candidate.strip()
        if tag == "*" or tag.removeprefix("W/") == etag:
            return True
    return False


def _shape_response(view: ShapeView) -> ShapeResponse:
    return ShapeResponse(
        shape_id=view.shape_id,
        line=view.line,
        color=view.color,
        coordinates=list(view.coordinates),
        stops=[
            ShapeStopSchema(
                stop_id=s.stop_id, name=s.name, lat=s.lat, lon=s.lon, sequence=s.sequence
            )
            for s in view.stops
        ],
    )
