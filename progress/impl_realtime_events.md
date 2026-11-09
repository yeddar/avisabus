# Implementación: realtime_events
Spec: specs/realtime_events/ (v1.2, APPROVED) · Ciclo de revisión: 0 (de la v1.2) · Agente: implementer · Fecha: 2026-11-09

## Tareas
- [x] T-01 `Event`, `DeviceId`/`parse_device_id`, `InvalidDeviceIdError`, puertos
      `EventPublisher`/`Subscription`/`DeviceHasher` y `HmacDeviceHasher` (AC-04, AC-05) (commit f0cf40c)
- [x] T-02 `InMemoryEventPublisher` con colas acotadas y desbordamiento (AC-01, AC-02, AC-03)
      (commit 2a8943e)
- [x] T-03 Filtro de excepciones en logs (H-01) y test de privacidad de logs (AC-12)
      (commit 9b125e4)
- [x] T-04 `/ws/passenger`, `ConnectionRegistry`, `EmptySnapshotProvider`,
      `device_hash_from_header`, configuración y composición (AC-03, AC-05…AC-13)
      (commit 72970e0)
- [x] T-06 (v1.2, arnés) `pytest-timeout` con `timeout = 30` y límite explícito en las esperas de
      WebSocket de los tests (commit f2cfe78)
- [x] T-05 Verificación completa: `CI=1 ./init.sh verify --e2e` en verde, repetida tras T-06
      (commit de este fichero)

## Decisiones locales
- T-01: `Event.message()` implementa la serialización del design (`{"type": type, **payload}`).
- T-01: `SubscriptionOverflowError` (la que lanza `Subscription.next_event`, design §3) vive en
  `domain/errors.py` junto a `InvalidDeviceIdError`, como excepción del contrato del puerto.
- T-02: `publish` ignora las suscripciones ya desbordadas; una suscripción desbordada sigue
  contando en `subscriber_count` hasta que su lector la cierra (AC-03). Al cerrar la última
  suscripción de un canal se elimina el canal.
- T-03 (mecanismo del filtro, AC-12): dos capas. (1) Procesador structlog
  `drop_exception_details`, en la cadena común (eventos structlog y `foreign_pre_chain`) y en la
  del `ProcessorFormatter`: quita `exc_info`, `exception`, `exc_text`, `stack_info` y `stack` y
  añade `error_type`. (2) `ExceptionDetailsFilter` en el *handler* raíz (Python 3.12: el filtro
  devuelve una copia del registro, sin tocar el original): un registro de la biblioteca estándar
  con excepción (p. ej. "Exception in ASGI application" de `uvicorn.error`, o `asyncio`) se
  sustituye por el evento `unhandled_exception` con `error_type`, sin mensaje, argumentos, traza
  ni pila. Se aplica a todos los registros *foreign* con excepción, no solo a los de
  `uvicorn.error`, porque su mensaje también puede construirse con la excepción. Los eventos de
  structlog conservan su nombre y campos. Se retira `format_exc_info` del formateador.
- T-03: el test de `project_scaffold.AC-12` `test_exceptions_are_rendered_inside_the_json_line`
  (`tests/unit/test_logging.py`) exigía la traza en la clave `exception`, justo lo que AC-12
  prohíbe. Se sustituye por `test_exceptions_are_reduced_to_their_type_inside_the_json_line`,
  que sigue comprobando la línea JSON (project_scaffold.AC-12) y ahora cita también
  realtime_events.AC-12 (`error_type`, sin mensaje).
- T-03: el test HTTP de AC-12 sirve la petición con el protocolo HTTP real de uvicorn
  (`H11Protocol`) sobre un transporte en memoria (sin sockets), para capturar también la línea
  que escribe uvicorn cuando Starlette relanza la excepción.
- T-04 (estructura del bucle, design §7): por conexión, una tarea lectora (ignora todo mensaje,
  `pong` incluido, y devuelve el código de cierre del cliente) y una escritora (espera a la vez
  el siguiente evento, el `ping` y la señal de parada); la primera que termina cancela la otra y
  la suscripción se cierra en `finally`. Tanto la espera del `hello` como la de la instantánea
  atienden también a la señal de parada (cierre `1001`). El `ping` cuenta desde el anterior
  `ping`, no se reinicia con cada evento.
