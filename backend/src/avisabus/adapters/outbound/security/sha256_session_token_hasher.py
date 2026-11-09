"""SHA-256 of the session tokens (driver_session AC-01). The token is random with 256 bits of
entropy, so no key is needed."""

import hashlib


class Sha256SessionTokenHasher:
    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
