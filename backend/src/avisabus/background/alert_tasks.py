"""Background tasks of the alert expiry (alert_expiry design §3, AC-10).

`PassageWatcher` (`WatchPassages.tick`, every 15 s) and `AlertExpiryTicker`
(`ExpireDueAlerts.tick`, every 10 s) are periodic loops started and cancelled with the
application's lifespan (`avisabus.main`). A failing cycle is logged as `unhandled_exception`
with only its type and the task name (never its message: it may carry an identifier, H-01) and
the loop goes on with the next cycle. Time only passes through the injected `sleep`; the ticks
read the injected `Clock`.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from contextlib import suppress
from datetime import timedelta
from typing import Any, Protocol

from avisabus.logging import UNHANDLED_EXCEPTION

PASSAGE_WATCHER = "alerts.passage_watcher"
ALERT_EXPIRY_TICKER = "alerts.expiry_ticker"

Sleep = Callable[[float], Awaitable[None]]
Tick = Callable[[], Awaitable[None]]


class Logger(Protocol):
    def error(self, event: str, **fields: Any) -> Any: ...


async def run_periodic(
    tick: Tick,
    interval: timedelta,
    logger: Logger,
    sleep: Sleep = asyncio.sleep,
) -> None:
    """Every `interval`, run `tick`; runs until cancelled. The `task` of the log is the name of
    the asyncio task running the loop."""
    current = asyncio.current_task()
    task = "unknown" if current is None else current.get_name()
    while True:
        await sleep(interval.total_seconds())
        try:
            await tick()
        except Exception as error:  # the next cycle must run (AC-10)
            logger.error(UNHANDLED_EXCEPTION, error_type=type(error).__name__, task=task)


def start_alert_tasks(
    watch_tick: Tick,
    expiry_tick: Tick,
    watch_interval: timedelta,
    expiry_interval: timedelta,
    logger: Logger,
    sleep: Sleep = asyncio.sleep,
) -> list[asyncio.Task[None]]:
    """Start the `PassageWatcher` and the `AlertExpiryTicker`, in this order."""
    return [
        asyncio.create_task(
            run_periodic(watch_tick, watch_interval, logger, sleep), name=PASSAGE_WATCHER
        ),
        asyncio.create_task(
            run_periodic(expiry_tick, expiry_interval, logger, sleep), name=ALERT_EXPIRY_TICKER
        ),
    ]


async def stop_tasks(tasks: Iterable[asyncio.Task[None]]) -> None:
    """Cancel the tasks and wait until they have finished. Idempotent."""
    pending = list(tasks)
    for task in pending:
        task.cancel()
    for task in pending:
        with suppress(asyncio.CancelledError):
            await task
