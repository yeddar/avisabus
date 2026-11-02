# Fuente de llegadas del SAE — tasks

> Feature: `sae_arrivals_source` · Versión: 1.2 · Estado: APPROVED
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

> **v1.2:** T-01…T-10 implementadas en versiones anteriores (T-08b sigue opcional). En esta versión
> solo quedan **T-11, T-12 y T-13**.
>
> **v1.1:** E-01 completada (`progress/explore_sae.md`); CP-3 resuelto. No repetir.

## Tareas

- [ ] **T-01** — Modelo normalizado (`ArrivalKind`, `SaeArrival`, `ArrivalsSnapshot`), puerto
  `ArrivalsSource` y `ArrivalsUnavailableError`.
  - AC: (base de todos)
  - Ficheros: `domain/models/arrivals.py`, `domain/ports/arrivals.py`, `domain/errors.py`
  - Verificación: `cd backend && uv run mypy`

- [ ] **T-02** — Fixtures iniciales: convertir las muestras de `progress/explore_sae_samples/` al
  formato de grabación (design §5, con `source_format: "qrphp_html"`) en
  `tests/fixtures/sae_recordings/samples/`: reales (minutos 508 y 2070, `Próximo` 2070, parada
  inexistente 99999, serie 2070 con el paso de la 95) y derivadas de
  `stop508_qrphp_https_20261102T110011Z` (sin llegadas: sin bloques de llegada; `HH:MM`: un tiempo
  cambiado a `22:41`), con `derived_from` y `note`, y `README.md`.
  - AC: sae_arrivals_source.AC-19 (b, c, d)
  - Ficheros: `backend/tests/fixtures/sae_recordings/**`
  - Verificación: revisión del README; `ls` de las muestras

- [ ] **T-03** — Parser `parse_qrphp_html` (reglas de design §4) con tests sobre las fixtures.
  - AC: sae_arrivals_source.AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-21
  - Ficheros: `adapters/outbound/sae/qrphp_parser.py`, `tests/unit/test_sae_parser.py`
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
  - AC: sae_arrivals_source.AC-14, AC-15, AC-16, AC-22
  - Ficheros: `adapters/outbound/sae/recording.py`, `adapters/outbound/sae/replay.py`, `tests/unit/test_sae_replay.py`, `tests/integration/test_sae_recording.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_replay.py tests/integration/test_sae_recording.py`

- [ ] **T-07** — CLI `sae fetch` y `sae record` (sleep y reloj inyectables).
  - AC: sae_arrivals_source.AC-17, AC-18
  - Ficheros: `adapters/inbound/cli/sae.py`, `tests/integration/test_cli_sae.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_sae.py`

- [ ] **T-08** — Grabar con la CLI la sesión real `stop_508_peak` (≥ 15 min, intervalo 20 s, hora
  punta **de lunes a jueves**, porque `gtfs_mini` no tiene los servicios del viernes; prevista el
  martes 2026-11-03 a las 7:45), comprobar que contiene el paso de al menos un autobús y
  documentarla en el `README.md`.
  Requiere red: si el agente no puede ejecutarla, la tarea queda marcada "pendiente de la persona"
  con el comando exacto, y la feature no pasa a revisión hasta tenerla.
  - AC: sae_arrivals_source.AC-19 (a)
  - Ficheros: `backend/tests/fixtures/sae_recordings/stop_508_peak/**`
  - Verificación: test `tests/unit/test_sae_fixtures.py` que recorre la sesión y detecta al menos un salto de ETA

- [ ] **T-08b** — *(Opcional, no bloquea la revisión.)* Grabación nocturna corta (~10 min hacia
  las 23:30, paradas 508 y 2070) para obtener casos reales de `HH:MM` (líneas nocturnas) y de
  parada sin llegadas. Si el formato real difiere de design §4, se anota en
  `progress/impl_sae_arrivals_source.md` y se abre CP-3; si coincide, las muestras reales sustituyen
  o complementan a las derivadas.
  - AC: sae_arrivals_source.AC-03, AC-07, AC-19 (b, c)
  - Ficheros: `backend/tests/fixtures/sae_recordings/night_*/**`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_parser.py`

- [ ] **T-09** — Composición `build_arrivals_source` según configuración, variables en
  `.env.example`, registro de la tarea de `sae.stats` en el ciclo de vida de la app.
  - AC: sae_arrivals_source.AC-13, AC-20
  - Ficheros: `adapters/outbound/sae/compose.py`, `config.py`, `main.py`, `.env.example`, `tests/unit/test_sae_compose.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_compose.py`

- [ ] **T-10** — Verificación completa.
  - Verificación: `./init.sh verify`

- [ ] **T-11** — (v1.2, NB-1) La caché negativa guarda solo el motivo del error y lanza una
  instancia nueva en cada acierto.
  - AC: sae_arrivals_source.AC-11
  - Ficheros: `adapters/outbound/sae/cache.py`, `tests/unit/test_sae_cache.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_cache.py`

- [ ] **T-12** — (v1.2, NB-4, NB-7) El comando de regeneración del `README.md` de las grabaciones
  usa una carpeta `--out` nueva (no sobrescribe sesiones); cerrar los clientes HTTP que los tests de
  composición dejan abiertos.
  - AC: (calidad; sin AC nuevo)
  - Ficheros: `backend/tests/fixtures/sae_recordings/README.md`, `tests/unit/test_sae_compose.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_sae_compose.py -W error::ResourceWarning`

- [ ] **T-13** — Verificación completa (v1.2).
  - Verificación: `./init.sh verify`
