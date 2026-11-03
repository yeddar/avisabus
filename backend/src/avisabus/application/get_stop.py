"""Use case: a stop and the lines serving it, from the QR link (stop_arrivals_api AC-01–AC-03)."""

from avisabus.domain.errors import NoActiveFeedError, StopNotFoundError
from avisabus.domain.models.network import Stop
from avisabus.domain.models.stop_arrivals import StopView
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.ports.stop_token import StopTokenSigner


class GetStop:
    def __init__(self, network: NetworkRepository, signer: StopTokenSigner) -> None:
        self._network = network
        self._signer = signer

    async def execute(self, stop_id: str, token: str) -> StopView:
        """Raises `StopNotFoundError` (invalid token or unknown stop) and `NoActiveFeedError`."""
        stop = find_stop(self._network, self._signer, stop_id, token)
        lines = tuple(self._network.lines_at_stop(stop_id))
        return StopView(stop_id=stop.stop_id, name=stop.name, lines=lines)


def find_stop(
    network: NetworkRepository, signer: StopTokenSigner, stop_id: str, token: str
) -> Stop:
    """Checks the token first (it does not depend on the network), then the active feed, then
    the stop. An invalid token and an unknown stop are the same error (AC-02)."""
    if not signer.verify(stop_id, token):
        raise StopNotFoundError(stop_id)
    if network.active_feed() is None:
        raise NoActiveFeedError()
    stop = network.get_stop(stop_id)
    if stop is None:
        raise StopNotFoundError(stop_id)
    return stop
