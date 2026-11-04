# Implementación: realtime_events
Spec: specs/realtime_events/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04

## Tareas
- [x] T-01 `Event`, `DeviceId`/`parse_device_id`, `InvalidDeviceIdError`, puertos
      `EventPublisher`/`Subscription`/`DeviceHasher` y `HmacDeviceHasher` (AC-04, AC-05) (commit f0cf40c)
- [x] T-02 `InMemoryEventPublisher` con colas acotadas y desbordamiento (AC-01, AC-02, AC-03)
      (commit 2a8943e)
- [x] T-03 Filtro de excepciones en logs (H-01) y test de privacidad de logs (AC-12)
      (commit 9b125e4)
- [x] T-04 `/ws/passenger`, `ConnectionRegistry`, `EmptySnapshotProvider`,
      `device_hash_from_header`, configuración y composición (AC-03, AC-05…AC-13)
- [ ] T-05 Verificación completa

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

## Bloqueos
- **AC-11 con uvicorn (requiere decisión de la persona, CP-3; no bloquea el resto).** El design
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
