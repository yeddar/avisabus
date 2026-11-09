# Demanda del conductor — design

> Feature: `driver_demand` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-23, RF-27, RF-28, RF-29, RNF-02, RNF-06 · Casos de uso: CU-03 (5a), CU-09, CU-10 (3) · Depende de: realtime_events, alert_create, driver_session

## 1. Resumen

```
CreateAlert ─▶ SessionDriverDirectory.find_driver(trip) ─▶ DELIVERED ─▶ DemandViews.touch(session)
driver_session ─▶ DemandSessionListener: service_selected / position_updated / session_closed
CancelAlert, ExpireAlert ─▶ DemandViewNotifier.alert_removed(session) ─▶ DemandViews.touch
DemandViews.touch(session) ─(≤ 1/s)─▶ BuildDriverView ─▶ publish("driver:<session>", driver.view)
/ws/driver: hello{session_token} ─▶ subscribe ─▶ driver.view actual ─▶ vistas nuevas
```

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/driver_view.py` | `DriverView`, `StopDemand`, `NeedCounts` |
| domain | `services/demand.py` | `stop_demand`, `capacity_flags` |
| application | `build_driver_view.py` | `BuildDriverView` |
| application | `deliver_alerts.py` | `DeliverPendingAlerts`, `UndeliverSessionAlerts` |
| application | `demand_views.py` | `DemandViews` (agrupación ≤ 1/s, `touch`, `refresh_all`) |
| adapters/outbound | `drivers/session_directory.py` | `SessionDriverDirectory` |
| adapters/outbound | `drivers/demand_listener.py` | `DemandSessionListener`, `DemandViewNotifier` |
| adapters/outbound | `persistence/sqlite_alerts.py` | Ampliación: `list_by_trip`, `list_by_session`, `set_delivery` (código de `alert_create`, autorizado por T-02) |
| adapters/inbound | `ws/driver.py` | `/ws/driver` |
| adapters/inbound | `http/routes/driver.py` | `GET /sessions/current/view` |
| background | `driver_tasks.py` | Refresco de vistas cada 15 s |
| adapters/inbound | `http/container.py`, `http/app.py` | Sustituye `NoDriverDirectory`, `NoopDriverViewNotifier`, `NoopDriverSessionListener` |

## 3. Interfaces

```python
# domain/models/driver_view.py
@dataclass(frozen=True, slots=True)
class NeedCounts:
    RAMP: int = 0; EXTRA_TIME: int = 0; SEAT: int = 0; VISUAL: int = 0

@dataclass(frozen=True, slots=True)
class StopDemand:
    stop_id: str; name: str; stop_sequence: int; distance_m: float
    waiting: int
    needs: NeedCounts
    alert_ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class DriverView:
    generated_at: datetime
    service: DriverServiceView | None      # line, direction_id, headsign, trip_id, service_date, departure_at, color, text_color
    gps: GpsState
    off_route: bool
    finished: bool
    stops: tuple[StopDemand, ...]          # hasta 5
    total_waiting: int
    free_places: int | None
    free_seats: int | None
    capacity_alert: bool
    seat_alert: bool
```

```python
# domain/services/demand.py
def stop_demand(upcoming: Sequence[UpcomingStop], alerts: Sequence[Alert]) -> tuple[StopDemand, ...]:
    # una solicitud cuenta en la parada si alert.stop_id == stop_id y alert.stop_sequence == stop_sequence
def capacity_flags(stops: Sequence[StopDemand], free_places: int | None, free_seats: int | None
                   ) -> tuple[bool, bool]:   # (capacity_alert, seat_alert)
```

```python
# application/deliver_alerts.py
class DeliverPendingAlerts:     # service_selected
    def __call__(self, session: DriverSession, previous: DriverService | None) -> None: ...
class UndeliverSessionAlerts:   # session_closed / cambio de salida
    def __call__(self, session_id: str) -> None: ...
# Cada cambio: alerts.set_delivery(alert_id, status, delivered_to) + publish(device_channel(hash),
# alert.delivered | alert.registered con {"alert": alert_payload(alert)}) + log.

# application/demand_views.py
class DemandViews:
    def __init__(self, build: BuildDriverView, events: EventPublisher, clock: Clock,
                 min_interval: timedelta = timedelta(seconds=1)) -> None: ...
    def touch(self, session_id: str) -> None: ...       # programa una publicación (agrupa ≤ 1/s)
    async def refresh_all(self) -> None: ...            # tarea de 15 s: solo turnos con suscriptores
```

`DemandSessionListener.position_updated` llama a `touch` solo si cambia algo visible (próximas
paradas, `off_route`, `finished`); `DriverSessionListener` de `driver_session` se le pasa ya
compuesto. Ocupación: `OccupancySensor.read(VehicleRef(trip_id, service_date), now)` y
`classify_occupancy` → `free_places`, `free_seats`.

Mensajes de `/ws/driver`:

```json
{"type": "driver.view", "generated_at": "…Z",
 "service": {"line": "93", "direction_id": 0, "headsign": "Passeig Marítim - Hospital Malva-rosa",
             "trip_id": "…", "service_date": "2026-11-09", "departure_at": "…Z",
             "color": "FE0000", "text_color": "FFFFFF"},
 "gps": "OK", "off_route": false, "finished": false,
 "stops": [{"stop_id": "508", "name": "…", "stop_sequence": 12, "distance_m": 640,
            "waiting": 2, "needs": {"RAMP": 1, "EXTRA_TIME": 0, "SEAT": 1, "VISUAL": 0},
            "alert_ids": ["…", "…"]}],
 "total_waiting": 2, "free_places": 30, "free_seats": 4,
 "capacity_alert": false, "seat_alert": false}
{"type": "session.closed", "reason": "IDLE"}
{"type": "ping"}
```

Códigos de cierre de `/ws/driver`: los de `realtime_events` más `4401` (token no válido).

## 4. Errores y logs

| Evento | Campos |
|---|---|
| `alert.delivered` | `alert_id`, `session_id` |
| `alert.undelivered` | `alert_id`, `session_id`, `reason` (`SESSION_CLOSED`, `SERVICE_CHANGED`) |
| `ws.connected` / `ws.closed` | `endpoint="/ws/driver"`, … (sin `session_id`) |

## 5. Estrategia de test

| AC | Test |
|---|---|
| AC-01–AC-04, AC-08, AC-10, AC-11 | `tests/integration/test_driver_demand.py`: turno + salida de `gtfs_mini`, posición antes de la parada, solicitud creada con `POST /alerts` (replay), vistas por `/ws/driver` y eventos por `/ws/passenger` |
| AC-05–AC-07 | `tests/unit/test_build_driver_view.py`, `tests/unit/test_demand.py` |
| AC-09 | `tests/unit/test_demand_views.py` (`FakeClock`, publicador falso) |
| AC-12 | logger falso |

## 6. Preguntas abiertas

Ninguna.
