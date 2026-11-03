"""E-03: GTFS passages (direction, stop_sequence, time) of C1/C2 at their terminals, Tue 2026-11-03.

Usage (from backend/): uv run --frozen python ../progress/explore_destinations_samples/c1term_e03.py <sqlite>
"""
import sys
import sqlalchemy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
M = ZoneInfo("Europe/Madrid")
repo = SqliteNetworkRepository(sqlalchemy.create_engine(f"sqlite:///{sys.argv[1]}"))
for stop, line, at in [("1959","C1","09:55"),("2277","C1","09:55"),("346","C2","09:55"),("1057","C2","09:55"),("166","C2","09:55"),("691","C2","09:55")]:
    h, m = map(int, at.split(":"))
    t0 = datetime(2026,11,3,h,m,tzinfo=M)
    ps = [p for p in repo.scheduled_stop_times(stop, t0, timedelta(minutes=40)) if p.line == line]
    print(stop, line, [(p.direction_id, p.stop_sequence, f"{p.arrival_s//3600:02d}:{p.arrival_s%3600//60:02d}") for p in ps])
