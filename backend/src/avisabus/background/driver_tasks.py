"""Background task of the shifts (driver_session AC-13): the `DriverSessionReaper` is a periodic
loop started and cancelled with the application's lifespan (`avisabus.main`), reusing
`run_periodic`, so a failing cycle only logs its exception type and the loop goes on."""

import asyncio
from datetime import timedelta

from avisabus.application.reap_driver_sessions import REAPER_TASK
from avisabus.background.alert_tasks import Logger, Sleep, Tick, run_periodic

DRIVER_SESSION_REAPER = REAPER_TASK


def start_driver_tasks(
    reap_tick: Tick,
    interval: timedelta,
    logger: Logger,
    sleep: Sleep = asyncio.sleep,
) -> list[asyncio.Task[None]]:
    return [
        asyncio.create_task(
            run_periodic(reap_tick, interval, logger, sleep), name=DRIVER_SESSION_REAPER
        )
    ]
