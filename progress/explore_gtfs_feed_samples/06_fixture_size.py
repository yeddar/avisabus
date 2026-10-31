"""E-01 (gtfs_import): estimacion del tamano de gtfs_mini (design §8) para 70, 93, C2 + una linea
que sirva la parada 2070. Solo lectura; no escribe la fixture.

Uso: python3 -I progress/explore_gtfs_feed_samples/06_fixture_size.py data/gtfs/emt
"""
import csv
import os
import sys
from collections import defaultdict
from datetime import date

src = sys.argv[1]


def raw(name):
    with open(os.path.join(src, name), encoding="utf-8-sig", newline="") as fh:
        header = fh.readline()
        for line in fh:
            yield line, next(csv.reader([line]))


def rows(name):
    with open(os.path.join(src, name), encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
cal = {c["service_id"]: c for c in rows("calendar.txt")}
exc = defaultdict(dict)
for c in rows("calendar_dates.txt"):
    exc[c["service_id"]][c["date"]] = c["exception_type"]


def active(sid, d):
    ds = d.strftime("%Y%m%d")
    e = exc.get(sid, {}).get(ds)
    if e:
        return e == "1"
    c = cal.get(sid)
    return bool(c) and c["start_date"] <= ds <= c["end_date"] and c[DAYS[d.weekday()]] == "1"


line_of = {r["route_id"]: r["route_short_name"] for r in rows("routes.txt")}
days = (date(2026, 11, 3), date(2026, 11, 4))
trips = [t for t in rows("trips.txt") if any(active(t["service_id"], d) for d in days)]
st_bytes = defaultdict(int)
trip_line = {t["trip_id"]: line_of[t["route_id"]] for t in trips}
for line, r in raw("stop_times.txt"):
    l = trip_line.get(r[0])
    if l:
        st_bytes[l] += len(line.encode())
shape_line = {t["shape_id"]: line_of[t["route_id"]] for t in trips}
sh_bytes = defaultdict(int)
for line, r in raw("shapes.txt"):
    l = shape_line.get(r[0])
    if l:
        sh_bytes[l] += len(line.encode())
for l in ("70", "93", "C2", "73", "95", "98", "99"):
    print(f"linea {l}: stop_times {st_bytes[l] / 1e6:.2f} MB, shapes {sh_bytes[l] / 1e6:.2f} MB, viajes {sum(1 for v in trip_line.values() if v == l)}")
base = sum(st_bytes[l] + sh_bytes[l] for l in ("70", "93", "C2"))
for extra in ("73", "95", "98", "99"):
    print(f"70+93+C2+{extra}: ~{(base + st_bytes[extra] + sh_bytes[extra]) / 1e6:.2f} MB (+ trips/stops/calendar, < 0.1 MB)")
