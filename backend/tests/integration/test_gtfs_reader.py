import zipfile
from pathlib import Path

import pytest

from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.application.errors import GtfsDataError, GtfsValidationError
from tests.support.gtfs import copy_gtfs_mini, drop_column, zip_feed


@pytest.fixture
def feed_dir(tmp_path: Path) -> Path:
    return copy_gtfs_mini(tmp_path / "feed")


def _first_rows(reader: CsvGtfsFeedReader, name: str, n: int = 2) -> list[dict[str, str]]:
    rows = []
    for row in reader.iter_rows(name):
        rows.append(dict(row.values))
        if len(rows) == n:
            break
    return rows


def test_reads_a_directory_feed(feed_dir: Path) -> None:
    with CsvGtfsFeedReader(feed_dir) as reader:
        reader.validate()
        assert reader.has_file("feed_info.txt")
        assert "direction_id" not in reader.columns("trips.txt")
        (agency,) = list(reader.iter_rows("agency.txt"))
        assert agency.values["agency_timezone"] == "Europe/Madrid"
        assert agency.line_number == 2
        assert sum(1 for _ in reader.iter_rows("stop_times.txt")) == 29040


@pytest.mark.spec("gtfs_import.AC-02")
def test_reads_a_zip_feed_like_a_directory(feed_dir: Path, tmp_path: Path) -> None:
    archive = zip_feed(feed_dir, tmp_path / "feed.zip")
    with CsvGtfsFeedReader(feed_dir) as from_dir, CsvGtfsFeedReader(archive) as from_zip:
        from_zip.validate()
        for name in ("routes.txt", "stops.txt", "trips.txt"):
            assert from_zip.columns(name) == from_dir.columns(name)
            assert _first_rows(from_zip, name) == _first_rows(from_dir, name)
        assert sum(1 for _ in from_zip.iter_rows("stop_times.txt")) == 29040


@pytest.mark.spec("gtfs_import.AC-02")
def test_zip_without_the_files_at_its_root_is_missing_them(feed_dir: Path, tmp_path: Path) -> None:
    archive = tmp_path / "nested.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in feed_dir.glob("*.txt"):
            zf.write(path, arcname=f"gtfs/{path.name}")
    with CsvGtfsFeedReader(archive) as reader, pytest.raises(GtfsValidationError) as exc:
        reader.validate()
    assert exc.value.column is None


@pytest.mark.spec("gtfs_import.AC-02")
def test_corrupt_zip_is_a_validation_error(tmp_path: Path) -> None:
    archive = tmp_path / "broken.zip"
    archive.write_bytes(b"PK\x03\x04 definitely not a zip")
    with pytest.raises(GtfsValidationError), CsvGtfsFeedReader(archive) as reader:
        reader.validate()


def test_missing_path_is_a_validation_error(tmp_path: Path) -> None:
    with pytest.raises(GtfsValidationError), CsvGtfsFeedReader(tmp_path / "nope") as reader:
        reader.validate()


@pytest.mark.spec("gtfs_import.AC-03")
@pytest.mark.parametrize(
    "missing",
    ["agency.txt", "routes.txt", "stops.txt", "trips.txt", "stop_times.txt", "shapes.txt"],
)
def test_missing_required_file_is_reported(feed_dir: Path, missing: str) -> None:
    (feed_dir / missing).unlink()
    with CsvGtfsFeedReader(feed_dir) as reader, pytest.raises(GtfsValidationError) as exc:
        reader.validate()
    assert exc.value.file == missing
    assert exc.value.column is None


@pytest.mark.spec("gtfs_import.AC-03")
def test_calendar_or_calendar_dates_is_enough(feed_dir: Path) -> None:
    (feed_dir / "calendar_dates.txt").unlink()
    with CsvGtfsFeedReader(feed_dir) as reader:
        reader.validate()
        assert not reader.has_file("calendar_dates.txt")
    (feed_dir / "calendar.txt").unlink()
    with CsvGtfsFeedReader(feed_dir) as reader, pytest.raises(GtfsValidationError) as exc:
        reader.validate()
    assert exc.value.file == "calendar.txt"


