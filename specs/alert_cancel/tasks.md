# Cancelar solicitud de parada — tasks

> Feature: `alert_cancel` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-22, RF-28 (pasajero), RNF-06, RNF-07 · Casos de uso: CU-04 · Depende de: alert_create

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — `AlertNotFoundError` y `CancelAlert`.
  - AC: alert_cancel.AC-01, AC-02, AC-04, AC-05
  - Ficheros: `domain/errors.py`, `application/cancel_alert.py`, `tests/unit/test_cancel_alert.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_cancel_alert.py`

- [ ] **T-02** — Endpoint `DELETE /alerts/{alert_id}`, error 404 y composición.
  - AC: alert_cancel.AC-01, AC-02, AC-03, AC-05
  - Ficheros: `adapters/inbound/http/routes/alerts.py`, `adapters/inbound/http/{errors,container}.py`, `main.py`, `tests/integration/test_alerts_cancel_api.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_alerts_cancel_api.py`

- [ ] **T-03** — Regenerar el contrato del frontend (`npm run gen:api`) y verificación completa.
  - Verificación: `./init.sh verify`
