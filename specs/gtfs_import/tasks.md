# Importación del GTFS — tasks

> Feature: `gtfs_import` · Versión: 1.3 · Estado: APPROVED
> Requisitos: RF-01, RF-02, RF-03, RF-04, RF-32 · Casos de uso: CU-11 · Depende de: project_scaffold

> **v1.1:** E-01 completada (`progress/explore_gtfs_feed.md`, scripts en
> `progress/explore_gtfs_feed_samples/`). No hace falta repetirla.

## Exploración

- **E-01** — En `data/gtfs/emt/` (cabeceras ya confirmadas, ver design §4.1): número de filas
  por fichero; ¿todos los viajes tienen `shape_id` y `trip_headsign`?; máximo `arrival_time`
  (¿hay horas ≥ 24:00:00?); ¿qué líneas sirven las paradas 508 y 2070?; patrones (`shape_id`) por
  línea con primera/última parada y nº de viajes; ¿qué líneas son circulares (extremos < 500 m)?;
  significado aparente de los campos de `trip_id` (p. ej. `4_1017_562_1585_2403_3_001`) y de
  `shape_id` (`1017_1585_2403` ≈ ruta_origen_destino) — **solo informativo**, el sistema no debe
  depender de ese formato. Aplicar a mano (script de lectura) el algoritmo de design §4.3 a todas
  las líneas y listar las que no den exactamente dos sentidos (o uno, si son circulares de un
  solo giro). → `progress/explore_gtfs_feed.md`

> Si el algoritmo de §4.3 produce resultados incoherentes en más de 3 líneas → CP-3.

## Tareas

- [ ] **T-01** — Modelos de red, `parse_gtfs_time` y normalización de nombres.
  - AC: gtfs_import.AC-07, AC-08
  - Ficheros: `domain/models/network.py`, `domain/services/gtfs_time.py`, `tests/unit/test_gtfs_time.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_gtfs_time.py`

- [ ] **T-02** — Cálculo de servicios activos (puro) con tabla de casos (rango, día de la semana,
  excepción 1, excepción 2, solo `calendar_dates`).
  - AC: gtfs_import.AC-14
  - Ficheros: `domain/services/service_calendar.py`, `tests/unit/test_service_calendar.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_service_calendar.py`

- [ ] **T-03** — Estado de vigencia del feed (válido / caduca en N días / caducado) y vigencia
  derivada sin `feed_info`.
  - AC: gtfs_import.AC-19, AC-20
  - Ficheros: `domain/services/feed_validity.py`, `tests/unit/test_feed_validity.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_feed_validity.py`

- [ ] **T-03b** — Derivación de sentidos `derive_directions` (pura) con patrones sintéticos:
  lineal ida/vuelta, variante corta, circular horaria/antihoraria, circular degenerada.
  - AC: gtfs_import.AC-24, AC-25 (incluido el desempate lexicográfico de AC-24)
  - Ficheros: `domain/services/direction_derivation.py`, `tests/unit/test_direction_derivation.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_direction_derivation.py`

- [ ] **T-04** — Script `make_gtfs_mini.py` y fixture `gtfs_mini` (líneas 70, 93, 98, C2) con README.
  - AC: gtfs_import.AC-21
  - Ficheros: `backend/scripts/make_gtfs_mini.py`, `backend/tests/fixtures/gtfs_mini/*`
  - Verificación: `du -sh backend/tests/fixtures/gtfs_mini` < 2,5 MB; `head` de cada fichero

- [ ] **T-05** — Lector `CsvGtfsFeedReader` (directorio y zip, UTF-8-sig, validación de ficheros y
  columnas, iteración en streaming).
  - AC: gtfs_import.AC-02, AC-03, AC-04, AC-07
  - Ficheros: `domain/ports/gtfs_import.py`, `adapters/outbound/gtfs/reader.py`, `tests/integration/test_gtfs_reader.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_gtfs_reader.py`

- [ ] **T-06** — Base de datos: motor, PRAGMAs, tablas de red y `create_all`.
  - AC: (soporte de AC-01, AC-06)
  - Ficheros: `adapters/outbound/persistence/db.py`, `adapters/outbound/persistence/network_tables.py`
  - Verificación: `cd backend && uv run pytest tests/integration -k db`

- [ ] **T-07** — Escritor `SqliteGtfsFeedWriter`: versión nueva, inserción por lotes, derivados,
  activación atómica, purga y descarte.
  - AC: gtfs_import.AC-05, AC-06, AC-09, AC-10, AC-11, AC-23, AC-24, AC-28, AC-29
  - Ficheros: `adapters/outbound/persistence/sqlite_network.py`, `tests/integration/test_gtfs_writer.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_gtfs_writer.py`

- [ ] **T-08** — Caso de uso `ImportGtfsFeed` (orquestación, descarte ante error).
  - AC: gtfs_import.AC-01, AC-05
  - Ficheros: `application/import_gtfs_feed.py`, `tests/unit/test_import_gtfs_feed.py` (con fakes)
  - Verificación: `cd backend && uv run pytest tests/unit/test_import_gtfs_feed.py`

- [ ] **T-09** — `SqliteNetworkRepository`: todas las consultas del puerto, incluido el caso de
  madrugada (día de servicio anterior).
  - AC: gtfs_import.AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-27, AC-29
  - Ficheros: `domain/ports/network.py`, `adapters/outbound/persistence/sqlite_network.py`, `tests/integration/test_network_repository.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_network_repository.py`

- [ ] **T-10** — CLI `gtfs import` y `gtfs info [--directions]` (contenedor de dependencias
  inyectable, códigos de salida, advertencias, log `gtfs.feed_expiring` / `gtfs.feed_expired`).
  - AC: gtfs_import.AC-01, AC-02, AC-03, AC-04, AC-18, AC-19, AC-26, AC-28
  - Ficheros: `application/get_feed_info.py`, `adapters/inbound/cli/gtfs.py`, `adapters/inbound/cli/container.py`, `tests/integration/test_cli_gtfs.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_gtfs.py`

- [ ] **T-11** — Prueba de importación del feed real (lenta, manual), registro de tiempo y memoria,
  y salida de `gtfs info --directions` guardada en `progress/impl_gtfs_import.md` para que la
  persona valide los sentidos derivados (CP-6).
  - AC: gtfs_import.AC-22, AC-26
  - Ficheros: `tests/integration/test_gtfs_real_feed.py` (`@pytest.mark.slow`)
  - Verificación: `cd backend && uv run pytest -m slow tests/integration/test_gtfs_real_feed.py` + anotar resultados

- [ ] **T-12** — Documentar las variables nuevas en `.env.example` y verificación completa.
  - AC: todos
  - Verificación: `./init.sh verify`
