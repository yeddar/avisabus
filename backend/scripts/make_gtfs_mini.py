"""Generate the `gtfs_mini` test fixture from the real EMT feed (gtfs_import design §8).

Usage (from `backend/`):

    uv run python scripts/make_gtfs_mini.py --src ../data/gtfs/emt --lines 70,93,98,C2 \
        --date 2026-11-09 --out tests/fixtures/gtfs_mini

Keeps `agency` and `feed_info`, the routes of the given lines, their trips whose service is
active on `--date` or the day before, the `stop_times` of those trips, the referenced stops and
shapes and the `calendar` / `calendar_dates` rows of those services. Rows are copied verbatim
(same bytes, same line endings) so the fixture keeps the quirks of the real feed.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

from avisabus.domain.models.network import CalendarException, ServiceCalendar
from avisabus.domain.services.service_calendar import active_services

REQUIRED_STOPS = ("508", "2070")
WEEKDAY_COLUMNS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

Row = dict[str, str]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()  # noqa: DTZ007 - calendar date, no time


def _rows(path: Path) -> Iterator[tuple[str, Row]]:
    """Yield `(raw_line, row)` keeping the original line (including its line ending)."""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        names = next(csv.reader([fh.readline()]))
        for raw in fh:
            values = next(csv.reader([raw]))
            yield raw, dict(zip(names, values, strict=True))


def _copy(src: Path, dst: Path, keep: Callable[[Row], bool]) -> int:
    kept = 0
    with src.open(encoding="utf-8-sig", newline="") as fh:
        header = fh.readline()
    with dst.open("w", encoding="utf-8", newline="") as out:
        out.write(header)
        for raw, row in _rows(src):
            if keep(row):
                out.write(raw)
                kept += 1
    return kept


def build(src: Path, out: Path, lines: set[str], ref_date: date) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    calendars = [
        ServiceCalendar(
            row["service_id"],
            tuple(row[c] == "1" for c in WEEKDAY_COLUMNS),  # type: ignore[arg-type]
            _parse_date(row["start_date"]),
            _parse_date(row["end_date"]),
        )
        for _, row in _rows(src / "calendar.txt")
    ]
    exceptions = [
        CalendarException(row["service_id"], _parse_date(row["date"]), int(row["exception_type"]))
        for _, row in _rows(src / "calendar_dates.txt")
    ]
    services = active_services(ref_date, calendars, exceptions) | active_services(
        ref_date - timedelta(days=1), calendars, exceptions
    )

    route_ids = {
        r["route_id"] for _, r in _rows(src / "routes.txt") if r["route_short_name"] in lines
    }
    trip_ids: set[str] = set()
    shape_ids: set[str] = set()
    used_services: set[str] = set()
    for _, trip in _rows(src / "trips.txt"):
        if trip["route_id"] in route_ids and trip["service_id"] in services:
            trip_ids.add(trip["trip_id"])
            shape_ids.add(trip["shape_id"])
            used_services.add(trip["service_id"])
    stop_ids = {
        st["stop_id"] for _, st in _rows(src / "stop_times.txt") if st["trip_id"] in trip_ids
    }
    missing = [stop for stop in REQUIRED_STOPS if stop not in stop_ids]
    if missing:
        raise SystemExit(f"the selected lines do not serve stops {missing}")

    counts = {
        "agency.txt": _copy(src / "agency.txt", out / "agency.txt", lambda _: True),
        "feed_info.txt": _copy(src / "feed_info.txt", out / "feed_info.txt", lambda _: True),
        "routes.txt": _copy(
            src / "routes.txt", out / "routes.txt", lambda r: r["route_id"] in route_ids
        ),
        "trips.txt": _copy(
            src / "trips.txt", out / "trips.txt", lambda r: r["trip_id"] in trip_ids
        ),
        "stop_times.txt": _copy(
            src / "stop_times.txt", out / "stop_times.txt", lambda r: r["trip_id"] in trip_ids
        ),
        "stops.txt": _copy(
            src / "stops.txt", out / "stops.txt", lambda r: r["stop_id"] in stop_ids
        ),
        "shapes.txt": _copy(
            src / "shapes.txt", out / "shapes.txt", lambda r: r["shape_id"] in shape_ids
        ),
        "calendar.txt": _copy(
            src / "calendar.txt", out / "calendar.txt", lambda r: r["service_id"] in used_services
        ),
        "calendar_dates.txt": _copy(
            src / "calendar_dates.txt",
            out / "calendar_dates.txt",
            lambda r: r["service_id"] in used_services,
        ),
    }
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", type=Path, required=True, help="real GTFS feed directory")
    parser.add_argument("--lines", required=True, help="comma-separated route_short_name list")
    parser.add_argument("--date", required=True, help="reference service date (YYYY-MM-DD)")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    args = parser.parse_args(argv)
    ref_date = date.fromisoformat(args.date)
    counts = build(args.src, args.out, set(args.lines.split(",")), ref_date)
    for name, count in counts.items():
        print(f"{name}: {count} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
