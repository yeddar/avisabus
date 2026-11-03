"""`SaeReplayArrivalsSource` driven by the clock (sae_arrivals_source T-06)."""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from avisabus.adapters.outbound.sae import replay as replay_module
from avisabus.adapters.outbound.sae.qrphp_parser import ParseResult, parse_qrphp_html
from avisabus.adapters.outbound.sae.replay import SaeReplayArrivalsSource
from avisabus.config import ConfigurationError
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalKind, SaeArrival
from tests.support.fake_clock import FakeClock
from tests.support.sae import E01, STOP_508_MINUTES

T0 = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)  # replay time, unrelated to the recording time


def _minutes(snapshot_arrivals: tuple[SaeArrival, ...]) -> list[tuple[str, int | None]]:
    return [(a.line, a.minutes) for a in snapshot_arrivals]


def _write_session(
    path: Path, recordings: list[dict[str, Any]], source_format: str = "qrphp_html"
) -> Path:
    path.mkdir(parents=True)
    session = {
        "started_at": "2026-11-03T06:45:00Z",
        "stops": sorted({r["stop_id"] for r in recordings}),
        "interval_s": 20,
        "source_url_template": "https://sae.example/QR.php?sec=est&p={stop_id}",
        "source_format": source_format,
    }
    (path / "session.json").write_text(json.dumps(session), encoding="utf-8")
    for recording in recordings:
        stop_dir = path / recording["stop_id"]
        stop_dir.mkdir(exist_ok=True)
        name = f"{recording['offset_s']:06d}.json"
        (stop_dir / name).write_text(json.dumps(recording), encoding="utf-8")
    return path


def _recording(offset_s: int, **fields: Any) -> dict[str, Any]:
    return {
        "stop_id": "508",
        "captured_at": "2026-11-03T06:45:00Z",
        "offset_s": offset_s,
        "status": 200,
        "content_type": "text/html; charset=utf-8",
        "body": STOP_508_MINUTES.decode("utf-8"),
        "error": None,
        **fields,
    }


# --- AC-15 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-15")
async def test_replay_follows_the_clock_from_the_first_request() -> None:
    clock = FakeClock(T0)
    source = SaeReplayArrivalsSource(E01, clock)

    first = await source.get_arrivals("508")  # elapsed 0 → offset 0 (93 at 7 min)
    assert first.fetched_at == T0
    assert _minutes(first.arrivals) == [("93", 7), ("70", 9), ("93", 14), ("70", 21)]
    assert first.arrivals[0].arrival_at == T0 + timedelta(minutes=7)

    clock.advance(timedelta(seconds=61))  # offset 62 not reached yet
    assert _minutes((await source.get_arrivals("508")).arrivals)[0] == ("93", 7)

    clock.advance(timedelta(seconds=1))  # elapsed 62 → offset 62 (93 at 5 min)
    snapshot = await source.get_arrivals("508")
    assert snapshot.fetched_at == T0 + timedelta(seconds=62)
    assert _minutes(snapshot.arrivals)[0] == ("93", 5)
    assert snapshot.arrivals[0].arrival_at == snapshot.fetched_at + timedelta(minutes=5)


@pytest.mark.spec("sae_arrivals_source.AC-15")
async def test_replay_shows_the_passage_of_line_95_at_stop_2070() -> None:
    clock = FakeClock(T0)
    source = SaeReplayArrivalsSource(E01, clock, start=T0)

    clock.advance(timedelta(seconds=50))
    before = await source.get_arrivals("2070")
    assert before.arrivals[0] == SaeArrival(
        "95", "Tres Creus", ArrivalKind.MINUTES, 0, T0 + timedelta(seconds=50)
    )

    clock.advance(timedelta(seconds=99))  # elapsed 149
    after = await source.get_arrivals("2070")
    first_95 = next(a for a in after.arrivals if a.line == "95")
    assert first_95.minutes == 10


@pytest.mark.spec("sae_arrivals_source.AC-15")
async def test_explicit_start_and_last_recording_after_the_end() -> None:
    clock = FakeClock(T0)
    source = SaeReplayArrivalsSource(E01, clock, start=T0 - timedelta(seconds=150))
    assert _minutes((await source.get_arrivals("508")).arrivals)[0] == ("93", 3)  # offset 147

    clock.advance(timedelta(hours=1))  # long after offset 212, the last one
    assert _minutes((await source.get_arrivals("508")).arrivals) == [
        ("93", 2),
        ("70", 6),
        ("93", 10),
        ("70", 17),
    ]


