"""Builders and fakes shared by the `driver_demand` tests (never in production)."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking, Need
from avisabus.domain.models.events import Event
from avisabus.domain.models.occupancy import OccupancyReading, VehicleRef

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)  # 09:00 in Madrid: second 32400 of Monday
MONDAY = date(2026, 11, 9)
TRIP = "trip-1"
SESSION = "session-1"


def alert_at(
    number: int,
    stop_id: str = "s1",
    stop_sequence: int = 2,
    needs: tuple[Need, ...] = (),
    *,
    trip_id: str = TRIP,
    service_date: date = MONDAY,
    status: AlertStatus = AlertStatus.DELIVERED,
    delivered_to: str | None = SESSION,
    created_at: datetime = NOW,
) -> Alert:
    """An alert of its own device (`device-<number>`), delivered to `SESSION` by default."""
    return Alert(
        alert_id=f"alert-{number}",
        device_hash=f"device-{number}",
        stop_id=stop_id,
        stop_name=f"Stop {stop_id}",
        line="93",
        direction_id=0,
        destination="Destination",
        trip_id=trip_id,
        service_date=service_date,
        stop_sequence=stop_sequence,
        needs=needs,
        status=status,
        delivered_to=delivered_to,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=30),
        tracking=AlertTracking(None, created_at, 0),
    )


@dataclass
class FakeOccupancySensor:
    """Answers `reading` for every vehicle; `reading = None` means "no data"."""

    reading: OccupancyReading | None = None
    queries: list[tuple[VehicleRef, datetime]] = field(default_factory=list)

    async def read(self, vehicle: VehicleRef, at: datetime) -> OccupancyReading | None:
        self.queries.append((vehicle, at))
        return self.reading


def occupancy(free_places: int, free_seats: int, capacity: int = 90) -> OccupancyReading:
    """A reading with those free places and seats (`seats − occupied = free_seats`)."""
    occupied = capacity - free_places
    return OccupancyReading(capacity, occupied + free_seats, occupied, NOW)


@dataclass
class ChannelPublisher:
    """Records what is published and answers `subscriber_count` from `subscribers`."""

    subscribers: dict[str, int] = field(default_factory=dict)
    published: list[tuple[str, Event]] = field(default_factory=list)

    def publish(self, channel: str, event: Event) -> None:
        self.published.append((channel, event))

    def subscribe(self, channel: str) -> Any:
        raise NotImplementedError

    def subscriber_count(self, channel: str | None = None) -> int:
        return self.subscribers.get(channel or "", 0)

    def of_type(self, event_type: str) -> list[tuple[str, Event]]:
        return [(channel, e) for channel, e in self.published if e.type == event_type]
