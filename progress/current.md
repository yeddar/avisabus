# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-03
**Fase:** Implementación — Bloque 2
**Feature en curso:** `passenger_map_view` v1.0 — `spec_blocked` (CP-3 en AC-04); T-01 hecha

## Último paso
PR #24 (CP-4, `passenger_stop_view` v1.1 spec, `frontend_i18n` v1.1) y PR #28 (T-11) fusionadas.
`passenger_map_view`: E-01 completada (`progress/explore_map.md`): react-leaflet 5.0.0 + leaflet ^1.9.4
compatibles (StrictMode sin errores; Leaflet en fragmento diferido de ~45 KB gzip); la demo cumple la
política de teselas de OSM → sin CP-3. → `implementing`.
Incidencia: el explorer envió por error el correo de contacto de la persona en el User-Agent de una
petición `HEAD` a `tile.openstreetmap.org` (anotado en el informe, sin el correo).

## Siguiente paso
1. `passenger_map_view`: **la persona decide el CP-3 (B-01, B-02) y O-1…O-4** → corrección de spec →
   implementer desde T-02 → reviewer nuevo → PR sin fusionar.
2. **Cuando la #29 esté fusionada** (`passenger_stop_view` v1.2: N-7/N-8; `position_estimation` v1.2:
   H-01/H-02): `passenger_stop_view` T-12 y `position_estimation` T-09, cada una con revisión nueva y
   PR propia.
3. CP-6 del bloque 2: textos (tablas es/ca en `progress/impl_passenger_stop_view.md`), anuncios con
   lector de pantalla, foco tras acciones manuales.

## Pendiente para specs futuras
- **passenger_map_view E-01 → `deployment_rpi` / docs:** no usar `Referrer-Policy: no-referrer` en nginx
  ni cachear teselas de OSM en el service worker; opcional `VITE_MAP_TILE_ATTRIBUTION` (la atribución
  es fija). Alternativas si OSM bloquea: IGN Base (WMTS, CC BY 4.0, plantilla sin verificar), CARTO (clave).
- **position_estimation (H-01, H-02, H-04 → spec-writer en la próxima revisión; H-03 → `nfr_validation`) H-01 (spec):** AC-03 y AC-04 se solapan si la parada objetivo es la primera del
  viaje (implementado: `AT_STOP`; no ocurre en EMT). H-02: viaje sin `shape_dist_traveled` y con una
  parada ausente del feed activo → 500 en vez de `NO_VEHICLE` (solo si el feed cambia entre consultas).
  H-03 → `nfr_validation`: `shape_stops` 17–24 ms en el peor caso (design: 20 ms; el coste está en leer
  horarios, el índice apenas ayuda). H-04: el test de AC-17 exige que los pares excluidos retrocedan
  (más estricto que la spec). H-05: integración de AC-09/AC-10 usa `estimate_position` como oráculo.
- **passenger_stop_view v1.1 → spec v1.2:** N-7: tras un 404 en una acción manual no hay "Reintentar"
  que enfocar (propuesta: foco al `h1` "Parada no encontrada"). N-8: si "Actualizar" falla y luego un
  refresco automático acierta, desaparece "Reintentar" y el foco cae en `body`. N-10: `Button` sin `ref`
  (dos envoltorios `div`). Siguen abiertos N-5 (repeticiones de estilo) y N-6 (OpenAPI desde
  `create_app(schema_only=True)`). Deuda: `overrides` de `openapi-typescript` con TS 6.
- **passenger_stop_view v1.0 (resueltos N-1…N-4 en v1.1) N-1 (accesibilidad):** si "Actualizar" falla no se anuncia nada y el foco se
  pierde (el botón desaparece); igual al acertar con "Reintentar". N-2: si solo falla la petición de
  la parada, el aviso habla de "las llegadas" y no se recupera solo. N-3: comentario desfasado en
  `shared/device/storage.ts`. N-6: el OpenAPI exportado sale de `create_app(schema_only=True)`, no de
  la app de `main.py`. Deuda: `overrides` de npm para `openapi-typescript` con TS 6 (quitar cuando haya
  versión compatible). Docs (CP-4, persona): conventions §4 (`avisabus.lastStop`); opcional, color EMT
  `#e50000` y ejemplo §5.6 en `docs/design.md`.
- **frontend_i18n N-01 (lo recoge el spec-writer, solo docs):** design §3 desfasado para i18next 26 (AC-05: post-procesador solo en
  desarrollo, `initAsync`) y sin los huecos de `eslint-plugin-i18next` 6.1 (AC-07: `no-restricted-syntax`).
  N-02: `eslint.config.js` importa un módulo interno del plugin. N-03: falso aviso del post-procesador
  con `t(key, { lng })`. N-04 → PWA offline / `deployment_rpi`: el service worker no precachea los
  `woff2` (sin conexión, `system-ui`). Capturas e2e: con `CI=1` o puerto 4173 libre.
- **stop_arrivals_api P-1:** ~~resuelto en la PR #7 (solo docs)~~ · AC-06 dice "superar" el umbral; design §3 dice `≥` (el código sigue el
  design; el único caso real en el límite, 1266 "C. Benlloch", da igual con ambas lecturas).
- **stop_arrivals_api P-2 / O-5:** ~~resuelto en la PR #7 (solo docs)~~ · la verificación de AC-19 cita C1 en integración, pero `gtfs_mini`
  no tiene C1 (cubierto en unitarios con datos reales y en test `slow` con el feed completo).
