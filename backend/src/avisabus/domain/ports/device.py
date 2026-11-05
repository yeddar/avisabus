"""Keyed hash of the anonymous device identifier (realtime_events design §3, AC-05)."""

from typing import Protocol

from avisabus.domain.models.device import DeviceId


class DeviceHasher(Protocol):
    def hash(self, device_id: DeviceId) -> str:
        """`device_hash`: 64 lowercase hexadecimal characters, stable for the same secret."""
        ...
