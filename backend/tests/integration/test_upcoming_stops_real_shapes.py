"""AC-09 (v1.4) with every shape of the real feed (`data/gtfs/emt/`, not versioned). Slow and
manual:

    cd backend && uv run pytest -m slow tests/integration/test_upcoming_stops_real_shapes.py

Skipped when the feed is not present. Each shape is driven at 30 km/h with a position every 5 s,
through the real `UpdateDriverPosition` and `TripRoutes`, with a `FakeClock` and Gaussian noise of
σ = 10 m (correlated, ρ = 0.95, and independent) with the seeds 1 to 20. The bus moves and the
errors are measured in real metres (the `shape_dist_traveled` of EMT's feed is not in metres).

AC-09 v1.4, for each noise model over the positions of the 20 seeds: at least 99.5 % with the
progress less than 150 m from the real one, and none more than 150 m ahead nor more than 500 m
behind (the U-turn lag is accepted). The result of every seed is printed even when the test
passes, and is part of the failure message.
"""

import csv
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from avisabus.application.driver_sessions import (
    TripRoutes,
    UpdateDriverPosition,
    UpdateDriverPositionCommand,
)
from avisabus.domain.models.driver import DriverService
from avisabus.domain.models.network import FeedVersion, ShapePoint, Stop, TripStopTime
from avisabus.domain.services.geometry import (
    EARTH_RADIUS_M,
    cumulative_distances,
    point_at_distance,
)
from tests.support.drivers import InMemorySessions, RecordingListener, session_of
from tests.support.fake_clock import FakeClock

REAL_FEED = Path(__file__).resolve().parents[3] / "data" / "gtfs" / "emt"
REAL_SHAPES = 94
SPEED_MPS = 30 / 3.6
STEP_S = 5
SEEDS = range(1, 21)
NEAR_M = 150.0  # "a menos de 150 m del real"
MIN_NEAR_SHARE = 0.995  # "AL MENOS el 99,5 % de las posiciones"
MAX_AHEAD_M = 150.0  # "NINGUNA … más de 150 m por delante"
MAX_BEHIND_M = 500.0  # "… ni más de 500 m por detrás"
START = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
TRIP_ID = "trip"
SERVICE = DriverService("93", 0, TRIP_ID, date(2026, 11, 9))

pytestmark = [
    pytest.mark.slow,
    pytest.mark.timeout(900),
    pytest.mark.skipif(not (REAL_FEED / "shapes.txt").is_file(), reason="no real feed"),
]


@dataclass(frozen=True)
class Noise:
    name: str
    sigma_m: float
    rho: float


@dataclass
class Figures:
    """Errors of one seed (or of the control) over every shape. Error = progress − real."""

    seed: int | None
    shapes: int = 0
    positions: int = 0
    near: int = 0
    no_progress: int = 0
    max_ahead_m: float = 0.0
    max_behind_m: float = 0.0
    too_far_ahead: int = 0
    too_far_behind: int = 0
    # shape_id → (positions not near, worst |error|)
    shapes_not_near: dict[str, tuple[int, float]] = field(default_factory=dict)

    def record(self, shape_id: str, error: float | None) -> None:
        self.positions += 1
        if error is None:
            self.no_progress += 1
            self._not_near(shape_id, math.inf)
            return
        self.max_ahead_m = max(self.max_ahead_m, error)
        self.max_behind_m = max(self.max_behind_m, -error)
        if error > MAX_AHEAD_M:
            self.too_far_ahead += 1
        if -error > MAX_BEHIND_M:
            self.too_far_behind += 1
        if abs(error) < NEAR_M:
            self.near += 1
        else:
            self._not_near(shape_id, abs(error))

    def _not_near(self, shape_id: str, error: float) -> None:
        count, worst = self.shapes_not_near.get(shape_id, (0, 0.0))
        self.shapes_not_near[shape_id] = (count + 1, max(worst, error))

    def line(self, noise: Noise) -> str:
        share = 100 * self.near / self.positions if self.positions else 0.0
        not_near = ", ".join(
            f"{shape_id}×{count} (máx {worst:.1f} m)"
            for shape_id, (count, worst) in sorted(self.shapes_not_near.items())
        )
        return (
            f"AC-09 real shapes [{noise.name}] seed={self.seed} shapes={self.shapes} "
            f"positions={self.positions} near={self.near} ({share:.3f} %) "
            f"max_ahead={self.max_ahead_m:.1f} m max_behind={self.max_behind_m:.1f} m "
            f"ahead>{MAX_AHEAD_M:.0f}={self.too_far_ahead} "
            f"behind>{MAX_BEHIND_M:.0f}={self.too_far_behind} "
            f"no_progress={self.no_progress} not_near=[{not_near}]"
        )


class _OneShapeNetwork:
    """What `TripRoutes` reads of the network, for one trip that follows `shape`."""

    def __init__(self, shape: list[ShapePoint]) -> None:
        self._shape = shape
        day = date(2026, 11, 1)
        self._feed = FeedVersion(1, "real", START, day, day, {})

    def active_feed(self) -> FeedVersion:
        return self._feed

    def trip_shape_id(self, _trip_id: str) -> str:
        return "shape"

    def trip_stop_times(self, _trip_id: str) -> list[TripStopTime]:
        return [TripStopTime("first", 1, 0, 0, self._shape[0].dist_traveled)]

    def shape_points(self, _shape_id: str) -> list[ShapePoint]:
        return self._shape

    def get_stop(self, stop_id: str) -> Stop:
        return Stop(stop_id, stop_id, self._shape[0].lat, self._shape[0].lon)


