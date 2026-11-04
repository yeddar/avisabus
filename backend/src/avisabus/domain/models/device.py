"""Anonymous device identifier (realtime_events design §3, AC-04).

The client generates a UUID v4 and sends it as `device_id`; the server only keeps its keyed hash
(`DeviceHasher`). The value is never shown by `repr`/`str`, so it cannot leak into a log.
"""

import re
from dataclasses import dataclass, field

from avisabus.domain.errors import InvalidDeviceIdError

_DEVICE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_MASKED = "DeviceId(***)"


@dataclass(frozen=True, slots=True, repr=False)
class DeviceId:
    """A canonical UUID v4 (36 lowercase characters with hyphens). Build it with
    `parse_device_id`."""

    value: str = field(repr=False)

    def __repr__(self) -> str:
        return _MASKED

    def __str__(self) -> str:
        return _MASKED


def parse_device_id(raw: str | None) -> DeviceId:
    """Accept only a canonical UUID v4; raise `InvalidDeviceIdError` for anything else."""
    if not isinstance(raw, str) or _DEVICE_ID.fullmatch(raw) is None:
        raise InvalidDeviceIdError()
    return DeviceId(raw)
