# API de parada y llegadas — tasks

> Feature: `stop_arrivals_api` · Versión: 1.4 · Estado: APPROVED
> Requisitos: RF-06, RF-09, RF-11, RF-15, RF-32, RNF-01, RNF-08 · Casos de uso: CU-01 · Depende de: gtfs_import, stop_tokens_qr, sae_arrivals_source, occupancy_sensor

## Exploración

- **E-01** — Destinos del SAE frente a headsigns del GTFS. Con las grabaciones de
  `tests/fixtures/sae_recordings/` y, si hace falta, nuevas consultas puntuales (≤ 1 cada 20 s por
  parada) a 20 paradas variadas (incluidas 508, 2070, una de cabecera y una de circular C1/C2/C3):
  tabla `línea | destino SAE | headsigns GTFS de esa línea en la parada | ¿un solo sentido?`.
  Proponer entradas de alias y *overrides*, y medir qué porcentaje resuelve el algoritmo de
  design §3 con `min_score = 0.34`.
  **Circulares (v1.1):** en el GTFS, C1, C2 y C3 vienen partidas en medios viajes con un destino en
  cada mitad (`progress/explore_gtfs_feed.md`). Comprobar en paradas de C1, C2 y C3 qué `destino`
  devuelve el SAE: si coincide con el destino del medio bucle, no hace falta nada; si es genérico
  (p. ej. "Circular") → proponer cómo resolver el sentido (p. ej. por sentido único en esa parada,
  que el GTFS garantiza si ningún medio bucle repite parada) o CP-3.
  → `progress/explore_destinations.md`
- **E-02** — Tolerancia de emparejamiento: con `stop_508_peak` y `gtfs_mini`, distribución de
  `|arrival_at − scheduled_at|` del mejor candidato; confirmar o proponer otra tolerancia.
  → `progress/explore_destinations.md`

> **v1.4:** E-01, E-02 y E-03 completadas (`progress/explore_destinations.md`, muestras en
> `progress/explore_destinations_samples/`). Resolución observada: 99,2 %. CP-3 resuelto. No repetir.

## Tareas

- [ ] **T-01** — Modelos `ArrivalView`, `StopArrivals`, `StopView`, `VehicleView`, `ArrivalSource`.
  - AC: (base)
  - Ficheros: `domain/models/stop_arrivals.py`
  - Verificación: `cd backend && uv run mypy`

- [ ] **T-02** — `normalize_destination` y `resolve_direction` (orden de resolución v1.4, alias
  revisados, prefijos 1 a 1, umbral 0,2, override por headsign, sentido que sale) con la tabla de
  casos reales de E-01 y E-03 (H-2, H-7), incluidas las cabeceras de C1 con "Cntr.Històric".
  - AC: stop_arrivals_api.AC-05, AC-06, AC-07, AC-09, AC-19, AC-20
  - Ficheros: `domain/services/direction_resolver.py`, `tests/unit/test_direction_resolver.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_direction_resolver.py`

- [ ] **T-03** — `match_trips` con asignación **óptima con orden** (v1.4), tolerancia 10 min,
  desempate determinista y duplicados; incluir el caso real de la 93 en la 508 de E-02.
  - AC: stop_arrivals_api.AC-10, AC-11, AC-22
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

- [ ] **T-05b** — Ampliar `SqliteNetworkRepository.scheduled_stop_times` (código de `gtfs_import`,
  modificación autorizada por esta tarea) para recorrer los días de servicio de `fecha(at) − 1` a
  `fecha(at + window)`. Test con una copia de `gtfs_mini` (helper `tests/support/gtfs.py`) que
  añade un viaje a las 00:20 del día de servicio siguiente. Los tests de `gtfs_import` AC-15 deben
  seguir pasando.
  - AC: stop_arrivals_api.AC-18
  - Ficheros: `adapters/outbound/persistence/sqlite_network.py`, `tests/integration/test_network_repository.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_network_repository.py`

- [ ] **T-05c** — Ampliar `NetworkRepository` con `departing_directions(stop_id, line)` (código de
  `gtfs_import`, modificación autorizada por esta tarea), con test sobre `gtfs_mini` (C2 en sus
  cabeceras).
  - AC: stop_arrivals_api.AC-19
  - Ficheros: `domain/ports/network.py`, `adapters/outbound/persistence/sqlite_network.py`, `tests/integration/test_network_repository.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_network_repository.py -k departing`

- [ ] **T-06** — `GetStopArrivals` (enriquecimiento, líneas fuera de red, ocupación, respaldo,
  logs).
  - AC: stop_arrivals_api.AC-04, AC-07, AC-08, AC-11, AC-12, AC-13, AC-14, AC-15, AC-21
  - Ficheros: `application/get_stop_arrivals.py`, `tests/unit/test_get_stop_arrivals.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_get_stop_arrivals.py`

- [ ] **T-07** — Endpoints, esquemas Pydantic con ejemplos (incluido `sae_destination`), mapeo de
  errores, `Cache-Control`, composición en `main.py`, carga y **validación** del fichero de
  *overrides* por headsign (AC-20) y fichero inicial `config/direction_overrides.json`.
  - AC: stop_arrivals_api.AC-01, AC-02, AC-03, AC-04, AC-16, AC-20, AC-21
  - Ficheros: `adapters/inbound/http/routes/stops.py`, `adapters/inbound/http/errors.py`, `main.py`, `config.py`, `.env.example`
  - Verificación: `cd backend && uv run pytest tests/integration/test_stops_api.py`

- [ ] **T-08** — Tests de integración de extremo a extremo con `gtfs_mini` + replay
  `stop_508_peak` + `samples/`, incluido el caso fuera de red y el respaldo.
  - AC: stop_arrivals_api.AC-04, AC-08, AC-12, AC-13, AC-15, AC-17
  - Ficheros: `tests/integration/test_stops_api.py`, `tests/integration/test_stops_api_perf.py` (`slow`)
  - Verificación: `cd backend && uv run pytest tests/integration/test_stops_api.py && uv run pytest -m slow tests/integration/test_stops_api_perf.py`

- [ ] **T-09** — Verificación completa.
  - Verificación: `./init.sh verify`
