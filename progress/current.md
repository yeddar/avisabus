# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `gtfs_import` — `spec_approved` v1.1 (CP-3 resuelto)

## Último paso
PR #6 (`project_scaffold` v1.1) fusionada. `gtfs_import`: rama `feat/gtfs_import`, exploración
E-01 completada → `progress/explore_gtfs_feed.md` (scripts en `progress/explore_gtfs_feed_samples/`).
§4.3 da exactamente 2 sentidos en las 42 líneas con viajes, pero ninguna es circular (< 500 m) →
la verificación de integración de AC-25 (C2) es incumplible → CP-3.

## Siguiente paso
1. `gtfs_import` v1.1: implementar (E-01 ya hecha, no repetir) → revisión.
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
Ninguno. CP-3 de `gtfs_import` resuelto por la persona (2026-10-31): opción A para circulares,
todas las formas por sentido (AC-29), solo líneas con viajes (AC-28), recorte de headsigns
(AC-07) y línea 98 en `gtfs_mini` → spec v1.1 aprobada.

## Bloqueos
Ninguno.
