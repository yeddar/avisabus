"""Composition of the arrivals source from the settings (sae_arrivals_source AC-20).

`AVISABUS_ARRIVALS_SOURCE=replay` → `SaeReplayArrivalsSource` over `AVISABUS_SAE_REPLAY_DIR`;
`http` → `SaeHttpArrivalsSource`. Either way wrapped by `CachedArrivalsSource`, which is
returned as such so that the caller can schedule its `emit_stats`.
"""

from datetime import timedelta

import httpx

from avisabus.adapters.outbound.sae.cache import CachedArrivalsSource
from avisabus.adapters.outbound.sae.http_source import SaeHttpArrivalsSource, build_user_agent
from avisabus.adapters.outbound.sae.replay import SaeReplayArrivalsSource
from avisabus.config import Settings
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock


def build_arrivals_source(
    settings: Settings, clock: Clock, http_client: httpx.AsyncClient
) -> CachedArrivalsSource:
    """Raises `ConfigurationError` if the replay session cannot be used."""
    inner: ArrivalsSource
    if settings.resolved_arrivals_source() == "replay":
        inner = SaeReplayArrivalsSource(settings.sae_replay_dir, clock)
    else:
        inner = SaeHttpArrivalsSource(
            client=http_client,
            url_template=settings.sae_url_template,
            clock=clock,
            timeout_s=settings.sae_timeout_s,
            user_agent=build_user_agent(settings.sae_contact),
        )
    return CachedArrivalsSource(
        inner=inner,
        clock=clock,
        ttl=timedelta(seconds=settings.sae_cache_ttl_s),
        error_ttl=timedelta(seconds=settings.sae_error_ttl_s),
        max_concurrency=settings.sae_max_concurrency,
    )
