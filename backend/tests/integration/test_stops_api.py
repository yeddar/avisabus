"""Stop endpoints over `gtfs_mini` and replayed SAE sessions (stop_arrivals_api T-07, T-08).

`gtfs_mini` has service on Monday 2026-11-02 (the date of `stop_508_peak`) and Tuesday
2026-11-03 (the date of `samples/day_2026-11-03`), so the `FakeClock` is set inside each session.
"""

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine
from structlog.testing import capture_logs

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.adapters.outbound.sae.replay import SaeReplayArrivalsSource
from avisabus.config import ConfigurationError, read_direction_overrides
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival
from avisabus.domain.models.occupancy import VehicleRef
from avisabus.domain.services.occupancy_classifier import classify_occupancy
from avisabus.domain.services.occupancy_simulation import service_day_start
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import DAY, DERIVED_NO_ARRIVALS, NIGHT, STOP_508_PEAK
from tests.support.stops import (
    API,
    import_feed,
    new_engine,
    replay,
    simulated_sensor,
    stops_client,
    stops_settings,
    token,
)

PROBLEM_JSON = "application/problem+json"
PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
DAY_START = datetime(2026, 11, 3, 8, 59, 0, 733841, tzinfo=UTC)
BACKEND = Path(__file__).resolve().parents[2]

ARRIVAL_FIELDS = {
    "line",
    "destination",
    "sae_destination",
    "direction_id",
    "in_network",
    "kind",
    "minutes",
    "arrival_at",
    "line_color",
    "line_text_color",
    "vehicle",
    "occupancy",
    "can_alert",
}


@pytest.fixture(scope="module")
def mini_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    engine = new_engine(tmp_path_factory.mktemp("stops") / "avisabus.sqlite")
    import_feed(engine, GTFS_MINI)
    yield engine
    engine.dispose()


@pytest.fixture
def empty_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = new_engine(tmp_path / "empty.sqlite")
    yield engine
    engine.dispose()


def _peak_clock(offset_s: float = 0) -> FakeClock:
    return FakeClock(PEAK_START + timedelta(seconds=offset_s))


# --- GET /stops/{stop_id} (T-07) ---


@pytest.mark.spec("stop_arrivals_api.AC-01")
async def test_stop_with_its_lines_in_natural_order(mini_engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock)
    repo = SqliteNetworkRepository(mini_engine)
    async with stops_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/stops/508", params={"t": token("508")})
        other = await client.get(f"{API}/stops/2070", params={"t": token("2070")})
    assert response.status_code == 200
    assert response.json() == {
        "stop_id": "508",
        "name": "Parc de l'Oest - Enguera",
        "lines": [
            {
                "line": d.line,
                "direction_id": d.direction_id,
                "headsign": d.headsign,
                "color": d.color,
                "text_color": d.text_color,
            }
            for d in repo.lines_at_stop("508")
        ],
    }
    assert [line["line"] for line in response.json()["lines"]] == ["70", "93"]
    assert response.json()["lines"][0] == {
        "line": "70",
        "direction_id": 1,
        "headsign": "Alboraia",
        "color": "FE0000",
        "text_color": "FFFFFF",
    }
    assert other.json()["lines"] == [
        {
            "line": "98",
            "direction_id": 1,
            "headsign": "Cid - Pere Maria Orts",
            "color": "FE0000",
            "text_color": "FFFFFF",
        }
    ]


def _not_found_requests() -> list[tuple[str, dict[str, str]]]:
    requests = []
    for suffix in ("", "/arrivals"):
        requests += [
            (f"{API}/stops/508{suffix}", {}),  # no token
            (f"{API}/stops/508{suffix}", {"t": ""}),
            (f"{API}/stops/508{suffix}", {"t": "short"}),  # length != 22
            (f"{API}/stops/508{suffix}", {"t": "A" * 22}),  # well formed, wrong
            (f"{API}/stops/508{suffix}", {"t": token("2070")}),  # token of another stop
            (f"{API}/stops/999999{suffix}", {"t": token("999999")}),  # unknown stop
        ]
    return requests