def _table(name: str) -> list[dict[str, str]]:
    with (REAL_FEED / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _real_shapes() -> dict[str, list[ShapePoint]]:
    """Every shape used by some trip, as the import keeps them."""
    used = {row["shape_id"].strip() for row in _table("trips.txt")}
    points: dict[str, list[ShapePoint]] = defaultdict(list)
    for row in _table("shapes.txt"):
        shape_id = row["shape_id"].strip()
        if shape_id in used:
            dist = row["shape_dist_traveled"].strip()
            points[shape_id].append(
                ShapePoint(
                    float(row["shape_pt_lat"]),
                    float(row["shape_pt_lon"]),
                    int(row["shape_pt_sequence"]),
                    float(dist) if dist else None,
                )
            )
    for shape in points.values():
        shape.sort(key=lambda point: point.sequence)
    return dict(points)


@pytest.fixture(scope="module")
def shapes() -> dict[str, list[ShapePoint]]:
    return _real_shapes()


def _offset(lat: float, lon: float, east_m: float, north_m: float) -> tuple[float, float]:
    return (
        lat + math.degrees(north_m / EARTH_RADIUS_M),
        lon + math.degrees(east_m / (EARTH_RADIUS_M * math.cos(math.radians(lat)))),
    )


async def _drive(shape_id: str, shape: list[ShapePoint], noise: Noise, figures: Figures) -> None:
    metres = cumulative_distances(shape)
    clock = FakeClock(START)
    sessions = InMemorySessions(session_of(1, SERVICE))
    routes = TripRoutes(_OneShapeNetwork(shape))  # type: ignore[arg-type]
    update = UpdateDriverPosition(sessions, routes, RecordingListener(), clock)
    rng = random.Random(f"{figures.seed}:{shape_id}:{noise.name}")  # noqa: S311 - reproducible
    east = rng.gauss(0, noise.sigma_m) if noise.sigma_m else 0.0
    north = rng.gauss(0, noise.sigma_m) if noise.sigma_m else 0.0
    innovation = noise.sigma_m * math.sqrt(1 - noise.rho**2)
    total = metres[-1]
    step = 0
    while True:
        real = min(step * SPEED_MPS * STEP_S, total)
        point = point_at_distance(shape, metres, real)
        lat, lon = _offset(point.lat, point.lon, east, north)
        await update.execute(
            UpdateDriverPositionCommand(
                session=sessions.rows["session-1"],
                lat=lat,
                lon=lon,
                accuracy_m=noise.sigma_m,
                recorded_at=clock.now(),
            )
        )
        progress = sessions.rows["session-1"].progress_m
        figures.record(shape_id, None if progress is None else progress - real)
        if real >= total:
            break
        step += 1
        clock.advance(timedelta(seconds=STEP_S))
        east = noise.rho * east + rng.gauss(0, innovation) if noise.sigma_m else 0.0
        north = noise.rho * north + rng.gauss(0, innovation) if noise.sigma_m else 0.0
    figures.shapes += 1


async def _figures(shapes: dict[str, list[ShapePoint]], noise: Noise, seed: int | None) -> Figures:
    figures = Figures(seed)
    for shape_id in sorted(shapes):
        await _drive(shape_id, shapes[shape_id], noise, figures)
    return figures


def _report(capsys: pytest.CaptureFixture[str], lines: list[str]) -> str:
    text = "\n".join(lines)
    with capsys.disabled():
        print("\n" + text)  # noqa: T201 - AC-09 v1.4: the result of every seed is reported
    return text


_NOISES = [
    Noise("sigma10_correlated", 10.0, 0.95),
    Noise("sigma10_independent", 10.0, 0.0),
]


@pytest.mark.spec("driver_session.AC-09")
@pytest.mark.parametrize("noise", _NOISES, ids=lambda noise: noise.name)
async def test_progress_with_seeds_1_to_20_meets_the_percentile_and_the_maxima(
    shapes: dict[str, list[ShapePoint]], noise: Noise, capsys: pytest.CaptureFixture[str]
) -> None:
    per_seed = [await _figures(shapes, noise, seed) for seed in SEEDS]
    positions = sum(figures.positions for figures in per_seed)
    near = sum(figures.near for figures in per_seed)
    too_far_ahead = sum(figures.too_far_ahead for figures in per_seed)
    too_far_behind = sum(figures.too_far_behind for figures in per_seed)
    report = _report(
        capsys,
        [figures.line(noise) for figures in per_seed]
        + [
            f"AC-09 real shapes [{noise.name}] seeds 1-20: positions={positions} near={near} "
            f"({100 * near / positions:.3f} %, min {100 * MIN_NEAR_SHARE:.1f} %) "
            f"max_ahead={max(f.max_ahead_m for f in per_seed):.1f} m "
            f"max_behind={max(f.max_behind_m for f in per_seed):.1f} m "
            f"ahead>{MAX_AHEAD_M:.0f}={too_far_ahead} behind>{MAX_BEHIND_M:.0f}={too_far_behind}"
        ],
    )

    assert all(figures.shapes == REAL_SHAPES for figures in per_seed), report
    assert near >= MIN_NEAR_SHARE * positions, report
    assert too_far_ahead == 0, report
    assert too_far_behind == 0, report


@pytest.mark.spec("driver_session.AC-09")
async def test_without_noise_the_progress_follows_the_bus(
    shapes: dict[str, list[ShapePoint]], capsys: pytest.CaptureFixture[str]
) -> None:
    """Control: an error here would be of the simulation, not of the noise."""
    noise = Noise("no_noise", 0.0, 0.0)
    figures = await _figures(shapes, noise, None)
    report = _report(capsys, [figures.line(noise)])

    assert figures.shapes == REAL_SHAPES, report
    assert figures.near == figures.positions, report
