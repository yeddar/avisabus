"""QR rendering port (stop_tokens_qr design §3)."""

from dataclasses import dataclass
from typing import Literal, Protocol

QrFormat = Literal["svg", "png"]


@dataclass(frozen=True, slots=True)
class QrLabel:
    title: str
    """Stop name, as it comes in the GTFS."""
    subtitle: str
    """`Parada {stop_id}` (same word in Spanish and Valencian)."""


@dataclass(frozen=True, slots=True)
class QrRequest:
    content: str
    """Text encoded in the QR (the stop URL)."""
    label: QrLabel
    format: QrFormat


class QrRenderer(Protocol):
    def render(self, request: QrRequest) -> bytes: ...
