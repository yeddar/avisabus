"""Dump parsed arrivals (and skipped entries) of a recording dir. Usage (from backend/):
uv run --frozen python ../progress/explore_destinations_samples/dump_night.py <recording_dir>
"""
import json, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from avisabus.adapters.outbound.sae.qrphp_parser import parse_qrphp_html
M = ZoneInfo("Europe/Madrid")
for f in sorted(Path(sys.argv[1]).rglob("*.json")):
    if f.name == "session.json": continue
    d = json.loads(f.read_text())
    at = datetime.fromisoformat(d["captured_at"].replace("Z", "+00:00"))
    r = parse_qrphp_html(d["body"].encode(), d["stop_id"], at)
    print(d["stop_id"], at.astimezone(M).strftime("%H:%M:%S"), [(a.line, a.destination, a.kind.value, a.minutes, a.arrival_at.astimezone(M).strftime("%H:%M")) for a in r.arrivals], "SKIPPED:" , r.skipped)
