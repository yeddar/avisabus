# Revisión: realtime_events (v1.2, T-06)
Ciclo: 1 (de la v1.2) · Fecha: 2026-11-09 · Agente: reviewer · Spec: `specs/realtime_events/` v1.2 (APPROVED)
Rama: `feat/realtime_events-v1.2` · Base: `origin/develop` · Commit de código: `f2cfe78`

## Veredicto: APPROVED

T-06 está hecha: `pytest-timeout` con `timeout = 30` y ninguna espera de WebSocket sin límite. Los
5 mutantes que colgaban la suite (N-03 de la revisión anterior) ahora fallan sin colgarse, y los
47 reemplazos no debilitan ningún test. `CI=1 ./init.sh verify --e2e` en verde. Sin hallazgos
bloqueantes; cuatro no bloqueantes, abajo.

**Decisión de las 1000 vueltas: cumple T-06 y no requiere CP-3.** T-06 pide un "límite explícito
en las esperas"; "`receive_json` con tiempo máximo" es el ejemplo entre paréntesis.
`receive_soon` tiene un límite explícito y finito, y `pytest-timeout` pone el límite en segundos a
todo el test. El límite en vueltas respeta además "sin reloj real" (AGENTS §6, conventions §6) y
no depende de la carga de la máquina: el máximo medido son 11 vueltas de 1000, bajo carga. La
contrapartida es que, si un endpoint delegase en un hilo, el test fallaría antes de tiempo (rojo
falso, no cuelgue); hoy no hay `to_thread`, `run_in_executor` ni `aiosqlite` en `backend/src`, y
la limitación está documentada en `tests/support/ws.py:50-53`.

## Matriz AC → evidencia

La v1.2 no cambia código de producción (`git diff origin/develop..HEAD -- backend/src`: vacío).
La tabla comprueba que cada AC conserva sus tests y que estos siguen detectando el fallo con las
esperas nuevas. Los ID de mutante son los de "Verificación ejecutada".

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `unit/test_in_memory_publisher.py`, `integration/test_ws_passenger.py` (orden, aislamiento por canal) | OK | M5 (solo la primera suscripción): 4 fallos, sin cuelgue. |
| AC-02 | `unit/test_in_memory_publisher.py` | OK | M1c (el publicador ignora el desbordamiento): 6 fallos. |
| AC-03 | `unit/test_in_memory_publisher.py`, `test_ws_passenger.py` (`subscriber_count` tras cerrar) | OK | Sin cambios salvo la espera; `wait_until_closed` ya estaba acotado. |
| AC-04 | `unit/test_device.py`, `integration/test_device_header.py` | OK | No usan WebSocket; sin cambios. |
| AC-05 | `unit/test_device.py`, `test_device_header.py`, `test_log_privacy.py::test_a_complete_websocket_session_never_logs_the_device` | OK | Las aserciones de logs no cambian; solo las 3 esperas de esa sesión. |
| AC-06 | `test_ws_passenger.py` (`4408`, `4400`, binario, configurable) | OK | W1 (`4408`→`4400`): 2 fallos. W2 (`4400`→`1008`): 16 fallos. |
| AC-07 | `test_ws_passenger.py` (instantánea y orden), `test_main_realtime.py` | OK | M5 y W7 detectados. |
| AC-08 | `test_ws_passenger.py` (`ping`, intervalo configurable, mensajes ignorados) | OK | W5 (`ping`→`pong`): 2 fallos. |
| AC-09 | `test_ws_passenger.py::test_closes_with_4429_when_the_subscription_overflows` | OK | W4 (`1001`): falla. M1a y M1b (ignorar el desbordamiento): fallan al momento. |
| AC-10 | `test_ws_passenger.py::test_closes_new_connections_with_1013_beyond_the_maximum`, `unit/test_ws_connections.py` | OK | W6 (`1000`): 2 fallos. M4 (no contar hasta el `hello`): 12 fallos. |
| AC-11 | `test_ws_passenger.py::test_closes_open_connections_with_1001_when_the_application_stops`, `test_ws_connections.py`, `test_main_realtime.py` | OK | W3 (`1000`): 2 fallos. M2 y M3 fallan; el subproceso corta a los 25,01 s. |
| AC-12 | `test_log_privacy.py`, `unit/test_logging.py` | OK | W10 (`1011`→`1000`): falla. |
| AC-13 | `test_ws_connections.py`, `test_log_privacy.py` | OK | Sin cambios salvo la espera. |

