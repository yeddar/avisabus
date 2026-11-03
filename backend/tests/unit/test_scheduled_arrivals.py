"""`ScheduledArrivalsProvider`: next scheduled passages per line and direction (T-05)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from tests.support.network import FakeNetwork

NOW = datetime(2026, 11, 2, 19, 0, tzinfo=UTC)
DAY = date(2026, 11, 2)


def _network() -> FakeNetwork:
    network = FakeNetwork()
    for n, minutes in enumerate((-1, 5, 20, 35, 50)):
        network.add_passage(
            "508", f"93_{n}", "93", 0, "Pg. Marítim", NOW + timedelta(minutes=minutes), DAY
        )
    for n, minutes in enumerate((10, 89, 90, 91)):
        network.add_passage(
            "508", f"70_{n}", "70", 1, "Alboraia", NOW + timedelta(minutes=minutes), DAY
        )
    network.add_passage("508", "70_back", "70", 0, "La Fontsanta", NOW + timedelta(minutes=30), DAY)
    network.add_passage("2070", "98_0", "98", 1, "Cid", NOW + timedelta(minutes=3), DAY)
    return network


@pytest.mark.spec("stop_arrivals_api.AC-13")
def test_at_most_two_next_passages_per_line_and_direction_in_the_window() -> None:
    network = _network()
    got = ScheduledArrivalsProvider(network).next_arrivals("508", NOW)
    assert [p.trip_id for p in got] == ["93_1", "70_0", "93_2", "70_back", "70_1"]
    assert network.scheduled_queries == [("508", NOW, timedelta(minutes=90))]


@pytest.mark.spec("stop_arrivals_api.AC-13")
def test_window_and_number_per_direction_are_configurable() -> None:
    network = _network()
    provider = ScheduledArrivalsProvider(network, window=timedelta(minutes=95), per_direction=3)
    got = provider.next_arrivals("508", NOW)
    assert [p.trip_id for p in got] == ["93_1", "70_0", "93_2", "70_back", "93_3", "70_1", "70_2"]
    assert network.scheduled_queries == [("508", NOW, timedelta(minutes=95))]


@pytest.mark.spec("stop_arrivals_api.AC-13")
def test_passages_at_the_end_of_the_window_are_included() -> None:
    network = _network()
    got = ScheduledArrivalsProvider(network, per_direction=4).next_arrivals("508", NOW)
    assert [p.trip_id for p in got if p.line == "70" and p.direction_id == 1] == [
        "70_0",
        "70_1",
        "70_2",
    ]


@pytest.mark.spec("stop_arrivals_api.AC-14")
def test_no_passages_in_the_window() -> None:
    network = _network()
    assert ScheduledArrivalsProvider(network).next_arrivals("2070", NOW + timedelta(hours=2)) == []
    assert ScheduledArrivalsProvider(network).next_arrivals("ghost", NOW) == []
