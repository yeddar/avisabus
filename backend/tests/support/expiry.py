"""Builders and fakes for the unit tests of the alert expiry (alert_expiry T-02)."""

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta

from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking, Need
from avisabus.domain.models.arrivals import ArrivalKind
from avisabus.domain.models.network import TripStopTime
from avisabus.domain.models.stop_arrivals import (
    ArrivalSource,
    ArrivalView,
    StopArrivals,
    VehicleView,
)
from avisabus.domain.services.occupancy_simulation import service_day_start
from tests.support.network import FakeNetwork

DAY = date(2026, 11, 2)
NOW = datetime(2026, 11, 2, 19, 48, 3, tzinfo=UTC)  # 20:48:03 in València (Monday)
DEVICE = "d" * 64
ALERT_ID = "6f1c0d6e-3b9a-4c2e-9f4d-2a7b8c9d0e1f"

# Trip 93_122: the alert's stop 508 is its occurrence 12, scheduled at 19:50:35 UTC; the next stop
# (2070, occurrence 13) at 19:52:00 UTC. Trip 70_071 ends at 508 (its last stop).
AT_508 = datetime(2026, 11, 2, 19, 50, 35, tzinfo=UTC)
AT_NEXT = datetime(2026, 11, 2, 19, 52, 0, tzinfo=UTC)
LAST_STOP_AT = datetime(2026, 11, 2, 19, 55, 0, tzinfo=UTC)


def service_s(when: datetime, service_date: date = DAY) -> int:
    return int((when - service_day_start(service_date)).total_seconds())


def stop_time(stop_id: str, sequence: int, when: datetime) -> TripStopTime:
    return TripStopTime(stop_id, sequence, service_s(when), service_s(when), None)


def network() -> FakeNetwork:
    fake = FakeNetwork()
    fake.add_stop("508", "Parc de l'Oest - Enguera")
    fake.add_stop("2070", "Avinguda del Port - Tres Forques")
    fake.trips["93_122"] = [
        stop_time("100", 11, AT_508 - timedelta(minutes=2)),
        stop_time("508", 12, AT_508),
        stop_time("2070", 13, AT_NEXT),
    ]
    fake.trips["70_071"] = [
        stop_time("300", 7, LAST_STOP_AT - timedelta(minutes=3)),
        stop_time("508", 8, LAST_STOP_AT),
    ]
    return fake


def alert(**changes: object) -> Alert:
    """Alert on the 93 at 508 (trip 93_122), created at `NOW`, last seen then arriving in 3 min
    (delay +60 s)."""
    base = Alert(
        alert_id=ALERT_ID,
        device_hash=DEVICE,
        stop_id="508",
        stop_name="Parc de l'Oest - Enguera",
        line="93",
        direction_id=0,
        destination="Passeig Marítim - Hospital Malva-rosa",
        trip_id="93_122",
        service_date=DAY,
        stop_sequence=12,
        needs=(Need.RAMP, Need.VISUAL),
        status=AlertStatus.PENDING_DRIVER,
        delivered_to=None,
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
        tracking=AlertTracking(NOW, NOW + timedelta(minutes=3), 60),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def arrival(
    trip_id: str | None,
    arrival_at: datetime,
    line: str = "93",
    service_date: date = DAY,
    minutes: int | None = None,
) -> ArrivalView:
    vehicle = None if trip_id is None else VehicleView(trip_id, service_date)
    return ArrivalView(
        line=line,
        destination="Passeig Marítim - Hospital Malva-rosa",
        direction_id=0,
        in_network=True,
        kind=ArrivalKind.MINUTES,
        minutes=minutes,
        arrival_at=arrival_at,
        line_color=None,
        line_text_color=None,
        sae_destination="Pass. Marítim",
        vehicle=vehicle,
        occupancy=None,
        can_alert=vehicle is not None,
    )


def observation(
    stop_id: str,
    generated_at: datetime,
    *arrivals: ArrivalView,
    source: ArrivalSource = ArrivalSource.REALTIME,
) -> StopArrivals:
    return StopArrivals(
        stop_id=stop_id,
        source=source,
        generated_at=generated_at,
        refresh_after_s=20,
        arrivals=tuple(sorted(arrivals, key=lambda a: a.arrival_at)),
    )


@dataclass
class ScriptedStopArrivals:
    """Stand-in for `GetStopArrivals`: answers `for_stop` with the next scripted observation (or
    exception) of the stop and records every call."""

    script: dict[str, list[StopArrivals | Exception]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def then(self, stop_id: str, *answers: StopArrivals | Exception) -> None:
        self.script.setdefault(stop_id, []).extend(answers)

    async def for_stop(self, stop_id: str) -> StopArrivals:
        self.calls.append(stop_id)
        answer = self.script[stop_id].pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def execute(self, stop_id: str, token: str) -> StopArrivals:
        raise AssertionError("the background tasks never use a stop token")


@dataclass
class RecordingNotifier:
    removed: list[str] = field(default_factory=list)

    def alert_removed(self, session_id: str) -> None:
        self.removed.append(session_id)
