# API de parada y llegadas — design

> Feature: `stop_arrivals_api` · Versión: 1.2 · Estado: APPROVED
> Requisitos: RF-06, RF-09, RF-11, RF-15, RF-32, RNF-01, RNF-08 · Casos de uso: CU-01 · Depende de: gtfs_import, stop_tokens_qr, sae_arrivals_source, occupancy_sensor

## 1. Resumen

```mermaid
flowchart LR
  REQ[GET /stops/:id/arrivals] --> TOK{token válido?}
  TOK -- no --> E404[404]
  TOK -- sí --> SRC[ArrivalsSource.get_arrivals]
  SRC -- ok --> ENR[para cada SaeArrival:<br/>línea en red? → DirectionResolver → TripMatcher → OccupancySensor]
  SRC -- ArrivalsUnavailable --> SCH[ScheduledArrivalsProvider<br/>2 pasadas por línea-sentido / 90 min]
  SCH --> OCC[OccupancySensor]
  ENR --> RESP[StopArrivals]
  OCC --> RESP
```

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/stop_arrivals.py` | `ArrivalSource`, `VehicleView`, `ArrivalView`, `StopArrivals`, `StopView` |
| domain | `services/direction_resolver.py` | `resolve_direction(...)`, `normalize_destination(...)`, `DEFAULT_ALIASES` |
| domain | `services/trip_matcher.py` | `match_trips(...)` |
| application | `get_stop.py` | `GetStop` |
| application | `get_stop_arrivals.py` | `GetStopArrivals` |
| application | `scheduled_arrivals.py` | `ScheduledArrivalsProvider` |
| adapters/inbound | `http/routes/stops.py` | Endpoints y esquemas Pydantic |
| adapters/inbound | `http/errors.py` | Mapeo `StopNotFoundError` → 404, `NoActiveFeedError` → 503 |
| main | `main.py` | Composición |

## 3. Interfaces

```python
# domain/models/stop_arrivals.py
class ArrivalSource(StrEnum):
    REALTIME = "REALTIME"; SCHEDULED = "SCHEDULED"

@dataclass(frozen=True, slots=True)
class VehicleView:
    trip_id: str
    service_date: date

@dataclass(frozen=True, slots=True)
class ArrivalView:
    line: str
    destination: str
    direction_id: int | None
    in_network: bool
    kind: ArrivalKind
    minutes: int | None
    arrival_at: datetime
    line_color: str | None
    line_text_color: str | None
    vehicle: VehicleView | None
    occupancy: OccupancyStatus | None
    can_alert: bool

@dataclass(frozen=True, slots=True)
class StopView:
    stop_id: str
    name: str
    lines: tuple[LineDirection, ...]

@dataclass(frozen=True, slots=True)
class StopArrivals:
    stop_id: str
    source: ArrivalSource
    generated_at: datetime
    refresh_after_s: int
    arrivals: tuple[ArrivalView, ...]
```

```python
# domain/services/direction_resolver.py
@dataclass(frozen=True, slots=True)
class DirectionCandidate:
    direction_id: int
    headsign: str

def normalize_destination(text: str, aliases: Mapping[str, str]) -> frozenset[str]: ...
    # casefold → NFKD sin diacríticos → no alfanumérico = espacio → tokens
    # → cada token sustituido por aliases.get(token, token) → descarta tokens vacíos

def resolve_direction(destination: str, candidates: Sequence[DirectionCandidate],
                      aliases: Mapping[str, str], min_score: float = 0.34,
                      overrides: Mapping[tuple[str, str], int] | None = None,
                      line: str | None = None) -> int | None: ...
    # candidates = un elemento por (direction_id, headsign) de headsigns_at_stop(stop, line);
    #              un mismo sentido puede aparecer varias veces (variantes de recorrido).
    # 0 candidatos → None; todos del mismo direction_id → ese direction_id
    # override exacto (line, destination) → ese direction_id si está entre los candidatos
    # si no: score(headsign) = |A∩B| / |A∪B| (Jaccard), contando como coincidencia también los
    #        pares en que un token es prefijo del otro con longitud ≥ 3;
    #        best[d] = máximo score de los headsigns del sentido d;
    #        gana d* si best[d*] ≥ min_score y best[d*] > best[d] para todo d ≠ d*; si no → None

