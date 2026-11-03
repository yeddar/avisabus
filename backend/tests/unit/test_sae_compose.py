"""Composition of the arrivals source and the `sae.stats` task (sae_arrivals_source T-09)."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from structlog.testing import capture_logs

from avisabus.adapters.outbound.sae.cache import CachedArrivalsSource
from avisabus.adapters.outbound.sae.compose import build_arrivals_source
from avisabus.background.sae_stats import SAE_STATS_INTERVAL, run_sae_stats
from avisabus.config import ConfigurationError, Settings
from tests.support.fake_clock import FakeClock
from tests.support.sae import E01, STOP_508_MINUTES

NOW = datetime(2026, 11, 3, 6, 45, tzinfo=UTC)
SECRET = "x" * 32


def _settings(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


class Transport:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def client(self) -> httpx.AsyncClient:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(
                200, headers={"content-type": "text/html; charset=utf-8"}, content=STOP_508_MINUTES
            )

        return httpx.AsyncClient(transport=httpx.MockTransport(handle))


# --- AC-20: settings ---------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-20")
@pytest.mark.parametrize(
    ("env", "expected"), [("test", "replay"), ("dev", "http"), ("prod", "http")]
)
def test_default_source_depends_on_the_environment(env: str, expected: str) -> None:
    settings = _settings(env=env, stop_token_secret=SECRET)
    assert settings.arrivals_source is None
    assert settings.resolved_arrivals_source() == expected


@pytest.mark.spec("sae_arrivals_source.AC-20")
def test_source_can_be_chosen_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVISABUS_ARRIVALS_SOURCE", "replay")
    assert _settings(env="dev").resolved_arrivals_source() == "replay"
    monkeypatch.setenv("AVISABUS_ARRIVALS_SOURCE", "http")
    assert _settings(env="test").resolved_arrivals_source() == "http"
    monkeypatch.setenv("AVISABUS_ARRIVALS_SOURCE", "sae")
    with pytest.raises(ValidationError):
        _settings(env="test")


@pytest.mark.spec("sae_arrivals_source.AC-20")
def test_sae_defaults() -> None:
    settings = _settings(env="dev")
    assert settings.sae_url_template == "https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}"
    assert (settings.sae_timeout_s, settings.sae_cache_ttl_s, settings.sae_error_ttl_s) == (
        3,
        20,
        5,
    )
    assert settings.sae_max_concurrency == 4
    assert settings.sae_replay_dir == Path("tests/fixtures/sae_recordings/stop_508_peak")
    assert settings.sae_contact == ""


@pytest.mark.spec("sae_arrivals_source.AC-20")
@pytest.mark.parametrize(
    "template", ["https://sae.example/QR.php", "https://sae.example/{stop}", "https://x/{0}"]
)
def test_url_template_without_stop_placeholder_is_rejected(template: str) -> None:
    with pytest.raises(ConfigurationError):
        _settings(env="dev", sae_url_template=template)


# --- AC-20: composition ------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-20")
async def test_http_source_wrapped_by_the_cache() -> None:
    transport, clock = Transport(), FakeClock(NOW)
    settings = _settings(
        env="dev",
        sae_url_template="https://sae.example/QR.php?p={stop_id}",
        sae_timeout_s=1.5,
        sae_contact="me@example.org",
        sae_cache_ttl_s=60,
    )
    async with transport.client() as client:
        source = build_arrivals_source(settings, clock, client)
        assert isinstance(source, CachedArrivalsSource)
        first = await source.get_arrivals("508")
        clock.advance(timedelta(seconds=59))
        assert await source.get_arrivals("508") is first  # configured TTL
    (request,) = transport.requests
    assert str(request.url) == "https://sae.example/QR.php?p=508"
    assert request.headers["user-agent"] == "AvisaBus/0.1.0 (TFM; me@example.org)"
    assert request.extensions["timeout"]["read"] == 1.5
    assert len(first.arrivals) == 4


@pytest.mark.spec("sae_arrivals_source.AC-20")
async def test_replay_source_wrapped_by_the_cache_and_never_the_network() -> None:
    transport, clock = Transport(), FakeClock(NOW)
    settings = _settings(env="test", sae_replay_dir=E01, sae_cache_ttl_s=120)
    async with transport.client() as client:
        source = build_arrivals_source(settings, clock, client)
        assert isinstance(source, CachedArrivalsSource)
        first = await source.get_arrivals("508")
        clock.advance(timedelta(seconds=62))  # offset 62 exists, but the cache still holds
        assert await source.get_arrivals("508") is first
        clock.advance(timedelta(seconds=58))  # 120 s: the cache expires, replay is at offset 62
        assert (await source.get_arrivals("508")).arrivals[0].minutes == 5
    assert [a.minutes for a in first.arrivals] == [7, 9, 14, 21]  # offset 0 of the E-01 session
    assert transport.requests == []


@pytest.mark.spec("sae_arrivals_source.AC-20")
async def test_cache_limits_come_from_the_settings() -> None:
    settings = _settings(env="test", sae_replay_dir=E01, sae_error_ttl_s=30)
    async with httpx.AsyncClient() as client:
        source = build_arrivals_source(settings, FakeClock(NOW), client)
        stats_before = source.stats()
        for _ in range(3):
            with pytest.raises(Exception, match="arrivals unavailable"):
                await source.get_arrivals("1234")  # no recording → cached error for 30 s
    assert source.stats().errors == stats_before.errors + 1


@pytest.mark.spec("sae_arrivals_source.AC-20")
@pytest.mark.spec("sae_arrivals_source.AC-22")
async def test_missing_replay_session_stops_the_composition(tmp_path: Path) -> None:
    settings = _settings(env="test", sae_replay_dir=tmp_path / "nothing")
    async with httpx.AsyncClient() as client:
        with pytest.raises(ConfigurationError):
            build_arrivals_source(settings, FakeClock(NOW), client)


# --- AC-13: periodic sae.stats -----------------------------------------------------------------


class Emitter:
    def __init__(self) -> None:
        self.calls = 0

    def emit_stats(self) -> None:
        self.calls += 1


@pytest.mark.spec("sae_arrivals_source.AC-13")
async def test_stats_are_emitted_every_five_minutes() -> None:
    emitter, sleeps = Emitter(), []

    async def sleep(seconds: float) -> None:
        if len(sleeps) == 3:
            raise asyncio.CancelledError
        sleeps.append(seconds)

    assert timedelta(minutes=5) == SAE_STATS_INTERVAL
    with pytest.raises(asyncio.CancelledError):
        await run_sae_stats(emitter, sleep=sleep)
    assert sleeps == [300, 300, 300]
    assert emitter.calls == 3


@pytest.mark.spec("sae_arrivals_source.AC-13")
async def test_stats_task_logs_the_cache_counters() -> None:
    settings = _settings(env="test", sae_replay_dir=E01)
    async with httpx.AsyncClient() as client:
        source = build_arrivals_source(settings, FakeClock(NOW), client)
        await source.get_arrivals("508")
        await source.get_arrivals("508")

    calls = 0

    async def sleep(_seconds: float) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise asyncio.CancelledError

    with capture_logs() as logs, pytest.raises(asyncio.CancelledError):
        await run_sae_stats(source, sleep=sleep)
    assert [log for log in logs if log["event"] == "sae.stats"] == [
        {"event": "sae.stats", "log_level": "info", "hits": 1, "misses": 1, "errors": 0}
    ]
