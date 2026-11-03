"""HMAC-SHA256 stop tokens (stop_tokens_qr design §3, "Firma")."""

import base64
import hashlib
import hmac
import re

TOKEN_LENGTH = 22
"""Base64url (no padding) length of the 16-byte truncated digest."""

_DIGEST_BYTES = 16
_TOKEN_PATTERN = re.compile(rf"[A-Za-z0-9_-]{{{TOKEN_LENGTH}}}")


class HmacStopTokenSigner:
    """Token = base64url(HMAC-SHA256(secret, "stop:" + stop_id)[:16]) without padding."""

    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def sign(self, stop_id: str) -> str:
        message = f"stop:{stop_id}".encode()
        digest = hmac.new(self._secret, message, hashlib.sha256).digest()[:_DIGEST_BYTES]
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def verify(self, stop_id: str, token: str) -> bool:
        # The shape check does not depend on the secret; it keeps `compare_digest` (constant
        # time) on ASCII strings, the only `str` it accepts without raising.
        if _TOKEN_PATTERN.fullmatch(token) is None:
            return False
        try:
            expected = self.sign(stop_id)
        except UnicodeEncodeError:
            return False
        return hmac.compare_digest(expected, token)