@pytest.mark.spec("stop_arrivals_api.AC-02")
@pytest.mark.spec("stop_arrivals_api.AC-16")
async def test_invalid_token_or_unknown_stop_is_the_same_404(mini_engine: Engine) -> None:
    clock = _peak_clock()
    source, counting = replay(STOP_508_PEAK, clock)
    async with stops_client(mini_engine, clock, source) as (client, _):
        responses = [await client.get(url, params=params) for url, params in _not_found_requests()]
    bodies = set()
    for response in responses:
        assert response.status_code == 404
        assert response.headers["content-type"].startswith(PROBLEM_JSON)
        assert response.headers["cache-control"] == "no-store"
        bodies.add(response.content)
    assert bodies == {
        json.dumps(
            {
                "type": "https://avisabus/problems/stop-not-found",
                "title": "Not Found",
                "status": 404,
            },
            separators=(",", ":"),
        ).encode()
    }
    assert counting.calls == 0  # the SAE is never asked for an unauthenticated stop


@pytest.mark.spec("stop_arrivals_api.AC-03")
@pytest.mark.spec("stop_arrivals_api.AC-16")
@pytest.mark.parametrize("suffix", ["", "/arrivals"])
async def test_no_active_feed_is_503(empty_engine: Engine, suffix: str) -> None:
    clock = _peak_clock()
    source, counting = replay(STOP_508_PEAK, clock)
    async with stops_client(empty_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/stops/508{suffix}", params={"t": token("508")})
    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "type": "https://avisabus/problems/network-unavailable",
        "title": "Service Unavailable",
        "status": 503,
    }
    assert counting.calls == 0


# --- GET /stops/{stop_id}/arrivals: contract (T-07) ---


@pytest.mark.spec("stop_arrivals_api.AC-04")
@pytest.mark.spec("stop_arrivals_api.AC-16")
@pytest.mark.spec("stop_arrivals_api.AC-21")
async def test_arrivals_response_contract(mini_engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock)
    async with stops_client(mini_engine, clock, source) as (client, _):
        stop = await client.get(f"{API}/stops/508", params={"t": token("508")})
        response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    assert stop.headers["cache-control"] == "no-store"
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"stop_id", "source", "generated_at", "refresh_after_s", "arrivals"}
    assert body["stop_id"] == "508"
    assert body["source"] == "REALTIME"
    assert body["generated_at"] == "2026-11-02T19:42:23.769219Z"
    assert body["refresh_after_s"] == 20
    assert body["arrivals"]
    for arrival in body["arrivals"]:
        assert set(arrival) == ARRIVAL_FIELDS
        assert arrival["sae_destination"] in {"Pass. Marítim", "Alboraia"}


@pytest.mark.spec("stop_arrivals_api.AC-04")
async def test_refresh_after_is_the_sae_cache_ttl(mini_engine: Engine) -> None:
    clock = _peak_clock()
    settings = stops_settings(sae_cache_ttl_s=35)
    source, _ = replay(STOP_508_PEAK, clock, ttl_s=35)
    async with stops_client(mini_engine, clock, source, settings=settings) as (client, _):
        response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    assert response.json()["refresh_after_s"] == 35


