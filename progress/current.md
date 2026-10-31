# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Especificación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ninguna (specs del bloque 1 en `spec_draft`)

## Último paso
Documentación global aprobada (`docs/`). Harness creado. Specs de las features 1–6 redactadas
en estado `DRAFT`.

## Siguiente paso
1. La persona revisa y aprueba las specs del bloque 1 (CP-1).
2. Cuando `project_scaffold` esté `spec_approved`: implementarla (sin exploración).
3. Después: exploración E-01 de `gtfs_import` sobre `data/gtfs/emt/` (ya disponible) para
   validar la derivación de sentidos.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.

## Checkpoints pendientes
- **CP-1** · `project_scaffold`, `gtfs_import`, `stop_tokens_qr`, `sae_arrivals_source`,
  `occupancy_sensor`, `stop_arrivals_api`.

## Bloqueos
Ninguno.
