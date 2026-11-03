"""`avisabus.main` composes the stop endpoints (stop_arrivals_api T-07).

Like `test_main_composition`, `avisabus.main` is imported in a subprocess (it builds everything
at import time) with a temporary database; no socket is opened.
"""

import json
from pathlib import Path

import pytest

from tests.integration.test_main_composition import _run_main

PROBE = """
import avisabus.main as main
routes = sorted(p for p in main.app.openapi()["paths"] if p.startswith("/api/v1/stops"))
print(routes)
print(type(main.stop_use_cases.get_stop_arrivals._arrivals).__name__)
print(main.stop_use_cases.get_stop_arrivals._refresh_after_s)
print(main.stop_use_cases.get_stop_arrivals._tolerance)
print(main.stop_use_cases.get_stop_arrivals._min_score)
print(main.stop_use_cases.get_stop_arrivals._scheduled._window)
print(main.stop_use_cases.get_stop_arrivals._scheduled._per_direction)
print(main.stop_use_cases.get_stop_arrivals._occupancy is main.occupancy_sensor)
print(main.stop_use_cases.get_stop_arrivals._thresholds)
print(dict(main.stop_use_cases.direction_overrides))
"""


def test_main_wires_the_stop_endpoints_with_the_configuration(tmp_path: Path) -> None:
    result = _run_main(
        tmp_path,
        probe=PROBE,
        AVISABUS_SAE_CACHE_TTL_S="30",
        AVISABUS_TRIP_MATCH_TOLERANCE_MIN="7",
        AVISABUS_DIRECTION_MIN_SCORE="0.3",
        AVISABUS_SCHEDULED_WINDOW_MIN="60",
        AVISABUS_SCHEDULED_PER_DIRECTION="3",
        AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM="0.4",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-10:] == [
        "['/api/v1/stops/{stop_id}', '/api/v1/stops/{stop_id}/arrivals', "
        "'/api/v1/stops/{stop_id}/lines/{line}/position']",
        "CachedArrivalsSource",
        "30",
        "0:07:00",
        "0.3",
        "1:00:00",
        "3",
        "True",
        "OccupancyThresholds(medium=0.4, full=0.85)",
        "{}",
    ]


@pytest.mark.spec("stop_arrivals_api.AC-20")
def test_invalid_overrides_are_logged_without_stopping_the_start_up(tmp_path: Path) -> None:
    # The database of the subprocess has no feed: no line exists, every entry is invalid.
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({"C2|Av. Aragó": "Estadi de Mestalla (front)"}))
    result = _run_main(tmp_path, probe=PROBE, AVISABUS_DIRECTION_OVERRIDES_FILE=str(overrides))
    assert result.returncode == 0, result.stderr
    logs = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    assert [
        (log["event"], log["entry"], log["headsign"], log["reason"], log["level"])
        for log in logs
        if log.get("event") == "arrivals.override_invalid"
    ] == [
        (
            "arrivals.override_invalid",
            "C2|Av. Aragó",
            "Estadi de Mestalla (front)",
            "unknown_line",
            "warning",
        )
    ]
    assert result.stdout.splitlines()[-1] == "{}"


def test_unusable_overrides_file_stops_the_start_up(tmp_path: Path) -> None:
    result = _run_main(tmp_path, AVISABUS_DIRECTION_OVERRIDES_FILE=str(tmp_path / "missing.json"))
    assert result.returncode != 0
    assert "ConfigurationError" in result.stderr
    assert not (tmp_path / "avisabus.sqlite").exists()
