"""Start-up validation of the direction overrides (stop_arrivals_api AC-20)."""

from datetime import UTC, datetime

import pytest

from avisabus.application.direction_overrides import validate_direction_overrides
from avisabus.domain.ports.gtfs_import import DirectionReport, StopRef
from tests.unit.test_get_stop_arrivals import FakeLogger

pytestmark = pytest.mark.spec("stop_arrivals_api.AC-20")

NOW = datetime(2026, 11, 3, tzinfo=UTC)


class FakeFeedInfo:
    def active_timezone(self) -> str | None:
        return "Europe/Madrid"

    def direction_report(self) -> list[DirectionReport]:
        def report(line: str, direction_id: int, *headsigns: str) -> DirectionReport:
            stop = StopRef("1", "x")
            return DirectionReport(
                line,
                direction_id,
                "derived",
                10,
                "s",
                stop,
                stop,
                tuple((h, 5) for h in headsigns),
                (("s", 10),),
            )

        return [
            report("C3", 0, "Conselleria d'Educació", "Avinguda Campanar - Centre de Salut"),
            report("C3", 1, "Eduard Boscà - Balears", "Cardenal Benlloch (imparell) - Port"),
            report("99", 0, "Mendizábal - Doctor Álvaro López"),
        ]


def test_valid_entries_are_keyed_by_line_and_sae_destination() -> None:
    logger = FakeLogger()
    entries = {
        "C3|Campanar": "Avinguda Campanar - Centre de Salut",
        "C3|C. Benlloch": "Cardenal Benlloch (imparell) - Port",
        "99|La Malva-rosa|x": "Mendizábal - Doctor Álvaro López",
    }
    assert validate_direction_overrides(entries, FakeFeedInfo(), logger) == {
        ("C3", "Campanar"): "Avinguda Campanar - Centre de Salut",
        ("C3", "C. Benlloch"): "Cardenal Benlloch (imparell) - Port",
        ("99", "La Malva-rosa|x"): "Mendizábal - Doctor Álvaro López",
    }
    assert logger.events == []


def test_invalid_entries_are_logged_and_ignored() -> None:
    logger = FakeLogger()
    entries = {
        "N4|Est.del Nord": "Estació del Nord",
        "C3|Campanar": "Campanar",
        "99|P. Congressos": "Avinguda Campanar - Centre de Salut",  # headsign of another line
        "C3 Campanar": "Conselleria d'Educació",
        "|Campanar": "Conselleria d'Educació",
        "C3|": "Conselleria d'Educació",
        "C3|Ed. Bosca": "Eduard Boscà - Balears",
    }
    valid = validate_direction_overrides(entries, FakeFeedInfo(), logger)
    assert valid == {("C3", "Ed. Bosca"): "Eduard Boscà - Balears"}
    assert [
        (level, event, fields["entry"], fields["reason"]) for level, event, fields in logger.events
    ] == [
        ("warning", "arrivals.override_invalid", "N4|Est.del Nord", "unknown_line"),
        ("warning", "arrivals.override_invalid", "C3|Campanar", "unknown_headsign"),
        ("warning", "arrivals.override_invalid", "99|P. Congressos", "unknown_headsign"),
        ("warning", "arrivals.override_invalid", "C3 Campanar", "malformed_entry"),
        ("warning", "arrivals.override_invalid", "|Campanar", "malformed_entry"),
        ("warning", "arrivals.override_invalid", "C3|", "malformed_entry"),
    ]
    assert logger.events[0][2]["headsign"] == "Estació del Nord"


def test_without_active_feed_every_entry_is_invalid() -> None:
    class Empty(FakeFeedInfo):
        def direction_report(self) -> list[DirectionReport]:
            return []

    logger = FakeLogger()
    assert validate_direction_overrides({"C3|Campanar": "x"}, Empty(), logger) == {}
    assert [fields["reason"] for _, _, fields in logger.events] == ["unknown_line"]