- T-04: las esperas (`hello`, `ping`, `ws.stats`) usan un `sleep` inyectable (por defecto
  `asyncio.sleep`), como `run_sae_stats`: en los tests es un `FakeSleep`
  (`tests/support/ws.py`) que vuelve al instante N veces o nunca; ningún test espera tiempo
  real. La duración de `ws.closed` se mide con el puerto `Clock` (`FakeClock` en los tests).
- T-04 (`ConnectionRegistry`): cuenta todo socket aceptado, también mientras espera su `hello`
  (AC-10). Para poder entregar `1013` el socket se acepta y se cierra a continuación. Eventos:
  `ws.connected` tras un `hello` válido; `ws.rejected` para `1013`, `4400` y `4408`; `ws.closed`
  (código y `duration_s` desde la aceptación, redondeada a ms) en cualquier otro final, incluido
  el cliente que se va antes del `hello`. Si la tarea se cancela sin código conocido se registra
  `1006`. `ws.stats` lleva `open_connections` y `subscriptions` (suscripciones del publicador).
  Al parar, `close_all` marca cada conexión para cerrar con `1001` y espera como mucho 5 s
  (`CLOSE_TIMEOUT_S`) a que terminen.
- T-04 (composición): `build_realtime(settings, clock, snapshots=None, sleep=asyncio.sleep)` y el
  contenedor `Realtime` (publicador, *hasher*, registro y `PassengerSocket`) viven en
  `adapters/inbound/http/container.py`, junto a los demás constructores. `create_app(...,
  realtime=...)` monta `/ws/passenger` sin prefijo, guarda el *hasher* en
  `app.state.device_hasher` y compone el `lifespan` recibido con `registry.running()` (por
  dentro, para que los sockets se cierren antes que el resto); así `main.py` solo llama a
  `build_realtime` y los tests de integración ejercitan el mismo `lifespan` que producción.
- T-04: el `hello` admite campos adicionales (los casos inválidos de AC-06 son JSON incorrecto,
  otro tipo o identificador inválido); un mensaje binario es inválido (`4400`). Una excepción no
  controlada en el WebSocket registra `unhandled_exception` (`error_type`, `endpoint`) con el
  logger `avisabus.ws` y cierra con `1011`.
- T-04: `InvalidDeviceIdError` → `400` `problem+json` con `type`
  `https://avisabus/problems/invalid-device-id` (sin `Cache-Control`, que el design no pide).
  `device_hash_from_header` se prueba con una ruta registrada solo en el test
  (`tests/integration/test_device_header.py`).
- T-04: test de composición de `main.py` en subproceso (`tests/integration/test_main_realtime.py`):
  configuración leída del entorno, instantánea vacía y cierre `1001` al parar.
- T-06 (espera acotada): `tests/support/ws.py` gana `receive_soon(ws)`, y `receive_json_soon` se
  apoya en ella; sustituyen a `ws.receive()` y `ws.receive_json()` en todos los tests con
  WebSocket. Las dos limitan la espera a 1000 vueltas del bucle de eventos, no a segundos: el
  endpoint hace todo su trabajo en el bucle (ningún `to_thread` en `src/`), así que el límite no
  depende de la carga de la máquina y sigue sin haber reloj real (`docs/conventions.md` §6). Si un
  endpoint llegara a trabajar en un hilo, habría que subir `turns` o pasar a un límite en segundos.
  El límite en segundos es el de `pytest-timeout`, que además cubre lo que el ayudante no alcanza
  (la aceptación dentro de `websocket_connect`, `next_event()` en tests unitarios).
- T-06 (API privada, NB-5 de `alert_expiry`): no hay recepción acotada pública en Starlette, así
  que `_send_rx` y `_raise_on_close` se siguen usando, ahora solo en `tests/support/ws.py`. Si
  Starlette los cambia, los tests fallan con `AttributeError`; no se cuelgan.
