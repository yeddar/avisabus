"""Domain exceptions. Inbound adapters translate them into problem+json responses."""


class DomainError(Exception):
    """Base class for every domain error."""


class UnknownLineError(DomainError):
    """The commercial line does not exist in the active network. The line is in `line`."""

    def __init__(self, line: str) -> None:
        self.line = line
        super().__init__("unknown line")
