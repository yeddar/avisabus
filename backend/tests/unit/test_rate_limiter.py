"""`InMemoryRateLimiter`: sliding window per key, with a `FakeClock` (alert_create T-02)."""

from datetime import UTC, datetime, timedelta

import pytest

from avisabus.adapters.outbound.rate_limit.in_memory import InMemoryRateLimiter
from tests.support.fake_clock import FakeClock

START = datetime(2026, 11, 4, 7, 40, tzinfo=UTC)
WINDOW = timedelta(minutes=10)


def _limiter(limit: int = 3) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(limit=limit, window=WINDOW)


@pytest.mark.spec("alert_create.AC-08")
def test_admits_up_to_the_limit_and_then_asks_to_retry() -> None:
    clock = FakeClock(START)
    limiter = _limiter()
    for _ in range(3):
        assert limiter.acquire("device:a", clock.now()) is None
        clock.advance(timedelta(minutes=1))
    # Now is START + 3 min. This rejected attempt counts too, so the next one is admitted when
    # the attempts at 0 and 1 min have left the window, at START + 11 min.
    assert limiter.acquire("device:a", clock.now()) == 8 * 60


@pytest.mark.spec("alert_create.AC-08")
def test_the_window_slides() -> None:
    clock = FakeClock(START)
    limiter = _limiter()
    for _ in range(3):  # at 0, 2 and 4 min
        assert limiter.acquire("k", clock.now()) is None
        clock.advance(timedelta(minutes=2))
    # At 10 min the attempt at 0 min has left the window (it lasts [t, t + 10 min)).
    clock.set(START + WINDOW)
    assert limiter.acquire("k", clock.now()) is None
    # Attempts at 2, 4, 10 and 10 min: room again when those at 2 and 4 min have left.
    assert limiter.acquire("k", clock.now()) == 4 * 60


@pytest.mark.spec("alert_create.AC-08")
def test_rejected_attempts_count_and_retry_after_waits_for_enough_room() -> None:
    clock = FakeClock(START)
    limiter = _limiter(limit=2)
    assert limiter.acquire("k", clock.now()) is None  # t = 0
    clock.advance(timedelta(minutes=1))
    assert limiter.acquire("k", clock.now()) is None  # t = 1 min
    clock.advance(timedelta(minutes=1))
    # t = 2 min: attempts at 0, 1 and 2 min; room again when 0 and 1 have left (11 min).
    assert limiter.acquire("k", clock.now()) == 9 * 60
    clock.advance(timedelta(minutes=1))
    # t = 3 min: attempts at 0, 1, 2 and 3 min; room again when 0, 1 and 2 have left (12 min).
    assert limiter.acquire("k", clock.now()) == 9 * 60
    clock.set(START + timedelta(minutes=12))
    assert limiter.acquire("k", clock.now()) is None


@pytest.mark.spec("alert_create.AC-08")
def test_retry_after_is_rounded_up_to_whole_seconds() -> None:
    clock = FakeClock(START)
    limiter = _limiter(limit=2)
    assert limiter.acquire("k", clock.now()) is None
    clock.advance(timedelta(seconds=0.4))
    assert limiter.acquire("k", clock.now()) is None
    clock.advance(timedelta(seconds=0.3))
    assert limiter.acquire("k", clock.now()) == 600  # 599.7 s: when the one at 0.4 s leaves


@pytest.mark.spec("alert_create.AC-08")
def test_keys_are_independent() -> None:
    clock = FakeClock(START)
    limiter = _limiter(limit=1)
    assert limiter.acquire("device:a", clock.now()) is None
    assert limiter.acquire("device:b", clock.now()) is None
    assert limiter.acquire("ip:192.0.2.1", clock.now()) is None
    assert limiter.acquire("device:a", clock.now()) is not None


@pytest.mark.spec("alert_create.AC-08")
def test_release_undoes_the_last_attempt() -> None:
    clock = FakeClock(START)
    limiter = _limiter(limit=2)
    assert limiter.acquire("k", clock.now()) is None
    for _ in range(5):  # requests answered with 200 (AC-07) do not count
        assert limiter.acquire("k", clock.now()) is None
        limiter.release("k", clock.now())
    assert limiter.acquire("k", clock.now()) is None
    assert limiter.acquire("k", clock.now()) is not None


@pytest.mark.spec("alert_create.AC-08")
def test_release_of_an_unknown_or_expired_key_does_nothing() -> None:
    clock = FakeClock(START)
    limiter = _limiter(limit=1)
    limiter.release("nobody", clock.now())
    assert limiter.acquire("k", clock.now()) is None
    clock.advance(WINDOW)
    limiter.release("k", clock.now())  # the attempt already left the window
    assert limiter.acquire("k", clock.now()) is None
    assert limiter.acquire("k", clock.now()) is not None


@pytest.mark.spec("alert_create.AC-08")
def test_expired_keys_are_forgotten() -> None:
    clock = FakeClock(START)
    limiter = _limiter()
    for n in range(50):
        limiter.acquire(f"device:{n}", clock.now())
    assert limiter.tracked_keys == 50
    clock.advance(WINDOW)
    limiter.acquire("device:new", clock.now())
    assert limiter.tracked_keys == 1


@pytest.mark.parametrize(
    ("limit", "window"), [(0, WINDOW), (1, timedelta(0)), (1, timedelta(seconds=-1))]
)
def test_rejects_an_invalid_configuration(limit: int, window: timedelta) -> None:
    with pytest.raises(ValueError, match="limit|window"):
        InMemoryRateLimiter(limit=limit, window=window)
