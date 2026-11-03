# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-03
**Fase:** Implementación — Bloque 2
**Feature en curso:** `frontend_i18n` v1.0 — `implementing` (rama `feat/frontend_i18n`)

## Último paso
PR #21 (`stop_arrivals_api`) fusionada: bloque 1 completo (6/6). PR #7 fusionada: specs del bloque 2
aprobadas (CP-1) y guía visual `docs/design.md`; la persona da paso al bloque 2 (CP-6 superado).
`frontend_i18n` (sin exploración) → `implementing`.

## Siguiente paso
1. Implementer (T-01…T-08) → reviewer nuevo → `done` → PR contra `develop` sin fusionar.
   Las features de frontend siguen `docs/design.md`; los AC de conformidad visual (revisión) se
   comprueban con capturas de las pruebas e2e.
2. Siguientes del bloque 2: `position_estimation`, `passenger_stop_view`, `passenger_map_view`.

## Pendiente para specs futuras
- **stop_arrivals_api P-1:** ~~resuelto en la PR #7 (solo docs)~~ · AC-06 dice "superar" el umbral; design §3 dice `≥` (el código sigue el
  design; el único caso real en el límite, 1266 "C. Benlloch", da igual con ambas lecturas).
- **stop_arrivals_api P-2 / O-5:** ~~resuelto en la PR #7 (solo docs)~~ · la verificación de AC-19 cita C1 en integración, pero `gtfs_mini`
  no tiene C1 (cubierto en unitarios con datos reales y en test `slow` con el feed completo).
- **stop_arrivals_api O-1/NB-4:** ~~resuelto en la PR #7 (solo docs)~~ · overrides validados solo al arrancar (sin feed se ignoran; tras
  reimportar no se revalidan). O-2: el formato por headsign no expresa un texto que cubre dos medios
  bucles (`C3|Campanar`). O-3: AC-09 no fija el headsign mostrado con override o sentido que sale.
  O-4: fichero de overrides ilegible no especificado (implementado: `ConfigurationError`).
- **stop_arrivals_api NB-1…NB-3:** similitudes mal anotadas en el impl (1751: 0,333; 229: 0,25);
  `FakeLogger` importado de otro test → `tests/support/`; ruta de overrides relativa a `backend/`
  en `.env.example` (→ `deployment_rpi`).
- **sae_arrivals_source v1.3:** ~~resuelto en la PR #7 (solo docs)~~ · SP-1 design §3 sin `ParseResult.without_time` (D-24); SP-2 design §8
  sigue citando la muestra derivada `HH:MM`. NB-1: `sae fetch` muestra `HH:MM` sin segundos. NB-2: en la
  sesión `night_2026-11-02` la 2312 empieza en el segundo 6. AC-19 (b) sigue con muestra derivada.
- **occupancy_sensor v1.2:** ~~resuelto en la PR #7 (solo docs)~~ · SP-1 (O-02) AC-15 cita "el contenedor de la CLI", que no compone sensor
  ni clasificador → "(si compone alguno)" o quitarlo. NB-1: subproceso sin `pytest-socket` y con
  `SystemClock` (mismo patrón que `test_main_composition.py`).
- **→ `stop_arrivals_api`:** al rebasar, adaptar usos de `derived_clock_time`/`STOP_508_CLOCK_TIME`
  (sustituida por `samples/night_2026-11-02/`).
- **stop_tokens_qr O-01:** `sae fetch|record` ya no emiten `security.dev_stop_token_secret` (no usan
  `build_cli_container`); AC-05 dice "al ejecutar la CLI" sin matizar → precisar en la spec.
- **stop_tokens_qr O-02:** `test_main_stop_token.py` importa `avisabus.main` en un subproceso sin
  bloqueo de sockets; fijar `AVISABUS_ARRIVALS_SOURCE=replay` lo blindaría.
- **stop_tokens_qr S-02, S-03, H-03:** `execute` síncrono frente a conventions §3; `--stop` repetido
  e `index.csv` no especificados; traza de Typer con secreto inválido.
- **occupancy_sensor NB-1 (v1.1):** ningún test comprueba que `main.py` pase
  `settings.occupancy_thresholds()` al sensor → cubrirlo en `test_main_composition.py`.
- **occupancy_sensor NB-2 (v1.1):** reforzar el barrido Hypothesis con `@example(4, 0.25, 0.50)`.
- **occupancy_sensor SP-02:** ~~resuelto en la PR #7 (solo docs)~~ · design §3 escribe `progress(trip_stop_times, at)` sin día de servicio ni
  la regla "mediodía − 12 h" (implementado con `service_date`).
- **occupancy_sensor → `stop_arrivals_api`:** inyección y ciclo de vida del engine/sensor en
  `main.py` (N-01); la vigencia del forzado usa `clock.now()`, no `at` (N-04). N-02
  (`service_day_start` duplicado), N-03 (`--clear` exige línea existente).
- **sae_arrivals_source → `stop_arrivals_api`:** `gtfs_mini` solo cubre la línea 98 de la parada
  2070 (73, 95, 99 sin GTFS; nota en la spec v1.3). Siguen abiertos NB-2 (test de composición no
  avanza el reloj ni comprueba `sae_max_concurrency`), NB-3 (detector de pasos laxo), NB-5 (nombre
  `stop_508_peak`), NB-8 (definir `AVISABUS_SAE_CONTACT` en dev/prod → `deployment_rpi`). O-01 (v1.2):
  llamantes concurrentes comparten la instancia del error (lo pide AC-10).
- **Bloque 4 (`driver_session`/`driver_ui`):** en C2 y C3 cada sentido agrupa dos medios bucles
  con destinos distintos; al elegir línea y sentido, el conductor debe ver **todos** los destinos del
  sentido (no solo el principal), y la comprobación de "fuera de recorrido" debe usar
  `shapes_for_direction` (todas las formas).
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.
- **H-09:** el primer subcomando de CLI que use configuración debe construir `Settings()`.
- **H-11:** en `deployment_rpi`, pasar la configuración con `env_file`/variables de Compose, no `../.env`.
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.
- **gtfs_import N-07 → `deployment_rpi`:** la BD crece al reimportar (68 → 139 MB) sin `VACUUM`.
- Resueltos en PR #17 + esta rama: occupancy SP-01; stop_tokens_qr S-01 y H-01;
  sae_arrivals_source NB-1, NB-4, NB-6, NB-7.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno. CP-6 del bloque 1 superado (la persona da paso al bloque 2, 2026-11-03).

## Bloqueos
Ninguno. 
