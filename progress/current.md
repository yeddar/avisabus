# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `gtfs_import` (siguiente: exploración E-01)

## Último paso
`project_scaffold` v1.1 (T-13, T-14) implementada y aprobada en revisión (ciclo 2). PR abierta
desde `feat/project_scaffold-v1.1` contra `develop`, pendiente de que la fusione la persona.
Rama remota `main` borrada.

## Siguiente paso
1. La persona fusiona la PR de `project_scaffold` v1.1.
2. `gtfs_import`: rama `feat/gtfs_import` desde `develop` (tras el merge), exploración E-01 sobre
   `data/gtfs/emt/` → **detenerse y enseñar el resumen a la persona** (sentidos derivados).
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
Ninguno.

## Bloqueos
Ninguno.
