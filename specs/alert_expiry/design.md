# Caducidad de las solicitudes de parada — design

> Feature: `alert_expiry` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-21, RF-28 (pasajero), RNF-06, RNF-08 · Casos de uso: CU-07 · Depende de: alert_create

## 1. Resumen

```
PassageWatcher (15 s): avisos agrupados por parada ─▶ GetStopArrivals.for_stop(stop) [caché SAE]
   REALTIME ─▶ PassageDetector.observe(alert, arrivals) ─▶ actualizar seguimiento | PASSED
AlertExpiryTicker (10 s): para cada aviso ─▶ ExpiryPolicy ─▶ NEXT_STOP | TIMEOUT
ExpireAlert: delete ─▶ alert.expired ─▶ DriverViewNotifier ─▶ log
```

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/alert.py` | Ampliación: `ExpiryReason` (`PASSED`, `NEXT_STOP`, `TIMEOUT`) |
| domain | `services/passage_detector.py` | `observe_passage` |
| domain | `services/expiry_policy.py` | `expiry_reason` |
| application | `get_stop_arrivals.py` | Ampliación: `for_stop(stop_id)` sin token (código de `stop_arrivals_api`, autorizado por T-02) |
| application | `expire_alert.py` | `ExpireAlert` (efectos comunes, AC-08) |
| application | `watch_passages.py` | `WatchPassages.tick()` |
| application | `expire_alerts.py` | `ExpireDueAlerts.tick()` |
| background | `alert_tasks.py` | Bucles `run_periodic(tick, interval, sleep)` para ambas tareas |
| raíz | `main.py` | Arranque y parada en el `lifespan` |

## 3. Interfaces

```python
# domain/services/passage_detector.py
@dataclass(frozen=True, slots=True)
class PassageObservation:
    trip_present: bool
    arrival_at: datetime | None        # si está presente
    delay_s: int | None                # arrival_at − programada en la parada (stop_sequence del aviso)

def observe_passage(tracking: AlertTracking, observation: PassageObservation, observed_at: datetime,
                    passage_window: timedelta = timedelta(minutes=2)) -> AlertTracking | ExpiryReason | None:
    # presente → AlertTracking(observed_at, arrival_at, delay_s)                     (AC-01)
    # ausente y last_seen_at no None y last_arrival_at − last_seen_at ≤ window → PASSED (AC-02)
    # ausente en otro caso → None (sin cambios)
```

```python
# domain/services/expiry_policy.py
def expiry_reason(alert: Alert, now: datetime, next_stop_scheduled_at: datetime | None,
                  seen_in_last_observation: bool,
                  next_stop_margin: timedelta = timedelta(minutes=2)) -> ExpiryReason | None:
    # NEXT_STOP si next_stop_scheduled_at no es None, no seen_in_last_observation y
    #   now ≥ next_stop_scheduled_at + last_delay_s + margin                         (AC-05)
    # TIMEOUT si now ≥ expires_at                                                    (AC-06)
    # (PASSED lo decide observe_passage; AC-07 se respeta porque el vigilante corre antes en el
    #  mismo ciclo y ExpireAlert ignora avisos ya borrados)
```

`seen_in_last_observation`: el vigilante guarda en memoria, por `alert_id`, si el viaje estaba en
la última observación `REALTIME` de su parada; tras un reinicio se considera `False` hasta la
primera observación. Si la última observación de la parada fue `SCHEDULED` o no hay ninguna, es
`False`.

`next_stop_scheduled_at`: con `network.trip_stop_times(trip_id)`, la entrada siguiente a
`stop_sequence`; inicio del día de servicio (`service_day_start(service_date)`, mediodía − 12 h) +
`arrival_s`. Si no hay siguiente (última parada) → `None`.

```python
# application/get_stop_arrivals.py
async def for_stop(self, stop_id: str) -> StopArrivals: ...
    # igual que execute pero sin comprobar el token (uso interno de las tareas de fondo);
    # StopNotFoundError si la parada ya no existe en la red activa

