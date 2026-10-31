from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

import pytest

from avisabus.application.errors import GtfsDataError, GtfsValidationError
from avisabus.application.import_gtfs_feed import ImportGtfsFeed, ImportGtfsFeedCommand
from avisabus.domain.models.network import CalendarException, FeedVersion, ServiceCalendar
from avisabus.domain.ports.gtfs_import import (
    DerivedSummary,
    GtfsRecord,
    GtfsRow,
    RouteRecord,
    StopTimeRecord,
    TripRecord,
)
from avisabus.domain.services.feed_validity import Expired, Expiring, Valid
from tests.support.fake_clock import FakeClock

NOW = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)

STOP_TIMES = [
    {
        "trip_id": f"t{trip}",
        "arrival_time": f"0{6 + seq}:00:00",
        "departure_time": f"0{6 + seq}:00:00",
        "stop_id": f"s{seq}",
        "stop_sequence": str(seq),
    }
    for trip in (1, 2, 3)
    for seq in (1, 2, 3)
]


def _feed() -> dict[str, list[dict[str, str]]]:
    return {
        "agency.txt": [{"agency_name": "EMT", "agency_timezone": "Europe/Madrid"}],
        "feed_info.txt": [
            {"feed_version": "v1", "feed_start_date": "20261016", "feed_end_date": "20261122"}
        ],
        "routes.txt": [
            {"route_id": "r1", "route_short_name": "70", "route_type": "3"},
            {"route_id": "r2", "route_short_name": "23", "route_type": "3"},
        ],
        "stops.txt": [
            {"stop_id": f"s{n}", "stop_name": f"Stop {n} ", "stop_lat": "39.4", "stop_lon": "-0.3"}
            for n in (1, 2, 3)
        ],
        "calendar.txt": [
            {
                "service_id": "wk",
                **dict.fromkeys(("monday", "tuesday", "wednesday", "thursday", "friday"), "1"),
                **dict.fromkeys(("saturday", "sunday"), "0"),
                "start_date": "20261016",
                "end_date": "20261122",
            }
        ],
        "calendar_dates.txt": [{"service_id": "wk", "date": "20261101", "exception_type": "2"}],
        "shapes.txt": [
            {
                "shape_id": "sh",
                "shape_pt_lat": "39.4",
                "shape_pt_lon": "-0.3",
                "shape_pt_sequence": "1",
            }
        ],
        "trips.txt": [
            {"route_id": "r1", "service_id": "wk", "trip_id": f"t{n}", "shape_id": "sh"}
            for n in (1, 2, 3)
        ],
        "stop_times.txt": [dict(row) for row in STOP_TIMES],
    }


class FakeReader:
    def __init__(
        self,
        files: dict[str, list[dict[str, str]]],
        fail_at: tuple[str, int] | None = None,
        invalid: GtfsValidationError | None = None,
    ) -> None:
        self.files = files
        self.fail_at = fail_at
        self.invalid = invalid
        self.closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def validate(self) -> None:
        if self.invalid is not None:
            raise self.invalid

    def has_file(self, name: str) -> bool:
        return name in self.files

    def columns(self, name: str) -> Sequence[str]:
        rows = self.files[name]
        return tuple(rows[0]) if rows else ()

    def iter_rows(self, name: str) -> Iterator[GtfsRow]:
        for index, values in enumerate(self.files[name]):
            if self.fail_at == (name, index):
                raise OSError("disk unplugged")
            yield GtfsRow(line_number=index + 2, values=values)


class FakeWriter:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.batches: list[tuple[type, int]] = []
        self.records: list[GtfsRecord] = []
        self.activated: tuple[FeedVersion, str] | None = None
        self.directions_from_feed: bool | None = None

    def begin_version(self) -> int:
        self.calls.append("begin")
        return 7

    def insert_batch(self, version_id: int, records: Sequence[GtfsRecord]) -> None:
        assert version_id == 7
        assert len({type(r) for r in records}) == 1
        self.batches.append((type(records[0]), len(records)))
        self.records.extend(records)

    def build_derived(self, version_id: int, directions_from_feed: bool) -> DerivedSummary:
        self.calls.append("derived")
        self.directions_from_feed = directions_from_feed
        return DerivedSummary(lines=1, ignored_route_ids=1)

    def activate(self, feed: FeedVersion, timezone: str) -> None:
        self.calls.append("activate")
        self.activated = (feed, timezone)

    def purge_inactive(self) -> None:
        self.calls.append("purge")

    def discard(self, version_id: int) -> None:
        self.calls.append(f"discard {version_id}")


def _use_case(
    reader: FakeReader, writer: FakeWriter, now: datetime = NOW, batch_size: int = 4
) -> ImportGtfsFeed:
    def open_reader(path: Path) -> FakeReader:
        assert path == Path("feed")
        return reader

    return ImportGtfsFeed(
        open_reader=open_reader,
        writer=writer,
        clock=FakeClock(now),
        batch_size=batch_size,
        warning_days=7,
    )


async def _run(reader: FakeReader, writer: FakeWriter, **kwargs: object):  # type: ignore[no-untyped-def]
    return await _use_case(reader, writer, **kwargs).execute(  # type: ignore[arg-type]
        ImportGtfsFeedCommand(path=Path("feed"))
    )


