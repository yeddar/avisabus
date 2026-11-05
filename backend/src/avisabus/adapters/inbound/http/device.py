"""`X-Device-Id` header → `device_hash` (realtime_events design §3).

`alert_create` and the other alert endpoints depend on `device_hash_from_header`; the identifier
in clear is validated, hashed and dropped here, never stored nor logged (RNF-06).
"""

from typing import Annotated

from fastapi import Header, Request

from avisabus.domain.models.device import parse_device_id
from avisabus.domain.ports.device import DeviceHasher


async def device_hash_from_header(
    request: Request, x_device_id: Annotated[str | None, Header()] = None
) -> str:
    """Raises `InvalidDeviceIdError` (→ `400`, invalid-device-id) for a missing or invalid
    header (AC-04)."""
    hasher: DeviceHasher = request.app.state.device_hasher
    return hasher.hash(parse_device_id(x_device_id))
