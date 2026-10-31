# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `occupancy_sensor` (`implementing`); `stop_tokens_qr` en `spec_blocked` (rama `feat/stop_tokens_qr`)

## Último paso
PR #10 y #11 fusionadas; la persona validó los sentidos de `gtfs_import`. `stop_tokens_qr`:
T-01…T-03 hechas, detenida en T-04 por CP-3 (B-01 fuente PNG, B-02 nivel QR), ya decidido por la
persona; spec v1.1 en PR aparte. Estado detallado en la rama `feat/stop_tokens_qr`. Empieza
`occupancy_sensor` en `feat/occupancy_sensor`.

## Siguiente paso
1. `occupancy_sensor` → reviewer → PR contra `develop` (sin fusionar).
2. `stop_tokens_qr`: cuando la persona fusione la spec v1.1 → rebase de `feat/stop_tokens_qr`
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
