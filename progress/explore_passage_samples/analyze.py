"""E-01 alert_expiry: passage detection (AC-01/AC-02) over the observations of collect.py.

Usage: python3 analyze.py <observations_<step>.json>

- A "trip" is (stop, trip_id, service_date) of an arrival in the network with a paired vehicle.
- A disappearance is a cycle in which the trip is absent after being present in the previous one.
- Ground truth (independent of trip ids): for the (stop, line, direction) of the trip, let L be
  the trip's last lead (arrival_at - generated_at). The bus is GONE if the number of arrivals of
  that line/direction with lead <= L + 120 s decreases between both cycles; otherwise it is STILL
  PRESENT (the pairing moved the trip id to another bus, or to none).
- For a window W, AC-02 declares PASSED at the first disappearance with L <= W (per alert: one
  alert per trip created at its first appearance; it ends at its first PASSED).
"""

import json
import sys
from collections import defaultdict

data = json.load(open(sys.argv[1]))
rows = [r for r in data["rows"] if r["in_network"] and r["trip_id"]]
ncycles = data["cycles"]
by_cycle = defaultdict(list)  # (stop, line, dir, cycle) -> rows
for r in data["rows"]:
    if r["in_network"]:
        by_cycle[(r["stop"], r["line"], r["direction_id"], r["cycle"])].append(r)
t_of = {r["cycle"]: r["t_s"] for r in data["rows"]}
pres = defaultdict(dict)  # trip key -> cycle -> row
for r in rows:
    pres[(r["stop"], r["line"], r["direction_id"], r["trip_id"], r["service_date"])][r["cycle"]] = r


def leads(stop, line, d, c):
    return sorted(x["lead_s"] for x in by_cycle[(stop, line, d, c)])


def fmt(stop, line, d, c):
    return "[" + ", ".join(
        f"{x['minutes']}m:{x['trip_id'][-3:] if x['trip_id'] else '-'}"
        for x in sorted(by_cycle[(stop, line, d, c)], key=lambda x: x["lead_s"])
    ) + "]"


events = []
for key, cyc in sorted(pres.items(), key=lambda kv: (kv[0][0], kv[0][1], min(kv[1]))):
    stop, line, d, trip, sd = key
    cs = sorted(cyc)
    for c in range(cs[0] + 1, ncycles):
        if c in cyc or (c - 1) not in cyc:
            continue
        L = cyc[c - 1]["lead_s"]
        before = sum(1 for x in leads(stop, line, d, c - 1) if x <= L + 120)
        after = sum(1 for x in leads(stop, line, d, c) if x <= L + 120)
        back = next((k for k in cs if k > c), None)
        events.append(dict(
            stop=stop, line=line, trip=trip, cycle=c, t=t_of[c], lead=L, minutes=cyc[c - 1]["minutes"],
            gone=after < before, reappears=back, back_lead=None if back is None else cyc[back]["lead_s"],
            ctx=f"{fmt(stop, line, d, c - 1)} -> {fmt(stop, line, d, c)}",
        ))

print(f"trips tracked: {len(pres)} | disappearances: {len(events)} | cycles: {ncycles}")
for e in events:
    print(f"  {e['stop']:>4} {e['line']:>3} {e['trip'][-3:]} c{e['cycle']:>2} t={e['t']:>4}s last={e['minutes']}m({e['lead']}s) "
          f"{'GONE ' if e['gone'] else 'STILL'} reappears={'-' if e['reappears'] is None else 'c%d (%ss)' % (e['reappears'], e['back_lead'])}  {e['ctx']}")

print("\nDisappearances by last lead (all / bus GONE / bus STILL present):")
for lim in (60, 120, 180, 240, 10**9):
    sel = [e for e in events if e["lead"] <= lim]
    print(f"  <= {lim if lim < 10**9 else 'inf'} s: {len(sel)} / {sum(e['gone'] for e in sel)} / {sum(not e['gone'] for e in sel)}")
far = [e for e in events if e["lead"] > 180]
print(f"  > 180 s (far): {len(far)}; of them bus STILL present (pairing switch): {sum(not e['gone'] for e in far)}; "
      f"bus GONE from the list: {sum(e['gone'] for e in far)}")
