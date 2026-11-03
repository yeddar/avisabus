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
