"""`run_periodic` (the `PassageWatcher` and `AlertExpiryTicker` loops) and their configuration
(alert_expiry T-03). The `sleep` is fake: no time passes for real."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from avisabus.background.alert_tasks import (
    ALERT_EXPIRY_TICKER,
    PASSAGE_WATCHER,
    run_periodic,
    start_alert_tasks,
    stop_tasks,
)
from avisabus.config import Settings
from tests.support.alerts import RecordingLogger
from tests.support.ws import FakeSleep


class StopLoopError(Exception):
    """Raised by the fake `sleep` to end the loop after the scripted cycles."""


@dataclass
class CycleSleep:
    """Returns at once `cycles` times, then raises `StopLoopError` (outside the loop's `try`)."""

    cycles: int
    calls: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if len(self.calls) > self.cycles:
            raise StopLoopError


@dataclass
class Ticks:
    fail_on: set[int] = field(default_factory=set)
    count: int = 0

    async def __call__(self) -> None:
        self.count += 1
        if self.count in self.fail_on:
            raise RuntimeError(f"alert {self.count} of device 3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b")


async def run_named(
    name: str,
    tick: Callable[[], Awaitable[None]],
    interval: timedelta,
    logger: Any,
    sleep: CycleSleep,
) -> None:
    task = asyncio.create_task(run_periodic(tick, interval, logger, sleep), name=name)
    with pytest.raises(StopLoopError):
        await task


@pytest.mark.spec("alert_expiry.AC-10")
async def test_each_cycle_sleeps_the_interval_and_then_ticks() -> None:
    ticks, sleep = Ticks(), CycleSleep(cycles=3)
    await run_named(PASSAGE_WATCHER, ticks, timedelta(seconds=15), RecordingLogger(), sleep)
    assert ticks.count == 3
    assert sleep.calls == [15.0, 15.0, 15.0, 15.0]


@pytest.mark.spec("alert_expiry.AC-10")
async def test_a_failing_cycle_is_logged_by_type_and_the_next_one_runs() -> None:
    ticks, sleep, logger = Ticks(fail_on={1, 3}), CycleSleep(cycles=4), RecordingLogger()
    await run_named(ALERT_EXPIRY_TICKER, ticks, timedelta(seconds=10), logger, sleep)
    assert ticks.count == 4
    assert logger.events == [
        (
            "error",
            "unhandled_exception",
            {"error_type": "RuntimeError", "task": ALERT_EXPIRY_TICKER},
        ),
        (
            "error",
            "unhandled_exception",
            {"error_type": "RuntimeError", "task": ALERT_EXPIRY_TICKER},
        ),
    ]
    assert "3f2b8c1e" not in repr(logger.events)  # never the exception's message


@pytest.mark.spec("alert_expiry.AC-10")
async def test_cancelling_stops_the_loop() -> None:
    started = asyncio.Event()

    async def tick() -> None:
        started.set()

    async def no_wait(seconds: float) -> None:
        await asyncio.sleep(0)

    task = asyncio.create_task(
        run_periodic(tick, timedelta(seconds=15), RecordingLogger(), no_wait)
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.spec("alert_expiry.AC-10")
async def test_both_tasks_start_with_their_names_and_intervals_and_stop() -> None:
    sleep = FakeSleep({15.0: 1, 10.0: 1})  # one cycle each, then asleep until cancelled
    ticked: list[str] = []

    async def watch() -> None:
        ticked.append("watch")

    async def expire() -> None:
        ticked.append("expire")

    tasks = start_alert_tasks(
        watch_tick=watch,
        expiry_tick=expire,
        watch_interval=timedelta(seconds=15),
        expiry_interval=timedelta(seconds=10),
        logger=RecordingLogger(),
        sleep=sleep,
    )
    for _ in range(10):
        await asyncio.sleep(0)
    assert [task.get_name() for task in tasks] == [PASSAGE_WATCHER, ALERT_EXPIRY_TICKER]
    assert sorted(sleep.calls) == [10.0, 10.0, 15.0, 15.0]
    assert sorted(ticked) == ["expire", "watch"]
    await stop_tasks(tasks)
    assert all(task.cancelled() for task in tasks)
    await stop_tasks(tasks)  # idempotent


# --- Configuration ---


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, env="test", **values)  # type: ignore[call-arg]


@pytest.mark.spec("alert_expiry.AC-10")
def test_default_intervals_window_and_margin() -> None:
    defaults = settings()
    assert (
        defaults.passage_watch_interval_s,
        defaults.alert_expiry_interval_s,
        defaults.passage_window_min,
        defaults.next_stop_margin_min,
    ) == (15, 10, 2, 2)


@pytest.mark.spec("alert_expiry.AC-10")
def test_the_values_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVISABUS_PASSAGE_WATCH_INTERVAL_S", "20")
    monkeypatch.setenv("AVISABUS_ALERT_EXPIRY_INTERVAL_S", "5")
    monkeypatch.setenv("AVISABUS_PASSAGE_WINDOW_MIN", "1.5")
    monkeypatch.setenv("AVISABUS_NEXT_STOP_MARGIN_MIN", "0")
    read = settings()
    assert (
        read.passage_watch_interval_s,
        read.alert_expiry_interval_s,
        read.passage_window_min,
        read.next_stop_margin_min,
    ) == (20, 5, 1.5, 0)


@pytest.mark.spec("alert_expiry.AC-10")
@pytest.mark.parametrize(
    "values",
    [
        {"passage_watch_interval_s": 0},
        {"alert_expiry_interval_s": -1},
        {"passage_window_min": 0},
        {"next_stop_margin_min": -1},
    ],
)
def test_invalid_values_are_rejected(values: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        settings(**values)
