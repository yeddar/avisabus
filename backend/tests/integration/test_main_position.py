"""`avisabus.main` composes the position and shape endpoints (position_estimation T-06).

Same approach as `test_main_stops`: `avisabus.main` is imported in a subprocess with a temporary
database; no socket is opened.
"""

from pathlib import Path

import pytest

from tests.integration.test_main_composition import _run_main

PROBE = """
import avisabus.main as main
from starlette.middleware.gzip import GZipMiddleware
paths = main.app.openapi()["paths"]
print(sorted(
    p for p in paths
    if (p.endswith("/position") and not p.startswith("/api/v1/driver/"))
    or p.startswith("/api/v1/shapes")
))
position = main.position_use_cases.get_vehicle_position
print(position._stop_arrivals is main.stop_use_cases.get_stop_arrivals)
print(position._clock is main.clock)
print(type(main.position_use_cases.get_shape._network).__name__)
print([m.kwargs for m in main.app.user_middleware if m.cls is GZipMiddleware])
"""


@pytest.mark.spec("position_estimation.AC-09")
@pytest.mark.spec("position_estimation.AC-16")
def test_main_wires_the_position_and_shape_endpoints(tmp_path: Path) -> None:
    result = _run_main(tmp_path, probe=PROBE)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-5:] == [
        "['/api/v1/shapes/{shape_id}', '/api/v1/stops/{stop_id}/lines/{line}/position']",
        "True",
        "True",
        "SqliteNetworkRepository",
        "[{'minimum_size': 1000}]",
    ]
