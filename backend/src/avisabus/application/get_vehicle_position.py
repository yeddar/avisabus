"""Use case: estimated position of the next bus of a line and direction at a stop
(position_estimation design §1 and §3, AC-09–AC-12).

The arrival is the first one of the line and direction computed by `GetStopArrivals`, so the
position shares its SAE cache and never asks the SAE again (AC-09). Scheduled arrivals give the
position on the timetable (δ = 0, AC-10).

A paired trip whose position cannot be estimated because the active network is incoherent for
it is answered like an arrival without a trip (`NO_VEHICLE`, the representative shape) and
logged as `position.estimate_failed` (AC-11, v1.2).
"""

from dataclasses import dataclass
from datetime import datetime

from avisabus.application.get_stop_arrivals import GetStopArrivals, Logger
from avisabus.domain.errors import (
    LineNotAtStopError,
    PositionNotEstimableError,
    StopNotFoundError,
)
from avisabus.domain.models.network import Stop
from avisabus.domain.models.position import PositionEstimate, PositionStatus
from avisabus.domain.models.stop_arrivals import ArrivalSource, ArrivalView, VehicleView
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.occupancy_simulation import service_day_start
from avisabus.domain.services.position_estimator import estimate_position


@dataclass(frozen=True, slots=True)
class VehiclePosition:
    stop: Stop
    line: str
    direction_id: int
    headsign: str
    """`LineDirection.headsign` of (stop, line, direction_id)."""
    source: ArrivalSource
    status: PositionStatus
    generated_at: datetime
    refresh_after_s: int
    arrival: ArrivalView | None
    shape_id: str | None
    """Shape of the trip, or the representative one of the line and direction without one."""
    estimate: PositionEstimate | None


class GetVehiclePosition:
    def __init__(
        self,
        stop_arrivals: GetStopArrivals,
        network: NetworkRepository,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._stop_arrivals = stop_arrivals
        self._network = network
        self._clock = clock
        self._logger = logger

    async def execute(
        self, stop_id: str, token: str, line: str, direction_id: int
    ) -> VehiclePosition:
        """Raises `StopNotFoundError` and `NoActiveFeedError` (like the arrivals, before asking
        the SAE) and `LineNotAtStopError`."""
        arrivals = await self._stop_arrivals.execute(stop_id, token)
        stop = self._network.get_stop(stop_id)
        if stop is None:  # the active feed changed in between
            raise StopNotFoundError(stop_id)
        direction = next(
            (
                d
                for d in self._network.lines_at_stop(stop_id)
                if d.line == line and d.direction_id == direction_id
            ),
            None,
        )
        if direction is None:
            raise LineNotAtStopError(stop_id, line, direction_id)
        arrival = next(
            (a for a in arrivals.arrivals if a.line == line and a.direction_id == direction_id),
            None,
        )

        def result(
            status: PositionStatus, shape_id: str, estimate: PositionEstimate | None = None
        ) -> VehiclePosition:
            return VehiclePosition(
                stop=stop,
                line=line,
                direction_id=direction_id,
                headsign=direction.headsign,
                source=arrivals.source,
                status=status,
                generated_at=arrivals.generated_at,
                refresh_after_s=arrivals.refresh_after_s,
                arrival=arrival,
                shape_id=shape_id,
                estimate=estimate,
            )

        if arrival is None:
            return result(PositionStatus.NO_ARRIVAL, direction.shape_id)
        if arrival.vehicle is None:
            return result(PositionStatus.NO_VEHICLE, direction.shape_id)
        shape_id = self._network.trip_shape_id(arrival.vehicle.trip_id)
        try:
            trip_shape_id, estimate = self._estimate(
                stop_id, arrival.vehicle, shape_id, arrival.arrival_at
            )
        except PositionNotEstimableError as error:
            self._logger.warning(
                "position.estimate_failed",
                trip_id=arrival.vehicle.trip_id,
                shape_id=shape_id,
                reason=error.reason,
            )
            return result(PositionStatus.NO_VEHICLE, direction.shape_id)
        return result(estimate.status, trip_shape_id, estimate)

    def _estimate(
        self, stop_id: str, vehicle: VehicleView, shape_id: str | None, arrival_at: datetime
    ) -> tuple[str, PositionEstimate]:
        """The trip's shape and the estimate.

        Raises `PositionNotEstimableError` when the active feed is incoherent for the paired
        trip: no timetable, no shape, an empty shape, a stop without distance nor coordinates or
        a trip that does not call at the stop (it can only happen if the feed changes)."""
        stop_times = self._network.trip_stop_times(vehicle.trip_id)
        if not stop_times:
            raise PositionNotEstimableError("missing_stop_times")
        if shape_id is None:
            raise PositionNotEstimableError("missing_shape")
        shape = self._network.shape_points(shape_id)
        stops = {
            stop.stop_id: stop
            for stop in (self._network.get_stop(s) for s in {st.stop_id for st in stop_times})
            if stop is not None
        }
        estimate = estimate_position(
            stop_times,
            shape,
            {stop_id: stop.name for stop_id, stop in stops.items()},
            stop_id,
            service_day_start(vehicle.service_date),
            arrival_at,
            self._clock.now(),
            stop_coordinates={stop_id: (stop.lat, stop.lon) for stop_id, stop in stops.items()},
        )
        if estimate is None:
            raise PositionNotEstimableError("target_not_in_trip")
        return shape_id, estimate
