# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-09
**Fase:** Cierre del Bloque 3 (CP-6 aprobado) — ajustes previos al bloque 4
**Feature en curso:** `realtime_events` v1.2 — `implementing` (solo T-06, `pytest-timeout`), rama
`feat/realtime_events-v1.2`

## Último paso
Bloque 3 fusionado (PR #40…#44). PR #45 (cierre del bloque 3, CP-6) y PR #46 (specs del bloque 4, CP-1)
fusionadas.

## Siguiente paso
Cada una con reviewer nuevo y PR contra `develop` sin fusionar:
1. `realtime_events` T-06 (`pytest-timeout`, primero).
2. `passenger_alert_ui` T-09.
3. Bloque 4 por orden: `driver_codes_cli`, `driver_session` (T-02 amplía la red: `list_lines`,
   `departures`; autorizado), `driver_demand` (T-02 amplía el repositorio de avisos; autorizado),
   `driver_ui`, `driver_gps_simulator`.

## Pendiente para specs futuras
- **passenger_alert_ui:** huecos de test (código correcto): H-01 ninguna llegada con `can_alert=false` y
  vehículo y sentido (`ArrivalRow.tsx:113`); H-02 el test de AC-08 no comprueba el filtro por parada
  (`StopPage.alerts.test.tsx:111`); H-03 solicitud cuyo viaje solo aparece fuera de red. H-04 `shared/`
  importa el validador de la feature. Para la persona/spec: H-05 foco si llega `alert.registered` con el
  diálogo abierto (cae en `body`); H-06 429 sin `Retry-After` (implementado: 10 min); H-07 título del
  diálogo con headsign GTFS frente a design §7 (texto del SAE); H-08 "Ver en el mapa" en dos líneas en
  móvil; H-09 pista de scroll en el diálogo en Pixel. D-1 recoger `GET` en `apiSend` (design §3).
- **alert_expiry E-01:** ventana de 2 min confirmada (0 prematuros con 1–3 min; 4/6 pasos seguros).
  AC-02 debe ser inclusivo (paso de la 70 con exactamente 120 s). AC-11 (a) no comprueba nada tal como
  está escrita → propuesta de reformulación (o aserción extra en T-05). LIM-02 (docs): el emparejamiento
  puede trasladar un viaje al autobús siguiente sin que desaparezca (93 a ~290 s) y el aviso caduca
  ~490 s tarde; en el bloque 4 llegaría al conductor equivocado.
- **alert_expiry (revisión):** con ventana de 4 min el test de T-05 (línea 93) sigue en verde: el paso
  prematuro de E-01 es de la línea 70 (`…_071`, c70) y solo con aviso recreado; proteger la ventana con
  la sesión real exigiría ampliar AC-11 con la línea 70 (decisión de la persona). NB-3 `WatchPassages`
  recibe `Clock` sin leerlo; NB-4 la ventana no se acota a 1–3 min (indicarlo en `.env.example`); NB-5
  `receive_json_soon` usa API privada de Starlette; NB-6 `alert.trip_lost` en cada ciclo (debug).
- **alert_cancel:** H-1 `no-store` en todos los 500 (`errors.py`), aceptado; anotar en docs como
  comportamiento transversal (persona). H-2 (arnés) `test_alerts_cancel_api.py:159-160` `receive_json()`
  sin límite: con el evento roto se cuelga (sin `pytest-timeout`; ver N-03 de `realtime_events`).
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
Ninguno. CP-6 del bloque 3 aprobado; CP-1 del bloque 4 aprobado (PR #45 y #46).

## Bloqueos
Ninguno. 
