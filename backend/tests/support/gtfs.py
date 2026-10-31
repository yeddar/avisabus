"""Helpers to build GTFS feeds for tests from the `gtfs_mini` fixture."""

import csv
import shutil
import zipfile
from pathlib import Path

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
