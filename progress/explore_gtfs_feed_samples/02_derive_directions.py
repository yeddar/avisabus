"""E-01 (gtfs_import): aplica a mano el algoritmo de design §4.3 a todas las lineas. Solo lectura.

Uso: python3 -I progress/explore_gtfs_feed_samples/02_derive_directions.py data/gtfs/emt [--json out.json]

Patron = shape_id. Primera/ultima parada = las del viaje representativo del patron (la pareja
(primera, ultima) mas frecuente entre los viajes del shape; se informa si hay discrepancias).
"""
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict

src = sys.argv[1]
json_out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None

R_EARTH = 6371008.8
CIRCULAR_M = 500.0
DEGENERATE_M2 = 1000.0


def rows(name):
    with open(os.path.join(src, name), encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def haversine(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(h))


def signed_area(points):
    """Shoelace sobre proyeccion equirrectangular (m^2). >0 antihorario, <0 horario."""
    lat0 = math.radians(sum(p[0] for p in points) / len(points))
    xy = [(math.radians(lon) * math.cos(lat0) * R_EARTH, math.radians(lat) * R_EARTH) for lat, lon in points]
    s = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        s += x1 * y2 - x2 * y1
    return s / 2


routes = {r["route_id"]: r for r in rows("routes.txt")}
stops = {s["stop_id"]: s for s in rows("stops.txt")}
coord = {sid: (float(s["stop_lat"]), float(s["stop_lon"])) for sid, s in stops.items()}
trips = {t["trip_id"]: t for t in rows("trips.txt")}

# primera / ultima parada de cada viaje (por stop_sequence)
ends = {}
for r in rows("stop_times.txt"):
    seq = int(r["stop_sequence"])
    e = ends.setdefault(r["trip_id"], [seq, r["stop_id"], seq, r["stop_id"], 0])
    e[4] += 1
    if seq < e[0]:
        e[0], e[1] = seq, r["stop_id"]
    if seq > e[2]:
        e[2], e[3] = seq, r["stop_id"]

shape_pts = defaultdict(list)
for r in rows("shapes.txt"):
    shape_pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
for k in shape_pts:
    shape_pts[k].sort()

# patrones por linea
line_patterns = defaultdict(lambda: defaultdict(lambda: {"trips": 0, "ends": Counter(), "headsigns": Counter(), "routes": set(), "nstops": Counter()}))
for tid, t in trips.items():
    line = routes[t["route_id"]]["route_short_name"]
    p = line_patterns[line][t["shape_id"]]
    p["trips"] += 1
    e = ends[tid]
    p["ends"][(e[1], e[3])] += 1
    p["nstops"][e[4]] += 1
    p["headsigns"][t["trip_headsign"]] += 1
    p["routes"].add(t["route_id"])


def natural(line):
    return (0, int(line), "") if line.isdigit() else (1, 0, line)


result = {}
for line in sorted(line_patterns, key=natural):
    pats = line_patterns[line]
    plist = []
    for sid, p in pats.items():
        (first, last), _ = p["ends"].most_common(1)[0]
        pts = [(la, lo) for _, la, lo in shape_pts[sid]]
        plist.append({
            "shape_id": sid, "trips": p["trips"], "first": first, "last": last,
            "ends_variants": len(p["ends"]), "ends_all": {f"{a}->{b}": n for (a, b), n in p["ends"].items()},
            "nstops": dict(p["nstops"]),
            "headsigns": dict(p["headsigns"]), "routes": sorted(p["routes"]),
            "pattern_ends_m": round(haversine(coord[first], coord[last])),
            "area_m2": signed_area(pts) if len(pts) >= 3 else 0.0,
            "shape_start_to_first_stop_m": round(haversine(pts[0], coord[first])),
            "shape_end_to_last_stop_m": round(haversine(pts[-1], coord[last])),
        })
    ref = sorted(plist, key=lambda p: (-p["trips"], p["shape_id"]))[0]
    O, D = coord[ref["first"]], coord[ref["last"]]
    od = haversine(O, D)
    circular = od < CIRCULAR_M
    for p in plist:
        F, L = coord[p["first"]], coord[p["last"]]
        if not circular:
            ci = haversine(F, O) + haversine(L, D)
            cv = haversine(F, D) + haversine(L, O)
            p["c_igual"], p["c_inverso"] = round(ci), round(cv)
            p["dir"] = 0 if ci <= cv else 1
            p["margin_m"] = round(abs(ci - cv))
        else:
            if abs(p["area_m2"]) < DEGENERATE_M2:
                p["dir"] = 0
                p["ambiguous"] = True
            else:
                p["dir"] = 0 if (p["area_m2"] > 0) == (ref["area_m2"] > 0) else 1
    result[line] = {"ref": ref["shape_id"], "od_m": round(od), "circular": circular, "patterns": plist}

if json_out:
    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump({"result": result, "stop_names": {k: v["stop_name"] for k, v in stops.items()}}, fh, ensure_ascii=False, indent=1)

# salida legible
for line, r in result.items():
    dirs = sorted({p["dir"] for p in r["patterns"]})
    print(f"\n=== Linea {line} | ref={r['ref']} | dist(O,D)={r['od_m']} m | {'CIRCULAR' if r['circular'] else 'lineal'} | sentidos={dirs}")
    for p in sorted(r["patterns"], key=lambda p: (p["dir"], -p["trips"], p["shape_id"])):
        extra = (f"c_igual={p['c_igual']} c_inv={p['c_inverso']} margen={p['margin_m']}" if not r["circular"]
                 else f"area={p['area_m2']:.0f} m2" + (" AMBIGUA" if p.get("ambiguous") else ""))
        print(f"  dir {p['dir']} | {p['shape_id']:<16} | {p['trips']:>4} viajes | {p['first']}({stops[p['first']]['stop_name']}) -> "
              f"{p['last']}({stops[p['last']]['stop_name']}) | extremos patron {p['pattern_ends_m']} m | {extra} | "
              f"ends_var={p['ends_variants']} | routes={p['routes']} | hs={p['headsigns']}")
