"""Driver codes: model, hasher, generator and use cases with fakes (driver_codes_cli T-01)."""

import hashlib
import hmac
import re
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.adapters.outbound.security.hmac_driver_code_hasher import HmacDriverCodeHasher
from avisabus.adapters.outbound.security.secrets_code_generator import SecretsCodeGenerator
from avisabus.application.driver_codes import (
    MAX_COLLISION_RETRIES,
    CreatedDriverCode,
    CreateDriverCode,
    ListDriverCodes,
    RevokeDriverCode,
)
from avisabus.domain.errors import (
    DriverCodeAlreadyRevokedError,
    DriverCodeCollisionError,
    DriverCodeNotFoundError,
    InvalidDriverCodeLabelError,
)
from avisabus.domain.models.device import parse_device_id
from avisabus.domain.models.driver import DriverCode
from avisabus.domain.ports.driver import CodeGenerator, DriverCodeHasher
from tests.support.fake_clock import FakeClock

NOW = datetime(2026, 11, 9, 15, 40, tzinfo=UTC)
SERVER_SECRET = b"s" * 32
PLAIN = "48210937"
DEVICE = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"


class FakeHasher:
    def hash(self, code: str) -> str:
        return f"hash-of-{code}"


class FakeGenerator:
    """Hands out the given codes in order; identifiers are `dc-000001`, `dc-000002`…"""

    def __init__(self, codes: Iterable[str]) -> None:
        self._codes = iter(codes)
        self._ids = 0

    def new_code(self) -> str:
        return next(self._codes)

    def new_code_id(self) -> str:
        self._ids += 1
        return f"dc-{self._ids:06d}"


class FakeRepository:
    """Enforces the same uniqueness as the table: `code_id` and `code_hash`."""

    def __init__(self, existing: Iterable[DriverCode] = ()) -> None:
        self.codes = {code.code_id: code for code in existing}
        self.add_calls = 0

    def add(self, code: DriverCode) -> None:
        self.add_calls += 1
        if code.code_id in self.codes or self.find_by_hash(code.code_hash) is not None:
            raise DriverCodeCollisionError()
        self.codes[code.code_id] = code

    def get(self, code_id: str) -> DriverCode | None:
        return self.codes.get(code_id)

    def find_by_hash(self, code_hash: str) -> DriverCode | None:
        return next((c for c in self.codes.values() if c.code_hash == code_hash), None)

    def list_all(self) -> list[DriverCode]:
        return sorted(self.codes.values(), key=lambda c: c.created_at)

    def revoke(self, code_id: str, at: datetime) -> DriverCode | None:
        code = self.codes.get(code_id)
        if code is None:
            return None
        revoked = DriverCode(code.code_id, code.code_hash, code.label, code.created_at, at)
        self.codes[code_id] = revoked
        return revoked


class FakeLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **fields: Any) -> None:
        self.calls.append((event, fields))


def _code(
    code_id: str = "dc-abc123",
    code_hash: str = "hash-of-11112222",
    revoked_at: datetime | None = None,
) -> DriverCode:
    return DriverCode(code_id, code_hash, "Tablet 3", NOW - timedelta(days=1), revoked_at)


def _create(
    repository: FakeRepository,
    logger: FakeLogger | None = None,
    codes: Iterable[str] = (PLAIN,),
) -> CreateDriverCode:
    return CreateDriverCode(
        repository=repository,
        generator=FakeGenerator(codes),
        hasher=FakeHasher(),
        clock=FakeClock(NOW),
        logger=logger or FakeLogger(),
    )


def _revoke(
    repository: FakeRepository,
    logger: FakeLogger | None = None,
    has_open_session: bool = False,
) -> RevokeDriverCode:
    return RevokeDriverCode(
        repository=repository,
        clock=FakeClock(NOW),
        has_open_session=lambda _code_id: has_open_session,
        logger=logger or FakeLogger(),
    )


# --- Generator ------------------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_generator_draws_the_code_from_the_whole_eight_digit_space() -> None:
    bounds: list[int] = []

    def randbelow(bound: int) -> int:
        bounds.append(bound)
        return 48210937

    generator: CodeGenerator = SecretsCodeGenerator(randbelow=randbelow)
    assert generator.new_code() == PLAIN
    assert bounds == [100_000_000]


