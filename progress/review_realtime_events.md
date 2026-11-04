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
