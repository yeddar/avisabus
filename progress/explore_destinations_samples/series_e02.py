"""E-02: per-snapshot greedy matching of one stop/line/direction (exploration only).

Usage (from backend/): uv run --frozen python ../progress/explore_destinations_samples/series_e02.py <sqlite> <recording_dir> <stop> <line> <direction_id>
"""
import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0, str(Path(__file__).parent))
from tolerance_e02 import match, service_day_start, MADRID
from analyze_recordings import iter_snapshots
import sqlalchemy
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
repo = SqliteNetworkRepository(sqlalchemy.create_engine(f"sqlite:///{sys.argv[1]}"))
stop, line, d = sys.argv[3], sys.argv[4], int(sys.argv[5])
snaps = sorted((s for s in iter_snapshots(Path(sys.argv[2])) if s[0] == stop), key=lambda x: x[1])
pas = repo.scheduled_stop_times(stop, snaps[0][1] - timedelta(minutes=30), timedelta(minutes=90))
cands = [(p.trip_id, service_day_start(p.service_date) + timedelta(seconds=p.arrival_s)) for p in pas if p.line == line and p.direction_id == d]
print("scheduled:", [ (c[0], c[1].astimezone(MADRID).strftime("%H:%M:%S")) for c in cands])
prev=None
for _, at, arr in snaps:
    times = sorted(a.arrival_at for a in arr if a.line == line)
    res = match(times, cands, timedelta(minutes=20))
    row = at.astimezone(MADRID).strftime("%H:%M:%S") + "  " + "  ".join(
        f"{t.astimezone(MADRID).strftime('%H:%M')}->{r[0] if r else None}({(t-r[1]).total_seconds()/60:+.1f})" if r else f"{t.astimezone(MADRID).strftime('%H:%M')}->None" for t, r in zip(times, res))
    print(row)
