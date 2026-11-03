"""`parse_qrphp_html` over the real and derived QR.php samples (sae_arrivals_source T-03, T-14)."""

from datetime import UTC, datetime, timedelta

import pytest
from structlog.testing import capture_logs

from avisabus.adapters.outbound.sae.qrphp_parser import (
    PARSERS,
    ParseResult,
    SaeUnparseableError,
    build_snapshot,
    parse_qrphp_html,
)
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalKind, SaeArrival
from tests.support.sae import (
    NIGHT,
    STOP_508_MINUTES,
    STOP_508_NO_ARRIVALS,
    STOP_2070_NEXT,
    STOP_2070_NIGHT,
    STOP_2312_WITHOUT_TIME,
    STOP_99999_UNKNOWN,
    recording_json,
    replace_once,
)

FETCHED_AT = datetime(2026, 11, 2, 11, 0, 11, tzinfo=UTC)  # 12:00:11 in Madrid (UTC+1)
SECOND_ENTRY = (
    'title="70" width="25px" height="25px"></span>'
    '<span style="position: relative; top: -5px;">&nbsp;&nbsp;Alboraia - 8 min.'
)


def _minutes(line: str, destination: str, minutes: int) -> SaeArrival:
    return SaeArrival(
        line=line,
        destination=destination,
        kind=ArrivalKind.MINUTES,
        minutes=minutes,
        arrival_at=FETCHED_AT + timedelta(minutes=minutes),
    )


NIGHT_2070_AT = datetime.fromisoformat(recording_json(NIGHT, "2070", 0)["captured_at"])
NIGHT_2312_AT = datetime.fromisoformat(recording_json(NIGHT, "2312", 6)["captured_at"])
LAST_NIGHT_ENTRY = "La Malva-rosa - 01:52:28"


def _clock_time(text: str, fetched_at: datetime) -> datetime:
    body = replace_once(STOP_2070_NIGHT, LAST_NIGHT_ENTRY, f"La Malva-rosa - {text}")
    arrival = parse_qrphp_html(body, "2070", fetched_at).arrivals[-1]
    assert arrival.kind is ArrivalKind.CLOCK_TIME
    assert arrival.minutes is None
    return arrival.arrival_at


# --- AC-02: minutes ----------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-02")
def test_minutes_are_normalised_with_arrival_at_relative_to_fetched_at() -> None:
    result = parse_qrphp_html(STOP_508_MINUTES, "508", FETCHED_AT)
    assert result == ParseResult(
        arrivals=(
            _minutes("93", "Pass. Marítim", 5),
            _minutes("70", "Alboraia", 8),
            _minutes("93", "Pass. Marítim", 13),
            _minutes("70", "Alboraia", 20),
        ),
        skipped=(),
    )


@pytest.mark.spec("sae_arrivals_source.AC-02")
def test_minutes_without_final_dot_are_accepted() -> None:
    body = replace_once(STOP_508_MINUTES, "Alboraia - 8 min.", "Alboraia - 8 min")
    arrivals = parse_qrphp_html(body, "508", FETCHED_AT).arrivals
    assert arrivals[1] == _minutes("70", "Alboraia", 8)


@pytest.mark.spec("sae_arrivals_source.AC-02")
def test_arrival_at_is_utc() -> None:
    (first, *_) = parse_qrphp_html(STOP_508_MINUTES, "508", FETCHED_AT).arrivals
    assert first.arrival_at.utcoffset() == timedelta(0)


