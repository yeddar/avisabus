# Fuente de llegadas del SAE — design

> Feature: `sae_arrivals_source` · Versión: 1.2 · Estado: APPROVED
> Requisitos: RF-07, RF-08, RF-11, RF-35, RNF-08, RNF-10, RNF-13 · Casos de uso: CU-01 · Depende de: project_scaffold

## 1. Resumen

```
CachedArrivalsSource ─▶ SaeHttpArrivalsSource (QR.php) ──(observador: grabación)──▶ parse_qrphp_html
                     └▶ SaeReplayArrivalsSource ── parser según session.source_format ──▶ parse_qrphp_html
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
| adapters/outbound | `sae/qrphp_parser.py` | `parse_qrphp_html(body, stop_id, fetched_at) -> ParseResult` (+ registro `PARSERS`) |
| adapters/outbound | `sae/http_source.py` | `SaeHttpArrivalsSource` |
| adapters/outbound | `sae/cache.py` | `CachedArrivalsSource` |
| adapters/outbound | `sae/recording.py` | `RecordingArrivalsSource`, `SaeRecording` (formato de fichero) |
| adapters/outbound | `sae/replay.py` | `SaeReplayArrivalsSource` |
| adapters/outbound | `sae/compose.py` | `build_arrivals_source(settings, clock, http_client) -> CachedArrivalsSource` (devuelve el tipo concreto para que `main.py` acceda a `stats()` y `emit_stats()`) |
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

# adapters/outbound/sae/qrphp_parser.py
@dataclass(frozen=True, slots=True)
class ParseResult:
    arrivals: tuple[SaeArrival, ...]
    skipped: tuple[str, ...]   # motivos de las entradas descartadas
def parse_qrphp_html(body: bytes, stop_id: str, fetched_at: datetime) -> ParseResult: ...
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
- Hit si `now - stored_at < ttl` (snapshot) o `< error_ttl` (error → se lanza una **instancia
  nueva** de `ArrivalsUnavailableError` con el mismo `stop_id` y `reason`; se guarda solo el motivo,
  no el objeto de la excepción) (v1.2, AC-11).
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

## 4. Formato bruto del SAE (`QR.php`, confirmado en E-01)

**Petición.** `GET https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}` (plantilla
`AVISABUS_SAE_URL_TEMPLATE`). Sin cookies ni cabeceras especiales; `User-Agent` del proyecto
(AC-01). Respuesta `200`, `text/html; charset=utf-8`, unos 2–5 KB, latencia observada 80–250 ms.

**Estructura relevante** (fragmento HTML de jQuery Mobile, sin `<html>`/`<body>`):

```html
<div style=" background: grey; …">508 - Parc de l'Oest - Enguera</div>        ← cabecera
<div style="padding-left: 5px;…border-bottom:1px solid black;" >
  <span class="imagenParada"><img src="…/line-icons/93bigW.gif" title="93" …></span>
  <span style="position: relative; top: -5px;">&nbsp;&nbsp;Pass. Marítim - 7 min.</span>
</div>                                                                           ← una llegada
```

**Reglas del parser** `parse_qrphp_html(body, stop_id, fetched_at)` (módulo
`adapters/outbound/sae/qrphp_parser.py`, con `html.parser` de la biblioteca estándar):

1. **Cabecera (AC-21):** se busca el texto de la cabecera; debe casar con
   `^{stop_id} - .+$` (tras desescapar y recortar). Si no existe o no casa →
   `SaeUnparseableError` (→ `ArrivalsUnavailableError(stop_id, "unparseable")`).
2. **Entradas:** cada bloque que contiene un `<img title="…">` seguido de un `<span>` de texto.
   `line` = valor de `title` recortado.
3. **Texto:** se desescapan las entidades y se recortan los espacios de los extremos, incluido
   `\xa0`. Se separa por el **último** `" - "`: a la izquierda `destination`, a la derecha el
   tiempo. Si no hay `" - "` → entrada descartada (AC-06).
4. **Tiempo:**
   - `^\d+ min\.?$` → `MINUTES`, `minutes = n` (AC-02);
   - `próximo` sin distinguir mayúsculas ni acentos → `MINUTES`, `minutes = 0` (AC-04);
   - `^\d{1,2}:\d{2}$` → `CLOCK_TIME` (AC-03; formato **supuesto**, no observado);
   - cualquier otro → entrada descartada y `sae.unparsed_entry` con el texto del tiempo (no el
     cuerpo) (AC-06). Así un marcador nuevo aparece en los logs sin romper el parser.
5. **Sin llegadas:** cabecera válida y ninguna entrada → lista vacía (AC-07).
6. Se conserva el orden de la página (ascendente por tiempo).

Si EMT cambia el HTML de forma que no se encuentre la cabecera, todas las consultas darán
`unparseable` y el sistema pasará al horario programado (RF-09) en lugar de mostrar "sin
llegadas" por error.

**Otras fuentes.** El parser se selecciona por formato (`qrphp_html`). Un futuro adaptador del XML
`getSAE`, si EMT lo autoriza (ADR-015), añadiría otro formato (`getsae_xml`) y su parser sin
cambiar las interfaces.

## 5. Formato de grabación

```
<dir>/
├── session.json        {"started_at": "...Z", "stops": ["508"], "interval_s": 20,
│                        "source_url_template": "...", "source_format": "qrphp_html"}
└── 508/
    ├── 000000.json     {"stop_id": "508", "captured_at": "...Z", "offset_s": 0, "status": 200,
    │                    "content_type": "...", "body": "<texto>", "error": null}
    ├── 000020.json
    └── ...
```

`interval_s` puede ser `null` en sesiones que no se grabaron a intervalo fijo (p. ej. las muestras
de la exploración E-01 convertidas a fixtures).

`body` se guarda como texto (decodificado con la codificación declarada; si es binario, base64
con `"body_encoding": "base64"`). Las fixtures derivadas (no reales) llevan
`"derived_from": "<fichero>"` y `"note": "<qué se cambió>"`.

`SaeReplayArrivalsSource` lee `source_format` de `session.json` y elige el parser con un registro
`PARSERS: Mapping[str, Callable[...]] = {"qrphp_html": parse_qrphp_html}`; formato desconocido →
`ConfigurationError` al construirse (AC-22).

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
| `AVISABUS_SAE_URL_TEMPLATE` | `https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}` | con `{stop_id}` |
| `AVISABUS_SAE_TIMEOUT_S` | `3` | |
| `AVISABUS_SAE_CACHE_TTL_S` | `20` | RF-08 |
| `AVISABUS_SAE_ERROR_TTL_S` | `5` | |
| `AVISABUS_SAE_MAX_CONCURRENCY` | `4` | |
| `AVISABUS_SAE_REPLAY_DIR` | `tests/fixtures/sae_recordings/stop_508_peak` | |
| `AVISABUS_SAE_CONTACT` | `""` | Se añade al User-Agent: `AvisaBus/<versión> (TFM; <contacto>)` |

## 8. Estrategia de test

- **Parser (unit):** se alimenta con los cuerpos reales de `progress/explore_sae_samples/`
  convertidos a fixtures (minutos, `Próximo`, parada inexistente) y con las derivadas (sin
  llegadas, `HH:MM`) (AC-02–AC-07, AC-21).
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
