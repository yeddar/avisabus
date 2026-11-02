"""`avisabus.main` composes the arrivals source and runs `sae.stats` with the app (T-09).

Like `test_main_composition`, `avisabus.main` is imported in a subprocess (it builds everything
at import time) with a temporary database; no socket is opened.
"""

from pathlib import Path

import pytest

from tests.integration.test_main_composition import _run_main

LIFESPAN_PROBE = """
import asyncio
import avisabus.main as main

async def probe():
    print(type(main.arrivals_source).__name__)
    async with main.app.router.lifespan_context(main.app):
        names = {task.get_name() for task in asyncio.all_tasks()}
        print("sae.stats running:", "sae.stats" in names)
        snapshot = await main.arrivals_source.get_arrivals("508")
        print("arrivals:", [a.minutes for a in snapshot.arrivals])
    names = {task.get_name() for task in asyncio.all_tasks()}
    print("sae.stats running:", "sae.stats" in names)
    print("http client closed:", main.http_client.is_closed)

asyncio.run(probe())
"""


@pytest.mark.spec("sae_arrivals_source.AC-13")
@pytest.mark.spec("sae_arrivals_source.AC-20")
def test_app_lifespan_runs_the_stats_task_over_the_replayed_source(tmp_path: Path) -> None:
    result = _run_main(tmp_path, probe=LIFESPAN_PROBE)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "CachedArrivalsSource",
        "sae.stats running: True",
        "arrivals: [7, 9, 14, 21]",
        "sae.stats running: False",
        "http client closed: True",
    ]


@pytest.mark.spec("sae_arrivals_source.AC-20")
@pytest.mark.spec("sae_arrivals_source.AC-22")
def test_application_refuses_to_start_without_a_usable_replay_session(tmp_path: Path) -> None:
    result = _run_main(tmp_path, AVISABUS_SAE_REPLAY_DIR=str(tmp_path / "missing"))
    assert result.returncode != 0
    assert "ConfigurationError" in result.stderr
    assert not (tmp_path / "avisabus.sqlite").exists()
