"""Use case: QR codes of stops for `avisabus qr generate` (stop_tokens_qr design §3).

Writing the files and `index.csv` is the CLI's job; this use case only builds them in memory.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from avisabus.domain.errors import NoActiveFeedError
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.ports.qr import QrFormat, QrLabel, QrRenderer, QrRequest
from avisabus.domain.ports.stop_token import StopTokenSigner
from avisabus.domain.services.stop_url import build_stop_url


@dataclass(frozen=True, slots=True)
class GenerateStopQrCodesCommand:
    stop_ids: Sequence[str] | None
    """Stops to generate, in order; `None` means every stop of the active feed."""
    format: QrFormat


@dataclass(frozen=True, slots=True)
class GeneratedQr:
    stop_id: str
    name: str
    url: str
    filename: str
    content: bytes


@dataclass(frozen=True, slots=True)
class QrGenerationResult:
    generated: list[GeneratedQr]
    missing_stop_ids: list[str]


class GenerateStopQrCodes:
    def __init__(
        self,
        network: NetworkRepository,
        signer: StopTokenSigner,
        renderer: QrRenderer,
        public_base_url: str,
    ) -> None:
        self._network = network
        self._signer = signer
        self._renderer = renderer
        self._public_base_url = public_base_url

    def execute(self, cmd: GenerateStopQrCodesCommand) -> QrGenerationResult:
        """Raises `NoActiveFeedError` when no feed has been imported (AC-11)."""
        if self._network.active_feed() is None:
            raise NoActiveFeedError
        stop_ids = self._network.list_stop_ids() if cmd.stop_ids is None else cmd.stop_ids
        generated: list[GeneratedQr] = []
        missing: list[str] = []
        # One file per stop (AC-08): a stop given twice is generated once.
        for stop_id in dict.fromkeys(stop_ids):
            stop = self._network.get_stop(stop_id)
            if stop is None:
                missing.append(stop_id)
                continue
            url = build_stop_url(self._public_base_url, stop_id, self._signer.sign(stop_id))
            label = QrLabel(title=stop.name, subtitle=f"Parada {stop_id}")
            content = self._renderer.render(QrRequest(content=url, label=label, format=cmd.format))
            generated.append(
                GeneratedQr(
                    stop_id=stop_id,
                    name=stop.name,
                    url=url,
                    filename=f"{stop_id}.{cmd.format}",
                    content=content,
                )
            )
        return QrGenerationResult(generated=generated, missing_stop_ids=missing)
