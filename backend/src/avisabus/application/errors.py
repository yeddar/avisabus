"""Application errors (gtfs_import design §6). Messages carry no personal identifiers."""


class GtfsImportError(Exception):
    """Base class of the errors that abort a GTFS import (CLI exit code 2)."""


class GtfsValidationError(GtfsImportError):
    """The feed cannot be read or lacks a required file or column."""

    def __init__(self, file: str, column: str | None = None, reason: str | None = None) -> None:
        self.file = file
        self.column = column
        self.reason = reason
        detail = f"{file}:{column}" if column is not None else file
        super().__init__(detail if reason is None else f"{detail}: {reason}")


class GtfsDataError(GtfsImportError):
    """A value of the feed is invalid (time, number, date...)."""

    def __init__(self, file: str, line_number: int, detail: str) -> None:
        self.file = file
        self.line_number = line_number
        self.detail = detail
        super().__init__(f"{file}:{line_number}: {detail}")
