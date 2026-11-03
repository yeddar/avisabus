"""`GET /api/v1/shapes/{shape_id}` over `gtfs_mini` (position_estimation T-05, T-06).

Expected coordinates and stops are read from the fixture CSV files, independently of the
repository (names and coordinates of the stops come from `get_stop`, tested in `gtfs_import`).
"""

import csv
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.application.import_gtfs_feed import ImportGtfsFeed, ImportGtfsFeedCommand
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.position import position_client
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, replay

PROBLEM_JSON = "application/problem+json"
PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
SHAPE_93 = "994_488_2271"


def _csv(name: str) -> list[dict[str, str]]:
    with (GTFS_MINI / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def mini_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    engine = new_engine(tmp_path_factory.mktemp("shapes") / "avisabus.sqlite")
    import_feed(engine, GTFS_MINI)
    yield engine
    engine.dispose()


def _clock() -> FakeClock:
    return FakeClock(PEAK_START)


def _expected_coordinates(shape_id: str) -> list[list[float]]:
    rows = sorted(
        (int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"]))
        for r in _csv("shapes.txt")
        if r["shape_id"] == shape_id
    )
    return [[lon, lat] for _, lon, lat in rows]


def _expected_stop_calls(shape_id: str) -> list[tuple[int, str]]:
    """(sequence, stop_id) of the most frequent stop pattern of the shape's trips."""
    trips = {r["trip_id"] for r in _csv("trips.txt") if r["shape_id"] == shape_id}
    calls: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in _csv("stop_times.txt"):
        if row["trip_id"] in trips:
            calls[row["trip_id"]].append((int(row["stop_sequence"]), row["stop_id"]))
    patterns = Counter(tuple(stop for _, stop in sorted(c)) for c in calls.values())
    pattern, _ = patterns.most_common(1)[0]
    trip_id = min(t for t, c in calls.items() if tuple(s for _, s in sorted(c)) == pattern)
    return sorted(calls[trip_id])


@pytest.mark.spec("position_estimation.AC-13")
@pytest.mark.parametrize("shape_id", [SHAPE_93, "1055_487_2271", "651_166_691"])
async def test_shape_with_its_coordinates_color_and_stops(
    mini_engine: Engine, shape_id: str
) -> None:
    clock = _clock()
    source, _ = replay(STOP_508_PEAK, clock)
    repo = SqliteNetworkRepository(mini_engine)
    async with position_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/shapes/{shape_id}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"shape_id", "line", "color", "coordinates", "stops"}
    line = {"994": "93", "105": "98", "651": "C2"}[shape_id[:3]]
    assert (body["shape_id"], body["line"], body["color"]) == (shape_id, line, "FE0000")
    assert body["coordinates"] == _expected_coordinates(shape_id)  # GeoJSON order: [lon, lat]
    expected_stops = []
    for sequence, stop_id in _expected_stop_calls(shape_id):
        stop = repo.get_stop(stop_id)
        assert stop is not None
        expected_stops.append(
            {
                "stop_id": stop_id,
                "name": stop.name,
                "lat": stop.lat,
                "lon": stop.lon,
                "sequence": sequence,
            }
        )
    assert body["stops"] == expected_stops


@pytest.mark.spec("position_estimation.AC-14")
async def test_shape_is_cacheable_with_an_etag_of_the_feed_version(mini_engine: Engine) -> None:
    clock = _clock()
    source, _ = replay(STOP_508_PEAK, clock)
    repo = SqliteNetworkRepository(mini_engine)
    feed = repo.active_feed()
    assert feed is not None
    etag = f'"{feed.version_id}-{SHAPE_93}"'
    async with position_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/shapes/{SHAPE_93}")
        not_modified = await client.get(f"{API}/shapes/{SHAPE_93}", headers={"If-None-Match": etag})
        weak_or_listed = await client.get(
            f"{API}/shapes/{SHAPE_93}", headers={"If-None-Match": f'"x", W/{etag}'}
        )
        other = await client.get(f"{API}/shapes/{SHAPE_93}", headers={"If-None-Match": '"1-x"'})
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.headers["etag"] == etag
    assert not_modified.status_code == 304
    assert not_modified.content == b""
    assert not_modified.headers["etag"] == etag
    assert not_modified.headers["cache-control"] == "public, max-age=86400"
    assert weak_or_listed.status_code == 304
    assert other.status_code == 200
    assert other.json() == response.json()


@pytest.mark.spec("position_estimation.AC-14")
async def test_etag_changes_with_the_feed_version(tmp_path: Path) -> None:
    engine = new_engine(tmp_path / "avisabus.sqlite")
    await _import(engine)
    clock = _clock()
    source, _ = replay(STOP_508_PEAK, clock)
    async with position_client(engine, clock, source) as (client, _):
        first = await client.get(f"{API}/shapes/{SHAPE_93}")
        await _import(engine)  # reimport: new active version
        second = await client.get(
            f"{API}/shapes/{SHAPE_93}", headers={"If-None-Match": first.headers["etag"]}
        )
    engine.dispose()
    assert first.headers["etag"] != second.headers["etag"]
    assert second.status_code == 200
    assert second.json() == first.json()


async def _import(engine: Engine) -> None:
    use_case = ImportGtfsFeed(CsvGtfsFeedReader, SqliteGtfsFeedWriter(engine), _clock())
    await use_case.execute(ImportGtfsFeedCommand(GTFS_MINI))


@pytest.mark.spec("position_estimation.AC-15")
@pytest.mark.parametrize("shape_id", ["ghost", "994_488_2271x"])
async def test_unknown_shape_is_404(mini_engine: Engine, shape_id: str) -> None:
    clock = _clock()
    source, counting = replay(STOP_508_PEAK, clock)
    async with position_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/shapes/{shape_id}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    assert response.json() == {
        "type": "https://avisabus/problems/shape-not-found",
        "title": "Not Found",
        "status": 404,
    }
    assert counting.calls == 0


async def test_shape_without_an_active_feed_is_503(tmp_path: Path) -> None:
    engine = new_engine(tmp_path / "empty.sqlite")
    clock = _clock()
    source, _ = replay(STOP_508_PEAK, clock)
    async with position_client(engine, clock, source) as (client, _):
        response = await client.get(f"{API}/shapes/{SHAPE_93}")
    engine.dispose()
    assert response.status_code == 503
    assert response.json()["type"] == "https://avisabus/problems/network-unavailable"
    assert response.headers["cache-control"] == "no-store"