- T-06: `test_main_realtime.py` espera dentro de un subproceso, que no puede importar
  `tests.support`; su límite es el `timeout` de `subprocess.run`, que baja de 60 a 25 s para
  quedar por debajo de los 30 s por test. Los otros subprocesos con `timeout=60` no usan WebSocket
  y no se tocan.
- T-06: ningún test `slow` necesita `@pytest.mark.timeout`: los 6 pasan con el límite de 30 s
  (el más largo, 4,6 s en una fase).

## Bloqueos
Ninguno abierto.

Resuelto (histórico):
- **AC-11 con uvicorn (CP-3, resuelto por la spec v1.1, PR #38: AC-11 admite `1001` o `1012`, opción (c)).** El design
  cierra los WebSockets con `1001` desde el `lifespan` (`ConnectionRegistry` en el `lifespan`).
  Así se implementa y se verifica (TestClient y `main.py`). Pero uvicorn 0.54, al recibir
  SIGTERM/SIGINT, primero cierra él mismo cada WebSocket abierto con el código **`1012`**
  (`connection.shutdown()` en `uvicorn/server.py` → `fail_connection(1012)` /
  `send_close(1012)` en `uvicorn/protocols/websockets/*_impl.py`), espera a que terminen y solo
  después ejecuta el `shutdown` del `lifespan`. En producción (`uvicorn avisabus.main:app`) el
  cliente recibirá `1012`, no `1001`; el `ws.closed` del servidor registrará `1012`. El cliente
  (`passenger_alert_ui`) se reconecta ante cualquier cierre, así que no hay efecto funcional.
  Propuestas: (a) aceptar `1012` como código de parada con uvicorn y anotarlo en el design
  (AC-11 se mantiene para el cierre ordenado del `lifespan`); (b) adelantar el cierre
  envolviendo el manejador de SIGTERM de uvicorn al arrancar (más frágil); (c) admitir `1001` o
  `1012` en AC-11.

## Verificación
`CI=1 ./init.sh verify --e2e` (2026-11-09, puerto 4173 libre, tras T-06): **todo en verde**.

| Paso | Resultado |
|---|---|
| backend: format / lint / types / architecture | OK |
| backend: tests | OK: 1325 passed, 6 deselected; cobertura `domain`+`application` 99,59 % |
| frontend: format / lint / types | OK |
| frontend: tests | OK: 55 ficheros, 555 passed, 2 skipped |
| frontend: build + bundle | OK (5 tests de presupuesto) |
| frontend: e2e + a11y | OK: 126 passed |
| harness: `feature_list.json` / trazabilidad AC→test | OK |

Prueba de T-06 (test temporal, no versionado; espera un evento que nunca llega):
- Antes de T-06, con `ws.receive_json()`: colgado hasta que lo mató un vigía externo a los 45 s.
- Con `timeout = 30` y la misma espera: `Failed: Timeout (>30.0s) from pytest-timeout`, en 30,16 s.
- Con `receive_json_soon`: `AssertionError: the socket sent nothing`, de inmediato.

Los 5 mutantes de N-03 que colgaban la suite (ignorar el desbordamiento, sin `close_all`, registro
fuera del `lifespan`, no contar hasta el `hello`, entregar solo a la primera suscripción), aplicados
en copias temporales, ahora fallan sin colgarse: 6, 2, 1, 12 y 4 tests en rojo, y todos terminan
en menos de 35 s. El único que agota los 30 s es un test unitario sobre `next_event()`.

Cambios de T-06 en los tests: 47 esperas sustituidas en `test_ws_passenger.py` (31),
`test_alerts_ws.py` (8), `test_alerts_cancel_api.py` (4) y `test_log_privacy.py` (4);
`test_alert_expiry.py` ya estaba acotado.
Verificación de la v1.0 (2026-11-04, tras T-04): 1098 tests de backend, 413 de frontend y 87 e2e
en verde. Mutaciones de entonces: sin `subscription.close()` fallan 3 tests (AC-03); cerrando con
`1001` en lugar de `4429` al desbordar falla el de AC-09.
