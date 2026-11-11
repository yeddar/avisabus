"""In-memory fakes of the driver ports (driver_session)."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from avisabus.domain.errors import DepartureTakenError
from avisabus.domain.models.driver import DriverService, DriverSession, SessionCloseReason

STARTED_AT = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)


def session_of(
    number: int = 1, service: DriverService | None = None, **values: Any
) -> DriverSession:
    fields: dict[str, Any] = {
        "session_id": f"session-{number}",
        "token_hash": f"hash-{number}",
        "code_id": f"dc-{number:06d}",
        "started_at": STARTED_AT,
        "service": service,
        "position": None,
        "progress_m": None,
        "off_route": False,
        "last_fix_at": None,
        "last_seen_at": None,
    }
    return DriverSession(**{**fields, **values})


class InMemorySessions:
    def __init__(self, *sessions: DriverSession) -> None:
        self.rows = {session.session_id: session for session in sessions}

    def add(self, session: DriverSession) -> None:
        self.rows[session.session_id] = session

    def by_token_hash(self, token_hash: str) -> DriverSession | None:
        return next((s for s in self.rows.values() if s.token_hash == token_hash), None)

    def by_code(self, code_id: str) -> DriverSession | None:
        return next((s for s in self.rows.values() if s.code_id == code_id), None)

    def by_trip(self, trip_id: str, service_date: date) -> DriverSession | None:
        return next(
            (
                s
                for s in self.rows.values()
                if s.service is not None
                and (s.service.trip_id, s.service.service_date) == (trip_id, service_date)
            ),
            None,
        )

    def list_all(self) -> list[DriverSession]:
        return list(self.rows.values())

    def save(self, session: DriverSession) -> None:
        if session.service is not None:
            holder = self.by_trip(session.service.trip_id, session.service.service_date)
            if holder is not None and holder.session_id != session.session_id:
                raise DepartureTakenError()
        self.rows[session.session_id] = session

    def delete(self, session_id: str) -> bool:
        return self.rows.pop(session_id, None) is not None


@dataclass
class RecordingListener:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def service_selected(self, session: DriverSession, previous: DriverService | None) -> None:
        self.calls.append(("service_selected", session.session_id, previous))

    def position_updated(self, session: DriverSession) -> None:
        self.calls.append(("position_updated", session.session_id))

    def session_closed(self, session_id: str, reason: SessionCloseReason) -> None:
        self.calls.append(("session_closed", session_id, reason))


@dataclass
class RecordingLogger:
    """Records every event with its fields; the tests check what is (not) in them."""

    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def info(self, event: str, **fields: Any) -> None:
        self.events.append((event, fields))

    def error(self, event: str, **fields: Any) -> None:
        self.events.append((event, fields))

    def named(self, event: str) -> list[dict[str, Any]]:
        return [fields for name, fields in self.events if name == event]
