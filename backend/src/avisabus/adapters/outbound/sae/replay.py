"""Replay of a recorded SAE session driven by the `Clock` (sae_arrivals_source AC-15, AC-16, AC-22).

For each request it returns the stop's recording with the greatest `offset_s` not beyond the
time elapsed since the replay started, parsed by the parser of the session's `source_format`
with `fetched_at = clock.now()`.
"""

import bisect
from datetime import datetime
from pathlib import Path

from avisabus.adapters.outbound.sae.qrphp_parser import PARSERS, build_snapshot
from avisabus.adapters.outbound.sae.recording import (
    SaeRecording,
    read_recordings,
    read_session,
)
from avisabus.config import ConfigurationError
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from avisabus.domain.ports.clock import Clock


class SaeReplayArrivalsSource:
    def __init__(self, recordings_dir: Path, clock: Clock, start: datetime | None = None) -> None:
        """`start = None` → the instant of the first `get_arrivals`.

        Raises `ConfigurationError` if the session cannot be read or its `source_format` has no
        parser.
        """
        try:
            session = read_session(recordings_dir)
            recordings = read_recordings(recordings_dir)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ConfigurationError(
                f"cannot read the SAE replay session in {recordings_dir} "
                f"({type(error).__name__}); check AVISABUS_SAE_REPLAY_DIR"
            ) from None
        parser = PARSERS.get(session.source_format)
        if parser is None:
            raise ConfigurationError(
                f"unknown source_format {session.source_format!r} in the SAE replay session "
                f"{recordings_dir} (known: {', '.join(sorted(PARSERS))})"
            )
        self._parser = parser
        self._clock = clock
        self._start = start
        self._recordings = recordings
        self._offsets = {
            stop_id: [recording.offset_s for recording in items]
            for stop_id, items in recordings.items()
        }

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        now = self._clock.now()
        if self._start is None:
            self._start = now
        recording = self._select(stop_id, (now - self._start).total_seconds())
        if recording is None:
            raise ArrivalsUnavailableError(stop_id, "no_recording")
        if recording.error is not None:
            raise ArrivalsUnavailableError(stop_id, recording.error)
        if recording.status is None or not 200 <= recording.status < 300:
            raise ArrivalsUnavailableError(stop_id, f"http_{recording.status}")
        if recording.body is None:
            raise ArrivalsUnavailableError(stop_id, "unparseable")
        return build_snapshot(self._parser, recording.body, stop_id, now)

    def _select(self, stop_id: str, elapsed_s: float) -> SaeRecording | None:
        offsets = self._offsets.get(stop_id, [])
        index = bisect.bisect_right(offsets, elapsed_s)
        return self._recordings[stop_id][index - 1] if index else None
