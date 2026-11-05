# Revisión: alert_create
Ciclo: 1 · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/alert_create/` v1.0 (APPROVED) · Rama `feat/alert_create` (HEAD `baa0fcd`), comparada con
`origin/feat/realtime_events` (`git diff origin/feat/realtime_events...HEAD`, 8 commits, de `f7e19b2` a `baa0fcd`).

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Los 14 AC tienen tests que comprueban el comportamiento de verdad
(lo confirman las mutaciones). La verificación completa con e2e pasa. Las tres lecturas que
señala el implementer caben en la spec y no requieren CP-3. Quedan 4 hallazgos no bloqueantes,
dos de ellos de redacción de la spec o de los docs.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | unit `test_get_stop_arrivals.py`: `test_realtime_arrival_can_be_requested_up_to_the_max_lead` (30 → true, 31 → false), `test_max_lead_is_configurable`, `test_arrivals_without_direction_trip_or_network_cannot_be_requested`, `test_scheduled_arrival_follows_the_same_rule`, `test_arrival_without_trip_within_tolerance` y `test_fallback_to_scheduled_arrivals_when_the_sae_is_unavailable` (adaptados); integration `test_stops_api.py`: `test_realtime_bus_can_be_requested_up_to_30_min_ahead`, `test_realtime_bus_without_trip_cannot_be_requested`, `test_scheduled_bus_can_be_requested_up_to_30_min_ahead`, `test_lines_outside_gtfs_mini_at_stop_2070`, `test_unresolved_direction_is_logged`, `test_real_c2_terminals_resolve_their_direction` (adaptado) | OK | Están todos los casos que pide la verificación: sin sentido, sin viaje, fuera de red, 31 min, 30 min y horario programado. Las mutaciones M01–M04 se detectan. |
| AC-02 | `test_alerts_api.py::test_creates_the_alert_for_a_bus_shown_by_the_arrivals`, `test_alert_ids_are_random`, `test_a_scheduled_bus_can_be_requested_when_the_sae_fails`; `test_create_alert.py::test_alert_payload_is_the_public_schema` | OK | Comprueba el esquema exacto, UUID v4, `destination` de la llegada y `expires_at = created_at + 30 min`. M15 y M17 se detectan. |
| AC-03 | `test_alerts_api.py::test_validation_reuses_the_cached_arrivals` (contador de la fuente = 1), `test_unknown_bus_is_not_requestable`, `test_a_bus_that_already_passed_is_not_requestable`, `test_a_bus_more_than_30_min_ahead_is_not_requestable`; `test_create_alert.py::test_bus_not_requestable_creates_nothing` (6 casos) | OK | Cubre bus inexistente, ya pasado y a más de 30 min, sin peticiones extra al SAE. M18 y M19 se detectan. |
| AC-04 | `test_alerts_api.py::test_invalid_token_or_unknown_stop_is_the_stop_404` (cuerpo igual al 404 de parada, 0 llamadas al SAE); `test_create_alert.py::test_invalid_token_or_unknown_stop_never_asks_the_sae` | OK | Ver la lectura 1 (orden frente a AC-07). |
| AC-05 | `test_alerts_api.py::test_missing_or_invalid_device_id_is_a_400` (5 variantes × `POST` y `GET /mine`) | OK | |
| AC-06 | `test_alerts_api.py::test_invalid_or_repeated_needs_are_a_422`, `test_needs_are_answered_in_canonical_order`; `test_alert_model.py`; `test_create_alert.py::test_needs_are_kept_in_canonical_order` | OK | M16 se detecta. |
| AC-07 | `test_alerts_api.py::test_second_request_at_the_same_stop_and_line_returns_the_first` (200 sin cambios ni eventos), `test_two_simultaneous_requests_leave_a_single_alert` (`GateSource` fuerza la carrera; SQLite en fichero); `test_alert_repository.py::test_concurrent_adds_leave_a_single_alert` (2 hilos, 2 engines); `test_create_alert.py` (duplicado y carrera) | OK | M06–M09, M08b–d y M21 se detectan. |
| AC-08 | `test_rate_limiter.py` (FakeClock: ventana deslizante, `Retry-After`, `release`, olvido de claves); `test_alerts_api.py::test_device_limit_answers_429_with_retry_after`, `test_ip_limit_counts_every_device`, `test_duplicates_do_not_count_and_the_window_slides`, `test_limits_and_their_keys_are_never_logged`; `test_create_alert.py` (límites antes que todo, `max` de los dos `Retry-After`); `test_main_alerts.py` | OK | M12, M13, M22, M23 y M28 se detectan. Ver la lectura 2. |
| AC-09 | `test_create_alert.py::test_without_driver_the_alert_is_registered_and_announced`, `test_with_a_driver_the_alert_is_delivered` (directorio falso con y sin conductor), `test_block_3_has_no_drivers`; `test_alerts_api.py::test_the_device_channel_gets_alert_registered_at_once`; `test_alerts_ws.py::test_alert_registered_reaches_the_open_socket_of_the_device` | OK | El evento ya está en cola cuando llega el 201, sin reloj real (RNF-02). El otro dispositivo no lo recibe. M10 y M24 se detectan. |
| AC-10 | `test_alerts_api.py::test_my_alerts_in_every_stop_by_creation` (varias paradas, orden, otro dispositivo aparte); `test_create_alert.py::test_list_my_alerts_returns_the_device_alerts_by_creation` | OK | M25 se detecta. |
| AC-11 | `test_alerts_ws.py::test_hello_gets_the_active_alerts_of_the_device` (igual que `/mine`), `test_a_device_without_alerts_gets_an_empty_snapshot`; `test_main_alerts.py` (composición real con `AlertSnapshotProvider`) | OK | M20 se detecta. |
| AC-12 | `test_alerts_api.py::test_alerts_survive_a_restart_and_only_the_hash_is_stored` (reinicio con otra app sobre el mismo fichero; `X-Device-Id` ausente de los ficheros de la BD); `test_alert_repository.py` (esquema, reinicio, filas) | OK | |
| AC-13 | `test_create_alert.py::test_logs_never_carry_the_device_the_ip_nor_the_needs` (logger falso); `test_alerts_api.py::test_created_and_rejected_alerts_are_logged_without_personal_data`, `test_limits_and_their_keys_are_never_logged` (structlog capturado) | OK | M11 y M27 se detectan. |
| AC-14 | `test_alerts_api.py`: `no-store` en 201, 200, 400, 404, 422 (bus y cuerpo), 429 y 503; `test_openapi_describes_the_alert_endpoints_with_examples`; `test_openapi_snapshot.py` (desfase, passenger_stop_view.AC-02) | OK | M14 y M29 se detectan. Ver H-1 (el 500 no lleva `no-store`). |

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e` con el puerto 4173 libre (`lsof` sin salida): **`verify: todo en verde`**, exit 0.
  - backend: format, lint, mypy y `lint-imports` OK. Tests: **1209 passed**, 6 deselected. Cobertura de `domain`+`application`: **99,54 %**.
  - frontend: format, lint y types OK. Tests: 44 ficheros, **413 passed**, 2 skipped. Build y presupuesto: 5 passed. e2e + axe: **87 passed**.
  - harness: `feature_list.json` y trazabilidad AC→test OK.
