# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `gtfs_import` — `spec_blocked` (CP-3 tras E-01)

## Último paso
PR #6 (`project_scaffold` v1.1) fusionada. `gtfs_import`: rama `feat/gtfs_import`, exploración
E-01 completada → `progress/explore_gtfs_feed.md` (scripts en `progress/explore_gtfs_feed_samples/`).
§4.3 da exactamente 2 sentidos en las 42 líneas con viajes, pero ninguna es circular (< 500 m) →
la verificación de integración de AC-25 (C2) es incumplible → CP-3.

## Siguiente paso
1. **La persona decide el CP-3 de `gtfs_import`** (ver "Checkpoints pendientes").
2. spec-writer corrige `specs/gtfs_import/` (v1.1) → CP-1 → implementación y revisión.
3. `stop_tokens_qr`, `occupancy_sensor`, `sae_arrivals_source` (requiere red para E-01 y la
   grabación de `stop_508_peak`) y `stop_arrivals_api`.
4. En paralelo (fuera de Claude Code): specs del bloque 2.

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
- **CP-3 · gtfs_import** — decisiones (detalle en `progress/explore_gtfs_feed.md` §Impacto/§Recomendación):
  1. Circulares: opción A (mantener §4.3; AC-25 solo unit; AC-24 integration "C2 da dos sentidos
     con dos `route_id` cada uno"; nota sobre los medios bucles de EMT) u opción B (sentido = giro).
  2. ¿Cada sentido guarda todas sus formas (`line_direction_shape`) o solo la del patrón principal?
  3. Solo se crean líneas con ≥ 1 viaje (42, no 46).
  4. Recortar espacios en `trip_headsign` como AC-07.
  5. Añadir la línea 98 a `gtfs_mini` (parada 2070, variante corta real; ~1,40 MB).

## Bloqueos
- `gtfs_import.AC-25`: la verificación de integración con C2 es incumplible con el feed real (C1/C2/C3
  vienen partidas en medios bucles; extremos a ≥ 1 382 m, así que la rama circular nunca se activa).