@pytest.mark.spec("driver_codes_cli.AC-01")
@pytest.mark.parametrize(
    ("drawn", "expected"), [(0, "00000000"), (42, "00000042"), (99_999_999, "99999999")]
)
def test_generator_keeps_leading_zeros(drawn: int, expected: str) -> None:
    assert SecretsCodeGenerator(randbelow=lambda _bound: drawn).new_code() == expected


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_generator_builds_the_code_id_from_the_injected_source() -> None:
    drawn = iter([0, 1, 25, 26, 35, 2])
    bounds: list[int] = []

    def randbelow(bound: int) -> int:
        bounds.append(bound)
        return next(drawn)

    assert SecretsCodeGenerator(randbelow=randbelow).new_code_id() == "dc-abz09c"
    assert bounds == [36] * 6


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_generator_uses_the_cryptographic_source_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(secrets, "randbelow", lambda _bound: 7)
    generator = SecretsCodeGenerator()
    assert generator.new_code() == "00000007"
    assert generator.new_code_id() == "dc-hhhhhh"


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_generator_output_has_the_documented_shape() -> None:
    generator = SecretsCodeGenerator()
    assert re.fullmatch(r"\d{8}", generator.new_code())
    assert re.fullmatch(r"dc-[a-z0-9]{6}", generator.new_code_id())


# --- Hasher ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_hash_is_hmac_sha256_with_the_derived_key() -> None:
    key = hmac.new(SERVER_SECRET, b"avisabus:driver-code:v1", hashlib.sha256).digest()
    expected = hmac.new(key, PLAIN.encode(), hashlib.sha256).hexdigest()
    hasher: DriverCodeHasher = HmacDriverCodeHasher(SERVER_SECRET)
    assert hasher.hash(PLAIN) == expected


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_hash_does_not_use_the_server_secret_directly() -> None:
    direct = hmac.new(SERVER_SECRET, PLAIN.encode(), hashlib.sha256).hexdigest()
    assert HmacDriverCodeHasher(SERVER_SECRET).hash(PLAIN) != direct


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_hash_is_separated_from_the_device_hash_domain() -> None:
    device_hash = HmacDeviceHasher(SERVER_SECRET).hash(parse_device_id(DEVICE))
    assert HmacDriverCodeHasher(SERVER_SECRET).hash(DEVICE) != device_hash


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_hash_depends_on_the_server_secret_and_on_the_code() -> None:
    hasher = HmacDriverCodeHasher(SERVER_SECRET)
    assert hasher.hash(PLAIN) == hasher.hash(PLAIN)
    assert hasher.hash(PLAIN) != hasher.hash("48210938")
    assert hasher.hash(PLAIN) != HmacDriverCodeHasher(b"t" * 32).hash(PLAIN)


# --- Model ----------------------------------------------------------------------------------


def test_driver_code_is_revoked_only_with_a_revocation_date() -> None:
    assert _code().revoked is False
    assert _code(revoked_at=NOW).revoked is True


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_repr_does_not_expose_the_plain_code_nor_the_hash() -> None:
    created = CreatedDriverCode(code=_code(code_hash="deadbeef"), plain_code=PLAIN)
    assert PLAIN not in repr(created)
    assert PLAIN not in str(created)
    assert "deadbeef" not in repr(created)


# --- CreateDriverCode -----------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_create_stores_the_code_and_returns_the_plain_one() -> None:
    repository = FakeRepository()
    result = _create(repository).execute("Tablet 3")
    expected = DriverCode("dc-000001", f"hash-of-{PLAIN}", "Tablet 3", NOW, None)
    assert result.code == expected
    assert result.plain_code == PLAIN
    assert repository.codes == {"dc-000001": expected}


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_create_never_stores_the_plain_code() -> None:
    repository = FakeRepository()
    _create(repository).execute("Tablet 3")
    stored = repository.codes["dc-000001"]
    assert stored.code_hash != PLAIN
    assert stored.label != PLAIN
    assert stored.code_id != PLAIN


@pytest.mark.spec("driver_codes_cli.AC-01")
@pytest.mark.parametrize("revoked_at", [None, NOW], ids=["active", "revoked"])
def test_create_generates_another_code_when_it_already_exists(revoked_at: datetime | None) -> None:
    taken = _code(code_hash=f"hash-of-{PLAIN}", revoked_at=revoked_at)
    repository = FakeRepository([taken])
    result = _create(repository, codes=[PLAIN, "11112222"]).execute("Tablet 3")
    assert result.plain_code == "11112222"
    assert repository.codes[result.code.code_id].code_hash == "hash-of-11112222"
    assert repository.codes[taken.code_id] == taken


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_create_retries_up_to_five_times() -> None:
    assert MAX_COLLISION_RETRIES == 5
    repository = FakeRepository([_code(code_hash=f"hash-of-{PLAIN}")])
    result = _create(repository, codes=[PLAIN] * 5 + ["11112222"]).execute("Tablet 3")
    assert result.plain_code == "11112222"
    assert repository.add_calls == 6


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_create_gives_up_after_the_retries_without_storing_anything() -> None:
    taken = _code(code_hash=f"hash-of-{PLAIN}")
    repository = FakeRepository([taken])
    logger = FakeLogger()
    with pytest.raises(DriverCodeCollisionError):
        _create(repository, logger, codes=[PLAIN] * 6 + ["11112222"]).execute("Tablet 3")
    assert repository.add_calls == 6
    assert repository.codes == {taken.code_id: taken}
    assert logger.calls == []