@pytest.mark.spec("gtfs_import.AC-01")
async def test_imports_every_file_in_order_then_activates_and_purges() -> None:
    reader, writer = FakeReader(_feed()), FakeWriter()
    result = await _run(reader, writer)
    assert writer.calls == ["begin", "derived", "activate", "purge"]
    order = [kind.__name__ for kind, _ in writer.batches]
    assert order == [
        "RouteRecord",
        "StopRecord",
        "ServiceCalendar",
        "CalendarException",
        "ShapePointRecord",
        "TripRecord",
        "StopTimeRecord",
        "StopTimeRecord",
        "StopTimeRecord",
    ]
    assert [n for kind, n in writer.batches if kind is StopTimeRecord] == [4, 4, 1]
    assert writer.activated is not None
    feed, timezone = writer.activated
    assert timezone == "Europe/Madrid"
    assert feed == FeedVersion(
        version_id=7,
        feed_version="v1",
        imported_at=NOW,
        start_date=date(2026, 10, 16),
        end_date=date(2026, 11, 22),
        counts={"lines": 1, "stops": 3, "trips": 3, "stop_times": 9, "ignored_route_ids": 1},
    )
    assert result.feed == feed
    assert result.ignored_route_ids == 1
    assert result.validity == Valid()
    assert reader.closed
    assert writer.directions_from_feed is False


@pytest.mark.spec("gtfs_import.AC-01")
async def test_records_are_converted_and_cleaned() -> None:
    writer = FakeWriter()
    await _run(FakeReader(_feed()), writer)
    stops = [r for r in writer.records if type(r).__name__ == "StopRecord"]
    assert [s.name for s in stops] == ["Stop 1", "Stop 2", "Stop 3"]  # type: ignore[union-attr]
    assert RouteRecord("r1", "70", "", "FE0000", "FFFFFF") in writer.records
    assert TripRecord("t1", "r1", "wk", None, "sh", None) in writer.records
    assert StopTimeRecord("t1", 2, "s2", 28800, 28800, None) in writer.records
    assert CalendarException("wk", date(2026, 11, 1), 2) in writer.records
    assert any(isinstance(r, ServiceCalendar) for r in writer.records)


@pytest.mark.spec("gtfs_import.AC-05")
async def test_failure_while_reading_stop_times_discards_the_new_version() -> None:
    writer = FakeWriter()
    with pytest.raises(OSError, match="disk unplugged"):
        await _run(FakeReader(_feed(), fail_at=("stop_times.txt", 6)), writer)
    assert writer.calls == ["begin", "discard 7"]
    assert writer.activated is None


@pytest.mark.spec("gtfs_import.AC-05")
async def test_invalid_value_discards_the_new_version() -> None:
    feed = _feed()
    feed["stop_times.txt"][5]["arrival_time"] = "soon"
    writer = FakeWriter()
    with pytest.raises(GtfsDataError) as exc:
        await _run(FakeReader(feed), writer)
    assert (exc.value.file, exc.value.line_number) == ("stop_times.txt", 7)
    assert writer.calls == ["begin", "discard 7"]


@pytest.mark.spec("gtfs_import.AC-05")
async def test_trip_with_unknown_route_is_a_data_error() -> None:
    feed = _feed()
    feed["trips.txt"][1]["route_id"] = "ghost"
    writer = FakeWriter()
    with pytest.raises(GtfsDataError) as exc:
        await _run(FakeReader(feed), writer)
    assert (exc.value.file, exc.value.line_number) == ("trips.txt", 3)
    assert writer.calls == ["begin", "discard 7"]


@pytest.mark.spec("gtfs_import.AC-03")
async def test_invalid_feed_is_rejected_before_writing_anything() -> None:
    writer = FakeWriter()
    reader = FakeReader(_feed(), invalid=GtfsValidationError("stops.txt"))
    with pytest.raises(GtfsValidationError):
        await _run(reader, writer)
    assert writer.calls == []
    assert writer.batches == []


@pytest.mark.spec("gtfs_import.AC-20")
async def test_validity_comes_from_calendars_without_feed_info() -> None:
    feed = _feed()
    del feed["feed_info.txt"]
    feed["calendar_dates.txt"].append(
        {"service_id": "x", "date": "20261130", "exception_type": "1"}
    )
    writer = FakeWriter()
    result = await _run(FakeReader(feed), writer)
    assert (result.feed.start_date, result.feed.end_date) == (
        date(2026, 10, 16),
        date(2026, 11, 30),
    )
    assert result.feed.feed_version is None


@pytest.mark.spec("gtfs_import.AC-20")
async def test_feed_without_any_date_is_a_data_error() -> None:
    feed = _feed()
    del feed["feed_info.txt"]
    feed["calendar.txt"] = []
    feed["calendar_dates.txt"] = []
    writer = FakeWriter()
    with pytest.raises(GtfsDataError):
        await _run(FakeReader(feed), writer)
    assert writer.calls[-1] == "discard 7"


@pytest.mark.spec("gtfs_import.AC-19")
async def test_validity_status_uses_the_clock_in_the_feed_timezone() -> None:
    # 2026-11-14 23:30 UTC is already 2026-11-15 in Madrid: 7 days left.
    result = await _run(
        FakeReader(_feed()), FakeWriter(), now=datetime(2026, 11, 14, 23, 30, tzinfo=UTC)
    )
    assert result.validity == Expiring(days_left=7)
    result = await _run(
        FakeReader(_feed()), FakeWriter(), now=datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    )
    assert result.validity == Expired(days_ago=2)


@pytest.mark.spec("gtfs_import.AC-23")
async def test_direction_column_makes_the_feed_directions_authoritative() -> None:
    feed = _feed()
    for trip in feed["trips.txt"]:
        trip["direction_id"] = "1"
    writer = FakeWriter()
    await _run(FakeReader(feed), writer)
    assert writer.directions_from_feed is True
    trips = [r for r in writer.records if isinstance(r, TripRecord)]
    assert {t.direction_id for t in trips} == {1}


async def test_empty_agency_is_a_data_error() -> None:
    feed = _feed()
    feed["agency.txt"] = []
    with pytest.raises(GtfsDataError):
        await _run(FakeReader(feed), FakeWriter())
