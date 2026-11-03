"""The `gtfs_mini` fixture keeps what the tests rely on (design §8)."""

import csv

import pytest

from tests.support.gtfs import FEED_FILES, GTFS_MINI

MAX_BYTES = 2_500_000


def _rows(name: str) -> list[dict[str, str]]:
    with (GTFS_MINI / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.spec("gtfs_import.AC-21")
def test_fixture_has_the_four_lines_and_key_stops_within_size() -> None:
    size = sum((GTFS_MINI / name).stat().st_size for name in FEED_FILES)
    assert size < MAX_BYTES
    routes = {r["route_id"]: r["route_short_name"] for r in _rows("routes.txt")}
    assert set(routes.values()) == {"70", "93", "98", "C2"}
    trips = {t["trip_id"]: routes[t["route_id"]] for t in _rows("trips.txt")}
    lines_at: dict[str, set[str]] = {}
    for row in _rows("stop_times.txt"):
        lines_at.setdefault(row["stop_id"], set()).add(trips[row["trip_id"]])
    assert lines_at["508"] == {"70", "93"}
    assert "98" in lines_at["2070"]
    shapes = {t["shape_id"] for t in _rows("trips.txt")}
    assert {"1054_487_2229", "1055_487_2271", "651_166_691", "996_1057_346"} <= shapes


@pytest.mark.spec("gtfs_import.AC-21")
def test_fixture_readme_documents_origin_reference_date_and_command() -> None:
    readme = (GTFS_MINI / "README.md").read_text(encoding="utf-8")
    assert "23-10-2026" in readme
    assert "2026-11-09" in readme
    assert "scripts/make_gtfs_mini.py --src ../data/gtfs/emt --lines 70,93,98,C2" in readme