# --- AC-03: HH:MM and HH:MM:SS ----------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-03")
@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_real_night_clock_times_with_seconds_cross_midnight() -> None:
    # Real 2070 page at 23:32:01 in Madrid (Monday 2026-11-02): two HH:MM:SS of line 99.
    assert NIGHT_2070_AT.isoformat() == "2026-11-02T22:32:01.467466+00:00"
    result = parse_qrphp_html(STOP_2070_NIGHT, "2070", NIGHT_2070_AT)
    assert result == ParseResult(
        arrivals=(
            SaeArrival(
                line="73",
                destination="Sant Isidre",
                kind=ArrivalKind.MINUTES,
                minutes=10,
                arrival_at=NIGHT_2070_AT + timedelta(minutes=10),
            ),
            SaeArrival(
                line="99",
                destination="La Malva-rosa",
                kind=ArrivalKind.CLOCK_TIME,
                minutes=None,
                arrival_at=datetime(2026, 11, 2, 23, 42, 28, tzinfo=UTC),  # 00:42:28 on 3 Nov
            ),
            SaeArrival(
                line="99",
                destination="La Malva-rosa",
                kind=ArrivalKind.CLOCK_TIME,
                minutes=None,
                arrival_at=datetime(2026, 11, 3, 0, 52, 28, tzinfo=UTC),  # 01:52:28 on 3 Nov
            ),
        ),
        skipped=(),
    )


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_clock_time_is_the_same_day_in_madrid_when_still_ahead() -> None:
    fetched_at = datetime(2026, 11, 2, 11, 0, 11, tzinfo=UTC)  # 12:00:11 in Madrid (UTC+1)
    assert _clock_time("22:41", fetched_at) == datetime(2026, 11, 2, 21, 41, tzinfo=UTC)
    assert _clock_time("22:41:07", fetched_at) == datetime(2026, 11, 2, 21, 41, 7, tzinfo=UTC)


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_clock_time_keeps_the_seconds() -> None:
    fetched_at = datetime(2026, 11, 2, 22, 30, tzinfo=UTC)  # 23:30 in Madrid
    assert _clock_time("23:59:59", fetched_at) == datetime(2026, 11, 2, 22, 59, 59, tzinfo=UTC)
    assert _clock_time("00:00:01", fetched_at) == datetime(2026, 11, 2, 23, 0, 1, tzinfo=UTC)
    assert _clock_time("9:05:30", datetime(2026, 11, 2, 7, 0, tzinfo=UTC)) == datetime(
        2026, 11, 2, 8, 5, 30, tzinfo=UTC
    )


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_clock_time_with_seconds_up_to_five_minutes_in_the_past_stays_today() -> None:
    fetched_at = datetime(2026, 11, 2, 21, 45, 30, tzinfo=UTC)  # 22:45:30 in Madrid
    assert _clock_time("22:40:30", fetched_at) == datetime(2026, 11, 2, 21, 40, 30, tzinfo=UTC)
    assert _clock_time("22:40:29", fetched_at) == datetime(2026, 11, 3, 21, 40, 29, tzinfo=UTC)


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_clock_time_crosses_midnight_to_the_next_day() -> None:
    fetched_at = datetime(2026, 11, 2, 22, 50, tzinfo=UTC)  # 23:50 in Madrid
    assert _clock_time("00:10", fetched_at) == datetime(2026, 11, 2, 23, 10, tzinfo=UTC)


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_clock_time_up_to_five_minutes_in_the_past_is_not_moved_to_the_next_day() -> None:
    fetched_at = datetime(2026, 11, 2, 21, 45, tzinfo=UTC)  # 22:45 in Madrid
    assert _clock_time("22:41", fetched_at) == datetime(2026, 11, 2, 21, 41, tzinfo=UTC)
    assert _clock_time("22:40", fetched_at) == datetime(2026, 11, 2, 21, 40, tzinfo=UTC)
    assert _clock_time("22:39", fetched_at) == datetime(2026, 11, 3, 21, 39, tzinfo=UTC)


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_clock_time_just_before_midnight_seen_just_after_midnight_is_yesterday() -> None:
    fetched_at = datetime(2026, 11, 2, 23, 2, tzinfo=UTC)  # 00:02 on 3 Nov in Madrid
    assert _clock_time("23:59", fetched_at) == datetime(2026, 11, 2, 22, 59, tzinfo=UTC)


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_clock_time_uses_summer_time_in_madrid() -> None:
    fetched_at = datetime(2026, 7, 1, 20, 0, tzinfo=UTC)  # 22:00 in Madrid (UTC+2)
    assert _clock_time("22:41", fetched_at) == datetime(2026, 7, 1, 20, 41, tzinfo=UTC)


@pytest.mark.spec("sae_arrivals_source.AC-03")
def test_single_digit_hour_is_accepted() -> None:
    fetched_at = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)  # 08:00 in Madrid
    assert _clock_time("9:05", fetched_at) == datetime(2026, 11, 2, 8, 5, tzinfo=UTC)


# --- AC-04: Próximo ----------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-04")
def test_proximo_in_a_real_sample_is_zero_minutes() -> None:
    result = parse_qrphp_html(STOP_2070_NEXT, "2070", FETCHED_AT)
    assert result.skipped == ()
    assert len(result.arrivals) == 8
    assert result.arrivals[0] == SaeArrival(
        line="95",
        destination="Tres Creus",
        kind=ArrivalKind.MINUTES,
        minutes=0,
        arrival_at=FETCHED_AT,
    )


@pytest.mark.spec("sae_arrivals_source.AC-04")
@pytest.mark.parametrize("marker", ["PRÓXIMO", "proximo", "Proximo", "pRóXiMo"])
def test_proximo_ignores_case_and_accents(marker: str) -> None:
    body = replace_once(STOP_2070_NEXT, "Tres Creus - Próximo", f"Tres Creus - {marker}")
    first = parse_qrphp_html(body, "2070", FETCHED_AT).arrivals[0]
    assert (first.kind, first.minutes, first.arrival_at) == (ArrivalKind.MINUTES, 0, FETCHED_AT)