T-06, por su criterio de verificación: un test temporal en una copia, con `ws.receive_json()` sobre
un evento que nunca llega, falla en 30,1 s con `Failed: Timeout (>30.0s) from pytest-timeout`.
Con `receive_json_soon` falla al momento con `AssertionError: the socket sent nothing`.

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre, comprobado con `lsof`): **todo en verde**,
  salida 0. Backend: format, lint, tipos y arquitectura OK; 1325 passed, 6 deselected; cobertura
  99,59 %. Frontend: format, lint y tipos OK; 555 passed, 2 skipped; build y presupuesto OK; e2e +
  a11y 126 passed. Arnés: `feature_list.json` y trazabilidad OK.
- `uv lock --check`: OK. `pytest-timeout` 2.4.0 en el grupo `dev` (`pyproject.toml:35`);
  `timeout = 30` (`pyproject.toml:52`).
- **Esperas sin límite** (`grep` de `receive_json`, `receive_text`, `receive_bytes`, `.receive(` e
  `iter_*` en `backend/tests/`): solo quedan `test_main_realtime.py:34` y `:37`, dentro del
  subproceso y limitadas por el `timeout=25` de `subprocess.run`. `test_alert_expiry.py`,
  `test_alerts_ws.py` y `test_alerts_cancel_api.py` usan `receive_json_soon`. Las llamadas a
  `next_event()` en tests de integración son `ensure_future` con una vuelta y cancelación.
- **47 reemplazos**: comparación línea a línea del diff, 1:1 sin más cambios en las aserciones
  (31 + 8 + 4 + 4; la línea 48 eliminada es el docstring del ayudante). `receive_soon` lee la misma
  cola que `ws.receive()` (`_send_rx`, Starlette 1.10.0) y `receive_json_soon` hace lo mismo que
  `receive_json` (`_raise_on_close` y `json.loads`). No se ha quitado ni añadido ningún test ni
  marcador.
- **`test_main_realtime.py` (60 → 25 s)**: 0,28 s en reposo; 16 de 16 pasan con 14 procesos de
  CPU y 8 ejecuciones en paralelo, sin `.pyc` del código (2,9-3,3 s contando el arranque de
  pytest). El margen frente a 25 s es amplio: no introduce intermitencias.
- **Estrés de las esperas**: 12 ejecuciones de los 57 tests de WebSocket (6 en paralelo, 14
  procesos de CPU): 0 fallos. 828 esperas instrumentadas: mediana 5 vueltas, máximo 11 de 1000.
- **Tests `slow`**: `uv run pytest -m slow`: 6 passed con el feed real presente (ninguno omitido),
  sin `@pytest.mark.timeout`. El más largo, 5,31 s.
- **Mutaciones** (copias en el scratchpad, venv original con `PYTHONPATH` a la copia, vigía externo,
  8 ficheros de tests, 85 tests; línea base 85 passed). Los 5 de N-03:

  | Mutante | Resultado | Duración |
  |---|---|---|
  | M1a, M1b: ignorar `SubscriptionOverflowError` en `_write` | 1 fallo | 4,5 s |
  | M1c: el publicador ignora el desbordamiento | 6 fallos | 3,0 s |
  | M2: sin `close_all` | 3 fallos | 28,2 s (25,01 s del subproceso) |
  | M3: registro fuera del `lifespan` | 2 fallos | 28,0 s (25,01 s del subproceso) |
  | M4: no contar hasta el `hello` | 12 fallos | 3,6 s |
  | M5: entregar solo a la primera suscripción | 4 fallos | 67,1 s (2 tests a 30 s por `pytest-timeout`) |

  Ninguno cuelga la suite. El recuento de M2 y M3 difiere en uno del de
  `progress/impl_realtime_events.md`, seguramente por el conjunto de ficheros ejecutado o la forma
  del mutante; no afecta al resultado.
  Comportamiento (W1-W10: códigos de cierre, `ping`, eventos `alert.registered`, `alert.cancelled`
  y `alert.expired`): los 10 detectados, de 1 a 16 fallos, unos 3 s cada uno.
  M6 (el endpoint nunca acepta; cubre la espera dentro de `websocket_connect`): falla en 30,1 s
  por `pytest-timeout`, comprobado sobre un test. No se ha medido con la suite completa: lo paré
  antes de terminar, porque cada test de WebSocket consumiría sus 30 s.