- `uv run pytest -m slow`: **6 passed** (incluye `test_stops_api_real_feed.py` con la regla nueva de `can_alert`). El aviso de cobertura de esta ejecución parcial no aplica.
- **Mutaciones** sobre una copia de `backend/` (HEAD) en el scratchpad, sin caché de bytecode. Se ejecutaron los tests de la feature y los de `stop_arrivals_api` afectados:
  - **Se detectan 31 de 33.** La regla de `can_alert` (sin viaje, `<` en vez de `<=`, sin límite de antelación, `SCHEDULED` siempre `true`). No se liberan los limitadores en un 200. Falta la comprobación de duplicado previa al SAE. Se quitan `ON CONFLICT`, la restricción `UNIQUE` o la detección de la carrera. El evento va a otro canal. El log lleva el *hash* o la IP. `Retry-After` usa `min`. El limitador no cuenta los rechazados o poda de forma estricta. Falta el *middleware* `no-store` o pone otro valor. Al *payload* le falta `destination`. Las necesidades no se ordenan. `expires_at` es erróneo. Se ignoran `service_date`, `can_alert` o el conductor. La instantánea sale vacía. La respuesta es siempre 201. La clave de IP es el dispositivo. El listado no se ordena. `last_seen_at` es siempre `None`. El duplicado se comprueba antes que el límite.
  - **Sobreviven 2, equivalentes:**
    - M05, `can_alert` sin exigir sentido: sin sentido resuelto no hay emparejamiento de viaje, así que `vehicle` ya es `None`.
    - M08 inicial (`INSERT OR ROLLBACK … ON CONFLICT DO NOTHING`): prevalece el *upsert*. Se sustituyó por M08b, que se detecta.