@pytest.mark.spec("driver_codes_cli.AC-02")
@pytest.mark.parametrize("label", ["T", "x" * 40, "Tablet 3", "Conductor nº 12 · València", "   "])
def test_create_accepts_labels_of_one_to_forty_printable_characters(label: str) -> None:
    assert _create(FakeRepository()).execute(label).code.label == label


@pytest.mark.spec("driver_codes_cli.AC-02")
@pytest.mark.parametrize(
    "label",
    ["", "x" * 41, "Tablet\n3", "Tablet\r3", "Tablet\t3", "Tablet\x1b[31m3", "Tablet 3"],
    ids=["empty", "too-long", "newline", "carriage-return", "tab", "escape", "line-separator"],
)
def test_create_rejects_invalid_labels_without_storing_anything(label: str) -> None:
    repository = FakeRepository()
    with pytest.raises(InvalidDriverCodeLabelError):
        _create(repository).execute(label)
    assert repository.add_calls == 0


def test_invalid_label_error_does_not_carry_the_label() -> None:
    assert "secret-label" not in str(InvalidDriverCodeLabelError())


@pytest.mark.spec("driver_codes_cli.AC-06")
def test_create_logs_only_the_code_id() -> None:
    logger = FakeLogger()
    _create(FakeRepository(), logger).execute("Tablet 3")
    assert logger.calls == [("driver_code.created", {"code_id": "dc-000001"})]


@pytest.mark.spec("driver_codes_cli.AC-06")
def test_create_logs_once_even_after_a_collision() -> None:
    logger = FakeLogger()
    repository = FakeRepository([_code(code_hash=f"hash-of-{PLAIN}")])
    _create(repository, logger, codes=[PLAIN, "11112222"]).execute("Tablet 3")
    assert logger.calls == [("driver_code.created", {"code_id": "dc-000002"})]


# --- ListDriverCodes ------------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-04")
def test_list_pairs_each_code_with_its_open_session_state() -> None:
    first = _code("dc-aaaaaa", "hash-a")
    second = DriverCode("dc-bbbbbb", "hash-b", "Tablet 4", NOW, NOW)
    use_case = ListDriverCodes(
        repository=FakeRepository([second, first]),
        has_open_session=lambda code_id: code_id == "dc-bbbbbb",
    )
    assert use_case.execute() == [(first, False), (second, True)]


# --- RevokeDriverCode -----------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-05")
@pytest.mark.parametrize("open_session", [False, True])
def test_revoke_marks_the_code_and_reports_the_open_session(open_session: bool) -> None:
    repository = FakeRepository([_code()])
    code, had_open_session = _revoke(repository, has_open_session=open_session).execute("dc-abc123")
    assert code.revoked_at == NOW
    assert repository.codes["dc-abc123"].revoked_at == NOW
    assert had_open_session is open_session


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_checks_the_open_session_before_revoking() -> None:
    repository = FakeRepository([_code()])
    use_case = RevokeDriverCode(
        repository=repository,
        clock=FakeClock(NOW),
        # Stands for a shift that ends as soon as its code is revoked.
        has_open_session=lambda code_id: not repository.codes[code_id].revoked,
        logger=FakeLogger(),
    )
    _code_after, had_open_session = use_case.execute("dc-abc123")
    assert had_open_session is True


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_of_an_unknown_code_raises_and_keeps_the_id_in_an_attribute() -> None:
    logger = FakeLogger()
    with pytest.raises(DriverCodeNotFoundError) as error:
        _revoke(FakeRepository(), logger).execute("dc-nope00")
    assert error.value.code_id == "dc-nope00"
    assert "dc-nope00" not in str(error.value)
    assert logger.calls == []


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_of_a_revoked_code_changes_nothing() -> None:
    earlier = NOW - timedelta(hours=2)
    repository = FakeRepository([_code(revoked_at=earlier)])
    logger = FakeLogger()
    with pytest.raises(DriverCodeAlreadyRevokedError) as error:
        _revoke(repository, logger).execute("dc-abc123")
    assert error.value.code_id == "dc-abc123"
    assert error.value.revoked_at == earlier
    assert "dc-abc123" not in str(error.value)
    assert repository.codes["dc-abc123"].revoked_at == earlier
    assert logger.calls == []


@pytest.mark.spec("driver_codes_cli.AC-06")
def test_revoke_logs_only_the_code_id() -> None:
    logger = FakeLogger()
    _revoke(FakeRepository([_code()]), logger).execute("dc-abc123")
    assert logger.calls == [("driver_code.revoked", {"code_id": "dc-abc123"})]
