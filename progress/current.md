# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ninguna (`project_scaffold` en `done`)

## Último paso
`project_scaffold` v1.0 implementada y aprobada en revisión (ciclo 1), PR #3. La persona decidió
sobre los hallazgos: H-02 y H-03 (opción a: `.env` único en la raíz) → spec **v1.1** (AC-23,
T-13, T-14) en `spec_draft`; H-01 → regla en `docs/conventions.md` y criterio en el bloque 3;
H-04 a H-08 descartados por ahora.

## Siguiente paso
1. La persona fusiona la PR #3 (`feat/project_scaffold`) y aprueba la spec v1.1 (CP-1).
2. `project_scaffold` v1.1: implementar **solo T-13 y T-14** → revisión (ciclo nuevo).
3. `gtfs_import`: exploración E-01 sobre `data/gtfs/emt/`, implementación y revisión. La persona
   valida la salida de `gtfs info --directions`.
4. `stop_tokens_qr`, `occupancy_sensor`, `sae_arrivals_source` (requiere red para E-01 y la
   grabación de `stop_508_peak`) y `stop_arrivals_api`.
5. En paralelo (fuera de Claude Code): specs del bloque 2.

## Pendiente para specs futuras
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
- **CP-1** · `project_scaffold` v1.1.

## Bloqueos
Ninguno.
