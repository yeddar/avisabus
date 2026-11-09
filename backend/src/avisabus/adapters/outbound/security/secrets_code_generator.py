"""Cryptographic generator of driver codes and their identifiers (driver_codes_cli AC-01)."""

import secrets
import string
from collections.abc import Callable

_CODE_SPACE = 100_000_000
_CODE_ID_PREFIX = "dc-"
_CODE_ID_LENGTH = 6
_CODE_ID_ALPHABET = string.ascii_lowercase + string.digits


class SecretsCodeGenerator:
    """`randbelow` is the source of randomness; only tests replace it."""

    def __init__(self, randbelow: Callable[[int], int] | None = None) -> None:
        self._randbelow = secrets.randbelow if randbelow is None else randbelow

    def new_code(self) -> str:
        return f"{self._randbelow(_CODE_SPACE):08d}"

    def new_code_id(self) -> str:
        suffix = "".join(
            _CODE_ID_ALPHABET[self._randbelow(len(_CODE_ID_ALPHABET))]
            for _ in range(_CODE_ID_LENGTH)
        )
        return f"{_CODE_ID_PREFIX}{suffix}"
