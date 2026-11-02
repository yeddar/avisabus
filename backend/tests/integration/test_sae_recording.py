"""Recording raw SAE responses to disk (sae_arrivals_source T-06, AC-14)."""

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from avisabus.adapters.outbound.sae.http_source import RawResponse, SaeHttpArrivalsSource
from avisabus.adapters.outbound.sae.recording import (
    RecordingArrivalsSource,
    SaeRecording,
    SaeSession,
)
from avisabus.adapters.outbound.sae.replay import SaeReplayArrivalsSource
from avisabus.domain.errors import ArrivalsUnavailableError
from tests.support.fake_clock import FakeClock
from tests.support.sae import STOP_508_MINUTES

START = datetime(2026, 11, 3, 6, 45, tzinfo=UTC)
TEMPLATE = "https://sae.example/QR.php?sec=est&p={stop_id}"
HTML = "text/html; charset=utf-8"


def _session(stops: tuple[str, ...] = ("508",)) -> SaeSession:
    return SaeSession(
        started_at=START,
        stops=stops,
        interval_s=20,
        source_url_template=TEMPLATE,
        source_format="qrphp_html",
    )


def _read(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _recording_source(
    handler: Callable[[httpx.Request], httpx.Response], clock: FakeClock, out: Path
) -> tuple[SaeHttpArrivalsSource, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = SaeHttpArrivalsSource(
        client=client,
        url_template=TEMPLATE,
        clock=clock,
        timeout_s=3,
        user_agent="AvisaBus/test",
        on_raw=RecordingArrivalsSource(out, _session()),
    )
    return source, client


@pytest.mark.spec("sae_arrivals_source.AC-14")
@pytest.mark.spec("sae_arrivals_source.AC-22")
def test_session_file_has_start_stops_interval_and_format(tmp_path: Path) -> None:
    out = tmp_path / "session"
    RecordingArrivalsSource(out, _session(("508", "2070")))
    assert _read(out / "session.json") == {
        "started_at": "2026-11-03T06:45:00Z",
        "stops": ["508", "2070"],
        "interval_s": 20,
        "source_url_template": TEMPLATE,
        "source_format": "qrphp_html",
    }


@pytest.mark.spec("sae_arrivals_source.AC-14")
async def test_every_raw_response_of_the_http_source_is_written(tmp_path: Path) -> None:
    clock = FakeClock(START)
    out = tmp_path / "session"
    replies = iter(
        [
            httpx.Response(200, headers={"content-type": HTML}, content=STOP_508_MINUTES),
            httpx.Response(503, headers={"content-type": "text/plain"}, content=b"busy"),
        ]
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        clock.advance(timedelta(milliseconds=200))
        try:
            return next(replies)
        except StopIteration:
            raise httpx.ReadTimeout("timed out") from None

    source, client = _recording_source(handler, clock, out)
    async with client:
        await source.get_arrivals("508")
        clock.set(START + timedelta(seconds=20))
        with pytest.raises(ArrivalsUnavailableError):
            await source.get_arrivals("508")
        clock.set(START + timedelta(seconds=40))
        with pytest.raises(ArrivalsUnavailableError):
            await source.get_arrivals("508")

    assert sorted(p.name for p in (out / "508").iterdir()) == [
        "000000.json",
        "000020.json",
        "000040.json",
    ]
    assert _read(out / "508" / "000000.json") == {
        "stop_id": "508",
        "captured_at": "2026-11-03T06:45:00.200000Z",
        "offset_s": 0,
        "status": 200,
        "content_type": HTML,
        "body": STOP_508_MINUTES.decode("utf-8"),
        "error": None,
    }
    failed = _read(out / "508" / "000020.json")
    assert (failed["offset_s"], failed["status"], failed["body"], failed["error"]) == (
        20,
        503,
        "busy",
        None,
    )
    timeout = _read(out / "508" / "000040.json")
    assert (timeout["status"], timeout["content_type"], timeout["body"], timeout["error"]) == (
        None,
        None,
        None,
        "timeout",
    )


@pytest.mark.spec("sae_arrivals_source.AC-14")
def test_body_that_is_not_text_is_stored_as_base64(tmp_path: Path) -> None:
    out = tmp_path / "session"
    recorder = RecordingArrivalsSource(out, _session())
    binary = b"\x89PNG\r\n\x1a\n\xff\xfe"
    recorder(RawResponse("508", START + timedelta(seconds=7.9), 200, "image/png", binary, None))
    data = _read(out / "508" / "000007.json")
    assert data["body_encoding"] == "base64"
    assert base64.b64decode(data["body"]) == binary
    assert SaeRecording.from_json(data).body == binary


@pytest.mark.spec("sae_arrivals_source.AC-14")
@pytest.mark.spec("sae_arrivals_source.AC-15")
async def test_recorded_session_replays_like_the_live_source(tmp_path: Path) -> None:
    clock = FakeClock(START)
    out = tmp_path / "session"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": HTML}, content=STOP_508_MINUTES)

    source, client = _recording_source(handler, clock, out)
    async with client:
        live = await source.get_arrivals("508")

    replay = SaeReplayArrivalsSource(out, FakeClock(START))
    assert await replay.get_arrivals("508") == live
