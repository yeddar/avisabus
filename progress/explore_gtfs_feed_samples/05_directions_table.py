"""E-01 (gtfs_import): tabla Markdown de sentidos derivados por linea (design §4.3). Solo lectura.

Uso:
  python3 -I progress/explore_gtfs_feed_samples/02_derive_directions.py data/gtfs/emt --json /tmp/x/derived.json
  python3 -I progress/explore_gtfs_feed_samples/05_directions_table.py data/gtfs/emt /tmp/x/derived.json

Anomalias marcadas automaticamente:
  - VARIANTE: el sentido tiene patrones con extremos distintos.
  - MULTI-ROUTE: el sentido agrupa patrones de varios route_id.
  - BUCLE: el route_id del patron tiene dos medios viajes P/Q (P.ultima = Q.primera y viceversa)
    cuya distancia mediana P->Q > 300 m (no recorren las mismas calles): linea circular partida en
    dos medios viajes. Se indica el giro del bucle completo (signo del area de P+Q).
"""
import csv
import json
import math
import os
import statistics
import sys
from collections import defaultdict

src, jpath = sys.argv[1], sys.argv[2]
data = json.load(open(jpath, encoding="utf-8"))
res, names = data["result"], data["stop_names"]
R = 6371008.8


def rows(name):
    with open(os.path.join(src, name), encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


c = math.cos(math.radians(39.47))
pts = defaultdict(list)
for r in rows("shapes.txt"):
    pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
xy = {s: [(math.radians(lo) * c * R, math.radians(la) * R) for _, la, lo in sorted(v)] for s, v in pts.items()}


def area(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def sd(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def med(p, q):
    return statistics.median(min(sd(x, q[i], q[i + 1]) for i in range(len(q) - 1)) for x in p[::3])


loop_of = {}  # shape_id -> "horario"/"antihorario"
for line, r in res.items():
    pats = r["patterns"]
    for i, p in enumerate(pats):
        for q in pats[i + 1:]:
            if p["routes"] == q["routes"] and p["last"] == q["first"] and q["last"] == p["first"]:
                if med(xy[p["shape_id"]], xy[q["shape_id"]]) > 300:
                    giro = "antihorario" if area(xy[p["shape_id"]] + xy[q["shape_id"]]) > 0 else "horario"
                    loop_of[p["shape_id"]] = loop_of[q["shape_id"]] = giro


def stop(s):
    return f"{s} {names[s].strip()}"


print("| Línea | Tipo (§4.3) | Sentido | Patrones (viajes) | Headsigns (viajes) | Primera → última (patrón principal) | Viajes | Anomalías |")
print("|---|---|---|---|---|---|---|---|")
for line, r in res.items():
    by_dir = defaultdict(list)
    for p in r["patterns"]:
        by_dir[p["dir"]].append(p)
    for d in sorted(by_dir):
        ps = sorted(by_dir[d], key=lambda p: (-p["trips"], p["shape_id"]))
        main = ps[0]
        hs = defaultdict(int)
        for p in ps:
            for h, n in p["headsigns"].items():
                hs[h.strip() if h != h.strip() else h] += n
        anomalies = []
        if len({(p["first"], p["last"]) for p in ps}) > 1:
            anomalies.append("VARIANTE: " + "; ".join(f"{p['shape_id']} {p['first']}→{p['last']}" for p in ps[1:]))
        if len({tuple(p["routes"]) for p in ps}) > 1:
            anomalies.append("MULTI-ROUTE " + "+".join(sorted({x for p in ps for x in p["routes"]})))
        loops = sorted({f"{p['routes'][0]}:{loop_of[p['shape_id']]}" for p in ps if p["shape_id"] in loop_of})
        if loops:
            anomalies.append("BUCLE (medio viaje de) " + ", ".join(loops))
        print(f"| {line} | {'circular' if r['circular'] else 'lineal'} ({r['od_m']} m) | {d} | "
              + "<br>".join(f"{p['shape_id']} ({p['trips']})" for p in ps) + " | "
              + "<br>".join(f"{h} ({n})" for h, n in sorted(hs.items(), key=lambda kv: -kv[1])) + " | "
              + f"{stop(main['first'])} → {stop(main['last'])} | {sum(p['trips'] for p in ps)} | "
              + ("<br>".join(anomalies) or "—") + " |")
