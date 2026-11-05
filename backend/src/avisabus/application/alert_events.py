"""Public schema of an alert and its confirmation events (alert_create design §3).

`alert_payload` is the alert as the API answers it (`POST /alerts`, `GET /alerts/mine`) and as
the events and the `alerts.snapshot` of `/ws/passenger` carry it. It never includes the
`device_hash` (RNF-06).
"""

from datetime import UTC, datetime

from avisabus.domain.models.alert import Alert
from avisabus.domain.models.events import Event

ALERT_REGISTERED = "alert.registered"
"""Stored without a driver connected to the bus (`PENDING_DRIVER`)."""
ALERT_DELIVERED = "alert.delivered"
"""Delivered to the driver of the bus (`DELIVERED`)."""


def alert_payload(alert: Alert) -> dict[str, object]:
    return {
        "alert_id": alert.alert_id,
        "stop_id": alert.stop_id,
        "stop_name": alert.stop_name,
        "line": alert.line,
        "direction_id": alert.direction_id,
        "destination": alert.destination,
        "trip_id": alert.trip_id,
        "service_date": alert.service_date.isoformat(),
        "needs": [need.value for need in alert.needs],
        "status": alert.status.value,
        "created_at": _utc_text(alert.created_at),
        "expires_at": _utc_text(alert.expires_at),
    }


def alert_event(event_type: str, alert: Alert) -> Event:
    """Event `{"type": event_type, "alert": <alert_payload>}` of the device channel."""
    return Event(event_type, {"alert": alert_payload(alert)})


def _utc_text(value: datetime) -> str:
    """ISO-8601 in UTC with `Z`, as the API serialises datetimes."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
