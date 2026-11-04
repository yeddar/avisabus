# Implementación: alert_create
Spec: specs/alert_create/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04

## Tareas
- [x] T-01 Regla nueva de `can_alert` en `GetStopArrivals` (`alert_max_lead`,
      `AVISABUS_ALERT_MAX_LEAD_MIN`) y adaptación de los tests de `stop_arrivals_api` (AC-01)
      (commit 57b2285)
- [x] T-02 Modelos, puertos, errores e `InMemoryRateLimiter` (AC-06, AC-08) (commit c75a001)
- [x] T-03 `SqliteAlertRepository` y tabla `alert` (AC-07, AC-12) (commit a79d05f)
- [x] T-04 `CreateAlert`, `ListMyAlerts`, `alert_payload`, `NoDriverDirectory`,
      `NoopDriverViewNotifier` (AC-03, AC-07, AC-08, AC-09, AC-13) (commit 3066888)
- [x] T-05 Endpoints `/alerts`, `AlertSnapshotProvider`, configuración y composición
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
- T-05 (composición, design §2: `AlertSnapshotProvider` sustituye a `EmptySnapshotProvider`):
  - `adapters/inbound/ws/passenger.py` (realtime_events): se añade `AlertSnapshotProvider`;
    `EmptySnapshotProvider` se conserva como valor por defecto de `build_realtime` (lo usan los
    tests de realtime_events), pero `main.py` pasa ya el proveedor de avisos.
  - `tests/integration/test_main_realtime.py` (realtime_events.AC-07/AC-11): esperaba
    `"snapshots": "EmptySnapshotProvider"` en la composición de `main.py`; ahora
    `"AlertSnapshotProvider"` (la instantánea sigue vacía porque la BD no tiene avisos).
  - `adapters/inbound/http/errors.py`, `container.py`, `app.py` y `main.py`: añadidos (manejadores
    nuevos, `AlertUseCases`, parámetro `alerts` de `create_app`); nada existente cambia de
    comportamiento.

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
- T-04 (orden de `execute`, el del design §3): límites → aviso activo (`find_active`) → llegadas
  → autobús → aparición y retraso → conductor → `add` → evento. Consecuencia del orden del
  design: si el dispositivo ya tiene aviso activo en esa parada y línea, se responde `200` con él
  **antes** de validar el token (no se llama a `GetStopArrivals`); AC-04 (`404`) se aplica a las
  peticiones que llegan a consultar las llegadas. Lo señalo para la revisión; no lo considero
  bloqueo porque el design fija el orden explícitamente ("se comprueba antes que el SAE").
- T-04 (`AlertTracking` al crear): `last_arrival_at` y `last_delay_s` son los de la llegada
  elegida (design). `last_seen_at` no tiene valor "al crear" en el design; se aplica su
  definición ("última observación REALTIME en que aparecía el viaje"): si las llegadas son
  `REALTIME`, el viaje aparece en esa observación y `last_seen_at = StopArrivals.generated_at`;
  si son `SCHEDULED`, `None` (nunca visto en tiempo real; alert_expiry AC-02/AC-03).
- T-04: `stop_sequence`/`last_delay_s` con `network.trip_stop_times(trip_id)`: entre las
  apariciones de la parada, la de hora programada más próxima a `arrival_at` (a igualdad, la de
  menor `stop_sequence`, como `estimate_position`); `last_delay_s = round(arrival_at −
  programada)` en segundos. Si el viaje ya no pasa por la parada (el feed activo cambió entre la
  consulta de llegadas y este paso), se trata como `BusNotRequestableError` (no hay autobús
  pedible en la red activa); si la parada ya no existe, `StopNotFoundError` (como
  `GetVehiclePosition`). Son carreras con una reimportación, no casos de la spec.
- T-04: `alert_id = str(uuid.uuid4())` en el caso de uso. `needs` se normaliza con
  `canonical_needs` también en el caso de uso (la API ya lo valida).
- T-04 (logs): `alert.created` y `alert.rejected` con nivel `info`; `alert.duplicate` con
  `debug` (design §6). El *logger* es un `Protocol` con `debug`/`info` (structlog en producción).
