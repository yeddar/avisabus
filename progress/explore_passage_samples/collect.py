"""E-01 alert_expiry: replay stop_508_peak over gtfs_mini through the real GetStopArrivals.

Run from backend/:  uv run python ../progress/explore_passage_samples/collect.py <scratch_dir> <step_s>
Writes <scratch_dir>/observations_<step>.json: one record per (cycle, stop, arrival).
No network, no real clock: FakeClock + SaeReplayArrivalsSource behind the production cache.
"""

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

sys.path.insert(0, str(Path.cwd()))  # backend/ → `tests.support`

from avisabus.adapters.inbound.http.container import build_stop_use_cases  # noqa: E402
from avisabus.domain.services.occupancy_simulation import service_day_start  # noqa: E402
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository  # noqa: E402
from tests.support.fake_clock import FakeClock  # noqa: E402
from tests.support.gtfs import GTFS_MINI  # noqa: E402
from tests.support.sae import STOP_508_PEAK  # noqa: E402
from tests.support.stops import (  # noqa: E402
    import_feed,
    new_engine,
    replay,
    simulated_sensor,
    stops_settings,
    token,
)

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
SESSION_S = 1480
STOPS = ("508", "2070")

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))


def prepare(scratch: Path):
    db = scratch / "gtfs_mini.sqlite"
    fresh = not db.exists()
    engine = new_engine(db)
    if fresh:
        import_feed(engine, GTFS_MINI)
    return engine


async def main(scratch: Path, step_s: int, engine) -> None:
    network = SqliteNetworkRepository(engine)
    settings = stops_settings()
    clock = FakeClock(PEAK_START)
    source, counting = replay(STOP_508_PEAK, clock)  # cache ttl 20 s as in production
    uc = build_stop_use_cases(
        settings, engine, clock, source, simulated_sensor(settings, engine, clock), {}
    ).get_stop_arrivals
    stop_times_cache: dict[str, list] = {}
    rows = []
    cycle = 0
    while (clock.now() - PEAK_START).total_seconds() <= SESSION_S:
        for stop in STOPS:
            res = await uc.execute(stop, token(stop))
            for rank, a in enumerate(res.arrivals):
                rec = {
                    "cycle": cycle,
                    "t_s": round((res.generated_at - PEAK_START).total_seconds()),
                    "stop": stop,
                    "source": res.source.value,
                    "rank": rank,
                    "line": a.line,
                    "direction_id": a.direction_id,
                    "in_network": a.in_network,
                    "sae_destination": a.sae_destination,
                    "minutes": a.minutes,
                    "lead_s": round((a.arrival_at - res.generated_at).total_seconds()),
                    "arrival_at": a.arrival_at.isoformat(),
                    "trip_id": None if a.vehicle is None else a.vehicle.trip_id,
                    "service_date": None if a.vehicle is None else a.vehicle.service_date.isoformat(),
                    "can_alert": a.can_alert,
                }
                if a.vehicle is not None:
                    st = stop_times_cache.setdefault(
                        a.vehicle.trip_id, sorted(network.trip_stop_times(a.vehicle.trip_id), key=lambda s: s.stop_sequence)
                    )
                    day = service_day_start(a.vehicle.service_date)
                    occ = [s for s in st if s.stop_id == stop]
                    closest = min(occ, key=lambda s: abs(day + timedelta(seconds=s.arrival_s) - a.arrival_at))
                    sched = day + timedelta(seconds=closest.arrival_s)
                    nxt = next((s for s in st if s.stop_sequence > closest.stop_sequence), None)
                    rec["scheduled_at"] = sched.isoformat()
                    rec["delay_s"] = round((a.arrival_at - sched).total_seconds())
                    rec["next_stop_scheduled_at"] = (
                        None if nxt is None else (day + timedelta(seconds=nxt.arrival_s)).isoformat()
                    )
                rows.append(rec)
        clock.advance(timedelta(seconds=step_s))
        cycle += 1
    out = scratch / f"observations_{step_s}.json"
    out.write_text(json.dumps({"cycles": cycle, "sae_requests": counting.calls, "rows": rows}, indent=0))
    print(f"cycles={cycle} sae_requests={counting.calls} rows={len(rows)} -> {out}")


if __name__ == "__main__":
    scratch = Path(sys.argv[1])
    asyncio.run(main(scratch, int(sys.argv[2]), prepare(scratch)))