- **stop_arrivals_api O-1/NB-4:** ~~resuelto en la PR #7 (solo docs)~~ · overrides validados solo al arrancar (sin feed se ignoran; tras
  reimportar no se revalidan). O-2: el formato por headsign no expresa un texto que cubre dos medios
  bucles (`C3|Campanar`). O-3: AC-09 no fija el headsign mostrado con override o sentido que sale.
  O-4: fichero de overrides ilegible no especificado (implementado: `ConfigurationError`).
- **stop_arrivals_api NB-1…NB-3:** similitudes mal anotadas en el impl (1751: 0,333; 229: 0,25);
  `FakeLogger` importado de otro test → `tests/support/`; ruta de overrides relativa a `backend/`
  en `.env.example` (→ `deployment_rpi`).
- **sae_arrivals_source v1.3:** ~~resuelto en la PR #7 (solo docs)~~ · SP-1 design §3 sin `ParseResult.without_time` (D-24); SP-2 design §8
  sigue citando la muestra derivada `HH:MM`. NB-1: `sae fetch` muestra `HH:MM` sin segundos. NB-2: en la
  sesión `night_2026-11-02` la 2312 empieza en el segundo 6. AC-19 (b) sigue con muestra derivada.
- **occupancy_sensor v1.2:** ~~resuelto en la PR #7 (solo docs)~~ · SP-1 (O-02) AC-15 cita "el contenedor de la CLI", que no compone sensor
  ni clasificador → "(si compone alguno)" o quitarlo. NB-1: subproceso sin `pytest-socket` y con
  `SystemClock` (mismo patrón que `test_main_composition.py`).
- **→ `stop_arrivals_api`:** al rebasar, adaptar usos de `derived_clock_time`/`STOP_508_CLOCK_TIME`
  (sustituida por `samples/night_2026-11-02/`).
- **stop_tokens_qr O-01:** `sae fetch|record` ya no emiten `security.dev_stop_token_secret` (no usan
  `build_cli_container`); AC-05 dice "al ejecutar la CLI" sin matizar → precisar en la spec.
- **stop_tokens_qr O-02:** `test_main_stop_token.py` importa `avisabus.main` en un subproceso sin
  bloqueo de sockets; fijar `AVISABUS_ARRIVALS_SOURCE=replay` lo blindaría.
- **stop_tokens_qr S-02, S-03, H-03:** `execute` síncrono frente a conventions §3; `--stop` repetido
  e `index.csv` no especificados; traza de Typer con secreto inválido.
- **occupancy_sensor NB-1 (v1.1):** ningún test comprueba que `main.py` pase
  `settings.occupancy_thresholds()` al sensor → cubrirlo en `test_main_composition.py`.
- **occupancy_sensor NB-2 (v1.1):** reforzar el barrido Hypothesis con `@example(4, 0.25, 0.50)`.
- **occupancy_sensor SP-02:** ~~resuelto en la PR #7 (solo docs)~~ · design §3 escribe `progress(trip_stop_times, at)` sin día de servicio ni
  la regla "mediodía − 12 h" (implementado con `service_date`).
- **occupancy_sensor → `stop_arrivals_api`:** inyección y ciclo de vida del engine/sensor en
  `main.py` (N-01); la vigencia del forzado usa `clock.now()`, no `at` (N-04). N-02
  (`service_day_start` duplicado), N-03 (`--clear` exige línea existente).
- **sae_arrivals_source → `stop_arrivals_api`:** `gtfs_mini` solo cubre la línea 98 de la parada
  2070 (73, 95, 99 sin GTFS; nota en la spec v1.3). Siguen abiertos NB-2 (test de composición no
  avanza el reloj ni comprueba `sae_max_concurrency`), NB-3 (detector de pasos laxo), NB-5 (nombre
  `stop_508_peak`), NB-8 (definir `AVISABUS_SAE_CONTACT` en dev/prod → `deployment_rpi`). O-01 (v1.2):
  llamantes concurrentes comparten la instancia del error (lo pide AC-10).
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
- Resueltos en PR #17 + esta rama: occupancy SP-01; stop_tokens_qr S-01 y H-01;
  sae_arrivals_source NB-1, NB-4, NB-6, NB-7.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
**CP-3 `passenger_map_view` AC-04** (T-01 hecha; T-02…T-07 bloqueadas; detalle en `progress/impl_passenger_map_view.md`):
- **B-01 `NOT_STARTED` "{primera parada}":** `PositionResponse` no la trae y en `NOT_STARTED`
  `next_stop` es la segunda parada. A (recomendada, solo frontend): `firstStop = shape.stops[0]?.name`
  en `buildSummary` y texto si el trazado aún no ha llegado. B: `first_stop` en la API (reabre
  `position_estimation`).
- **B-02 "Llega en {tiempo}" con `CLOCK_TIME`:** propuesta: misma regla que `passenger_stop_view.AC-06`
  ("Llega en N minutos" / "Llega a las HH:MM" / "Está llegando."), con textos es/ca.
- Observaciones (decisiones locales salvo indicación): O-1 altura del mapa 360 px (guía §5.7) frente a
  60/70 dvh del design; O-2 atribución solo dentro del mapa (el pie exigiría tocar `Layout.tsx`); O-3
  color del trazado con `accessibleLineColors(color, 'FFFFFF').bg`; O-4 `shape_id` nulo, trazado 404,
  ruta sin token, `direction_id` no numérico.
PR #29 (specs v1.2 de `passenger_stop_view` y `position_estimation`) pendiente de la persona.

## Bloqueos
Ninguno. 
