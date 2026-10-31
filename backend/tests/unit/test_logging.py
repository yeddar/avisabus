import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from avisabus.logging import configure_logging

REQUIRED_KEYS = {"timestamp", "level", "event", "logger"}


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


def _lines(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.strip()]


@pytest.mark.spec("project_scaffold.AC-12")
def test_structlog_events_are_emitted_as_one_json_line_each(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    log = structlog.get_logger("avisabus.tests")
    log.info("first_event", answer=42)
    log.warning("second_event")

    records = _lines(capsys.readouterr().out)
    assert len(records) == 2
    first, second = records
    assert first.keys() >= REQUIRED_KEYS
    assert first["event"] == "first_event"
    assert first["level"] == "info"
    assert first["logger"] == "avisabus.tests"
    assert first["answer"] == 42
    assert second["event"] == "second_event"
    assert second["level"] == "warning"


@pytest.mark.spec("project_scaffold.AC-12")
def test_timestamp_is_iso_8601_in_utc(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger("avisabus.tests").info("tick")
    (record,) = _lines(capsys.readouterr().out)
    assert record["timestamp"].endswith("Z")
    assert "T" in record["timestamp"]


@pytest.mark.spec("project_scaffold.AC-12")
def test_standard_library_logs_use_the_same_json_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    logging.getLogger("uvicorn.error").warning("server %s", "started")
    (record,) = _lines(capsys.readouterr().out)
    assert record.keys() >= REQUIRED_KEYS
    assert record["event"] == "server started"
    assert record["level"] == "warning"
    assert record["logger"] == "uvicorn.error"


@pytest.mark.spec("project_scaffold.AC-12")
def test_events_below_the_configured_level_are_dropped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("WARNING")
    structlog.get_logger("avisabus.tests").info("too_verbose")
    logging.getLogger("uvicorn.error").info("too_verbose_too")
    structlog.get_logger("avisabus.tests").error("kept")
    records = _lines(capsys.readouterr().out)
    assert [r["event"] for r in records] == ["kept"]


@pytest.mark.spec("project_scaffold.AC-12")
def test_exceptions_are_rendered_inside_the_json_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        structlog.get_logger("avisabus.tests").exception("failed")
    (record,) = _lines(capsys.readouterr().out)
    assert record["event"] == "failed"
    assert "RuntimeError" in record["exception"]
