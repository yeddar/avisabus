"""Start-up check of the direction overrides against the active network (stop_arrivals_api AC-20).

Each entry is `"{line}|{SAE destination}": "{GTFS headsign}"`. It is kept only if the line
exists and some direction of it has that headsign; otherwise `arrivals.override_invalid` is
logged and the entry is ignored, without stopping the start-up. The headsign is turned into a
direction on every request, with the headsigns of the stop (`resolve_direction`).
"""

from collections.abc import Mapping

from avisabus.application.get_stop_arrivals import Logger
from avisabus.domain.ports.gtfs_import import FeedInfoSource


def validate_direction_overrides(
    entries: Mapping[str, str], network: FeedInfoSource, logger: Logger
) -> dict[tuple[str, str], str]:
    """Valid entries keyed by `(line, SAE destination)`."""
    headsigns: dict[str, set[str]] = {}
    for direction in network.direction_report():
        headsigns.setdefault(direction.line, set()).update(h for h, _ in direction.headsigns)
    valid: dict[tuple[str, str], str] = {}
    for entry, headsign in entries.items():
        line, separator, destination = entry.partition("|")
        if not separator or not line or not destination:
            reason = "malformed_entry"
        elif line not in headsigns:
            reason = "unknown_line"
        elif headsign not in headsigns[line]:
            reason = "unknown_headsign"
        else:
            valid[(line, destination)] = headsign
            continue
        logger.warning("arrivals.override_invalid", entry=entry, headsign=headsign, reason=reason)
    return valid
