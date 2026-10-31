# Fuente de llegadas del SAE — design

> Feature: `sae_arrivals_source` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-07, RF-08, RF-11, RF-35, RNF-08, RNF-10, RNF-13 · Casos de uso: CU-01 · Depende de: project_scaffold

## 1. Resumen

```
CachedArrivalsSource ─▶ RecordingArrivalsSource? ─▶ SaeHttpArrivalsSource ─▶ SaeResponseParser
                     └▶ SaeReplayArrivalsSource ─────────────────────────────▶ SaeResponseParser
```

Todas implementan el puerto `ArrivalsSource`. El parser es una función pura sobre el cuerpo
bruto, compartida por la fuente HTTP y la de replay, de modo que los tests con grabaciones
ejercitan el mismo código que producción.

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/arrivals.py` | `ArrivalKind`, `SaeArrival`, `ArrivalsSnapshot` |
| domain | `ports/arrivals.py` | `ArrivalsSource` (Protocol) |
| domain | `errors.py` | `ArrivalsUnavailableError(stop_id, reason)` |
| adapters/outbound | `sae/parser.py` | `parse_sae_response(body, content_type, fetched_at) -> ParseResult` |
| adapters/outbound | `sae/http_source.py` | `SaeHttpArrivalsSource` |
| adapters/outbound | `sae/cache.py` | `CachedArrivalsSource` |
| adapters/outbound | `sae/recording.py` | `RecordingArrivalsSource`, `SaeRecording` (formato de fichero) |
| adapters/outbound | `sae/replay.py` | `SaeReplayArrivalsSource` |
| adapters/outbound | `sae/compose.py` | `build_arrivals_source(settings, clock, http_client) -> ArrivalsSource` |
| adapters/inbound | `cli/sae.py` | `avisabus sae fetch`, `avisabus sae record` |

## 3. Interfaces

```python
# domain/models/arrivals.py
class ArrivalKind(StrEnum):
    MINUTES = "MINUTES"
    CLOCK_TIME = "CLOCK_TIME"

@dataclass(frozen=True, slots=True)
class SaeArrival:
    line: str                  # tal cual (p. ej. "93", "C2", "N4")
    destination: str           # tal cual (p. ej. "Pass. Marítim")
    kind: ArrivalKind
    minutes: int | None        # solo si kind == MINUTES
    arrival_at: datetime       # tz-aware UTC

@dataclass(frozen=True, slots=True)
class ArrivalsSnapshot:
    stop_id: str
    fetched_at: datetime       # tz-aware UTC
    arrivals: tuple[SaeArrival, ...]   # en el orden del SAE

# domain/ports/arrivals.py
class ArrivalsSource(Protocol):
    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot: ...
    # lanza ArrivalsUnavailableError

# adapters/outbound/sae/parser.py
@dataclass(frozen=True, slots=True)
class ParseResult:
    arrivals: tuple[SaeArrival, ...]
    skipped: tuple[str, ...]   # motivos de las entradas descartadas
def parse_sae_response(body: bytes, content_type: str | None, fetched_at: datetime) -> ParseResult: ...
# lanza SaeUnparseableError si el cuerpo completo no es interpretable

# adapters/outbound/sae/http_source.py
class SaeHttpArrivalsSource:
    def __init__(self, client: httpx.AsyncClient, url_template: str, clock: Clock,
                 timeout_s: float, user_agent: str, on_raw: RawObserver | None = None) -> None: ...

# adapters/outbound/sae/cache.py
class CachedArrivalsSource:
    def __init__(self, inner: ArrivalsSource, clock: Clock, ttl: timedelta,
                 error_ttl: timedelta, max_concurrency: int) -> None: ...
    def stats(self) -> CacheStats: ...          # hits, misses, errors

# adapters/outbound/sae/replay.py
class SaeReplayArrivalsSource:
    def __init__(self, recordings_dir: Path, clock: Clock, start: datetime | None = None) -> None: ...
    # start = None → instante del primer get_arrivals