@pytest.mark.spec("gtfs_import.AC-03")
def test_feed_info_is_optional(feed_dir: Path) -> None:
    (feed_dir / "feed_info.txt").unlink()
    with CsvGtfsFeedReader(feed_dir) as reader:
        reader.validate()
        assert not reader.has_file("feed_info.txt")


@pytest.mark.spec("gtfs_import.AC-04")
@pytest.mark.parametrize(
    ("file", "column"),
    [
        ("agency.txt", "agency_timezone"),
        ("routes.txt", "route_short_name"),
        ("stops.txt", "stop_lat"),
        ("trips.txt", "shape_id"),
        ("stop_times.txt", "arrival_time"),
        ("shapes.txt", "shape_pt_sequence"),
        ("calendar.txt", "sunday"),
        ("calendar_dates.txt", "exception_type"),
    ],
)
def test_missing_required_column_is_reported(feed_dir: Path, file: str, column: str) -> None:
    drop_column(feed_dir / file, column)
    with CsvGtfsFeedReader(feed_dir) as reader, pytest.raises(GtfsValidationError) as exc:
        reader.validate()
    assert (exc.value.file, exc.value.column) == (file, column)


@pytest.mark.spec("gtfs_import.AC-04")
def test_missing_optional_column_is_accepted(feed_dir: Path) -> None:
    drop_column(feed_dir / "trips.txt", "trip_headsign")
    drop_column(feed_dir / "stop_times.txt", "shape_dist_traveled")
    with CsvGtfsFeedReader(feed_dir) as reader:
        reader.validate()


@pytest.mark.spec("gtfs_import.AC-07")
def test_reads_utf8_with_bom_and_keeps_values_untouched(tmp_path: Path) -> None:
    feed = copy_gtfs_mini(tmp_path / "feed")
    stops = feed / "stops.txt"
    stops.write_bytes(
        "﻿stop_id,stop_name,stop_lat,stop_lon\r\n"
        "2009,Tres Creus - Músic Ayllón ,39.47,-0.40\r\n"
        "1551,Tarongers (imparell)  - Metro La Cadena,39.48,-0.35\r\n".encode()
    )
    with CsvGtfsFeedReader(feed) as reader:
        reader.validate()
        assert reader.columns("stops.txt")[0] == "stop_id"
        rows = [dict(r.values) for r in reader.iter_rows("stops.txt")]
    assert rows[0]["stop_id"] == "2009"
    assert rows[0]["stop_name"] == "Tres Creus - Músic Ayllón "
    assert rows[1]["stop_name"] == "Tarongers (imparell)  - Metro La Cadena"


@pytest.mark.spec("gtfs_import.AC-07")
def test_invalid_utf8_is_a_data_error(feed_dir: Path) -> None:
    (feed_dir / "stops.txt").write_bytes(
        b"stop_id,stop_name,stop_lat,stop_lon\r\n1,Ok,39.4,-0.3\r\n2,Bad \xff,39.4,-0.3\r\n"
    )
    with CsvGtfsFeedReader(feed_dir) as reader, pytest.raises(GtfsDataError) as exc:
        reader.validate()
        list(reader.iter_rows("stops.txt"))
    assert exc.value.file == "stops.txt"


def test_short_rows_get_empty_values(feed_dir: Path) -> None:
    (feed_dir / "stops.txt").write_text(
        "stop_id,stop_name,stop_lat,stop_lon,stop_code\n1,A,39.4,-0.3\n", encoding="utf-8"
    )
    with CsvGtfsFeedReader(feed_dir) as reader:
        (row,) = list(reader.iter_rows("stops.txt"))
    assert row.values["stop_code"] == ""
    assert row.line_number == 2
