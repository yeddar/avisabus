"""Helpers to build GTFS feeds for tests from the `gtfs_mini` fixture."""

import csv
import shutil
import zipfile
from pathlib import Path

from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.application import gtfs_rows
from avisabus.domain.ports.gtfs_import import GtfsFeedWriter, GtfsRecord

GTFS_MINI = Path(__file__).resolve().parents[1] / "fixtures" / "gtfs_mini"
FEED_FILES = (
    "agency.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "feed_info.txt",
    "routes.txt",
    "shapes.txt",
    "stop_times.txt",
    "stops.txt",
    "trips.txt",
)


def copy_gtfs_mini(dst: Path) -> Path:
    """Copy the feed files of `gtfs_mini` (without the README) into `dst`."""
    dst.mkdir(parents=True, exist_ok=True)
    for name in FEED_FILES:
        shutil.copyfile(GTFS_MINI / name, dst / name)
    return dst


def zip_feed(src: Path, dst: Path) -> Path:
    """Zip the `.txt` files of `src` at the root of the archive `dst`."""
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(src.glob("*.txt")):
            archive.write(path, arcname=path.name)
    return dst


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def write_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh, lineterminator="\r\n").writerows(rows)


def drop_column(path: Path, column: str) -> None:
    rows = read_rows(path)
    index = rows[0].index(column)
    write_rows(path, [[c for i, c in enumerate(row) if i != index] for row in rows])


def add_column(path: Path, column: str, value_for: dict[str, str], key: str) -> None:
    """Append `column`; each row gets `value_for[row[key]]`."""
    rows = read_rows(path)
    key_index = rows[0].index(key)
    out = [[*rows[0], column]]
    out += [[*row, value_for[row[key_index]]] for row in rows[1:]]
    write_rows(path, out)


def append_rows(path: Path, rows: list[list[str]]) -> None:
    write_rows(path, read_rows(path) + rows)


FILE_ORDER = (
    "routes.txt",
    "stops.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "shapes.txt",
    "trips.txt",
    "stop_times.txt",
)


class InjectedFailureError(RuntimeError):
    """Failure injected by tests in the middle of a file."""


def load_feed(
    writer: GtfsFeedWriter,
    feed_dir: Path,
    fail_in: str | None = None,
    batch_size: int = 1000,
    derive: bool = True,
) -> int:
    """Load `feed_dir` into a new inactive version (no activation). Returns the version id.

    With `fail_in`, raises `InjectedFailureError` after the first batch of that file, leaving the
    version partially written (the caller decides whether to discard it).
    """
    version_id = writer.begin_version()
    with CsvGtfsFeedReader(feed_dir) as reader:
        reader.validate()
        has_direction = "direction_id" in reader.columns("trips.txt")
        parsers = {
            "routes.txt": gtfs_rows.route_record,
            "stops.txt": gtfs_rows.stop_record,
            "calendar.txt": gtfs_rows.calendar_record,
            "calendar_dates.txt": gtfs_rows.calendar_date_record,
            "shapes.txt": gtfs_rows.shape_point_record,
            "trips.txt": lambda row: gtfs_rows.trip_record(row, has_direction),
            "stop_times.txt": gtfs_rows.stop_time_record,
        }
        for name in FILE_ORDER:
            if not reader.has_file(name):
                continue
            batch: list[GtfsRecord] = []
            for row in reader.iter_rows(name):
                batch.append(parsers[name](row))
                if len(batch) == batch_size:
                    writer.insert_batch(version_id, batch)
                    batch = []
                    if name == fail_in:
                        raise InjectedFailureError(name)
            if batch:
                writer.insert_batch(version_id, batch)
        if derive:
            writer.build_derived(version_id, directions_from_feed=has_direction)
    return version_id
