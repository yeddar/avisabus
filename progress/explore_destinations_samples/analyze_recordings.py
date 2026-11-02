"""E-01/E-02 harness: parse SAE recordings and resolve directions against a GTFS SQLite DB.

Usage (from backend/):
  uv run --frozen python ../progress/explore_destinations_samples/analyze_recordings.py \
      <sqlite_path> <recording_dir> [<recording_dir> ...]
Recording dirs follow tests/fixtures/sae_recordings format (<stop>/<offset>.json).
--proposal FILE: JSON with add_aliases, remove_aliases, overrides ("line|dest": dir), min_score.
--lenient: count every raw entry (also the ones the parser skips).
Prints one row per (stop, line, SAE destination) with counts and resolution.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import sqlalchemy

sys.path.insert(0, str(Path(__file__).parent))
from resolver_prototype import DEFAULT_ALIASES, DirectionCandidate, resolve_direction  # noqa: E402

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.adapters.outbound.sae.qrphp_parser import (
    SaeUnparseableError,
    _QrPhpPage,
    parse_qrphp_html,
)

LENIENT = "--lenient" in sys.argv
if LENIENT:
    sys.argv.remove("--lenient")
PROPOSAL = None
if "--proposal" in sys.argv:
    i = sys.argv.index("--proposal")
    PROPOSAL = json.loads(Path(sys.argv[i + 1]).read_text())
    del sys.argv[i:i + 2]


def lenient_entries(body: str):
    """(line, destination) of EVERY entry, also those the parser skips (HH:MM:SS, empty time)."""
    page = _QrPhpPage()
    page.feed(body)
    page.close()
    for line, text in page.entries:
        text = (text or "").strip()
        dest = text.rsplit(" -", 1)[0].strip() if " -" in text else text
        yield line.strip(), dest


def iter_snapshots(rec_dir: Path):
    for f in sorted(rec_dir.rglob("*.json")):
        if f.name == "session.json":
            continue
        d = json.loads(f.read_text())
        if not d.get("body") or d.get("status") != 200:
            continue
        at = datetime.fromisoformat(d["captured_at"].replace("Z", "+00:00"))
        try:
            res = parse_qrphp_html(d["body"].encode(), d["stop_id"], at)
        except SaeUnparseableError:
            continue
        yield d["stop_id"], at, res.arrivals


def main() -> None:
    db = sys.argv[1]
    repo = SqliteNetworkRepository(sqlalchemy.create_engine(f"sqlite:///{db}"))
    aliases, overrides, min_score = dict(DEFAULT_ALIASES), {}, 0.34
    if PROPOSAL:
        for k in PROPOSAL.get("remove_aliases", []):
            aliases.pop(k, None)
        aliases.update(PROPOSAL.get("add_aliases", {}))
        overrides = {tuple(k.split("|", 1)): v for k, v in PROPOSAL.get("overrides", {}).items()}
        min_score = PROPOSAL.get("min_score", 0.34)
    counts: Counter = Counter()
    for rec in sys.argv[2:]:
        if LENIENT:
            for f in sorted(Path(rec).rglob("*.json")):
                if f.name == "session.json":
                    continue
                d = json.loads(f.read_text())
                if d.get("status") == 200 and d.get("body"):
                    for line, dest in lenient_entries(d["body"]):
                        counts[(d["stop_id"], line, dest)] += 1
            continue
        for stop, _at, arrivals in iter_snapshots(Path(rec)):
            for a in arrivals:
                counts[(stop, a.line, a.destination)] += 1
    total = in_net = resolved = 0
    rows = []
    for (stop, line, dest), n in sorted(counts.items()):
        hs = repo.headsigns_at_stop(stop, line)
        cands = [DirectionCandidate(h.direction_id, h.headsign) for h in hs]
        ex: dict = {}
        d = resolve_direction(dest, cands, aliases, min_score=min_score, overrides=overrides,
                              line=line, explain=ex)
        total += n
        if cands:
            in_net += n
            resolved += n if d is not None else 0
        hs_txt = "; ".join(f"{h.direction_id}:{h.headsign}({h.trip_count})" for h in hs) or "-"
        rows.append((stop, line, dest, n, hs_txt, len({c.direction_id for c in cands}),
                     ex.get("rule", "out_of_network"), ex.get("best"), d))
    for r in rows:
        print(" | ".join(str(x) for x in r))
    print(f"TOTAL arrivals={total} in_network={in_net} resolved={resolved} "
          f"pct={(100 * resolved / in_net) if in_net else 0:.1f}%")


if __name__ == "__main__":
    main()
