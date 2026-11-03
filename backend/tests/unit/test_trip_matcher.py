"""`match_trips`: optimal order-preserving assignment of arrivals to trips (design §3, v1.4)."""

import itertools
from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.domain.services.trip_matcher import TripCandidate, match_trips

TOLERANCE = timedelta(minutes=10)
SERVICE_DATE = date(2026, 11, 2)
T0 = datetime(2026, 11, 2, 19, 0, tzinfo=UTC)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def trip(trip_id: str, minutes: float) -> TripCandidate:
    return TripCandidate(trip_id=trip_id, service_date=SERVICE_DATE, scheduled_at=at(minutes))


def ids(result: list[TripCandidate | None]) -> list[str | None]:
    return [None if c is None else c.trip_id for c in result]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_real_case_two_buses_of_the_93_close_together_at_stop_508() -> None:
    # stop_508_peak, 2026-11-02 at 20:48:03 (Madrid): the SAE gives the 93 in 7 and 8 min
    # (20:55:03 and 20:56:03); scheduled at 508: 20:50:35 (_122), 20:59:08 (_123) and
    # 21:08:08 (_124) (progress/explore_destinations.md H-6, out_e02_series_508_93.txt).
    # The greedy matcher gave _123 (−4.1 min) and _124 (−12.1 min); the optimal assignment
    # pairs both buses with the trips around them.
    prefix = "93_994_561_488_2271_2_"
    candidates = [
        TripCandidate(f"{prefix}122", SERVICE_DATE, datetime(2026, 11, 2, 19, 50, 35, tzinfo=UTC)),
        TripCandidate(f"{prefix}123", SERVICE_DATE, datetime(2026, 11, 2, 19, 59, 8, tzinfo=UTC)),
        TripCandidate(f"{prefix}124", SERVICE_DATE, datetime(2026, 11, 2, 20, 8, 8, tzinfo=UTC)),
    ]
    arrivals = [
        datetime(2026, 11, 2, 19, 55, 3, tzinfo=UTC),
        datetime(2026, 11, 2, 19, 56, 3, tzinfo=UTC),
    ]
    assert ids(match_trips(arrivals, candidates, TOLERANCE)) == [f"{prefix}122", f"{prefix}123"]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_maximizes_the_number_of_matched_arrivals_first() -> None:
    # Pairing the second arrival with A (0.5 min) leaves the first one alone; pairing both
    # (A at +1.5, B at +8.5) matches two arrivals, which wins despite a larger total.
    candidates = [trip("A", 1.5), trip("B", 10)]
    assert ids(match_trips([at(0), at(1)], candidates, TOLERANCE)) == ["A", "B"]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_minimizes_the_total_deviation_with_the_same_number_of_matches() -> None:
    candidates = [trip("A", -6), trip("B", 1), trip("C", 9)]
    # Two arrivals, three trips: (B, C) totals 1 + 1 = 2 min, (A, B) 6 + 7 = 13 min.
    assert ids(match_trips([at(0), at(8)], candidates, TOLERANCE)) == ["B", "C"]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_each_trip_is_used_once_and_order_is_kept() -> None:
    # Both arrivals are closest to A; the later one cannot take an earlier trip than the first.
    candidates = [trip("Z", -5), trip("A", 2)]
    assert ids(match_trips([at(1), at(2)], candidates, TOLERANCE)) == ["Z", "A"]
    candidates = [trip("A", 2), trip("Y", 8)]
    assert ids(match_trips([at(1), at(2)], candidates, TOLERANCE)) == ["A", "Y"]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_scheduled_times_must_be_strictly_increasing() -> None:
    # Two trips at the very same time cannot serve two consecutive arrivals.
    candidates = [trip("A", 0), trip("B", 0)]
    assert ids(match_trips([at(0), at(1)], candidates, TOLERANCE)) == ["A", None]


@pytest.mark.spec("stop_arrivals_api.AC-10")
@pytest.mark.spec("stop_arrivals_api.AC-11")
def test_tolerance_is_inclusive() -> None:
    assert ids(match_trips([at(0)], [trip("A", 10)], TOLERANCE)) == ["A"]
    assert ids(match_trips([at(0)], [trip("A", -10)], TOLERANCE)) == ["A"]
    late = TripCandidate("A", SERVICE_DATE, at(10) + timedelta(seconds=1))
    assert ids(match_trips([at(0)], [late], TOLERANCE)) == [None]


