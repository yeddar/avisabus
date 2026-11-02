"""`avisabus sae fetch` and `avisabus sae record` (sae_arrivals_source T-07).

The CLI runtime is replaced: simulated HTTP transport, FakeClock and a `sleep` that advances the
clock instead of waiting.
"""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from avisabus.adapters.inbound.cli import sae as sae_cli
from avisabus.adapters.inbound.cli.main import app
from avisabus.adapters.inbound.cli.sae import SaeCliRuntime
from avisabus.config import Settings
from tests.support.fake_clock import FakeClock
from tests.support.sae import (
    STOP_508_CLOCK_TIME,
    STOP_508_MINUTES,
    STOP_508_NO_ARRIVALS,
    STOP_99999_UNKNOWN,
)

runner = CliRunner()
NOW = datetime(2026, 11, 3, 6, 45, tzinfo=UTC)  # Tuesday 07:45 in Madrid
TEMPLATE = "https://sae.example/QR.php?sec=est&p={stop_id}"
HTML = "text/html; charset=utf-8"
LATENCY = timedelta(milliseconds=200)

Handler = Callable[[httpx.Request], httpx.Response]


class Harness:
    def __init__(self) -> None:
        self.clock = FakeClock(NOW)
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self.handler: Handler = lambda _request: httpx.Response(500)
        self.settings = Settings(  # type: ignore[call-arg]
            _env_file=None, env="test", sae_url_template=TEMPLATE, sae_contact="me@example.org"
        )

    def transport(self) -> httpx.MockTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            self.clock.advance(LATENCY)
            return self.handler(request)

        return httpx.MockTransport(handle)

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.clock.advance(timedelta(seconds=seconds))

    def runtime(self) -> SaeCliRuntime:
        return SaeCliRuntime(
            settings=self.settings, clock=self.clock, transport=self.transport(), sleep=self.sleep
        )


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    harness = Harness()
    monkeypatch.setattr(sae_cli, "build_runtime", harness.runtime)
    yield harness


def _html(body: bytes) -> Handler:
    return lambda _request: httpx.Response(200, headers={"content-type": HTML}, content=body)


