"""Daily warning about the expiry of the active GTFS feed (deployment_rpi AC-11, design §7).

`GtfsExpiryWatcher.tick()` logs `gtfs.feed_expiring` (with `days_left`) while the feed is within
`AVISABUS_GTFS_EXPIRY_WARNING_DAYS` of its `feed_end_date`, and `gtfs.feed_expired` once it has
passed; nothing while it is valid or when there is no feed (`/api/v1/health` reports that). The
task runs it when the application starts and then once a day, with `run_periodic`, so a failing
check only logs its exception type and the next one runs.
"""

import asyncio
from datetime import timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from avisabus.background.alert_tasks import Sleep, Tick, run_periodic
from avisabus.domain.models.network import FeedVersion
from avisabus.domain.ports.clock import Clock
from avisabus.domain.services.feed_validity import Expired, Expiring, feed_validity_status
from avisabus.logging import UNHANDLED_EXCEPTION

GTFS_EXPIRY_WATCHER = "gtfs.expiry_watcher"
EXPIRY_CHECK_INTERVAL = timedelta(days=1)
LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")
"""`days_left` counts days in València (design §7)."""


class Logger(Protocol):
    def warning(self, event: str, **fields: Any) -> Any: ...

    def error(self, event: str, **fields: Any) -> Any: ...


class ActiveFeed(Protocol):
    """The part of the `NetworkRepository` that the watcher reads."""

    def active_feed(self) -> FeedVersion | None: ...


class GtfsExpiryWatcher:
    def __init__(
        self, network: ActiveFeed, clock: Clock, warning_days: int, logger: Logger
    ) -> None:
        self._network = network
        self._clock = clock
        self._warning_days = warning_days
        self._logger = logger

    async def tick(self) -> None:
        feed = self._network.active_feed()
        if feed is None:
            return
        today = self._clock.now().astimezone(LOCAL_TIMEZONE).date()
        status = feed_validity_status(feed, today, self._warning_days)
        end_date = feed.end_date.isoformat()
        if isinstance(status, Expiring):
            self._logger.warning(
                "gtfs.feed_expiring", days_left=status.days_left, end_date=end_date
            )
        elif isinstance(status, Expired):
            self._logger.warning(
                "gtfs.feed_expired",
                days_left=-status.days_ago,
                days_ago=status.days_ago,
                end_date=end_date,
            )


async def _check_now_and_daily(tick: Tick, logger: Logger, sleep: Sleep) -> None:
    current = asyncio.current_task()
    task = "unknown" if current is None else current.get_name()
    try:
        await tick()
    except Exception as error:  # the daily checks must still run
        logger.error(UNHANDLED_EXCEPTION, error_type=type(error).__name__, task=task)
    await run_periodic(tick, EXPIRY_CHECK_INTERVAL, logger, sleep)


def start_gtfs_tasks(
    tick: Tick, logger: Logger, sleep: Sleep = asyncio.sleep
) -> list[asyncio.Task[None]]:
    """Start the `GtfsExpiryWatcher`: one check now, then one every day."""
    return [
        asyncio.create_task(_check_now_and_daily(tick, logger, sleep), name=GTFS_EXPIRY_WATCHER)
    ]