- **Alcance** (`git diff origin/develop..HEAD`): `backend/pyproject.toml`, `backend/uv.lock`, tests
  de integración con WebSocket y su ayudante `tests/support/ws.py`, más `feature_list.json` y
  `progress/`. Sin cambios en `backend/src`, `frontend/`, `specs/` ni `docs/`. Commits con formato
  Conventional Commits y ámbito de la feature.
- Lista de `docs/verification.md` §4: arquitectura, privacidad, accesibilidad e i18n no cambian
  (sin código de producción ni frontend). Tests sin red, sin reloj real ni sleeps reales en el
  camino normal; los límites en segundos solo actúan si algo falla.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **NB-1** `backend/pyproject.toml:52` (método por defecto de `pytest-timeout`, `signal`): si un
  endpoint bloquea el bucle de eventos de forma síncrona, la suite sigue colgada. Con
  `time.sleep(3600)` antes de `accept`, en una copia, seguía colgada a los 100 s, cuando la paró
  el vigía externo. Causa probable (no aislada): tras la señal, la salida de `websocket_connect`
  llama a `portal.call` sobre un bucle bloqueado, y el temporizador ya ha saltado. No incumple
  T-06, que trata de esperas sin límite, y los mutantes de N-03 no son de este tipo. Si se quiere
  cubrir, valorar `timeout_method = "thread"`, que mata el proceso y vuelca las pilas, a cambio de
  perder el resto de la ejecución.
- **NB-2** `backend/tests/integration/test_gtfs_real_feed.py:34`: `MAX_SECONDS = 120`
  (`gtfs_import.AC-22`, "menos de 2 minutos") queda por encima del límite de 30 s por test, de modo
  que una importación que cumpla el AC entre 30 y 120 s fallaría por tiempo. Hoy tarda 5,3 s. T-06
  permite subirlo con `@pytest.mark.timeout`; conviene hacerlo si el test se usa en una máquina
  más lenta.
- **NB-3** `timeout=60` en `test_alerts_cancel_api.py:386`, `test_occupancy_composition.py:217`,
  `test_main_composition.py:44`, `test_main_alerts.py:67` y `test_main_stop_token.py:39`: ya no se
  alcanzan, porque `pytest-timeout` corta antes a los 30 s (estos tests tardan unos 0,3 s). Sin
  efecto funcional; solo cambia el mensaje de fallo. No usan WebSocket, así que quedan fuera de T-06.
- **NB-4** `specs/realtime_events/tasks.md:38`: "con tiempo máximo" no describe con exactitud el
  límite en vueltas. No es una contradicción y no requiere CP-3; se puede precisar la redacción si
  hay otra versión de la spec.

Estado de los hallazgos de la revisión anterior: N-01 resuelto (`impl_realtime_events.md` al
día), N-02 resuelto (design v1.2), N-03 resuelto (este ciclo), N-04 sigue abierto (no es de T-06).

---

# Revisión: realtime_events
Ciclo: 1 · Fecha: 2026-11-04 · Agente: reviewer · Spec: `specs/realtime_events/` v1.1 (APPROVED)
Rama: `feat/realtime_events` · Base: `origin/develop` (`git diff origin/develop...HEAD`)

## Veredicto: APPROVED

