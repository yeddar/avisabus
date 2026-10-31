# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ninguna (`gtfs_import` en `done`; PR abierta, pendiente de validación de sentidos)

## Último paso
`gtfs_import` v1.2 implementada (T-01…T-12) y aprobada en revisión (ciclo 1,
`progress/review_gtfs_import.md`). Importación del feed real: 4,6 s / 75 MB; 42 líneas × 2
sentidos `derived`, coincidentes con E-01. PR abierta desde `feat/gtfs_import` contra `develop`.

## Siguiente paso
1. **La persona valida los sentidos derivados** (salida de `gtfs info --directions` en
   `progress/impl_gtfs_import.md` §Verificación) y fusiona la PR de `gtfs_import`.
2. Decidir si los huecos de spec S-1…S-3 de la revisión se llevan a una v1.3 (no bloquean).
3. `stop_tokens_qr`, `occupancy_sensor`, `sae_arrivals_source` (requiere red para E-01 y la
   grabación de `stop_508_peak`) y `stop_arrivals_api` (v1.1: E-01 incluye las circulares).
4. En paralelo (fuera de Claude Code): specs del bloque 2 (PR #7).

## Pendiente para specs futuras
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.
- **H-09:** el primer subcomando de CLI que use configuración debe construir `Settings()`.
- **H-11:** en `deployment_rpi`, pasar la configuración con `env_file`/variables de Compose, no `../.env`.
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.
- **gtfs_import S-1:** design §2/§3 sin `FeedInfoSource`/`DirectionReport`; "hoy" = fecha del reloj
  en la zona horaria del feed; `feed_end_date` cuenta como día válido (implementado así).
- **gtfs_import S-2:** desempate del `route_id` con más viajes en AC-09 (implementado: `route_id` menor).
- **gtfs_import S-3:** `direction_id` vacío en algunas filas y `route_id` desconocido en `trips.txt`
  (implementado: error de datos).
- **gtfs_import N-07 → `stop_arrivals_api`:** design §3 solo consulta los días de servicio D y D−1;
  una ventana que cruce la medianoche no incluye las salidas 00:xx del día siguiente.
- **gtfs_import N-07 → `deployment_rpi`:** la BD crece al reimportar (68 → 139 MB) sin `VACUUM`.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
- **Validación de sentidos de `gtfs_import`** (pedida por la persona antes de seguir con el
  bloque 1): salida completa en `progress/impl_gtfs_import.md`.

## Bloqueos
Ninguno.
