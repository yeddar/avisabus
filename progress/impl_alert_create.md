# Implementación: alert_create
Spec: specs/alert_create/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04

## Tareas
- [x] T-01 Regla nueva de `can_alert` en `GetStopArrivals` (`alert_max_lead`,
      `AVISABUS_ALERT_MAX_LEAD_MIN`) y adaptación de los tests de `stop_arrivals_api` (AC-01)
- [ ] T-02 Modelos, puertos, errores e `InMemoryRateLimiter` (AC-06, AC-08)
- [ ] T-03 `SqliteAlertRepository` y tabla `alert` (AC-07, AC-12)
- [ ] T-04 `CreateAlert`, `ListMyAlerts`, `alert_payload`, `NoDriverDirectory`,
      `NoopDriverViewNotifier` (AC-03, AC-07, AC-08, AC-09, AC-13)
- [ ] T-05 Endpoints `/alerts`, `AlertSnapshotProvider`, configuración y composición
      (AC-02…AC-14)
- [ ] T-06 Contrato del frontend (`npm run gen:api`) y verificación completa

## Cambios en código de otras features
- T-01 (autorizado por la tarea y por la persona; `stop_arrivals_api` v1.6):
  - `application/get_stop_arrivals.py`: nuevo parámetro obligatorio del constructor
    `alert_max_lead: timedelta`; `can_alert` = en red ∧ sentido resuelto ∧ viaje emparejado ∧
    `arrival_at − ahora ≤ alert_max_lead`, igual en `REALTIME` y `SCHEDULED`
    (`GetStopArrivals._can_alert`).
  - `tests/unit/test_get_stop_arrivals.py`:
    `test_arrival_without_trip_within_tolerance` (stop_arrivals_api.AC-11) esperaba
    `can_alert = true` sin viaje; ahora `false` (AC-11 v1.6).
    `test_fallback_to_scheduled_arrivals_when_the_sae_is_unavailable` (AC-13) exigía
    `can_alert = true` en todas las pasadas programadas; la cuarta (70 a +40 min) es ahora
    `false` (AC-13 v1.6). Ambos citan también `alert_create.AC-01`.
  - `tests/integration/test_stops_api.py`: `test_real_c2_terminals_resolve_their_direction`
    exigía `can_alert = true` en las dos C2; en la 346 la segunda llega a más de 30 min, así que
    ahora se comprueba la regla (`can_alert` ⇔ llega en ≤ 30 min; el viaje ya se exige). El resto
    de tests de integración de `stop_arrivals_api` (508 en hora punta, 2070, respaldo a las
    19:45) no necesitaron cambios: todas sus llegadas con viaje están a ≤ 30 min. Se añade la
    cita a `alert_create.AC-01` en los de fuera de red y sentido sin resolver.
  - `tests/unit/test_get_vehicle_position.py` (position_estimation): solo se añade el argumento
    nuevo `alert_max_lead` al construir `GetStopArrivals` (sin cambio de comportamiento).
  - `.env.example`: el comentario de `AVISABUS_TRIP_MATCH_TOLERANCE_MIN` decía que sin viaje se
    podía seguir avisando; se corrige y se documenta `AVISABUS_ALERT_MAX_LEAD_MIN`.
  - El test lento `tests/integration/test_stops_api_real_feed.py` (C1 en sus cabeceras) sigue en
    verde con la regla nueva (`uv run pytest -m slow`), sin cambios.

## Decisiones locales

## Bloqueos

## Verificación