DEFAULT_ALIASES = {"pass": "passeig", "pg": "passeig", "est": "estacio", "av": "avinguda",
                   "avda": "avinguda", "pl": "placa", "hosp": "hospital", "univ": "universitats",
                   "c": "carrer"}
```

La tabla definitiva de alias y los *overrides* se completan con los hallazgos de E-01 (decisión
local permitida: añadir entradas; no cambiar el algoritmo).

```python
# domain/services/trip_matcher.py
@dataclass(frozen=True, slots=True)
class TripCandidate:
    trip_id: str
    service_date: date
    scheduled_at: datetime        # tz-aware UTC

def match_trips(arrival_times: Sequence[datetime], candidates: Sequence[TripCandidate],
                tolerance: timedelta) -> list[TripCandidate | None]: ...
    # Para llegadas de la MISMA línea y sentido, ordenadas por tiempo:
    # asignación voraz en orden: a cada llegada, el candidato libre con menor |scheduled_at − t|
    # dentro de la tolerancia; además, el candidato elegido debe ser posterior al asignado a la
    # llegada anterior (orden temporal). Sin candidato → None.
```

```python
# application/get_stop_arrivals.py
class GetStopArrivals:
    def __init__(self, network: NetworkRepository, signer: StopTokenSigner,
                 arrivals: ArrivalsSource, scheduled: ScheduledArrivalsProvider,
                 occupancy: OccupancySensor, thresholds: OccupancyThresholds, clock: Clock,
                 refresh_after_s: int, match_tolerance: timedelta,
                 aliases: Mapping[str, str], direction_overrides: Mapping[tuple[str, str], int],
                 logger: Logger) -> None: ...
    async def execute(self, stop_id: str, token: str) -> StopArrivals: ...
    # lanza StopNotFoundError (token inválido o parada inexistente) y NoActiveFeedError

# application/scheduled_arrivals.py
class ScheduledArrivalsProvider:
    def __init__(self, network: NetworkRepository, window: timedelta = timedelta(minutes=90),
                 per_direction: int = 2) -> None: ...
    def next_arrivals(self, stop_id: str, now: datetime) -> list[ScheduledStopTime]: ...
