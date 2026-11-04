# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-04
**Fase:** Cierre del Bloque 2 (CP-6 aprobado) — ajustes previos al bloque 3
**Feature en curso:** `passenger_map_view` v1.2 (T-08) — siguiente. `passenger_stop_view` v1.3: `done`, PR abierta.

## Último paso
CP-6 del bloque 2 aprobado por la persona. PR #32 y PR #33 (cierre del bloque 2: `passenger_stop_view`
v1.3, `passenger_map_view` v1.2, `position_estimation` v1.3) fusionadas.

## Siguiente paso
1. `passenger_stop_view` T-13 (H-04): APPROVED; PR abierta.
2. `passenger_map_view` T-08 (insignia sin posición, quitar `waitForTimeout`) → reviewer nuevo → PR.
3. `position_estimation` T-10 (tests de la segunda parada y del `shape_id` registrado) → reviewer → PR.
4. Avisar a la persona: el spec-writer redactará las specs del bloque 3.

## Pendiente para specs futuras
- **CP-4 (persona):** `docs/verification.md:26`, fila "Build": ahora el paso de verify es
  `npm run test:bundle` (build + presupuesto), no `npm run build`.
- **passenger_stop_view v1.3:** N-1 la regex del test del arnés (`bundle-budget.test.ts:133-135`) no
  está anclada (no detecta el paso dentro de `if $e2e`). N-2 la fila AC-21 de `design.md:201` conserva
  el texto v1.0 ("si no existe `dist/`, se omite").
- **Harness (H-04 de la revisión de `position_estimation` v1.2):** `frontend/src/__tests__/bundle-budget.test.ts`
  lee `frontend/dist/`, pero `init.sh` ejecuta los tests antes del build: con un `dist/` antiguo,
  `./init.sh verify` (sin `--e2e`) puede dar falso rojo o falso verde. Origen: `passenger_map_view` T-06
  (patrón de `passenger_stop_view` T-09).
- **position_estimation v1.2:** H-01 añadir `logger: Logger` a la firma de `GetVehiclePosition` en el
  design §3 (D-19). H-02 falta un test con la segunda parada como objetivo (el mutante `k <= 1`
  sobrevive). H-03 AC-11 no dice qué `shape_id` registrar; la respuesta conserva `vehicle` con `NO_VEHICLE`.
- **passenger_map_view:** N-01 resuelto en ciclo 2 (design §3 `aria-describedby="summary-id"` frente a §4
  `map.regionDescription` sigue por alinear). N-05 `waitForTimeout(400)` en `e2e/map-view.spec.ts:422`
  (sobra). N-06 preferencia de movimiento reducido leída al montar. N-07 restauración de `panBy` sin test. N-02 elisión valenciana sin i/u
  semiconsonántica ("de Iaia"). N-03 → CP-6: insignia "Posición estimada" junto a "Posición no
  disponible…" en NO_ARRIVAL (cumple AC-05 "siempre"). N-04 costuras de teselas solo por el PNG simulado.
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
Ninguno. CP-6 del bloque 2 aprobado (2026-11-04).

## Bloqueos
Ninguno. 