@pytest.mark.spec("stop_arrivals_api.AC-16")
async def test_openapi_describes_both_endpoints_with_examples(mini_engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock)
    async with stops_client(mini_engine, clock, source) as (client, _):
        spec = (await client.get("/openapi.json")).json()
    schemas = spec["components"]["schemas"]
    for name in ("StopResponse", "StopArrivalsResponse"):
        assert schemas[name]["examples"], name
    example = schemas["StopArrivalsResponse"]["examples"][0]
    assert set(example["arrivals"][0]) == ARRIVAL_FIELDS
    assert set(schemas["ArrivalSchema"]["properties"]) == ARRIVAL_FIELDS
    for path, schema in (
        ("/api/v1/stops/{stop_id}", "StopResponse"),
        ("/api/v1/stops/{stop_id}/arrivals", "StopArrivalsResponse"),
    ):
        get = spec["paths"][path]["get"]
        ok = get["responses"]["200"]["content"]["application/json"]["schema"]
        assert ok == {"$ref": f"#/components/schemas/{schema}"}
        assert {"404", "503"} <= set(get["responses"])
        assert [p["name"] for p in get["parameters"]] == ["stop_id", "t"]


# --- Overrides by headsign (T-07, AC-20) ---


async def _arrivals_at_346(
    engine: Engine, override_entries: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], str]]:
    # Real answer of the C2 terminal 346 (E-03): "Av. Aragó", which matches no headsign by text.
    clock = FakeClock(datetime(2026, 11, 3, 9, 0, 7, tzinfo=UTC))
    source, _ = replay(DAY, clock, start=DAY_START)
    with capture_logs() as logs:
        async with stops_client(engine, clock, source, override_entries=override_entries) as (
            client,
            use_cases,
        ):
            response = await client.get(f"{API}/stops/346/arrivals", params={"t": token("346")})
    c2 = [a for a in response.json()["arrivals"] if a["line"] == "C2"]
    return c2, logs, dict(use_cases.direction_overrides)


@pytest.mark.spec("stop_arrivals_api.AC-20")
async def test_override_entries_are_validated_at_start_up(mini_engine: Engine) -> None:
    entries = {
        "C2|Av. Aragó": "Estació d'autobusos",  # valid: a headsign of C2
        "C3|Campanar": "Avinguda Campanar - Centre de Salut",  # C3 is not in gtfs_mini
        "93|Pass. Marítim": "Passeig Marítim",  # no such headsign of the 93
        "Av. Aragó": "Estació d'autobusos",  # malformed key
    }
    _, logs, valid = await _arrivals_at_346(mini_engine, entries)
    assert valid == {("C2", "Av. Aragó"): "Estació d'autobusos"}
    invalid = [log for log in logs if log["event"] == "arrivals.override_invalid"]
    assert [(log["entry"], log["headsign"], log["reason"]) for log in invalid] == [
        ("C3|Campanar", "Avinguda Campanar - Centre de Salut", "unknown_line"),
        ("93|Pass. Marítim", "Passeig Marítim", "unknown_headsign"),
        ("Av. Aragó", "Estació d'autobusos", "malformed_entry"),
    ]
    assert all(log["log_level"] == "warning" for log in invalid)


@pytest.mark.spec("stop_arrivals_api.AC-20")
@pytest.mark.spec("stop_arrivals_api.AC-19")
async def test_override_by_headsign_is_applied_at_the_stop(mini_engine: Engine) -> None:
    # Without override, the departing direction resolves "Av. Aragó" at 346 (direction 1).
    without, _, _ = await _arrivals_at_346(mini_engine, {})
    assert [(a["direction_id"], a["destination"]) for a in without] == [
        (1, "Estadi de Mestalla (front)"),
        (1, "Estadi de Mestalla (front)"),
    ]
    # A (deliberately wrong) override naming the headsign of direction 0 wins over that rule.
    with_override, _, _ = await _arrivals_at_346(
        mini_engine, {"C2|Av. Aragó": "Estació d'autobusos"}
    )
    assert [(a["direction_id"], a["destination"]) for a in with_override] == [
        (0, "Estació d'autobusos"),
        (0, "Estació d'autobusos"),
    ]
    assert all(a["sae_destination"] == "Av. Aragó" for a in with_override)


