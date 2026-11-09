"""Use cases of the driver access codes (driver_codes_cli design §2, CU-13).

Privacy (AC-03, AC-06): the plain code only travels in `CreatedDriverCode`, to be shown once; the
log carries the `code_id` and neither the label nor the code.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from avisabus.domain.errors import (
    DriverCodeAlreadyRevokedError,
    DriverCodeCollisionError,
    DriverCodeNotFoundError,
    InvalidDriverCodeLabelError,
)
from avisabus.domain.models.driver import DriverCode, is_valid_driver_code_label
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.driver import CodeGenerator, DriverCodeHasher, DriverCodeRepository

MAX_COLLISION_RETRIES = 5
DRIVER_CODE_CREATED = "driver_code.created"
DRIVER_CODE_REVOKED = "driver_code.revoked"

HasOpenSession = Callable[[str], bool]
"""`has_open_session(code_id)`: whether the code has a shift open (design §2)."""


class Logger(Protocol):
    def info(self, event: str, **fields: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class CreatedDriverCode:
    code: DriverCode
    plain_code: str = field(repr=False)
    """Only to print it once; left out of `repr` so that it cannot reach a log by accident."""


class CreateDriverCode:
    def __init__(
        self,
        repository: DriverCodeRepository,
        generator: CodeGenerator,
        hasher: DriverCodeHasher,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._repository = repository
        self._generator = generator
        self._hasher = hasher
        self._clock = clock
        self._log = logger

    def execute(self, label: str) -> CreatedDriverCode:
        """Raises `InvalidDriverCodeLabelError` (AC-02) or, when every retry collides,
        `DriverCodeCollisionError` (AC-01), without storing anything."""
        if not is_valid_driver_code_label(label):
            raise InvalidDriverCodeLabelError()
        for _attempt in range(1 + MAX_COLLISION_RETRIES):
            plain_code = self._generator.new_code()
            code = DriverCode(
                code_id=self._generator.new_code_id(),
                code_hash=self._hasher.hash(plain_code),
                label=label,
                created_at=self._clock.now(),
                revoked_at=None,
            )
            try:
                self._repository.add(code)
            except DriverCodeCollisionError:
                continue
            self._log.info(DRIVER_CODE_CREATED, code_id=code.code_id)
            return CreatedDriverCode(code=code, plain_code=plain_code)
        raise DriverCodeCollisionError()


class ListDriverCodes:
    def __init__(self, repository: DriverCodeRepository, has_open_session: HasOpenSession) -> None:
        self._repository = repository
        self._has_open_session = has_open_session

    def execute(self) -> list[tuple[DriverCode, bool]]:
        return [
            (code, self._has_open_session(code.code_id)) for code in self._repository.list_all()
        ]


class RevokeDriverCode:
    def __init__(
        self,
        repository: DriverCodeRepository,
        clock: Clock,
        has_open_session: HasOpenSession,
        logger: Logger,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._has_open_session = has_open_session
        self._log = logger

    def execute(self, code_id: str) -> tuple[DriverCode, bool]:
        """Return the revoked code and whether it had a shift open (AC-05).

        Raises `DriverCodeNotFoundError` if it does not exist and `DriverCodeAlreadyRevokedError`
        if it was already revoked; neither changes anything nor logs.
        """
        existing = self._repository.get(code_id)
        if existing is None:
            raise DriverCodeNotFoundError(code_id)
        if existing.revoked_at is not None:
            raise DriverCodeAlreadyRevokedError(code_id, existing.revoked_at)
        had_open_session = self._has_open_session(code_id)
        revoked = self._repository.revoke(code_id, self._clock.now())
        if revoked is None:  # deleted between both calls: the store has no deletion today
            raise DriverCodeNotFoundError(code_id)
        self._log.info(DRIVER_CODE_REVOKED, code_id=code_id)
        return revoked, had_open_session
