# Implementación: alert_expiry
Spec: specs/alert_expiry/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04
Rama: `feat/alert_expiry` (apilada sobre `feat/alert_cancel`, `feat/alert_create` y
`feat/realtime_events`). Exploración usada: `progress/explore_passage.md` (E-01).

## Tareas
- [x] T-01 `ExpiryReason`, `observe_passage` y `expiry_reason` (AC-01, AC-02, AC-05, AC-06, AC-07)
- [x] T-02 `GetStopArrivals.for_stop`, `ExpireAlert`, `WatchPassages` y `ExpireDueAlerts` (AC-03, AC-04,
      AC-05, AC-06, AC-08, AC-09)
- [x] T-03 `run_periodic`, `lifespan`, configuración y `.env.example` (AC-10)
- [x] T-04 Integración: caché compartida, fuente que falla, evento por WebSocket, reinicio (AC-03,
      AC-04, AC-08, AC-09, AC-10; además AC-05 con la red real)
- [x] T-05 Sesión real `stop_508_peak` (AC-11)
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
- T-03 (apoyo de tests): `RecordingLogger` (`tests/support/alerts.py`) gana `error()`.
- T-03 (composición): `adapters/inbound/http/container.py` gana `AlertExpiry` y
  `build_alert_expiry` (y la constante `BACKGROUND_LOGGER`); `main.py` compone `alert_expiry` y el
  `lifespan` arranca y para las dos tareas además de `sae.stats` (sin cambios en lo existente).
  `container.py` no está en la lista de ficheros de T-03, pero `background/` no puede importar
  adaptadores (contrato de capas: `adapters | background` son independientes) y así los tests de
  integración componen igual que `main.py`, como ya hacen `build_alert_use_cases` y los demás.
- T-04 (apoyo de tests de alert_create y realtime_events): `tests/support/alerts_app.py`,
  `AlertsApp` gana el campo `expiry` (`build_alert_expiry`, como en `main.py`);
  `tests/support/ws.py` gana `receive_json_soon(ws)`: recibe un mensaje del socket dejando correr
  el bucle de la aplicación como mucho 1000 vueltas (sin reloj real) y falla con
  `AssertionError` si no llega nada, en lugar de colgarse como `receive_json()` (hallazgo
  pendiente del arnés). Lo usan solo los tests nuevos.

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

- T-03: el campo `task` de `unhandled_exception` (design §5) es el nombre de la tarea asyncio que
  ejecuta el bucle (`asyncio.current_task().get_name()`), para no cambiar la firma de
  `run_periodic` del design: `alerts.passage_watcher` y `alerts.expiry_ticker`. Nivel `error`, como
  los otros `unhandled_exception`; nunca el mensaje de la excepción.
- T-03: `background/alert_tasks.py` añade `start_alert_tasks` (crea las dos tareas con su nombre y
  su intervalo) y `stop_tasks` (las cancela y espera; idempotente), que usa el `lifespan`.
- T-03 (configuración, `.env.example` documentado): `AVISABUS_PASSAGE_WATCH_INTERVAL_S` (15, > 0),
  `AVISABUS_ALERT_EXPIRY_INTERVAL_S` (10, > 0), `AVISABUS_PASSAGE_WINDOW_MIN` (2, > 0),
  `AVISABUS_NEXT_STOP_MARGIN_MIN` (2, ≥ 0: un margen 0 tiene sentido). No se acota la ventana a
  1–3 min en la validación: el rango del design §7 se refiere al valor por defecto que puede
  elegir el implementer.
- T-03: logger de las tareas `avisabus.background`; el de `ExpireAlert` y `WatchPassages`,
  `avisabus.alerts` (el de `CreateAlert`/`CancelAlert`).

- T-04 (tests): los instantes salen de la línea temporal de E-01 (`timeline_20s.txt`): la 93
  `…_122` está a 0 min de 720 s a 760 s y desaparece a 780 s; la 98 `…_059` de la 2070 se ve por
  última vez a 320 s a 4 min. Con la caché de producción (TTL 20 s) delante de la reproducción.
  El reinicio (AC-09) se simula con dos composiciones sobre el mismo fichero SQLite (el primer
  motor se cierra; la segunda instancia no tiene nada en memoria). Que el otro dispositivo no
  recibe el evento se comprueba con `receive_json_soon` acotado (falla con "sent nothing").
- T-04: se añade un test de AC-05 con la red real: el aviso de la 98 `…_059` caduca como
  `NEXT_STOP` en el ciclo de 820 s (primer ciclo de 20 s ≥ 803 s, el instante que calcula E-01).
- T-04: los tests de integración pasan a la primera porque prueban, juntas, piezas ya hechas con
  TDD en T-01–T-03 (no hubo código nuevo de producción en T-04).

- T-05 (AC-11): 75 ciclos de 20 s (0–1480 s) con la caché de producción (TTL 20 s) delante de la
  reproducción. En cada ciclo: vigilante, *ticker* y después `GET /arrivals` de la 508 (misma
  caché: es la observación que ha visto el vigilante) y un `POST /alerts` por cada autobús de la
  93 con `can_alert` que aparece por primera vez (un dispositivo por autobús; un viaje que ya tuvo
  aviso no se vuelve a pedir). Los motivos se leen de los eventos `alert.expired` del canal de
  cada dispositivo.
  - Resultado: **PASSED = 2 (`…_122` en c39 y `…_123` en c52), NEXT_STOP = 0, TIMEOUT = 0, vivos
    = 3 (`…_124` c39, `…_125` c52, `…_126` c61)**, idéntico a E-01; el test lo exige, y también
    75 peticiones al SAE (una por ciclo: el vigilante comparte la caché).
  - (a) como está escrita (la observación del ciclo del `PASSED` no tiene su viaje a más de 2 min)
    y, además, la aserción que propone E-01 (autorizada por el orquestador, sin cambiar la spec):
    ningún `PASSED` en un ciclo en el que el número de llegadas de su línea y sentido con
    antelación ≤ (última antelación del viaje + 2 min) no baja respecto al ciclo anterior.
  - (b): al menos un `PASSED` llega como mucho dos ciclos después de la última observación con su
    viaje a ≤ 2 min (los dos lo cumplen: un ciclo después).
  - "Informar": el test imprime `[alert_expiry.AC-11] 93 at 508, 5 alerts: {...}` en la salida de
    pytest (con `capsys.disabled()`) y lo guarda como propiedad `alert_expiry_reasons` (JUnit).

## Bloqueos
Ninguno.

## Verificación
