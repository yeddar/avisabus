"""CSV reader for GTFS feeds stored as a directory or a zip (gtfs_import design §4.1).

Files are read as UTF-8 accepting a BOM, row by row (streaming). Values are returned untouched;
cleaning and conversion happen in the application layer.
"""

import csv
import io
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Self

from avisabus.application.errors import GtfsDataError, GtfsValidationError
from avisabus.domain.ports.gtfs_import import GtfsRow

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "agency.txt": ("agency_name", "agency_timezone"),
    "routes.txt": ("route_id", "route_short_name", "route_type"),
    "stops.txt": ("stop_id", "stop_name", "stop_lat", "stop_lon"),
    "trips.txt": ("route_id", "service_id", "trip_id", "shape_id"),
    "stop_times.txt": ("trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"),
    "shapes.txt": ("shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"),
    "calendar.txt": (
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    ),
    "calendar_dates.txt": ("service_id", "date", "exception_type"),
    "feed_info.txt": (),
}
REQUIRED_FILES = (
    "agency.txt",
    "routes.txt",
    "stops.txt",
    "trips.txt",
    "stop_times.txt",
    "shapes.txt",
)
CALENDAR_FILES = ("calendar.txt", "calendar_dates.txt")
ENCODING = "utf-8-sig"


class CsvGtfsFeedReader:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._zip: zipfile.ZipFile | None = None
        self._files: set[str] | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None

    def validate(self) -> None:
        files = self._available_files()
        for name in REQUIRED_FILES:
            if name not in files:
                raise GtfsValidationError(name)
        if not any(name in files for name in CALENDAR_FILES):
            raise GtfsValidationError(CALENDAR_FILES[0])
        for name, required in REQUIRED_COLUMNS.items():
            if name not in files:
                continue
            columns = self.columns(name)
            for column in required:
                if column not in columns:
                    raise GtfsValidationError(name, column)

    def has_file(self, name: str) -> bool:
        return name in self._available_files()

    def columns(self, name: str) -> Sequence[str]:
        with self._open(name) as stream:
            try:
                header = next(csv.reader(stream), [])
            except UnicodeDecodeError as error:
                raise GtfsDataError(name, 1, "invalid UTF-8") from error
            except csv.Error as error:
                raise GtfsDataError(name, 1, str(error)) from error
        return tuple(column.strip() for column in header)

    def iter_rows(self, name: str) -> Iterator[GtfsRow]:
        with self._open(name) as stream:
            reader = csv.reader(stream)
            try:
                header = [column.strip() for column in next(reader, [])]
                for cells in reader:
                    if not cells:
                        continue
                    values = dict(zip(header, cells, strict=False))
                    for column in header[len(cells) :]:
                        values[column] = ""
                    yield GtfsRow(line_number=reader.line_num, values=values)
            except UnicodeDecodeError as error:
                raise GtfsDataError(name, reader.line_num + 1, "invalid UTF-8") from error
            except csv.Error as error:
                raise GtfsDataError(name, reader.line_num, str(error)) from error

    def _available_files(self) -> set[str]:
        if self._files is None:
            self._files = self._list_files()
        return self._files

    def _list_files(self) -> set[str]:
        path = self._path
        if path.is_dir():
            return {child.name for child in path.iterdir() if child.is_file()}
        if path.is_file():
            try:
                self._zip = zipfile.ZipFile(path)
            except (zipfile.BadZipFile, OSError) as error:
                raise GtfsValidationError(path.name, reason="not a valid zip file") from error
            return {name for name in self._zip.namelist() if "/" not in name}
        raise GtfsValidationError(path.name, reason="path not found")

    def _open(self, name: str) -> IO[str]:
        if name not in self._available_files():
            raise GtfsValidationError(name)
        if self._zip is not None:
            try:
                binary = self._zip.open(name)
            except (zipfile.BadZipFile, OSError) as error:
                raise GtfsValidationError(name, reason="unreadable zip member") from error
            return io.TextIOWrapper(binary, encoding=ENCODING, newline="")
        return (self._path / name).open(encoding=ENCODING, newline="")
