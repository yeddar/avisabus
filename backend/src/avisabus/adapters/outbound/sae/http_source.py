"""SAE arrivals over HTTP (`QR.php`, sae_arrivals_source design §3, §4 and §6).

One GET per call, identified by the project's User-Agent. Every raw outcome (response or
transport failure) can be handed to an observer, which is how `avisabus sae record` writes the
sessions (`RecordingArrivalsSource`).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import httpx
import structlog

import avisabus
from avisabus.adapters.outbound.sae.qrphp_parser import build_snapshot, parse_qrphp_html
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from avisabus.domain.ports.clock import Clock

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RawResponse:
    """What the SAE returned for one request, before parsing."""

    stop_id: str
    captured_at: datetime
    status: int | None
    """HTTP status; `None` if no response was received."""
    content_type: str | None
    body: bytes | None
    error: str | None
    """`timeout` or `network` when no response was received; otherwise `None`."""


RawObserver = Callable[[RawResponse], None]


def build_user_agent(contact: str) -> str:
    """`AvisaBus/<version> (TFM; <contact>)` (design §7)."""
    return f"AvisaBus/{avisabus.__version__} (TFM; {contact})"


class SaeHttpArrivalsSource:
    def __init__(
        self,
        client: httpx.AsyncClient,
        url_template: str,
        clock: Clock,
        timeout_s: float,
        user_agent: str,
        on_raw: RawObserver | None = None,
    ) -> None:
        self._client = client
        self._url_template = url_template
        self._clock = clock
        self._timeout = httpx.Timeout(timeout_s)
        self._user_agent = user_agent
        self._on_raw = on_raw

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        started = self._clock.now()
        url = self._url_template.format(stop_id=quote(stop_id, safe=""))
        try:
            response = await self._client.get(
                url, headers={"User-Agent": self._user_agent}, timeout=self._timeout
            )
        except httpx.TimeoutException:
            raise self._transport_failure(stop_id, "timeout", started) from None
        except httpx.HTTPError:
            raise self._transport_failure(stop_id, "network", started) from None

        captured_at = self._clock.now()
        body = response.content
        self._notify(
            RawResponse(
                stop_id=stop_id,
                captured_at=captured_at,
                status=response.status_code,
                content_type=response.headers.get("content-type"),
                body=body,
                error=None,
            )
        )
        if not response.is_success:
            raise self._failure(stop_id, f"http_{response.status_code}", started)
        try:
            return build_snapshot(parse_qrphp_html, body, stop_id, captured_at)
        except ArrivalsUnavailableError as error:
            raise self._failure(stop_id, error.reason, started) from None

    def _transport_failure(
        self, stop_id: str, reason: str, started: datetime
    ) -> ArrivalsUnavailableError:
        self._notify(
            RawResponse(
                stop_id=stop_id,
                captured_at=self._clock.now(),
                status=None,
                content_type=None,
                body=None,
                error=reason,
            )
        )
        return self._failure(stop_id, reason, started)

    def _failure(self, stop_id: str, reason: str, started: datetime) -> ArrivalsUnavailableError:
        elapsed_ms = round((self._clock.now() - started).total_seconds() * 1000)
        log.warning("sae.error", stop_id=stop_id, reason=reason, elapsed_ms=elapsed_ms)
        return ArrivalsUnavailableError(stop_id, reason)

    def _notify(self, raw: RawResponse) -> None:
        if self._on_raw is not None:
            self._on_raw(raw)