@pytest.mark.spec("sae_arrivals_source.AC-15")
async def test_replay_uses_the_same_parser_as_the_http_source() -> None:
    source = SaeReplayArrivalsSource(E01, FakeClock(T0))
    snapshot = await source.get_arrivals("508")
    body = (json.loads((E01 / "508" / "000000.json").read_text(encoding="utf-8"))["body"]).encode()
    assert snapshot.arrivals == parse_qrphp_html(body, "508", T0).arrivals


# --- AC-16 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-16")
async def test_stop_without_recordings_is_unavailable() -> None:
    source = SaeReplayArrivalsSource(E01, FakeClock(T0))
    with pytest.raises(ArrivalsUnavailableError) as raised:
        await source.get_arrivals("1234")
    assert (raised.value.stop_id, raised.value.reason) == ("1234", "no_recording")


@pytest.mark.spec("sae_arrivals_source.AC-16")
async def test_stop_without_a_recording_yet_is_unavailable() -> None:
    source = SaeReplayArrivalsSource(E01, FakeClock(T0))
    with pytest.raises(ArrivalsUnavailableError) as raised:
        await source.get_arrivals("2070")  # first recording of 2070 is at offset 50
    assert raised.value.reason == "no_recording"


@pytest.mark.spec("sae_arrivals_source.AC-16")
@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"status": None, "content_type": None, "body": None, "error": "timeout"}, "timeout"),
        ({"status": None, "content_type": None, "body": None, "error": "network"}, "network"),
        ({"status": 503, "content_type": "text/plain", "body": "busy"}, "http_503"),
    ],
)
async def test_recorded_error_is_replayed_as_unavailable(
    tmp_path: Path, fields: dict[str, Any], reason: str
) -> None:
    session = _write_session(tmp_path / "s", [_recording(0), _recording(20, **fields)])
    clock = FakeClock(T0)
    source = SaeReplayArrivalsSource(session, clock)
    assert len((await source.get_arrivals("508")).arrivals) == 4
    clock.advance(timedelta(seconds=20))
    with pytest.raises(ArrivalsUnavailableError) as raised:
        await source.get_arrivals("508")
    assert (raised.value.stop_id, raised.value.reason) == ("508", reason)


@pytest.mark.spec("sae_arrivals_source.AC-16")
@pytest.mark.spec("sae_arrivals_source.AC-19")
async def test_recorded_unknown_stop_page_is_unparseable() -> None:
    clock = FakeClock(T0)
    source = SaeReplayArrivalsSource(E01, clock, start=T0)
    clock.advance(timedelta(seconds=54))
    with pytest.raises(ArrivalsUnavailableError) as raised:
        await source.get_arrivals("99999")
    assert raised.value.reason == "unparseable"


# --- AC-22 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-22")
def test_unknown_source_format_fails_at_construction(tmp_path: Path) -> None:
    session = _write_session(tmp_path / "s", [_recording(0)], source_format="getsae_xml")
    with pytest.raises(ConfigurationError, match="getsae_xml"):
        SaeReplayArrivalsSource(session, FakeClock(T0))


@pytest.mark.spec("sae_arrivals_source.AC-22")
def test_session_without_source_format_fails_at_construction(tmp_path: Path) -> None:
    session = _write_session(tmp_path / "s", [_recording(0)])
    data = json.loads((session / "session.json").read_text(encoding="utf-8"))
    del data["source_format"]
    (session / "session.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        SaeReplayArrivalsSource(session, FakeClock(T0))


@pytest.mark.spec("sae_arrivals_source.AC-22")
def test_missing_session_fails_at_construction(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        SaeReplayArrivalsSource(tmp_path / "missing", FakeClock(T0))
    shutil.copytree(E01, tmp_path / "copy")
    (tmp_path / "copy" / "session.json").unlink()
    with pytest.raises(ConfigurationError):
        SaeReplayArrivalsSource(tmp_path / "copy", FakeClock(T0))


@pytest.mark.spec("sae_arrivals_source.AC-22")
async def test_parser_is_chosen_by_the_session_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[bytes] = []

    def other_parser(body: bytes, stop_id: str, fetched_at: datetime) -> ParseResult:
        seen.append(body)
        return ParseResult(arrivals=(), skipped=())

    monkeypatch.setattr(
        replay_module, "PARSERS", {"qrphp_html": parse_qrphp_html, "other": other_parser}
    )
    session = _write_session(tmp_path / "s", [_recording(0, body="opaque")], "other")
    snapshot = await SaeReplayArrivalsSource(session, FakeClock(T0)).get_arrivals("508")
    assert snapshot.arrivals == ()
    assert seen == [b"opaque"]


@pytest.mark.spec("sae_arrivals_source.AC-22")
def test_every_sample_session_declares_the_qrphp_format() -> None:
    for session in sorted((E01.parent).iterdir()):
        data = json.loads((session / "session.json").read_text(encoding="utf-8"))
        assert data["source_format"] == "qrphp_html", session.name
