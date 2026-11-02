"""Recorded SAE sessions (sae_arrivals_source design §5, RF-35).

```
<dir>/
├── session.json        started_at, stops, interval_s, source_url_template, source_format
└── <stop_id>/<offset_s:06d>.json   stop_id, captured_at, offset_s, status, content_type,
                                    body, error
```

The body is stored as text decoded with the declared charset (UTF-8 if none); a body that is not
valid text is stored in base64 with `"body_encoding": "base64"`. Extra keys (e.g. `note`,
`derived_from` in derived fixtures) are ignored when reading.
"""

import base64
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avisabus.adapters.outbound.sae.http_source import RawResponse

SESSION_FILE = "session.json"
BASE64 = "base64"
_CHARSET = re.compile(r"charset\s*=\s*\"?([\w.:-]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SaeSession:
    started_at: datetime
    stops: tuple[str, ...]
    interval_s: int | None
    """`None` only in sessions not recorded with `avisabus sae record` (irregular requests)."""
    source_url_template: str
    source_format: str

    def to_json(self) -> dict[str, Any]:
        return {
            "started_at": _iso(self.started_at),
            "stops": list(self.stops),
            "interval_s": self.interval_s,
            "source_url_template": self.source_url_template,
            "source_format": self.source_format,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SaeSession":
        return cls(
            started_at=_parse_iso(data["started_at"]),
            stops=tuple(str(stop) for stop in data["stops"]),
            interval_s=None if data["interval_s"] is None else int(data["interval_s"]),
            source_url_template=str(data["source_url_template"]),
            source_format=str(data["source_format"]),
        )


@dataclass(frozen=True, slots=True)
class SaeRecording:
    stop_id: str
    captured_at: datetime
    offset_s: int
    status: int | None
    content_type: str | None
    body: bytes | None
    error: str | None

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "stop_id": self.stop_id,
            "captured_at": _iso(self.captured_at),
            "offset_s": self.offset_s,
            "status": self.status,
            "content_type": self.content_type,
            "body": None,
            "error": self.error,
        }
        if self.body is not None:
            try:
                data["body"] = self.body.decode(_charset(self.content_type))
            except (UnicodeDecodeError, LookupError):
                data["body"] = base64.b64encode(self.body).decode("ascii")
                data["body_encoding"] = BASE64
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SaeRecording":
        content_type = data.get("content_type")
        body_text = data.get("body")
        body: bytes | None = None
        if body_text is not None:
            if data.get("body_encoding") == BASE64:
                body = base64.b64decode(body_text)
            else:
                body = str(body_text).encode(_charset(content_type))
        return cls(
            stop_id=str(data["stop_id"]),
            captured_at=_parse_iso(data["captured_at"]),
            offset_s=int(data["offset_s"]),
            status=None if data.get("status") is None else int(data["status"]),
            content_type=content_type,
            body=body,
            error=data.get("error"),
        )


def read_session(directory: Path) -> SaeSession:
    """Raises `OSError`, `ValueError` or `KeyError` if `session.json` is missing or invalid."""
    return SaeSession.from_json(_load(directory / SESSION_FILE))


def read_recordings(directory: Path) -> dict[str, list[SaeRecording]]:
    """Every recording of the session by stop, sorted by `offset_s`."""
    by_stop: dict[str, list[SaeRecording]] = {}
    for path in sorted(directory.glob("*/*.json")):
        recording = SaeRecording.from_json(_load(path))
        by_stop.setdefault(recording.stop_id, []).append(recording)
    for recordings in by_stop.values():
        recordings.sort(key=lambda recording: recording.offset_s)
    return by_stop


class RecordingArrivalsSource:
    """Observer of `SaeHttpArrivalsSource` that writes every raw response of a session (AC-14).

    Creating it writes `session.json`; each call writes `<stop_id>/<offset_s:06d>.json`, where
    `offset_s` is the whole number of seconds from `session.started_at` to `captured_at`.
    """

    def __init__(self, directory: Path, session: SaeSession) -> None:
        self._directory = directory
        self._session = session
        directory.mkdir(parents=True, exist_ok=True)
        _dump(directory / SESSION_FILE, session.to_json())

    def __call__(self, raw: RawResponse) -> None:
        offset_s = int((raw.captured_at - self._session.started_at).total_seconds())
        recording = SaeRecording(
            stop_id=raw.stop_id,
            captured_at=raw.captured_at,
            offset_s=offset_s,
            status=raw.status,
            content_type=raw.content_type,
            body=raw.body,
            error=raw.error,
        )
        stop_dir = self._directory / raw.stop_id
        stop_dir.mkdir(exist_ok=True)
        _dump(stop_dir / f"{offset_s:06d}.json", recording.to_json())


def _charset(content_type: str | None) -> str:
    match = _CHARSET.search(content_type or "")
    return match.group(1) if match else "utf-8"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamps of a recorded session must include the time zone")
    return parsed.astimezone(UTC)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def _dump(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
