"""`ReapDriverSessions` and its background task (driver_session T-06). No time passes for real."""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from avisabus.application.close_driver_session import CloseDriverSession
from avisabus.application.reap_driver_sessions import ReapDriverSessions
from avisabus.background.alert_tasks import stop_tasks
from avisabus.background.driver_tasks import DRIVER_SESSION_REAPER, start_driver_tasks
from avisabus.config import Settings
from avisabus.domain.models.driver import DriverCode, SessionCloseReason
from tests.support.drivers import (
    STARTED_AT,
    InMemorySessions,
    RecordingListener,
    RecordingLogger,
    session_of,
)
from tests.support.fake_clock import FakeClock

IDLE = timedelta(minutes=10)
NOW = STARTED_AT + timedelta(minutes=30)
FAILURE_TEXT = "session of device 3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"


class FakeCodes:
    def __init__(self, revoked: set[str] | None = None, unknown: set[str] | None = None) -> None:
        self._revoked = revoked or set()
        self._unknown = unknown or set()

    def get(self, code_id: str) -> DriverCode | None:
        if code_id in self._unknown:
            return None
        return DriverCode(
            code_id=code_id,
            code_hash="h",
            label="L",
            created_at=STARTED_AT,
            revoked_at=STARTED_AT if code_id in self._revoked else None,
        )


class Harness:
    def __init__(self, *sessions: Any, codes: FakeCodes | None = None) -> None:
        self.clock = FakeClock(NOW)
        self.sessions = InMemorySessions(*sessions)
        self.listener = RecordingListener()
        self.logger = RecordingLogger()
        self.close = CloseDriverSession(self.sessions, self.listener, self.clock, self.logger)
        self.reap = ReapDriverSessions(
            self.sessions, codes or FakeCodes(), self.close, self.clock, IDLE, self.logger
        )

    def open_ids(self) -> set[str]:
        return {session.session_id for session in self.sessions.list_all()}


def _session(number: int, last_seen_ago: timedelta | None = None, **values: Any) -> Any:
    """A shift whose last sign of life (any valid `PUT …/position`, v1.3) was `last_seen_ago`."""
    last = None if last_seen_ago is None else NOW - last_seen_ago
    return session_of(number, last_seen_at=last, **values)


@pytest.mark.spec("driver_session.AC-13")
async def test_a_session_silent_for_10_minutes_is_closed_as_idle() -> None:
    harness = Harness(_session(1, timedelta(minutes=10)))
    await harness.reap.tick()
    assert harness.open_ids() == set()
    assert harness.listener.calls == [("session_closed", "session-1", SessionCloseReason.IDLE)]


@pytest.mark.spec("driver_session.AC-13")
async def test_a_session_with_a_recent_sign_of_life_stays_open() -> None:
    harness = Harness(_session(1, timedelta(minutes=9, seconds=59)))
    await harness.reap.tick()
    assert harness.open_ids() == {"session-1"}
    assert harness.listener.calls == []


@pytest.mark.spec("driver_session.AC-13")
async def test_a_resent_position_keeps_the_shift_alive_without_a_new_fix() -> None:
    harness = Harness(_session(1, timedelta(seconds=5), last_fix_at=NOW - timedelta(minutes=20)))
    await harness.reap.tick()
    assert harness.open_ids() == {"session-1"}


@pytest.mark.spec("driver_session.AC-13")
async def test_without_any_position_the_idle_time_counts_from_the_start() -> None:
    harness = Harness(_session(1, started_at=NOW - timedelta(minutes=10)))
    await harness.reap.tick()
    assert harness.open_ids() == set()


@pytest.mark.spec("driver_session.AC-13")
async def test_a_new_session_without_position_stays_open() -> None:
    harness = Harness(_session(1, started_at=NOW - timedelta(minutes=9, seconds=59)))
    await harness.reap.tick()
    assert harness.open_ids() == {"session-1"}


@pytest.mark.spec("driver_session.AC-13")
async def test_the_session_of_a_revoked_code_is_closed_as_revoked() -> None:
    session = _session(1, timedelta(seconds=1))
    harness = Harness(session, codes=FakeCodes(revoked={session.code_id}))
    await harness.reap.tick()
    assert harness.open_ids() == set()
    assert harness.listener.calls == [("session_closed", "session-1", SessionCloseReason.REVOKED)]


@pytest.mark.spec("driver_session.AC-13")
async def test_revoked_wins_over_idle() -> None:
    session = _session(1, timedelta(hours=1))
    harness = Harness(session, codes=FakeCodes(revoked={session.code_id}))
    await harness.reap.tick()
    assert harness.listener.calls == [("session_closed", "session-1", SessionCloseReason.REVOKED)]


