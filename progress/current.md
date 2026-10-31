# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ninguna (specs del bloque 1 aprobadas)

## Último paso
Specs del bloque 1 aprobadas por la persona (CP-1) el 2026-10-31.

## Siguiente paso
1. Implementar `project_scaffold` (sin exploración) → revisión.
2. `gtfs_import`: exploración E-01 sobre `data/gtfs/emt/` (validar la derivación de sentidos),
   implementación y revisión. La persona valida la salida de `gtfs info --directions`.
3. `stop_tokens_qr`, `occupancy_sensor`, `sae_arrivals_source` (requiere red para E-01 y la
   grabación de la sesión `stop_508_peak`) y `stop_arrivals_api`.
4. En paralelo (fuera de Claude Code): specs del bloque 2.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.

## Checkpoints pendientes
Ninguno.

## Bloqueos
Ninguno.