# --- AC-05: line and destination as given ------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-05")
def test_line_and_destination_are_kept_verbatim_but_trimmed() -> None:
    body = replace_once(STOP_508_MINUTES, SECOND_ENTRY, SECOND_ENTRY.replace('"70"', '"  C2 "'))
    body = replace_once(
        body, "&nbsp;&nbsp;Alboraia - 8 min.", "&nbsp; Est. del Nord&nbsp; - 8 min. "
    )
    second = parse_qrphp_html(body, "508", FETCHED_AT).arrivals[1]
    assert (second.line, second.destination, second.minutes) == ("C2", "Est. del Nord", 8)


@pytest.mark.spec("sae_arrivals_source.AC-05")
def test_destination_containing_the_separator_is_split_at_the_last_one() -> None:
    body = replace_once(STOP_508_MINUTES, "Alboraia - 8 min.", "Natzaret - Port - 8 min.")
    second = parse_qrphp_html(body, "508", FETCHED_AT).arrivals[1]
    assert (second.destination, second.minutes) == ("Natzaret - Port", 8)


@pytest.mark.spec("sae_arrivals_source.AC-05")
def test_html_entities_are_unescaped() -> None:
    body = replace_once(
        STOP_508_MINUTES, "Pass. Marítim - 5 min.", "Pass. Mar&iacute;tim &amp; Port - 5 min."
    )
    assert parse_qrphp_html(body, "508", FETCHED_AT).arrivals[0].destination == (
        "Pass. Marítim & Port"
    )


# --- AC-06: entries that cannot be interpreted -------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-06")
@pytest.mark.parametrize(
    ("new_text", "reason_fragment"),
    [
        ("Alboraia - Sin estimación", "Sin estimación"),  # unknown time marker
        ("Alboraia 8 min.", "no separator"),
        ("Alboraia - 25:61", "25:61"),  # not a valid clock time
        ("Alboraia - 22:41:60", "22:41:60"),  # not a valid clock time (seconds)
        ("Alboraia - 22:41:5", "22:41:5"),  # seconds need two digits
        ("Alboraia - 22:41:05:00", "22:41:05:00"),
        ("Alboraia - 8 minutos", "8 minutos"),
    ],
)
def test_uninterpretable_entry_is_skipped_and_the_rest_returned(
    new_text: str, reason_fragment: str
) -> None:
    body = replace_once(STOP_508_MINUTES, "Alboraia - 8 min.", new_text)
    result = parse_qrphp_html(body, "508", FETCHED_AT)
    assert [(a.line, a.minutes) for a in result.arrivals] == [("93", 5), ("93", 13), ("70", 20)]
    (reason,) = result.skipped
    assert reason_fragment in reason


@pytest.mark.spec("sae_arrivals_source.AC-06")
def test_entry_without_text_or_line_is_skipped() -> None:
    body = replace_once(STOP_508_MINUTES, SECOND_ENTRY, SECOND_ENTRY.replace('"70"', '" "'))
    result = parse_qrphp_html(body, "508", FETCHED_AT)
    assert len(result.arrivals) == 3
    assert len(result.skipped) == 1
    no_text = replace_once(
        STOP_508_MINUTES,
        '<span style="position: relative; top: -5px;">&nbsp;&nbsp;Pass. Marítim - 5 min.</span>',
        "",
    )
    result = parse_qrphp_html(no_text, "508", FETCHED_AT)
    assert len(result.arrivals) == 3
    assert len(result.skipped) == 1


@pytest.mark.spec("sae_arrivals_source.AC-06")
def test_skipped_entries_are_logged_with_stop_and_reason_but_not_the_body() -> None:
    body = replace_once(STOP_508_MINUTES, "Alboraia - 8 min.", "Alboraia - Sin estimación")
    with capture_logs() as logs:
        snapshot = build_snapshot(parse_qrphp_html, body, "508", FETCHED_AT)
    assert len(snapshot.arrivals) == 3
    (event,) = [log for log in logs if log["event"] == "sae.unparsed_entry"]
    assert event["stop_id"] == "508"
    assert "Sin estimación" in event["reason"]
    assert "Pass. Marítim" not in str(event)  # nothing else from the page
    assert "imagenParada" not in str(event)


# --- AC-07: no arrivals ------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-07")
@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_valid_page_without_arrivals_is_an_empty_list() -> None:
    assert parse_qrphp_html(STOP_508_NO_ARRIVALS, "508", FETCHED_AT) == ParseResult((), ())
    snapshot = build_snapshot(parse_qrphp_html, STOP_508_NO_ARRIVALS, "508", FETCHED_AT)
    assert (snapshot.stop_id, snapshot.fetched_at, snapshot.arrivals) == ("508", FETCHED_AT, ())


