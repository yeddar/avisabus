"""HMAC-SHA256 hash of the device identifier (realtime_events design §3, AC-05)."""

import hashlib
import hmac

from avisabus.domain.models.device import DeviceId

_DOMAIN = b"avisabus:device-id:v1"
"""Domain separation: the server secret also signs stop tokens, so the hash uses a derived key."""


class HmacDeviceHasher:
    """key = HMAC-SHA256(server_secret, "avisabus:device-id:v1");
    hash = hex(HMAC-SHA256(key, device_id))."""

    def __init__(self, server_secret: bytes) -> None:
        self._key = hmac.new(server_secret, _DOMAIN, hashlib.sha256).digest()

    def hash(self, device_id: DeviceId) -> str:
        return hmac.new(self._key, device_id.value.encode("ascii"), hashlib.sha256).hexdigest()
