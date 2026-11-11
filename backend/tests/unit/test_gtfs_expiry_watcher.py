"""`GtfsExpiryWatcher` and its daily task (deployment_rpi AC-11). The clock is a `FakeClock` and
the `sleep` is fake: no time passes for real."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.background.alert_tasks import stop_tasks
from avisabus.background.gtfs_tasks import (
    EXPIRY_CHECK_INTERVAL,
    GTFS_EXPIRY_WATCHER,
    GtfsExpiryWatcher,
    start_gtfs_tasks,
)
from avisabus.domain.models.network import FeedVersion
from tests.support.alerts import RecordingLogger
from tests.support.fake_clock import FakeClock

END = date(2026, 11, 22)
NOON = datetime(2026, 11, 11, 11, 0, tzinfo=UTC)  # 12:00 in Madrid


def _feed(end: date = END) -> FeedVersion:
    return FeedVersion(
        version_id=1,
        feed_version="23-10-2026",
        imported_at=datetime(2026, 10, 31, 8, 0, tzinfo=UTC),
        start_date=date(2026, 10, 16),
        end_date=end,
        counts={},
    )


@dataclass
class OneFeed:
    feed: FeedVersion | None

    def active_feed(self) -> FeedVersion | None:
        return self.feed


def _watcher(
    now: datetime, feed: FeedVersion | None = None, warning_days: int = 7
) -> tuple[GtfsExpiryWatcher, RecordingLogger]:
    logger = RecordingLogger()
    watcher = GtfsExpiryWatcher(
        network=OneFeed(feed if feed is not None else _feed()),
        clock=FakeClock(now),
        warning_days=warning_days,
        logger=logger,
    )
    return watcher, logger


def _at_days_left(days_left: int) -> datetime:
    return datetime.combine(END - timedelta(days=days_left), NOON.timetz())


@pytest.mark.spec("deployment_rpi.AC-11")
@pytest.mark.parametrize("days_left", [7, 3, 1, 0])
async def test_logs_feed_expiring_while_within_the_warning_days(days_left: int) -> None:
    watcher, logger = _watcher(_at_days_left(days_left))
    await watcher.tick()
    assert logger.events == [
        ("warning", "gtfs.feed_expiring", {"days_left": days_left, "end_date": "2026-11-22"})
    ]


@pytest.mark.spec("deployment_rpi.AC-11")
@pytest.mark.parametrize("days_left", [8, 11, 30])
async def test_logs_nothing_while_the_feed_is_valid(days_left: int) -> None:
    watcher, logger = _watcher(_at_days_left(days_left))
    await watcher.tick()
    assert logger.events == []


@pytest.mark.spec("deployment_rpi.AC-11")
async def test_the_warning_days_come_from_the_configuration() -> None:
    watcher, logger = _watcher(_at_days_left(11), warning_days=11)
    await watcher.tick()
    assert logger.named("gtfs.feed_expiring") == [{"days_left": 11, "end_date": "2026-11-22"}]


@pytest.mark.spec("deployment_rpi.AC-11")
@pytest.mark.parametrize("days_ago", [1, 5])
async def test_logs_feed_expired_once_it_has_expired(days_ago: int) -> None:
    watcher, logger = _watcher(_at_days_left(-days_ago))
    await watcher.tick()
    assert logger.events == [
        (
            "warning",
            "gtfs.feed_expired",
            {"days_left": -days_ago, "days_ago": days_ago, "end_date": "2026-11-22"},
        )
    ]


@pytest.mark.spec("deployment_rpi.AC-11")
async def test_today_is_the_date_in_madrid() -> None:
    # 2026-11-21 23:30 UTC is already 2026-11-22 00:30 in Madrid: the last valid day.
    watcher, logger = _watcher(datetime(2026, 11, 21, 23, 30, tzinfo=UTC))
    await watcher.tick()
    assert logger.named("gtfs.feed_expiring") == [{"days_left": 0, "end_date": "2026-11-22"}]
    # 2026-11-22 23:30 UTC is 2026-11-23 in Madrid: expired.
    watcher, logger = _watcher(datetime(2026, 11, 22, 23, 30, tzinfo=UTC))
    await watcher.tick()
    assert [name for _, name, _ in logger.events] == ["gtfs.feed_expired"]


@pytest.mark.spec("deployment_rpi.AC-11")
async def test_logs_nothing_without_a_feed() -> None:
    logger = RecordingLogger()
    watcher = GtfsExpiryWatcher(OneFeed(None), FakeClock(NOON), 7, logger)
    await watcher.tick()
    assert logger.events == []


class StopLoopError(Exception):
    """Raised by the fake `sleep` to end the loop after the scripted days."""


@dataclass
class Days:
    """Fake `sleep`: each call is one day of the `FakeClock`; after `days`, the loop ends."""

    clock: FakeClock
    days: int
    calls: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if len(self.calls) > self.days:
            raise StopLoopError
        self.clock.advance(timedelta(seconds=seconds))


@pytest.mark.spec("deployment_rpi.AC-11")
async def test_the_task_checks_at_start_and_then_once_a_day() -> None:
    clock = FakeClock(_at_days_left(9))
    logger = RecordingLogger()
    watcher = GtfsExpiryWatcher(OneFeed(_feed()), clock, 7, logger)
    sleep = Days(clock, days=11)

    (task,) = start_gtfs_tasks(watcher.tick, logger, sleep)
    assert task.get_name() == GTFS_EXPIRY_WATCHER
    with pytest.raises(StopLoopError):
        await task

    assert sleep.calls == [EXPIRY_CHECK_INTERVAL.total_seconds()] * 12 == [86400.0] * 12
    # Days left at start and after each of the 11 days: 9, 8, 7, …, 0, -1, -2.
    assert [f["days_left"] for f in logger.named("gtfs.feed_expiring")] == [7, 6, 5, 4, 3, 2, 1, 0]
    assert [f["days_ago"] for f in logger.named("gtfs.feed_expired")] == [1, 2]


@pytest.mark.spec("deployment_rpi.AC-11")
async def test_a_failing_check_is_logged_by_type_and_the_task_goes_on() -> None:
    clock = FakeClock(_at_days_left(1))
    logger = RecordingLogger()
    watcher = GtfsExpiryWatcher(OneFeed(_feed()), clock, 7, logger)
    calls = 0

    async def flaky() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("database is locked")
        await watcher.tick()

    sleep = Days(clock, days=1)
    (task,) = start_gtfs_tasks(flaky, logger, sleep)
    with pytest.raises(StopLoopError):
        await task

    assert logger.events[0] == (
        "error",
        "unhandled_exception",
        {"error_type": "RuntimeError", "task": GTFS_EXPIRY_WATCHER},
    )
    assert logger.named("gtfs.feed_expiring") == [{"days_left": 0, "end_date": "2026-11-22"}]


@pytest.mark.spec("deployment_rpi.AC-11")
async def test_the_task_stops_when_cancelled() -> None:
    logger = RecordingLogger()
    watcher = GtfsExpiryWatcher(OneFeed(_feed()), FakeClock(NOON), 7, logger)

    async def never(_seconds: float) -> None:
        await asyncio.Event().wait()

    tasks = start_gtfs_tasks(watcher.tick, logger, never)
    await asyncio.sleep(0)
    await stop_tasks(tasks)
    assert all(task.cancelled() for task in tasks)