- Comprobación de que T-01 solo toca los tests que lo exigen: con la aserción original (`can_alert is True`), `test_real_c2_terminals_resolve_their_direction` **falla** solo en la parada 346, la que llega a más de 30 min. El cambio es necesario.
- `git status` limpio tras la revisión.

## T-01: cambio autorizado en `stop_arrivals_api`

- `GetStopArrivals._can_alert` (`backend/src/avisabus/application/get_stop_arrivals.py:271`) es literalmente la fórmula del design §3 y de AC-01: en la red ∧ sentido resuelto ∧ `vehicle` ∧ `arrival_at − ahora ≤ alert_max_lead`. Se aplica igual a `REALTIME` y `SCHEDULED`. Coincide con `stop_arrivals_api` v1.6 (AC-11 y AC-13 remiten a `alert_create.AC-01`). Los ejemplos de OpenAPI de `routes/stops.py` siguen siendo coherentes.
- Tests de `stop_arrivals_api` cambiados, cada uno solo donde lo exige la regla nueva:
  - AC-11, sin viaje: pasa de `true` a `false`.
  - AC-13: la cuarta pasada, a +40 min, pasa a `false`.
  - C2 en la 346: lo exige la regla, comprobado arriba.
  - El resto solo añade la cita a `alert_create.AC-01`.
- `position_estimation` (`test_get_vehicle_position.py`) solo recibe el argumento nuevo. Ningún código de producción salvo `routes/stops.py` lee `can_alert`. Sin regresiones: la suite completa y los tests lentos pasan.
- `realtime_events`: `main.py` compone `AlertSnapshotProvider`, verificado por `test_main_alerts.py` y por el ajuste de `test_main_realtime.py`. Por defecto, `build_realtime` sigue usando `EmptySnapshotProvider`, así que los tests de realtime_events no cambian.

## Las tres lecturas señaladas por el implementer

1. **200 con aviso activo antes de validar el token** (`create_alert.py:99` antes de `:103`).
   **Cabe en la spec; no requiere CP-3.**
   - El design §3, paso 2, fija el orden de forma explícita ("Se comprueba antes que el SAE para no gastar consultas").
   - Los requisitos no fijan la precedencia entre AC-04 y AC-07, dos condiciones incondicionales que pueden darse a la vez. El design la resuelve.
   - **Información:** no filtra nada que no dé ya `GET /alerts/mine`. Ese endpoint solo exige el mismo `X-Device-Id`, que es el secreto portador, y devuelve todos los avisos del dispositivo.
   - **Abuso:** el 200 no crea, no modifica, no emite eventos y no consulta el SAE. Cuesta un `SELECT` por índice único, lo mismo que `/alerts/mine`, que tampoco tiene límite. El token sirve para demostrar presencia en la parada al crear, y aquí no se crea nada.
   - Nota menor: el diagrama de `docs/architecture.md:223` dice "validar token, rate limit, unicidad", un orden ilustrativo distinto del del design (ver H-3).