# --- AC-23: entries without time --------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-23")
@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_real_night_entries_without_time_are_discarded_but_not_unparsed() -> None:
    # Real 2312 page (terminus) at 23:32:08 in Madrid: 5 of its 6 entries are "{destination} -".
    result = parse_qrphp_html(STOP_2312_WITHOUT_TIME, "2312", NIGHT_2312_AT)
    assert result == ParseResult(
        arrivals=(
            SaeArrival(
                line="62",
                destination="Benimàmet",
                kind=ArrivalKind.MINUTES,
                minutes=54,
                arrival_at=NIGHT_2312_AT + timedelta(minutes=54),
            ),
        ),
        skipped=(),
        without_time=("7", "9", "62", "60", "9"),
    )


@pytest.mark.spec("sae_arrivals_source.AC-23")
def test_entries_without_time_are_logged_only_at_debug_level_with_stop_and_line() -> None:
    with capture_logs() as logs:
        snapshot = build_snapshot(parse_qrphp_html, STOP_2312_WITHOUT_TIME, "2312", NIGHT_2312_AT)
    assert [(a.line, a.minutes) for a in snapshot.arrivals] == [("62", 54)]
    assert [log for log in logs if log["event"] == "sae.unparsed_entry"] == []
    events = [log for log in logs if log["event"] == "sae.entry_without_time"]
    assert events == [
        {"event": "sae.entry_without_time", "log_level": "debug", "stop_id": "2312", "line": line}
        for line in ("7", "9", "62", "60", "9")
    ]
    assert "Benimàmet" not in str(logs)  # no destination nor anything else from the page
    assert "Est.del Nord" not in str(logs)


@pytest.mark.spec("sae_arrivals_source.AC-23")
@pytest.mark.parametrize(
    "new_text",
    [
        "Alboraia -",
        "Alboraia - ",
        "Alboraia -&nbsp;",
        "Natzaret - Port -",  # the separator inside the destination does not make it a time
    ],
)
def test_entry_ending_in_a_dash_is_without_time(new_text: str) -> None:
    body = replace_once(STOP_508_MINUTES, "Alboraia - 8 min.", new_text)
    result = parse_qrphp_html(body, "508", FETCHED_AT)
    assert [(a.line, a.minutes) for a in result.arrivals] == [("93", 5), ("93", 13), ("70", 20)]
    assert (result.skipped, result.without_time) == ((), ("70",))


@pytest.mark.spec("sae_arrivals_source.AC-23")
@pytest.mark.parametrize("new_text", ["-", " - ", "&nbsp;-", "Alboraia-", "Alboraia--"])
def test_a_dash_without_a_destination_or_a_separator_is_still_unparsed(new_text: str) -> None:
    body = replace_once(STOP_508_MINUTES, "Alboraia - 8 min.", new_text)
    result = parse_qrphp_html(body, "508", FETCHED_AT)
    assert len(result.arrivals) == 3
    assert len(result.skipped) == 1
    assert result.without_time == ()


# --- AC-21: stop header ------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-21")
@pytest.mark.spec("sae_arrivals_source.AC-19")
def test_unknown_stop_page_with_empty_header_is_unparseable() -> None:
    with pytest.raises(SaeUnparseableError):
        parse_qrphp_html(STOP_99999_UNKNOWN, "99999", FETCHED_AT)
    with pytest.raises(ArrivalsUnavailableError) as raised:
        build_snapshot(parse_qrphp_html, STOP_99999_UNKNOWN, "99999", FETCHED_AT)
    assert (raised.value.stop_id, raised.value.reason) == ("99999", "unparseable")


@pytest.mark.spec("sae_arrivals_source.AC-21")
@pytest.mark.parametrize("stop_id", ["2070", "50", "5080"])
def test_header_of_another_stop_is_unparseable(stop_id: str) -> None:
    with pytest.raises(SaeUnparseableError):
        parse_qrphp_html(STOP_508_MINUTES, stop_id, FETCHED_AT)


@pytest.mark.spec("sae_arrivals_source.AC-21")
@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"<html><body>Mantenimiento</body></html>",
        b"<div>508 - Parc de l'Oest</div>",  # header-like text outside the header block
        replace_once(STOP_508_MINUTES, "508 - Parc de l'Oest - Enguera", "508 -"),
        b"\xff\xfe not utf-8",
    ],
)
def test_page_without_a_valid_header_is_unparseable(body: bytes) -> None:
    with pytest.raises(SaeUnparseableError):
        parse_qrphp_html(body, "508", FETCHED_AT)


def test_the_qrphp_html_format_is_registered() -> None:
    assert PARSERS["qrphp_html"] is parse_qrphp_html
