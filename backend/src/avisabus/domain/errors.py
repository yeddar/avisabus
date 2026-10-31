"""Domain exceptions. Inbound adapters translate them into problem+json responses."""


class DomainError(Exception):
    """Base class for every domain error."""
