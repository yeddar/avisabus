# Caducidad de las solicitudes de parada — tasks

> Feature: `alert_expiry` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-21, RF-28 (pasajero), RNF-06, RNF-08 · Casos de uso: CU-07 · Depende de: alert_create

## Exploración

- **E-01** — Con `stop_508_peak` (paradas 508 y 2070) y `gtfs_mini`, simular la detección de paso
  de AC-01/AC-02 para cada viaje de las líneas en red, cada 20 s: ¿cuántos viajes desaparecen con
  ≤ 1, ≤ 2 y ≤ 3 min en su última observación? ¿Cuántos desaparecen estando lejos (cambio de
  viaje del emparejamiento)? ¿Algún viaje desaparece y vuelve a aparecer? ¿Con qué ventana se
  detectan más pasos sin ningún paso prematuro? → `progress/explore_passage.md`

> Si ninguna ventana entre 1 y 3 min evita los pasos prematuros, o casi ningún paso es
> detectable → CP-3.

## Tareas

- [ ] **T-01** — `ExpiryReason`, `observe_passage` y `expiry_reason`.
  - AC: alert_expiry.AC-01, AC-02, AC-05, AC-06, AC-07
  - Ficheros: `domain/models/alert.py`, `domain/services/{passage_detector,expiry_policy}.py`, `tests/unit/test_passage_detector.py`, `tests/unit/test_expiry_policy.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_passage_detector.py tests/unit/test_expiry_policy.py`

- [ ] **T-02** — `GetStopArrivals.for_stop`, `ExpireAlert`, `WatchPassages` y `ExpireDueAlerts`.
  - AC: alert_expiry.AC-03, AC-04, AC-05, AC-06, AC-08, AC-09
  - Ficheros: `application/{get_stop_arrivals,expire_alert,watch_passages,expire_alerts}.py`, `tests/unit/test_watch_passages.py`, `tests/unit/test_expire_due_alerts.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_watch_passages.py tests/unit/test_expire_due_alerts.py`

- [ ] **T-03** — `run_periodic`, arranque y parada en el `lifespan`, configuración y `.env.example`.
  - AC: alert_expiry.AC-10
  - Ficheros: `background/alert_tasks.py`, `main.py`, `config.py`, `.env.example`, `tests/unit/test_alert_tasks.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_alert_tasks.py`

- [ ] **T-04** — Integración: caché compartida, fuente que falla, evento por WebSocket, reinicio.
  - AC: alert_expiry.AC-03, AC-04, AC-08, AC-09, AC-10
  - Ficheros: `tests/integration/test_alert_expiry.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_alert_expiry.py`

- [ ] **T-05** — Test con la sesión real `stop_508_peak`.
  - AC: alert_expiry.AC-11
  - Ficheros: `tests/integration/test_alert_expiry_real_session.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_alert_expiry_real_session.py`

- [ ] **T-06** — Verificación completa.
  - Verificación: `./init.sh verify`