Los 13 AC tienen tests que verifican de verdad el comportamiento; las mutaciones de AC-03, AC-09,
AC-11 y AC-12 se detectan; `CI=1 ./init.sh verify --e2e` en verde. No hay hallazgos bloqueantes.
Hay cuatro hallazgos no bloqueantes (abajo).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `tests/unit/test_in_memory_publisher.py` (`test_delivers_to_every_subscription_of_the_channel_in_order`, `test_does_not_deliver_to_other_channels`, `test_a_waiting_reader_is_woken_by_a_publication`, `test_publishing_to_a_channel_without_subscriptions_does_nothing`); `tests/integration/test_ws_passenger.py` (`test_subscribes_before_the_snapshot_…`, `test_receives_only_the_events_of_its_own_device`) | OK | Orden y aislamiento por canal. Mutante "solo la primera suscripción" detectado (cuelga). |
| AC-02 | `test_in_memory_publisher.py` (`test_default_capacity_is_100_events`, `test_a_full_queue_overflows_without_blocking_nor_affecting_the_others`, `test_an_overflow_wakes_a_waiting_reader_with_the_error`, `test_overflowed_events_are_discarded`) | OK | Capacidad 100 por defecto; `publish` síncrono; no afecta a otras suscripciones. Mutante "sin marca de desbordamiento": 4 fallos. |
| AC-03 | `test_in_memory_publisher.py` (`test_closing_removes_the_subscription`, `test_a_closed_subscription_receives_nothing_more`, `test_an_overflowed_subscription_is_removed_when_closed`); `test_ws_passenger.py` (`test_closing_the_socket_removes_its_subscription`, `test_closes_with_4429_…`, más el recuento en `test_closes_open_connections_with_1001_…` y los de `4400`/`4408`) | OK | Mutantes: sin `subscription.close()` en `_serve` → 3 fallos; `_remove` sin efecto → 6 fallos. |
| AC-04 | `tests/unit/test_device.py` (tabla de 5 válidos y 19 inválidos: mayúsculas, sin guiones, llaves, `urn:`, salto de línea final, versión 1/5, variante, dígito no ASCII, UUID nulo…); `tests/integration/test_device_header.py` (`400` problem+json sin eco del valor) | OK | `fullmatch` evita el `\n` final que admitiría `$`. |
| AC-05 | `test_device.py` (vector fijo, derivación con separación de dominio, estabilidad, dependencia del secreto, `repr`/`str` enmascarados); `test_device_header.py`; `tests/integration/test_log_privacy.py::test_a_complete_websocket_session_never_logs_the_device` | OK | Vector `933f99…b76f` recalculado de forma independiente: coincide. Sesión completa a nivel DEBUG sin `device_id` (minúsculas ni mayúsculas) ni `device_hash`. Mutantes "sin separación de dominio" y "`repr` muestra el valor" detectados. |
| AC-06 | `test_ws_passenger.py` (`test_closes_with_4408_when_no_hello_arrives_in_5_seconds`, `test_hello_timeout_is_configurable`, `test_closes_with_4400_when_the_hello_is_invalid` ×14, `…_binary_frame`) | OK | Espera de 5 s comprobada con `FakeSleep` (sin tiempo real). Mutantes "4400 en vez de 4408" y "no se comprueba `type`" detectados. |
| AC-07 | `test_ws_passenger.py` (`test_valid_hello_gets_an_empty_snapshot_by_default`, `test_subscribes_before_the_snapshot_and_forwards_events_after_it_in_order`); `tests/integration/test_main_realtime.py` | OK | El proveedor publica durante la instantánea y el test exige que el evento llegue después. Mutante "instantánea antes de suscribir" detectado. |
| AC-08 | `test_ws_passenger.py` (`test_sends_ping_every_25_seconds`, `test_ping_interval_is_configurable`, `test_ignores_pong_and_any_other_client_message`) | OK | Mutante "responder a mensajes del cliente" detectado. |
| AC-09 | `test_ws_passenger.py::test_closes_with_4429_when_the_subscription_overflows` | OK | Mutantes: `1001` en vez de `4429` → falla; ignorar el desbordamiento → cuelga (detectado, ver N-03). |
| AC-10 | `test_ws_passenger.py::test_closes_new_connections_with_1013_beyond_the_maximum`; `tests/unit/test_ws_connections.py` (`test_rejects_new_connections_beyond_the_maximum`, `test_default_maximum_is_500`) | OK | Cuenta también los sockets que esperan `hello`; el `hello` del rechazado no llega al proveedor. Mutantes "`>` en vez de `>=`" (3 fallos) y "no contar hasta el `hello`" (cuelga) detectados. |
| AC-11 | `test_ws_passenger.py::test_closes_open_connections_with_1001_when_the_application_stops`; `test_ws_connections.py` (`test_close_all_…`, `test_running_closes_…`); `test_main_realtime.py` (composición real de `main.py`, cierre `1001`) | OK | `1001` por el `lifespan`, también para un socket que aún espera su `hello`. Sin manejo de señales propio (`grep signal\|SIGTERM\|1012` en `backend/src`: nada). `1012` de uvicorn: por revisión, conforme a v1.1. Mutantes: cerrar con `1000` (2 fallos), ignorar la parada durante el `hello` (1 fallo), sin `close_all` / registro fuera del `lifespan` (cuelgan). |
| AC-12 | `test_log_privacy.py` (HTTP servido con `H11Protocol` real de uvicorn sobre transporte en memoria; structlog; biblioteca estándar `uvicorn.error` y `asyncio` con `exc_info`/`stack_info` y causa encadenada; WebSocket con `1011`); `tests/unit/test_logging.py::test_exceptions_are_reduced_to_their_type_inside_the_json_line` | OK | Marcador con el `device_id` dentro: ausente de todas las líneas y de la respuesta 500; sin `Traceback`. Mutantes: quitar las dos capas → 4 fallos; conservar el mensaje del registro *foreign* → 2 fallos; registrar `str(error)` o relanzar en el WS → 1 fallo cada uno. Quitar una sola capa no hace fallar los tests (ver N-04). |
| AC-13 | `test_ws_connections.py` (logger falso: `ws.connected`, `ws.closed` con `code` y `duration_s`, `ws.rejected`, `ws.stats` cada 300 s, sin campos de dispositivo); `test_log_privacy.py::test_a_complete_websocket_session_never_logs_the_device` | OK | Mutantes "campo extra en `ws.connected`" y "sin `duration_s`" detectados. Revisión: ningún evento del registro ni del endpoint lleva `device_id`, `device_hash` ni canal. |

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre, comprobado con `lsof`): **todo en verde**, salida 0.
  - backend: format, lint, mypy (102 ficheros), lint-imports (2 contratos) OK.
  - backend tests: 1098 passed, 6 deselected; cobertura `domain`+`application` 99 %.
    Avisos: `StarletteDeprecationWarning` de `starlette.testclient` (esperado) y los dos de
    `pytest_socket` de los tests de bloqueo de red (preexistentes).
  - frontend: format, lint, types OK; 413 passed, 2 skipped; build + presupuesto OK; e2e + a11y 87 passed.
  - arnés: `feature_list.json` y trazabilidad AC→test OK.