@pytest.mark.spec("stop_arrivals_api.AC-20")
def test_shipped_overrides_file_is_valid_and_empty() -> None:
    # Every override proposed by E-01/E-03 is redundant with the v1.4 rules (see
    # tests/unit/test_direction_resolver.py::test_proposed_overrides_are_not_needed_…).
    path = BACKEND / "config" / "direction_overrides.json"
    assert read_direction_overrides(stops_settings(direction_overrides_file=str(path))) == {}
    assert read_direction_overrides(stops_settings()) == {}


@pytest.mark.spec("stop_arrivals_api.AC-20")
def test_overrides_file_is_read_as_entries(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({"C2|Av. Aragó": "Estadi de Mestalla (front)"}), encoding="utf-8")
    settings = stops_settings(direction_overrides_file=str(path))
    assert read_direction_overrides(settings) == {"C2|Av. Aragó": "Estadi de Mestalla (front)"}


@pytest.mark.parametrize(
    "content", [None, "not json", "[]", '{"C2|Av. Aragó": 1}', '{"C2|Av. Aragó": null}']
)
def test_unusable_overrides_file_is_a_configuration_error(
    tmp_path: Path, content: str | None
) -> None:
    path = tmp_path / "overrides.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="AVISABUS_DIRECTION_OVERRIDES_FILE|JSON object"):
        read_direction_overrides(stops_settings(direction_overrides_file=str(path)))


# --- End to end with gtfs_mini and the replayed sessions (T-08) ---


async def _parsed(session: Path, stop_id: str, clock: FakeClock, start: datetime) -> list[Any]:
    """What the SAE said, parsed independently of the API (same replay, no cache)."""
    snapshot = await SaeReplayArrivalsSource(session, clock, start).get_arrivals(stop_id)
    return list(snapshot.arrivals)


def _scheduled_at(
    repo: SqliteNetworkRepository, trip_id: str, service_date: str, stop: str
) -> datetime:
    (stop_time,) = [st for st in repo.trip_stop_times(trip_id) if st.stop_id == stop]
    day = date.fromisoformat(service_date)
    return service_day_start(day) + timedelta(seconds=stop_time.arrival_s)


@pytest.mark.spec("stop_arrivals_api.AC-04")
@pytest.mark.spec("stop_arrivals_api.AC-09")
@pytest.mark.spec("stop_arrivals_api.AC-12")
@pytest.mark.spec("stop_arrivals_api.AC-21")
@pytest.mark.parametrize("offset_s", [0, 520, 1040, 1480])
async def test_realtime_arrivals_of_stop_508(mini_engine: Engine, offset_s: int) -> None:
    clock = _peak_clock(offset_s)
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    settings = stops_settings()
    sensor = simulated_sensor(settings, mini_engine, clock)
    repo = SqliteNetworkRepository(mini_engine)
    async with stops_client(mini_engine, clock, source, sensor=sensor) as (client, _):
        response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    body = response.json()
    assert body["source"] == "REALTIME"
    sae = sorted(await _parsed(STOP_508_PEAK, "508", clock, PEAK_START), key=lambda a: a.arrival_at)
    arrivals = body["arrivals"]
    assert arrivals
    # One entry per SAE arrival, sorted by arrival_at, with the SAE data unchanged.
    assert [
        (a["line"], a["sae_destination"], a["kind"], a["minutes"], a["arrival_at"])
        for a in arrivals
    ] == [
        (
            s.line,
            s.destination,
            s.kind.value,
            s.minutes,
            s.arrival_at.isoformat().replace("+00:00", "Z"),
        )
        for s in sae
    ]
    headsigns = {"70": (1, "Alboraia"), "93": (0, "Passeig Marítim - Hospital Malva-rosa")}
    for arrival in arrivals:
        assert arrival["in_network"] is True
        assert (arrival["direction_id"], arrival["destination"]) == headsigns[arrival["line"]]
        assert (arrival["line_color"], arrival["line_text_color"]) == ("FE0000", "FFFFFF")
        assert arrival["can_alert"] is True
        # Every arrival of the session has a trip within the 10 min tolerance (E-02).
        vehicle = arrival["vehicle"]
        assert vehicle is not None
        assert repo.trip_line(vehicle["trip_id"]) == arrival["line"]
        scheduled = _scheduled_at(repo, vehicle["trip_id"], vehicle["service_date"], "508")
        arrival_at = datetime.fromisoformat(arrival["arrival_at"])
        assert abs(scheduled - arrival_at) <= timedelta(minutes=10)
        # Occupancy of that trip, as the simulated sensor and the classifier give it now.
        reading = await sensor.read(
            VehicleRef(vehicle["trip_id"], date.fromisoformat(vehicle["service_date"])), clock.now()
        )
        assert reading is not None
        status = classify_occupancy(reading, settings.occupancy_thresholds())
        assert arrival["occupancy"] == {
            "level": status.level.value,
            "has_free_seats": status.has_free_seats,
            "free_seats": status.free_seats,
        }
    trips = [(a["line"], a["vehicle"]["trip_id"]) for a in arrivals]
    assert len(set(trips)) == len(trips)  # a trip is never given to two arrivals


