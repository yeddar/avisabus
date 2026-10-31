# Sensor de ocupación — design

> Feature: `occupancy_sensor` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-14, RF-15 · Casos de uso: CU-01 · Depende de: project_scaffold, gtfs_import

## 1. Resumen

`SimulatedOccupancySensor` calcula `occupied = capacity × f_hora × f_recorrido × f_viaje`
(acotado) de forma determinista. Un forzado por línea, guardado en SQLite y leído con caché de
5 s, permite provocar escenarios en demos (p. ej. autobús lleno → alerta de capacidad).

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/occupancy.py` | `VehicleRef`, `OccupancyReading`, `OccupancyLevel`, `OccupancyStatus`, `OccupancyThresholds` |
| domain | `services/occupancy_classifier.py` | `classify_occupancy(reading, thresholds) -> OccupancyStatus` |
| domain | `services/occupancy_simulation.py` | Funciones puras: `hour_factor`, `route_factor`, `trip_factor`, `simulate_occupied` |
| domain | `ports/occupancy.py` | `OccupancySensor`, `OccupancyOverrideRepository` |
| application | `set_occupancy_override.py` | `SetOccupancyOverride`, `ClearOccupancyOverride`, `ListOccupancyOverrides` |
| adapters/outbound | `occupancy/simulated_sensor.py` | `SimulatedOccupancySensor` |
| adapters/outbound | `persistence/sqlite_occupancy_override.py` | Repositorio + tabla `occupancy_override` |
| adapters/inbound | `cli/occupancy.py` | `avisabus occupancy override …` |

## 3. Interfaces

```python
# domain/models/occupancy.py
@dataclass(frozen=True, slots=True)
class VehicleRef:
    trip_id: str
    service_date: date

@dataclass(frozen=True, slots=True)
class OccupancyReading:
    capacity: int
    seats: int
    occupied: int
    measured_at: datetime
    @property
    def free_places(self) -> int: ...
    @property
    def free_seats(self) -> int: ...

class OccupancyLevel(StrEnum):
    FREE = "FREE"; MEDIUM = "MEDIUM"; FULL = "FULL"

@dataclass(frozen=True, slots=True)
class OccupancyThresholds:
    medium: float = 0.50
    full: float = 0.85

@dataclass(frozen=True, slots=True)
class OccupancyStatus:
    level: OccupancyLevel
    has_free_seats: bool
    free_seats: int
    free_places: int
    ratio: float

# domain/ports/occupancy.py
class OccupancySensor(Protocol):
    async def read(self, vehicle: VehicleRef, at: datetime) -> OccupancyReading | None: ...

@dataclass(frozen=True, slots=True)
class OccupancyOverride:
    line: str
    level: OccupancyLevel
    expires_at: datetime

class OccupancyOverrideRepository(Protocol):
    def set(self, override: OccupancyOverride) -> None: ...
    def clear(self, line: str) -> bool: ...
    def active(self, now: datetime) -> list[OccupancyOverride]: ...
```

### Simulación (funciones puras en `domain/services/occupancy_simulation.py`)

| Factor | Definición |
|---|---|
| `hour_factor(local_dt)` | Tabla por hora local (Europe/Madrid): 00–06 → 0,15; 06–07 → 0,40; 07–09 → 1,00; 09–13 → 0,60; 13–15 → 0,85; 15–17 → 0,60; 17–20 → 0,95; 20–22 → 0,45; 22–24 → 0,25. Sábado, domingo: × 0,70. |
| `route_factor(p)` | `max(0,15, sin(π·p) ** 0,8)` con `p ∈ [0, 1]` |
| `trip_factor(seed, trip_id, service_date)` | `0,75 + 0,5 · u`, con `u ∈ [0, 1)` derivado de `sha256(f"{seed}:{trip_id}:{service_date}")` (determinista, sin `random`) |
| `simulate_occupied(capacity, h, r, t)` | `clamp(round(capacity · min(1,05, h·r·t)), 0, capacity)` |

`progress(trip_stop_times, at)`: con el día de servicio y `arrival_s` de la primera y última
parada, `p = (s_at − s_first) / (s_last − s_first)` acotado a [0, 1].

### Forzado

Con forzado activo para la línea del viaje, `occupied` se fija a `round(capacity × r)` con
`r = 0,20` (FREE), `0,65` (MEDIUM) o `0,95` (FULL). La línea del viaje se obtiene de
`NetworkRepository` (los `TripStopTime` no la incluyen; se añade la consulta
`trip_line(trip_id) -> str | None` al repositorio — ampliación del puerto definida aquí).

El sensor cachea `overrides.active(now)` durante 5 s (según `Clock`).

### CLI

```
avisabus occupancy override --line L --level FREE|MEDIUM|FULL [--minutes 30]
avisabus occupancy override --line L --clear
avisabus occupancy override --list
```

## 4. Datos

Tabla `occupancy_override(line TEXT PRIMARY KEY, level TEXT NOT NULL, expires_at TEXT NOT NULL)`
(UTC ISO-8601). Se crea con `create_all` (ADR-011).

## 5. Errores

| Situación | Resultado |
|---|---|
| Configuración inválida (umbrales, asientos > capacidad) | `ConfigurationError` al construir `Settings` |
| Viaje inexistente | `read` devuelve `None` |
| Línea inexistente en `override` | CLI: error y código 2 |

## 6. Configuración

| Variable | Default |
|---|---|
| `AVISABUS_OCCUPANCY_CAPACITY` | `90` |
| `AVISABUS_OCCUPANCY_SEATS` | `28` |
| `AVISABUS_OCCUPANCY_SEED` | `avisabus` |
| `AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM` | `0.50` |
| `AVISABUS_OCCUPANCY_THRESHOLD_FULL` | `0.85` |

## 7. Estrategia de test

- Unit puros: clasificador (fronteras), factores, `simulate_occupied`, progreso; Hypothesis para
  AC-05 (dependencia de desarrollo `hypothesis`).
- Unit del sensor con `NetworkRepository` fake y `OccupancyOverrideRepository` en memoria.
- Integration: repositorio SQLite de forzados y CLI con `CliRunner` y `FakeClock`.

## 8. Decisiones locales permitidas

- Estructura interna de la caché de forzados.

## 9. Preguntas abiertas

Ninguna.
