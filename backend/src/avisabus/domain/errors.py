"""Domain exceptions. Inbound adapters translate them into problem+json responses."""


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