@pytest.mark.spec("stop_arrivals_api.AC-10")
async def test_two_93_buses_close_together_get_consecutive_trips(mini_engine: Engine) -> None:
    # 20:48:03 in Madrid (offset 340 s): the SAE gives the 93 in 7 and 8 min (E-02, H-6).
    clock = _peak_clock(340)
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with stops_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    the_93 = [a for a in response.json()["arrivals"] if a["line"] == "93"]
    assert [(a["minutes"], a["vehicle"]["trip_id"]) for a in the_93] == [
        (7, "93_994_561_488_2271_2_122"),
        (8, "93_994_561_488_2271_2_123"),
    ]


@pytest.mark.spec("stop_arrivals_api.AC-08")
@pytest.mark.spec("stop_arrivals_api.AC-04")
@pytest.mark.parametrize("offset_s", [0, 700, 1480])
async def test_lines_outside_gtfs_mini_at_stop_2070(mini_engine: Engine, offset_s: int) -> None:
    # 2070 is served by 73, 95, 98 and 99, but gtfs_mini only has the 98 (design §7, v1.3).
    clock = _peak_clock(offset_s)
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with stops_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/stops/2070/arrivals", params={"t": token("2070")})
    arrivals = response.json()["arrivals"]
    sae = await _parsed(STOP_508_PEAK, "2070", clock, PEAK_START)
    assert len(arrivals) == len(sae)
    outside = [a for a in arrivals if a["line"] in {"73", "95", "99"}]
    assert {a["line"] for a in outside} == {"73", "95", "99"}
    for arrival in outside:
        assert arrival["in_network"] is False
        assert arrival["direction_id"] is None
        assert arrival["vehicle"] is None
        assert arrival["occupancy"] is None
        assert arrival["can_alert"] is False
        assert arrival["line_color"] is None
        assert arrival["line_text_color"] is None
        assert arrival["destination"] == arrival["sae_destination"]
        assert arrival["minutes"] is not None or arrival["kind"] == "CLOCK_TIME"
    for arrival in (a for a in arrivals if a["line"] == "98"):
        assert arrival["in_network"] is True
        assert arrival["direction_id"] == 1
        assert arrival["destination"] == "Cid - Pere Maria Orts"
        assert arrival["sae_destination"] == "Av. Cid"
        assert arrival["can_alert"] is True


@pytest.mark.spec("stop_arrivals_api.AC-12")
async def test_matched_trip_without_sensor_reading(mini_engine: Engine) -> None:
    class NoReadings:
        async def read(self, vehicle: VehicleRef, at: datetime) -> None:
            return None

    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with stops_client(mini_engine, clock, source, sensor=NoReadings()) as (client, _):
        response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    arrivals = response.json()["arrivals"]
    assert arrivals
    assert all(a["vehicle"] is not None and a["occupancy"] is None for a in arrivals)


