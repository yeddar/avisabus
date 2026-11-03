# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-02
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `stop_arrivals_api` v1.3 — `exploring` (rama `feat/stop_arrivals_api`)

## Último paso
PR #18 fusionada. `stop_arrivals_api` en `exploring`: E-01 y E-02 completadas
(`progress/explore_destinations.md`, muestras nocturnas en `progress/explore_destinations_samples/`,
22 consultas al SAE). Resolución de sentido 99,2 % de las llegadas reales (≈ 95,5 % estimado en toda
la red; suelo 91,6 %) → no salta el umbral de CP-3 del 90 %.

## Siguiente paso
1. **La persona revisa la exploración** (pedido explícito) y decide los puntos de
   "Checkpoints pendientes". Después: implementer → reviewer → PR. Fin del bloque 1 (CP-6).
2. E-03 hecha (cabeceras e intermedias de C1/C2 de día). La persona prepara la PR de specs con las
   decisiones del CP-3; **no lanzar el implementer** hasta que esté fusionada.
3. T-08b de `sae_arrivals_source` (nocturna): parcialmente cubierta por las muestras de E-01 de
   `stop_arrivals_api` (`night_20261102/`).

## Pendiente para specs futuras
- **stop_tokens_qr O-01:** `sae fetch|record` ya no emiten `security.dev_stop_token_secret` (no usan
  `build_cli_container`); AC-05 dice "al ejecutar la CLI" sin matizar → precisar en la spec.
- **stop_tokens_qr O-02:** `test_main_stop_token.py` importa `avisabus.main` en un subproceso sin
  bloqueo de sockets; fijar `AVISABUS_ARRIVALS_SOURCE=replay` lo blindaría.
- **stop_tokens_qr S-02, S-03, H-03:** `execute` síncrono frente a conventions §3; `--stop` repetido
  e `index.csv` no especificados; traza de Typer con secreto inválido.
- **occupancy_sensor NB-1 (v1.1):** ningún test comprueba que `main.py` pase
  `settings.occupancy_thresholds()` al sensor → cubrirlo en `test_main_composition.py`.
- **occupancy_sensor NB-2 (v1.1):** reforzar el barrido Hypothesis con `@example(4, 0.25, 0.50)`.
- **occupancy_sensor SP-02:** design §3 escribe `progress(trip_stop_times, at)` sin día de servicio ni
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
Ninguno. CP-3 de `stop_arrivals_api` resuelto por la persona (2026-11-03), opción (c) para C1:
spec v1.4 (sentido que sale, overrides por headsign, umbral 0,2, alias revisados, emparejamiento
óptimo con tolerancia de 10 min, `sae_destination`, duplicados). Se reabren `sae_arrivals_source`
v1.3 (`HH:MM:SS`, entradas sin tiempo, muestra nocturna real) y `occupancy_sensor` v1.2 (test de
composición). `stop_tokens_qr` v1.3: solo redacción de AC-05.

## Bloqueos
Ninguno. 
