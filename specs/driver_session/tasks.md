# Turno del conductor — tasks

> Feature: `driver_session` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-24, RF-25, RF-26, RF-30, RNF-06, RNF-07, RNF-13 · Casos de uso: CU-08, CU-09 (posición), CU-10, CU-13 (revocación) · Depende de: gtfs_import, driver_codes_cli

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Modelos, puertos, errores, `SqliteDriverSessionRepository` y consulta de turno
  abierto para `driver-codes list/revoke`.
  - AC: driver_session.AC-14
  - Ficheros: `domain/models/driver.py`, `domain/ports/driver.py`, `domain/errors.py`, `adapters/outbound/persistence/{sqlite_driver_sessions,db}.py`, `adapters/inbound/cli/container.py`, `tests/integration/test_driver_session_repository.py`, `tests/integration/test_cli_driver_codes.py`
  - Verificación: `cd backend && uv run pytest -k "driver_session_repository or cli_driver_codes"`

- [ ] **T-02** — `list_lines` y `departures` en la red; `ListDriverLines` y `ListDepartures`.
  - AC: driver_session.AC-05, AC-06
  - Ficheros: `domain/ports/network.py`, `adapters/outbound/persistence/sqlite_network.py`, `application/driver_sessions.py`, `tests/unit/test_departures.py`, `tests/integration/test_network_departures.py`
  - Verificación: `cd backend && uv run pytest -k departures`

- [ ] **T-03** — `project_progress` y `upcoming_stops`.
  - AC: driver_session.AC-09, AC-10
  - Ficheros: `domain/services/upcoming_stops.py`, `tests/unit/test_upcoming_stops.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_upcoming_stops.py`

- [ ] **T-04** — Casos de uso de sesión (inicio con limitador, salida, posición, estado, fin),
  `CloseDriverSession`, `NoopDriverSessionListener`.
  - AC: driver_session.AC-01, AC-02, AC-03, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-15
  - Ficheros: `application/{driver_sessions,close_driver_session}.py`, `adapters/outbound/drivers/noop_session_listener.py`, `tests/unit/test_driver_sessions.py`, `tests/unit/test_driver_login.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_driver_sessions.py tests/unit/test_driver_login.py`

- [ ] **T-05** — Endpoints `/driver`, autenticación por token, errores, configuración y
  composición.
  - AC: driver_session.AC-01 … AC-08, AC-11, AC-12, AC-15
  - Ficheros: `adapters/inbound/http/routes/driver.py`, `adapters/inbound/http/{driver_auth,errors,container,app}.py`, `config.py`, `.env.example`, `tests/integration/test_driver_api.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_driver_api.py`

- [ ] **T-06** — `ReapDriverSessions` y su tarea de fondo.
  - AC: driver_session.AC-13
  - Ficheros: `application/reap_driver_sessions.py`, `background/driver_tasks.py`, `adapters/inbound/http/app.py`, `tests/unit/test_reap_driver_sessions.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_reap_driver_sessions.py`

- [ ] **T-07** — Regenerar el contrato del frontend (`npm run gen:api`) y verificación completa.
  - Verificación: `./init.sh verify`
