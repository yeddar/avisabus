# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-11
**Fase:** Implementación — Bloque 4 (conductor)
**Feature en curso:** `driver_gps_simulator` v1.0 — `implementing` (rama `feat/driver_gps_simulator`, apilada sobre `feat/driver_ui`, PR #57, y esta sobre la #56)

## Último paso
`driver_ui` v1.1: revisión ciclo 2 APPROVED; PR #57 contra `develop` (apilada sobre la #56), sin fusionar.

## Siguiente paso
1. `driver_gps_simulator`, revisión nueva y PR.
Después, CP-6 del bloque 4 (persona). Orden de fusión: #56, #57 y la de `driver_gps_simulator`.

## Pendiente para specs futuras
- **driver_ui v1.1:** P-05 (CP-4, persona) el permiso de ubicación se pide ya en el primer selector (AC-04/AC-09 v1.1)
  y CU-08 lo pone en el paso 4, tras elegir salida: A (recomendada) actualizar CU-08; B limitar la v1.1 a la siguiente
  salida. P-02 estado en cabecera (§5.9) sin texto; decidir en CP-6. P-03 plurales fijos ("Esperan 1 personas"). P-04
  textos sin definir (salidas vacías, errores). N-10 una vista `service: null` tardía podría contar como la primera de la
  salida y hacer sonar el tono por solicitudes previas (no reproducido). N-11 `useDriverShift.ts` no está en design §1.
  N-01…N-09 en `progress/review_driver_ui.md`. Valenciano sin revisión de persona hablante y tablet real parada → CP-6.
- **driver_session v1.3:** N-10 (CP-4, persona) `docs/architecture.md:119` sigue con `last_position_at`. N-11 design §2
  (`:61`) declara aún `last_position_at` "renombrado a `last_fix_at`". `.env.example:158-161` describe aún la v1.2
  ("sin recibir posición"). Siguen N-01, N-03…N-08 de la v1.2.
- **driver_demand v1.0:** N-01 tests y `http/access_log.py:9` citan AC-12 para la IP; la regla es `driver_session.AC-15`.
  N-02 (spec) salida que desaparece de la red da `service = null`, sin contemplar en ninguna spec. N-03 sin test de
  que la suscripción de `/ws/driver` ocurre antes de la vista inicial (`ws/driver.py:111`). N-04 AC-11 con `FakeClock`:
  latencia real → `nfr_validation`. N-05 (spec) AC-09 no precisa si `distance_m` cuenta (hoy, refresco de 15 s). N-06
  carrera acotada en `watch_passages.py:73,84` (se corrige en ≤ 15 s). N-07 `ws/driver.py` usa privados de
  `ws/passenger.py`; proponer `ws/protocol.py`. N-08 (persona) la IP sigue en `uvicorn.error` para `/ws/passenger`,
  igual que `/alerts`. Reflejar en `design.md` las desviaciones juzgadas y en `tasks.md` el filtro de `http/access_log.py`.
- **driver_session v1.2 (decisión de la persona):** N-05 el umbral de 150 m solo se cumple con la semilla del test:
  con semillas 1–20 a σ 10 m, 5/20 correlado (hasta 422 m por detrás, giros en U, se recupera solo) y 1/20
  independiente; con paradas simuladas, 12/20 y 19/20. Limitación aceptada por el reviewer; volver a medir con
  `driver_gps_simulator`. N-06 retirar "(la que fijó el progreso)" del design. Abiertos N-01, N-03, N-04, N-07…N-09.
- **position_estimation v1.4:** N-01 fixtures del frontend con distancias infladas (3403 m frente a ~1242 m
  reales; las capturas `map-*` muestran "3,4 km") → regenerar antes del CP-6 del bloque 4. N-02 texto residual
  en requirements (`:13-14`, AC-05). N-03 aclarar AC-06 (la 1282 difiere 339 m de la proyección). N-04/N-05
  huecos de test (horarios parciales; valores iguales del feed, D-25). N-06 `_stop_distances` es privada:
  `driver_session` no debe duplicar esa lógica.
- **driver_codes_cli:** N-07 que la traza de Typer no muestre variables locales depende del valor por
  defecto (`show_locals`): con `True` imprimiría `plain_code` → fijarlo a `False` y testearlo. N-08 un
  `OperationalError` sale como traza (sin valores). N-09 `hide_parameters` no oculta filas con
  `sqlalchemy.engine` en DEBUG (nada lo activa). N-03/N-04 abiertos. N-06 (spec): design §2 cita
  `IntegrityError` y T-01 no lista `errors.py`. Etiqueta solo de espacios aceptada por el literal de AC-02.
- **passenger_alert_ui v1.1:** H-10 la cláusula de AC-06 "sin `Retry-After`, N = 10" no tiene test que la
  fije. H-11 hueco de test (V07). H-12 (persona, siguiente CP): `alerts.snapshot` con el diálogo abierto
  hace caer el foco en `body` (también al recargar con solicitud activa); redacción propuesta en
  `progress/review_passenger_alert_ui.md`. H-13 añadir `registerDialog` al design §3.
- **realtime_events v1.2:** NB-1 si un endpoint bloquea el bucle de forma síncrona la suite sigue colgada
  (valorar `timeout_method = "thread"`). NB-2 `test_gtfs_real_feed.py:34` admite 120 s (AC-22 de
  `gtfs_import`) pero el límite general corta a 30 s (hoy 5,3 s). NB-3 cinco `timeout=60` de subprocesos ya
  no se alcanzan. NB-4 T-06 dice "con tiempo máximo" y el límite es en vueltas del bucle.
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
Ninguno. CP-3 de `driver_ui` (P-01) resuelto en la PR #55.

## Bloqueos
Ninguno.
