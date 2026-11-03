"""Parser of the SAE `QR.php` page (sae_arrivals_source design §4).

`parse_qrphp_html` is a pure function over the raw body, shared by the HTTP and the replay
sources so that recorded sessions exercise the production code. The page is a jQuery Mobile
fragment: a header `<div style="background: grey…">{stop_id} - {name}</div>` and, per arrival,
an `<img title="{line}">` followed by a `<span>` with `"{destination} - {time}"`. The time is
`{N} min.`, `Próximo`, `HH:MM` or `HH:MM:SS` (seen at night, v1.3); an entry with no time at all
(`"{destination} -"`, seen at termini at the end of the service) is discarded silently (AC-23).
"""

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from html.parser import HTMLParser
from types import MappingProxyType
from zoneinfo import ZoneInfo

import structlog

from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival

MADRID = ZoneInfo("Europe/Madrid")
CLOCK_TIME_TOLERANCE = timedelta(minutes=5)
"""A `HH:MM[:SS]` up to this much before `fetched_at` is still today's (AC-03)."""

SEPARATOR = " - "
WITHOUT_TIME_SUFFIX = " -"
_HEADER_STYLE = re.compile(r"background\s*:\s*grey", re.IGNORECASE)
_MINUTES = re.compile(r"(\d+) min\.?")
_CLOCK_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
_NEXT = "proximo"
_ICON_CLASS = "imagenParada"
_MAX_REASON_TEXT = 60

log = structlog.get_logger(__name__)


class SaeUnparseableError(Exception):
    """The whole body cannot be interpreted (e.g. no valid stop header, AC-21)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"unparseable SAE page ({detail})")


@dataclass(frozen=True, slots=True)
class ParseResult:
    arrivals: tuple[SaeArrival, ...]
    skipped: tuple[str, ...]
    """Reasons of the discarded entries (AC-06); never the whole body."""
    without_time: tuple[str, ...] = ()
    """Lines of the entries discarded because they carry no time (AC-23); not `skipped`."""


Parser = Callable[[bytes, str, datetime], ParseResult]


def parse_qrphp_html(body: bytes, stop_id: str, fetched_at: datetime) -> ParseResult:
    """Normalise a `QR.php` page; raises `SaeUnparseableError` if it is not a page of `stop_id`."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise SaeUnparseableError("not utf-8") from None
    page = _QrPhpPage()
    page.feed(text)
    page.close()
    header = (page.header or "").strip()
    if not re.fullmatch(rf"{re.escape(stop_id)} - .+", header, re.DOTALL):
        raise SaeUnparseableError("missing stop header" if not header else "header mismatch")

    arrivals: list[SaeArrival] = []
    skipped: list[str] = []
    without_time: list[str] = []
    for line, entry_text in page.entries:
        arrival = _arrival(line, entry_text, fetched_at)
        if isinstance(arrival, SaeArrival):
            arrivals.append(arrival)
        elif isinstance(arrival, _WithoutTime):
            without_time.append(arrival.line)
        else:
            skipped.append(arrival)
    return ParseResult(
        arrivals=tuple(arrivals), skipped=tuple(skipped), without_time=tuple(without_time)
    )


PARSERS: Mapping[str, Parser] = MappingProxyType({"qrphp_html": parse_qrphp_html})
"""Parser of each recorded `source_format` (AC-22)."""


def build_snapshot(
    parser: Parser, body: bytes, stop_id: str, fetched_at: datetime
) -> ArrivalsSnapshot:
    """Parse `body` into a snapshot, logging `sae.unparsed_entry` for each skipped entry.

    Entries without time are only logged as `sae.entry_without_time` at debug level (AC-23).

    Raises `ArrivalsUnavailableError(stop_id, "unparseable")` when the whole body is not valid.
    """
    try:
        result = parser(body, stop_id, fetched_at)
    except SaeUnparseableError:
        raise ArrivalsUnavailableError(stop_id, "unparseable") from None
    for reason in result.skipped:
        log.warning("sae.unparsed_entry", stop_id=stop_id, reason=reason)
    for line in result.without_time:
        log.debug("sae.entry_without_time", stop_id=stop_id, line=line)
    return ArrivalsSnapshot(stop_id=stop_id, fetched_at=fetched_at, arrivals=result.arrivals)


@dataclass(frozen=True, slots=True)
class _WithoutTime:
    line: str


