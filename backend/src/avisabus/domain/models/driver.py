"""Driver access codes (driver_codes_cli design §2, ADR-017).

The plain code is never part of this model: only its keyed hash is kept. Codes are not tied to
people; the label is free text chosen by the administrator.
"""

from dataclasses import dataclass, field
from datetime import datetime

MAX_LABEL_LENGTH = 40


@dataclass(frozen=True, slots=True)
class DriverCode:
    code_id: str
    """`dc-` + 6 characters in [a-z0-9]."""
    code_hash: str = field(repr=False)
    """Hexadecimal keyed hash, left out of `repr` so that it cannot reach a log by accident."""
    label: str
    created_at: datetime
    revoked_at: datetime | None

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


def is_valid_driver_code_label(label: str) -> bool:
    """AC-02: from 1 to 40 printable characters; line breaks and controls are not printable."""
    return 1 <= len(label) <= MAX_LABEL_LENGTH and label.isprintable()
