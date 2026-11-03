"""E-01 (gtfs_import): deteccion de bucles partidos en dos medios viajes y cobertura de la forma
representativa de cada sentido. Solo lectura.

Uso: python3 -I progress/explore_gtfs_feed_samples/04_loops_and_coverage.py data/gtfs/emt

Para cada route_id con dos patrones P, Q tales que P.ultima == Q.primera y Q.ultima == P.primera:
  - area(P), area(Q), area(P+Q) (shoelace, m2) y ratio = |area(P+Q)| / (|area(P)| + |area(Q)|)
  - mediana de la distancia de los puntos de P a la polilinea Q (m)
Cobertura: % de puntos de cada patron a > 150 m de la forma representativa de su sentido
(sentido segun design §4.3, forma representativa = shape con mas viajes del sentido; CU-08 4b).
"""
import csv
import math
import os
import statistics
import sys
from collections import Counter, defaultdict

src = sys.argv[1]
R = 6371008.8


def rows(name):
    with open(os.path.join(src, name), encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def proj(points, lat0):
    c = math.cos(math.radians(lat0))
    return [(math.radians(lo) * c * R, math.radians(la) * R) for la, lo in points]


def area(xy):
    return sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1] for i in range(len(xy))) / 2


def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def dist_to_poly(p, poly):
    return min(seg_dist(p, poly[i], poly[i + 1]) for i in range(len(poly) - 1))


LAT0 = 39.47
routes = {r["route_id"]: r["route_short_name"] for r in rows("routes.txt")}
trips = list(rows("trips.txt"))
shape_route = {}
shape_trips = Counter()
for t in trips:
    shape_route[t["shape_id"]] = t["route_id"]
    shape_trips[t["shape_id"]] += 1
first_trip = {}
for t in trips:
    first_trip.setdefault(t["shape_id"], t["trip_id"])
want = set(first_trip.values())
ends = {}
for r in rows("stop_times.txt"):
    if r["trip_id"] in want:
        ends.setdefault(r["trip_id"], []).append((int(r["stop_sequence"]), r["stop_id"]))
fl = {s: (min(ends[t])[1], max(ends[t])[1]) for s, t in first_trip.items()}
pts = defaultdict(list)
for r in rows("shapes.txt"):
    pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
xy = {s: proj([(la, lo) for _, la, lo in sorted(v)], LAT0) for s, v in pts.items()}

print("## Parejas de medios viajes por route_id")
print("linea route  P / Q | area P | area Q | area P+Q | ratio | mediana d(P,Q) m")
by_route = defaultdict(list)
for s, rid in shape_route.items():
    by_route[rid].append(s)
for rid in sorted(by_route, key=lambda r: routes[r]):
    shs = by_route[rid]
    for i, p in enumerate(shs):
        for q in shs[i + 1:]:
            if fl[p][1] == fl[q][0] and fl[q][1] == fl[p][0]:
                ap, aq, apq = area(xy[p]), area(xy[q]), area(xy[p] + xy[q])
                ratio = abs(apq) / (abs(ap) + abs(aq))
                med = statistics.median(dist_to_poly(pt, xy[q]) for pt in xy[p][::3])
                print(f"{routes[rid]:>3} {rid:>5} {p} / {q} | {ap:,.0f} | {aq:,.0f} | {apq:,.0f} | {ratio:.2f} | {med:.0f}")

print("\n## Cobertura de la forma representativa (lineas con > 1 patron por sentido segun §4.3)")
# sentidos segun §4.3 (solo rama lineal: no hay lineas circulares segun la regla de 500 m)
stops = {s["stop_id"]: (float(s["stop_lat"]), float(s["stop_lon"])) for s in rows("stops.txt")}


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


line_shapes = defaultdict(list)
for s, rid in shape_route.items():
    line_shapes[routes[rid]].append(s)
for line, shs in sorted(line_shapes.items()):
    ref = sorted(shs, key=lambda s: (-shape_trips[s], s))[0]
    O, D = stops[fl[ref][0]], stops[fl[ref][1]]
    dirs = defaultdict(list)
    for s in shs:
        F, L = stops[fl[s][0]], stops[fl[s][1]]
        dirs[0 if hav(F, O) + hav(L, D) <= hav(F, D) + hav(L, O) else 1].append(s)
    for d, ss in sorted(dirs.items()):
        if len(ss) < 2:
            continue
        rep = sorted(ss, key=lambda s: (-shape_trips[s], s))[0]
        for s in ss:
            if s == rep:
                continue
            far = sum(1 for pt in xy[s] if dist_to_poly(pt, xy[rep]) > 150)
            print(f"{line} dir {d}: rep={rep} patron={s} puntos a >150 m de rep: {far}/{len(xy[s])} ({100 * far / len(xy[s]):.0f} %)")
