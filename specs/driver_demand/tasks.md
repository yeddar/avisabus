# Demanda del conductor — tasks

> Feature: `driver_demand` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-23, RF-27, RF-28, RF-29, RNF-02, RNF-06 · Casos de uso: CU-03 (5a), CU-09, CU-10 (3) · Depende de: realtime_events, alert_create, driver_session

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — `DriverView`, `stop_demand`, `capacity_flags` y `BuildDriverView`.
  - AC: driver_demand.AC-05, AC-06, AC-07
  - Ficheros: `domain/models/driver_view.py`, `domain/services/demand.py`, `application/build_driver_view.py`, `tests/unit/test_demand.py`, `tests/unit/test_build_driver_view.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_demand.py tests/unit/test_build_driver_view.py`

- [ ] **T-02** — Repositorio de avisos ampliado, `SessionDriverDirectory`, `DeliverPendingAlerts`,
  `UndeliverSessionAlerts`.
  - AC: driver_demand.AC-01, AC-02, AC-03, AC-12
  - Ficheros: `adapters/outbound/persistence/sqlite_alerts.py`, `adapters/outbound/drivers/session_directory.py`, `application/deliver_alerts.py`, `tests/unit/test_deliver_alerts.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_deliver_alerts.py`

- [ ] **T-03** — `DemandViews`, `DemandSessionListener`, `DemandViewNotifier` y refresco de 15 s.
  - AC: driver_demand.AC-04, AC-09
  - Ficheros: `application/demand_views.py`, `adapters/outbound/drivers/demand_listener.py`, `background/driver_tasks.py`, `tests/unit/test_demand_views.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_demand_views.py`

- [ ] **T-04** — `/ws/driver`, `GET /sessions/current/view` y composición (sustituir los
  componentes vacíos del bloque 3 y de `driver_session`).
  - AC: driver_demand.AC-01 … AC-04, AC-08, AC-10, AC-11
  - Ficheros: `adapters/inbound/ws/driver.py`, `adapters/inbound/http/routes/driver.py`, `adapters/inbound/http/{container,app}.py`, `tests/integration/test_driver_demand.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_driver_demand.py`

- [ ] **T-05** — Regenerar el contrato del frontend y verificación completa.
  - Verificación: `./init.sh verify`
