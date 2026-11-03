"""`SegnoQrRenderer`: SVG and PNG with label, decoded back with zxing-cpp."""

import csv
from importlib import resources
from typing import Any

import pytest
import segno
from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageFont

from avisabus.adapters.outbound.qr import segno_renderer
from avisabus.adapters.outbound.qr.segno_renderer import SegnoQrRenderer
from avisabus.domain.ports.qr import QrFormat, QrLabel, QrRenderer, QrRequest
from tests.support.gtfs import GTFS_MINI
from tests.support.qr import decode_image, decode_svg, open_png, parse_svg, svg_text_lines

URL = "http://localhost:5173/p/508?t=83Rg_QTPgamZSDGo9T168g"
LABEL = QrLabel(title="Parc de l'Oest - Enguera", subtitle="Parada 508")
LONG_NAME = "Institut Obrer de València (imparell) - Amado Granell Mesado"
QUIET_ZONE = 4


def _render(fmt: QrFormat, label: QrLabel = LABEL, content: str = URL) -> bytes:
    renderer: QrRenderer = SegnoQrRenderer()
    return renderer.render(QrRequest(content=content, label=label, format=fmt))


def _dark_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = ImageChops.invert(image.convert("L")).getbbox()
    assert bbox is not None
    return bbox


@pytest.mark.spec("stop_tokens_qr.AC-07")
def test_svg_encodes_the_url() -> None:
    (decoded,) = decode_svg(_render("svg"))
    assert decoded.text == URL


@pytest.mark.spec("stop_tokens_qr.AC-07")
def test_svg_label_shows_name_and_stop_code_below_the_qr() -> None:
    svg = parse_svg(_render("svg"))
    assert svg_text_lines(svg) == [["Parc de l'Oest - Enguera"], ["Parada 508"]]
    texts = svg.root.findall("{http://www.w3.org/2000/svg}text")
    title_y = float(texts[0].attrib.get("y") or texts[0][0].attrib["y"])
    assert svg.size_px < title_y < float(texts[1].attrib["y"]) <= float(svg.root.attrib["height"])
    assert [t.attrib["font-size"] for t in texts] == ["28", "22"]
    assert all(t.attrib["font-family"] == "sans-serif" for t in texts)
    assert all(t.attrib["text-anchor"] == "middle" for t in texts)


@pytest.mark.spec("stop_tokens_qr.AC-07")
def test_svg_label_text_is_escaped() -> None:
    label = QrLabel(title='Pl. <Ajuntament> & "Correus"', subtitle="Parada 1")
    svg = parse_svg(_render("svg", label))  # would not parse if not escaped
    title_lines, subtitle_lines = svg_text_lines(svg)
    assert " ".join(title_lines) == 'Pl. <Ajuntament> & "Correus"'
    assert subtitle_lines == ["Parada 1"]


@pytest.mark.spec("stop_tokens_qr.AC-07")
def test_svg_long_names_are_wrapped_inside_the_label() -> None:
    svg = parse_svg(_render("svg", QrLabel(title=LONG_NAME, subtitle="Parada 1234")))
    title_lines, subtitle_lines = svg_text_lines(svg)
    assert len(title_lines) > 1
    assert " ".join(title_lines) == LONG_NAME
    assert subtitle_lines == ["Parada 1234"]


@pytest.mark.spec("stop_tokens_qr.AC-07")
def test_svg_uses_segno_at_scale_10_on_a_white_background() -> None:
    svg = parse_svg(_render("svg"))
    assert svg.scale == 10
    assert svg.root.attrib["width"] == str(svg.size_px)
    assert int(svg.root.attrib["height"]) > svg.size_px
    background = svg.root.find("{http://www.w3.org/2000/svg}rect")
    assert background is not None
    assert background.attrib["fill"] == "#fff"


@pytest.mark.spec("stop_tokens_qr.AC-09")
def test_png_qr_is_at_least_600_px_and_decodes_to_the_url() -> None:
    image = open_png(_render("png"))
    width, height = image.size
    assert width >= 600
    qr_area = image.crop((0, 0, width, width))
    (decoded,) = decode_image(qr_area)
    assert decoded.text == URL
    assert height > width  # label band below the QR


@pytest.mark.spec("stop_tokens_qr.AC-09")
def test_png_has_a_label_band_with_text() -> None:
    image = open_png(_render("png")).convert("L")
    width, height = image.size
    band = image.crop((0, width, width, height))
    assert band.getextrema()[0] < 128  # there is dark text
    other = open_png(_render("png", QrLabel(title="Altra parada", subtitle="Parada 9"))).convert(
        "L"
    )
    other_band = other.crop((0, width, width, other.size[1]))
    assert band.size != other_band.size or ImageChops.difference(band, other_band).getbbox()


@pytest.mark.spec("stop_tokens_qr.AC-09")
def test_png_long_name_text_stays_inside_the_image() -> None:
    image = open_png(_render("png", QrLabel(title=LONG_NAME, subtitle="Parada 1234"))).convert("L")
    width, height = image.size
    left, _, right, bottom = _dark_bbox(image.crop((0, width, width, height)))
    assert left > 0
    assert right < width
    assert bottom < height - width


