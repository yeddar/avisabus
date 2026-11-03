import pytest

from avisabus.domain.services.line_order import natural_line_key


@pytest.mark.spec("gtfs_import.AC-13")
def test_numeric_lines_go_first_in_ascending_order_then_alphanumeric() -> None:
    lines = ["C2", "98", "7", "N1", "70", "C1", "100", "9"]
    assert sorted(lines, key=natural_line_key) == ["7", "9", "70", "98", "100", "C1", "C2", "N1"]


@pytest.mark.spec("gtfs_import.AC-13")
def test_alphanumeric_lines_compare_their_numbers_naturally() -> None:
    assert sorted(["C10", "C2", "C1"], key=natural_line_key) == ["C1", "C2", "C10"]
