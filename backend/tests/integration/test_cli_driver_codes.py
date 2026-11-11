"""`avisabus driver-codes …` with a temporary database and a FakeClock (driver_codes_cli T-03).

The commands use the real composition unless a test needs a known code or an open shift. The
tests with real JSON logs keep `configure_logging`, so they capture what the process writes.
"""

import hashlib
import hmac
import json
import logging
import re
import sys
import traceback
from collections.abc import Callable, Iterable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import structlog
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner, Result

from avisabus.adapters.inbound.cli import driver_codes as driver_codes_cli
from avisabus.adapters.inbound.cli import main as main_module
from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.inbound.cli.main import app
from avisabus.adapters.outbound.persistence.db import create_engine
from avisabus.adapters.outbound.persistence.sqlite_driver_codes import SqliteDriverCodeRepository
from avisabus.adapters.outbound.persistence.sqlite_driver_sessions import (
    SqliteDriverSessionRepository,
)
from avisabus.adapters.outbound.security.hmac_driver_code_hasher import HmacDriverCodeHasher
from avisabus.application.driver_codes import CreateDriverCode, ListDriverCodes, RevokeDriverCode
from avisabus.config import Settings
from avisabus.domain.models.driver import DriverSession
from avisabus.domain.ports.clock import Clock
from avisabus.logging import configure_logging
from tests.support.fake_clock import FakeClock

runner = CliRunner()
NOW = datetime(2026, 11, 9, 15, 40, tzinfo=UTC)
SECRET = "x" * 32
LABEL = "Tablet 3"
SPACED_CODE = re.compile(r"Código de acceso: (\d{4}) (\d{4})")


class FixedGenerator:
    def __init__(self, codes: Iterable[str]) -> None:
        self._codes = iter(codes)
        self._ids = 0

    def new_code(self) -> str:
        return next(self._codes)

    def new_code_id(self) -> str:
        self._ids += 1
        return f"dc-fixed{self._ids}"


def _settings(path: Path, secret: str | None = SECRET) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, env="test", database_url=f"sqlite:///{path}", stop_token_secret=secret
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "avisabus.sqlite"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture
def customise(
    monkeypatch: pytest.MonkeyPatch, db_path: Path, clock: FakeClock
) -> Callable[..., None]:
    """Make the CLI use the test settings and clock, plus the given container changes."""

    def apply(
        secret: str | None = SECRET,
        change: Callable[[CliContainer], dict[str, Any]] | None = None,
    ) -> None:
        def build(_settings: Settings, _clock: Clock) -> CliContainer:
            container = build_cli_container(_settings_for(secret), clock)
            return replace(container, **change(container)) if change else container

        def _settings_for(value: str | None) -> Settings:
            return _settings(db_path, value)

        monkeypatch.setattr(driver_codes_cli, "build_cli_container", build)

    return apply


@pytest.fixture(autouse=True)
def _default_container(monkeypatch: pytest.MonkeyPatch, customise: Callable[..., None]) -> None:
    customise()
    monkeypatch.setattr(driver_codes_cli, "configure_logging", lambda _level: None)


@pytest.fixture
def real_logging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    monkeypatch.setattr(driver_codes_cli, "configure_logging", configure_logging)
    monkeypatch.setenv("AVISABUS_LOG_LEVEL", "DEBUG")
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


def _run(*args: str) -> Result:
    return runner.invoke(app, ["driver-codes", *args])


def _create(label: str = LABEL) -> Result:
    result = _run("create", "--label", label)
    assert result.exit_code == 0, result.output
    return result


def _plain_code(result: Result) -> str:
    match = SPACED_CODE.search(result.stdout)
    assert match is not None, result.stdout
    return match.group(1) + match.group(2)


def _code_id(result: Result) -> str:
    match = re.search(r"Código creado: (dc-[a-z0-9]{6})", result.stdout)
    assert match is not None, result.stdout
    return match.group(1)


def _rows(db_path: Path) -> list[dict[str, Any]]:
    engine = create_engine(_settings(db_path))
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM driver_code ORDER BY created_at")).mappings()
            return [dict(row) for row in rows]
    finally:
        engine.dispose()