@pytest.mark.spec("driver_session.AC-13")
async def test_a_session_whose_code_no_longer_exists_is_closed_as_revoked() -> None:
    session = _session(1, timedelta(seconds=1))
    harness = Harness(session, codes=FakeCodes(unknown={session.code_id}))
    await harness.reap.tick()
    assert harness.listener.calls == [("session_closed", "session-1", SessionCloseReason.REVOKED)]


@pytest.mark.spec("driver_session.AC-13")
async def test_only_the_affected_sessions_are_closed() -> None:
    idle = _session(1, timedelta(minutes=11))
    alive = _session(2, timedelta(minutes=1))
    harness = Harness(idle, alive)
    await harness.reap.tick()
    assert harness.open_ids() == {"session-2"}


@pytest.mark.spec("driver_session.AC-13")
async def test_closing_has_the_common_effects() -> None:
    harness = Harness(_session(1, timedelta(minutes=10)))
    await harness.reap.tick()
    assert harness.logger.named("driver.session_closed") == [
        {"session_id": "session-1", "reason": "IDLE", "duration_s": 1800}
    ]


@pytest.mark.spec("driver_session.AC-13")
async def test_a_failure_with_one_session_does_not_stop_the_others() -> None:
    class Flaky(InMemorySessions):
        def delete(self, session_id: str) -> bool:
            if session_id == "session-1":
                raise RuntimeError(FAILURE_TEXT)
            return super().delete(session_id)

    harness = Harness()
    harness.sessions = Flaky(_session(1, timedelta(minutes=11)), _session(2, timedelta(minutes=11)))
    harness.reap = ReapDriverSessions(
        harness.sessions,
        FakeCodes(),
        CloseDriverSession(harness.sessions, harness.listener, harness.clock, harness.logger),
        harness.clock,
        IDLE,
        harness.logger,
    )

    await harness.reap.tick()

    assert harness.open_ids() == {"session-1"}
    errors = harness.logger.named("unhandled_exception")
    assert errors == [{"error_type": "RuntimeError", "task": DRIVER_SESSION_REAPER}]
    assert FAILURE_TEXT not in repr(harness.logger.events)


@dataclass
class ScriptedSleep:
    """Returns at once `cycles` times, then waits forever until cancelled."""

    cycles: int
    calls: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if len(self.calls) > self.cycles:
            await asyncio.Event().wait()


async def _settle(sleep: ScriptedSleep, expected_calls: int) -> None:
    for _ in range(100):
        if len(sleep.calls) >= expected_calls:
            return
        await asyncio.sleep(0)
    pytest.fail("the background task did not run its cycles")


@pytest.mark.spec("driver_session.AC-13")
async def test_the_task_reaps_periodically_with_the_configured_interval() -> None:
    harness = Harness(_session(1, timedelta(minutes=11)))
    sleep = ScriptedSleep(cycles=2)
    tasks = start_driver_tasks(
        harness.reap.tick, timedelta(seconds=60), harness.logger, sleep=sleep
    )
    await _settle(sleep, 3)
    await stop_tasks(tasks)
    assert sleep.calls == [60.0, 60.0, 60.0]
    assert harness.open_ids() == set()
    assert [task.get_name() for task in tasks] == [DRIVER_SESSION_REAPER]


@pytest.mark.spec("driver_session.AC-13")
async def test_the_task_goes_on_after_an_exception_logging_only_its_type() -> None:
    harness = Harness()
    ticks: list[int] = []

    async def failing_tick() -> None:
        ticks.append(len(ticks))
        if len(ticks) == 1:
            raise RuntimeError(FAILURE_TEXT)

    sleep = ScriptedSleep(cycles=2)
    tasks = start_driver_tasks(failing_tick, timedelta(seconds=60), harness.logger, sleep=sleep)
    await _settle(sleep, 3)
    await stop_tasks(tasks)
    assert len(ticks) == 2
    assert harness.logger.named("unhandled_exception") == [
        {"error_type": "RuntimeError", "task": DRIVER_SESSION_REAPER}
    ]
    assert FAILURE_TEXT not in repr(harness.logger.events)


@pytest.mark.spec("driver_session.AC-13")
def test_interval_and_timeout_settings() -> None:
    settings = Settings(_env_file=None, env="test")  # type: ignore[call-arg]
    assert settings.driver_reaper_interval_s == 60
    assert settings.driver_idle_timeout_min == 10
    assert settings.driver_gps_stale_s == 30
    assert settings.driver_login_max_failures == 5
    assert settings.driver_login_block_min == 15


@pytest.mark.spec("driver_session.AC-13")
@pytest.mark.parametrize(
    "values",
    [
        {"driver_reaper_interval_s": 0},
        {"driver_idle_timeout_min": 0},
        {"driver_gps_stale_s": 0},
        {"driver_login_max_failures": 1},
        {"driver_login_block_min": 0},
    ],
)
def test_invalid_settings_are_rejected(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="test", **values)  # type: ignore[call-arg]
