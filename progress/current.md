# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-02
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ajustes de cierre del bloque 1 (rama `fix/bloque-1-ajustes`): `stop_tokens_qr` v1.2,
`sae_arrivals_source` v1.2, `occupancy_sensor` v1.1 — `implementing`

## Último paso
PR #16 (`sae_arrivals_source`) y PR #17 (specs de ajustes de cierre del bloque 1) fusionadas.
Rama `fix/bloque-1-ajustes`; implementer con las tareas nuevas: `stop_tokens_qr` T-08/T-09,
`sae_arrivals_source` T-11…T-13, `occupancy_sensor` T-07/T-08.

## Siguiente paso
1. Reviewer nuevo de las tres versiones → si APPROVED, `done` y PR contra `develop` (sin fusionar).
2. Tras la fusión: `stop_arrivals_api` (v1.3), rama propia, E-01 (destinos del SAE frente a
   headsigns del GTFS, incluidas circulares) y **parar** para revisar la exploración con la persona.
3. Fin del bloque 1 (CP-6). T-08b de `sae_arrivals_source` (nocturna) opcional.

## Pendiente para specs futuras
- **sae_arrivals_source NB-1 → `stop_arrivals_api`:** la caché negativa relanza la misma instancia
  de excepción y su traza crece con cada acierto (`cache.py:67,76`); usar `with_traceback(None)`.
- **sae_arrivals_source NB-6:** alinear design (`build_arrivals_source` devuelve
  `CachedArrivalsSource`, D-12; `interval_s: null` en sesiones E-01, D-08) y `parser.py` §3.
- **sae_arrivals_source → `stop_arrivals_api`:** `gtfs_mini` solo cubre la línea 98 de la parada
  2070 (73, 95, 99 sin GTFS). NB-2/NB-7 (tests de composición), NB-3 (detector de pasos laxo),
  NB-4 (comando de regeneración del README), NB-5 (nombre `stop_508_peak`), NB-8 (definir
  `AVISABUS_SAE_CONTACT` en dev/prod → `deployment_rpi`).
- **Bloque 4 (`driver_session`/`driver_ui`):** en C2 y C3 cada sentido agrupa dos medios bucles
  con destinos distintos; al elegir línea y sentido, el conductor debe ver **todos** los destinos del
  sentido (no solo el principal), y la comprobación de "fuera de recorrido" debe usar
  `shapes_for_direction` (todas las formas).
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.
- **H-09:** el primer subcomando de CLI que use configuración debe construir `Settings()`.
- **H-11:** en `deployment_rpi`, pasar la configuración con `env_file`/variables de Compose, no `../.env`.
- **stop_tokens_qr H-01:** el aviso `security.dev_stop_token_secret` sale por stdout sin formato JSON
  porque `Settings()` se construye antes de `configure_logging` (`cli/qr.py`, `main.py`); solo dev/test.
- **stop_tokens_qr S-01…S-03:** código de salida de uso incorrecto de la CLI (2 de Click = 2 de AC-10);
  `execute` síncrono sin justificar frente a conventions §3; `--stop` repetido e `index.csv` no
  especificados (implementado: deduplicar; `index.csv` siempre). H-03: traza de Typer con secreto inválido.
- **occupancy_sensor SP-01 (O-01):** AC-11 choca con las proporciones fijas de forzado (0,20/0,65/0,95)
  si los umbrales no son los de por defecto (p. ej. `full = 0,99` → FULL forzado = MEDIUM). Salidas:
  (c) limitar AC-11 a umbrales por defecto, (b) acotar umbrales en AC-03, (a) derivar `r` de los umbrales.
- **occupancy_sensor SP-02:** design §3 escribe `progress(trip_stop_times, at)` sin día de servicio ni
  la regla "mediodía − 12 h" (implementado con `service_date`).
- **occupancy_sensor → `stop_arrivals_api`:** definir inyección y ciclo de vida del engine/sensor
  expuestos en `main.py` (N-01); la vigencia del forzado usa `clock.now()`, no `at` (N-04).
- occupancy_sensor N-02 (`service_day_start` duplicado), N-03 (`--clear` exige línea existente).
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.
- **gtfs_import N-07 → `deployment_rpi`:** la BD crece al reimportar (68 → 139 MB) sin `VACUUM`.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno. CP-3 de `sae_arrivals_source` resuelto por la persona (2026-11-02): fuente `QR.php`
(ADR-015), cabecera de parada obligatoria (AC-21), `source_format` en las grabaciones (AC-22),
muestras derivadas para "sin llegadas" y `HH:MM`, grabación nocturna opcional (T-08b). Correo
enviado a EMT pidiendo permiso para `getSAE` y preguntando por una API oficial.

## Bloqueos
Ninguno. 