@pytest.mark.spec("stop_arrivals_api.AC-06")
@pytest.mark.spec("stop_arrivals_api.AC-19")
@pytest.mark.parametrize(
    ("stop_id", "captured", "sae_text", "direction_id", "headsign"),
    [
        ("166", "08:59:45", "Pl. Espanya", 0, "Plaça d'Espanya - Ermita"),
        ("346", "09:00:07", "Av. Aragó", 1, "Estadi de Mestalla (front)"),  # departing direction
        ("691", "09:00:28", "Blasco Ibáñez", 1, "Blasco Ibáñez - Facultat de Geografia"),
        ("1057", "09:00:50", "Est. Autobusos", 0, "Estació d'autobusos"),
    ],
)
async def test_real_c2_terminals_resolve_their_direction(
    mini_engine: Engine,
    stop_id: str,
    captured: str,
    sae_text: str,
    direction_id: int,
    headsign: str,
) -> None:
    clock = FakeClock(datetime.fromisoformat(f"2026-11-03T{captured}+00:00"))
    source, _ = replay(DAY, clock, start=DAY_START)
    repo = SqliteNetworkRepository(mini_engine)
    with capture_logs() as logs:
        async with stops_client(mini_engine, clock, source) as (client, _):
            response = await client.get(
                f"{API}/stops/{stop_id}/arrivals", params={"t": token(stop_id)}
            )
    c2 = [a for a in response.json()["arrivals"] if a["line"] == "C2"]
    assert len(c2) == 2
    for arrival in c2:
        assert arrival["sae_destination"] == sae_text
        assert (arrival["direction_id"], arrival["destination"]) == (direction_id, headsign)
        assert arrival["can_alert"] is True
        # At a terminal the SAE shows the bus that departs (E-03): it has its departing trip.
        assert arrival["vehicle"] is not None
        trip = repo.trip_stop_times(arrival["vehicle"]["trip_id"])
        assert trip[0].stop_id == stop_id
    assert not [log for log in logs if log["event"] == "arrivals.direction_unresolved"]


@pytest.mark.spec("stop_arrivals_api.AC-22")
@pytest.mark.spec("stop_arrivals_api.AC-08")
async def test_duplicate_entries_are_kept(mini_engine: Engine) -> None:
    # 1057 (E-03): "12 C.Art.Faller - 7 min." twice; the 12 is not in gtfs_mini.
    clock = FakeClock(datetime(2026, 11, 3, 9, 0, 50, tzinfo=UTC))
    source, _ = replay(DAY, clock, start=DAY_START)
    async with stops_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/stops/1057/arrivals", params={"t": token("1057")})
    twelve = [a for a in response.json()["arrivals"] if a["line"] == "12"]
    assert len(twelve) == 2
    assert twelve[0] == twelve[1]
    assert twelve[0]["in_network"] is False


@pytest.mark.spec("stop_arrivals_api.AC-07")
async def test_unresolved_direction_is_logged(mini_engine: Engine) -> None:
    class Fixed:
        async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
            # The 98 is in the network but does not stop at 508: no headsign to compare with.
            arrival = SaeArrival(
                "98", "Av. Cid", ArrivalKind.MINUTES, 3, PEAK_START + timedelta(minutes=3)
            )
            return ArrivalsSnapshot(stop_id, PEAK_START, (arrival,))

    clock = _peak_clock()
    with capture_logs() as logs:
        async with stops_client(mini_engine, clock, Fixed()) as (client, _):
            response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    (arrival,) = response.json()["arrivals"]
    assert (arrival["in_network"], arrival["direction_id"], arrival["can_alert"]) == (
        True,
        None,
        False,
    )
    assert arrival["destination"] == "Av. Cid"
    assert arrival["vehicle"] is None
    unresolved = [log for log in logs if log["event"] == "arrivals.direction_unresolved"]
    assert [(log["stop_id"], log["line"], log["destination"]) for log in unresolved] == [
        ("508", "98", "Av. Cid")
    ]


