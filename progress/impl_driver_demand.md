# Implementación: driver_demand
Spec: specs/driver_demand/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-10

## Tareas
- [x] T-01 `DriverView`, `stop_demand`, `capacity_flags` y `BuildDriverView` (AC-05, AC-06, AC-07) (commit 5f972e0)
- [x] T-02 Repositorio de avisos ampliado, `SessionDriverDirectory`, `DeliverPendingAlerts`, `UndeliverSessionAlerts` (AC-01, AC-02, AC-03, AC-12) (commit b075fa0)
- [x] T-03 `DemandViews`, `DemandSessionListener`, `DemandViewNotifier` y refresco de 15 s (AC-04, AC-09) (commit 5c7e466)
- [x] T-04 `/ws/driver`, `GET /sessions/current/view` y composición (AC-01 a AC-04, AC-08, AC-10, AC-11) (commit bbf67d3)
- [x] T-05 Contrato del frontend regenerado (`npm run gen:api`) y verificación completa (commit 8c9e191)

## Decisiones locales

`design.md` no tiene sección de decisiones locales permitidas. Lo siguiente son detalles que la spec no
fija; ninguno cambia un contrato público salvo donde se indica, y la persona o el reviewer pueden pedir
otra cosa sin rehacer el resto.

**Cómo llega `touch` desde `CreateAlert` (AC-01)**
- El design dibuja `CreateAlert ─▶ find_driver ─▶ DELIVERED ─▶ DemandViews.touch`, pero no dice quién
  llama a `touch`, y `CreateAlert` no recibe ningún notificador (código de `alert_create`, que ninguna
  tarea autoriza a cambiar más allá del repositorio). Se resuelve con `DeliveryObservingAlerts`
  (`application/deliver_alerts.py`): decora el `AlertRepository` que recibe `CreateAlert` y, si el aviso
  se guardó de verdad ya entregado, registra `alert.delivered` y hace `touch`. Así `create_alert.py` no
  cambia, y un aviso que pierde la carrera de AC-07 no avisa a nadie. Se descartó hacerlo dentro de
  `find_driver`: se ejecuta antes de guardar y no conoce el `alert_id` que exige AC-12.

**Firmas ampliadas respecto a design §3**
- `UndeliverSessionAlerts.__call__(session_id, reason=SESSION_CLOSED)`: el design pide `reason` en el log
  (§4) pero no en la firma.
- `DemandViews` añade los argumentos de palabra clave `logger` y `sleep`, y los métodos `last_view`,
  `forget` y `aclose`.
- `BuildDriverView` añade `for_session_id` y `open_session_ids`; así `DemandViews` conserva el constructor
  del design y `refresh_all` sabe qué turnos hay. El puerto no tiene búsqueda por id: se recorre
  `list_all`, como en `CloseDriverSession`.
- `DriverDemand` y `build_driver_demand` en `container.py`, antes que avisos y turnos, porque estos
  necesitan su directorio, notificador y *listener*. Por eso tiene su propio `GetDriverSession`.
- `driver_channel` vive en `application/demand_views.py`, para no tocar `domain/ports/events.py`.

**Comportamiento en casos que la spec no cubre**
- **Qué cambia "algo visible" en `position_updated`:** se compara con la última vista publicada: `gps`,
  `off_route`, `finished` y la identidad de las próximas paradas (`stop_id`, `stop_sequence`). Incluye
  `gps` porque AC-09 lo enumera, aunque design §3 no lo cite. No compara `distance_m`, que cambia con
  cada posición; la actualiza el refresco de 15 s.
- **`refresh_all`:** publica si cambia cualquier campo salvo `generated_at`, y lo hace mediante `touch`
  para respetar el límite de una vista por segundo.
- **`touch` siempre publica**, aunque el aviso quede fuera de las 5 paradas mostradas (AC-01, AC-04 piden
  "una vista nueva").
- **Salida que ya no está en la red activa** (el feed cambió durante el turno): `service = null`, sin
  paradas, plazas ni alertas, para que el conductor elija otra.
- **`GET …/view`:** devuelve los campos de la vista sin `type`, que es la envoltura del mensaje WebSocket.
- **`/ws/driver`:** un mensaje que no es `hello` o sin `session_token` de tipo texto cierra con `4400`
  (código de `realtime_events`); un token con surrogates sueltos, que no se puede codificar para calcular
  su *hash*, cierra con `4401`, como cualquier token no válido.
- **Log `alert.delivered` también al crear el aviso** entregado (además de `alert.created`), con los campos
  de AC-12.
- **Refresco cada 15 s:** constante `VIEW_REFRESH_INTERVAL` en `background/driver_tasks.py`; no hay
  variable de entorno porque el design no la lista.

