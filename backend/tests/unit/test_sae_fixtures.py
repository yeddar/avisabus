"""Contents of the SAE fixtures (sae_arrivals_source AC-19).

A bus passage is detected as in AC-19 (a): the first ETA of a line (and destination) reaches
0–2 minutes and, in the next response, the first arrival of that line jumps to what was the
following bus.
"""

import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from avisabus.adapters.outbound.sae.qrphp_parser import parse_qrphp_html
from avisabus.adapters.outbound.sae.recording import SaeRecording, read_recordings, read_session
from avisabus.domain.models.arrivals import ArrivalKind, SaeArrival
from tests.support.sae import (
    DERIVED_CLOCK_TIME,
    DERIVED_NO_ARRIVALS,
    E01,
    SAE_RECORDINGS,
    STOP_508_PEAK,
)

MADRID = ZoneInfo("Europe/Madrid")
ARRIVING_MAX_MIN = 2
JUMP_MIN = 3
TOLERANCE_MIN = 3

Key = tuple[str, str]


def _minutes_by_line(arrivals: tuple[SaeArrival, ...]) -> dict[Key, list[int]]:
    by_line: dict[Key, list[int]] = {}
    for arrival in arrivals:
        if arrival.kind is ArrivalKind.MINUTES and arrival.minutes is not None:
            by_line.setdefault((arrival.line, arrival.destination), []).append(arrival.minutes)
    return by_line


def _snapshots(recordings: list[SaeRecording]) -> list[tuple[int, dict[Key, list[int]]]]:
    result = []
    for recording in recordings:
        if recording.error is None and recording.status == 200 and recording.body is not None:
            parsed = parse_qrphp_html(recording.body, recording.stop_id, recording.captured_at)
            result.append((recording.offset_s, _minutes_by_line(parsed.arrivals)))
    return result


def passages(recordings: list[SaeRecording]) -> list[tuple[int, Key]]:
    """`(offset_s, (line, destination))` of every observed passage of a bus."""
    found = []
    snapshots = _snapshots(recordings)
    for (prev_offset, prev), (offset, curr) in zip(snapshots, snapshots[1:], strict=False):
        elapsed_min = (offset - prev_offset) / 60
        for key, prev_etas in prev.items():
            curr_etas = curr.get(key)
            if not curr_etas or prev_etas[0] > ARRIVING_MAX_MIN:
                continue
            if curr_etas[0] < prev_etas[0] + JUMP_MIN:
                continue
            if len(prev_etas) > 1 and abs(curr_etas[0] - (prev_etas[1] - elapsed_min)) > (
                TOLERANCE_MIN
            ):
                continue
            found.append((offset, key))
    return found


# --- passage detector over the real E-01 samples -----------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_detects_the_real_passage_of_line_95_at_stop_2070() -> None:
    recordings = read_recordings(E01)
    assert passages(recordings["2070"]) == [(149, ("95", "Tres Creus"))]


@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_decreasing_etas_are_not_a_passage() -> None:
    assert passages(read_recordings(E01)["508"]) == []


# --- (b), (c), (d) -----------------------------------------------------------------------------


def _derived(session: Path) -> SaeRecording:
    (recording,) = read_recordings(session)["508"]
    data = json.loads((session / "508" / "000000.json").read_text(encoding="utf-8"))
    assert data["derived_from"].startswith("progress/explore_sae_samples/")
    assert data["note"]
    return recording


@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_b_response_without_arrivals_is_derived_and_documented() -> None:
    recording = _derived(DERIVED_NO_ARRIVALS)
    assert recording.body is not None
    assert parse_qrphp_html(recording.body, "508", recording.captured_at).arrivals == ()


@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_c_response_with_clock_time_is_derived_and_documented() -> None:
    recording = _derived(DERIVED_CLOCK_TIME)
    assert recording.body is not None
    arrivals = parse_qrphp_html(recording.body, "508", recording.captured_at).arrivals
    assert [a.kind for a in arrivals].count(ArrivalKind.CLOCK_TIME) == 1


@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_d_real_error_case_is_the_unknown_stop() -> None:
    (recording,) = read_recordings(E01)["99999"]
    assert recording.status == 200
    data = json.loads((E01 / "99999" / "000054.json").read_text(encoding="utf-8"))
    assert "derived_from" not in data


@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_readme_describes_every_session() -> None:
    readme = (SAE_RECORDINGS / "README.md").read_text(encoding="utf-8")
    for session in ("e01_2026-11-02", "derived_no_arrivals", "derived_clock_time", "stop_508_peak"):
        assert f"`{session}" in readme or f"/{session}/" in readme, session


# --- (a) real peak session of stop 508 (T-08) --------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_a_real_peak_session_of_stop_508_shows_a_passage() -> None:
    assert (STOP_508_PEAK / "session.json").is_file(), (
        "stop_508_peak has not been recorded yet (T-08, needs the network: see "
        "tests/fixtures/sae_recordings/README.md)"
    )
    session = read_session(STOP_508_PEAK)
    assert session.stops == ("508",)
    assert session.interval_s == 20
    assert session.source_format == "qrphp_html"
    assert session.started_at.astimezone(MADRID).weekday() <= 3  # Mon–Thu (gtfs_mini services)
    recordings = read_recordings(STOP_508_PEAK)["508"]
    assert recordings[-1].offset_s + session.interval_s >= 15 * 60
    for path in (STOP_508_PEAK / "508").glob("*.json"):
        assert "derived_from" not in json.loads(path.read_text(encoding="utf-8")), path.name
    assert passages(recordings), "no bus passage observed in stop_508_peak"