@pytest.mark.spec("stop_arrivals_api.AC-11")
def test_arrival_without_trip_within_tolerance_is_unmatched() -> None:
    candidates = [trip("A", -11), trip("B", 0), trip("C", 30)]
    assert ids(match_trips([at(0), at(15)], candidates, TOLERANCE)) == ["B", None]
    assert match_trips([at(0)], [], TOLERANCE) == [None]
    assert match_trips([], [trip("A", 0)], TOLERANCE) == []


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_configurable_tolerance() -> None:
    assert ids(match_trips([at(0)], [trip("A", 12)], timedelta(minutes=15))) == ["A"]
    assert ids(match_trips([at(0)], [trip("A", 12)], TOLERANCE)) == [None]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_ties_are_broken_by_trip_id() -> None:
    # Same count and same total: the lexicographically smaller assignment of trip ids.
    candidates = [trip("B", -5), trip("A", 5)]
    assert ids(match_trips([at(0)], candidates, TOLERANCE)) == ["A"]
    candidates = [trip("A", -5), trip("B", 5)]
    assert ids(match_trips([at(0)], candidates, TOLERANCE)) == ["A"]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_matching_is_stable_whatever_the_input_order() -> None:
    candidates = [trip("A", -3), trip("B", 2), trip("C", 6), trip("D", 7), trip("E", 15)]
    arrivals = [at(0), at(5), at(8), at(14)]
    expected = ids(match_trips(arrivals, candidates, TOLERANCE))
    for order in itertools.permutations(candidates):
        assert ids(match_trips(arrivals, list(order), TOLERANCE)) == expected
    # The result follows the order of the given arrival times.
    reversed_result = ids(match_trips(arrivals[::-1], candidates, TOLERANCE))
    assert reversed_result == expected[::-1]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_matching_returns_the_candidates_themselves() -> None:
    candidate = trip("A", 1)
    (matched,) = match_trips([at(0)], [candidate], TOLERANCE)
    assert matched is candidate


@pytest.mark.spec("stop_arrivals_api.AC-22")
def test_duplicate_arrivals_never_share_a_trip() -> None:
    # 1057, 2026-11-03: "12 C.Art.Faller - 7 min." twice in the same answer.
    assert ids(match_trips([at(7), at(7)], [trip("A", 6)], TOLERANCE)) == ["A", None]
    candidates = [trip("A", 6), trip("B", 9)]
    assert ids(match_trips([at(7), at(7)], candidates, TOLERANCE)) == ["A", "B"]


@pytest.mark.spec("stop_arrivals_api.AC-10")
def test_matches_the_brute_force_optimum() -> None:
    """Exhaustive check on small cases: count first, then total deviation, then trip ids."""
    candidates = [trip(f"T{n}", minutes) for n, minutes in enumerate((-9, -2, 3, 4, 11, 13, 25))]
    for arrivals_min in itertools.combinations_with_replacement((-4, 0, 1, 6, 12, 20), 3):
        arrivals = [at(m) for m in arrivals_min]
        got = match_trips(arrivals, candidates, TOLERANCE)
        assert _key(arrivals, got) == min(
            _key(arrivals, option) for option in _assignments(arrivals, candidates)
        )


def _assignments(
    arrivals: list[datetime], candidates: list[TripCandidate]
) -> list[list[TripCandidate | None]]:
    options: list[list[TripCandidate | None]] = []
    for choice in itertools.product([None, *candidates], repeat=len(arrivals)):
        used = [c for c in choice if c is not None]
        if len({c.trip_id for c in used}) != len(used):
            continue
        times = [c.scheduled_at for c in used]
        if any(b <= a for a, b in itertools.pairwise(times)):
            continue
        if any(
            c is not None and abs(c.scheduled_at - t) > TOLERANCE
            for t, c in zip(arrivals, choice, strict=True)
        ):
            continue
        options.append(list(choice))
    return options


def _key(
    arrivals: list[datetime], choice: list[TripCandidate | None]
) -> tuple[int, timedelta, tuple[tuple[int, str], ...]]:
    matched = [(t, c) for t, c in zip(arrivals, choice, strict=True) if c is not None]
    total = sum((abs(c.scheduled_at - t) for t, c in matched), timedelta())
    trips = tuple((1, "") if c is None else (0, c.trip_id) for c in choice)
    return -len(matched), total, trips
