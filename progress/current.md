# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ninguna (`project_scaffold` en `done`)

## Último paso
`project_scaffold` implementada y aprobada en revisión (ciclo 1), en la rama
`feat/project_scaffold` (pendiente de PR/merge a `develop`).

## Siguiente paso
1. Merge de `feat/project_scaffold` a `develop`.
2. `gtfs_import`: exploración E-01 sobre `data/gtfs/emt/` (validar la derivación de sentidos),
   implementación y revisión. La persona valida la salida de `gtfs info --directions`.
3. `stop_tokens_qr`, `occupancy_sensor`, `sae_arrivals_source` (requiere red para E-01 y la
   grabación de la sesión `stop_508_peak`) y `stop_arrivals_api`.
4. En paralelo (fuera de Claude Code): specs del bloque 2.

## Decisiones pendientes de la persona (hallazgos de `progress/review_project_scaffold.md`)
- H-02: añadir `include_external_packages = True` al extracto de `.importlinter` en
  `specs/project_scaffold/design.md` §4 (el código ya lo lleva; es imprescindible para AC-03).
- H-03: ubicación del `.env` — `Settings` lo busca en el directorio de trabajo (`backend/`) pero
  `./init.sh setup` lo copia a la raíz. Decidir (CP-3 o en `deployment_rpi`).
- H-01: riesgo futuro de privacidad — Uvicorn registra la traza de excepciones no controladas;
  cubrirlo en la spec de la primera feature que maneje identificadores.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno formal (ver "Decisiones pendientes").

## Bloqueos
Ninguno.
