# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `gtfs_import` v1.1 — `spec_blocked` (CP-3 en T-04, fixture `gtfs_mini`)

## Último paso
PR #8 (spec `gtfs_import` v1.1) fusionada. Implementación en `feat/gtfs_import`: T-01…T-03b hechas
(commits 6257969…8939de8); detenida en T-04 por el bloqueo B-01 (`progress/impl_gtfs_import.md`).
`backend/scripts/make_gtfs_mini.py` (T-04, según design §8) queda sin commit en el árbol.

## Siguiente paso
1. **La persona decide el CP-3 B-01** (ver "Checkpoints pendientes") → spec-writer (v1.2) → CP-1.
2. Reanudar `gtfs_import` desde T-04 (sin rehacer T-01…T-03b) → revisión → PR.
3. `stop_tokens_qr`, `occupancy_sensor`, `sae_arrivals_source` (requiere red para E-01 y la
   grabación de `stop_508_peak`) y `stop_arrivals_api` (v1.1: E-01 incluye las circulares).
4. En paralelo (fuera de Claude Code): specs del bloque 2 (PR #7).

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
- **CP-3 · gtfs_import B-01** — `gtfs_mini` con `--date 2026-11-04` (miércoles + martes) no
  contiene `route_id` 1055 de la 98 (`38_1055_603`/`604`: solo sábado/domingo; 1054 solo L–V,
  confirmado en `calendar.txt`) → AC-24 y AC-29 incumplibles para la 98. Opciones:
  1. (recomendada por el implementer) `--date 2026-11-09` (lunes + domingo), 2,15 MB; subir el
     objetivo de tamaño a < 2,5 MB en design §8 y T-04.
  2. Mantener la fecha y añadir `--extra 98:2026-11-08` al generador (~1,6 MB; describirlo en design).
  3. Reescribir las verificaciones de AC-24/AC-29 (se pierde la variante real en el mismo sentido).
- Aclaración a la vez: design §3 define `gtfs import PATH [--yes]` sin decir qué hace `--yes`.

## Bloqueos
- B-01 (arriba). Nota para T-06: `sqlalchemy>=2` no está aún en las dependencias del backend.
