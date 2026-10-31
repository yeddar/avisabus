# Fuente de llegadas del SAE — tasks

> Feature: `sae_arrivals_source` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-07, RF-08, RF-11, RF-35, RNF-08, RNF-10, RNF-13 · Casos de uso: CU-01 · Depende de: project_scaffold

## Exploración

- **E-01** — Endpoint y formato del SAE. Fuentes de partida: el campo de "próximas llegadas" del
  dataset de paradas EMT del Ajuntament (opendata.vlci.valencia.es, dataset `emt`; capa
  `geoportal.valencia.es/server/rest/services/OPENDATA/Trafico/MapServer/226`) y el cliente
  comunitario `emtvlcapi` (PyPI). Documentar URL, parámetros, `content_type`, codificación,
  estructura y ejemplos reales de las paradas **508** y **2070** (minutos, hora `HH:MM`,
  "llegando/en parada", sin llegadas, parada inexistente), latencia y cualquier condición de uso.
  Máximo 1 petición cada 20 s por parada durante la exploración. Guardar las respuestas brutas
  de ejemplo (cuerpo + cabeceras relevantes) en `progress/explore_sae_samples/`.
  → `progress/explore_sae.md`

> Si E-01 contradice §4 de `design.md` → CP-3 antes de implementar.

## Tareas

- [ ] **T-01** — Modelo normalizado (`ArrivalKind`, `SaeArrival`, `ArrivalsSnapshot`), puerto
  `ArrivalsSource` y `ArrivalsUnavailableError`.
  - AC: (base de todos)
  - Ficheros: `domain/models/arrivals.py`, `domain/ports/arrivals.py`, `domain/errors.py`
  - Verificación: `cd backend && uv run mypy`

- [ ] **T-02** — Fixtures iniciales: convertir las muestras de `progress/explore_sae_samples/` al
  formato de grabación (design §5) en `tests/fixtures/sae_recordings/samples/` (minutos, hora
  `HH:MM`, llegando, sin llegadas, error; las derivadas, marcadas como tales) con `README.md`.
  - AC: sae_arrivals_source.AC-19 (b, c, d)
  - Ficheros: `backend/tests/fixtures/sae_recordings/**`
  - Verificación: revisión del README; `ls` de las muestras

- [ ] **T-03** — Parser `parse_sae_response` con tests sobre los cuerpos reales.
  - AC: sae_arrivals_source.AC-02, AC-03, AC-04, AC-05, AC-06, AC-07
  - Ficheros: `adapters/outbound/sae/parser.py`, `tests/unit/test_sae_parser.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_parser.py`

- [ ] **T-04** — `SaeHttpArrivalsSource` (URL, timeout, User-Agent, errores, observador de
  respuestas brutas).
  - AC: sae_arrivals_source.AC-01, AC-08
  - Ficheros: `adapters/outbound/sae/http_source.py`, `tests/integration/test_sae_http_source.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_sae_http_source.py`

- [ ] **T-05** — `CachedArrivalsSource` (TTL, single-flight, caché negativa, semáforo,
  contadores y `emit_stats`).
  - AC: sae_arrivals_source.AC-09, AC-10, AC-11, AC-12, AC-13
  - Ficheros: `adapters/outbound/sae/cache.py`, `tests/unit/test_sae_cache.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_cache.py`

- [ ] **T-06** — Grabación (`RecordingArrivalsSource` como observador) y `SaeReplayArrivalsSource`.
  - AC: sae_arrivals_source.AC-14, AC-15, AC-16
  - Ficheros: `adapters/outbound/sae/recording.py`, `adapters/outbound/sae/replay.py`, `tests/unit/test_sae_replay.py`, `tests/integration/test_sae_recording.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_replay.py tests/integration/test_sae_recording.py`

- [ ] **T-07** — CLI `sae fetch` y `sae record` (sleep y reloj inyectables).
  - AC: sae_arrivals_source.AC-17, AC-18
  - Ficheros: `adapters/inbound/cli/sae.py`, `tests/integration/test_cli_sae.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_sae.py`

- [ ] **T-08** — Grabar con la CLI la sesión real `stop_508_peak` (≥ 15 min, intervalo 20 s, hora
  punta), comprobar que contiene el paso de al menos un autobús y documentarla en el `README.md`.
  Requiere red: si el agente no puede ejecutarla, la tarea queda marcada "pendiente de la persona"
  con el comando exacto, y la feature no pasa a revisión hasta tenerla.
  - AC: sae_arrivals_source.AC-19 (a)
  - Ficheros: `backend/tests/fixtures/sae_recordings/stop_508_peak/**`
  - Verificación: test `tests/unit/test_sae_fixtures.py` que recorre la sesión y detecta al menos un salto de ETA

- [ ] **T-09** — Composición `build_arrivals_source` según configuración, variables en
  `.env.example`, registro de la tarea de `sae.stats` en el ciclo de vida de la app.
  - AC: sae_arrivals_source.AC-13, AC-20
  - Ficheros: `adapters/outbound/sae/compose.py`, `config.py`, `main.py`, `.env.example`, `tests/unit/test_sae_compose.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_compose.py`

- [ ] **T-10** — Verificación completa.
  - Verificación: `./init.sh verify`
