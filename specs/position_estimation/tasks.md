# Estimación de la posición del autobús — tasks

> Feature: `position_estimation` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-12, RNF-01 · Casos de uso: CU-02 · Depende de: gtfs_import, stop_arrivals_api

## Exploración

No necesaria (los datos de `shape_dist_traveled` se confirmaron con las cabeceras del feed y la
exploración de `gtfs_import`).

## Tareas

- [ ] **T-01** — Geometría: `haversine_m`, `cumulative_distances`, `point_at_distance`,
  `bearing_deg`, `project_onto_shape` (monótona).
  - AC: position_estimation.AC-05, AC-06
  - Ficheros: `domain/services/geometry.py`, `tests/unit/test_geometry.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_geometry.py`

- [ ] **T-02** — Modelos de posición y `estimate_position` con el viaje sintético.
  - AC: position_estimation.AC-01, AC-02, AC-03, AC-04, AC-07, AC-08
  - Ficheros: `domain/models/position.py`, `domain/services/position_estimator.py`, `tests/unit/test_position_estimator.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_position_estimator.py`

- [ ] **T-03** — Ampliación de `NetworkRepository`: `trip_shape_id`, `shape_stops`, `shape_line`.
  - AC: (soporte de AC-09, AC-13)
  - Ficheros: `domain/ports/network.py`, `adapters/outbound/persistence/sqlite_network.py`, `tests/integration/test_network_repository.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_network_repository.py -k "shape"`

- [ ] **T-04** — `GetVehiclePosition` (con fakes: llegada con viaje, sin viaje, sin llegada,
  horario programado, línea que no pasa).
  - AC: position_estimation.AC-09, AC-10, AC-11, AC-12
  - Ficheros: `application/get_vehicle_position.py`, `domain/errors.py`, `tests/unit/test_get_vehicle_position.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_get_vehicle_position.py`

- [ ] **T-05** — `GetShape` y endpoint `/shapes/{shape_id}` con `ETag`, `304` y caché.
  - AC: position_estimation.AC-13, AC-14, AC-15
  - Ficheros: `application/get_shape.py`, `adapters/inbound/http/routes/shapes.py`, `tests/integration/test_shapes_api.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_shapes_api.py`

- [ ] **T-06** — Endpoint de posición, `GZipMiddleware`, composición en `main.py`.
  - AC: position_estimation.AC-09, AC-10, AC-11, AC-12, AC-16
  - Ficheros: `adapters/inbound/http/routes/position.py`, `adapters/inbound/http/app.py`, `main.py`, `tests/integration/test_position_api.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_position_api.py`

- [ ] **T-07** — Test de coherencia con la sesión real `stop_508_peak`.
  - AC: position_estimation.AC-17
  - Ficheros: `tests/integration/test_position_real_session.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_position_real_session.py`

- [ ] **T-08** — Regenerar el contrato del frontend (`npm run gen:api`) si existe
  `frontend/src/shared/api/openapi.json`, y verificación completa.
  - Verificación: `./init.sh verify`