2. **Qué cuenta para el límite de AC-08** (`create_alert.py:94`, `in_memory.py:34`).
   **Cabe en la spec; no requiere CP-3.**
   - El design sitúa el limitador en el paso 1 de `CreateAlert.execute` y en el §1 detrás de `device_hash_from_header`. Por construcción, el 400 de cabecera y el 422 de cuerpo inválido no llegan al limitador. Sin dispositivo válido, además, no hay clave de dispositivo.
   - Cuentan los 201, 404, 422 de bus, 503 y 429, y no los 200, como dice AC-08 ("todas salvo… 200").
   - La redacción "contando todas" de AC-08 es más amplia que el design. Es inocuo: esas peticiones no tocan ni el SAE ni la BD. Ver H-2.
   - Que los 429 cuenten es coherente con "todas" y con el contrato del puerto ("registra el intento"). `Retry-After` es exacto: el siguiente intento a esa hora se admite, como verifican los tests.
3. **`last_seen_at` al crear = `generated_at` si las llegadas son `REALTIME`, `None` si son `SCHEDULED`** (`create_alert.py:134`).
   **Cabe en la spec.**
   - Aplica la definición del campo del design §3 ("última observación REALTIME en que aparecía el viaje"). Es coherente con `alert_expiry` AC-01, AC-02 ("nunca se le vio en tiempo real") y AC-03 (`SCHEDULED` no actualiza).
   - Además permite detectar el paso de un autobús pedido a ≤ 2 min.
   - Nota para `alert_expiry`: `generated_at` es el instante de la consulta (`now`), no el `fetched_at` del SAE, que puede tener hasta `refresh_after_s` de antigüedad. `alert_expiry` debería usar el mismo criterio para "instante de la observación".

## Privacidad, concurrencia y otras decisiones locales

- **Privacidad:**
  - Logs: `alert.created` solo lleva `alert_id`, `stop_id`, `line`, `direction_id` y `status`. `alert.rejected` lleva `reason` y `stop_id`. `alert.duplicate` (debug) lleva `stop_id` y `line`. Ni *hash*, ni IP, ni necesidades, verificado con logs capturados y con mutaciones.
  - `RateLimitedError` y `BusNotRequestableError` no llevan identificadores. `alert_payload` excluye `device_hash` y `delivered_to`.
  - Los eventos se publican solo en `device_channel(hash)`. `/ws/passenger` suscribe cada conexión solo al canal de su dispositivo (realtime_events). Los tests comprueban que el otro dispositivo no recibe el evento ni ve los avisos ajenos en su instantánea.
  - La BD guarda el *hash* y nunca el `X-Device-Id`, comprobado sobre los ficheros SQLite y su WAL.
  - Los contadores del limitador viven solo en memoria y se olvidan al salir de la ventana.
- **Concurrencia y unicidad:**
  - `UNIQUE (device_hash, stop_id, line)` más `INSERT … ON CONFLICT DO NOTHING` y lectura del ganador en la misma transacción. Con `busy_timeout=5000` y WAL es correcto.
  - El caso de uso hace `release` y devuelve `created=False` sin evento si pierde la carrera.
  - La prueba es real: `GateSource` asegura que las dos peticiones superan `find_active` antes de insertar, y hay otra prueba con 2 hilos sobre 2 engines.
  - `release` quita el último instante de la clave, aunque fuera de otra petición concurrente. Es inocuo porque el recuento no cambia.
