from pathlib import Path

import pytest
from pydantic import ValidationError

from avisabus.config import Settings


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("AVISABUS_GTFS_EXPIRY_WARNING_DAYS", "AVISABUS_GTFS_BATCH_SIZE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


def test_gtfs_settings_defaults() -> None:
    settings = Settings()
    assert settings.gtfs_expiry_warning_days == 7
    assert settings.gtfs_batch_size == 10_000


def test_gtfs_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVISABUS_GTFS_EXPIRY_WARNING_DAYS", "14")
    monkeypatch.setenv("AVISABUS_GTFS_BATCH_SIZE", "500")
    settings = Settings()
    assert (settings.gtfs_expiry_warning_days, settings.gtfs_batch_size) == (14, 500)


@pytest.mark.parametrize(
    ("name", "value"),
    [("AVISABUS_GTFS_EXPIRY_WARNING_DAYS", "-1"), ("AVISABUS_GTFS_BATCH_SIZE", "0")],
)
def test_gtfs_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()
