# Implementación: alert_expiry
Spec: specs/alert_expiry/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04
Rama: `feat/alert_expiry` (apilada sobre `feat/alert_cancel`, `feat/alert_create` y
`feat/realtime_events`). Exploración usada: `progress/explore_passage.md` (E-01).

## Tareas
- [x] T-01 `ExpiryReason`, `observe_passage` y `expiry_reason` (AC-01, AC-02, AC-05, AC-06, AC-07)
- [x] T-02 `GetStopArrivals.for_stop`, `ExpireAlert`, `WatchPassages` y `ExpireDueAlerts` (AC-03, AC-04,
      AC-05, AC-06, AC-08, AC-09)
- [ ] T-03 `run_periodic`, `lifespan`, configuración y `.env.example`
- [ ] T-04 Integración
- [ ] T-05 Sesión real `stop_508_peak`
- [ ] T-06 Verificación completa

## Cambios en código de otras features
- T-02 (autorizado por `tasks.md` y por la persona; código de `stop_arrivals_api`):
  `application/get_stop_arrivals.py` gana `for_stop(stop_id)`. `execute` no cambia de
  comportamiento: tras `find_stop` delega en el nuevo `_arrivals_of(stop_id)`, que es el cuerpo
  que ya tenía. `for_stop` comprueba el feed activo (`NoActiveFeedError`) y la parada
  (`StopNotFoundError`) antes de preguntar al SAE, sin token. Los tests de `stop_arrivals_api`
  siguen en verde sin cambios.
- T-02 (apoyo de tests de alert_create): `tests/support/alerts.py`,
  `FakeAlertRepository.update_tracking` lanzaba `NotImplementedError`; ahora sustituye el
  seguimiento si el aviso existe (como el SQLite). Ningún test existente lo usaba.

## Decisiones locales
- T-01: `AVISABUS_PASSAGE_WINDOW_MIN` se queda en **2 min** (valor por defecto del design; E-01:
  4 de 6 pasos reales detectados y 0 prematuros, el primer prematuro aparece con 4 min). El `≤` de
  AC-02 es inclusivo (E-01: la 70 desaparece con exactamente 120 s).
- T-01: `PassageObservation` lleva valores por defecto `None` en `arrival_at` y `delay_s` (ausente
  = `PassageObservation(False)`). Si el viaje está presente pero su aparición en la parada
  (`stop_sequence` del aviso) ya no está en el feed activo (carrera con una reimportación),
  `delay_s = None` y `observe_passage` conserva el `last_delay_s` anterior. Presente sin
  `arrival_at` → `ValueError` (error de programación).
- T-01: el cálculo de `next_stop_scheduled_at` del design §3 vive como función pura
  `next_stop_scheduled_at(stop_times, stop_sequence, service_date)` en
  `domain/services/expiry_policy.py` (lo prueba `test_expiry_policy.py` con hora > 24 h, como pide
  el design §6). La siguiente parada es la entrada de menor `stop_sequence` mayor que la del aviso.

- T-02 (`seen_in_last_observation`, estructura permitida por design §7): un `dict[str, bool]`
  privado de `WatchPassages`, por `alert_id`, expuesto con `seen_in_last_observation(alert_id)`;
  la composición pasa ese método como `seen` a `ExpireDueAlerts` (así coinciden las firmas del
  design). Se fija a `True`/`False` con cada observación REALTIME de la parada y a `False` con una
  SCHEDULED; una parada que no se puede leer (`passage.stop_skipped`) no lo cambia (no hubo
  observación). Al principio de cada ciclo se olvidan las entradas de avisos que ya no existen y
  se quita la de un aviso al caducarlo como `PASSED`: la memoria no crece.
- T-02: `observed_at` = `StopArrivals.generated_at` (E-01, coherente con alert_create). El `Clock`
  que recibe `WatchPassages` (design §3) no se lee directamente: `generated_at` lo lee el mismo
  `Clock` en `GetStopArrivals` en ese ciclo.
- T-02: el viaje se busca entre las llegadas con `vehicle` por `trip_id` y `service_date` (la
  primera, por `arrival_at`). `delay_s` = `arrival_at` − hora programada en la aparición
  `stop_sequence` del aviso (`trip_stop_times`, inicio del día de servicio + `arrival_s`),
  redondeado a segundos como en `CreateAlert`; si esa aparición ya no está en el feed, `None`
  (se conserva el retraso anterior, T-01). `trip_stop_times` se consulta una vez por viaje y
  ciclo.
- T-02 (logs): `alert.trip_lost` (debug) en **cada** observación REALTIME en la que el viaje no
  aparece y no hay paso (no solo en la transición), con `alert_id` y `stop_id`.
  `passage.stop_skipped` con nivel `warning`. `alert.expired` con nivel `info` (como
  `alert.cancelled`). Solo `StopNotFoundError` y `NoActiveFeedError` se registran y se salta la
  parada (design §3); cualquier otra excepción sale de `tick()` y la registra la tarea periódica
  (AC-10).
- T-02: el evento lleva `reason` como texto (`reason.value`). `alert_removed` se llama si el
  aviso está `DELIVERED` y tiene `delivered_to`.
- T-02: `ExpireDueAlerts` lee el `Clock` una vez por ciclo. Si el viaje ya no está en el feed
  activo (`trip_stop_times` vacío), no hay parada siguiente: solo aplica `TIMEOUT`.

## Bloqueos
Ninguno.

## Verificación
