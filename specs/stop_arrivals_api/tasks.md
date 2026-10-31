# API de parada y llegadas — tasks

> Feature: `stop_arrivals_api` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-06, RF-09, RF-11, RF-15, RF-32, RNF-01, RNF-08 · Casos de uso: CU-01 · Depende de: gtfs_import, stop_tokens_qr, sae_arrivals_source, occupancy_sensor

## Exploración

- **E-01** — Destinos del SAE frente a headsigns del GTFS. Con las grabaciones de
  `tests/fixtures/sae_recordings/` y, si hace falta, nuevas consultas puntuales (≤ 1 cada 20 s por
  parada) a 20 paradas variadas (incluidas 508, 2070, una de cabecera y una de circular C1/C2/C3):
  tabla `línea | destino SAE | headsigns GTFS de esa línea en la parada | ¿un solo sentido?`.
  Proponer entradas de alias y *overrides*, y medir qué porcentaje resuelve el algoritmo de
  design §3 con `min_score = 0.34`. → `progress/explore_destinations.md`
- **E-02** — Tolerancia de emparejamiento: con `stop_508_peak` y `gtfs_mini`, distribución de
  `|arrival_at − scheduled_at|` del mejor candidato; confirmar o proponer otra tolerancia.
  → `progress/explore_destinations.md`

> Si el porcentaje de resolución de E-01 es < 90 % de las llegadas en red, → CP-3 (puede requerir
> otra estrategia).

## Tareas

- [ ] **T-01** — Modelos `ArrivalView`, `StopArrivals`, `StopView`, `VehicleView`, `ArrivalSource`.
  - AC: (base)
  - Ficheros: `domain/models/stop_arrivals.py`
  - Verificación: `cd backend && uv run mypy`

- [ ] **T-02** — `normalize_destination` y `resolve_direction` con casos de E-01 y alias.
  - AC: stop_arrivals_api.AC-05, AC-06, AC-07, AC-09
  - Ficheros: `domain/services/direction_resolver.py`, `tests/unit/test_direction_resolver.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_direction_resolver.py`

- [ ] **T-03** — `match_trips` (proximidad, tolerancia, unicidad y orden).
  - AC: stop_arrivals_api.AC-10, AC-11
  - Ficheros: `domain/services/trip_matcher.py`, `tests/unit/test_trip_matcher.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_trip_matcher.py`

- [ ] **T-04** — `GetStop` (token, parada, líneas, errores).
  - AC: stop_arrivals_api.AC-01, AC-02, AC-03
  - Ficheros: `application/get_stop.py`, `domain/errors.py`, `tests/unit/test_get_stop.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_get_stop.py`

- [ ] **T-05** — `ScheduledArrivalsProvider`.
  - AC: stop_arrivals_api.AC-13, AC-14
  - Ficheros: `application/scheduled_arrivals.py`, `tests/unit/test_scheduled_arrivals.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_scheduled_arrivals.py`

- [ ] **T-06** — `GetStopArrivals` (enriquecimiento, líneas fuera de red, ocupación, respaldo,
  logs).
  - AC: stop_arrivals_api.AC-04, AC-07, AC-08, AC-11, AC-12, AC-13, AC-14, AC-15
  - Ficheros: `application/get_stop_arrivals.py`, `tests/unit/test_get_stop_arrivals.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_get_stop_arrivals.py`

- [ ] **T-07** — Endpoints, esquemas Pydantic con ejemplos, mapeo de errores, `Cache-Control`,
  composición en `main.py`, carga del fichero de *overrides*.
  - AC: stop_arrivals_api.AC-01, AC-02, AC-03, AC-04, AC-16
  - Ficheros: `adapters/inbound/http/routes/stops.py`, `adapters/inbound/http/errors.py`, `main.py`, `config.py`, `.env.example`
  - Verificación: `cd backend && uv run pytest tests/integration/test_stops_api.py`

- [ ] **T-08** — Tests de integración de extremo a extremo con `gtfs_mini` + replay
  `stop_508_peak` + `samples/`, incluido el caso fuera de red y el respaldo.
  - AC: stop_arrivals_api.AC-04, AC-08, AC-12, AC-13, AC-15, AC-17
  - Ficheros: `tests/integration/test_stops_api.py`, `tests/integration/test_stops_api_perf.py` (`slow`)
  - Verificación: `cd backend && uv run pytest tests/integration/test_stops_api.py && uv run pytest -m slow tests/integration/test_stops_api_perf.py`

- [ ] **T-09** — Verificación completa.
  - Verificación: `./init.sh verify`