@pytest.mark.spec("stop_arrivals_api.AC-13")
@pytest.mark.spec("stop_arrivals_api.AC-21")
async def test_fallback_to_the_timetable_when_the_sae_fails(mini_engine: Engine) -> None:
    # The night session has no recording of 508: the replay fails with `no_recording`.
    now = datetime(2026, 11, 2, 19, 45, tzinfo=UTC)
    clock = FakeClock(now)
    source, _ = replay(NIGHT, clock)
    repo = SqliteNetworkRepository(mini_engine)
    with capture_logs() as logs:
        async with stops_client(mini_engine, clock, source) as (client, _):
            response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "SCHEDULED"
    expected: list[Any] = []
    taken: dict[tuple[str, int], int] = {}
    for passage in repo.scheduled_stop_times("508", now, timedelta(minutes=90)):
        key = (passage.line, passage.direction_id)
        if taken.get(key, 0) < 2:
            taken[key] = taken.get(key, 0) + 1
            expected.append(passage)
    assert len(expected) == 4
    assert [(a["vehicle"]["trip_id"], a["vehicle"]["service_date"]) for a in body["arrivals"]] == [
        (p.trip_id, p.service_date.isoformat()) for p in expected
    ]
    for arrival, passage in zip(body["arrivals"], expected, strict=True):
        when = service_day_start(passage.service_date) + timedelta(seconds=passage.arrival_s)
        assert arrival["arrival_at"] == when.isoformat().replace("+00:00", "Z")
        assert arrival["kind"] == "CLOCK_TIME"
        assert arrival["minutes"] is None
        assert arrival["destination"] == passage.headsign
        assert arrival["sae_destination"] is None
        assert arrival["direction_id"] == passage.direction_id
        assert arrival["in_network"] is True
        assert arrival["can_alert"] is True
        assert arrival["occupancy"] is not None
    fallback = [log for log in logs if log["event"] == "arrivals.fallback"]
    assert [(log["stop_id"], log["reason"]) for log in fallback] == [("508", "no_recording")]


@pytest.mark.spec("stop_arrivals_api.AC-14")
async def test_fallback_without_passages_in_the_window(mini_engine: Engine) -> None:
    # gtfs_mini has no Saturday service.
    clock = FakeClock(datetime(2026, 11, 7, 11, 0, tzinfo=UTC))
    source, _ = replay(NIGHT, clock)
    async with stops_client(mini_engine, clock, source) as (client, _):
        response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    assert response.status_code == 200
    assert response.json()["source"] == "SCHEDULED"
    assert response.json()["arrivals"] == []


@pytest.mark.spec("stop_arrivals_api.AC-15")
async def test_sae_without_arrivals_does_not_fall_back(mini_engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(DERIVED_NO_ARRIVALS, clock)
    with capture_logs() as logs:
        async with stops_client(mini_engine, clock, source) as (client, _):
            response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    assert response.status_code == 200
    assert response.json()["source"] == "REALTIME"
    assert response.json()["arrivals"] == []
    assert not [log for log in logs if log["event"] == "arrivals.fallback"]


@pytest.mark.spec("stop_arrivals_api.AC-17")
async def test_cached_stop_never_asks_the_sae_again(mini_engine: Engine) -> None:
    clock = _peak_clock()
    source, counting = replay(STOP_508_PEAK, clock)
    async with stops_client(mini_engine, clock, source) as (client, _):
        for _ in range(200):
            response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
            assert response.status_code == 200
        clock.advance(timedelta(seconds=19))
        await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
        assert counting.calls == 1
        clock.advance(timedelta(seconds=1))  # TTL of 20 s reached
        await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    assert counting.calls == 2
