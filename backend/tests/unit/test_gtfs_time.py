import pytest

from avisabus.domain.services.gtfs_time import (
    InvalidGtfsTimeError,
    format_gtfs_time,
    parse_gtfs_time,
)


@pytest.mark.spec("gtfs_import.AC-08")
@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("00:00:00", 0),
        ("05:50:18", 21018),
        ("23:59:59", 86399),
        ("24:00:00", 86400),
        ("25:10:00", 90600),
        ("28:00:01", 100801),
        ("5:50:00", 21000),
        (" 07:05:00 ", 25500),
    ],
)
def test_parses_times_as_seconds_since_service_day_start(value: str, seconds: int) -> None:
    assert parse_gtfs_time(value) == seconds


@pytest.mark.spec("gtfs_import.AC-08")
@pytest.mark.parametrize(
    "value", ["", "25:10", "aa:bb:cc", "10:60:00", "10:00:60", "-1:00:00", "10:00:00:00"]
)
def test_rejects_malformed_times(value: str) -> None:
    with pytest.raises(InvalidGtfsTimeError):
        parse_gtfs_time(value)


@pytest.mark.spec("gtfs_import.AC-08")
@pytest.mark.parametrize(
    ("seconds", "text"), [(0, "00:00:00"), (21018, "05:50:18"), (90600, "25:10:00")]
)
def test_formats_seconds_back_to_gtfs_time(seconds: int, text: str) -> None:
    assert format_gtfs_time(seconds) == text
    assert parse_gtfs_time(format_gtfs_time(seconds)) == seconds
