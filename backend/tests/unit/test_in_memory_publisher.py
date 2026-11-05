"""In-memory event publisher with bounded queues (realtime_events T-02)."""

import asyncio

import pytest

from avisabus.adapters.outbound.events.in_memory import InMemoryEventPublisher
from avisabus.domain.errors import SubscriptionOverflowError
from avisabus.domain.models.events import Event
from avisabus.domain.ports.events import EventPublisher, Subscription


def _event(n: int) -> Event:
    return Event(type="test.event", payload={"n": n})


async def _drain(subscription: Subscription, count: int) -> list[Event]:
    return [await subscription.next_event() for _ in range(count)]


async def _is_waiting(subscription: Subscription) -> bool:
    """True when `next_event` waits (nothing queued for it)."""
    task = asyncio.ensure_future(subscription.next_event())
    for _ in range(3):
        await asyncio.sleep(0)
    waiting = not task.done()
    task.cancel()
    return waiting


def test_implements_the_port() -> None:
    publisher: EventPublisher = InMemoryEventPublisher()
    subscription: Subscription = publisher.subscribe("device:a")
    assert subscription.overflowed is False


@pytest.mark.spec("realtime_events.AC-01")
async def test_delivers_to_every_subscription_of_the_channel_in_order() -> None:
    publisher = InMemoryEventPublisher()
    first, second = publisher.subscribe("device:a"), publisher.subscribe("device:a")
    for n in range(5):
        publisher.publish("device:a", _event(n))
    assert await _drain(first, 5) == [_event(n) for n in range(5)]
    assert await _drain(second, 5) == [_event(n) for n in range(5)]


@pytest.mark.spec("realtime_events.AC-01")
async def test_does_not_deliver_to_other_channels() -> None:
    publisher = InMemoryEventPublisher()
    mine, other = publisher.subscribe("device:a"), publisher.subscribe("device:b")
    publisher.publish("device:a", _event(1))
    publisher.publish("device:b", _event(2))
    assert await mine.next_event() == _event(1)
    assert await other.next_event() == _event(2)
    assert await _is_waiting(mine)
    assert await _is_waiting(other)


@pytest.mark.spec("realtime_events.AC-01")
async def test_a_waiting_reader_is_woken_by_a_publication() -> None:
    publisher = InMemoryEventPublisher()
    subscription = publisher.subscribe("device:a")
    reader = asyncio.ensure_future(subscription.next_event())
    await asyncio.sleep(0)
    assert not reader.done()
    publisher.publish("device:a", _event(7))
    assert await reader == _event(7)


@pytest.mark.spec("realtime_events.AC-01")
def test_publishing_to_a_channel_without_subscriptions_does_nothing() -> None:
    publisher = InMemoryEventPublisher()
    publisher.publish("device:nobody", _event(1))
    assert publisher.subscriber_count() == 0


@pytest.mark.spec("realtime_events.AC-02")
async def test_default_capacity_is_100_events() -> None:
    publisher = InMemoryEventPublisher()
    subscription = publisher.subscribe("device:a")
    for n in range(99):
        publisher.publish("device:a", _event(n))
    assert subscription.overflowed is False
    publisher.publish("device:a", _event(99))
    assert subscription.overflowed is False  # 100 queued: full but not overflowed yet
    assert await _drain(subscription, 100) == [_event(n) for n in range(100)]
    for n in range(101):
        publisher.publish("device:a", _event(n))
    assert subscription.overflowed is True


@pytest.mark.spec("realtime_events.AC-02")
async def test_a_full_queue_overflows_without_blocking_nor_affecting_the_others() -> None:
    publisher = InMemoryEventPublisher(queue_size=3)
    slow, fast = publisher.subscribe("device:a"), publisher.subscribe("device:a")
    for n in range(3):
        publisher.publish("device:a", _event(n))
    assert await _drain(fast, 3) == [_event(n) for n in range(3)]

    publisher.publish("device:a", _event(3))  # `slow` is full: synchronous call, no waiting
    assert slow.overflowed is True
    assert fast.overflowed is False
    assert await fast.next_event() == _event(3)

    publisher.publish("device:a", _event(4))  # no longer queued to `slow`
    assert await fast.next_event() == _event(4)
    with pytest.raises(SubscriptionOverflowError):
        await slow.next_event()
    with pytest.raises(SubscriptionOverflowError):
        await slow.next_event()


@pytest.mark.spec("realtime_events.AC-02")
async def test_an_overflow_wakes_a_waiting_reader_with_the_error() -> None:
    publisher = InMemoryEventPublisher(queue_size=1)
    subscription = publisher.subscribe("device:a")
    publisher.publish("device:a", _event(0))
    assert await subscription.next_event() == _event(0)
    reader = asyncio.ensure_future(subscription.next_event())
    await asyncio.sleep(0)
    # Both publications happen before the reader runs again: the second one overflows.
    publisher.publish("device:a", _event(1))
    publisher.publish("device:a", _event(2))
    assert subscription.overflowed is True
    with pytest.raises(SubscriptionOverflowError):
        await reader


@pytest.mark.spec("realtime_events.AC-02")
async def test_overflowed_events_are_discarded() -> None:
    publisher = InMemoryEventPublisher(queue_size=2)
    subscription = publisher.subscribe("device:a")
    for n in range(3):
        publisher.publish("device:a", _event(n))
    # The queued events are dropped: the reader goes straight to the error.
    with pytest.raises(SubscriptionOverflowError):
        await subscription.next_event()


@pytest.mark.spec("realtime_events.AC-03")
def test_closing_removes_the_subscription() -> None:
    publisher = InMemoryEventPublisher()
    first, second = publisher.subscribe("device:a"), publisher.subscribe("device:b")
    third = publisher.subscribe("device:b")
    assert publisher.subscriber_count() == 3
    assert publisher.subscriber_count("device:b") == 2
    first.close()
    assert publisher.subscriber_count("device:a") == 0
    assert publisher.subscriber_count() == 2
    second.close()
    second.close()  # idempotent
    third.close()
    assert publisher.subscriber_count() == 0
    assert publisher.subscriber_count("device:b") == 0


@pytest.mark.spec("realtime_events.AC-03")
async def test_a_closed_subscription_receives_nothing_more() -> None:
    publisher = InMemoryEventPublisher()
    closed, open_ = publisher.subscribe("device:a"), publisher.subscribe("device:a")
    closed.close()
    publisher.publish("device:a", _event(1))
    assert await open_.next_event() == _event(1)
    assert await _is_waiting(closed)


@pytest.mark.spec("realtime_events.AC-03")
async def test_an_overflowed_subscription_is_removed_when_closed() -> None:
    publisher = InMemoryEventPublisher(queue_size=1)
    subscription = publisher.subscribe("device:a")
    publisher.publish("device:a", _event(0))
    publisher.publish("device:a", _event(1))
    assert subscription.overflowed is True
    subscription.close()
    assert publisher.subscriber_count() == 0


@pytest.mark.parametrize("queue_size", [0, -1])
def test_queue_size_must_be_positive(queue_size: int) -> None:
    with pytest.raises(ValueError, match="queue_size"):
        InMemoryEventPublisher(queue_size=queue_size)
