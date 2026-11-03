"""`GetStopArrivals` with fakes of every port (stop_arrivals_api T-06)."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.domain.errors import ArrivalsUnavailableError, NoActiveFeedError, StopNotFoundError
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival
from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyStatus,
    OccupancyThresholds,
    VehicleRef,
)
from avisabus.domain.models.stop_arrivals import ArrivalSource, ArrivalView, VehicleView
from avisabus.domain.services.direction_resolver import DEFAULT_ALIASES
from tests.support.fake_clock import FakeClock
from tests.support.network import FakeNetwork, FakeStopTokenSigner, line_direction

NOW = datetime(2026, 11, 2, 19, 48, 3, tzinfo=UTC)  # 20:48:03 in València (Monday)
DAY = date(2026, 11, 2)
SIGNER = FakeStopTokenSigner()
TOKEN = SIGNER.sign("508")
THRESHOLDS = OccupancyThresholds()
TOLERANCE = timedelta(minutes=10)


@dataclass
class FakeArrivalsSource:
    arrivals: tuple[SaeArrival, ...] = ()
    error: str | None = None
    calls: list[str] = field(default_factory=list)

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.calls.append(stop_id)
        if self.error is not None:
            raise ArrivalsUnavailableError(stop_id, self.error)
        return ArrivalsSnapshot(stop_id=stop_id, fetched_at=NOW, arrivals=self.arrivals)


@dataclass
class FakeOccupancySensor:
    occupied: dict[str, int] = field(default_factory=dict)
    reads: list[tuple[VehicleRef, datetime]] = field(default_factory=list)

    async def read(self, vehicle: VehicleRef, at: datetime) -> OccupancyReading | None:
        self.reads.append((vehicle, at))
        occupied = self.occupied.get(vehicle.trip_id)
        if occupied is None:
            return None
        return OccupancyReading(capacity=90, seats=28, occupied=occupied, measured_at=at)


@dataclass
class FakeLogger:
    events: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def debug(self, event: str, **fields: Any) -> None:
        self.events.append(("debug", event, fields))

    def info(self, event: str, **fields: Any) -> None:
        self.events.append(("info", event, fields))

    def warning(self, event: str, **fields: Any) -> None:
        self.events.append(("warning", event, fields))

    def named(self, event: str) -> list[dict[str, Any]]:
        return [fields for _, name, fields in self.events if name == event]


@dataclass
class World:
    network: FakeNetwork
    source: FakeArrivalsSource
    sensor: FakeOccupancySensor
    logger: FakeLogger
    clock: FakeClock

    def use_case(self, **overrides: Any) -> GetStopArrivals:
        params: dict[str, Any] = {
            "network": self.network,
            "signer": SIGNER,
            "arrivals": self.source,
            "scheduled": ScheduledArrivalsProvider(self.network),
            "occupancy": self.sensor,
            "thresholds": THRESHOLDS,
            "clock": self.clock,
            "refresh_after_s": 20,
            "match_tolerance": TOLERANCE,
            "aliases": DEFAULT_ALIASES,
            "direction_overrides": {},
            "min_score": 0.2,
            "logger": self.logger,
        }
        params.update(overrides)
        return GetStopArrivals(**params)

    async def execute(self, **overrides: Any) -> Any:
        return await self.use_case(**overrides).execute("508", TOKEN)


def at(minutes: float) -> datetime:
    return NOW + timedelta(minutes=minutes)


def sae(line: str, destination: str, minutes: int) -> SaeArrival:
    return SaeArrival(line, destination, ArrivalKind.MINUTES, minutes, at(minutes))


def clock_time(line: str, destination: str, when: datetime) -> SaeArrival:
    return SaeArrival(line, destination, ArrivalKind.CLOCK_TIME, None, when)


@pytest.fixture
def world() -> World:
    network = FakeNetwork()
    network.add_line("93", "1E90FF", "FFFFFF")
    network.add_line("70", "FE0000", "000000")
    network.add_line("C1")
    network.add_stop(
        "508",
        "Parc de l'Oest - Enguera",
        line_direction("70", 1, "Alboraia"),
        line_direction("93", 0, "Passeig Marítim - Hospital Malva-rosa"),
    )
    network.add_headsign("508", "93", 0, "Passeig Marítim - Hospital Malva-rosa")
    network.add_headsign("508", "70", 1, "Alboraia")
    # Real schedule of the 93 at 508 (E-02) and some 70s.
    for suffix, when in (
        ("122", datetime(2026, 11, 2, 19, 50, 35, tzinfo=UTC)),
        ("123", datetime(2026, 11, 2, 19, 59, 8, tzinfo=UTC)),
        ("124", datetime(2026, 11, 2, 20, 8, 8, tzinfo=UTC)),
    ):
        network.add_passage(
            "508", f"93_{suffix}", "93", 0, "Passeig Marítim - Hospital Malva-rosa", when, DAY
        )
    network.add_passage("508", "70_a", "70", 1, "Alboraia", at(3), DAY)
    network.add_passage("508", "70_b", "70", 1, "Alboraia", at(40), DAY)
    sensor = FakeOccupancySensor({"93_122": 20, "93_123": 60, "70_a": 85})
    return World(network, FakeArrivalsSource(), sensor, FakeLogger(), FakeClock(NOW))


def _status(occupied: int) -> OccupancyStatus:
    from avisabus.domain.services.occupancy_classifier import classify_occupancy

    return classify_occupancy(OccupancyReading(90, 28, occupied, NOW), THRESHOLDS)


# --- Real time ---


@pytest.mark.spec("stop_arrivals_api.AC-04")
@pytest.mark.spec("stop_arrivals_api.AC-12")
@pytest.mark.spec("stop_arrivals_api.AC-21")
@pytest.mark.spec("stop_arrivals_api.AC-09")
async def test_realtime_arrivals_are_enriched_and_sorted(world: World) -> None:
    world.source.arrivals = (
        sae("93", "Pass. Marítim", 7),
        sae("70", "Alboraia", 2),
        sae("93", "Pass. Marítim", 8),
    )
    result = await world.execute()
    assert result.stop_id == "508"
    assert result.source is ArrivalSource.REALTIME
    assert result.generated_at == NOW
    assert result.refresh_after_s == 20
    assert result.arrivals == (
        ArrivalView(
            line="70",
            destination="Alboraia",
            direction_id=1,
            in_network=True,
            kind=ArrivalKind.MINUTES,
            minutes=2,
            arrival_at=at(2),
            line_color="FE0000",
            line_text_color="000000",
            sae_destination="Alboraia",
            vehicle=VehicleView("70_a", DAY),
            occupancy=_status(85),
            can_alert=True,
        ),
        ArrivalView(
            line="93",
            destination="Passeig Marítim - Hospital Malva-rosa",
            direction_id=0,
            in_network=True,
            kind=ArrivalKind.MINUTES,
            minutes=7,
            arrival_at=at(7),
            line_color="1E90FF",
            line_text_color="FFFFFF",
            sae_destination="Pass. Marítim",
            vehicle=VehicleView("93_122", DAY),
            occupancy=_status(20),
            can_alert=True,
        ),
        ArrivalView(
            line="93",
            destination="Passeig Marítim - Hospital Malva-rosa",
            direction_id=0,
            in_network=True,
            kind=ArrivalKind.MINUTES,
            minutes=8,
            arrival_at=at(8),
            line_color="1E90FF",
            line_text_color="FFFFFF",
            sae_destination="Pass. Marítim",
            vehicle=VehicleView("93_123", DAY),
            occupancy=_status(60),
            can_alert=True,
        ),
    )
    assert [a.occupancy.level for a in result.arrivals if a.occupancy] == [
        OccupancyLevel.FULL,
        OccupancyLevel.FREE,
        OccupancyLevel.MEDIUM,
    ]
    # Occupancy is read now, for the matched trip of its service day.
    assert (VehicleRef("93_122", DAY), NOW) in world.sensor.reads


@pytest.mark.spec("stop_arrivals_api.AC-10")
async def test_candidates_are_the_scheduled_passages_around_each_line_and_direction(
    world: World,
) -> None:
    world.source.arrivals = (sae("93", "Pass. Marítim", 7), sae("93", "Pass. Marítim", 8))
    await world.execute()
    # One query per (line, direction): from the first arrival − tolerance, 2·tolerance + range.
    assert world.network.scheduled_queries == [
        ("508", at(7) - TOLERANCE, 2 * TOLERANCE + timedelta(minutes=1))
    ]


@pytest.mark.spec("stop_arrivals_api.AC-22")
async def test_duplicate_sae_entries_are_kept_and_get_different_trips(world: World) -> None:
    world.source.arrivals = (sae("93", "Pass. Marítim", 7), sae("93", "Pass. Marítim", 7))
    result = await world.execute()
    assert len(result.arrivals) == 2
    assert [a.vehicle for a in result.arrivals] == [
        VehicleView("93_122", DAY),
        VehicleView("93_123", DAY),
    ]


@pytest.mark.spec("stop_arrivals_api.AC-11")
async def test_arrival_without_trip_within_tolerance(world: World) -> None:
    world.source.arrivals = (sae("70", "Alboraia", 20),)  # trips at +3 and +40 min
    result = await world.execute()
    (arrival,) = result.arrivals
    assert arrival.vehicle is None
    assert arrival.occupancy is None
    assert arrival.can_alert is True
    assert arrival.direction_id == 1
    assert world.logger.named("arrivals.trip_unmatched") == [
        {"stop_id": "508", "line": "70", "direction_id": 1}
    ]
    assert ("debug", "arrivals.trip_unmatched") in [(lvl, ev) for lvl, ev, _ in world.logger.events]


@pytest.mark.spec("stop_arrivals_api.AC-12")
async def test_matched_trip_without_sensor_reading_has_no_occupancy(world: World) -> None:
    world.source.arrivals = (sae("93", "Pass. Marítim", 17),)  # 20:05:03 → _124 (20:08:08)
    result = await world.execute()
    (arrival,) = result.arrivals
    assert arrival.vehicle == VehicleView("93_124", DAY)
    assert arrival.occupancy is None
    assert arrival.can_alert is True


@pytest.mark.spec("stop_arrivals_api.AC-07")
@pytest.mark.spec("stop_arrivals_api.AC-09")
async def test_unresolved_direction(world: World) -> None:
    world.network.add_headsign("508", "C1", 0, "Xàtiva - Institut Lluís Vives")
    world.network.add_headsign("508", "C1", 1, "Blanqueria - Pare d'Òrfens")
    world.network.add_passage("508", "C1_x", "C1", 0, "Xàtiva - Institut Lluís Vives", at(5), DAY)
    world.source.arrivals = (sae("C1", "Cntr.Històric", 5),)
    result = await world.execute()
    (arrival,) = result.arrivals
    assert arrival.direction_id is None
    assert arrival.can_alert is False
    assert arrival.destination == "Cntr.Històric"
    assert arrival.sae_destination == "Cntr.Històric"
    assert arrival.in_network is True
    assert arrival.vehicle is None
    assert arrival.occupancy is None
    assert (arrival.line_color, arrival.line_text_color) == ("FE0000", "FFFFFF")
    assert world.logger.named("arrivals.direction_unresolved") == [
        {"stop_id": "508", "line": "C1", "destination": "Cntr.Històric"}
    ]
    assert world.network.scheduled_queries == []


@pytest.mark.spec("stop_arrivals_api.AC-07")
async def test_line_in_the_network_that_does_not_serve_the_stop_is_unresolved(world: World) -> None:
    world.source.arrivals = (sae("C1", "Cntr.Històric", 5),)
    (arrival,) = (await world.execute()).arrivals
    assert (arrival.in_network, arrival.direction_id, arrival.can_alert) == (True, None, False)
    assert len(world.logger.named("arrivals.direction_unresolved")) == 1


@pytest.mark.spec("stop_arrivals_api.AC-19")
async def test_departing_direction_resolves_a_generic_destination(world: World) -> None:
    world.network.add_headsign("508", "C1", 0, "Xàtiva - Institut Lluís Vives")
    world.network.add_headsign("508", "C1", 1, "Blanqueria - Pare d'Òrfens")
    world.network.departing[("508", "C1")] = frozenset({1})
    world.network.add_passage("508", "C1_out", "C1", 1, "Blanqueria - Pare d'Òrfens", at(5), DAY)
    world.source.arrivals = (sae("C1", "Cntr.Històric", 5),)
    (arrival,) = (await world.execute()).arrivals
    assert arrival.direction_id == 1
    assert arrival.destination == "Blanqueria - Pare d'Òrfens"
    assert arrival.vehicle == VehicleView("C1_out", DAY)
    assert arrival.can_alert is True
    assert world.logger.named("arrivals.direction_unresolved") == []


async def test_departing_directions_are_only_queried_with_several_directions(world: World) -> None:
    world.source.arrivals = (sae("93", "Pass. Marítim", 7), sae("70", "Alboraia", 2))
    await world.execute()
    assert world.network.departing_queries == []


@pytest.mark.spec("stop_arrivals_api.AC-20")
async def test_override_by_line_and_sae_destination_names_a_headsign(world: World) -> None:
    world.network.add_headsign("508", "C1", 0, "Xàtiva - Institut Lluís Vives")
    world.network.add_headsign("508", "C1", 1, "Blanqueria - Pare d'Òrfens")
    world.network.departing[("508", "C1")] = frozenset({1})
    world.source.arrivals = (sae("C1", "Cntr.Històric", 5), sae("C1", "Centre", 6))
    overrides = {("C1", "Cntr.Històric"): "Xàtiva - Institut Lluís Vives"}
    result = await world.execute(direction_overrides=overrides)
    assert [(a.direction_id, a.destination) for a in result.arrivals] == [
        (0, "Xàtiva - Institut Lluís Vives"),
        (1, "Blanqueria - Pare d'Òrfens"),
    ]


async def test_min_score_and_aliases_are_passed_to_the_resolver(world: World) -> None:
    world.network.add_headsign("508", "16", 0, "Poeta Querol - Teatre Principal")
    world.network.add_headsign("508", "16", 1, "Vinalesa - Plaça d'Ausiàs March")
    world.network.add_line("16")
    world.source.arrivals = (sae("16", "Vinalesa", 5),)
    assert (await world.execute()).arrivals[0].direction_id == 1
    assert (await world.execute(min_score=0.3)).arrivals[0].direction_id is None
    # An alias that empties the SAE text leaves nothing to compare.
    assert (await world.execute(aliases={"vinalesa": ""})).arrivals[0].direction_id is None


@pytest.mark.spec("stop_arrivals_api.AC-08")
async def test_line_outside_the_network(world: World) -> None:
    world.source.arrivals = (clock_time("N4", "Est.del Nord", at(70)), sae("70", "Alboraia", 2))
    result = await world.execute()
    assert result.arrivals[1] == ArrivalView(
        line="N4",
        destination="Est.del Nord",
        direction_id=None,
        in_network=False,
        kind=ArrivalKind.CLOCK_TIME,
        minutes=None,
        arrival_at=at(70),
        line_color=None,
        line_text_color=None,
        sae_destination="Est.del Nord",
        vehicle=None,
        occupancy=None,
        can_alert=False,
    )
    assert world.logger.named("arrivals.direction_unresolved") == []


@pytest.mark.spec("stop_arrivals_api.AC-15")
async def test_sae_without_arrivals_is_an_empty_realtime_answer(world: World) -> None:
    result = await world.execute()
    assert result.source is ArrivalSource.REALTIME
    assert result.arrivals == ()
    assert world.network.scheduled_queries == []
    assert world.logger.named("arrivals.fallback") == []


# --- Fallback to the timetable ---


@pytest.mark.spec("stop_arrivals_api.AC-13")
@pytest.mark.spec("stop_arrivals_api.AC-21")
async def test_fallback_to_scheduled_arrivals_when_the_sae_is_unavailable(world: World) -> None:
    world.source.error = "timeout"
    result = await world.execute()
    assert result.source is ArrivalSource.SCHEDULED
    assert result.generated_at == NOW
    assert result.refresh_after_s == 20
    # Two per (line, direction) in 90 min, in time order: 93 at 19:50:35 and 19:59:08 UTC,
    # 70 at 19:51:03 and 20:28:03 (the third 93, at 20:08:08, is left out).
    assert [a.vehicle for a in result.arrivals] == [
        VehicleView("93_122", DAY),
        VehicleView("70_a", DAY),
        VehicleView("93_123", DAY),
        VehicleView("70_b", DAY),
    ]
    assert result.arrivals[1] == ArrivalView(
        line="70",
        destination="Alboraia",
        direction_id=1,
        in_network=True,
        kind=ArrivalKind.CLOCK_TIME,
        minutes=None,
        arrival_at=at(3),
        line_color="FE0000",
        line_text_color="000000",
        sae_destination=None,
        vehicle=VehicleView("70_a", DAY),
        occupancy=_status(85),
        can_alert=True,
    )
    assert result.arrivals[0].arrival_at == datetime(2026, 11, 2, 19, 50, 35, tzinfo=UTC)
    assert result.arrivals[0].destination == "Passeig Marítim - Hospital Malva-rosa"
    assert all(a.can_alert and a.sae_destination is None for a in result.arrivals)
    assert world.logger.named("arrivals.fallback") == [{"stop_id": "508", "reason": "timeout"}]
    assert world.network.scheduled_queries == [("508", NOW, timedelta(minutes=90))]


@pytest.mark.spec("stop_arrivals_api.AC-13")
async def test_scheduled_arrival_without_sensor_reading(world: World) -> None:
    world.source.error = "http_503"
    result = await world.execute()
    assert result.arrivals[3].vehicle == VehicleView("70_b", DAY)
    assert result.arrivals[3].occupancy is None


@pytest.mark.spec("stop_arrivals_api.AC-14")
async def test_fallback_without_scheduled_passages_is_empty(world: World) -> None:
    world.source.error = "network"
    world.clock.set(NOW + timedelta(hours=3))
    result = await world.execute()
    assert result.source is ArrivalSource.SCHEDULED
    assert result.arrivals == ()
    assert world.logger.named("arrivals.fallback") == [{"stop_id": "508", "reason": "network"}]


# --- Errors ---


@pytest.mark.spec("stop_arrivals_api.AC-02")
async def test_invalid_token_or_unknown_stop_never_asks_the_sae(world: World) -> None:
    with pytest.raises(StopNotFoundError):
        await world.use_case().execute("508", "nope")
    with pytest.raises(StopNotFoundError):
        await world.use_case().execute("999", SIGNER.sign("999"))
    assert world.source.calls == []


@pytest.mark.spec("stop_arrivals_api.AC-03")
async def test_no_active_feed(world: World) -> None:
    world.network.feed = None
    with pytest.raises(NoActiveFeedError):
        await world.execute()
    assert world.source.calls == []
