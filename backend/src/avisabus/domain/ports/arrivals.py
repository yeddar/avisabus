"""Real-time arrivals port (sae_arrivals_source design §3)."""

from typing import Protocol

from avisabus.domain.models.arrivals import ArrivalsSnapshot


class ArrivalsSource(Protocol):
    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        """Current arrivals of the stop; raises `ArrivalsUnavailableError` if unavailable."""
        ...
