"""AC-09 (v1.1) with every shape of the real feed (`data/gtfs/emt/`, not versioned). Slow and
manual:

    cd backend && uv run pytest -m slow tests/integration/test_upcoming_stops_real_shapes.py -s

Skipped when the feed is not present. Each shape is driven at 30 km/h with a position every 5 s,
through the real `UpdateDriverPosition`, with a `FakeClock` and Gaussian noise of fixed seed. The
bus moves in real metres along the shape and the errors are measured in real metres: the
`shape_dist_traveled` of EMT's feed is not in metres (see Bloqueos of
`progress/impl_driver_session.md`). The figures go to stdout (`-s`).
"""

import bisect
import csv
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from avisabus.application.driver_sessions import (
    TripRoute,
    UpdateDriverPosition,
    UpdateDriverPositionCommand,
)
from avisabus.domain.models.driver import DriverService
from avisabus.domain.models.network import ShapePoint
from avisabus.domain.services.geometry import (
    EARTH_RADIUS_M,
    cumulative_distances,
    point_at_distance,
    shape_distances,
)
from tests.support.drivers import InMemorySessions, RecordingListener, session_of
from tests.support.fake_clock import FakeClock

REAL_FEED = Path(__file__).resolve().parents[3] / "data" / "gtfs" / "emt"
SPEED_MPS = 30 / 3.6
STEP_S = 5
MAX_ERROR_M = 100.0
SEED = 20261109
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
    shapes: int = 0
    positions: int = 0
    max_ahead_m: float = 0.0
    max_behind_m: float = 0.0
    beyond_ahead: int = 0
    beyond_behind: int = 0
    shapes_beyond: int = 0
    no_progress: int = 0


class _Routes:
    def __init__(self, route: TripRoute) -> None:
        self._route = route

    def of(self, _trip_id: str) -> TripRoute:
        return self._route


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


def _in_metres(progress: float, route: list[float], metres: list[float]) -> float:
    """Real metres along the shape of a progress measured with the distances of the route."""
    n = max(min(bisect.bisect_right(route, progress) - 1, len(route) - 2), 0)
    span = route[n + 1] - route[n]
    fraction = 0.0 if span <= 0 else (progress - route[n]) / span
    return metres[n] + fraction * (metres[n + 1] - metres[n])


async def _drive(shape_id: str, shape: list[ShapePoint], noise: Noise, figures: Figures) -> None:
    distances = shape_distances(shape)  # the distances `TripRoutes` gives the use case
    metres = cumulative_distances(shape)
    clock = FakeClock(START)
    sessions = InMemorySessions(session_of(1, SERVICE))
    route = TripRoute(tuple(shape), tuple(distances), ())
    update = UpdateDriverPosition(sessions, _Routes(route), RecordingListener(), clock)  # type: ignore[arg-type]
    rng = random.Random(f"{SEED}:{shape_id}:{noise.name}")  # noqa: S311 - reproducible noise
    east = rng.gauss(0, noise.sigma_m) if noise.sigma_m else 0.0
    north = rng.gauss(0, noise.sigma_m) if noise.sigma_m else 0.0
    innovation = noise.sigma_m * math.sqrt(1 - noise.rho**2)
    total = metres[-1]
    step = 0
    beyond = False
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
        figures.positions += 1
        if progress is None:
            figures.no_progress += 1
            beyond = True
        else:
            error = _in_metres(progress, distances, metres) - real
            figures.max_ahead_m = max(figures.max_ahead_m, error)
            figures.max_behind_m = max(figures.max_behind_m, -error)
            if error > MAX_ERROR_M:
                figures.beyond_ahead += 1
                beyond = True
            elif -error > MAX_ERROR_M:
                figures.beyond_behind += 1
                beyond = True
        if real >= total:
            break
        step += 1
        clock.advance(timedelta(seconds=STEP_S))
        east = noise.rho * east + rng.gauss(0, innovation) if noise.sigma_m else 0.0
        north = noise.rho * north + rng.gauss(0, innovation) if noise.sigma_m else 0.0
    figures.shapes += 1
    figures.shapes_beyond += beyond


async def _figures(shapes: dict[str, list[ShapePoint]], noise: Noise) -> Figures:
    figures = Figures()
    for shape_id in sorted(shapes):
        await _drive(shape_id, shapes[shape_id], noise, figures)
    print(  # noqa: T201 - figures for the progress notes (`-s`)
        f"AC-09 real shapes [{noise.name}]: shapes={figures.shapes} "
        f"positions={figures.positions} max_ahead={figures.max_ahead_m:.1f} m "
        f"max_behind={figures.max_behind_m:.1f} m beyond_ahead={figures.beyond_ahead} "
        f"beyond_behind={figures.beyond_behind} shapes_beyond={figures.shapes_beyond} "
        f"no_progress={figures.no_progress}"
    )
    return figures


def _assert_within(figures: Figures) -> None:
    assert figures.shapes == 94
    assert figures.no_progress == 0
    assert figures.beyond_ahead == 0
    assert figures.beyond_behind == 0


@pytest.mark.spec("driver_session.AC-09")
@pytest.mark.parametrize(
    "noise",
    [Noise("sigma10_correlated", 10.0, 0.95), Noise("sigma10_independent", 10.0, 0.0)],
    ids=lambda noise: noise.name,
)
async def test_progress_stays_within_100_m_of_the_real_position(
    shapes: dict[str, list[ShapePoint]], noise: Noise
) -> None:
    _assert_within(await _figures(shapes, noise))


@pytest.mark.spec("driver_session.AC-09")
async def test_without_noise_the_progress_follows_the_bus(
    shapes: dict[str, list[ShapePoint]],
) -> None:
    """Control: an error here would be of the simulation, not of the noise."""
    _assert_within(await _figures(shapes, Noise("no_noise", 0.0, 0.0)))
