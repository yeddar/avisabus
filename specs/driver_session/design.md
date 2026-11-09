# Turno del conductor — design

> Feature: `driver_session` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-24, RF-25, RF-26, RF-30, RNF-06, RNF-07, RNF-13 · Casos de uso: CU-08, CU-09 (posición), CU-10, CU-13 (revocación) · Depende de: gtfs_import, driver_codes_cli

## 1. Resumen

```
POST /driver/sessions {code} ─▶ LoginLimiter(IP) ─▶ hash ─▶ DriverCodeRepository ─▶ sesión + token
GET  /driver/lines · /driver/departures ─▶ NetworkRepository
PUT  /driver/sessions/current/service ─▶ validar salida ─▶ DriverSessionListener.service_selected
PUT  /driver/sessions/current/position ─▶ UpcomingStopsResolver (proyección) ─▶ guardar
DriverSessionReaper (60 s) ─▶ cerrar IDLE / REVOKED ─▶ DriverSessionListener.session_closed
```

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/driver.py` | Ampliación: `DriverSession`, `DriverService`, `DriverPosition`, `SessionCloseReason`, `GpsState`, `UpcomingStop`, `SessionProgress` |
| domain | `ports/driver.py` | Ampliación: `DriverSessionRepository`, `SessionTokenHasher`, `DriverSessionListener` |
| domain | `services/upcoming_stops.py` | `project_progress`, `upcoming_stops` |
| domain | `errors.py` | `InvalidDriverCodeError`, `InvalidSessionError`, `InvalidDepartureError`, `DepartureTakenError` |
| application | `driver_sessions.py` | `StartDriverSession`, `SelectDriverService`, `UpdateDriverPosition`, `GetDriverSession`, `EndDriverSession`, `ListDriverLines`, `ListDepartures` |
| application | `close_driver_session.py` | `CloseDriverSession` (efectos comunes) |
| application | `reap_driver_sessions.py` | `ReapDriverSessions.tick()` |
| adapters/outbound | `persistence/sqlite_driver_sessions.py` | Tabla `driver_session` |
| adapters/outbound | `persistence/sqlite_network.py` | Ampliación: `list_lines()`, `departures(...)` (código de `gtfs_import`, autorizado por T-02) |
| adapters/outbound | `drivers/noop_session_listener.py` | `NoopDriverSessionListener` |
| adapters/inbound | `http/routes/driver.py`, `http/driver_auth.py` | Endpoints y dependencia `current_session` |
| background | `driver_tasks.py` | Bucle del *reaper* (reutiliza `run_periodic`) |

## 3. Interfaces

```python
# domain/models/driver.py
class SessionCloseReason(StrEnum): ENDED = "ENDED"; IDLE = "IDLE"; REVOKED = "REVOKED"; REPLACED = "REPLACED"
class GpsState(StrEnum): WAITING = "WAITING"; OK = "OK"; STALE = "STALE"

@dataclass(frozen=True, slots=True)
class DriverService:
    line: str
    direction_id: int
    trip_id: str
    service_date: date

@dataclass(frozen=True, slots=True)
class DriverPosition:
    lat: float; lon: float; accuracy_m: float; recorded_at: datetime

@dataclass(frozen=True, slots=True)
class DriverSession:
    session_id: str              # uuid4
    token_hash: str              # SHA-256 hex del token
    code_id: str
    started_at: datetime
    service: DriverService | None
    position: DriverPosition | None
    progress_m: float | None     # sobre el trazado del viaje
    off_route: bool
    last_position_at: datetime | None   # instante de servidor de la última posición aceptada

@dataclass(frozen=True, slots=True)
class UpcomingStop:
    stop_id: str; name: str; stop_sequence: int; distance_m: float

@dataclass(frozen=True, slots=True)
class SessionProgress:
    gps: GpsState
    off_route: bool
    finished: bool
    upcoming: tuple[UpcomingStop, ...]    # hasta 5
```

```python
# domain/services/upcoming_stops.py
PASSED_MARGIN_M = 20.0
OFF_ROUTE_M = 150.0
def project_progress(shape: Sequence[ShapePoint], distances: Sequence[float], lat: float, lon: float,
                     previous_m: float | None, back_m: float = 100.0, ahead_m: float = 3000.0
                     ) -> tuple[float, float]:
    # (progreso candidato, distancia al trazado): segmento más cercano dentro de
    # [previous − back, previous + ahead] (todo el trazado si previous es None)
def upcoming_stops(stops: Sequence[tuple[UpcomingStop, float]],   # (parada, distancia sobre el trazado)
                   progress_m: float, limit: int = 5) -> tuple[tuple[UpcomingStop, ...], bool]:
    # paradas con dist > progress + PASSED_MARGIN_M; finished si progress ≥ última − PASSED_MARGIN_M
```

Regla en `UpdateDriverPosition`: si la distancia al trazado > `OFF_ROUTE_M` → `off_route=True`,
progreso sin cambios; si no, `progress = max(previous, candidato)`, `off_route=False`. Las
distancias de las paradas del viaje sobre el trazado se calculan con `shape_dist_traveled` o, si
falta, con `project_onto_shape` (como en `position_estimation`), y se cachean por `shape_id`.

```python
# domain/ports/driver.py
class SessionTokenHasher(Protocol):
    def hash(self, token: str) -> str: ...            # SHA-256 hex
