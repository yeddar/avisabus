# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `stop_tokens_qr` (reanudación desde T-04 en su rama); `occupancy_sensor` en `done` (PR abierta)

## Último paso
PR #10 y #11 fusionadas; la persona validó los sentidos de `gtfs_import`. `stop_tokens_qr`:
T-01…T-03 hechas, detenida en T-04 por CP-3 (B-01 fuente PNG, B-02 nivel QR), ya decidido por la
persona; spec v1.1 en PR aparte. Estado detallado en la rama `feat/stop_tokens_qr`. `occupancy_sensor` implementada y
aprobada en revisión (ciclo 1, `progress/review_occupancy_sensor.md`); PR abierta contra `develop`.
Spec `stop_tokens_qr` v1.1 fusionada (PR #12).

## Siguiente paso
1. `stop_tokens_qr`: spec v1.1 fusionada (PR #12) → rebase de `feat/stop_tokens_qr`
   sobre `develop` → reanudar desde T-04 → reviewer → PR (sin fusionar).
3. `sae_arrivals_source`: **preguntar a la persona antes de empezar E-01** (requiere red y la
   grabación de 15 min en la parada 508 en hora punta, `stop_508_peak`).
4. `stop_arrivals_api` (v1.2).
5. En paralelo (fuera de Claude Code): specs del bloque 2 (PR #7).

## Pendiente para specs futuras
- **Bloque 4 (`driver_session`/`driver_ui`):** en C2 y C3 cada sentido agrupa dos medios bucles
  con destinos distintos; al elegir línea y sentido, el conductor debe ver **todos** los destinos del
  sentido (no solo el principal), y la comprobación de "fuera de recorrido" debe usar
  `shapes_for_direction` (todas las formas).
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.
- **H-09:** el primer subcomando de CLI que use configuración debe construir `Settings()`.
- **H-11:** en `deployment_rpi`, pasar la configuración con `env_file`/variables de Compose, no `../.env`.
- **occupancy_sensor SP-01 (O-01):** AC-11 choca con las proporciones fijas de forzado (0,20/0,65/0,95)
  si los umbrales no son los de por defecto (p. ej. `full = 0,99` → FULL forzado = MEDIUM). Salidas:
  (c) limitar AC-11 a umbrales por defecto, (b) acotar umbrales en AC-03, (a) derivar `r` de los umbrales.
- **occupancy_sensor SP-02:** design §3 escribe `progress(trip_stop_times, at)` sin día de servicio ni
  la regla "mediodía − 12 h" (implementado con `service_date`).
- **occupancy_sensor → `stop_arrivals_api`:** definir inyección y ciclo de vida del engine/sensor
  expuestos en `main.py` (N-01); la vigencia del forzado usa `clock.now()`, no `at` (N-04).
- occupancy_sensor N-02 (`service_day_start` duplicado), N-03 (`--clear` exige línea existente).
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.
- **gtfs_import N-07 → `deployment_rpi`:** la BD crece al reimportar (68 → 139 MB) sin `VACUUM`.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno pendiente de decisión. (Sentidos de `gtfs_import` validados; CP-3 de `stop_tokens_qr`
decidido, a la espera de la spec v1.1.)

## Bloqueos
- `stop_tokens_qr` en `spec_blocked` hasta que se fusione su spec v1.1.
