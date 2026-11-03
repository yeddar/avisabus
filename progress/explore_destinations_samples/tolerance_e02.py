"""E-02: distribution of |arrival_at - scheduled_at| of the best candidate (exploration only).

Usage (from backend/):
  uv run --frozen python ../progress/explore_destinations_samples/tolerance_e02.py \
      <sqlite_path> <recording_dir>
Directions resolved with the design §3 prototype; matching = design §3 match_trips (greedy, in
order, each trip at most once, strictly increasing scheduled time), evaluated for several
tolerances. Also reports the unconstrained nearest candidate (|delta| of the best candidate).
"""
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import sqlalchemy

sys.path.insert(0, str(Path(__file__).parent))
from analyze_recordings import iter_snapshots  # noqa: E402
from resolver_prototype import DEFAULT_ALIASES, DirectionCandidate, resolve_direction  # noqa: E402

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository

MADRID = ZoneInfo("Europe/Madrid")
TOLS = [5, 8, 10, 12, 15, 20, 30]


def service_day_start(d):
    # GTFS: noon minus 12h, local time
    return datetime(d.year, d.month, d.day, 12, tzinfo=MADRID) - timedelta(hours=12)


def match(times, cands, tol):
    out, used, last = [], set(), None
    for t in times:
        best = None
        for c in cands:
            if c[0] in used or (last is not None and c[1] <= last):
                continue
            dd = abs((c[1] - t).total_seconds())
            if dd <= tol.total_seconds() and (best is None or dd < abs((best[1] - t).total_seconds())):
                best = c
        out.append(best)
        if best:
            used.add(best[0]); last = best[1]
    return out


def main():
    repo = SqliteNetworkRepository(sqlalchemy.create_engine(f"sqlite:///{sys.argv[1]}"))
    nearest = defaultdict(list)       # line -> [signed delta min]
    rank_deltas = defaultdict(list)   # (rank) -> [abs delta] with tol 30
    matched = {t: [0, 0] for t in TOLS}
    first_trip = {}                   # (stop,line,dir) -> trip id of first arrival, to count switches
    switches = defaultdict(int)
    for stop, at, arrivals in sorted(iter_snapshots(Path(sys.argv[2])), key=lambda x: (x[0], x[1])):
        groups = defaultdict(list)
        for a in arrivals:
            hs = repo.headsigns_at_stop(stop, a.line)
            if not hs:
                continue
            d = resolve_direction(a.destination, [DirectionCandidate(h.direction_id, h.headsign) for h in hs],
                                  DEFAULT_ALIASES, line=a.line)
            if d is None:
                continue
            groups[(a.line, d)].append(a.arrival_at)
        for (line, d), times in groups.items():
            times.sort()
            span = times[-1] - times[0]
            pas = repo.scheduled_stop_times(stop, times[0] - timedelta(minutes=60), timedelta(minutes=120) + span)
            cands = [(p.trip_id + "@" + str(p.service_date), service_day_start(p.service_date) + timedelta(seconds=p.arrival_s))
                     for p in pas if p.line == line and p.direction_id == d]
            for t in times:
                if cands:
                    b = min(cands, key=lambda c: abs((c[1] - t).total_seconds()))
                    nearest[line].append((t - b[1]).total_seconds() / 60)
            for tol in TOLS:
                res = match(times, cands, timedelta(minutes=tol))
                matched[tol][0] += sum(1 for r in res if r)
                matched[tol][1] += len(res)
                if tol == 20:
                    k = (stop, line, d)
                    if res and res[0]:
                        if k in first_trip and first_trip[k] != res[0][0]:
                            switches[k] += 1
                        first_trip[k] = res[0][0]
                if tol == 30:
                    for i, (t, r) in enumerate(zip(times, res)):
                        if r:
                            rank_deltas[i].append(abs((r[1] - t).total_seconds()) / 60)
    allabs = []
    for line, v in sorted(nearest.items()):
        a = sorted(abs(x) for x in v)
        allabs += a
        q = statistics.quantiles(a, n=20) if len(a) > 1 else a
        print(f"line {line}: n={len(v)} signed mean={statistics.mean(v):+.1f} min, |d| median={statistics.median(a):.1f} "
              f"p95={q[18] if len(a)>1 else a[0]:.1f} max={max(a):.1f}")
    a = sorted(allabs)
    q = statistics.quantiles(a, n=20)
    print(f"ALL: n={len(a)} |d| median={statistics.median(a):.1f} p90={q[17]:.1f} p95={q[18]:.1f} max={max(a):.1f}")
    for th in (2, 5, 10, 15, 20):
        print(f"  share |d|<={th} min: {100*sum(1 for x in a if x<=th)/len(a):.1f}%")
    for i, v in sorted(rank_deltas.items()):
        print(f"rank {i+1} (tol 30, greedy): n={len(v)} median={statistics.median(v):.1f} max={max(v):.1f}")
    for tol in TOLS:
        m, n = matched[tol]
        print(f"tol {tol:>2} min: matched {m}/{n} = {100*m/n:.1f}%")
    print("first-arrival trip switches (tol 20):", dict(switches))


if __name__ == "__main__":
    main()
