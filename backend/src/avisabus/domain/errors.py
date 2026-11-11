"""Domain exceptions. Inbound adapters translate them into problem+json responses."""

from datetime import datetime


class DomainError(Exception):
    """Base class for every domain error."""


class UnknownLineError(DomainError):
    """The commercial line does not exist in the active network. The line is in `line`."""

    def __init__(self, line: str) -> None:
        self.line = line
        super().__init__("unknown line")


class NoActiveFeedError(DomainError):
    """No GTFS feed has been imported yet, so there is no active network to read."""

    def __init__(self) -> None:
        super().__init__("no active GTFS feed")


class ArrivalsUnavailableError(DomainError):
    """Real-time arrivals of a stop cannot be obtained (sae_arrivals_source design §6).

    `stop_id` is the stop; `reason` is `timeout`, `network`, `http_<code>`, `unparseable`,
    `no_recording` or the error recorded in a replayed session.
    """

    def __init__(self, stop_id: str, reason: str) -> None:
        self.stop_id = stop_id
        self.reason = reason
        super().__init__(f"arrivals unavailable ({reason})")


class StopNotFoundError(DomainError):
    """The stop token is missing or invalid, or the stop does not exist (stop_arrivals_api AC-02).

    The three cases are deliberately the same error. The stop is in `stop_id`.
    """

    def __init__(self, stop_id: str) -> None:
        self.stop_id = stop_id
        super().__init__("stop not found")


class LineNotAtStopError(DomainError):
    """The line does not serve the stop in that direction (position_estimation AC-12).

    The line and direction are in `line` and `direction_id`; the stop is in `stop_id`.
    """

    def __init__(self, stop_id: str, line: str, direction_id: int) -> None:
        self.stop_id = stop_id
        self.line = line
        self.direction_id = direction_id
        super().__init__("line not at stop")


class ShapeNotFoundError(DomainError):
    """No trip of the active feed uses the shape (position_estimation AC-15). It is in
    `shape_id`."""

    def __init__(self, shape_id: str) -> None:
        self.shape_id = shape_id
        super().__init__("shape not found")


class PositionNotEstimableError(DomainError, ValueError):
    """The position of a paired trip cannot be estimated because the active network is
    incoherent for it (position_estimation AC-11, v1.2).

    `reason` is `missing_stop_times`, `missing_shape`, `empty_shape`, `missing_stop_coordinates`
    or `target_not_in_trip`. It is a `ValueError` too: the data, not the code, is wrong.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"position not estimable ({reason})")


class InvalidDeviceIdError(DomainError):
    """The device identifier is not a canonical UUID v4 (realtime_events AC-04).

    The rejected value is deliberately not kept: it could be a real identifier (RNF-06).
    """

    def __init__(self) -> None:
        super().__init__("invalid device id")


class SubscriptionOverflowError(DomainError):
    """The queue of an event subscription filled up and it stopped receiving events
    (realtime_events AC-02): the reader must drop it and start over with a fresh snapshot."""

    def __init__(self) -> None:
        super().__init__("subscription overflowed")


class BusNotRequestableError(DomainError):
    """No arrival of the stop matches the requested bus (line, direction, trip and service day)
    with `can_alert` (alert_create AC-03)."""

    def __init__(self) -> None:
        super().__init__("bus not requestable")


class RateLimitedError(DomainError):
    """Too many alert requests from the device or the IP address (alert_create AC-08).

    `retry_after_s` is the value of `Retry-After`. Neither the key nor the address is kept.
    """

    def __init__(self, retry_after_s: int) -> None:
        self.retry_after_s = retry_after_s
        super().__init__("rate limited")


class AlertNotFoundError(DomainError):
    """The alert does not exist, already expired or belongs to another device (alert_cancel
    AC-02). The three cases are deliberately the same error, without the identifier."""

    def __init__(self) -> None:
        super().__init__("alert not found")


class InvalidDriverCodeLabelError(DomainError):
    """The label of a driver code is not 1 to 40 printable characters (driver_codes_cli AC-02)."""

    def __init__(self) -> None:
        super().__init__("invalid driver code label")


class DriverCodeCollisionError(DomainError):
    """The hash or the identifier of a new driver code already exist (driver_codes_cli AC-01)."""

    def __init__(self) -> None:
        super().__init__("driver code collision")


class DriverCodeNotFoundError(DomainError):
    """No driver code has that identifier (driver_codes_cli AC-05). It is in `code_id`."""

    def __init__(self, code_id: str) -> None:
        self.code_id = code_id
        super().__init__("driver code not found")


class DriverCodeAlreadyRevokedError(DomainError):
    """The driver code was already revoked, so nothing changed (driver_codes_cli AC-05).

    The identifier and the original date are in `code_id` and `revoked_at`.
    """

    def __init__(self, code_id: str, revoked_at: datetime) -> None:
        self.code_id = code_id
        self.revoked_at = revoked_at
        super().__init__("driver code already revoked")


class InvalidDriverCodeError(DomainError):
    """The driver code does not exist or is revoked (driver_session AC-02). Both cases are
    deliberately the same error, without the code."""

    def __init__(self) -> None:
        super().__init__("invalid driver code")


class InvalidSessionError(DomainError):
    """The session token is missing or does not belong to an open shift (driver_session AC-04)."""

    def __init__(self) -> None:
        super().__init__("invalid session")


class InvalidDepartureError(DomainError):
    """The departure is not one of those offered to the driver now (driver_session AC-07)."""

    def __init__(self) -> None:
        super().__init__("invalid departure")


class DepartureTakenError(DomainError):
    """Another open shift already holds the departure (driver_session AC-07)."""

    def __init__(self) -> None:
        super().__init__("departure taken")


class InvalidPositionError(DomainError):
    """The position was recorded too far in the future (driver_session AC-08). The coordinates
    are deliberately not kept."""

    def __init__(self) -> None:
        super().__init__("invalid position")
