"""Signed stop tokens (stop_tokens_qr design §3): the QR URL proves the stop was not made up."""

from typing import Protocol


class StopTokenSigner(Protocol):
    def sign(self, stop_id: str) -> str: ...

    def verify(self, stop_id: str, token: str) -> bool:
        """True only if `token` is the token of `stop_id`. Never raises."""
        ...
