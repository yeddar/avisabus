# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `gtfs_import` v1.2 — `implementing` (desde T-04)

## Último paso
PR #9 (spec `gtfs_import` v1.2) fusionada: resuelve B-01 (`gtfs_mini` con `--date 2026-11-09`,
< 2,5 MB; `gtfs import` sin `--yes`). `feat/gtfs_import` rebasada sobre `develop`; T-01…T-03b
ya hechas. Implementación reanudada desde T-04.

## Siguiente paso
1. `gtfs_import`: implementer desde T-04 (sin rehacer T-01…T-03b) → reviewer nuevo → PR contra
   `develop` (sin fusionar) → **detenerse y enseñar a la persona la salida de
   `gtfs info --directions`** antes de seguir con el bloque 1.
2. `stop_tokens_qr`, `occupancy_sensor`, `sae_arrivals_source` (requiere red para E-01 y la
   grabación de `stop_508_peak`) y `stop_arrivals_api` (v1.1: E-01 incluye las circulares).
3. En paralelo (fuera de Claude Code): specs del bloque 2 (PR #7).

## Pendiente para specs futuras
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.
- **H-09:** el primer subcomando de CLI que use configuración debe construir `Settings()`.
- **H-11:** en `deployment_rpi`, pasar la configuración con `env_file`/variables de Compose, no `../.env`.
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno. CP-3 B-01 de `gtfs_import` resuelto por la persona (spec v1.2, PR #9).

## Bloqueos
Ninguno. Nota para T-06: `sqlalchemy>=2` no está aún en las dependencias del backend.
