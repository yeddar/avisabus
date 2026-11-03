"""E-03: evaluate an alternative fallback rule (exploration only, NOT in the spec):
when resolve_direction (design §3, given aliases/overrides) returns None at a stop where exactly
one candidate direction has trips that START at that stop, pick that "departing" direction.

Usage (from backend/): uv run --frozen python ../progress/explore_destinations_samples/departing_rule_e03.py \
    <sqlite> <proposal.json> <recording_dir> [...]
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import sqlalchemy

sys.path.insert(0, str(Path(__file__).parent))
from analyze_recordings import lenient_entries  # noqa: E402
from resolver_prototype import DEFAULT_ALIASES, DirectionCandidate, resolve_direction  # noqa: E402

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository


def main():
    db, prop = sys.argv[1], json.loads(Path(sys.argv[2]).read_text())
    repo = SqliteNetworkRepository(sqlalchemy.create_engine(f"sqlite:///{db}"))
    con = sqlite3.connect(db)
    starts = {}
    for line, stop, d in con.execute(
        "select t.line, st.stop_id, t.direction_id from gtfs_stop_time st join gtfs_trip t "
        "on t.trip_id = st.trip_id and t.feed_version_id = st.feed_version_id "
        "where st.stop_sequence = 1 group by 1, 2, 3"):
        starts.setdefault((line, stop), set()).add(d)
    aliases = dict(DEFAULT_ALIASES)
    for k in prop.get("remove_aliases", []):
        aliases.pop(k, None)
    aliases.update(prop.get("add_aliases", {}))
    overrides = {tuple(k.split("|", 1)): v for k, v in prop.get("overrides", {}).items()}
    counts = Counter()
    for rec in sys.argv[3:]:
        for f in sorted(Path(rec).rglob("*.json")):
            if f.name == "session.json":
                continue
            d = json.loads(f.read_text())
            for line, dest in lenient_entries(d["body"]):
                counts[(d["stop_id"], line, dest)] += 1
    tot = res = 0
    for (stop, line, dest), n in sorted(counts.items()):
        hs = repo.headsigns_at_stop(stop, line)
        if not hs:
            continue
        cands = [DirectionCandidate(h.direction_id, h.headsign) for h in hs]
        r = resolve_direction(dest, cands, aliases, overrides=overrides, line=line)
        rule = "algorithm"
        if r is None and len({c.direction_id for c in cands}) > 1:
            dep = starts.get((line, stop), set()) & {c.direction_id for c in cands}
            if len(dep) == 1:
                r, rule = next(iter(dep)), "departing"
        tot += n
        res += n if r is not None else 0
        if rule == "departing" or r is None:
            print(f"{stop} | {line} | {dest} | n={n} | {rule} -> {r}")
    print(f"TOTAL in_network={tot} resolved={res} pct={100 * res / tot:.1f}%")


if __name__ == "__main__":
    main()
