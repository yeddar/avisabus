"""`avisabus qr generate` with a temporary database imported from `gtfs_mini` (no network)."""

import asyncio
import csv
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from avisabus.adapters.inbound.cli import qr as qr_cli
from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.inbound.cli.main import app
from avisabus.adapters.outbound.security.hmac_stop_token import HmacStopTokenSigner
from avisabus.application.import_gtfs_feed import ImportGtfsFeedCommand
from avisabus.config import Settings
from avisabus.domain.ports.clock import Clock
from avisabus.domain.services.gtfs_text import clean_name
from tests.conftest import DEFAULT_NOW
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI, read_rows
from tests.support.qr import decode_image, decode_svg, open_png, parse_svg, svg_text_lines

runner = CliRunner()
SECRET = "qr-cli-test-secret-0123456789abcdef"  # noqa: S105 (test-only secret)
BASE_URL = "https://avisabus.example/"
SIGNER = HmacStopTokenSigner(SECRET.encode())
INDEX_HEADER = ["stop_id", "name", "url", "file"]


def _settings(db: Path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        env="test",
        database_url=f"sqlite:///{db}",
        public_base_url=BASE_URL,
        stop_token_secret=SECRET,
    )


@pytest.fixture(scope="module")
def imported_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Database with `gtfs_mini` imported once per module (the `qr` command only reads it)."""
    db = tmp_path_factory.mktemp("qr_db") / "avisabus.sqlite"
    container = build_cli_container(_settings(db), FakeClock(DEFAULT_NOW))
    try:
        asyncio.run(container.import_gtfs_feed.execute(ImportGtfsFeedCommand(GTFS_MINI)))
    finally:
        container.close()
    return db


def _use_db(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    def build(_ignored: Settings, _clock: Clock) -> CliContainer:
        return build_cli_container(_settings(db), FakeClock(DEFAULT_NOW))

    monkeypatch.setattr(qr_cli, "build_cli_container", build)
    monkeypatch.setattr(qr_cli, "configure_logging", lambda _level: None)


@pytest.fixture
def with_feed(monkeypatch: pytest.MonkeyPatch, imported_db: Path) -> Iterator[None]:
    _use_db(monkeypatch, imported_db)
    yield


@pytest.fixture
def without_feed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    _use_db(monkeypatch, tmp_path / "empty.sqlite")
    yield


def _run(*args: str) -> Result:
    return runner.invoke(app, ["qr", "generate", *args], prog_name="avisabus")


def _url(stop_id: str) -> str:
    return f"https://avisabus.example/p/{stop_id}?t={SIGNER.sign(stop_id)}"


def _index(out: Path) -> list[list[str]]:
    with (out / "index.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh))


def _gtfs_mini_names() -> dict[str, str]:
    """Stop names as the feed gives them, trimmed like on import (gtfs_import RF-32)."""
    rows = read_rows(GTFS_MINI / "stops.txt")
    header = rows[0]
    stop_id, name = header.index("stop_id"), header.index("stop_name")
    return {row[stop_id]: clean_name(row[name]) for row in rows[1:]}


@pytest.mark.spec("stop_tokens_qr.AC-07")
@pytest.mark.usefixtures("with_feed")
def test_single_stop_writes_an_svg_with_the_url_and_the_label(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = _run("--stop", "508", "--out", str(out))
    assert result.exit_code == 0, result.output
    data = (out / "508.svg").read_bytes()
    (decoded,) = decode_svg(data)
    assert decoded.text == _url("508")
    assert svg_text_lines(parse_svg(data)) == [["Parc de l'Oest - Enguera"], ["Parada 508"]]


@pytest.mark.spec("stop_tokens_qr.AC-07")
@pytest.mark.usefixtures("with_feed")
def test_output_directory_defaults_to_qr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = _run("--stop", "508")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "qr" / "508.svg").is_file()


@pytest.mark.spec("stop_tokens_qr.AC-08")
@pytest.mark.usefixtures("with_feed")
def test_several_stops_write_one_file_each_and_an_index(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = _run("--stop", "508", "--stop", "1990", "--stop", "347", "--out", str(out))
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out.iterdir()) == ["1990.svg", "347.svg", "508.svg", "index.csv"]
    assert _index(out) == [
        INDEX_HEADER,
        ["508", "Parc de l'Oest - Enguera", _url("508"), "508.svg"],
        ["1990", "Alfauir - Estadi Ciutat de València", _url("1990"), "1990.svg"],
        ["347", "Menéndez Pidal - Pasarel·la", _url("347"), "347.svg"],
    ]
    (decoded,) = decode_svg((out / "1990.svg").read_bytes())
    assert decoded.text == _url("1990")


@pytest.mark.spec("stop_tokens_qr.AC-08")
@pytest.mark.usefixtures("with_feed")
def test_index_is_utf8_with_the_documented_header(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert _run("--stop", "1990", "--out", str(out)).exit_code == 0
    raw = (out / "index.csv").read_bytes()
    assert raw.startswith(b"stop_id,name,url,file\r\n")
    assert "València".encode() in raw


@pytest.mark.spec("stop_tokens_qr.AC-08")
@pytest.mark.usefixtures("with_feed")
def test_all_writes_every_stop_of_the_active_feed(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = _run("--all", "--out", str(out))
    assert result.exit_code == 0, result.output
    names = _gtfs_mini_names()
    header, *rows = _index(out)
    assert header == INDEX_HEADER
    assert len(rows) == len(names) == 178
    assert {row[0]: row[1] for row in rows} == names
    assert all(row[2] == _url(row[0]) and row[3] == f"{row[0]}.svg" for row in rows)
    assert sorted(p.name for p in out.glob("*.svg")) == sorted(f"{s}.svg" for s in names)


@pytest.mark.spec("stop_tokens_qr.AC-09")
@pytest.mark.usefixtures("with_feed")
def test_png_format_writes_a_600_px_qr_with_the_label(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = _run("--stop", "508", "--format", "png", "--out", str(out))
    assert result.exit_code == 0, result.output
    image = open_png((out / "508.png").read_bytes())
    width, height = image.size
    assert width >= 600
    assert height > width  # label band below the QR
    (decoded,) = decode_image(image.crop((0, 0, width, width)))
    assert decoded.text == _url("508")
    band = image.convert("L").crop((0, width, width, height))
    assert band.getextrema()[0] < 128  # the label is drawn
    assert _index(out)[1] == ["508", "Parc de l'Oest - Enguera", _url("508"), "508.png"]
    assert not (out / "508.svg").exists()


@pytest.mark.spec("stop_tokens_qr.AC-10")
@pytest.mark.usefixtures("with_feed")
def test_missing_stop_is_reported_others_are_generated_and_exit_code_is_2(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = _run("--stop", "508", "--stop", "9999", "--stop", "64", "--out", str(out))
    assert result.exit_code == 2
    assert "ERROR: parada 9999 no existe" in result.stderr
    assert sorted(p.name for p in out.iterdir()) == ["508.svg", "64.svg", "index.csv"]
    assert [row[0] for row in _index(out)[1:]] == ["508", "64"]


@pytest.mark.spec("stop_tokens_qr.AC-10")
@pytest.mark.usefixtures("with_feed")
def test_every_missing_stop_is_reported(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = _run("--stop", "9999", "--stop", "0", "--out", str(out))
    assert result.exit_code == 2
    assert "ERROR: parada 9999 no existe" in result.stderr
    assert "ERROR: parada 0 no existe" in result.stderr
    assert not list(out.glob("*.svg"))


@pytest.mark.spec("stop_tokens_qr.AC-11")
@pytest.mark.usefixtures("without_feed")
@pytest.mark.parametrize("selection", [["--stop", "508"], ["--all"]])
def test_without_a_feed_exits_1_and_writes_nothing(tmp_path: Path, selection: list[str]) -> None:
    out = tmp_path / "out"
    result = _run(*selection, "--out", str(out))
    assert result.exit_code == 1
    assert "No hay ningún feed importado" in result.output
    assert not out.exists()


@pytest.mark.usefixtures("with_feed")
@pytest.mark.parametrize(
    "args", [[], ["--stop", "508", "--all"]], ids=["no selection", "stop and all"]
)
def test_stop_and_all_are_mutually_exclusive_and_one_is_required(
    tmp_path: Path, args: list[str]
) -> None:
    out = tmp_path / "out"
    result = _run(*args, "--out", str(out))
    assert result.exit_code != 0
    assert "--stop" in result.output
    assert not out.exists()