- **`no-store`:** un *middleware* ASGI acotado a `/api/v1/alerts` y sus subrutas lo pone también en el 400 y en el 422 de validación sin tocar manejadores ajenos. Correcto y probado. Excepción: el 500, ver H-1.
- **`Retry-After`:** en segundos, redondeado hacia arriba (≥ 1). Es el mayor de los dos limitadores y está documentado en el OpenAPI.
- **Esquemas:**
  - `CreateAlertRequest`, `AlertSchema` y `MyAlertsResponse` llevan ejemplos, como permite el design §8.
  - `needs` es obligatorio (`[]` si no hay necesidades), igual que en el cuerpo de AC-02 y del design.
  - El 422 documenta las dos formas: *problem* y validación.
- **Arquitectura y convenciones:**
  - `domain/` sin I/O y `lint-imports` OK. Fuera de `main.py` se usan los puertos.
  - No hay `datetime.now()` ni `time.time()`. Los tests no usan red ni *sleeps* reales.
  - Commits Conventional Commits con ámbito `alert_create`. Las variables nuevas están en `.env.example`.
- **Alcance:**
  - El diff solo toca lo previsto por `tasks.md`. Las dos excepciones están justificadas: `test_get_vehicle_position.py` por el argumento nuevo y `test_main_realtime.py` por la composición del design §2.
  - Los cambios en `frontend/` son solo añadidos al contrato generado (0 líneas borradas). Sin cambios de interfaz, así que i18n y accesibilidad no aplican.
  - `feature_list.json` y `progress/` los tocan los commits del orquestador.

## Hallazgos

Bloqueantes: **ninguno**.

No bloqueantes:

- **H-1 (no bloqueante, AC-14)** — `backend/src/avisabus/adapters/inbound/http/app.py:63`: un 500 inesperado bajo `/api/v1/alerts` sale **sin** `Cache-Control: no-store`.
  - Comprobado con una sonda en el scratchpad: `500 None`.
  - El manejador de `Exception` lo ejecuta `ServerErrorMiddleware`, que queda fuera del *middleware* del usuario.
  - El cuerpo es genérico y sin datos personales, y el design §3 no lista el 500 en su tabla, así que el riesgo es nulo en la práctica.
  - Si se quiere cumplir AC-14 al pie de la letra, el manejador de errores inesperados podría poner la cabecera cuando la ruta sea de `/alerts`. Puede hacerse en `alert_cancel`, que añade `DELETE /alerts/{id}`.
- **H-2 (no bloqueante, problema de spec menor, AC-08)** — `specs/alert_create/requirements.md` AC-08 dice "contando todas salvo las… 200". El design (paso 1 del caso de uso) excluye en la práctica el 400 de cabecera y el 422 de cuerpo.
  - La implementación sigue el design y `.env.example` lo documenta ("las que llegan a procesarse").
  - Se recomienda aclarar la redacción de AC-08 en una próxima versión. No hace falta para cerrar la feature.
- **H-3 (no bloqueante, coherencia docs ↔ spec)** — Dos puntos de `docs/architecture.md` no coinciden con el design:
  - `docs/architecture.md:81` sitúa el *rate limiter* en `adapters/outbound/security/`. El design §2 lo pone en `adapters/outbound/rate_limit/in_memory.py`, y la implementación sigue al design.
  - `docs/architecture.md:223` enumera "validar token, rate limit, unicidad", un orden distinto del design §3.

  Las dos cosas son ilustrativas y no normativas. Propuesta para la persona: alinear `docs/architecture.md` con el design. Corresponde a una persona, no a los agentes.
- **H-4 (no bloqueante, tests)** — `backend/tests/integration/test_stops_api.py:503-504`: la aserción adaptada de las C2 recalcula la regla (`can_alert is (lead <= 30 min)`) en vez de fijar el valor esperado de cada parada. Es correcta y, con la aserción original, falla solo en la 346; pero sería más expresivo fijar `[True, False]` o el valor de cada caso. Los valores frontera de la regla ya los fijan otros tests (30 y 31 min).
