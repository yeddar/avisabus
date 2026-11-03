"""`SaeHttpArrivalsSource` over a simulated HTTP transport (sae_arrivals_source T-04).

`httpx.MockTransport` never opens a socket; the handler can advance the FakeClock to simulate
latency.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from structlog.testing import capture_logs

from avisabus.adapters.outbound.sae.http_source import RawResponse, SaeHttpArrivalsSource
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalKind
from tests.support.fake_clock import FakeClock
from tests.support.sae import STOP_508_MINUTES, STOP_99999_UNKNOWN

NOW = datetime(2026, 11, 2, 11, 0, 11, tzinfo=UTC)
TEMPLATE = "https://sae.example/QR.php?sec=est&p={stop_id}"
USER_AGENT = "AvisaBus/0.1.0 (TFM; contacto@example.org)"
HTML = "text/html; charset=utf-8"

Handler = Callable[[httpx.Request], httpx.Response]


def _source(
    handler: Handler, clock: FakeClock, raws: list[RawResponse] | None = None
) -> tuple[SaeHttpArrivalsSource, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = SaeHttpArrivalsSource(
        client=client,
        url_template=TEMPLATE,
        clock=clock,
        timeout_s=3,
        user_agent=USER_AGENT,
        on_raw=None if raws is None else raws.append,
    )
    return source, client


def _ok(body: bytes, *, latency: timedelta = timedelta(0), clock: FakeClock) -> Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        clock.advance(latency)
        return httpx.Response(200, headers={"content-type": HTML}, content=body)

    return handler


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


# --- AC-01 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-01")
async def test_single_request_with_url_timeout_and_user_agent(clock: FakeClock) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        clock.advance(timedelta(milliseconds=150))
        return httpx.Response(200, headers={"content-type": HTML}, content=STOP_508_MINUTES)

    source, client = _source(handler, clock)
    async with client:
        snapshot = await source.get_arrivals("508")

    (request,) = requests
    assert request.method == "GET"
    assert str(request.url) == "https://sae.example/QR.php?sec=est&p=508"
    assert request.headers["user-agent"] == USER_AGENT
    assert request.extensions["timeout"] == {"connect": 3, "read": 3, "write": 3, "pool": 3}
    fetched_at = NOW + timedelta(milliseconds=150)
    assert snapshot.stop_id == "508"
    assert snapshot.fetched_at == fetched_at
    assert [(a.line, a.destination, a.kind, a.minutes) for a in snapshot.arrivals] == [
        ("93", "Pass. Marítim", ArrivalKind.MINUTES, 5),
        ("70", "Alboraia", ArrivalKind.MINUTES, 8),
        ("93", "Pass. Marítim", ArrivalKind.MINUTES, 13),
        ("70", "Alboraia", ArrivalKind.MINUTES, 20),
    ]
    assert snapshot.arrivals[0].arrival_at == fetched_at + timedelta(minutes=5)


@pytest.mark.spec("sae_arrivals_source.AC-01")
async def test_stop_id_is_escaped_in_the_url(clock: FakeClock) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(404)

    source, client = _source(handler, clock)
    async with client:
        with pytest.raises(ArrivalsUnavailableError):
            await source.get_arrivals("508&p=1")
    assert urls == ["https://sae.example/QR.php?sec=est&p=508%26p%3D1"]


@pytest.mark.spec("sae_arrivals_source.AC-01")
async def test_raw_response_is_handed_to_the_observer(clock: FakeClock) -> None:
    raws: list[RawResponse] = []
    source, client = _source(
        _ok(STOP_508_MINUTES, latency=timedelta(milliseconds=80), clock=clock), clock, raws
    )
    async with client:
        await source.get_arrivals("508")
    assert raws == [
        RawResponse(
            stop_id="508",
            captured_at=NOW + timedelta(milliseconds=80),
            status=200,
            content_type=HTML,
            body=STOP_508_MINUTES,
            error=None,
        )
    ]


# --- AC-08 -------------------------------------------------------------------------------------


def _raising(error: Exception, clock: FakeClock) -> Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        clock.advance(timedelta(seconds=3))
        raise error

    return handler


@pytest.mark.spec("sae_arrivals_source.AC-08")
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx.ReadTimeout("timed out"), "timeout"),
        (httpx.ConnectTimeout("timed out"), "timeout"),
        (httpx.PoolTimeout("timed out"), "timeout"),
        (httpx.ConnectError("refused"), "network"),
        (httpx.RemoteProtocolError("closed"), "network"),
    ],
)
async def test_transport_failures_raise_unavailable_with_reason_and_log(
    clock: FakeClock, error: Exception, reason: str
) -> None:
    raws: list[RawResponse] = []
    source, client = _source(_raising(error, clock), clock, raws)
    async with client:
        with capture_logs() as logs, pytest.raises(ArrivalsUnavailableError) as raised:
            await source.get_arrivals("508")
    assert (raised.value.stop_id, raised.value.reason) == ("508", reason)
    assert [log for log in logs if log["event"] == "sae.error"] == [
        {
            "event": "sae.error",
            "log_level": "warning",
            "stop_id": "508",
            "reason": reason,
            "elapsed_ms": 3000,
        }
    ]
    assert raws == [RawResponse("508", NOW + timedelta(seconds=3), None, None, None, error=reason)]


@pytest.mark.spec("sae_arrivals_source.AC-08")
@pytest.mark.parametrize("status", [301, 404, 429, 500, 503])
async def test_non_2xx_status_raises_http_reason(clock: FakeClock, status: int) -> None:
    raws: list[RawResponse] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"content-type": "text/plain"}, content=b"down")

    source, client = _source(handler, clock, raws)
    async with client:
        with capture_logs() as logs, pytest.raises(ArrivalsUnavailableError) as raised:
            await source.get_arrivals("508")
    assert raised.value.reason == f"http_{status}"
    (event,) = [log for log in logs if log["event"] == "sae.error"]
    assert (event["stop_id"], event["reason"]) == ("508", f"http_{status}")
    assert [(r.status, r.body, r.error) for r in raws] == [(status, b"down", None)]


@pytest.mark.spec("sae_arrivals_source.AC-08")
@pytest.mark.spec("sae_arrivals_source.AC-21")
async def test_unparseable_body_raises_unparseable_and_logs(clock: FakeClock) -> None:
    source, client = _source(_ok(STOP_99999_UNKNOWN, clock=clock), clock)
    async with client:
        with capture_logs() as logs, pytest.raises(ArrivalsUnavailableError) as raised:
            await source.get_arrivals("99999")
    assert (raised.value.stop_id, raised.value.reason) == ("99999", "unparseable")
    (event,) = [log for log in logs if log["event"] == "sae.error"]
    assert (event["stop_id"], event["reason"]) == ("99999", "unparseable")
    assert "Gestiona" not in str(event)  # the body is never logged


@pytest.mark.spec("sae_arrivals_source.AC-08")
async def test_successful_fetch_logs_no_error(clock: FakeClock) -> None:
    source, client = _source(_ok(STOP_508_MINUTES, clock=clock), clock)
    async with client:
        with capture_logs() as logs:
            await source.get_arrivals("508")
    assert [log for log in logs if log["event"] == "sae.error"] == []
