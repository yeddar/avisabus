# Crear solicitud de parada — design

> Feature: `alert_create` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-16, RF-17, RF-19, RF-20, RF-23, RNF-02, RNF-06, RNF-07 · Casos de uso: CU-03 · Depende de: stop_arrivals_api, realtime_events

## 1. Resumen

```
POST /alerts ─▶ device_hash_from_header ─▶ RateLimiter (dispositivo, IP)
             ─▶ CreateAlert: GetStopArrivals.execute(stop, token) ─▶ llegada con ese viaje y can_alert
                             ─▶ ¿aviso activo (device, stop, line)? ─▶ 200 existente
                             ─▶ DriverDirectory.find(viaje) ─▶ AlertRepository.add ─▶ EventPublisher
             ◀─ 201 aviso
```

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/alert.py` | `Need`, `AlertStatus`, `Alert`, `AlertTracking` |
| domain | `ports/alerts.py` | `AlertRepository`, `DriverDirectory`, `DriverViewNotifier`, `RateLimiter` |
| domain | `errors.py` | `BusNotRequestableError`, `RateLimitedError` |
| application | `create_alert.py` | `CreateAlert`, `CreateAlertCommand`, `CreateAlertResult` |
| application | `list_my_alerts.py` | `ListMyAlerts` |
| application | `alert_events.py` | `alert_payload(alert)`, eventos `alert.registered` / `alert.delivered` |
| application | `get_stop_arrivals.py` | Regla nueva de `can_alert` (AC-01; código de `stop_arrivals_api`, autorizado por T-01) |
| adapters/outbound | `persistence/sqlite_alerts.py` | Tabla `alert`, `SqliteAlertRepository` |
| adapters/outbound | `drivers/no_driver_directory.py` | `NoDriverDirectory` (bloque 3) |
| adapters/outbound | `drivers/noop_notifier.py` | `NoopDriverViewNotifier` (bloque 3; lo usan `alert_cancel` y `alert_expiry`) |
| adapters/outbound | `rate_limit/in_memory.py` | `InMemoryRateLimiter` (ventana deslizante) |
| adapters/inbound | `http/routes/alerts.py` | `POST /alerts`, `GET /alerts/mine` |
| adapters/inbound | `ws/passenger.py` | `AlertSnapshotProvider` (sustituye a `EmptySnapshotProvider`) |
| adapters/inbound | `http/container.py`, `http/app.py`, `main.py` | Composición |

## 3. Interfaces

```python
# domain/models/alert.py
class Need(StrEnum):
    RAMP = "RAMP"; EXTRA_TIME = "EXTRA_TIME"; SEAT = "SEAT"; VISUAL = "VISUAL"
NEED_ORDER: tuple[Need, ...] = (Need.RAMP, Need.EXTRA_TIME, Need.SEAT, Need.VISUAL)

class AlertStatus(StrEnum):
    PENDING_DRIVER = "PENDING_DRIVER"; DELIVERED = "DELIVERED"
    # EXPIRED / CANCELLED solo existen en los eventos finales (el aviso se borra, RNF-06)

@dataclass(frozen=True, slots=True)
class AlertTracking:                 # seguimiento del viaje en la parada (lo usa alert_expiry)
    last_seen_at: datetime | None    # última observación REALTIME en que aparecía el viaje
    last_arrival_at: datetime        # su arrival_at entonces (al crear: el de la llegada elegida)
    last_delay_s: int                # arrival_at − hora programada en la parada (al crear: el de la llegada)

@dataclass(frozen=True, slots=True)
class Alert:
    alert_id: str                    # uuid4
    device_hash: str
    stop_id: str
    stop_name: str
    line: str
    direction_id: int
    destination: str                 # ArrivalView.destination
    trip_id: str
    service_date: date
    stop_sequence: int               # aparición de la parada en el viaje (circulares: la más próxima a arrival_at)
    needs: tuple[Need, ...]          # orden canónico, sin repetidos
    status: AlertStatus
    delivered_to: str | None         # session_id del conductor (bloque 4)
    created_at: datetime
    expires_at: datetime             # created_at + alert_max_age
    tracking: AlertTracking
