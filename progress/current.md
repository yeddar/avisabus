# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `stop_tokens_qr` — `spec_blocked` (CP-3 en T-04); `occupancy_sensor` sin empezar

## Último paso
PR #10 (`gtfs_import`) y PR #11 (spec `gtfs_import` v1.3 —documenta S-1…S-3, sin cambios de
código— y `stop_arrivals_api` v1.2 —AC-18/T-05b, cruce de medianoche—) fusionadas. La persona
validó los sentidos derivados. Empieza `stop_tokens_qr` en `feat/stop_tokens_qr`.
`stop_tokens_qr`: T-01…T-03 hechas (c5bc0c0, 89808c2, e30bd75); T-04 codificada según el design
(6c73adb) pero detenida por B-01 (`progress/impl_stop_tokens_qr.md`). T-05…T-07 sin empezar.

## Siguiente paso
1. **La persona decide el CP-3 de `stop_tokens_qr`** (B-01, B-02) → spec-writer → CP-1 → reanudar
   desde T-04 → reviewer → PR contra `develop` (sin fusionar).
2. `occupancy_sensor` (rama `feat/occupancy_sensor` desde `develop`) → reviewer → PR.
3. `sae_arrivals_source`: **preguntar a la persona antes de empezar E-01** (requiere red y la
   grabación de 15 min en la parada 508 en hora punta, `stop_508_peak`).
4. `stop_arrivals_api` (v1.2).
5. En paralelo (fuera de Claude Code): specs del bloque 2 (PR #7).

## Pendiente para specs futuras
- **Bloque 4 (`driver_session`/`driver_ui`):** en C2 y C3 cada sentido agrupa dos medios bucles
  con destinos distintos; al elegir línea y sentido, el conductor debe ver **todos** los destinos del
  sentido (no solo el principal), y la comprobación de "fuera de recorrido" debe usar
  `shapes_for_direction` (todas las formas).
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.
- **H-09:** el primer subcomando de CLI que use configuración debe construir `Settings()`.
- **H-11:** en `deployment_rpi`, pasar la configuración con `env_file`/variables de Compose, no `../.env`.
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.
- **gtfs_import N-07 → `deployment_rpi`:** la BD crece al reimportar (68 → 139 MB) sin `VACUUM`.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
- **CP-3 · stop_tokens_qr B-01** — design §5: la etiqueta PNG usa "la fuente por defecto de Pillow o
  DejaVuSans si está disponible". La fuente por defecto de Pillow 13 (Aileron) no tiene glifos para
  `àèéíòóúçñ…` (comprobado) y DejaVuSans no está en macOS ni en imágenes Docker slim → 620 de
  1 117 nombres de parada saldrían mal ("Val□ncia"); incumple AC-07/AC-09 en PNG (SVG no afectado).
  Propuestas: (rec.) incluir `DejaVuSans.ttf` (~750 KB, licencia libre) en
  `adapters/outbound/qr/fonts/` y usarla siempre + test de cobertura de glifos sobre `gtfs_mini`;
  o lista de fuentes del sistema con fallo explícito + `fonts-dejavu-core` en `deployment_rpi`.
- **CP-3 · stop_tokens_qr B-02 (menor)** — `segno.make(..., error="m")` sube el nivel a Q/H por
  `boost_error=True`; AC-12 exige M. Implementado con `boost_error=False`. Propuesta: que el design
  lo diga explícitamente, o AC-12 "al menos M".

## Bloqueos
- B-01 y B-02 de `stop_tokens_qr` (arriba).
