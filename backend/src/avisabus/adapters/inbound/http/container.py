"""Use cases of the stop endpoints, built from the settings (stop_arrivals_api design §2).

`avisabus.main` calls `build_stop_use_cases` at start-up; the integration tests call it too, with
a `FakeClock` and a replayed or fake arrivals source.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy import Engine

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.adapters.outbound.security.hmac_stop_token import HmacStopTokenSigner
from avisabus.application.direction_overrides import validate_direction_overrides
from avisabus.application.get_stop import GetStop
from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.config import Settings
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.occupancy import OccupancySensor
from avisabus.domain.services.direction_resolver import DEFAULT_ALIASES

ARRIVALS_LOGGER = "avisabus.arrivals"


@dataclass(frozen=True, slots=True)
class StopUseCases:
    get_stop: GetStop
    get_stop_arrivals: GetStopArrivals
    direction_overrides: Mapping[tuple[str, str], str]
    """Valid overrides, keyed by (line, SAE destination) (AC-20)."""


def build_stop_use_cases(
    settings: Settings,
    engine: Engine,
    clock: Clock,
    arrivals: ArrivalsSource,
    occupancy: OccupancySensor,
    override_entries: Mapping[str, str],
) -> StopUseCases:
    """`override_entries` come from `read_direction_overrides`; they are checked here against
    the active network (`arrivals.override_invalid`)."""
    network = SqliteNetworkRepository(engine)
    signer = HmacStopTokenSigner(settings.stop_token_secret_bytes())
    logger = structlog.get_logger(ARRIVALS_LOGGER)
    overrides = validate_direction_overrides(override_entries, network, logger)
    scheduled = ScheduledArrivalsProvider(
        network,
        window=timedelta(minutes=settings.scheduled_window_min),
        per_direction=settings.scheduled_per_direction,
    )
    return StopUseCases(
        get_stop=GetStop(network, signer),
        get_stop_arrivals=GetStopArrivals(
            network=network,
            signer=signer,
            arrivals=arrivals,
            scheduled=scheduled,
            occupancy=occupancy,
            thresholds=settings.occupancy_thresholds(),
            clock=clock,
            refresh_after_s=math.ceil(settings.sae_cache_ttl_s),
            match_tolerance=timedelta(minutes=settings.trip_match_tolerance_min),
            aliases=DEFAULT_ALIASES,
            direction_overrides=overrides,
            min_score=settings.direction_min_score,
            logger=logger,
        ),
        direction_overrides=overrides,
    )
