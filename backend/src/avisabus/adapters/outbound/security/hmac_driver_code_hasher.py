"""HMAC-SHA256 hash of the driver access codes (driver_codes_cli design §2, AC-03, ADR-017)."""

import hashlib
import hmac

_DOMAIN = b"avisabus:driver-code:v1"
"""Domain separation: the server secret also signs stop tokens and derives the device key."""


class HmacDriverCodeHasher:
    """key = HMAC-SHA256(server_secret, "avisabus:driver-code:v1");
    hash = hex(HMAC-SHA256(key, code))."""

    def __init__(self, server_secret: bytes) -> None:
        self._key = hmac.new(server_secret, _DOMAIN, hashlib.sha256).digest()

    def hash(self, code: str) -> str:
        return hmac.new(self._key, code.encode("ascii"), hashlib.sha256).hexdigest()
