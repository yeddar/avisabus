# Implementación: alert_create
Spec: specs/alert_create/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04

## Tareas
- [x] T-01 Regla nueva de `can_alert` en `GetStopArrivals` (`alert_max_lead`,
      `AVISABUS_ALERT_MAX_LEAD_MIN`) y adaptación de los tests de `stop_arrivals_api` (AC-01)
      (commit 57b2285)
- [x] T-02 Modelos, puertos, errores e `InMemoryRateLimiter` (AC-06, AC-08) (commit c75a001)
- [x] T-03 `SqliteAlertRepository` y tabla `alert` (AC-07, AC-12)
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
- T-01: `alert_max_lead` es un parámetro obligatorio (sin valor por defecto) del constructor de
  `GetStopArrivals`; el valor sale de `Settings.alert_max_lead_min` (default 30, > 0).
- T-02 (`InMemoryRateLimiter`, estructura interna permitida por design §8): una `deque` de
  instantes por clave; la ventana de un intento es `[t, t + ventana)`. Limpieza perezosa: se
  podan los intentos de la clave al usarla y, como mucho una vez por ventana, se recorren todas
  las claves para olvidar las que ya no tienen intentos (así no crece con dispositivos que no
  vuelven). `acquire` **registra siempre el intento**, se admita o no (design §3: "registra el
  intento"; AC-08: "contando todas salvo las … 200"); por eso un `429` también cuenta y
  `Retry-After` es el tiempo hasta que la siguiente petición se admitiría de verdad: cuando han
  salido de la ventana los `excess + 1` intentos más antiguos (redondeado hacia arriba, ≥ 1 s).
  `release` quita el último intento de la clave (si sigue en la ventana). Límite < 1 o ventana
  ≤ 0 → `ValueError`.
- T-02: `canonical_needs(needs)` (en `domain/models/alert.py`) ordena según `NEED_ORDER` y lanza
  `ValueError` con repetidos; lo usan el esquema de la API (AC-06) y el caso de uso.
- T-02: `BusNotRequestableError` y `RateLimitedError(retry_after_s)` sin identificadores en el
  mensaje (`"bus not requestable"`, `"rate limited"`).

- T-03: la tabla `alert` tiene su propio `MetaData` (como `occupancy_override`) y `init_db` la
  crea. La unicidad es una restricción `UNIQUE (device_hash, stop_id, line)`
  (`uq_alert_device_stop_line`) más el índice `ix_alert_stop_id`. `add` hace
  `INSERT … ON CONFLICT (device_hash, stop_id, line) DO NOTHING` y, si no inserta, devuelve el
  aviso existente leído en la misma transacción (carreras resueltas por el índice). Todas las
  columnas son `NOT NULL` salvo `delivered_to` y `last_seen_at`. Las listas se ordenan en Python
  por (`created_at`, `alert_id`) comparando `datetime`, no texto ISO.

## Bloqueos

## Verificación
