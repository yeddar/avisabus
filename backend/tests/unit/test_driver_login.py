"""Start of a shift and its login limiter (driver_session T-04)."""

import hashlib
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from avisabus.adapters.outbound.drivers.noop_session_listener import NoopDriverSessionListener
from avisabus.adapters.outbound.rate_limit.in_memory import InMemoryRateLimiter
from avisabus.application.close_driver_session import CloseDriverSession
from avisabus.application.driver_sessions import (
    LoginLimiter,
    StartDriverSession,
    StartDriverSessionCommand,
)
from avisabus.domain.errors import InvalidDriverCodeError, RateLimitedError
from avisabus.domain.models.driver import DriverCode, SessionCloseReason
from tests.support.drivers import InMemorySessions, RecordingListener, RecordingLogger, session_of
from tests.support.fake_clock import FakeClock

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
PLAIN = "48210937"
OTHER_PLAIN = "11112222"
IP = "203.0.113.7"
BLOCK = timedelta(minutes=15)
ACTIVE = DriverCode("dc-000001", f"hash-of-{PLAIN}", "Tablet 3", NOW, None)
REVOKED = DriverCode("dc-000002", f"hash-of-{OTHER_PLAIN}", "Tablet 4", NOW, NOW)


class FakeCodeHasher:
    def hash(self, code: str) -> str:
        return f"hash-of-{code}"


class FakeCodes:
    def __init__(self, *codes: DriverCode) -> None:
        self._codes = {code.code_hash: code for code in codes}
        self.lookups: list[str] = []

    def find_by_hash(self, code_hash: str) -> DriverCode | None:
        self.lookups.append(code_hash)
        return self._codes.get(code_hash)


class Harness:
    def __init__(self, *sessions: object) -> None:
        self.clock = FakeClock(NOW)
        self.sessions = InMemorySessions(*sessions)  # type: ignore[arg-type]
        self.listener = RecordingListener()
        self.logger = RecordingLogger()
        self.codes = FakeCodes(ACTIVE, REVOKED)
        close = CloseDriverSession(self.sessions, self.listener, self.clock, self.logger)
        self.use_case = StartDriverSession(
            codes=self.codes,
            code_hasher=FakeCodeHasher(),
            sessions=self.sessions,
            token_hasher=FakeTokenHasher(),
            close=close,
            limiter=_limiter(),
            clock=self.clock,
            idle_timeout=timedelta(minutes=10),
            logger=self.logger,
        )

    async def start(self, code: str = PLAIN, ip: str = IP):  # noqa: ANN201
        return await self.use_case.execute(StartDriverSessionCommand(code=code, client_ip=ip))


class FakeTokenHasher:
    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


def _limiter() -> LoginLimiter:
    return LoginLimiter(InMemoryRateLimiter(limit=4, window=BLOCK), block=BLOCK)


async def _fail(harness: Harness, times: int = 1, ip: str = IP) -> None:
    for _ in range(times):
        with pytest.raises(InvalidDriverCodeError):
            await harness.start("99990000", ip)


@pytest.mark.spec("driver_session.AC-01")
async def test_a_valid_code_starts_a_session() -> None:
    harness = Harness()
    result = await harness.start()
    assert result.idle_timeout_s == 600
    stored = harness.sessions.by_code(ACTIVE.code_id)
    assert stored is not None
    assert stored.session_id == result.session_id
    assert uuid.UUID(result.session_id).version == 4
    assert stored.started_at == NOW
    assert stored.service is None
    assert stored.position is None
    assert stored.progress_m is None
    assert stored.off_route is False
    assert stored.last_position_at is None


@pytest.mark.spec("driver_session.AC-01")
async def test_token_is_long_random_base64url_and_only_its_hash_is_stored() -> None:
    harness = Harness()
    first = await harness.start()
    second = await Harness().start()
    assert first.session_token != second.session_token
    assert len(first.session_token) >= 43  # 32 bytes in base64url without padding
    assert set(first.session_token) <= set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    )
    stored = harness.sessions.by_code(ACTIVE.code_id)
    assert stored is not None
    assert stored.token_hash == hashlib.sha256(first.session_token.encode()).hexdigest()
    assert first.session_token not in repr(stored)
    assert first.session_token not in repr(first)


@pytest.mark.spec("driver_session.AC-01")
@pytest.mark.parametrize("code", ["4821 0937", " 48210937 ", "4 8 2 1 0 9 3 7"])
async def test_spaces_in_the_code_are_ignored(code: str) -> None:
    result = await Harness().start(code)
    assert result.session_id


@pytest.mark.spec("driver_session.AC-02")
@pytest.mark.parametrize(
    "code",
    ["", "1234567", "123456789", "abcdefgh", "١٢٣٤٥٦٧٨", "1234567\t"],
)
async def test_a_malformed_code_fails_like_an_unknown_one(code: str) -> None:
    harness = Harness()
    with pytest.raises(InvalidDriverCodeError):
        await harness.start(code)
    assert harness.logger.named("driver.login_failed") == [{}]


@pytest.mark.spec("driver_session.AC-02")
async def test_unknown_and_revoked_codes_are_the_same_error() -> None:
    harness = Harness()
    with pytest.raises(InvalidDriverCodeError) as unknown:
        await harness.start("99990000")
    with pytest.raises(InvalidDriverCodeError) as revoked:
        await harness.start(OTHER_PLAIN)
    assert type(unknown.value) is type(revoked.value)
    assert str(unknown.value) == str(revoked.value)
    assert harness.sessions.list_all() == []