- T-04: `alert_event(type, alert)` (en `application/alert_events.py`) construye el `Event` con
  carga `{"alert": alert_payload(alert)}`; constantes `ALERT_REGISTERED` y `ALERT_DELIVERED`.
  `alert_payload` serializa fechas como ISO UTC con `Z` (igual que Pydantic en la API REST) y
  `needs` como lista de textos; nunca incluye `device_hash` ni `delivered_to`.
- T-04: `ListMyAlerts.execute(device_hash)` es `async` (hace E/S) y devuelve
  `list_by_device` sin filtrar por `expires_at` (todas las filas son activas, design §4).

- T-05 (`Cache-Control: no-store` en todas las respuestas de `/alerts`, AC-14): con un
  *middleware* ASGI (`adapters/inbound/http/no_store.py`, `NoStoreMiddleware`) para
  `/api/v1/alerts` y `/api/v1/alerts/…`, que `create_app` añade si recibe `alerts`. Así lo llevan
  también las respuestas que construyen manejadores ajenos a la feature (`400` de
  `X-Device-Id`, `422` de validación de FastAPI) sin tocarlos. Los manejadores nuevos (`422`
  bus-not-requestable y `429`) ya lo ponen ellos mismos, como los de `stop_arrivals_api`.
- T-05 (esquemas Pydantic, nombres permitidos por design §8): `CreateAlertRequest`,
  `AlertSchema`, `MyAlertsResponse`; `needs` es `list[Need]` **obligatorio** (el cuerpo del
  design lo incluye; vacío `[]` si no hay necesidades) con validador de repetidos
  (`canonical_needs`); `status` es el enum `AlertStatus`. El `422` del `POST` documenta las dos
  formas: `problem+json` (bus-not-requestable) y el error de validación de FastAPI
  (`HTTPValidationError`). El `429` documenta la cabecera `Retry-After`.
- T-05: la IP es `request.client.host` (design); si el servidor no la conociera se usa la clave
  `"unknown"` (no ocurre con uvicorn).
- T-05 (qué peticiones cuentan para el límite, AC-08): las que llegan al caso de uso, como fija
  el design (el limitador es el paso 1 de `CreateAlert.execute`): `201`, `404`, `422`
  bus-not-requestable, `503` y los propios `429`; no cuentan los `200` (AC-07) ni las que
  FastAPI rechaza antes (`400` de `X-Device-Id`, `422` de cuerpo inválido), que no tocan el SAE
  ni la BD. Lo señalo para la revisión por si "contando todas" debiera incluirlas.
- T-05 (composición): `build_alert_snapshots(engine)` crea el `AlertSnapshotProvider` antes de
  `build_realtime` (que lo necesita) y `build_alert_use_cases(settings, engine, clock, stops,
  publisher)` crea `CreateAlert` con el `GetStopArrivals` de las paradas (misma caché del SAE),
  el publicador de tiempo real, `NoDriverDirectory`, dos `InMemoryRateLimiter` y el logger
  `avisabus.alerts`; `ListMyAlerts` sobre `SqliteAlertRepository`. `NoopDriverViewNotifier` aún
  no se compone (lo usarán `alert_cancel`/`alert_expiry`).
- T-05: configuración nueva (`.env.example` documentado): `AVISABUS_ALERT_MAX_AGE_MIN` (30),
  `AVISABUS_ALERT_RATE_DEVICE` (10), `AVISABUS_ALERT_RATE_IP` (30),
  `AVISABUS_ALERT_RATE_WINDOW_MIN` (10); todos > 0.
- T-05 (tests): `tests/support/alerts_app.py` compone la app igual que `main.py`. La
  concurrencia de AC-07 usa `GateSource`, que retiene las peticiones hasta que las dos han pasado
  la comprobación de duplicado, para forzar la carrera de verdad sobre `SqliteAlertRepository`
  (fichero temporal). Que el evento llega "en ≤ 5 s" (AC-09/RNF-02) se comprueba sin reloj real:
  el evento ya está en la cola de la suscripción cuando llega la respuesta `201` (una vuelta del
  bucle con `asyncio.sleep(0)`), y por `/ws/passenger` se recibe tras el `POST`. Test nuevo de
  composición de `main.py` en subproceso (`tests/integration/test_main_alerts.py`).
- T-05: hasta T-06 falla `test_frontend_openapi_matches_the_backend` (passenger_stop_view.AC-02):
  el contrato del frontend se regenera en T-06, como indica `tasks.md`.

## Bloqueos

## Verificación
