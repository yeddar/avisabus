"""Periodic `sae.stats` log of the arrivals cache counters (sae_arrivals_source AC-13).

Started and cancelled with the application's lifespan (`avisabus.main`).
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Protocol

SAE_STATS_INTERVAL = timedelta(minutes=5)


class StatsEmitter(Protocol):
    def emit_stats(self) -> None: ...


async def run_sae_stats(
    emitter: StatsEmitter,
    interval: timedelta = SAE_STATS_INTERVAL,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Every `interval`, log the counters; runs until cancelled."""
    while True:
        await sleep(interval.total_seconds())
        emitter.emit_stats()
