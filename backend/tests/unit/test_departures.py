"""`ListDriverLines` and `ListDepartures`: window and service days with a FakeClock (T-02)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.application.driver_sessions import (
    ListDepartures,
    ListDeparturesCommand,
    ListDriverLines,
)
from avisabus.domain.errors import NoActiveFeedError
from avisabus.domain.models.driver import DriverService
from avisabus.domain.models.network import (
    Departure,
    DirectionHeadsign,
    FeedVersion,
    LineDirectionsView,
)
from tests.support.drivers import InMemorySessions, session_of
from tests.support.fake_clock import FakeClock

FEED = FeedVersion(
    1, "v", datetime(2026, 11, 1, tzinfo=UTC), date(2026, 11, 1), date(2026, 12, 1), {}
)
MONDAY = date(2026, 11, 9)
SUNDAY = date(2026, 11, 8)


class FakeNetwork:
    def __init__(
        self,
        departures: dict[date, list[Departure]] | None = None,
        lines: list[LineDirectionsView] | None = None,
        feed: FeedVersion | None = FEED,
    ) -> None:
        self._departures = departures or {}
        self._lines = lines or []
        self._feed = feed
        self.windows: dict[date, tuple[int, int]] = {}
        self.queries: list[tuple[str, int]] = []

    def active_feed(self) -> FeedVersion | None:
        return self._feed

    def list_lines(self) -> list[LineDirectionsView]:
        return self._lines

    def departures(
        self, line: str, direction_id: int, service_date: date, from_s: int, to_s: int
    ) -> list[Departure]:
        self.windows[service_date] = (from_s, to_s)
        self.queries.append((line, direction_id))
        return [
            d for d in self._departures.get(service_date, []) if from_s <= d.departure_s <= to_s
        ]


def _departure(trip_id: str, service_date: date, seconds: int) -> Departure:
    return Departure(trip_id, service_date, seconds, "First stop", "Headsign")


def _use_case(network: FakeNetwork, clock: FakeClock, sessions: InMemorySessions) -> ListDepartures:
    return ListDepartures(network, sessions, clock)


def _command(session_number: int = 1) -> ListDeparturesCommand:
    return ListDeparturesCommand(session_of(session_number), "93", 0)


@pytest.mark.spec("driver_session.AC-05")
async def test_lines_come_from_the_network() -> None:
    lines = [LineDirectionsView("93", "FE0000", "FFFFFF", (DirectionHeadsign(0, "A"),))]
    assert await ListDriverLines(FakeNetwork(lines=lines)).execute() == lines


@pytest.mark.spec("driver_session.AC-05")
async def test_lines_without_an_active_feed_are_unavailable() -> None:
    with pytest.raises(NoActiveFeedError):
        await ListDriverLines(FakeNetwork(feed=None)).execute()


@pytest.mark.spec("driver_session.AC-06")
async def test_asks_today_and_the_previous_service_day_for_the_window() -> None:
    network = FakeNetwork()
    clock = FakeClock(datetime(2026, 11, 9, 8, 0, tzinfo=UTC))  # 09:00 in Madrid
    await _use_case(network, clock, InMemorySessions()).execute(_command())
    nine = 9 * 3600
    assert network.windows == {
        MONDAY: (nine - 1800, nine + 3600),
        SUNDAY: (nine - 1800 + 86400, nine + 3600 + 86400),
    }
    assert set(network.queries) == {("93", 0)}


@pytest.mark.spec("driver_session.AC-06")
async def test_uses_the_local_day_right_after_midnight() -> None:
    network = FakeNetwork()
    # 00:10 in Madrid on Monday is still Sunday in UTC.
    clock = FakeClock(datetime(2026, 11, 8, 23, 10, tzinfo=UTC))
    await _use_case(network, clock, InMemorySessions()).execute(_command())
    assert set(network.windows) == {MONDAY, SUNDAY}
    assert network.windows[MONDAY] == (600 - 1800, 600 + 3600)


@pytest.mark.spec("driver_session.AC-06")
async def test_window_bounds_are_inclusive() -> None:
    now = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)  # 09:00 in Madrid: second 32400 of Monday
    network = FakeNetwork(
        departures={
            MONDAY: [
                _departure("before", MONDAY, 32400 - 1801),
                _departure("first", MONDAY, 32400 - 1800),
                _departure("last", MONDAY, 32400 + 3600),
                _departure("after", MONDAY, 32400 + 3601),
            ]
        }
    )
    found = await _use_case(network, FakeClock(now), InMemorySessions()).execute(_command())
    assert [d.trip_id for d in found] == ["first", "last"]


@pytest.mark.spec("driver_session.AC-06")
async def test_fractions_of_a_second_never_widen_the_window() -> None:
    network = FakeNetwork()
    now = datetime(2026, 11, 9, 8, 0, 0, 500_000, tzinfo=UTC)
    await _use_case(network, FakeClock(now), InMemorySessions()).execute(_command())
    assert network.windows[MONDAY] == (32400 - 1800 + 1, 32400 + 3600)


@pytest.mark.spec("driver_session.AC-06")
async def test_departures_of_both_service_days_are_merged_in_time_order() -> None:
    # 00:10 on Monday in Madrid. A trip at 24:20 of Sunday leaves after one at 00:15 of Monday.
    network = FakeNetwork(
        departures={
            SUNDAY: [_departure("sunday-late", SUNDAY, 24 * 3600 + 20 * 60)],
            MONDAY: [_departure("monday-early", MONDAY, 15 * 60)],
        }
    )
    clock = FakeClock(datetime(2026, 11, 8, 23, 10, tzinfo=UTC))
    found = await _use_case(network, clock, InMemorySessions()).execute(_command())
    assert [(d.trip_id, d.service_date) for d in found] == [
        ("monday-early", MONDAY),
        ("sunday-late", SUNDAY),
    ]
    assert found[0].departure_at == datetime(2026, 11, 8, 23, 15, tzinfo=UTC)
    assert found[1].departure_at == datetime(2026, 11, 8, 23, 20, tzinfo=UTC)


@pytest.mark.spec("driver_session.AC-06")
async def test_equal_times_are_ordered_by_trip() -> None:
    network = FakeNetwork(
        departures={MONDAY: [_departure("b", MONDAY, 32400), _departure("a", MONDAY, 32400)]}
    )
    clock = FakeClock(datetime(2026, 11, 9, 8, 0, tzinfo=UTC))
    found = await _use_case(network, clock, InMemorySessions()).execute(_command())
    assert [d.trip_id for d in found] == ["a", "b"]


@pytest.mark.spec("driver_session.AC-06")
async def test_service_day_starts_at_noon_minus_twelve_hours_on_a_dst_change() -> None:
    # 2026-10-25 (25 h): 12:00 local (UTC+1) − 12 h is 23:00 UTC of the 24th, i.e. 00:00 CEST + 1 h.
    change = date(2026, 10, 25)
    network = FakeNetwork(departures={change: [_departure("trip", change, 3600)]})
    start = datetime(2026, 10, 24, 23, 0, tzinfo=UTC)
    clock = FakeClock(start + timedelta(minutes=10))
    found = await _use_case(network, clock, InMemorySessions()).execute(_command())
    assert found[0].departure_at == start + timedelta(hours=1)


@pytest.mark.spec("driver_session.AC-06")
async def test_taken_tells_when_another_open_shift_holds_the_departure() -> None:
    network = FakeNetwork(
        departures={
            MONDAY: [
                _departure("held", MONDAY, 32400),
                _departure("free", MONDAY, 32460),
                _departure("mine", MONDAY, 32520),
            ]
        }
    )
    sessions = InMemorySessions(
        session_of(1, DriverService("93", 0, "mine", MONDAY)),
        session_of(2, DriverService("93", 0, "held", MONDAY)),
    )
    clock = FakeClock(datetime(2026, 11, 9, 8, 0, tzinfo=UTC))
    found = await _use_case(network, clock, sessions).execute(_command(1))
    assert {d.trip_id: d.taken for d in found} == {"held": True, "free": False, "mine": False}


@pytest.mark.spec("driver_session.AC-06")
async def test_taken_compares_the_service_day_too() -> None:
    network = FakeNetwork(departures={MONDAY: [_departure("trip", MONDAY, 32400)]})
    sessions = InMemorySessions(session_of(2, DriverService("93", 0, "trip", SUNDAY)))
    clock = FakeClock(datetime(2026, 11, 9, 8, 0, tzinfo=UTC))
    found = await _use_case(network, clock, sessions).execute(_command(1))
    assert [d.taken for d in found] == [False]


@pytest.mark.spec("driver_session.AC-06")
async def test_departures_carry_the_fields_of_the_api() -> None:
    network = FakeNetwork(departures={MONDAY: [_departure("trip", MONDAY, 32400)]})
    clock = FakeClock(datetime(2026, 11, 9, 8, 0, tzinfo=UTC))
    found = (await _use_case(network, clock, InMemorySessions()).execute(_command()))[0]
    assert (found.trip_id, found.service_date, found.first_stop_name, found.headsign) == (
        "trip",
        MONDAY,
        "First stop",
        "Headsign",
    )
    assert found.departure_at == datetime(2026, 11, 9, 8, 0, tzinfo=UTC)


@pytest.mark.spec("driver_session.AC-06")
async def test_departures_without_an_active_feed_are_unavailable() -> None:
    clock = FakeClock(datetime(2026, 11, 9, 8, 0, tzinfo=UTC))
    with pytest.raises(NoActiveFeedError):
        await _use_case(FakeNetwork(feed=None), clock, InMemorySessions()).execute(_command())
