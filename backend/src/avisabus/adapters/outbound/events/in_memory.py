"""In-memory publisher with one bounded queue per subscription (realtime_events design §3).

ADR-003: the backend is a single process, so events never leave it. Every call happens in the
event loop thread; `publish` is synchronous and never waits for a slow subscriber.
"""

import asyncio

from avisabus.domain.errors import SubscriptionOverflowError
from avisabus.domain.models.events import Event

DEFAULT_QUEUE_SIZE = 100


class _Subscription:
    def __init__(self, publisher: "InMemoryEventPublisher", channel: str, queue_size: int) -> None:
        self._publisher = publisher
        self._channel = channel
        # `None` is the wake-up sentinel queued after an overflow.
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=queue_size)
        self._overflowed = False

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    async def next_event(self) -> Event:
        if self._overflowed:
            raise SubscriptionOverflowError()
        event = await self._queue.get()
        if event is None:
            raise SubscriptionOverflowError()
        return event

    def close(self) -> None:
        self._publisher._remove(self._channel, self)

    def _offer(self, event: Event) -> None:
        if self._overflowed:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            # AC-02: stop queueing, drop what was queued and wake a waiting reader up.
            self._overflowed = True
            while not self._queue.empty():
                self._queue.get_nowait()
            self._queue.put_nowait(None)


class InMemoryEventPublisher:
    """Channels of subscriptions; each subscription keeps at most `queue_size` pending events."""

    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be at least 1")
        self._queue_size = queue_size
        self._channels: dict[str, set[_Subscription]] = {}

    def publish(self, channel: str, event: Event) -> None:
        # A copy: nothing here yields, but a subscriber set must never change while iterated.
        for subscription in tuple(self._channels.get(channel, ())):
            subscription._offer(event)

    def subscribe(self, channel: str) -> _Subscription:
        subscription = _Subscription(self, channel, self._queue_size)
        self._channels.setdefault(channel, set()).add(subscription)
        return subscription

    def subscriber_count(self, channel: str | None = None) -> int:
        if channel is not None:
            return len(self._channels.get(channel, ()))
        return sum(len(subscriptions) for subscriptions in self._channels.values())

    def _remove(self, channel: str, subscription: _Subscription) -> None:
        subscriptions = self._channels.get(channel)
        if subscriptions is None:
            return
        subscriptions.discard(subscription)
        if not subscriptions:
            del self._channels[channel]  # AC-03: no empty channels left behind
