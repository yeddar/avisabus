"""Closes the shifts that lost their driver (driver_session AC-13): no position for the idle
timeout, or a code that was revoked. Runs every minute (`background.driver_tasks`)."""

from datetime import datetime, timedelta
from typing import Any, Protocol

from avisabus.application.close_driver_session import CloseDriverSession
from avisabus.domain.models.driver import DriverSession, SessionCloseReason
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.driver import DriverCodeRepository, DriverSessionRepository

UNHANDLED_EXCEPTION = "unhandled_exception"
REAPER_TASK = "driver.session_reaper"


class Logger(Protocol):
    def error(self, event: str, **fields: Any) -> Any: ...


class ReapDriverSessions:
    def __init__(
        self,
        sessions: DriverSessionRepository,
        codes: DriverCodeRepository,
        close: CloseDriverSession,
        clock: Clock,
        idle_timeout: timedelta,
        logger: Logger,
    ) -> None:
        self._sessions = sessions
        self._codes = codes
        self._close = close
        self._clock = clock
        self._idle_timeout = idle_timeout
        self._log = logger

    async def tick(self) -> None:
        """One pass. A session that fails to close does not stop the others; only the type of its
        exception is logged."""
        now = self._clock.now()
        for session in self._sessions.list_all():
            try:
                reason = self._reason(session, now)
                if reason is not None:
                    await self._close.execute(session.session_id, reason)
            except Exception as error:  # the other sessions must be closed anyway
                self._log.error(
                    UNHANDLED_EXCEPTION, error_type=type(error).__name__, task=REAPER_TASK
                )

    def _reason(self, session: DriverSession, now: datetime) -> SessionCloseReason | None:
        code = self._codes.get(session.code_id)
        if code is None or code.revoked:
            return SessionCloseReason.REVOKED
        last_seen = session.last_position_at or session.started_at
        if now - last_seen >= self._idle_timeout:
            return SessionCloseReason.IDLE
        return None