**Implementación**
- `ws/driver.py` importa los auxiliares genéricos de `ws/passenger.py` (`_close`, `_send`, `_cancel`,
  `_Closed`, `_read_until_closed`, `_until_stopping` y los códigos) en lugar de duplicarlos, sin cambiar ese
  fichero. Son nombres privados: si se acepta, conviene moverlos a un `ws/protocol.py` común.
- `NoDriverDirectory`, `NoopDriverViewNotifier` y `NoopDriverSessionListener` siguen como valores por
  defecto de `build_alert_use_cases`, `build_alert_expiry` y `build_driver_use_cases` para las
  composiciones parciales de los tests (mismo patrón que `EmptySnapshotProvider`). `main.py` ya usa las
  implementaciones reales, y los tests de composición lo comprueban.
- `list_by_session` se añadió en T-01 (el puerto y SQLite) porque `BuildDriverView` lo necesita; `list_by_trip`
  y `set_delivery` en T-02.
- El commit de T-04 deja `test_openapi_snapshot` en rojo hasta T-05, que regenera el contrato.

**Código de otras features tocado**
- `alert_create` (autorizado por T-02): `domain/ports/alerts.py` y `persistence/sqlite_alerts.py` con
  `list_by_session`, `list_by_trip` y `set_delivery`. `create_alert.py` no cambia.
- `driver_session`: `http/access_log.py` (filtro nuevo para `/ws/driver`), `http/routes/driver.py` (ruta de
  la vista), `background/driver_tasks.py` (`start_demand_tasks`), `http/container.py`, `http/app.py` y
  `main.py` (composición de T-04).
- Tests que afirmaban los valores provisionales que T-04 sustituye:
  `test_main_alerts.py` (`drivers`), `test_alert_expiry.py` y `test_alerts_cancel_api.py` (`notifier`) y
  `test_main_driver.py` (`listener`; ese test cambia de nombre y su sonda se amplía con la vista,
  `/ws/driver` y la tarea de refresco). `tests/support/alerts.py`: el repositorio falso implementa los
  métodos nuevos.

**Privacidad: logs de acceso de `/ws/driver`**
- uvicorn no escribe los WebSocket en `uvicorn.access`, sino en `uvicorn.error`, con la forma
  `<dirección> - "WebSocket <ruta>" [accepted]`, o un estado. El filtro de `access_log.py` no los cubría y
  exponía la IP. `DriverSocketAddressFilter` (en `uvicorn.error`) enmascara la dirección y descarta la
  *query string*, por si un cliente pone ahí un token.
- Comprobado además con un uvicorn real en local, fuera de la suite, conectando a
  `/ws/driver?session_token=LEAKME` con un `hello` de token inválido: el log dice
  `- - "WebSocket /ws/driver" [accepted]` y `ws.rejected` con `code 4401`, sin IP ni token.

## Bloqueos

Ninguno.

### Avisos para la persona (no bloquean)
- **IP en el log de `/ws/passenger`.** Sigue escribiéndose en `uvicorn.error`; es el mismo problema que ya
  anotó `driver_session` para `/alerts`. El filtro nuevo solo cubre `/ws/driver`, que es lo pedido.
- **AC-11 (≤ 5 s)** se comprueba con `FakeClock` y una espera acotada en vueltas del bucle: demuestra que no
  hay esperas en el camino, no mide latencia real. La medida real corresponde a `nfr_validation`.
- **Avisos por encima del límite de vistas.** La primera vista tras más de 1 s sale de inmediato y las
  siguientes se agrupan; con `touch` constantes el conductor recibe una por segundo, como pide AC-09.

## Verificación

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre), salida 0, "verify: todo en verde":

| Paso | Resultado |
|---|---|
| Backend: `ruff format --check`, `ruff check`, `mypy`, `lint-imports` | OK (2 contratos respetados) |
| Backend: `pytest` | 1844 passed, 12 deselected; cobertura `domain` + `application` 99,65 % |
| Frontend: `format:check`, `lint`, `typecheck` | OK |
| Frontend: `vitest` | 563 passed, 2 skipped (55 ficheros) |
| Frontend: `build` + presupuesto JS | OK (5 passed) |
| Frontend: Playwright + axe | 126 passed |
| Trazabilidad AC → test y esquema de `feature_list.json` | OK |

Comprobación adicional fuera de `verify`: se introdujeron a mano 10 fallos en el código (socket sin
`session.closed`, sin `touch` al crear, sin devolver avisos al cerrar, notificador vacío, sin comparar
`stop_sequence`, sin espera de 1 s, sin devolver al cambiar de salida, filtro de log desactivado, `4401`
sustituido por `4400`). Los tests detectaron nueve; el décimo era una conversión a UTC redundante
(`service_day_start` ya devuelve UTC), que se eliminó.
