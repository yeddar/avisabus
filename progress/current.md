# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-02
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ajustes de cierre del bloque 1 (rama `fix/bloque-1-ajustes`) — `done`, PR abierta
(sin fusionar). Siguiente: `stop_arrivals_api` v1.3.

## Último paso
Ajustes de cierre del bloque 1 en `fix/bloque-1-ajustes`: `stop_tokens_qr` v1.2 (T-08/T-09),
`sae_arrivals_source` v1.2 (T-11…T-13), `occupancy_sensor` v1.1 (T-07/T-08). Revisión ciclo 1 de
estas versiones: **APPROVED** las tres, sin bloqueantes. `done`; PR contra `develop` abierta.

## Siguiente paso
1. La persona revisa y fusiona la PR de `fix/bloque-1-ajustes`.
2. Tras la fusión: `stop_arrivals_api` (v1.3), rama propia, E-01 (destinos del SAE frente a
   headsigns del GTFS, incluidas circulares) y **parar** para revisar la exploración con la persona.
3. Fin del bloque 1 (CP-6). T-08b de `sae_arrivals_source` (nocturna) opcional.

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
Ninguno. CP-3 de `sae_arrivals_source` resuelto por la persona (2026-11-02): fuente `QR.php`
(ADR-015), cabecera de parada obligatoria (AC-21), `source_format` en las grabaciones (AC-22),
muestras derivadas para "sin llegadas" y `HH:MM`, grabación nocturna opcional (T-08b). Correo
enviado a EMT pidiendo permiso para `getSAE` y preguntando por una API oficial.

## Bloqueos
Ninguno. 