@pytest.mark.spec("stop_tokens_qr.AC-12")
def test_segno_is_called_with_level_m_and_no_micro_qr(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    real_make = segno.make

    def spy(content: str, **kwargs: Any) -> segno.QRCode:
        calls.append({"content": content, **kwargs})
        return real_make(content, **kwargs)

    monkeypatch.setattr(segno_renderer.segno, "make", spy)
    _render("svg")
    _render("png")
    expected = {"content": URL, "error": "m", "micro": False, "boost_error": False}
    assert calls == [expected, expected]


@pytest.mark.spec("stop_tokens_qr.AC-12")
@pytest.mark.parametrize("fmt", ["svg", "png"])
def test_error_correction_level_is_m(fmt: QrFormat) -> None:
    # segno's default `boost_error=True` would raise this content to level Q.
    data = _render(fmt, content="http://avisa.es/p/5?t=AAAAAAAAAAAAAAAAAAAAAA")
    image = open_png(data) if fmt == "png" else None
    decoded = (
        decode_image(image.crop((0, 0, image.width, image.width))) if image else decode_svg(data)
    )
    assert [d.ec_level for d in decoded] == ["M"]


@pytest.mark.spec("stop_tokens_qr.AC-12")
def test_svg_has_a_quiet_zone_of_4_modules() -> None:
    svg = parse_svg(_render("svg"))
    size = len(svg.modules)
    expected = segno.make(URL, error="m", micro=False, boost_error=False).symbol_size(border=4)
    assert (size, size) == expected
    dark_rows = [r for r, line in enumerate(svg.modules) if any(line)]
    dark_cols = [c for c in range(size) if any(line[c] for line in svg.modules)]
    assert (dark_rows[0], dark_rows[-1]) == (QUIET_ZONE, size - 1 - QUIET_ZONE)
    assert (dark_cols[0], dark_cols[-1]) == (QUIET_ZONE, size - 1 - QUIET_ZONE)


@pytest.mark.spec("stop_tokens_qr.AC-12")
def test_png_has_a_quiet_zone_of_4_modules() -> None:
    image = open_png(_render("png"))
    width = image.size[0]
    modules = segno.make(URL, error="m", micro=False, boost_error=False).symbol_size(border=4)[0]
    module_px = width // modules
    assert module_px * modules == width
    left, top, right, bottom = _dark_bbox(image.crop((0, 0, width, width)))
    assert (left, top) == (QUIET_ZONE * module_px, QUIET_ZONE * module_px)
    assert (right, bottom) == (width - QUIET_ZONE * module_px, width - QUIET_ZONE * module_px)


FONTS = resources.files("avisabus.adapters.outbound.qr") / "fonts"


def _gtfs_mini_stop_names() -> list[str]:
    with (GTFS_MINI / "stops.txt").open(encoding="utf-8-sig", newline="") as fh:
        return [row["stop_name"] for row in csv.DictReader(fh)]


@pytest.mark.spec("stop_tokens_qr.AC-13")
def test_bundled_font_has_a_glyph_for_every_character_of_gtfs_mini_stop_names() -> None:
    characters = set("".join(_gtfs_mini_stop_names()))
    # The fixture does exercise the characters Pillow's default font cannot draw.
    assert {"à", "è", "é", "í", "ò", "ó", "ñ", "ç", "·", "À", "Á"} <= characters
    cmap = TTFont(FONTS / "DejaVuSans.ttf").getBestCmap()
    missing = sorted(c for c in characters if ord(c) not in cmap)
    assert missing == []


@pytest.mark.spec("stop_tokens_qr.AC-13")
def test_dejavu_license_is_shipped_next_to_the_font() -> None:
    license_text = (FONTS / "LICENSE-DejaVu.txt").read_text(encoding="utf-8")
    assert "Bitstream Vera Fonts Copyright" in license_text
    assert "DejaVu changes are in public domain" in license_text


@pytest.mark.spec("stop_tokens_qr.AC-13")
def test_png_label_is_always_drawn_with_the_bundled_font(monkeypatch: pytest.MonkeyPatch) -> None:
    bundled = (FONTS / "DejaVuSans.ttf").read_bytes()
    loaded: list[bytes] = []
    real_truetype = ImageFont.truetype

    def spy(font: Any, size: float, *args: Any, **kwargs: Any) -> ImageFont.FreeTypeFont:
        loaded.append(font.getvalue() if hasattr(font, "getvalue") else font)
        return real_truetype(font, size, *args, **kwargs)

    def no_default(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Pillow's default font must not be used")

    monkeypatch.setattr(segno_renderer.ImageFont, "truetype", spy)
    monkeypatch.setattr(segno_renderer.ImageFont, "load_default", no_default)
    _render("png", QrLabel(title="Pasarel·la", subtitle="Parada 347"))
    assert loaded
    assert all(font == bundled for font in loaded)


@pytest.mark.spec("stop_tokens_qr.AC-13")
def test_png_label_draws_distinct_accented_letters() -> None:
    # A font without these glyphs draws the same "missing glyph" box for all of them.
    bands = []
    for title in ("Valencia", "València", "Valéncia", "Calassanç", "Calassanc"):
        image = open_png(_render("png", QrLabel(title=title, subtitle="Parada 1"))).convert("L")
        bands.append(image.crop((0, image.width, image.width, image.height)).tobytes())
    assert len(set(bands)) == len(bands)
