"""`GetStop`: token, stop, lines and errors (stop_arrivals_api T-04)."""

import pytest

from avisabus.application.get_stop import GetStop
from avisabus.domain.errors import NoActiveFeedError, StopNotFoundError
from avisabus.domain.models.stop_arrivals import StopView
from tests.support.network import FakeNetwork, FakeStopTokenSigner, line_direction

SIGNER = FakeStopTokenSigner()


@pytest.fixture
def network() -> FakeNetwork:
    network = FakeNetwork()
    network.add_stop(
        "508",
        "Parc de l'Oest - Enguera",
        line_direction("70", 1, "Alboraia"),
        line_direction("93", 0, "Passeig Marítim - Hospital Malva-rosa", "00AA00", "000000"),
    )
    return network


@pytest.mark.spec("stop_arrivals_api.AC-01")
async def test_returns_the_stop_with_its_lines(network: FakeNetwork) -> None:
    view = await GetStop(network, SIGNER).execute("508", SIGNER.sign("508"))
    assert view == StopView(
        stop_id="508",
        name="Parc de l'Oest - Enguera",
        lines=(
            line_direction("70", 1, "Alboraia"),
            line_direction("93", 0, "Passeig Marítim - Hospital Malva-rosa", "00AA00", "000000"),
        ),
    )


@pytest.mark.spec("stop_arrivals_api.AC-02")
@pytest.mark.parametrize(
    ("stop_id", "token"),
    [
        ("508", ""),
        ("508", "x" * 22),
        ("508", SIGNER.sign("2070")),
        ("999", SIGNER.sign("999")),  # valid token, but the stop does not exist
    ],
)
async def test_invalid_token_or_unknown_stop_is_the_same_error(
    network: FakeNetwork, stop_id: str, token: str
) -> None:
    with pytest.raises(StopNotFoundError) as raised:
        await GetStop(network, SIGNER).execute(stop_id, token)
    assert raised.value.stop_id == stop_id
    assert stop_id not in str(raised.value)


@pytest.mark.spec("stop_arrivals_api.AC-03")
async def test_no_active_feed(network: FakeNetwork) -> None:
    network.feed = None
    with pytest.raises(NoActiveFeedError):
        await GetStop(network, SIGNER).execute("508", SIGNER.sign("508"))


@pytest.mark.spec("stop_arrivals_api.AC-02")
async def test_token_is_checked_before_the_network(network: FakeNetwork) -> None:
    network.feed = None
    with pytest.raises(StopNotFoundError):
        await GetStop(network, SIGNER).execute("508", "bad")
