import pytest

from avisabus.domain.services.stop_url import build_stop_url

TOKEN = "83Rg_QTPgamZSDGo9T168g"  # noqa: S105 (public test vector)


@pytest.mark.spec("stop_tokens_qr.AC-06")
@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://avisabus.example", f"https://avisabus.example/p/508?t={TOKEN}"),
        ("https://avisabus.example/", f"https://avisabus.example/p/508?t={TOKEN}"),
        ("https://avisabus.example//", f"https://avisabus.example/p/508?t={TOKEN}"),
        ("http://localhost:5173", f"http://localhost:5173/p/508?t={TOKEN}"),
        ("https://emt.example/avisabus/", f"https://emt.example/avisabus/p/508?t={TOKEN}"),
    ],
)
def test_stop_url_has_no_duplicated_slashes(base_url: str, expected: str) -> None:
    assert build_stop_url(base_url, "508", TOKEN) == expected


@pytest.mark.spec("stop_tokens_qr.AC-06")
def test_stop_url_contains_the_stop_and_its_token() -> None:
    url = build_stop_url("https://avisabus.example", "1234", "A" * 22)
    assert url == "https://avisabus.example/p/1234?t=AAAAAAAAAAAAAAAAAAAAAA"
