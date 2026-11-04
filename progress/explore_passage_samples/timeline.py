"""Per-cycle timeline of the in-network arrivals: `minutes m / lead s : trip suffix (delay s)`.

Usage: python3 timeline.py <observations_<step>.json>
"""

import json
import sys
from collections import defaultdict

data = json.load(open(sys.argv[1]))
by = defaultdict(list)
for r in data["rows"]:
    if r["in_network"]:
        by[(r["stop"], r["line"], r["cycle"])].append(r)
for stop, line in sorted({(k[0], k[1]) for k in by}):
    print(f"== stop {stop} line {line}")
    for c in range(data["cycles"]):
        rs = sorted(by[(stop, line, c)], key=lambda r: r["lead_s"])
        t = rs[0]["t_s"] if rs else "-"
        print(f"c{c:<3} t={t:<5} " + "  ".join(
            f"{r['minutes']}m/{r['lead_s']}s:{r['trip_id'][-3:] if r['trip_id'] else '-'}(d{r.get('delay_s')})"
            for r in rs))