def _read(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# --- AC-18: fetch ------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-18")
def test_fetch_shows_line_destination_and_minutes(harness: Harness) -> None:
    harness.handler = _html(STOP_508_MINUTES)
    result = runner.invoke(app, ["sae", "fetch", "--stop", "508"])
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == "Parada 508 · 2026-11-03 06:45:00 UTC · 4 llegadas"
    assert [line.split() for line in lines[1:]] == [
        ["93", "Pass.", "Marítim", "5", "min"],
        ["70", "Alboraia", "8", "min"],
        ["93", "Pass.", "Marítim", "13", "min"],
        ["70", "Alboraia", "20", "min"],
    ]
    (request,) = harness.requests
    assert str(request.url) == "https://sae.example/QR.php?sec=est&p=508"
    assert request.headers["user-agent"] == "AvisaBus/0.1.0 (TFM; me@example.org)"


@pytest.mark.spec("sae_arrivals_source.AC-18")
def test_fetch_shows_clock_times_in_madrid(harness: Harness) -> None:
    harness.handler = _html(STOP_508_CLOCK_TIME)
    result = runner.invoke(app, ["sae", "fetch", "--stop", "508"])
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[-1].split() == ["70", "Alboraia", "22:41"]


@pytest.mark.spec("sae_arrivals_source.AC-18")
def test_fetch_without_arrivals(harness: Harness) -> None:
    harness.handler = _html(STOP_508_NO_ARRIVALS)
    result = runner.invoke(app, ["sae", "fetch", "--stop", "508"])
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [
        "Parada 508 · 2026-11-03 06:45:00 UTC · 0 llegadas",
        "  Sin llegadas.",
    ]


@pytest.mark.spec("sae_arrivals_source.AC-18")
@pytest.mark.parametrize(
    ("handler", "reason"),
    [
        (_html(STOP_99999_UNKNOWN), "unparseable"),
        (lambda _request: httpx.Response(503), "http_503"),
    ],
)
def test_fetch_shows_the_error_reason(harness: Harness, handler: Handler, reason: str) -> None:
    harness.handler = handler
    result = runner.invoke(app, ["sae", "fetch", "--stop", "99999"])
    assert result.exit_code == 1
    assert "Parada" not in result.stdout  # no arrivals listing (stdout only carries the logs)
    assert result.stderr.strip() == (
        f"ERROR: llegadas no disponibles para la parada 99999 (motivo: {reason})"
    )


@pytest.mark.spec("sae_arrivals_source.AC-18")
def test_fetch_shows_timeout(harness: Harness) -> None:
    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    harness.handler = timeout
    result = runner.invoke(app, ["sae", "fetch", "--stop", "508"])
    assert result.exit_code == 1
    assert "(motivo: timeout)" in result.stderr


# --- AC-17: record -----------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-17")
def test_record_queries_every_interval_for_the_duration(harness: Harness, tmp_path: Path) -> None:
    harness.handler = _html(STOP_508_MINUTES)
    out = tmp_path / "stop_508_peak"
    result = runner.invoke(
        app,
        [
            "sae",
            "record",
            "--stop",
            "508",
            "--interval",
            "20",
            "--duration",
            "900",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output

    files = sorted(p.name for p in (out / "508").iterdir())
    assert files == [f"{offset:06d}.json" for offset in range(0, 900, 20)]  # 45 queries
    assert len(harness.requests) == 45
    assert _read(out / "session.json") == {
        "started_at": "2026-11-03T06:45:00Z",
        "stops": ["508"],
        "interval_s": 20,
        "source_url_template": TEMPLATE,
        "source_format": "qrphp_html",
    }
    last = _read(out / "508" / "000880.json")
    assert last["captured_at"] == "2026-11-03T06:59:40.200000Z"
    assert last["body"] == STOP_508_MINUTES.decode("utf-8")
    # Each cycle starts `interval` seconds after the previous one, discounting the request time.
    assert harness.sleeps == [pytest.approx(19.8)] * 44
    assert harness.clock.now() == NOW + timedelta(seconds=880) + LATENCY


@pytest.mark.spec("sae_arrivals_source.AC-17")
def test_record_keeps_going_and_exits_0_when_queries_fail(harness: Harness, tmp_path: Path) -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.params["p"] == "2070" and calls["n"] % 4 == 0:
            raise httpx.ConnectTimeout("timed out")
        return httpx.Response(200, headers={"content-type": HTML}, content=STOP_508_MINUTES)

    harness.handler = flaky
    out = tmp_path / "two_stops"
    result = runner.invoke(
        app,
        [
            "sae",
            "record",
            "--stop",
            "508",
            "--stop",
            "2070",
            "--interval",
            "30",
            "--duration",
            "120",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert [r.url.params["p"] for r in harness.requests] == ["508", "2070"] * 4
    assert sorted(p.name for p in (out / "508").iterdir()) == [
        "000000.json",
        "000030.json",
        "000060.json",
        "000090.json",
    ]
    recorded_2070 = [_read(p) for p in sorted((out / "2070").iterdir())]
    assert len(recorded_2070) == 4
    assert [r["error"] for r in recorded_2070] == [None, "timeout", None, "timeout"]
    # 508 parses as 508 but not as 2070 (header of another stop): recorded, reported, not fatal.
    assert "2070: error (unparseable)" in result.stdout
    assert "2070: error (timeout)" in result.stdout


@pytest.mark.spec("sae_arrivals_source.AC-17")
def test_record_refuses_to_overwrite_a_session(harness: Harness, tmp_path: Path) -> None:
    out = tmp_path / "existing"
    out.mkdir()
    (out / "session.json").write_text("{}", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "sae",
            "record",
            "--stop",
            "508",
            "--interval",
            "20",
            "--duration",
            "60",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 2
    assert harness.requests == []
    assert (out / "session.json").read_text(encoding="utf-8") == "{}"


@pytest.mark.spec("sae_arrivals_source.AC-17")
@pytest.mark.parametrize(
    "args",
    [
        ["--interval", "20", "--duration", "60"],  # no --stop
        ["--stop", "508", "--interval", "0", "--duration", "60"],
        ["--stop", "508", "--interval", "20", "--duration", "0"],
    ],
)
def test_record_rejects_invalid_options(harness: Harness, tmp_path: Path, args: list[str]) -> None:
    result = runner.invoke(app, ["sae", "record", *args, "--out", str(tmp_path / "x")])
    assert result.exit_code == 2
    assert harness.requests == []