# application/expire_alert.py
class ExpireAlert:
    def __init__(self, alerts: AlertRepository, events: EventPublisher,
                 drivers: DriverViewNotifier, logger: Logger) -> None: ...
    def __call__(self, alert: Alert, reason: ExpiryReason) -> bool: ...   # False si ya no existía

# application/watch_passages.py
class WatchPassages:
    def __init__(self, alerts: AlertRepository, stop_arrivals: GetStopArrivals,
                 network: NetworkRepository, expire: ExpireAlert, clock: Clock, logger: Logger,
                 passage_window: timedelta) -> None: ...
    async def tick(self) -> None: ...
    # agrupa list_all() por stop_id; una llamada for_stop por parada (AC-04); si REALTIME, para
    # cada aviso: observation (viaje por trip_id+service_date entre arrivals con vehicle),
    # observe_passage → update_tracking | expire(PASSED); recuerda seen_in_last_observation.
    # StopNotFoundError o NoActiveFeedError de una parada → se registra y se sigue con la siguiente.

# application/expire_alerts.py
class ExpireDueAlerts:
    def __init__(self, alerts: AlertRepository, network: NetworkRepository, expire: ExpireAlert,
                 seen: Callable[[str], bool], clock: Clock, next_stop_margin: timedelta) -> None: ...
    async def tick(self) -> None: ...

# background/alert_tasks.py
async def run_periodic(tick: Callable[[], Awaitable[None]], interval: timedelta, logger: Logger,
                       sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...
    # bucle: sleep(interval); try tick() except Exception → unhandled_exception(error_type) (AC-10)
```

Evento (canal `device:<hash>`): `{"type": "alert.expired", "alert_id": "…", "reason": "PASSED"}`.

## 4. Configuración

| Variable | Default |
|---|---|
| `AVISABUS_PASSAGE_WATCH_INTERVAL_S` | `15` |
| `AVISABUS_ALERT_EXPIRY_INTERVAL_S` | `10` |
| `AVISABUS_PASSAGE_WINDOW_MIN` | `2` (ajustable con E-01) |
| `AVISABUS_NEXT_STOP_MARGIN_MIN` | `2` |

## 5. Errores y logs

| Evento | Campos |
|---|---|
| `alert.expired` | `alert_id`, `stop_id`, `line`, `reason` |
| `alert.trip_lost` (debug) | `alert_id`, `stop_id` (viaje ausente sin paso) |
| `passage.stop_skipped` | `stop_id`, `error_type` |
| `unhandled_exception` | `error_type`, `task` |

## 6. Estrategia de test

| AC | Test |
|---|---|
| AC-01, AC-02, AC-07 | `tests/unit/test_passage_detector.py` (tabla) |
| AC-05, AC-06, AC-07 | `tests/unit/test_expiry_policy.py` (`FakeClock`, día de servicio con hora > 24 h) |
| AC-03, AC-04, AC-08 | `tests/unit/test_watch_passages.py` y `test_expire_due_alerts.py` (fakes) + `tests/integration/test_alert_expiry.py` (fuente con contador; fuente que falla; evento por `/ws/passenger`) |
| AC-09 | `tests/integration/test_alert_expiry.py` (repositorio sobre fichero; dos instancias) |
| AC-10 | `tests/unit/test_alert_tasks.py` (`sleep` falso que corta tras N ciclos; `tick` que lanza) + arranque con `lifespan` |
| AC-11 | `tests/integration/test_alert_expiry_real_session.py`: recorre `stop_508_peak` con `FakeClock` cada 20 s; crea avisos con `POST /alerts` (un dispositivo por autobús de la 93) al principio de la sesión y cuando aparecen autobuses nuevos; informa de los motivos |

## 7. Decisiones locales permitidas

- Estructura de `seen_in_last_observation` (diccionario en memoria compartido entre tareas).
- Valores de `AVISABUS_PASSAGE_WINDOW_MIN` entre 1 y 3 min si E-01 lo justifica (anotarlo en el
  progreso); fuera de ese rango → CP-3.

## 8. Preguntas abiertas

- Delegada a exploración E-01.
