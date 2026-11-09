"""Ports of the driver access codes (driver_codes_cli design §2)."""

from datetime import datetime
from typing import Protocol

from avisabus.domain.models.driver import DriverCode


class DriverCodeHasher(Protocol):
    def hash(self, code: str) -> str:
        """Keyed hash (hexadecimal) of a code of 8 digits without spaces."""
        ...


class CodeGenerator(Protocol):
    def new_code(self) -> str:
        """A new code of 8 digits, with leading zeros."""
        ...

    def new_code_id(self) -> str:
        """A new identifier: `dc-` + 6 characters in [a-z0-9]."""
        ...


class DriverCodeRepository(Protocol):
    def add(self, code: DriverCode) -> None:
        """Store the code. Raises `DriverCodeCollisionError` if its hash or id already exist."""
        ...

    def get(self, code_id: str) -> DriverCode | None: ...

    def find_by_hash(self, code_hash: str) -> DriverCode | None: ...

    def list_all(self) -> list[DriverCode]:
        """Every code, active or revoked, ordered by `created_at`."""
        ...

    def revoke(self, code_id: str, at: datetime) -> DriverCode | None:
        """Mark the code as revoked at `at` and return it; `None` if it does not exist. A code
        that was already revoked keeps its original date."""
        ...
