"""Use case: state of the active feed for `avisabus gtfs info` (AC-18, AC-19, AC-26)."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from avisabus.domain.models.network import FeedVersion
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.gtfs_import import DirectionReport, FeedInfoSource
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.feed_validity import (
    DEFAULT_WARNING_DAYS,
    FeedValidityStatus,
    feed_validity_status,
)

FALLBACK_TIMEZONE = "UTC"


@dataclass(frozen=True, slots=True)
class GetFeedInfoQuery:
    include_directions: bool = False


@dataclass(frozen=True, slots=True)
class FeedInfo:
    feed: FeedVersion
    validity: FeedValidityStatus
    directions: tuple[DirectionReport, ...]


class GetFeedInfo:
    def __init__(
        self,
        network: NetworkRepository,
        source: FeedInfoSource,
        clock: Clock,
        warning_days: int = DEFAULT_WARNING_DAYS,
    ) -> None:
        self._network = network
        self._source = source
        self._clock = clock
        self._warning_days = warning_days

    async def execute(self, query: GetFeedInfoQuery) -> FeedInfo | None:
        """`None` when no feed has been imported yet."""
        feed = self._network.active_feed()
        if feed is None:
            return None
        timezone = self._source.active_timezone() or FALLBACK_TIMEZONE
        today = self._clock.now().astimezone(ZoneInfo(timezone)).date()
        directions = tuple(self._source.direction_report()) if query.include_directions else ()
        return FeedInfo(
            feed=feed,
            validity=feed_validity_status(feed, today, self._warning_days),
            directions=directions,
        )
