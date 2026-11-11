"""Common effects of closing a shift (driver_session design §3), whatever the reason."""

from typing import Any, Protocol

from avisabus.domain.models.driver import SessionCloseReason
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.driver import DriverSessionListener, DriverSessionRepository

DRIVER_SESSION_CLOSED = "driver.session_closed"


class Logger(Protocol):
    def info(self, event: str, **fields: Any) -> Any: ...


class CloseDriverSession:
    def __init__(
        self,
        sessions: DriverSessionRepository,
        listener: DriverSessionListener,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._sessions = sessions
        self._listener = listener
        self._clock = clock
        self._log = logger

    async def execute(self, session_id: str, reason: SessionCloseReason) -> None:
        """Delete the session with its position and notify; idempotent."""
        session = next((s for s in self._sessions.list_all() if s.session_id == session_id), None)
        if session is None or not self._sessions.delete(session_id):
            return
        self._listener.session_closed(session_id, reason)
        self._log.info(
            DRIVER_SESSION_CLOSED,
            session_id=session_id,
            reason=reason.value,
            duration_s=int((self._clock.now() - session.started_at).total_seconds()),
        )
