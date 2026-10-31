"""`GenerateStopQrCodes` with fakes: existing and missing stops, all stops, no active feed."""

from datetime import UTC, date, datetime

import pytest

from avisabus.application.generate_stop_qr_codes import (
    GeneratedQr,
    GenerateStopQrCodes,
    GenerateStopQrCodesCommand,
)
from avisabus.domain.errors import DomainError, NoActiveFeedError
from avisabus.domain.models.network import FeedVersion, Stop
from avisabus.domain.ports.qr import QrLabel, QrRequest

BASE_URL = "https://avisabus.example/"
FEED = FeedVersion(
    version_id=1,
    feed_version="23-10-2026",
    imported_at=datetime(2026, 10, 31, 8, 0, tzinfo=UTC),
    start_date=date(2026, 10, 16),
    end_date=date(2026, 11, 22),
    counts={},
)
STOPS = {
    "64": Stop("64", "Vall de la Ballestera - Campanar", 39.48, -0.39),
    "508": Stop("508", "Parc de l'Oest - Enguera", 39.47, -0.40),
    "1990": Stop("1990", "Alfauir - Estadi Ciutat de València", 39.49, -0.36),
}


class FakeNetwork:
    """The subset of `NetworkRepository` used by the use case."""

    def __init__(self, stops: dict[str, Stop], feed: FeedVersion | None = FEED) -> None:
        self._stops = stops
        self._feed = feed

    def active_feed(self) -> FeedVersion | None:
        return self._feed

    def get_stop(self, stop_id: str) -> Stop | None:
        return self._stops.get(stop_id)

    def list_stop_ids(self) -> list[str]:
        return sorted(self._stops)


class FakeSigner:
    def sign(self, stop_id: str) -> str:
        return f"token-{stop_id}"

    def verify(self, stop_id: str, token: str) -> bool:
        return token == self.sign(stop_id)


class FakeRenderer:
    def __init__(self) -> None:
        self.requests: list[QrRequest] = []

    def render(self, request: QrRequest) -> bytes:
        self.requests.append(request)
        return f"{request.format}:{request.content}".encode()


def _use_case(
    network: FakeNetwork | None = None, renderer: FakeRenderer | None = None
) -> GenerateStopQrCodes:
    return GenerateStopQrCodes(
        network=network or FakeNetwork(STOPS),  # type: ignore[arg-type]
        signer=FakeSigner(),
        renderer=renderer or FakeRenderer(),
        public_base_url=BASE_URL,
    )


@pytest.mark.spec("stop_tokens_qr.AC-07")
@pytest.mark.spec("stop_tokens_qr.AC-08")
def test_generates_a_qr_per_requested_stop_with_signed_url_and_label() -> None:
    renderer = FakeRenderer()
    result = _use_case(renderer=renderer).execute(
        GenerateStopQrCodesCommand(stop_ids=["508", "64"], format="svg")
    )
    url_508 = "https://avisabus.example/p/508?t=token-508"
    url_64 = "https://avisabus.example/p/64?t=token-64"
    assert result.generated == [
        GeneratedQr(
            stop_id="508",
            name="Parc de l'Oest - Enguera",
            url=url_508,
            filename="508.svg",
            content=f"svg:{url_508}".encode(),
        ),
        GeneratedQr(
            stop_id="64",
            name="Vall de la Ballestera - Campanar",
            url=url_64,
            filename="64.svg",
            content=f"svg:{url_64}".encode(),
        ),
    ]
    assert result.missing_stop_ids == []
    assert renderer.requests == [
        QrRequest(url_508, QrLabel("Parc de l'Oest - Enguera", "Parada 508"), "svg"),
        QrRequest(url_64, QrLabel("Vall de la Ballestera - Campanar", "Parada 64"), "svg"),
    ]


@pytest.mark.spec("stop_tokens_qr.AC-08")
def test_all_stops_of_the_active_feed_when_no_stop_is_given() -> None:
    result = _use_case().execute(GenerateStopQrCodesCommand(stop_ids=None, format="svg"))
    assert [qr.stop_id for qr in result.generated] == ["1990", "508", "64"]
    assert [qr.filename for qr in result.generated] == ["1990.svg", "508.svg", "64.svg"]
    assert result.missing_stop_ids == []


@pytest.mark.spec("stop_tokens_qr.AC-09")
def test_png_format_is_passed_to_the_renderer_and_names_the_file() -> None:
    renderer = FakeRenderer()
    result = _use_case(renderer=renderer).execute(
        GenerateStopQrCodesCommand(stop_ids=["1990"], format="png")
    )
    (qr,) = result.generated
    assert qr.filename == "1990.png"
    assert [r.format for r in renderer.requests] == ["png"]
    assert renderer.requests[0].label == QrLabel(
        "Alfauir - Estadi Ciutat de València", "Parada 1990"
    )


@pytest.mark.spec("stop_tokens_qr.AC-08")
def test_a_stop_given_twice_is_generated_once() -> None:
    result = _use_case().execute(
        GenerateStopQrCodesCommand(stop_ids=["508", "64", "508"], format="svg")
    )
    assert [qr.stop_id for qr in result.generated] == ["508", "64"]


@pytest.mark.spec("stop_tokens_qr.AC-10")
def test_missing_stops_are_reported_and_the_others_still_generated() -> None:
    renderer = FakeRenderer()
    result = _use_case(renderer=renderer).execute(
        GenerateStopQrCodesCommand(stop_ids=["9999", "508", "0", "64"], format="svg")
    )
    assert [qr.stop_id for qr in result.generated] == ["508", "64"]
    assert result.missing_stop_ids == ["9999", "0"]
    assert [r.label.subtitle for r in renderer.requests] == ["Parada 508", "Parada 64"]


@pytest.mark.spec("stop_tokens_qr.AC-11")
def test_without_an_active_feed_it_raises_and_renders_nothing() -> None:
    renderer = FakeRenderer()
    use_case = _use_case(network=FakeNetwork(STOPS, feed=None), renderer=renderer)
    with pytest.raises(NoActiveFeedError):
        use_case.execute(GenerateStopQrCodesCommand(stop_ids=["508"], format="svg"))
    with pytest.raises(NoActiveFeedError):
        use_case.execute(GenerateStopQrCodesCommand(stop_ids=None, format="png"))
    assert renderer.requests == []


@pytest.mark.spec("stop_tokens_qr.AC-11")
def test_no_active_feed_error_is_a_domain_error() -> None:
    assert issubclass(NoActiveFeedError, DomainError)
