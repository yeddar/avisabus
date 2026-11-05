"""Publish/subscribe of real-time events by channel (realtime_events design §3, ADR-003)."""

from typing import Protocol

from avisabus.domain.models.events import Event


class Subscription(Protocol):
    @property
    def overflowed(self) -> bool:
        """True once its queue filled up: it no longer receives events (AC-02)."""
        ...

    async def next_event(self) -> Event:
        """Wait for the next event, in publication order. Raises `SubscriptionOverflowError` once
        the subscription has overflowed."""
        ...

    def close(self) -> None:
        """Remove the subscription from its publisher. Idempotent (AC-03)."""
        ...


class EventPublisher(Protocol):
    def publish(self, channel: str, event: Event) -> None:
        """Deliver `event` to every active subscription of `channel`. Synchronous: it never waits
        for a slow subscriber (AC-01, AC-02)."""
        ...

    def subscribe(self, channel: str) -> Subscription: ...

    def subscriber_count(self, channel: str | None = None) -> int:
        """Active subscriptions of `channel`, or of every channel when it is `None`."""
        ...


def device_channel(device_hash: str) -> str:
    """Channel of the events of one device."""
    return f"device:{device_hash}"
