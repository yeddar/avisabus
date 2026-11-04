"""Alert expiry over `gtfs_mini`, the replayed SAE behind the production cache, SQLite and
`/ws/passenger` (alert_expiry T-03, T-04).

The cycles are run by calling `tick()` with a `FakeClock`: no time passes for real.
"""

from pathlib import Path

import pytest

from tests.integration.test_main_composition import _run_main

LIFESPAN_PROBE = """
import asyncio
import avisabus.main as main

expiry = main.alert_expiry
watch, ticker = expiry.watch_passages, expiry.expire_due_alerts
print("intervals:", expiry.watch_interval.total_seconds(), expiry.expiry_interval.total_seconds())
print("window:", watch._window.total_seconds(), "margin:", ticker._margin.total_seconds())
print("same arrivals:", watch._stop_arrivals is main.stop_use_cases.get_stop_arrivals)
print("same publisher:", watch._expire._events is main.realtime.publisher)
print("shared expiry:", watch._expire is ticker._expire)
print("seen from the watcher:", ticker._seen == watch.seen_in_last_observation)
print("notifier:", type(watch._expire._drivers).__name__)

def running():
    return sorted(t.get_name() for t in asyncio.all_tasks() if t.get_name().startswith("alerts."))

async def probe():
    async with main.app.router.lifespan_context(main.app):
        await asyncio.sleep(0)
        print("running:", running())
    print("running:", running())

asyncio.run(probe())
"""


@pytest.mark.spec("alert_expiry.AC-10")
def test_the_application_starts_and_stops_both_tasks(tmp_path: Path) -> None:
    result = _run_main(
        tmp_path,
        probe=LIFESPAN_PROBE,
        AVISABUS_PASSAGE_WATCH_INTERVAL_S="20",
        AVISABUS_PASSAGE_WINDOW_MIN="3",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "intervals: 20.0 10.0",
        "window: 180.0 margin: 120.0",
        "same arrivals: True",
        "same publisher: True",
        "shared expiry: True",
        "seen from the watcher: True",
        "notifier: NoopDriverViewNotifier",
        "running: ['alerts.expiry_ticker', 'alerts.passage_watcher']",
        "running: []",
    ]
