"""Import of the real EMT feed (`data/gtfs/emt/`, not versioned). Slow and manual (AC-22):

    cd backend && uv run pytest -m slow tests/integration/test_gtfs_real_feed.py -s

Skipped when the feed is not present. Time and memory are written to stdout (`-s`) and noted in
`progress/impl_gtfs_import.md`.
"""

import resource
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from typer.testing import CliRunner

from avisabus.adapters.inbound.cli import gtfs as gtfs_cli
from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.inbound.cli.main import app
from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.application.import_gtfs_feed import ImportGtfsFeed, ImportGtfsFeedCommand
from avisabus.config import Settings
from avisabus.domain.ports.clock import Clock
from tests.support.fake_clock import FakeClock

REAL_FEED = Path(__file__).resolve().parents[3] / "data" / "gtfs" / "emt"
MAX_SECONDS = 120
MAX_MEMORY_MB = 500
NOW = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not (REAL_FEED / "stop_times.txt").is_file(), reason="no real feed"),
]


def _max_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


@pytest.mark.spec("gtfs_import.AC-22")
async def test_real_feed_imports_within_time_and_memory_budget(engine: Engine) -> None:
    use_case = ImportGtfsFeed(CsvGtfsFeedReader, SqliteGtfsFeedWriter(engine), FakeClock(NOW))
    started = time.perf_counter()
    result = await use_case.execute(ImportGtfsFeedCommand(REAL_FEED))
    elapsed = time.perf_counter() - started
    peak_mb = _max_rss_mb()
    print(
        f"\nAC-22 real feed import: {elapsed:.1f} s, peak RSS of the test process {peak_mb:.0f} MB"
    )
    assert elapsed < MAX_SECONDS
    assert peak_mb < MAX_MEMORY_MB
    assert dict(result.feed.counts) == {
        "lines": 42,
        "stops": 1117,
        "trips": 20598,
        "stop_times": 508134,
        "ignored_route_ids": 3,
    }

    repo = SqliteNetworkRepository(engine)
    report = repo.direction_report()
    per_line = Counter(r.line for r in report)
    assert len(per_line) == 42
    assert set(per_line.values()) == {2}
    assert {r.source for r in report} == {"derived"}
    by_key = {(r.line, r.direction_id): r for r in report}
    # E-01: the 98 short variant and C2/C3 half loops keep their direction.
    assert dict(by_key[("98", 0)].patterns) == {"1055_487_2271": 74, "1054_487_2229": 71}
    assert {s for s, _ in by_key[("C2", 0)].patterns} == {"651_166_691", "996_1057_346"}
    assert {s for s, _ in by_key[("C3", 1)].patterns} == {"1074_1265_231", "1075_1266_229"}
    assert by_key[("59", 0)].main_shape_id == "1070_2285_2437"  # 135/135 tie
    assert sum(r.trip_count for r in report) == 20598


@pytest.mark.spec("gtfs_import.AC-26")
def test_real_feed_directions_report_through_the_cli(
    monkeypatch: pytest.MonkeyPatch, db_settings: Settings
) -> None:
    def build(_settings: Settings, _clock: Clock) -> CliContainer:
        return build_cli_container(db_settings, FakeClock(NOW))

    monkeypatch.setattr(gtfs_cli, "build_cli_container", build)
    monkeypatch.setattr(gtfs_cli, "configure_logging", lambda _level: None)
    runner = CliRunner()
    imported = runner.invoke(app, ["gtfs", "import", str(REAL_FEED)])
    assert imported.exit_code == 0, imported.output
    assert "Líneas: 42 · Paradas: 1 117 · Viajes: 20 598 · Horarios de parada: 508 134" in (
        imported.output
    )
    assert "route_id sin viajes ignorados: 3" in imported.output
    result = runner.invoke(app, ["gtfs", "info", "--directions"])
    assert result.exit_code == 0
    assert result.output.count("· origen: derived ·") == 84
    print("\n" + result.output)
