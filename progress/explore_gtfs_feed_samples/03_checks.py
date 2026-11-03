"""E-01 (gtfs_import): comprobaciones complementarias. Solo lectura.

Uso: python3 -I progress/explore_gtfs_feed_samples/03_checks.py data/gtfs/emt

- rutas/lineas sin viajes
- formato de trip_id / service_id / shape_id
- viajes con horas >= 24h (muestra) y viaje con arrival maximo
- solape de paradas entre patrones de C1/C2/C3 (ida-vuelta por las mismas calles o semibucles)
- area del poligono formado por la concatenacion de los dos patrones de cada route_id de C2/C3
- espacios sobrantes en nombres y headsigns
- servicios activos el 2026-11-03 y 2026-11-04 para 70, 93, C2 y candidatas para la parada 2070
"""
import csv
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date

src = sys.argv[1]
R_EARTH = 6371008.8


def rows(name):
    with open(os.path.join(src, name), encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def signed_area(points):
    lat0 = math.radians(sum(p[0] for p in points) / len(points))
    xy = [(math.radians(lon) * math.cos(lat0) * R_EARTH, math.radians(lat) * R_EARTH) for lat, lon in points]
    return sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1] for i in range(len(xy))) / 2


routes = {r["route_id"]: r for r in rows("routes.txt")}
trips = list(rows("trips.txt"))
line_of = {rid: r["route_short_name"] for rid, r in routes.items()}
used_routes = Counter(t["route_id"] for t in trips)

print("## Rutas y lineas")
print("route_id:", len(routes), "| route_short_name distintos:", len(set(line_of.values())),
      "| lineas con viajes:", len({line_of[r] for r in used_routes}))
print("route_id sin viajes:", [(rid, line_of[rid], routes[rid]["route_desc"]) for rid in routes if rid not in used_routes])
multi = defaultdict(list)
for rid, l in line_of.items():
    multi[l].append((rid, used_routes.get(rid, 0)))
print("lineas con varios route_id (route_id, viajes):", {l: v for l, v in multi.items() if len(v) > 1})

print("\n## Formato de identificadores")
pat_trip = re.compile(r"^([^_]+)_(\d+)_([^_]+(?:_EXC)?)_(\d+)_(\d+)_(\d+)_(\d+)$")
bad = [t["trip_id"] for t in trips if not pat_trip.match(t["trip_id"])]
print("trip_id que no encajan en <linea>_<route>_<svc>_<orig>_<dest>_<n>_<seq>:", len(bad), bad[:5])
f6 = Counter()
chk = Counter()
for t in trips:
    m = pat_trip.match(t["trip_id"])
    if not m:
        continue
    l, rid, svc, o, dst, n, seq = m.groups()
    f6[n] += 1
    chk["line==short_name"] += l == line_of[t["route_id"]]
    chk["route==route_id"] += rid == t["route_id"]
    chk["prefix==service_id"] += t["trip_id"].startswith(t["service_id"] + "_")
    chk["shape==route_orig_dest"] += t["shape_id"] == f"{rid}_{o}_{dst}"
print("campo 6 (valores):", dict(f6))
print("coincidencias sobre", len(trips), "viajes:", dict(chk))
svc = Counter(re.sub(r"\d", "9", t["service_id"]) for t in trips)
print("formas de service_id:", dict(svc))
print("muestra service_id:", sorted({t["service_id"] for t in trips})[:6])

