"""E-02 bis: stability of the trip assigned to the FIRST arrival of each line+direction across
consecutive snapshots, greedy (design §3) vs. optimal order-preserving assignment.

Optimal = among all order-preserving injective assignments within tolerance, maximise the number of
matched arrivals, then minimise the sum of |delta|. Exploration only.
Usage (from backend/): uv run --frozen python ../progress/explore_destinations_samples/matching_stability_e02.py <sqlite> <recording_dir>
"""
import itertools
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import sqlalchemy

sys.path.insert(0, str(Path(__file__).parent))
from analyze_recordings import iter_snapshots  # noqa: E402
from resolver_prototype import DEFAULT_ALIASES, DirectionCandidate, resolve_direction  # noqa: E402
from tolerance_e02 import match as greedy, service_day_start  # noqa: E402

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository


def optimal(times, cands, tol):
    best, best_key = [None] * len(times), (0, 0.0)
    opts = [[None] + [c for c in cands if abs((c[1] - t).total_seconds()) <= tol.total_seconds()] for t in times]
    for combo in itertools.product(*opts):
        chosen = [c for c in combo if c]
        if len({c[0] for c in chosen}) != len(chosen):
            continue
        if any(b[1] <= a[1] for a, b in zip(chosen, chosen[1:])):
            continue
        cost = sum(abs((c[1] - t).total_seconds()) for t, c in zip(times, combo) if c)
        key = (len(chosen), -cost)
        if key > best_key or (best_key == (0, 0.0) and not any(best)):
            best, best_key = list(combo), key
    return best


def main():
    repo = SqliteNetworkRepository(sqlalchemy.create_engine(f"sqlite:///{sys.argv[1]}"))
    snaps = sorted(iter_snapshots(Path(sys.argv[2])), key=lambda x: (x[0], x[1]))
    for tol_min in (10, 15, 20):
        tol = timedelta(minutes=tol_min)
        for name, fn in (("greedy", greedy), ("optimal", optimal)):
            last, sw, back, matched, n = {}, 0, 0, 0, 0
            for stop, at, arrivals in snaps:
                groups = defaultdict(list)
                for a in arrivals:
                    hs = repo.headsigns_at_stop(stop, a.line)
                    d = resolve_direction(a.destination, [DirectionCandidate(h.direction_id, h.headsign) for h in hs], DEFAULT_ALIASES)
                    if d is not None:
                        groups[(a.line, d)].append(a.arrival_at)
                for (line, d), times in groups.items():
                    times.sort()
                    pas = repo.scheduled_stop_times(stop, times[0] - timedelta(minutes=60), timedelta(minutes=120) + (times[-1] - times[0]))
                    cands = [(p.trip_id, service_day_start(p.service_date) + timedelta(seconds=p.arrival_s)) for p in pas if p.line == line and p.direction_id == d]
                    res = fn(times, cands, tol)
                    n += len(res); matched += sum(1 for r in res if r)
                    k = (stop, line, d)
                    if res[0]:
                        if k in last and last[k][0] != res[0][0]:
                            sw += 1
                            if res[0][1] < last[k][1]:
                                back += 1
                        last[k] = res[0]
            print(f"tol {tol_min:>2} {name:<7}: matched {matched}/{n}, first-arrival trip changes {sw} (backwards {back})")


if __name__ == "__main__":
    main()