```

`RawObserver` = `Callable[[RawResponse], None]`, donde `RawResponse` contiene `stop_id`,
`captured_at`, `status`, `content_type`, `body`, `error`. `RecordingArrivalsSource` se implementa
como un observador que escribe ficheros (no necesita envolver la fuente).

### Caché (detalle)

- Entrada por `stop_id`: `(snapshot | error, stored_at)`.
- Hit si `now - stored_at < ttl` (snapshot) o `< error_ttl` (error → se relanza el mismo error).
- Single-flight: diccionario `stop_id → asyncio.Future` en vuelo; los llamantes concurrentes
  esperan el mismo `Future`.
- Concurrencia: `asyncio.Semaphore(max_concurrency)` alrededor de la llamada a `inner`.
- `sae.stats`: lo emite una tarea ligera en `background/` (se registra en el ciclo de vida de la
  app); en tests se invoca `emit_stats()` directamente.

### CLI

```
avisabus sae fetch --stop ID
avisabus sae record --stop ID [--stop ID ...] --interval S --duration S --out DIR
```

`record` usa siempre la fuente HTTP con observador de grabación (sin caché), recorre las paradas
en cada ciclo y espera con una función `sleep` inyectable.

## 4. Formato bruto del SAE

> **Se fija tras la exploración E-01.** El explorer documenta en `progress/explore_sae.md`:
> URL y parámetros, método, `content_type`, codificación, estructura (XML/JSON/HTML), ejemplos
> reales de: llegadas en minutos, llegadas con hora, marcadores de "llegando/en parada", sin
> llegadas, parada inexistente; latencia típica; condiciones de uso conocidas.
>
> - Si el formato contiene, por llegada, **línea, destino y minutos u hora** (como `emtvlcapi`),
>   el implementer escribe el parser según esos hallazgos **sin cambiar los AC ni las
>   interfaces** de este documento y registra las reglas concretas de parseo en
>   `progress/impl_sae_arrivals_source.md` § "Decisiones locales".
> - Si no los contiene o requiere otra estrategia (autenticación, scraping de HTML complejo,
>   bloqueo), → **CP-3**.

Plantilla de URL configurable (`AVISABUS_SAE_URL_TEMPLATE`, con `{stop_id}`), con el valor
encontrado en E-01 como default.

## 5. Formato de grabación

```
<dir>/
├── session.json        {"started_at": "...Z", "stops": ["508"], "interval_s": 20, "source_url_template": "..."}
└── 508/
    ├── 000000.json     {"stop_id": "508", "captured_at": "...Z", "offset_s": 0, "status": 200,
    │                    "content_type": "...", "body": "<texto>", "error": null}
    ├── 000020.json
    └── ...
```

`body` se guarda como texto (decodificado con la codificación declarada; si es binario, base64
con `"body_encoding": "base64"`). Las fixtures derivadas (no reales) llevan
`"derived_from": "<fichero>"` y `"note": "<qué se cambió>"`.

## 6. Errores

| Situación | Resultado |
|---|---|
| Timeout | `ArrivalsUnavailableError(stop_id, "timeout")` |
| Error de red | `ArrivalsUnavailableError(stop_id, "network")` |
| HTTP no 2xx | `ArrivalsUnavailableError(stop_id, "http_503")` |
| Cuerpo no interpretable | `ArrivalsUnavailableError(stop_id, "unparseable")` |
| Replay sin datos | `ArrivalsUnavailableError(stop_id, "no_recording")` |

Logs: `sae.error` (`stop_id`, `reason`, `elapsed_ms`), `sae.unparsed_entry` (`stop_id`,
`reason`), `sae.stats` (`hits`, `misses`, `errors`).

## 7. Configuración

| Variable | Default | Notas |
|---|---|---|
| `AVISABUS_ARRIVALS_SOURCE` | `http` (`replay` si `env=test`) | `http` \| `replay` |
| `AVISABUS_SAE_URL_TEMPLATE` | valor de E-01 | con `{stop_id}` |
| `AVISABUS_SAE_TIMEOUT_S` | `3` | |
| `AVISABUS_SAE_CACHE_TTL_S` | `20` | RF-08 |
| `AVISABUS_SAE_ERROR_TTL_S` | `5` | |
| `AVISABUS_SAE_MAX_CONCURRENCY` | `4` | |
| `AVISABUS_SAE_REPLAY_DIR` | `tests/fixtures/sae_recordings/stop_508_peak` | |
| `AVISABUS_SAE_CONTACT` | `""` | Se añade al User-Agent: `AvisaBus/<versión> (TFM; <contacto>)` |

## 8. Estrategia de test

- **Parser (unit):** se alimenta con los cuerpos de las grabaciones reales (AC-02–AC-07).
- **HTTP (integration):** `httpx.MockTransport` (no abre sockets) para respuestas, errores,
  timeouts (`httpx.TimeoutException`) y verificación de URL y cabeceras (AC-01, AC-08).
- **Caché (unit):** fuente fake con contador de llamadas y `FakeClock` (AC-09–AC-13); para
  single-flight, la fuente fake espera un `asyncio.Event`.
- **Replay (unit):** directorio temporal con grabaciones sintéticas mínimas + las reales
  (AC-15, AC-16).
- **CLI (integration):** `CliRunner`, transporte simulado, `sleep` y reloj inyectados (AC-17, AC-18).
- **Grabación real:** la hace la persona o el explorer **fuera de los tests** con
  `avisabus sae record` (AC-19); nunca en CI.

## 9. Decisiones locales permitidas

- Reglas concretas del parser derivadas de E-01 (dentro de las interfaces y AC).
- Librería de parseo (XML estándar, `json`, `selectolax` para HTML si fuera necesario).

## 10. Preguntas abiertas

- Delegada a exploración E-01: endpoint y formato exactos (ver §4).