class DriverSessionRepository(Protocol):
    def add(self, session: DriverSession) -> None: ...
    def by_token_hash(self, token_hash: str) -> DriverSession | None: ...
    def by_code(self, code_id: str) -> DriverSession | None: ...
    def by_trip(self, trip_id: str, service_date: date) -> DriverSession | None: ...
    def list_all(self) -> list[DriverSession]: ...
    def save(self, session: DriverSession) -> None: ...
    def delete(self, session_id: str) -> bool: ...
class DriverSessionListener(Protocol):        # lo implementa driver_demand
    def service_selected(self, session: DriverSession, previous: DriverService | None) -> None: ...
    def position_updated(self, session: DriverSession) -> None: ...
    def session_closed(self, session_id: str, reason: SessionCloseReason) -> None: ...
```

### API (`/api/v1/driver`, `Cache-Control: no-store`)

| Método | Ruta | Cuerpo / respuesta |
|---|---|---|
| POST | `/sessions` | `{"code": "4821 0937"}` → `201 {"session_id", "session_token", "idle_timeout_s": 600}` |
| GET | `/lines` | `{"lines": [{"line": "93", "color": "FE0000", "text_color": "FFFFFF", "directions": [{"direction_id": 0, "headsign": "…"}]}]}` |
| GET | `/departures?line=93&direction_id=0` | `{"departures": [{"trip_id", "service_date", "departure_at", "first_stop_name", "headsign", "taken"}]}` |
| PUT | `/sessions/current/service` | `{"line", "direction_id", "trip_id", "service_date"}` → `200` estado (como `GET /sessions/current`) |
| PUT | `/sessions/current/position` | `{"lat", "lon", "accuracy_m", "recorded_at"}` → `204` |
| GET | `/sessions/current` | `{"session_id", "service": {…} \| null, "gps", "off_route", "finished", "upcoming": [{"stop_id", "name", "stop_sequence", "distance_m"}]}` |
| DELETE | `/sessions/current` | `204` |

`departures` (red): para el día de servicio de hoy y el anterior (horas ≥ 24:00), viajes de
`line`/`direction_id` con servicio activo, salida de la primera parada (`departure_s` de
`stop_sequence` mínima) en `[now − 30 min, now + 60 min]`. Nuevo método
`NetworkRepository.departures(line, direction_id, service_date, from_s, to_s) -> list[Departure]`
y `list_lines() -> list[LineDirectionsView]`.

`LoginLimiter`: reutiliza `InMemoryRateLimiter` de `alert_create` con clave `driver-login:<ip>`,
5 fallos en 15 min; mientras haya bloqueo se responde `429` sin comprobar el código. Solo los
fallos llaman a `acquire`; un acierto no reinicia el contador.

Errores: `401 …/invalid-driver-code`, `401 …/invalid-session`, `409 …/departure-taken`,
`422 …/invalid-departure`, `429 …/rate-limited`, `503 …/network-unavailable`.

`CloseDriverSession(session_id, reason)`: borra la sesión y llama a
`listener.session_closed`; idempotente.

## 4. Datos

Tabla `driver_session`: `session_id` PK, `token_hash` UNIQUE, `code_id` UNIQUE, `started_at`,
`line`, `direction_id`, `trip_id`, `service_date` (NULL hasta elegir salida), índice único
parcial `(trip_id, service_date)` donde `trip_id` no es NULL, `lat`, `lon`, `accuracy_m`,
`recorded_at`, `last_position_at`, `progress_m`, `off_route`.

## 5. Configuración

| Variable | Default |
|---|---|
| `AVISABUS_DRIVER_IDLE_TIMEOUT_MIN` | `10` |
| `AVISABUS_DRIVER_GPS_STALE_S` | `30` |
| `AVISABUS_DRIVER_LOGIN_MAX_FAILURES` | `5` |
| `AVISABUS_DRIVER_LOGIN_BLOCK_MIN` | `15` |
| `AVISABUS_DRIVER_REAPER_INTERVAL_S` | `60` |

## 6. Estrategia de test

| AC | Test |
|---|---|
| AC-01–AC-08, AC-11, AC-12 | `tests/integration/test_driver_api.py` (`gtfs_mini`, `FakeClock`, código creado con el caso de uso) |
| AC-02 (limitador), AC-06 (ventana) | `tests/unit/test_driver_login.py`, `tests/unit/test_departures.py` |
| AC-09, AC-10 | `tests/unit/test_upcoming_stops.py` (trazados sintéticos: recta, bucle, ida y vuelta por la misma calle; posición fuera de ruta) |
| AC-13 | `tests/unit/test_reap_driver_sessions.py` + arranque con `lifespan` |
| AC-14 | `tests/integration/test_cli_driver_codes.py` (amplía) |
| AC-15 | logger falso + logs capturados |

## 7. Decisiones locales permitidas

- Caché de las distancias de paradas por `shape_id`.
- Estructura de `LineDirectionsView` y `Departure` (con los campos de la API).

## 8. Preguntas abiertas

Ninguna.