- Mutaciones (copia del backend en el scratchpad, venv original con `PYTHONPATH` a la copia,
  sockets bloqueados, timeout de 60 s por mutante): 33 mutantes sobre los 8 ficheros de tests de
  la feature. 23 fallan, 5 cuelgan (detectados por timeout) y 5 sobreviven, todos equivalentes o
  de capa redundante del filtro de AC-12: quitar solo el `ExceptionDetailsFilter`, quitar solo el
  procesador del `ProcessorFormatter`, no limpiar `exc_info` en el filtro, añadir
  `format_exc_info` tras `drop_exception_details` y no renombrar el evento en el procesador
  (lo hace el filtro). El repositorio no se ha modificado.
- Vector de `HmacDeviceHasher` recalculado aparte con `hmac`/`hashlib`: coincide.
- `git diff origin/develop...HEAD`: solo ficheros de la feature (`backend/src` de T-01…T-04,
  tests, `.env.example`) y de progreso (`feature_list.json`, `progress/`). Sin cambios en
  `specs/`, `docs/` ni `frontend/`.

## Revisión de decisiones locales (progress/impl_realtime_events.md)

- **Filtro en dos capas** (procesador structlog en la cadena común y en el formateador, más
  `logging.Filter` en el *handler* raíz): coincide con design §3 ("en el `ProcessorFormatter` y
  como `logging.Filter` en el handler raíz") y design §7 lo deja como decisión local. Que se
  aplique a todo registro *foreign* con excepción, no solo a `uvicorn.error`, es más estricto que
  el design y cubre `asyncio` ("Task exception was never retrieved" lleva `exc_info` y el `repr`
  de la tarea con el mensaje: se sustituye entero). Los loggers de uvicorn propagan al raíz.
- **Bucle lectura/escritura**: lectora + escritora, la primera que acaba cancela a la otra,
  `subscription.close()` en `finally` (design §3). Las esperas de `hello` e instantánea atienden a
  la parada. Cabe en design §7.
- **`ConnectionRegistry`**: cuenta desde la aceptación; acepta y cierra con `1013`; eventos de
  design §5. Cabe en design §7. `close_all` espera como mucho 5 s reales: solo en producción.
- **Composición en `http/container.py` + `create_app(realtime=…)`**: el design §2 pone la
  composición en `main.py`; aquí `main.py` solo llama a `build_realtime` y `create_app` compone el
  `lifespan`. Es el patrón existente (`build_stop_use_cases`) y permite que los tests usen el mismo
  `lifespan` que producción. Ver N-02.
- **Sleep inyectable y `Clock` para `duration_s`**: cumple "sin reloj real" (verification §4).
- **`hello` con campos extra admitido; binario → `4400`**: compatible con AC-06.
- **Cambio de `test_exceptions_are_rendered_inside_the_json_line`**: correcto.
  `project_scaffold.AC-12` solo exige JSON de una línea con `timestamp`, `level`, `event` y
  `logger` (`specs/project_scaffold/requirements.md:70`), no la traza; exigir la traza contradice
  `realtime_events.AC-12` y `docs/conventions.md` §3 (H-01). El test nuevo sigue comprobando una
  sola línea JSON con su `event`; los demás tests de `test_logging.py` siguen cubriendo los campos
  mínimos. No rompe la intención de `project_scaffold.AC-12`.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-01** `progress/impl_realtime_events.md:2` y `:77-91` ("Bloqueos"): el fichero
  sigue diciendo "Spec … (v1.0, APPROVED) · Ciclo de revisión: 0" y mantiene abierto el bloqueo
  CP-3 de AC-11, ya resuelto por la v1.1 (PR #38). Regla: AGENTS.md §7 (formato del progreso).
  Actualizar la versión de spec y marcar el bloqueo como resuelto en el próximo ciclo o al cerrar.
- **N-02** `backend/src/avisabus/adapters/inbound/http/app.py:48-49,71-83` y `container.py:112-152`:
  la composición del registro en el `lifespan` vive en `create_app`/`container.py`, no en
  `main.py` como dice design §2. Diferencia de ubicación sin cambio de contrato; `container.py` no
  aparece en la lista de ficheros de T-04. Sugerencia: reflejarlo en el design en la próxima
  versión de la spec (no requiere CP-3).
- **N-03** `backend/tests/support/ws.py:10-22` y la suite en general: 5 de 33 mutantes (ignorar el
  desbordamiento, sin `close_all`, registro fuera del `lifespan`, no contar hasta el `hello`,
  entregar solo a la primera suscripción) hacen que la suite **cuelgue** en vez de fallar, porque
  `FakeSleep` y `receive()` esperan para siempre y no hay timeout por test (`pytest-timeout` no
  está instalado). La regresión se detecta, pero en CI se vería como un trabajo colgado. Regla:
  verification §4 "Tests" (diagnóstico). Sugerencia para el arnés: timeout por test.
- **N-04** `backend/src/avisabus/logging.py:86-117`: las dos capas del filtro de AC-12 son
  redundantes entre sí; ningún test fija cada capa por separado (quitar solo el `logging.Filter`
  o solo el procesador del formateador no rompe nada). Además el procesador del
  `ProcessorFormatter` va después de `remove_processors_meta`, así que no ve `_record` ni
  `_from_structlog` y, para registros *foreign*, solo el de `foreign_pre_chain` añade
  `error_type`. No incumple AC-12 (con cualquiera de las capas el mensaje no aparece); es una
  observación sobre la solidez de la defensa en profundidad.
