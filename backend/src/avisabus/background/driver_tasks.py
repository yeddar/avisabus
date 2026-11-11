"""Background tasks of the shifts: the `DriverSessionReaper` (driver_session AC-13) and the refresh
of the driver views every 15 s (driver_demand AC-09). They are periodic loops started and cancelled
with the application's lifespan (`avisabus.main`), reusing `run_periodic`, so a failing cycle only
logs its exception type and the loop goes on."""

import asyncio
from datetime import timedelta

from avisabus.application.reap_driver_sessions import REAPER_TASK
from avisabus.background.alert_tasks import Logger, Sleep, Tick, run_periodic

DRIVER_SESSION_REAPER = REAPER_TASK
DEMAND_VIEW_REFRESHER = "demand.view_refresher"
VIEW_REFRESH_INTERVAL = timedelta(seconds=15)


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


def start_demand_tasks(
    refresh_tick: Tick,
    interval: timedelta,
    logger: Logger,
    sleep: Sleep = asyncio.sleep,
) -> list[asyncio.Task[None]]:
    return [
        asyncio.create_task(
            run_periodic(refresh_tick, interval, logger, sleep), name=DEMAND_VIEW_REFRESHER
        )
    ]
