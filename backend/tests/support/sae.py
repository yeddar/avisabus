"""Helpers for the SAE fixtures (`tests/fixtures/sae_recordings/`)."""

import json
from pathlib import Path
from typing import Any

SAE_RECORDINGS = Path(__file__).resolve().parent.parent / "fixtures" / "sae_recordings"
SAMPLES = SAE_RECORDINGS / "samples"
E01 = SAMPLES / "e01_2026-11-02"
DERIVED_NO_ARRIVALS = SAMPLES / "derived_no_arrivals"
DERIVED_CLOCK_TIME = SAMPLES / "derived_clock_time"
STOP_508_PEAK = SAE_RECORDINGS / "stop_508_peak"


def recording_json(session: Path, stop_id: str, offset_s: int) -> dict[str, Any]:
    path = session / stop_id / f"{offset_s:06d}.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def sample_body(session: Path, stop_id: str, offset_s: int) -> bytes:
    """Raw body (UTF-8 bytes, as received from QR.php) of a recorded response."""
    return str(recording_json(session, stop_id, offset_s)["body"]).encode("utf-8")


STOP_508_MINUTES = sample_body(E01, "508", 62)  # 93 5 min, 70 8 min, 93 13 min, 70 20 min
STOP_2070_NEXT = sample_body(E01, "2070", 50)  # first entry: 95 "Tres Creus - Próximo"
STOP_99999_UNKNOWN = sample_body(E01, "99999", 54)  # 200 with an empty header
STOP_508_NO_ARRIVALS = sample_body(DERIVED_NO_ARRIVALS, "508", 0)
STOP_508_CLOCK_TIME = sample_body(DERIVED_CLOCK_TIME, "508", 0)  # last entry "Alboraia - 22:41"


def replace_once(body: bytes, old: str, new: str) -> bytes:
    """Variant of a real body with exactly one text changed (fails if `old` is not unique)."""
    text = body.decode("utf-8")
    assert text.count(old) == 1, f"{old!r} must appear exactly once"
    return text.replace(old, new).encode("utf-8")
