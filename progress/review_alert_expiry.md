# Revisión: alert_expiry
Ciclo: 1 · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/alert_expiry/` v1.0 (APPROVED) · Rama: `feat/alert_expiry` (HEAD `253ed30`), base de
la revisión `origin/feat/alert_cancel` (PR #42; apilada sobre #41 y #40).

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Los 11 AC tienen tests que verifican el comportamiento, y 22
mutaciones en la lógica de producción hacen fallar al menos un test. Quedan 6 observaciones no
bloqueantes y una nota de spec ya conocida por E-01.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `unit/test_passage_detector.py` (`test_a_present_trip_updates_its_tracking`, `…never_passes_even_arriving_now`, `…without_a_known_delay_keeps_the_previous_one`); `unit/test_watch_passages.py` (`…updates_its_stored_tracking`, `…matched_by_trip_and_service_date`, `…rounded_to_whole_seconds`, `…occurrence_left_the_feed_keeps_its_delay`) | OK | `last_seen_at` = `generated_at`, `last_arrival_at` y `last_delay_s` respecto a la aparición `stop_sequence`. Mutaciones M02, M09 y M10 detectadas. |
| AC-02 | `unit/test_passage_detector.py` (tabla con 0, −15 s, 105 s, 2 min inclusivo, 2 min 1 s, 3 min, 27 min y nunca visto; ventana configurable; antelación medida en la última observación); `unit/test_watch_passages.py` | OK | El `≤` es inclusivo (E-01: la 70 desaparece con 120 s exactos). M01 (`<`) detectada. |
| AC-03 | `unit/test_watch_passages.py` (`…scheduled_observation_neither_tracks_nor_passes`, `…forgets_the_last_realtime_one`, `test_for_stop_falls_back_to_the_timetable_like_execute`); `integration/test_alert_expiry.py::test_a_failing_sae_neither_tracks_nor_passes` | OK | Con la fuente que falla en el instante del paso, nada cambia; al volver el SAE, `PASSED`. M07 y M08 detectadas. |
| AC-04 | `unit/test_watch_passages.py` (`…queried_once_per_cycle`, `…without_alerts_nothing_is_queried`, `test_for_stop_reads_the_arrivals_without_a_token`); `integration/test_alert_expiry.py::test_each_stop_with_alerts_is_read_once_per_cycle_through_the_shared_cache`; `test_alert_expiry_real_session.py` (`sae.calls == 75`) | OK | Una petición por parada y ciclo, a través de la caché de producción compartida con `GET /arrivals`. El *ticker* no consulta. Detectadas M11 (una consulta por aviso) y M18 (vigilante que salta la caché). |
| AC-05 | `unit/test_expiry_policy.py` (límite −1 s/0/+3 min, visto en la última observación, última parada, retraso −300/0/420, margen configurable, siguiente parada en recorrido circular y desordenado, hora > 24 h, cambio de hora); `unit/test_expire_due_alerts.py`; `unit/test_watch_passages.py` (`seen_in_last_observation`); `integration/test_alert_expiry.py::test_a_bus_lost_far_away_expires_by_next_stop` | OK | Con la red real, la 98 `…_059` caduca como `NEXT_STOP` a los 820 s, primer ciclo ≥ 803 s, que es lo que da E-01. Detectadas M03, M05, M20 y M21. |
| AC-06 | `unit/test_expiry_policy.py` (`…expires_at_its_expiry_time`, `…applies_while_the_trip_is_still_seen`); `unit/test_expire_due_alerts.py` (última parada, viaje fuera del feed, 30 min frente a 31 min, nada antes de tiempo, una sola lectura del reloj) | OK | M04 (`>`) detectada. |
| AC-07 | `unit/test_expiry_policy.py::test_next_stop_comes_before_timeout`; `unit/test_passage_detector.py::test_a_present_trip_never_passes_even_arriving_now`; `unit/test_expire_due_alerts.py` (`…next_stop_comes_before_timeout`, `…passed_in_the_same_cycle_is_not_expired_again`) | OK | `PASSED` va primero porque `ExpireAlert` es idempotente (design §3). M06 (`TIMEOUT` antes) detectada. |
| AC-08 | `unit/test_expire_due_alerts.py` (borrado, evento con los 3 motivos, log, `alert_removed` si `DELIVERED`, nada si ya no existía, log sin datos personales); `integration/test_alert_expiry.py::test_an_expired_alert_reaches_the_device_sockets_and_its_row_is_deleted` | OK | El evento llega a las dos pestañas del dispositivo y no al otro. La fila desaparece con sus necesidades, `GET /alerts/mine` queda vacío y el log va sin hash ni necesidades. Detectadas M12, M13 y M14. |
| AC-09 | `unit/test_watch_passages.py` (seguimiento guardado); `integration/test_alert_expiry.py::test_the_tracking_survives_a_restart` | OK | Dos composiciones sobre el mismo fichero SQLite. Tras el reinicio, `seen` = `False` y el paso se detecta con la observación guardada. |
| AC-10 | `unit/test_alert_tasks.py` (`sleep` falso, `tick` que lanza, cancelación, nombres e intervalos, idempotencia de `stop_tasks`, configuración y validación); `integration/test_alert_expiry.py::test_the_application_starts_and_stops_both_tasks` (`lifespan` real de `main.py` en subproceso) | OK | `unhandled_exception` solo lleva `error_type` y `task`: el mensaje, que incluye un UUID, no aparece. Detectadas M15, M16 y M17 (sin `stop_tasks` en el `lifespan`). |
| AC-11 | `integration/test_alert_expiry_real_session.py::test_alerts_on_the_93_expire_as_its_buses_pass` | OK | 75 ciclos de 20 s. Resultado `{'PASSED': 2, 'NEXT_STOP': 0, 'TIMEOUT': 0, 'ALIVE': 3}`: `…_122` y `…_123` creados en c0 y caducados en c39 y c52; `…_124`, `…_125` y `…_126` creados en c39, c52 y c61 y vivos. Coincide con la tabla «Lo que esperaría AC-11» de E-01. Comprueba (a) tal como está escrita, la aserción adicional de E-01 y (b), e informa del recuento. Ver NB-1. |

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre, árbol limpio): **exit 0, «verify: todo en
  verde»**.
  - backend: format, lint, types y architecture OK. 1325 passed, 6 deselected. Cobertura de
    `domain`+`application`: 99,59 %. La salida incluye
    `[alert_expiry.AC-11] 93 at 508, 5 alerts: {'PASSED': 2, 'NEXT_STOP': 0, 'TIMEOUT': 0, 'ALIVE': 3}`.
  - frontend: format, lint, types OK; 44 ficheros, 413 passed y 2 skipped; build y presupuesto
    (5) OK; e2e + a11y: 87 passed.
  - harness: `feature_list.json` y trazabilidad AC→test OK.
- `git fetch`; `git log origin/feat/alert_cancel..HEAD` (9 commits: 5 de la feature, T-01…T-06, y
  4 `chore(progress)`); `git diff --stat origin/feat/alert_cancel...HEAD` (34 ficheros).
- Repetí 30 veces `test_an_expired_alert_reaches_the_device_sockets_and_its_row_is_deleted`, que
  usa `receive_json_soon` y su rama «sent nothing»: 30/30 en verde, 0,36–0,38 s cada una, sin
  cuelgues. El fichero de integración y `test_alert_tasks.py` tardan 0,90 s en total.
- **Mutaciones**, en una copia de `backend/` en el *scratchpad*
  (`…/scratchpad/mut/backend`, ejecutada con `PYTHONPATH` sobre la copia; el repo no se ha
  tocado). Script: `…/scratchpad/scripts/mutate.py`. Se ejecutaron los 7 ficheros de test de la
  feature:
  - 21 de 21 mutaciones de la lógica de producción detectadas (M01–M21, citadas en la matriz).
    M19, `for_stop` sin comprobar la parada, también se detecta.
  - **Ventana a 4 min** (`passage_window_min` por defecto 2 → 4): T-05 **sigue en verde** (2/0/0/3),
    y también con 10 min. Con 16 min falla (`last_lead 900 > 120`), así que la mutación sí llega
    al test. Se detecta en `unit/test_alert_tasks.py:150` (valor por defecto). Ver NB-1.
  - Aserción adicional de E-01 sobre la **línea 70**, variante B (copia del test de T-05
    parametrizada: `MUT_LINE=70`, se vuelve a crear el aviso cuando el viaje reaparece tras un
    `PASSED`):
    - con W = 2 min pasa: `…_070` caduca como `PASSED` en c26 con 120 s y `…_071` en c59; no hay
      falsos positivos;
    - con W = 4 min y el umbral del test a 240 s falla justo en la aserción del recuento
      (`assert 1 < 1`, `…_071` en c70, línea 205). Es el paso prematuro que describe E-01.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes

- **NB-1. T-05 no detecta la ventana mutada a 4 min, porque en la 93 no hay ningún caso que la
  delate** (`tests/integration/test_alert_expiry_real_session.py:42`, `:205`). El único paso
  prematuro de E-01 con 4 min es de la **línea 70** (`…_071` en c70) y solo aparece en la
  variante B, cuando se vuelve a crear el aviso al reaparecer el viaje. Con la 93 y W = 4 min,
  incluso con W = 10 min, el resultado sigue siendo 2/0/0/3. La premisa «con 4 min aparece uno»
  no vale para la 93.
  - La aserción adicional **sí funciona**: detecta el prematuro de la 70 y no da falsos positivos
    con 2 min (ver «Verificación»).
  - El valor de 2 min queda fijado por `unit/test_alert_tasks.py:150` y
    `unit/test_passage_detector.py:31`.
  - AC-11 se refiere solo a la 93 y se cumple. Si se quiere que la sesión real proteja la
    ventana, habría que añadir un escenario con la 70 y la variante B. Eso amplía AC-11 y lo
    decidiría la persona en la spec.
- **NB-2. `container.py` no está en la lista de ficheros de T-03, pero cabe**
  (`backend/src/avisabus/adapters/inbound/http/container.py:55`, `:229`).
  - `background/` no puede importar adaptadores, porque `adapters | background` son capas
    independientes en `.importlinter`.
  - Componer en `container.py` sigue el precedente de `build_alert_use_cases` y permite que los
    tests usen la misma composición que `main.py`, como comprueba el test de AC-10 en subproceso.
  - Es composición pura, sin cambios en lo existente. Encaja en el espíritu de T-03 («arranque y
    parada en el `lifespan`»).
  - Recomendación: que el spec-writer incluya `container.py` en las listas de ficheros de las
    próximas specs con tareas de fondo.
- **NB-3. `WatchPassages` recibe el `Clock` pero no lo lee**
  (`backend/src/avisabus/application/watch_passages.py:61`). El instante de la observación es
  `StopArrivals.generated_at`, que viene del mismo `Clock` inyectado en `GetStopArrivals`. Es
  coherente con E-01 y alert_create, y mantiene la firma del design §3. Si alguna vez se compone
  con relojes distintos, el atributo no usado puede llevar a confusión. Sin impacto hoy.
- **NB-4. `AVISABUS_PASSAGE_WINDOW_MIN` solo exige `> 0`, no el rango de 1 a 3 min**
  (`backend/src/avisabus/config.py:68`). La lectura del implementer es razonable: el rango del
  design §7 limita el valor que puede elegir el implementer, no la configuración del operador.
  Sugerencia: indicar en `.env.example` que solo está validado entre 1 y 3 min.
- **NB-5. `receive_json_soon` usa API privada de Starlette** (`_send_rx`, `_raise_on_close`;
  `backend/tests/support/ws.py:50`, `:56`).
  - Está acotada a 1000 vueltas del bucle, sin reloj real.
  - Falla con `AssertionError` en vez de colgarse: comprobado, 30/30 sin cuelgues.
  - Si el stream se cierra, `EndOfStream` se propaga y tampoco se cuelga.
  - Riesgo: puede romperse al actualizar Starlette. Solo la usan los tests nuevos.
- **NB-6. `alert.trip_lost` se registra en cada ciclo REALTIME sin el viaje, no solo en la
  transición** (`backend/src/avisabus/application/watch_passages.py:116`). Es a nivel `debug`, con
  `alert_id` y `stop_id`, como pide el design §5. Es aceptable, pero con varios avisos lejanos
  genera ruido si se activa `debug` en producción.

### Problema de spec (no bloqueante; ya señalado por E-01; no requiere CP-3)

- **AC-11 (a) es tautológica tal como está escrita**: si el viaje aparece, AC-02 no puede dar
  `PASSED`. El test añade la aserción de recuento propuesta por E-01 y queda cubierto. Sigue
  pendiente que la persona decida si reformula AC-11 (a) y si documenta en LIM-02 que el viaje
  puede pasar al autobús siguiente sin desaparecer (E-01, «Impacto», puntos 2 y 3).

### Otras comprobaciones (sin hallazgos)

- **`GetStopArrivals.for_stop`** (`get_stop_arrivals.py:102`):
  - no pide token;
  - comprueba el feed activo y luego la parada, en el mismo orden que `find_stop` pero sin token,
    y antes de preguntar al SAE;
  - delega en `_arrivals_of`, que es el cuerpo anterior de `execute` sin cambios. `execute`
    (`:96`) solo extrae ese cuerpo, y los tests de stop_arrivals_api no se han modificado;
  - comparte la caché (M18 detectada).
- **Tareas periódicas**:
  - `run_periodic` captura `Exception`, pero no `CancelledError`;
  - la parada en el `lifespan` (`stop_tasks`) cancela y espera, y es idempotente;
  - los tests no usan reloj real (`sleep` falso, `asyncio.sleep(0)`).
- **Decisiones locales**: todas caben en la spec.
  - `seen_in_last_observation`: diccionario privado del vigilante, con limpieza por ciclo y al
    caducar como `PASSED`. Una observación SCHEDULED lo pone a `False` y una parada ilegible no
    lo cambia. Es lo que dice el design.
  - `delay_s` se conserva si la aparición desaparece del feed tras una reimportación.
  - `next_stop_scheduled_at` es una función pura de dominio y se prueba con hora > 24 h y con el
    cambio de hora.
  - Niveles de log: `info`/`warning`/`debug`/`error`.
- **Privacidad (AGENTS.md §6, conventions §3)**:
  - `alert.expired` lleva solo `alert_id`, `stop_id`, `line` y `reason`;
  - `passage.stop_skipped` lleva `stop_id` y `error_type`;
  - `unhandled_exception` va sin mensaje;
  - los tests comprueban que no aparecen `device_id`, el hash ni las necesidades.
- **Arquitectura**:
  - `lint-imports` OK y dominio sin I/O;
  - no hay `datetime.now()` ni `time.time()` en el diff;
  - Pydantic solo en `config.py`.
- **Configuración**: las 4 variables están en `.env.example`, con sus valores por defecto y su
  validación.
- **Alcance**: en `backend/src` solo cambian los ficheros del design §2, más `container.py` y
  `config.py` (NB-2). En tests de otras features:
  - `FakeAlertRepository.update_tracking` deja de lanzar `NotImplementedError` (no lo usaba
    ningún test);
  - `RecordingLogger.error`, `AlertsApp.expiry` y `receive_json_soon` son nuevos.
  Son cambios aditivos y justificados en `progress/impl_alert_expiry.md`. Sin frontend: a11y e
  i18n no aplican.
- **Commits**: Conventional Commits con ámbito `alert_expiry` y cita de la tarea (T-01…T-06).
