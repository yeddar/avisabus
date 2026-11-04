"""Use case: arrivals of a stop, enriched, or the timetable as fallback (stop_arrivals_api).

Real time (AC-04): every SAE arrival is kept; lines outside the GTFS stay as they come (AC-08);
the others get their direction (`resolve_destination`, AC-05–AC-07, AC-19, AC-20), then the
arrivals of each (line, direction) are paired with scheduled trips (`match_trips`, AC-10,
AC-11, AC-22) and the paired trips get their occupancy (AC-12).

Fallback (AC-13, AC-14): when the SAE is unavailable, the next scheduled passages.

An arrival can be requested (`can_alert`, alert_create AC-01, v1.6) only when it is in the
network, its direction is resolved, it has a paired trip and it arrives within the max lead.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from avisabus.application.get_stop import find_stop
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.domain.errors import ArrivalsUnavailableError, NoActiveFeedError, StopNotFoundError
from avisabus.domain.models.arrivals import ArrivalKind, SaeArrival
from avisabus.domain.models.network import Line, ScheduledStopTime
from avisabus.domain.models.occupancy import OccupancyStatus, OccupancyThresholds, VehicleRef
from avisabus.domain.models.stop_arrivals import (
    ArrivalSource,
    ArrivalView,
    StopArrivals,
    VehicleView,
)
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.ports.occupancy import OccupancySensor
from avisabus.domain.ports.stop_token import StopTokenSigner
from avisabus.domain.services.direction_resolver import (
    DestinationResolution,
    DirectionCandidate,
    resolve_destination,
)
from avisabus.domain.services.occupancy_classifier import classify_occupancy
from avisabus.domain.services.occupancy_simulation import service_day_start
from avisabus.domain.services.trip_matcher import TripCandidate, match_trips


class Logger(Protocol):
    """Structured logger (structlog's bound logger in production)."""

    def debug(self, event: str, **fields: Any) -> Any: ...

    def info(self, event: str, **fields: Any) -> Any: ...

    def warning(self, event: str, **fields: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class _LineAtStop:
    candidates: tuple[DirectionCandidate, ...]
    departing: frozenset[int]


class GetStopArrivals:
    def __init__(
        self,
        network: NetworkRepository,
        signer: StopTokenSigner,
        arrivals: ArrivalsSource,
        scheduled: ScheduledArrivalsProvider,
        occupancy: OccupancySensor,
        thresholds: OccupancyThresholds,
        clock: Clock,
        refresh_after_s: int,
        match_tolerance: timedelta,
        aliases: Mapping[str, str],
        direction_overrides: Mapping[tuple[str, str], str],
        min_score: float,
        alert_max_lead: timedelta,
        logger: Logger,
    ) -> None:
        self._network = network
        self._signer = signer
        self._arrivals = arrivals
        self._scheduled = scheduled
        self._occupancy = occupancy
        self._thresholds = thresholds
        self._clock = clock
        self._refresh_after_s = refresh_after_s
        self._tolerance = match_tolerance
        self._aliases = aliases
        self._overrides = direction_overrides
        self._min_score = min_score
        self._alert_max_lead = alert_max_lead
        self._log = logger

    async def execute(self, stop_id: str, token: str) -> StopArrivals:
        """Raises `StopNotFoundError` (invalid token or unknown stop) and `NoActiveFeedError`,
        always before asking the SAE."""
        find_stop(self._network, self._signer, stop_id, token)
        return await self._arrivals_of(stop_id)

    async def for_stop(self, stop_id: str) -> StopArrivals:
        """Same as `execute` without the stop token: internal use of the background tasks
        (alert_expiry design §3), through the same SAE cache. Raises `NoActiveFeedError` and
        `StopNotFoundError` (the stop is no longer in the active network) before asking the SAE.
        """
        if self._network.active_feed() is None:
            raise NoActiveFeedError()
        if self._network.get_stop(stop_id) is None:
            raise StopNotFoundError(stop_id)
        return await self._arrivals_of(stop_id)

    async def _arrivals_of(self, stop_id: str) -> StopArrivals:
        now = self._clock.now()
        try:
            snapshot = await self._arrivals.get_arrivals(stop_id)
        except ArrivalsUnavailableError as error:
            self._log.warning("arrivals.fallback", stop_id=stop_id, reason=error.reason)
            views = await self._scheduled_views(stop_id, now)
            return self._result(stop_id, ArrivalSource.SCHEDULED, now, views)
        views = await self._realtime_views(stop_id, snapshot.arrivals, now)
        return self._result(stop_id, ArrivalSource.REALTIME, now, views)

    def _result(
        self, stop_id: str, source: ArrivalSource, now: datetime, views: list[ArrivalView]
    ) -> StopArrivals:
        views.sort(key=lambda view: view.arrival_at)
        return StopArrivals(
            stop_id=stop_id,
            source=source,
            generated_at=now,
            refresh_after_s=self._refresh_after_s,
            arrivals=tuple(views),
        )

    # --- Real time ---

    async def _realtime_views(
        self, stop_id: str, arrivals: tuple[SaeArrival, ...], now: datetime
    ) -> list[ArrivalView]:
        lines: dict[str, Line | None] = {}
        at_stop: dict[str, _LineAtStop] = {}
        resolutions: list[DestinationResolution | None] = []
        for arrival in arrivals:
            if arrival.line not in lines:
                lines[arrival.line] = self._network.get_line(arrival.line)
            if lines[arrival.line] is None:
                resolutions.append(None)
                continue
            if arrival.line not in at_stop:
                at_stop[arrival.line] = self._line_at_stop(stop_id, arrival.line)
            resolution = self._resolve(arrival, at_stop[arrival.line])
            if resolution is None:
                self._log.info(
                    "arrivals.direction_unresolved",
                    stop_id=stop_id,
                    line=arrival.line,
                    destination=arrival.destination,
                )
            resolutions.append(resolution)
        trips = self._match(stop_id, arrivals, resolutions)
        views = []
        for arrival, resolution, trip in zip(arrivals, resolutions, trips, strict=True):
            line = lines[arrival.line]
            vehicle = None if trip is None else VehicleView(trip.trip_id, trip.service_date)
            views.append(
                ArrivalView(
                    line=arrival.line,
                    destination=arrival.destination if resolution is None else resolution.headsign,
                    direction_id=None if resolution is None else resolution.direction_id,
                    in_network=line is not None,
                    kind=arrival.kind,
                    minutes=arrival.minutes,
                    arrival_at=arrival.arrival_at,
                    line_color=None if line is None else line.color,
                    line_text_color=None if line is None else line.text_color,
                    sae_destination=arrival.destination,
                    vehicle=vehicle,
                    occupancy=await self._occupancy_of(vehicle, now),
                    can_alert=self._can_alert(
                        in_network=line is not None,
                        direction_id=None if resolution is None else resolution.direction_id,
                        vehicle=vehicle,
                        arrival_at=arrival.arrival_at,
                        now=now,
                    ),
                )
            )
        return views

    def _line_at_stop(self, stop_id: str, line: str) -> _LineAtStop:
        candidates = tuple(
            DirectionCandidate(h.direction_id, h.headsign)
            for h in self._network.headsigns_at_stop(stop_id, line)
        )
        several = len({candidate.direction_id for candidate in candidates}) > 1
        departing = (
            self._network.departing_directions(stop_id, line) if several else frozenset[int]()
        )
        return _LineAtStop(candidates, departing)

    def _resolve(self, arrival: SaeArrival, line: _LineAtStop) -> DestinationResolution | None:
        return resolve_destination(
            arrival.destination,
            line.candidates,
            self._aliases,
            min_score=self._min_score,
            override_headsign=self._overrides.get((arrival.line, arrival.destination)),
            departing_directions=line.departing,
        )

    def _match(
        self,
        stop_id: str,
        arrivals: tuple[SaeArrival, ...],
        resolutions: list[DestinationResolution | None],
    ) -> list[TripCandidate | None]:
        """Trip of each arrival: per (line, direction), the scheduled passages from the first
        arrival − tolerance to the last one + tolerance (design §3)."""
        groups: dict[tuple[str, int], list[int]] = defaultdict(list)
        for index, (arrival, resolution) in enumerate(zip(arrivals, resolutions, strict=True)):
            if resolution is not None:
                groups[(arrival.line, resolution.direction_id)].append(index)
        trips: list[TripCandidate | None] = [None] * len(arrivals)
        for (line, direction_id), indexes in groups.items():
            times = [arrivals[index].arrival_at for index in indexes]
            first, last = min(times), max(times)
            passages = self._network.scheduled_stop_times(
                stop_id, first - self._tolerance, 2 * self._tolerance + (last - first)
            )
            candidates = [
                _trip_candidate(passage)
                for passage in passages
                if passage.line == line and passage.direction_id == direction_id
            ]
            for index, trip in zip(
                indexes, match_trips(times, candidates, self._tolerance), strict=True
            ):
                trips[index] = trip
                if trip is None:
                    self._log.debug(
                        "arrivals.trip_unmatched",
                        stop_id=stop_id,
                        line=line,
                        direction_id=direction_id,
                    )
        return trips

    # --- Fallback ---

    async def _scheduled_views(self, stop_id: str, now: datetime) -> list[ArrivalView]:
        lines: dict[str, Line | None] = {}
        views = []
        for passage in self._scheduled.next_arrivals(stop_id, now):
            if passage.line not in lines:
                lines[passage.line] = self._network.get_line(passage.line)
            line = lines[passage.line]
            vehicle = VehicleView(passage.trip_id, passage.service_date)
            arrival_at = _scheduled_at(passage)
            views.append(
                ArrivalView(
                    line=passage.line,
                    destination=passage.headsign,
                    direction_id=passage.direction_id,
                    in_network=True,
                    kind=ArrivalKind.CLOCK_TIME,
                    minutes=None,
                    arrival_at=arrival_at,
                    line_color=None if line is None else line.color,
                    line_text_color=None if line is None else line.text_color,
                    sae_destination=None,
                    vehicle=vehicle,
                    occupancy=await self._occupancy_of(vehicle, now),
                    can_alert=self._can_alert(
                        in_network=True,
                        direction_id=passage.direction_id,
                        vehicle=vehicle,
                        arrival_at=arrival_at,
                        now=now,
                    ),
                )
            )
        return views

    def _can_alert(
        self,
        *,
        in_network: bool,
        direction_id: int | None,
        vehicle: VehicleView | None,
        arrival_at: datetime,
        now: datetime,
    ) -> bool:
        """alert_create AC-01: the bus is known (paired trip) and arrives within the max lead,
        since an alert expires after that long (RF-21). Same rule for REALTIME and SCHEDULED."""
        return (
            in_network
            and direction_id is not None
            and vehicle is not None
            and arrival_at - now <= self._alert_max_lead
        )

    async def _occupancy_of(
        self, vehicle: VehicleView | None, now: datetime
    ) -> OccupancyStatus | None:
        if vehicle is None:
            return None
        reading = await self._occupancy.read(VehicleRef(vehicle.trip_id, vehicle.service_date), now)
        return None if reading is None else classify_occupancy(reading, self._thresholds)


def _scheduled_at(passage: ScheduledStopTime) -> datetime:
    return service_day_start(passage.service_date) + timedelta(seconds=passage.arrival_s)


def _trip_candidate(passage: ScheduledStopTime) -> TripCandidate:
    return TripCandidate(passage.trip_id, passage.service_date, _scheduled_at(passage))