def _json_lines(output: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def _expected_hash(code: str, secret: str = SECRET) -> str:
    key = hmac.new(secret.encode(), b"avisabus:driver-code:v1", hashlib.sha256).digest()
    return hmac.new(key, code.encode(), hashlib.sha256).hexdigest()


def _open_session_container(open_ids: set[str]) -> Callable[[CliContainer], dict[str, Any]]:
    def change(container: CliContainer) -> dict[str, Any]:
        repository = SqliteDriverCodeRepository(container.engine)
        has_open_session = open_ids.__contains__
        return {
            "list_driver_codes": ListDriverCodes(repository, has_open_session),
            "revoke_driver_code": RevokeDriverCode(
                repository, FakeClock(NOW), has_open_session, structlog.get_logger()
            ),
        }

    return change


def _fixed_generator_container(codes: Iterable[str]) -> Callable[[CliContainer], dict[str, Any]]:
    generator = FixedGenerator(codes)

    def change(container: CliContainer) -> dict[str, Any]:
        return {
            "create_driver_code": CreateDriverCode(
                repository=SqliteDriverCodeRepository(container.engine),
                generator=generator,
                hasher=HmacDriverCodeHasher(SECRET.encode()),
                clock=FakeClock(NOW),
                logger=structlog.get_logger(),
            )
        }

    return change


# --- create ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_create_prints_the_code_grouped_with_its_id_and_label(db_path: Path) -> None:
    result = _create()
    code_id = _code_id(result)
    plain = _plain_code(result)
    assert re.fullmatch(r"\d{8}", plain)
    spaced = f"{plain[:4]} {plain[4:]}"
    assert result.stdout.splitlines()[-3:] == [
        f"Código creado: {code_id}  ·  {LABEL}",
        f"  Código de acceso: {spaced}",
        "  Apúntalo ahora: no se volverá a mostrar.",
    ]
    assert (result.stdout + result.stderr).count(spaced) == 1
    assert (result.stdout + result.stderr).count(plain) == 0


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_create_stores_the_generated_code(db_path: Path) -> None:
    result = _create()
    assert _rows(db_path) == [
        {
            "code_id": _code_id(result),
            "code_hash": _expected_hash(_plain_code(result)),
            "label": LABEL,
            "created_at": "2026-11-09T15:40:00+00:00",
            "revoked_at": None,
        }
    ]


@pytest.mark.spec("driver_codes_cli.AC-01")
@pytest.mark.parametrize("revoke_first", [False, True], ids=["active", "revoked"])
def test_create_generates_another_code_when_the_code_exists(
    db_path: Path, customise: Callable[..., None], revoke_first: bool
) -> None:
    customise(change=_fixed_generator_container(["48210937", "48210937", "11112222"]))
    first = _create()
    assert _plain_code(first) == "48210937"
    if revoke_first:
        assert _run("revoke", "dc-fixed1").exit_code == 0
    second = _create("Tablet 4")
    assert _plain_code(second) == "11112222"
    assert [row["code_hash"] for row in _rows(db_path)] == [
        _expected_hash("48210937"),
        _expected_hash("11112222"),
    ]


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_create_fails_cleanly_when_every_retry_collides(
    db_path: Path, customise: Callable[..., None]
) -> None:
    customise(change=_fixed_generator_container(["48210937"] * 7))
    _create()
    result = _run("create", "--label", "Tablet 4")
    assert result.exit_code == 1
    assert "ERROR" in result.stderr
    assert "48210937" not in result.output
    assert len(_rows(db_path)) == 1


@pytest.mark.spec("driver_codes_cli.AC-02")
@pytest.mark.parametrize(
    "label",
    ["", "x" * 41, "Tablet\n3", "Tablet\t3", "Tablet\x1b[31m3"],
    ids=["empty", "too-long", "newline", "tab", "escape"],
)
def test_create_rejects_invalid_labels(db_path: Path, label: str) -> None:
    result = _run("create", "--label", label)
    assert result.exit_code != 0
    assert "etiqueta" in result.stderr
    assert "1 a 40" in result.stderr
    assert _rows(db_path) == []


@pytest.mark.spec("driver_codes_cli.AC-02")
def test_create_requires_a_label(db_path: Path) -> None:
    result = _run("create")
    assert result.exit_code != 0
    assert "etiqueta" in result.stderr
    assert not db_path.exists()


@pytest.mark.spec("driver_codes_cli.AC-02")
@pytest.mark.parametrize("label", ["T", "x" * 40, "Conductor nº 12 · València"])
def test_create_accepts_valid_labels(db_path: Path, label: str) -> None:
    _create(label)
    assert [row["label"] for row in _rows(db_path)] == [label]


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_the_hash_uses_the_configured_server_secret(
    db_path: Path, customise: Callable[..., None]
) -> None:
    customise(secret="y" * 32)
    result = _create()
    plain = _plain_code(result)
    assert _rows(db_path)[0]["code_hash"] == _expected_hash(plain, "y" * 32)
    assert _rows(db_path)[0]["code_hash"] != _expected_hash(plain, SECRET)


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_the_plain_code_is_not_in_the_table(db_path: Path) -> None:
    plain = _plain_code(_create())
    row = _rows(db_path)[0]
    assert all(plain not in str(value) for value in row.values())


@pytest.mark.spec("driver_codes_cli.AC-03")
@pytest.mark.usefixtures("real_logging")
def test_neither_the_code_nor_its_hash_reach_the_logs(db_path: Path) -> None:
    result = _create()
    plain = _plain_code(result)
    code_hash = _rows(db_path)[0]["code_hash"]
    output = result.stdout + result.stderr
    log_lines = [line for line in output.splitlines() if line.startswith("{")]
    assert any("driver_code.created" in line for line in log_lines)
    for line in log_lines:
        assert plain not in line
        assert f"{plain[:4]} {plain[4:]}" not in line
        assert code_hash not in line


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_a_failed_write_shows_neither_the_hash_nor_the_label(
    customise: Callable[..., None],
) -> None:
    fixed = _fixed_generator_container(["48210937"])

    def drop_table_after_composing(container: CliContainer) -> dict[str, Any]:
        # `build_cli_container` runs `init_db`, so the table can only be removed afterwards.
        with container.engine.begin() as conn:
            conn.execute(text("DROP TABLE driver_code"))
        return fixed(container)

    customise(change=drop_table_after_composing)
    result = _run("create", "--label", "EtiquetaSensible")

    assert result.exit_code == 1
    assert isinstance(result.exception, OperationalError)
    shown = result.output + "".join(traceback.format_exception(result.exception))
    assert _expected_hash("48210937") not in shown
    assert "EtiquetaSensible" not in shown
    assert "48210937" not in shown


def _frame_locals(error: BaseException) -> list[dict[str, Any]]:
    return [frame.f_locals for frame, _line in traceback.walk_tb(error.__traceback__)]


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_the_error_trace_does_not_show_the_code_kept_in_a_local_variable(
    customise: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """v1.1 (T-05): the trace Typer prints when the CLI fails must not show local variables."""
    fixed = _fixed_generator_container(["48210937"])

    def drop_table_after_composing(container: CliContainer) -> dict[str, Any]:
        with container.engine.begin() as conn:
            conn.execute(text("DROP TABLE driver_code"))
        return fixed(container)

    customise(change=drop_table_after_composing)
    # Call the app as the `avisabus` binary does (`CliRunner` skips `Typer.__call__`, which
    # attaches the trace settings to the exception), and restore the hook it installs.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.delenv("TYPER_STANDARD_TRACEBACK", raising=False)
    monkeypatch.delenv("_TYPER_STANDARD_TRACEBACK", raising=False)
    with pytest.raises(OperationalError) as raised:
        app(["driver-codes", "create", "--label", "EtiquetaSensible"], prog_name="avisabus")
    error = raised.value
    # The failure happens while the plain code is still a local variable of the use case.
    assert any(local.get("plain_code") == "48210937" for local in _frame_locals(error))

    # Render the trace as the process does on exit: with the hook Typer has just installed.
    capsys.readouterr()
    sys.excepthook(type(error), error, error.__traceback__)
    trace = capsys.readouterr().err

    assert "OperationalError" in trace
    assert "48210937" not in trace
    assert "4821 0937" not in trace
    assert _expected_hash("48210937") not in trace
    assert "EtiquetaSensible" not in trace


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_the_cli_sets_show_locals_off_explicitly() -> None:
    """v1.1 (T-05): `False` is written in `cli/main.py`, not inherited from Typer's default."""
    source = Path(main_module.__file__).read_text(encoding="utf-8")
    assert re.search(r"pretty_exceptions_show_locals\s*=\s*False", source)
    assert app.pretty_exceptions_show_locals is False


@pytest.mark.spec("driver_codes_cli.AC-06")
@pytest.mark.usefixtures("real_logging")
def test_create_and_revoke_log_the_code_id_only() -> None:
    created = _create()
    code_id = _code_id(created)
    revoked = _run("revoke", code_id)
    assert revoked.exit_code == 0
    events = [
        event
        for event in _json_lines(created.stdout + revoked.stdout)
        if str(event["event"]).startswith("driver_code.")
    ]
    assert [event["event"] for event in events] == ["driver_code.created", "driver_code.revoked"]
    for event in events:
        assert event["code_id"] == code_id
        assert LABEL not in json.dumps(event)
        assert "label" not in event


# --- list -----------------------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-04")
def test_list_shows_the_table_without_code_nor_hash(db_path: Path, clock: FakeClock) -> None:
    created = _create()
    code_id = _code_id(created)
    clock.advance(timedelta(minutes=5))
    other_id = _code_id(_create("Conductor 12"))
    assert _run("revoke", other_id).exit_code == 0

    result = _run("list")

    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert lines[0].split() == ["CODE_ID", "ETIQUETA", "CREADO", "ESTADO", "TURNO"]
    assert lines[1].split() == [code_id, "Tablet", "3", "2026-11-09", "15:40", "activo", "no"]
    assert lines[2].split() == [
        other_id,
        "Conductor",
        "12",
        "2026-11-09",
        "15:45",
        "revocado",
        "no",
    ]
    plain = _plain_code(created)
    assert plain not in result.output
    assert f"{plain[:4]} {plain[4:]}" not in result.output
    for row in _rows(db_path):
        assert row["code_hash"] not in result.output


@pytest.mark.spec("driver_codes_cli.AC-04")
def test_list_aligns_the_columns_with_long_labels() -> None:
    _create("x" * 40)
    _create("y")
    lines = _run("list").stdout.splitlines()
    assert len({line.index("2026-11-09") for line in lines[1:]}) == 1
    assert lines[0].index("CREADO") == lines[1].index("2026-11-09")


@pytest.mark.spec("driver_codes_cli.AC-04")
def test_list_tells_when_a_code_has_an_open_shift(customise: Callable[..., None]) -> None:
    code_id = _code_id(_create())
    customise(change=_open_session_container({code_id}))
    lines = _run("list").stdout.splitlines()
    assert lines[1].split()[-1] == "sí"


@pytest.mark.spec("driver_codes_cli.AC-04")
def test_list_without_codes() -> None:
    result = _run("list")
    assert result.exit_code == 0
    assert "No hay códigos" in result.stdout


@pytest.mark.spec("driver_codes_cli.AC-04")
def test_list_as_json_has_the_same_information(
    db_path: Path, customise: Callable[..., None]
) -> None:
    created = _create()
    code_id = _code_id(created)
    customise(change=_open_session_container({code_id}))
    other_id = _code_id(runner.invoke(app, ["driver-codes", "create", "--label", "Conductor 12"]))
    assert _run("revoke", other_id).exit_code == 0

    result = _run("list", "--json")

    assert result.exit_code == 0
    assert sorted(json.loads(result.stdout), key=lambda item: item["code_id"]) == sorted(
        [
            {
                "code_id": code_id,
                "label": LABEL,
                "created_at": "2026-11-09T15:40:00+00:00",
                "status": "activo",
                "has_open_session": True,
            },
            {
                "code_id": other_id,
                "label": "Conductor 12",
                "created_at": "2026-11-09T15:40:00+00:00",
                "status": "revocado",
                "has_open_session": False,
            },
        ],
        key=lambda item: str(item["code_id"]),
    )
    plain = _plain_code(created)
    assert plain not in result.output
    for row in _rows(db_path):
        assert row["code_hash"] not in result.output


@pytest.mark.spec("driver_codes_cli.AC-04")
def test_list_as_json_without_codes() -> None:
    result = _run("list", "--json")
    assert result.exit_code == 0
    assert json.loads(result.stdout) == []


@pytest.mark.spec("driver_codes_cli.AC-04")
@pytest.mark.usefixtures("real_logging")
def test_list_as_json_keeps_logs_out_of_stdout(customise: Callable[..., None]) -> None:
    customise(secret=None)  # the development secret logs a warning while composing the CLI
    _create()
    result = _run("list", "--json")
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 1
    assert "security.dev_stop_token_secret" in result.stderr


# --- revoke ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_marks_the_code_with_its_date(db_path: Path, clock: FakeClock) -> None:
    code_id = _code_id(_create())
    clock.advance(timedelta(hours=1))
    result = _run("revoke", code_id)
    assert result.exit_code == 0
    assert result.stdout.splitlines()[-1] == (
        f"Código {code_id} revocado. No tenía ningún turno abierto."
    )
    assert _rows(db_path)[0]["revoked_at"] == "2026-11-09T16:40:00+00:00"


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_reports_the_open_shift(customise: Callable[..., None]) -> None:
    code_id = _code_id(_create())
    customise(change=_open_session_container({code_id}))
    result = _run("revoke", code_id)
    assert result.exit_code == 0
    assert result.stdout.splitlines()[-1] == (
        f"Código {code_id} revocado. Tenía un turno abierto: se cerrará en menos de 1 minuto."
    )


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_of_an_unknown_code_exits_with_one(db_path: Path) -> None:
    _create()
    result = _run("revoke", "dc-nope00")
    assert result.exit_code == 1
    assert "dc-nope00" in result.stderr
    assert _rows(db_path)[0]["revoked_at"] is None


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_of_a_revoked_code_is_harmless(db_path: Path, clock: FakeClock) -> None:
    code_id = _code_id(_create())
    assert _run("revoke", code_id).exit_code == 0
    original = _rows(db_path)[0]["revoked_at"]
    clock.advance(timedelta(hours=1))
    result = _run("revoke", code_id)
    assert result.exit_code == 0
    assert "ya estaba revocado" in result.stderr
    assert _rows(db_path)[0]["revoked_at"] == original


@pytest.mark.spec("driver_codes_cli.AC-05")
@pytest.mark.usefixtures("real_logging")
def test_revoke_of_a_revoked_code_logs_nothing_new() -> None:
    code_id = _code_id(_create())
    assert _run("revoke", code_id).exit_code == 0
    again = _run("revoke", code_id)
    assert [e for e in _json_lines(again.stdout) if e["event"] == "driver_code.revoked"] == []


def _open_shift(db_path: Path, code_id: str) -> None:
    """A real row of `driver_session`: the commands below use the real composition."""
    engine = create_engine(_settings(db_path))
    try:
        SqliteDriverSessionRepository(engine).add(
            DriverSession(
                session_id="session-1",
                token_hash="f" * 64,
                code_id=code_id,
                started_at=NOW,
                service=None,
                position=None,
                progress_m=None,
                off_route=False,
                last_fix_at=None,
                last_seen_at=None,
            )
        )
    finally:
        engine.dispose()


@pytest.mark.spec("driver_session.AC-14")
def test_list_consults_the_real_open_sessions(db_path: Path) -> None:
    with_shift = _code_id(_create())
    without_shift = _code_id(_create("Tablet 4"))
    _open_shift(db_path, with_shift)

    by_id = {item["code_id"]: item for item in json.loads(_run("list", "--json").stdout)}

    assert by_id[with_shift]["has_open_session"] is True
    assert by_id[without_shift]["has_open_session"] is False


@pytest.mark.spec("driver_session.AC-14")
def test_revoke_consults_the_real_open_sessions(db_path: Path) -> None:
    code_id = _code_id(_create())
    _open_shift(db_path, code_id)
    result = _run("revoke", code_id)
    assert result.exit_code == 0
    assert result.stdout.splitlines()[-1] == (
        f"Código {code_id} revocado. Tenía un turno abierto: se cerrará en menos de 1 minuto."
    )


@pytest.mark.spec("driver_session.AC-14")
def test_revoke_without_an_open_session_does_not_announce_one() -> None:
    code_id = _code_id(_create())
    result = _run("revoke", code_id)
    assert result.exit_code == 0
    assert "No tenía ningún turno abierto." in result.stdout.splitlines()[-1]