```

**Días de servicio consultados (v1.2, AC-18):** `NetworkRepository.scheduled_stop_times(stop_id,
at, window)` debe devolver las pasadas de **todos** los días de servicio entre `fecha(at) − 1` y
`fecha(at + window)` (zona del feed). La implementación de `gtfs_import` solo cubría `D − 1` y `D`;
se amplía en esta feature (T-05b), sin cambiar la firma.

Candidatos de `TripMatcher`: `network.scheduled_stop_times(stop_id, at=arrival_at − tolerance,
window=2·tolerance + rango de llegadas)` filtrados por línea y sentido, convertidos a
`TripCandidate` con `scheduled_at` = inicio del día de servicio (Europe/Madrid) + `arrival_s`.

### API

Para `destination` (AC-09) con sentido resuelto se devuelve el headsign ganador (el más parecido
al destino del SAE); en el caso de sentido único, el headsign más frecuente de ese sentido en la
parada.

`GET /api/v1/stops/{stop_id}?t=` → `StopResponse`

```json
{
  "stop_id": "508",
  "name": "Parc de l'Oest - Enguera",
  "lines": [
    {"line": "70", "direction_id": 0, "headsign": "Alboraia", "color": "FE0000", "text_color": "FFFFFF"},
    {"line": "93", "direction_id": 0, "headsign": "Pg. Marítim", "color": "FE0000", "text_color": "FFFFFF"}
  ]
}
```

`GET /api/v1/stops/{stop_id}/arrivals?t=` → `StopArrivalsResponse`

```json
{
  "stop_id": "508",
  "source": "REALTIME",
  "generated_at": "2026-11-04T07:40:00Z",
  "refresh_after_s": 20,
  "arrivals": [
    {
      "line": "93", "destination": "Pg. Marítim", "direction_id": 0, "in_network": true,
      "kind": "MINUTES", "minutes": 4, "arrival_at": "2026-11-04T07:44:00Z",
      "line_color": "FE0000", "line_text_color": "FFFFFF",
      "vehicle": {"trip_id": "12345", "service_date": "2026-11-04"},
      "occupancy": {"level": "MEDIUM", "has_free_seats": true, "free_seats": 6},
      "can_alert": true
    },
    {
      "line": "N4", "destination": "Est.del Nord", "direction_id": null, "in_network": false,
      "kind": "CLOCK_TIME", "minutes": null, "arrival_at": "2026-11-04T21:41:00Z",
      "line_color": null, "line_text_color": null,
      "vehicle": null, "occupancy": null, "can_alert": false
    }
  ]
}
```

(Los valores de ejemplo son ilustrativos.)

Errores (`problem+json`):

| Caso | status | type |
|---|---|---|
| Token inválido / ausente / parada inexistente | 404 | `https://avisabus/problems/stop-not-found` |
| Sin feed activo | 503 | `https://avisabus/problems/network-unavailable` |
| `t` con formato inválido (longitud ≠ 22) | 404 (mismo cuerpo) | idem |

## 4. Datos

Sin tablas nuevas. *Overrides* de sentido opcionales en un JSON:

```json
{ "93|Pass. Marítim": 0, "C2|Circular": 0 }
```

## 5. Errores y logs

| Evento | Campos |
|---|---|
| `arrivals.direction_unresolved` | `stop_id`, `line`, `destination` |
| `arrivals.trip_unmatched` (debug) | `stop_id`, `line`, `direction_id` |
| `arrivals.fallback` | `stop_id`, `reason` |

## 6. Configuración

| Variable | Default |
|---|---|
| `AVISABUS_TRIP_MATCH_TOLERANCE_MIN` | `20` |
| `AVISABUS_SCHEDULED_WINDOW_MIN` | `90` |
| `AVISABUS_SCHEDULED_PER_DIRECTION` | `2` |
| `AVISABUS_DIRECTION_OVERRIDES_FILE` | *(vacío)* |
| `AVISABUS_DIRECTION_MIN_SCORE` | `0.34` |

## 7. Estrategia de test

- **Unit (dominio):** `normalize_destination`, `resolve_direction` con tabla de casos reales de
  E-01 y casos sintéticos de ambigüedad (AC-05–AC-07, AC-09); `match_trips` (AC-10, AC-11).
- **Unit (aplicación):** `GetStopArrivals` con fakes de todos los puertos (AC-04, AC-07, AC-08,
  AC-11–AC-15).
- **Integration (API):** app completa con BD de `gtfs_mini`, replay de `stop_508_peak` y
  `samples/`, `FakeClock` situado dentro de la sesión, `httpx.AsyncClient` (AC-01–AC-04, AC-08,
  AC-12–AC-17).
- La fixture `gtfs_mini` y la sesión `stop_508_peak` deben ser coherentes en fecha: los tests fijan
  el `FakeClock` en la fecha de la grabación y el día de la semana correspondiente debe tener
  servicio en `gtfs_mini` (si no, se regenera `gtfs_mini` con `--date` de la grabación; la
  regeneración se documenta en su README).

## 8. Decisiones locales permitidas

- Entradas de la tabla de alias y del fichero de *overrides* (con los casos de E-01).
- Nombres de los esquemas Pydantic.

## 9. Preguntas abiertas

- Delegadas a exploración: E-01 (destinos SAE vs headsigns GTFS) y E-02 (tolerancia de
  emparejamiento).
