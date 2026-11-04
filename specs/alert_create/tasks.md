# Crear solicitud de parada — tasks

> Feature: `alert_create` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-16, RF-17, RF-19, RF-20, RF-23, RNF-02, RNF-06, RNF-07 · Casos de uso: CU-03 · Depende de: stop_arrivals_api, realtime_events

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Regla nueva de `can_alert` en `GetStopArrivals` (parámetro `alert_max_lead`,
  `AVISABUS_ALERT_MAX_LEAD_MIN`) y actualización de los tests de `stop_arrivals_api` que la
  contradicen (AC-11 y AC-13 de `stop_arrivals_api` v1.6).
  - AC: alert_create.AC-01
  - Ficheros: `application/get_stop_arrivals.py`, `adapters/inbound/http/container.py`, `config.py`, `.env.example`, `tests/unit/test_get_stop_arrivals.py`, `tests/integration/test_stops_api.py`
  - Verificación: `cd backend && uv run pytest -k "stop_arrivals or stops_api"`

- [ ] **T-02** — Modelos (`Need`, `AlertStatus`, `Alert`, `AlertTracking`), puertos, errores y
  `InMemoryRateLimiter`.
  - AC: alert_create.AC-06, AC-08
  - Ficheros: `domain/models/alert.py`, `domain/ports/alerts.py`, `domain/errors.py`, `adapters/outbound/rate_limit/in_memory.py`, `tests/unit/test_rate_limiter.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_rate_limiter.py`

- [ ] **T-03** — `SqliteAlertRepository` y tabla `alert` en `init_db`.
  - AC: alert_create.AC-07, AC-12
  - Ficheros: `adapters/outbound/persistence/{sqlite_alerts,db}.py`, `tests/integration/test_alert_repository.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_alert_repository.py`

- [ ] **T-04** — `CreateAlert`, `ListMyAlerts`, `alert_payload`, `NoDriverDirectory` y
  `NoopDriverViewNotifier`.
  - AC: alert_create.AC-03, AC-07, AC-08, AC-09, AC-13
  - Ficheros: `application/{create_alert,list_my_alerts,alert_events}.py`, `adapters/outbound/drivers/{no_driver_directory,noop_notifier}.py`, `tests/unit/test_create_alert.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_create_alert.py`

- [ ] **T-05** — Endpoints `/alerts`, errores 422/429, `AlertSnapshotProvider` en
  `/ws/passenger`, configuración y composición.
  - AC: alert_create.AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-13, AC-14
  - Ficheros: `adapters/inbound/http/routes/alerts.py`, `adapters/inbound/http/{errors,container,app}.py`, `adapters/inbound/ws/passenger.py`, `config.py`, `main.py`, `.env.example`, `tests/integration/test_alerts_api.py`, `tests/integration/test_alerts_ws.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_alerts_api.py tests/integration/test_alerts_ws.py`

- [ ] **T-06** — Regenerar el contrato del frontend (`npm run gen:api`) y verificación completa.
  - Verificación: `./init.sh verify`
