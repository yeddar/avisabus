"""QR codes with segno: SVG (default) or PNG, with the stop label below (design §5).

Error correction level M (`boost_error=False`, so segno never raises it) and a quiet zone of
4 modules (AC-12). Long stop names are wrapped into several lines (layout is a local decision).
The PNG label is always drawn with the bundled DejaVu Sans (`fonts/`, with its licence), never
with system fonts, so every stop name renders the same on any machine (AC-13).
"""

import functools
import html
import io
import math
import textwrap
from importlib import resources

import segno
from PIL import Image, ImageDraw, ImageFont

from avisabus.domain.ports.qr import QrLabel, QrRequest

BORDER = 4
SVG_SCALE = 10
SVG_TITLE_PX = 28
SVG_SUBTITLE_PX = 22
SVG_CHAR_WIDTH_EM = 0.5
"""Average glyph width of a sans-serif font (in em), used to wrap the SVG title."""

PNG_MIN_QR_PX = 600
PNG_TITLE_RATIO = 0.065
PNG_SUBTITLE_RATIO = 0.052
"""Font sizes of the PNG label relative to the QR side (40 px and 32 px for 615 px)."""

FONT_PACKAGE = "avisabus.adapters.outbound.qr"
FONT_FILE = "fonts/DejaVuSans.ttf"
"""DejaVu Sans 2.37, shipped as package data next to `fonts/LICENSE-DejaVu.txt`."""

Font = ImageFont.FreeTypeFont


class SegnoQrRenderer:
    def render(self, request: QrRequest) -> bytes:
        qr = segno.make(request.content, error="m", micro=False, boost_error=False)
        if request.format == "png":
            return _render_png(qr, request.label)
        return _render_svg(qr, request.label)


def _render_svg(qr: segno.QRCode, label: QrLabel) -> bytes:
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=SVG_SCALE, border=BORDER, xmldecl=False, svgns=False)
    qr_svg = buffer.getvalue().decode("utf-8")
    side, _ = qr.symbol_size(scale=SVG_SCALE, border=BORDER)

    margin = SVG_SCALE * BORDER // 2
    max_chars = max(1, int((side - 2 * margin) / (SVG_TITLE_PX * SVG_CHAR_WIDTH_EM)))
    title_lines = textwrap.wrap(label.title, width=max_chars) or [""]
    title_line_px = round(SVG_TITLE_PX * 1.25)
    first_baseline = side + SVG_TITLE_PX
    subtitle_baseline = first_baseline + (len(title_lines) - 1) * title_line_px + SVG_TITLE_PX
    height = subtitle_baseline + SVG_SUBTITLE_PX
    center = side // 2

    spans = "".join(
        f'<tspan x="{center}" y="{first_baseline + i * title_line_px}">{_escape(line)}</tspan>'
        for i, line in enumerate(title_lines)
    )
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" height="{height}" '
        f'viewBox="0 0 {side} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        qr_svg,
        f'<text font-size="{SVG_TITLE_PX}" font-family="sans-serif" text-anchor="middle" '
        f'fill="#000">{spans}</text>',
        f'<text x="{center}" y="{subtitle_baseline}" font-size="{SVG_SUBTITLE_PX}" '
        f'font-family="sans-serif" text-anchor="middle" fill="#000">'
        f"{_escape(label.subtitle)}</text>",
        "</svg>",
    ]
    return ("\n".join(parts) + "\n").encode("utf-8")


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _render_png(qr: segno.QRCode, label: QrLabel) -> bytes:
    modules, _ = qr.symbol_size(scale=1, border=BORDER)
    scale = math.ceil(PNG_MIN_QR_PX / modules)
    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=scale, border=BORDER)
    qr_image = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")
    side = qr_image.width

    title_font = _font(round(side * PNG_TITLE_RATIO))
    subtitle_font = _font(round(side * PNG_SUBTITLE_RATIO))
    margin = scale * BORDER // 2
    measure = ImageDraw.Draw(qr_image)
    title_lines = _wrap(measure, label.title, title_font, side - 2 * margin)
    title_line_px = _line_height(title_font)
    subtitle_line_px = _line_height(subtitle_font)
    band = len(title_lines) * title_line_px + subtitle_line_px + 2 * margin

    image = Image.new("RGB", (side, side + band), "white")
    image.paste(qr_image, (0, 0))
    draw = ImageDraw.Draw(image)
    y = side + margin // 2
    for line in title_lines:
        draw.text((side / 2, y), line, fill="black", font=title_font, anchor="ma")
        y += title_line_px
    draw.text((side / 2, y), label.subtitle, fill="black", font=subtitle_font, anchor="ma")

    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


@functools.cache
def _font_bytes() -> bytes:
    return resources.files(FONT_PACKAGE).joinpath(FONT_FILE).read_bytes()


def _font(size: int) -> Font:
    return ImageFont.truetype(io.BytesIO(_font_bytes()), size)


def _line_height(font: Font) -> int:
    _, top, _, bottom = font.getbbox("ÀÉgjpqy")
    return math.ceil((bottom - top) * 1.3)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: Font, max_px: int) -> list[str]:
    """Greedy word wrap measured with the real font."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and draw.textlength(candidate, font=font) > max_px:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    return lines