re = [e for e in events if e["reappears"] is not None]
print(f"  disappear and reappear: {len(re)} events over {len({(e['stop'], e['trip']) for e in re})} trips; "
      f"with last lead <= 180 s: {sum(e['lead'] <= 180 for e in re)}")

# Real passages (ground truth at SAE level, independent of trip ids): per line/direction, cycles
# where the number of arrivals with lead <= 240 s decreases.
print("\nReal passages (count of arrivals with lead <= first lead + 120 s decreases, first lead <= 300 s):")
real = []
for (stop, line, d) in sorted({(k[0], k[1], k[2]) for k in pres}):
    for c in range(1, ncycles):
        prev = leads(stop, line, d, c - 1)
        if not prev or prev[0] > 300:
            continue
        lim = prev[0] + 120
        if sum(x <= lim for x in leads(stop, line, d, c)) < sum(x <= lim for x in prev):
            real.append((stop, line, c))
            print(f"  {stop} {line} c{c} t={t_of[c]}s {fmt(stop, line, d, c - 1)} -> {fmt(stop, line, d, c)}")

print("\nWindow sweep (one alert per trip from its first appearance; PASSED at first disappearance with lead <= W):")
print("  W(s)  PASSED  correct  premature  real passages caught / total")
for W in (0, 30, 60, 90, 120, 150, 180, 210, 240, 300, 420, 600):
    passed = {}
    for e in events:
        k = (e["stop"], e["trip"])
        if k not in passed and e["lead"] <= W:
            passed[k] = e
    ok = sum(e["gone"] for e in passed.values())
    bad = [e for e in passed.values() if not e["gone"]]
    caught = sum(any(e["gone"] and (e["stop"], e["line"], e["cycle"]) == rp for e in passed.values()) for rp in real)
    print(f"  {W:>4}  {len(passed):>6}  {ok:>7}  {len(bad):>9}  {caught} / {len(real)}"
          + ("   premature: " + ", ".join(f"{e['stop']} {e['line']} {e['trip'][-3:]} c{e['cycle']} ({e['lead']}s)" for e in bad) if bad else ""))

# Variant B: an alert is (re)created whenever the trip is present (can_alert) and has no live
# alert, e.g. a passenger who requests the trip again after it reappears.
print("\nVariant B (alert re-created on reappearance): W  PASSED  premature")
for W in (60, 120, 180, 240, 300):
    passed, bad = 0, []
    for key, cyc in pres.items():
        stop, line, d, trip, sd = key
        alive, last = False, None
        for c in range(min(cyc), ncycles):
            if c in cyc:
                if cyc[c]["can_alert"]:
                    alive = True
                last = cyc[c]
            elif alive and last is not None and (c - 1) in cyc and last["lead_s"] <= W:
                e = next(e for e in events if e["stop"] == stop and e["trip"] == trip and e["cycle"] == c)
                passed += 1
                alive = False
                if not e["gone"]:
                    bad.append(f"{stop} {line} {trip[-3:]} c{c} ({last['lead_s']}s)")
    print(f"  {W:>4}  {passed:>6}  {len(bad)}  {', '.join(bad)}")

# NEXT_STOP (AC-05, margin 2 min) for every disappearance that is not followed by a reappearance:
# instant at which it would fire (scheduled at the next stop + last delay + 120 s), relative to
# the session start, and whether the trip's bus is still listed at that cycle.
from datetime import datetime, timezone
start = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=timezone.utc)
print("\nNEXT_STOP after each disappearance without reappearance (margin 120 s):")
for e in events:
    if e["reappears"] is not None:
        continue
    key = next(k for k in pres if k[0] == e["stop"] and k[3] == e["trip"])
    last = pres[key][e["cycle"] - 1]
    if last.get("next_stop_scheduled_at") is None:
        print(f"  {e['stop']} {e['line']} {e['trip'][-3:]}: last stop, n/a")
        continue
    fire = (datetime.fromisoformat(last["next_stop_scheduled_at"]) - start).total_seconds() + last["delay_s"] + 120
    print(f"  {e['stop']} {e['line']} {e['trip'][-3:]} gone at t={e['t']}s (last {e['lead']}s, delay {last['delay_s']}s)"
          f" -> NEXT_STOP at t={fire:.0f}s ({fire - e['t']:+.0f}s after the disappearance)")