```

```python
# domain/ports/alerts.py
class AlertRepository(Protocol):
    def add(self, alert: Alert) -> Alert: ...
        # si ya existe uno activo con (device_hash, stop_id, line) → devuelve ESE (índice único; AC-07)
    def find_active(self, device_hash: str, stop_id: str, line: str) -> Alert | None: ...
    def list_by_device(self, device_hash: str) -> list[Alert]: ...       # por created_at
    def get(self, alert_id: str) -> Alert | None: ...
    def list_all(self) -> list[Alert]: ...                                # lo usa alert_expiry
    def update_tracking(self, alert_id: str, tracking: AlertTracking) -> None: ...
    def delete(self, alert_id: str) -> bool: ...                          # True si existía

@dataclass(frozen=True, slots=True)
class DriverRef:
    session_id: str

class DriverDirectory(Protocol):
    def find_driver(self, line: str, direction_id: int, trip_id: str, service_date: date) -> DriverRef | None: ...

class DriverViewNotifier(Protocol):
    def alert_removed(self, session_id: str) -> None: ...   # lo implementa driver_demand (bloque 4)

class RateLimiter(Protocol):
    def acquire(self, key: str, now: datetime) -> int | None: ...
        # registra el intento; devuelve None si se admite o los segundos de Retry-After si no
    def release(self, key: str, now: datetime) -> None: ...   # deshace el último intento (AC-07: 200 no cuenta)
```

```python
# application/create_alert.py
@dataclass(frozen=True, slots=True)
class CreateAlertCommand:
    device_hash: str
    client_ip: str
    stop_id: str
    token: str
    line: str
    direction_id: int
    trip_id: str
    service_date: date
    needs: tuple[Need, ...]

@dataclass(frozen=True, slots=True)
class CreateAlertResult:
    alert: Alert
    created: bool                     # False → ya existía (200)

class CreateAlert:
    def __init__(self, stop_arrivals: GetStopArrivals, network: NetworkRepository,
                 alerts: AlertRepository, drivers: DriverDirectory,
                 device_limiter: RateLimiter, ip_limiter: RateLimiter,
                 events: EventPublisher, clock: Clock, max_age: timedelta, logger: Logger) -> None: ...
    async def execute(self, command: CreateAlertCommand) -> CreateAlertResult: ...
```

Orden de `execute`:

1. `device_limiter.acquire("device:"+hash)` y `ip_limiter.acquire("ip:"+ip)` → `RateLimitedError(retry_after_s)` con el mayor de los dos (AC-08).
2. `find_active(hash, stop, line)` → si existe: `release` de ambos limitadores y devolver `created=False` (AC-07). Se comprueba antes que el SAE para no gastar consultas.
3. `stop_arrivals.execute(stop_id, token)` (puede lanzar `StopNotFoundError`, `NoActiveFeedError`).
4. Buscar la llegada con `line`, `direction_id`, `vehicle.trip_id`, `vehicle.service_date` y `can_alert` → si no hay, `BusNotRequestableError` (AC-03).
5. `stop_sequence` y `last_delay_s`: con `network.trip_stop_times(trip_id)`, la aparición de la parada con hora programada más próxima a `arrival_at` (misma regla que `position_estimation.AC-07`); `last_delay_s = round(arrival_at − programada)`.
6. `drivers.find_driver(...)` → `status`, `delivered_to` (AC-09).
7. `alerts.add(alert)`; si devuelve otro aviso (carrera), `release` y `created=False`.
8. Publicar en `device_channel(hash)` `alert.registered` o `alert.delivered` con `{"alert": alert_payload(alert)}`; registrar `alert.created`.

```python
# application/get_stop_arrivals.py — regla de can_alert (AC-01, stop_arrivals_api v1.6)
can_alert = (in_network and direction_id is not None and vehicle is not None
             and arrival_at - now <= alert_max_lead)
# alert_max_lead: nuevo parámetro del constructor (timedelta), desde AVISABUS_ALERT_MAX_LEAD_MIN
```

### API

`POST /api/v1/alerts` (cabecera `X-Device-Id`)

```json
{"stop_id": "508", "token": "…", "line": "93", "direction_id": 0,
 "trip_id": "38_1054_561_2229_487_4_001", "service_date": "2026-11-04",
 "needs": ["RAMP", "VISUAL"]}
```

Respuesta `201` (o `200` si ya existía):

```json
{"alert_id": "6f1c…", "stop_id": "508", "stop_name": "Parc de l'Oest - Enguera",
 "line": "93", "direction_id": 0, "destination": "Passeig Marítim - Hospital Malva-rosa",
 "trip_id": "38_1054_561_2229_487_4_001", "service_date": "2026-11-04",
 "needs": ["RAMP", "VISUAL"], "status": "PENDING_DRIVER",
 "created_at": "2026-11-04T07:40:00Z", "expires_at": "2026-11-04T08:10:00Z"}