ends = {}
stop_seq = defaultdict(list)
over = []
mx = ("", "")
for r in rows("stop_times.txt"):
    stop_seq[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"], r["arrival_time"]))
for tid in stop_seq:
    stop_seq[tid].sort()
print("\n## stop_sequence")
print("viajes con stop_sequence no 1..n contiguo:",
      sum(1 for v in stop_seq.values() if [s for s, _, _ in v] != list(range(1, len(v) + 1))))
tr = {t["trip_id"]: t for t in trips}
first_after_24 = [(tid, v[0][2], v[-1][2]) for tid, v in stop_seq.items() if int(v[0][2].split(":")[0]) >= 24]
print("viajes que EMPIEZAN >= 24:00:", len(first_after_24), first_after_24[:5])
latest = sorted(stop_seq.items(), key=lambda kv: kv[1][-1][2].zfill(8))[-3:]
for tid, v in latest:
    print("ultimo arrival:", tid, line_of[tr[tid]["route_id"]], "salida", v[0][2], "llegada", v[-1][2], "paradas", len(v))
t31 = stop_seq["24_1040_602_2253_2172_3_031"]
print("muestra 24_1040_602_2253_2172_3_031 (primeras/ultimas 3):", t31[:3], t31[-3:])

print("\n## Solape de paradas entre patrones (C1, C2, C3, 98)")
shape_stops = {}
for t in trips:
    shape_stops.setdefault(t["shape_id"], [s for _, s, _ in stop_seq[t["trip_id"]]])
by_line = defaultdict(set)
for t in trips:
    by_line[line_of[t["route_id"]]].add(t["shape_id"])
for l in ("C1", "C2", "C3", "98", "4"):
    shs = sorted(by_line[l])
    for i, a in enumerate(shs):
        for b in shs[i + 1:]:
            A, B = set(shape_stops[a]), set(shape_stops[b])
            print(f"{l}: {a}({len(A)}) vs {b}({len(B)}) comunes={len(A & B)}")

pts = defaultdict(list)
for r in rows("shapes.txt"):
    pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
for k in pts:
    pts[k] = [(la, lo) for _, la, lo in sorted(pts[k])]
print("\n## Area (m2) de cada forma y de la concatenacion ida+vuelta por route_id")
for l in ("C1", "C2", "C3", "4", "70", "93"):
    for rid, _ in multi[l]:
        shs = sorted(s for s in by_line[l] if s.startswith(rid + "_"))
        if len(shs) == 2:
            a, b = shs
            print(f"{l} route {rid}: area({a})={signed_area(pts[a]):.0f} area({b})={signed_area(pts[b]):.0f} "
                  f"area(concat)={signed_area(pts[a] + pts[b]):.0f}")

print("\n## Espacios sobrantes")
stops = list(rows("stops.txt"))
ws = lambda s: s != s.strip() or "  " in s
print("stop_name con espacios sobrantes:", sum(ws(s["stop_name"]) for s in stops), [s["stop_name"] for s in stops if ws(s["stop_name"])][:5])
print("trip_headsign con espacios sobrantes:", Counter(t["trip_headsign"] for t in trips if ws(t["trip_headsign"])))
print("route_long_name con espacios sobrantes:", [r["route_long_name"] for r in routes.values() if ws(r["route_long_name"])])

print("\n## Servicios activos (fixture gtfs_mini)")
cal = {c["service_id"]: c for c in rows("calendar.txt")}
exc = defaultdict(dict)
for c in rows("calendar_dates.txt"):
    exc[c["service_id"]][c["date"]] = c["exception_type"]
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def active(sid, d):
    ds = d.strftime("%Y%m%d")
    e = exc.get(sid, {}).get(ds)
    if e == "1":
        return True
    if e == "2":
        return False
    c = cal.get(sid)
    return bool(c) and c["start_date"] <= ds <= c["end_date"] and c[DAYS[d.weekday()]] == "1"


print("service_id solo en calendar_dates:", sorted(set(exc) - set(cal))[:10], "...", len(set(exc) - set(cal)))
print("service_id usados por viajes y ausentes de calendar y calendar_dates:",
      len({t["service_id"] for t in trips} - set(cal) - set(exc)))
stop_lines_trips = Counter()
for t in trips:
    if "2070" in shape_stops[t["shape_id"]]:
        stop_lines_trips[line_of[t["route_id"]]] += 1
print("viajes (todo el feed) que pasan por 2070, por linea:", dict(stop_lines_trips))
for d in (date(2026, 11, 3), date(2026, 11, 4)):
    cnt = Counter()
    rows_cnt = Counter()
    for t in trips:
        if active(t["service_id"], d):
            cnt[line_of[t["route_id"]]] += 1
            rows_cnt[line_of[t["route_id"]]] += len(stop_seq[t["trip_id"]])
    print(d, {l: (cnt[l], rows_cnt[l]) for l in ("70", "93", "C2", "73", "95", "98", "99")}, "(viajes, filas stop_times)")
