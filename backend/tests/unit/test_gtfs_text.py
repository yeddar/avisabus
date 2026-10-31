import pytest

from avisabus.domain.services.gtfs_text import clean_name


@pytest.mark.spec("gtfs_import.AC-07")
@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Terramelar ", "Terramelar"),
        ("  La Malva-rosa - Mendizábal ", "La Malva-rosa - Mendizábal"),
        # Inner spaces and Valencian characters are kept exactly as in the feed.
        (
            "Doctor J.J. Dòmine  - Edifici del Rellotge",
            "Doctor J.J. Dòmine  - Edifici del Rellotge",
        ),
        ("Plaça de l'Ajuntament - Ateneu", "Plaça de l'Ajuntament - Ateneu"),
        ("Sant Marcel·lí", "Sant Marcel·lí"),
        ("\tEstació del Cabanyal\t", "Estació del Cabanyal"),
        ("", ""),
    ],
)
def test_only_leading_and_trailing_whitespace_is_removed(raw: str, clean: str) -> None:
    assert clean_name(raw) == clean
