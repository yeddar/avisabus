"""Estimated position of the bus on the shape of its trip (position_estimation design §3).

If the bus will reach the target stop δ later than scheduled, it is assumed to carry that same
delay along the whole trip: at `now` it is where the timetable puts it at `now − δ`, interpolated
by time between two consecutive stops (AC-01, AC-02).
"""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from itertools import accumulate

from avisabus.domain.errors import PositionNotEstimableError
from avisabus.domain.models.network import ShapePoint, TripStopTime
from avisabus.domain.models.position import PositionEstimate, PositionStatus, StopRef
from avisabus.domain.services.geometry import (
    cumulative_distances,
    feed_to_metres,
    point_at_distance,
    project_onto_shape,
)


def estimate_position(
    stop_times: Sequence[TripStopTime],
    shape: Sequence[ShapePoint],
    stop_names: Mapping[str, str],
    target_stop_id: str,
    service_day_start: datetime,
    arrival_at: datetime,
    now: datetime,
    stop_coordinates: Mapping[str, tuple[float, float]] | None = None,
) -> PositionEstimate | None:
    """Position at `now` of the trip that reaches `target_stop_id` at `arrival_at`.

    `service_day_start` is the start of the trip's service day (local noon − 12 h); `arrival_at`
    and `now` are timezone-aware. `stop_coordinates` (`(lat, lon)` by stop) are only needed when
    the stop times or the shape lack `shape_dist_traveled` (AC-06). Every distance of the estimate
    is in real metres along the shape. Returns `None` if the trip does not call at the target
    stop; raises `PositionNotEstimableError` if the shape is empty or a stop can be placed neither
    by distance nor by coordinates.
    """
    ordered = sorted(stop_times, key=lambda stop_time: stop_time.stop_sequence)
    occurrences = [n for n, st in enumerate(ordered) if st.stop_id == target_stop_id]
    if not occurrences:
        return None
    if not shape:
        raise PositionNotEstimableError("empty_shape")
    along_shape = cumulative_distances(shape)
    along_stops = _stop_distances(ordered, shape, along_shape, stop_coordinates)

    def scheduled(n: int) -> datetime:
        return service_day_start + timedelta(seconds=ordered[n].arrival_s)

    # AC-07: the occurrence of the target closest to the arrival (circular lines).
    k = min(occurrences, key=lambda n: (abs(scheduled(n) - arrival_at), n))
    delay = arrival_at - scheduled(k)
    s = (now - delay - service_day_start).total_seconds()

    # AC-03; with the target as the first stop of the trip, AC-03 prevails over AC-04 (v1.2).
    if k == 0 or s >= ordered[k].arrival_s:
        status, d = PositionStatus.AT_STOP, along_stops[k]
    elif s < ordered[0].departure_s:  # AC-04
        status, d = PositionStatus.NOT_STARTED, along_stops[0]
    else:  # AC-01
        status, d = PositionStatus.EN_ROUTE, _interpolate(ordered, along_stops, k, s)

    point = point_at_distance(shape, along_shape, d)
    target_d = along_stops[k]
    if status is PositionStatus.AT_STOP:
        next_index = k
    else:
        next_index = next((j for j in range(k + 1) if along_stops[j] > d), k)
    next_id = ordered[next_index].stop_id
    return PositionEstimate(
        status=status,
        lat=point.lat,
        lon=point.lon,
        bearing_deg=point.bearing_deg,
        shape_distance_m=d,
        distance_to_stop_m=max(0.0, target_d - d),
        stops_away=sum(1 for j in range(k) if along_stops[j] > d),
        next_stop=StopRef(next_id, stop_names.get(next_id, "")),
    )


def _interpolate(
    ordered: Sequence[TripStopTime], along_stops: Sequence[float], k: int, s: float
) -> float:
    """Distance at `s` (seconds of the service day), with `departure_s[0] <= s < arrival_s[k]`.

    Between the departure of stop `i` and the arrival of `i + 1`, linear in time; while the bus
    waits at a stop (between its arrival and its departure), at that stop.
    """
    for i in range(k):
        s_next = ordered[i + 1].arrival_s
        if s >= s_next:
            continue
        s_i = ordered[i].departure_s
        if s <= s_i or s_next <= s_i:
            return along_stops[i]
        fraction = (s - s_i) / (s_next - s_i)
        return along_stops[i] + fraction * (along_stops[i + 1] - along_stops[i])
    return along_stops[k]


def _stop_distances(
    ordered: Sequence[TripStopTime],
    shape: Sequence[ShapePoint],
    along_shape: Sequence[float],
    stop_coordinates: Mapping[str, tuple[float, float]] | None,
) -> list[float]:
    """Metres along the shape of each stop, never decreasing along the trip (AC-06).

    The stops are placed with their `shape_dist_traveled` if the shape has it too (its values are
    only comparable with those of the shape), and projected onto the shape otherwise.
    """
    feed = [st.shape_dist_traveled for st in ordered if st.shape_dist_traveled is not None]
    if len(feed) == len(ordered) and all(point.dist_traveled is not None for point in shape):
        metres = feed_to_metres(shape, feed)
    elif stop_coordinates is None or any(st.stop_id not in stop_coordinates for st in ordered):
        # Without usable shape_dist_traveled, the coordinates of every stop are needed.
        raise PositionNotEstimableError("missing_stop_coordinates")
    else:
        points = [stop_coordinates[stop_time.stop_id] for stop_time in ordered]
        metres = project_onto_shape(points, shape, along_shape)
    return list(accumulate(metres, max))
