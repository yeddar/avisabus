"""E-01 (gtfs_import): estadisticas basicas del feed. Solo lectura.

Uso: python3 -I progress/explore_gtfs_feed_samples/01_basic_stats.py data/gtfs/emt
"""
import csv
import os
import sys
from collections import Counter, defaultdict

src = sys.argv[1]


def rows(name):
    with open(os.path.join(src, name), encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def secs(t):
    h, m, s = (int(x) for x in t.strip().split(":"))
    return h * 3600 + m * 60 + s


print("## Filas de datos por fichero (sin cabecera)")
for f in sorted(os.listdir(src)):
    if f.endswith(".txt"):
        print(f"{f}: {sum(1 for _ in rows(f))}")

routes = {r["route_id"]: r for r in rows("routes.txt")}
trips = list(rows("trips.txt"))
print("\n## trips.txt")
print("viajes:", len(trips))
print("sin shape_id:", sum(1 for t in trips if not t["shape_id"].strip()))
print("sin trip_headsign:", sum(1 for t in trips if not t["trip_headsign"].strip()))
print("trip_id == trip_short_name:", sum(1 for t in trips if t["trip_id"] == t["trip_short_name"]))
print("route_id inexistente:", sum(1 for t in trips if t["route_id"] not in routes))
# shape compartida entre lineas
shape_lines = defaultdict(set)
for t in trips:
    shape_lines[t["shape_id"]].add(routes[t["route_id"]]["route_short_name"])
print("shape_id distintos:", len(shape_lines))
print("shape_id compartidos entre lineas:", {s: sorted(l) for s, l in shape_lines.items() if len(l) > 1})

trip_line = {t["trip_id"]: routes[t["route_id"]]["route_short_name"] for t in trips}
print("\n## stop_times.txt")
max_arr = (0, None)
over24_trips = set()
over24_rows = 0
empty_times = 0
stop_lines = defaultdict(set)
headsign_nonempty = 0
for r in rows("stop_times.txt"):
    if not r["arrival_time"].strip():
        empty_times += 1
        continue
    s = secs(r["arrival_time"])
    if s > max_arr[0]:
        max_arr = (s, r["arrival_time"], r["trip_id"])
    if s >= 86400:
        over24_rows += 1
        over24_trips.add(r["trip_id"])
    if r["stop_headsign"].strip():
        headsign_nonempty += 1
    stop_lines[r["stop_id"]].add(trip_line[r["trip_id"]])
print("arrival_time maximo:", max_arr)
print("filas con arrival >= 24:00:00:", over24_rows, "en", len(over24_trips), "viajes")
print("lineas con viajes >= 24h:", sorted(Counter(trip_line[t] for t in over24_trips).items()))
print("filas con arrival_time vacio:", empty_times)
print("filas con stop_headsign no vacio:", headsign_nonempty)

stops = {s["stop_id"]: s for s in rows("stops.txt")}
print("\n## Paradas 508 y 2070")
for sid in ("508", "2070"):
    st = stops.get(sid)
    print(sid, st and st["stop_name"], "->", sorted(stop_lines.get(sid, set())))
print("paradas sin viajes:", sum(1 for s in stops if s not in stop_lines))
print("stop_id == stop_code:", sum(1 for s in stops.values() if s["stop_id"] == s["stop_code"]), "/", len(stops))