```

`GET /api/v1/alerts/mine` → `{"alerts": [ …mismo esquema… ]}`.

La IP es `request.client.host`; detrás de los *proxies* la corrige `uvicorn --proxy-headers`
(`deployment_rpi`). `needs` en Pydantic: `list[Need]` con validador de no repetidos.

Errores (`problem+json`, `Cache-Control: no-store`):

| Caso | status | type |
|---|---|---|
| `X-Device-Id` ausente o inválido | 400 | `…/invalid-device-id` |
| Token o parada | 404 | `…/stop-not-found` |
| Autobús no admite solicitud | 422 | `…/bus-not-requestable` |
| Cuerpo inválido | 422 | validación de FastAPI |
| Límite superado | 429 | `…/rate-limited` + `Retry-After` |
| Sin feed | 503 | `…/network-unavailable` |

Eventos (canal `device:<hash>`), carga útil `{"alert": <esquema de AC-02>}`:
`alert.registered` (`PENDING_DRIVER`) y `alert.delivered` (`DELIVERED`).

## 4. Datos

Tabla `alert` (en `init_db`, `create_all`, ADR-011):

| Columna | Tipo | Notas |
|---|---|---|
| `alert_id` | TEXT PK | |
| `device_hash` | TEXT NOT NULL | |
| `stop_id`, `stop_name`, `line`, `destination` | TEXT NOT NULL | |
| `direction_id`, `stop_sequence` | INTEGER NOT NULL | |
| `trip_id` | TEXT NOT NULL | |
| `service_date` | TEXT (ISO) | |
| `needs` | TEXT | valores separados por comas, orden canónico; `""` sin necesidades |
| `status` | TEXT | |
| `delivered_to` | TEXT NULL | |
| `created_at`, `expires_at` | TEXT (ISO UTC) | |
| `last_seen_at` | TEXT NULL | |
| `last_arrival_at` | TEXT | |
| `last_delay_s` | INTEGER | |

Índices: `UNIQUE (device_hash, stop_id, line)` (todas las filas son activas: las caducadas y
canceladas se borran), `(stop_id)`.

## 5. Configuración

| Variable | Default |
|---|---|
| `AVISABUS_ALERT_MAX_AGE_MIN` | `30` (RF-21, D9) |
| `AVISABUS_ALERT_MAX_LEAD_MIN` | `30` |
| `AVISABUS_ALERT_RATE_DEVICE` | `10` |
| `AVISABUS_ALERT_RATE_IP` | `30` |
| `AVISABUS_ALERT_RATE_WINDOW_MIN` | `10` |

## 6. Errores y logs

| Evento | Campos |
|---|---|
| `alert.created` | `alert_id`, `stop_id`, `line`, `direction_id`, `status` |
| `alert.duplicate` (debug) | `stop_id`, `line` |
| `alert.rejected` | `reason`, `stop_id` (sin IP ni *hash*) |

## 7. Estrategia de test

| AC | Test |
|---|---|
| AC-01 | `tests/unit/test_get_stop_arrivals.py` (casos nuevos de `can_alert`) + `tests/integration/test_stops_api.py` (actualizar los que esperaban `can_alert = true` sin viaje: ahora `false`) |
| AC-02–AC-07, AC-10, AC-12, AC-14 | `tests/integration/test_alerts_api.py` con `gtfs_mini`, replay de `stop_508_peak`, `FakeClock` dentro de la sesión, `httpx.AsyncClient` |
| AC-07 (concurrencia) | dos `POST` con `asyncio.gather` + `SqliteAlertRepository` real sobre fichero temporal |
| AC-08 | `tests/unit/test_rate_limiter.py` (`FakeClock`) + integración con límites bajos |
| AC-09 | `tests/unit/test_create_alert.py` (fakes) + `tests/integration/test_alerts_ws.py` (evento por `/ws/passenger`) |
| AC-11 | `tests/integration/test_alerts_ws.py` |
| AC-13 | `tests/unit/test_create_alert.py` (logger falso) + logs capturados en integración |

Los `trip_id`/`service_date` válidos se obtienen en el test llamando antes a
`GET /arrivals` con el mismo `FakeClock` (no se escriben a mano).

## 8. Decisiones locales permitidas

- Estructura interna del limitador (deque por clave, limpieza perezosa).
- Nombres de los esquemas Pydantic.

## 9. Preguntas abiertas

Ninguna.
