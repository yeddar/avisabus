"""Real-time events delivered through the in-memory publisher (realtime_events design §3)."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Event:
    """`type` is the event name (`alert.registered`, `alert.expired`…); `payload` is JSON
    serialisable and never carries `device_id` nor `device_hash`."""

    type: str
    payload: Mapping[str, object]

    def message(self) -> dict[str, object]:
        """The message sent to a client: `{"type": type, **payload}`."""
        return {"type": self.type, **self.payload}