@pytest.mark.spec("driver_session.AC-02")
async def test_after_five_failures_any_attempt_is_rate_limited() -> None:
    harness = Harness()
    await _fail(harness, 5)
    with pytest.raises(RateLimitedError) as error:
        await harness.start(PLAIN)
    assert error.value.retry_after_s == 15 * 60
    assert harness.sessions.list_all() == []


@pytest.mark.spec("driver_session.AC-02")
async def test_the_fifth_failure_is_still_an_invalid_code() -> None:
    harness = Harness()
    await _fail(harness, 4)
    with pytest.raises(InvalidDriverCodeError):
        await harness.start("99990000")


@pytest.mark.spec("driver_session.AC-02")
async def test_four_failures_do_not_block() -> None:
    harness = Harness()
    await _fail(harness, 4)
    assert (await harness.start(PLAIN)).session_id


@pytest.mark.spec("driver_session.AC-02")
async def test_while_blocked_the_code_is_not_checked() -> None:
    harness = Harness()
    await _fail(harness, 5)
    lookups = len(harness.codes.lookups)
    with pytest.raises(RateLimitedError):
        await harness.start(PLAIN)
    assert len(harness.codes.lookups) == lookups


@pytest.mark.spec("driver_session.AC-02")
async def test_the_block_lasts_15_minutes_after_the_last_failure() -> None:
    harness = Harness()
    for _ in range(5):
        await _fail(harness)
        harness.clock.advance(timedelta(minutes=2))
    # Last failure at minute 8; the block ends at minute 23.
    harness.clock.set(NOW + timedelta(minutes=23) - timedelta(seconds=1))
    with pytest.raises(RateLimitedError) as error:
        await harness.start(PLAIN)
    assert error.value.retry_after_s == 1
    harness.clock.set(NOW + timedelta(minutes=23))
    assert (await harness.start(PLAIN)).session_id


@pytest.mark.spec("driver_session.AC-02")
async def test_blocked_attempts_do_not_extend_the_block() -> None:
    harness = Harness()
    await _fail(harness, 5)
    harness.clock.advance(timedelta(minutes=14))
    with pytest.raises(RateLimitedError):
        await harness.start("99990000")
    harness.clock.advance(timedelta(minutes=1))
    assert (await harness.start(PLAIN)).session_id


@pytest.mark.spec("driver_session.AC-02")
async def test_the_count_starts_again_after_the_block() -> None:
    harness = Harness()
    await _fail(harness, 5)
    harness.clock.advance(timedelta(minutes=15))
    await _fail(harness, 4)
    assert (await harness.start(PLAIN)).session_id


@pytest.mark.spec("driver_session.AC-02")
async def test_failures_older_than_the_window_do_not_count() -> None:
    harness = Harness()
    await _fail(harness, 4)
    harness.clock.advance(timedelta(minutes=15))
    await _fail(harness)
    assert (await harness.start(PLAIN)).session_id


@pytest.mark.spec("driver_session.AC-02")
async def test_a_success_does_not_reset_the_count() -> None:
    harness = Harness()
    await _fail(harness, 4)
    await harness.start(PLAIN)
    await _fail(harness, 1)
    with pytest.raises(RateLimitedError):
        await harness.start(PLAIN)


@pytest.mark.spec("driver_session.AC-02")
async def test_each_address_is_counted_on_its_own() -> None:
    harness = Harness()
    await _fail(harness, 5)
    assert (await harness.start(PLAIN, "198.51.100.1")).session_id


@pytest.mark.spec("driver_session.AC-02")
def test_expired_blocks_are_forgotten() -> None:
    limiter = _limiter()
    for _ in range(5):
        limiter.record_failure(IP, NOW)
    limiter.check("198.51.100.1", NOW + BLOCK)
    assert limiter.blocked_addresses == 0


@pytest.mark.spec("driver_session.AC-03")
async def test_a_second_login_replaces_the_open_shift() -> None:
    previous = replace(session_of(), code_id=ACTIVE.code_id)
    harness = Harness(previous)
    result = await harness.start()
    open_now = harness.sessions.list_all()
    assert [s.session_id for s in open_now] == [result.session_id]
    assert result.session_id != previous.session_id
    assert harness.listener.calls == [
        ("session_closed", previous.session_id, SessionCloseReason.REPLACED)
    ]
    assert harness.logger.named("driver.session_closed")[0]["reason"] == "REPLACED"


@pytest.mark.spec("driver_session.AC-15")
async def test_session_started_is_logged_with_the_session_only() -> None:
    harness = Harness()
    result = await harness.start()
    assert harness.logger.named("driver.session_started") == [{"session_id": result.session_id}]


@pytest.mark.spec("driver_session.AC-15")
async def test_failed_logins_are_logged_without_data() -> None:
    harness = Harness()
    await _fail(harness, 2)
    assert harness.logger.named("driver.login_failed") == [{}, {}]


@pytest.mark.spec("driver_session.AC-15")
async def test_nothing_of_the_code_token_or_address_reaches_the_log() -> None:
    harness = Harness()
    result = await harness.start("4821 0937")
    await _fail(harness)
    logged = repr(harness.logger.events)
    for secret in (PLAIN, "4821", "99990000", IP, result.session_token):
        assert secret not in logged


def test_noop_listener_satisfies_the_port() -> None:
    listener = NoopDriverSessionListener()
    session = session_of()
    assert listener.service_selected(session, None) is None
    assert listener.position_updated(session) is None
    assert listener.session_closed(session.session_id, SessionCloseReason.ENDED) is None
