"""Health endpoint: liveness, version and the active GTFS feed (deployment_rpi AC-10).

It always answers `200` while the process is up (the container health check relies on it);
`status` is `degraded` when there is no feed or the active one has expired.
"""

from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

import avisabus
from avisabus.adapters.inbound.http.container import GtfsStatus

router = APIRouter(tags=["health"])

LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")
"""`days_left` counts days in València (design §7)."""


class GtfsHealth(BaseModel):
    feed_version: str | None = Field(description="`feed_version` of the active feed, if any.")
    feed_end_date: date = Field(description="Last valid day of the active feed (inclusive).")
    days_left: int = Field(
        description="Days from today (Europe/Madrid) to `feed_end_date`; negative once expired."
    )


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    gtfs: GtfsHealth | None = Field(description="Active GTFS feed; `null` when there is none.")


def _gtfs_health(status: GtfsStatus | None) -> GtfsHealth | None:
    feed = None if status is None else status.network.active_feed()
    if status is None or feed is None:
        return None
    today = status.clock.now().astimezone(LOCAL_TIMEZONE).date()
    return GtfsHealth(
        feed_version=feed.feed_version,
        feed_end_date=feed.end_date,
        days_left=(feed.end_date - today).days,
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    gtfs = _gtfs_health(request.app.state.gtfs_status)
    degraded = gtfs is None or gtfs.days_left < 0
    return HealthResponse(
        status="degraded" if degraded else "ok", version=avisabus.__version__, gtfs=gtfs
    )
