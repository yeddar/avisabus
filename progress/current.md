# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-04
**Fase:** Implementación — Bloque 3 (solicitud de parada)
**Feature en curso:** `alert_cancel` v1.0 — `implementing` (rama `feat/alert_cancel`, apilada sobre
`feat/alert_create`, PR #41)

## Último paso
`realtime_events` v1.1: APPROVED (ciclo 1); PR #40 abierta. `alert_create` → `implementing`.

## Siguiente paso
Bloque 3 por orden, cada una con reviewer nuevo y PR contra `develop` sin fusionar:
1. `realtime_events`: APPROVED; PR #40.
2. `alert_create`: APPROVED; PR #41 (apilada sobre la #40).
3. `alert_cancel`.
4. `alert_expiry` (exploración E-01 sobre `stop_508_peak`; T-02 añade `GetStopArrivals.for_stop`, autorizado).
5. `passenger_alert_ui`.
Las ramas se apilan sobre la anterior mientras sus PRs no estén fusionadas.

## Pendiente para specs futuras
- **alert_create:** H-1 un 500 inesperado bajo `/api/v1/alerts` sale sin `Cache-Control: no-store`
  (corregible en `alert_cancel`). H-2 AC-08 dice "contando todas" y el design pone el limitador en el
  caso de uso (no cuentan 400/422). H-3 (CP-4, persona) `docs/architecture.md:81` y `:223` no coinciden
  con el design en la ubicación del limitador y el orden de validaciones. H-4 aserción adaptada de las C2
  recalcula la regla. **→ `alert_expiry`:** `last_seen_at` usa `generated_at` (no `fetched_at` del SAE).
- **realtime_events:** N-01 `progress/impl_realtime_events.md` sigue diciendo v1.0/ciclo 0 con el CP-3
  abierto. N-02 la composición está en `http/app.py` + `container.py`, no en `main.py` (design §2).
  N-03 (arnés) sin timeout por test: 5 regresiones cuelgan la suite (`pytest-timeout`). N-04 las dos
  capas del filtro de logs son redundantes y sin test por separado.
- **passenger_map_view:** N-06 preferencia de movimiento reducido leída al montar. N-07 restauración de
  `panBy` sin test. N-02 elisión valenciana sin i/u semiconsonántica ("de Iaia"). N-04 costuras de
  teselas solo por el PNG simulado. (N-01, N-03 y N-05 resueltos en v1.1/v1.2.)
- **passenger_map_view E-01 → `deployment_rpi` / docs:** no usar `Referrer-Policy: no-referrer` en nginx
  ni cachear teselas de OSM en el service worker; opcional `VITE_MAP_TILE_ATTRIBUTION` (la atribución
  es fija). Alternativas si OSM bloquea: IGN Base (WMTS, CC BY 4.0, plantilla sin verificar), CARTO (clave).
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
- Resueltos: PR #17/#18 (occupancy SP-01; stop_tokens_qr S-01, H-01; sae NB-1, NB-4, NB-6, NB-7);
  PR #29/#33 y ajustes (position_estimation H-01…H-04 de v1.1 y v1.2; passenger_stop_view N-1…N-4,
  N-7, N-8; passenger_map_view N-01, N-03, N-05; harness H-04 en la PR #34).

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno. CP-3 de `realtime_events` resuelto (PR #38, v1.1: AC-11 admite `1001` o `1012`).

## Bloqueos
Ninguno. 