def _arrival(
    line: str, entry_text: str | None, fetched_at: datetime
) -> SaeArrival | _WithoutTime | str:
    """The normalised arrival, an entry without time, or the reason why the entry is skipped."""
    line = line.strip()
    if not line:
        return "entry without line"
    if entry_text is None:
        return "entry without text"
    text = entry_text.strip()
    if text.endswith(WITHOUT_TIME_SUFFIX):  # "{destination} -" (AC-23)
        return _WithoutTime(line)
    if SEPARATOR not in text:
        return f"no separator in {_short(text)}"
    destination, raw_time = text.rsplit(SEPARATOR, 1)
    destination, raw_time = destination.strip(), raw_time.strip()

    if minutes_match := _MINUTES.fullmatch(raw_time):
        minutes = int(minutes_match.group(1))
        return _minutes(line, destination, minutes, fetched_at)
    if _fold(raw_time) == _NEXT:
        return _minutes(line, destination, 0, fetched_at)
    if clock_match := _CLOCK_TIME.fullmatch(raw_time):
        hour, minute = int(clock_match.group(1)), int(clock_match.group(2))
        second = int(clock_match.group(3) or 0)
        if hour > 23 or minute > 59 or second > 59:
            return f"invalid clock time {_short(raw_time)}"
        return SaeArrival(
            line=line,
            destination=destination,
            kind=ArrivalKind.CLOCK_TIME,
            minutes=None,
            arrival_at=_next_occurrence(time(hour, minute, second), fetched_at),
        )
    return f"unrecognised time {_short(raw_time)}"


def _minutes(line: str, destination: str, minutes: int, fetched_at: datetime) -> SaeArrival:
    return SaeArrival(
        line=line,
        destination=destination,
        kind=ArrivalKind.MINUTES,
        minutes=minutes,
        arrival_at=fetched_at + timedelta(minutes=minutes),
    )


def _next_occurrence(local: time, fetched_at: datetime) -> datetime:
    """First occurrence of `local` (Europe/Madrid) not earlier than `fetched_at − 5 min` (AC-03)."""
    threshold = fetched_at - CLOCK_TIME_TOLERANCE
    day = threshold.astimezone(MADRID).date()
    candidate = _at(day, local)
    if candidate < threshold:
        candidate = _at(day + timedelta(days=1), local)
    return candidate


def _at(day: date, local: time) -> datetime:
    return datetime.combine(day, local, tzinfo=MADRID).astimezone(UTC)


def _fold(value: str) -> str:
    """Case- and accent-insensitive form (`Próximo` → `proximo`)."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _short(text: str) -> str:
    return repr(text[:_MAX_REASON_TEXT])


def _is_icon(attrs: list[tuple[str, str | None]]) -> bool:
    """The `<span class="imagenParada">` that wraps the line icon is not the entry text."""
    return _ICON_CLASS in (dict(attrs).get("class") or "").split()


class _QrPhpPage(HTMLParser):
    """Collects the header text and the `(line, text)` of each arrival entry."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.header: str | None = None
        self.entries: list[tuple[str, str | None]] = []
        self._header_depth = 0
        self._header_chunks: list[str] = []
        self._pending_line: str | None = None
        self._text_depth = 0
        self._text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._header_depth:
            if tag == "div":
                self._header_depth += 1
            return
        if self.header is None:
            style = dict(attrs).get("style") or ""
            if tag == "div" and _HEADER_STYLE.search(style):
                self._header_depth = 1
            return
        if self._text_depth:
            if tag == "span":
                self._text_depth += 1
            return
        title = dict(attrs).get("title")
        if tag == "img" and title is not None:
            if self._pending_line is not None:
                self.entries.append((self._pending_line, None))
            self._pending_line = title
        elif tag == "span" and self._pending_line is not None and not _is_icon(attrs):
            self._text_depth = 1
            self._text_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if self._header_depth:
            if tag == "div":
                self._header_depth -= 1
                if not self._header_depth:
                    self.header = "".join(self._header_chunks)
            return
        if self._text_depth and tag == "span":
            self._text_depth -= 1
            if not self._text_depth and self._pending_line is not None:
                self.entries.append((self._pending_line, "".join(self._text_chunks)))
                self._pending_line = None

    def handle_data(self, data: str) -> None:
        if self._header_depth:
            self._header_chunks.append(data)
        elif self._text_depth:
            self._text_chunks.append(data)

    def close(self) -> None:
        super().close()
        if self._header_depth:  # unterminated header block
            self.header = "".join(self._header_chunks)
        if self._pending_line is not None:
            self.entries.append((self._pending_line, None))
            self._pending_line = None
