# Implementación: realtime_events
Spec: specs/realtime_events/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04

## Tareas
- [x] T-01 `Event`, `DeviceId`/`parse_device_id`, `InvalidDeviceIdError`, puertos
      `EventPublisher`/`Subscription`/`DeviceHasher` y `HmacDeviceHasher` (AC-04, AC-05) (commit f0cf40c)
- [x] T-02 `InMemoryEventPublisher` con colas acotadas y desbordamiento (AC-01, AC-02, AC-03)
      (commit 2a8943e)
- [x] T-03 Filtro de excepciones en logs (H-01) y test de privacidad de logs (AC-12)
- [ ] T-04 `/ws/passenger`, `ConnectionRegistry`, `EmptySnapshotProvider`,
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

## Bloqueos

## Verificación
