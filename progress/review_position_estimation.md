# Revisión: position_estimation
Ciclo: 1 · Fecha: 2026-11-03 · Agente: reviewer
Spec revisada: `specs/position_estimation/` v1.1 (APPROVED) · Rama: `feat/position_estimation`
(HEAD `7c2b11e`) · Base: `origin/develop` (`7e8a7ff`; el `develop` local está atrasado, por eso
`git diff develop...HEAD` muestra los ficheros de la spec v1.1 traídos con el merge).

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Los 17 AC tienen tests que los verifican de verdad,
`CI=1 ./init.sh verify --e2e` está en verde y las 18 decisiones locales caben en el design v1.1
o cubren huecos menores sin contradecirlo. Quedan 5 observaciones no bloqueantes (una es un
problema de spec menor, para la próxima revisión de la spec).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `tests/unit/test_position_estimator.py::test_between_two_stops_the_bus_is_interpolated_by_time` (6 casos), `::test_two_stops_at_the_same_time_do_not_divide_by_zero`, `::test_uses_the_departure_of_the_previous_stop_and_the_arrival_of_the_next` | OK | Valores esperados calculados a mano (viaje rectilíneo de 5 paradas, 1000 m / 120 s); se cubre `f = 0` con `s_i = s_{i+1}` y el uso de `departure_s[i]` / `arrival_s[i+1]` del paso 5. |
| AC-02 | `test_position_estimator.py::test_a_bus_3_min_late_is_where_the_timetable_puts_it_3_min_earlier`, `::test_an_early_bus_is_ahead_of_the_timetable` | OK | Igualdad exacta de la estimación con +3 min de retraso y de la puntual 3 min antes. |
| AC-03 | `test_position_estimator.py::test_at_or_after_the_scheduled_time_the_bus_is_at_the_stop`, `::test_an_arrival_of_0_minutes_is_at_the_stop`; `tests/unit/test_get_vehicle_position.py::test_an_arrival_of_0_minutes_is_at_the_stop` | OK | El caso "0 min" se verifica de extremo a extremo con el SAE (`arrival_at = fetched_at`, `qrphp_parser.py:162`). |
| AC-04 | `test_position_estimator.py::test_before_the_departure_the_bus_is_at_the_first_stop`, `::test_at_the_departure_the_bus_is_en_route` | OK | Frontera estricta `s < departure_s[0]` (design v1.1 §3 paso 5). |
| AC-05 | `tests/unit/test_geometry.py` (rumbo cardinal y rango 0–360, punto a distancia < 1 m, interpolación en esquina, recorte, puntos repetidos); `test_position_estimator.py::test_coordinates_and_bearing_come_from_the_shape` | OK | Error < 1 m comprobado con haversine contra posiciones construidas independientemente. |
| AC-06 | `test_geometry.py::test_cumulative_distances_*`, `::test_shape_distances_*`, `::test_stops_beside_the_shape_project_onto_their_distance`, `::test_projection_never_goes_back_along_the_trip`, `::test_projection_of_stops_out_of_order_does_not_decrease`; `test_position_estimator.py::test_without_distances_the_shape_and_the_stops_are_measured`, `::test_without_stop_distances_nor_coordinates_it_cannot_estimate`, `::test_stop_coordinates_is_the_eighth_parameter_of_the_design` | OK | Monotonía comprobada en línea circular (última parada = primera) y en paradas desordenadas. Firma v1.1 (octavo parámetro posicional) comprobada. |
| AC-07 | `test_position_estimator.py::test_a_repeated_target_uses_the_occurrence_closest_to_the_arrival`, `::test_the_closest_occurrence_is_chosen_by_the_arrival_not_by_now` | OK | Ambas apariciones de la parada repetida. |
| AC-08 | `test_position_estimator.py::test_distance_stops_away_and_next_stop` (5 casos) + aserciones en AC-03/AC-04/AC-07 | OK | Incluye el caso "exactamente en B" (B queda detrás). |
| AC-09 | `tests/integration/test_position_api.py::test_position_of_the_first_arrival_of_the_line_and_direction`, `::test_the_position_alone_asks_the_sae_once_and_shares_the_cache`; `test_get_vehicle_position.py::test_position_of_the_first_arrival_of_the_line_and_direction`; `tests/integration/test_main_position.py`; `test_network_repository.py::test_trip_shape_id_is_the_shape_of_every_trip` | OK | Contrato completo de la respuesta (`set(body) == RESPONSE_FIELDS`), `headsign` igual al de `GET /stops/{id}`, llegada idéntica a la de la API de llegadas, contador del SAE = 1 (y = 2 tras caducar la caché). Composición en `main.py` comparte `GetStopArrivals`. |
| AC-10 | `test_position_api.py::test_scheduled_arrival_gives_the_position_on_the_timetable`; `test_get_vehicle_position.py::test_scheduled_arrivals_give_the_position_on_the_timetable` | OK | `source = SCHEDULED`, `arrival_at` = hora programada (δ = 0), posición con valor calculado a mano en el unitario. |
| AC-11 | `test_position_api.py::test_without_arrivals_the_status_is_no_arrival` (93 y 70), `::test_an_arrival_without_a_paired_trip_is_no_vehicle`; `test_get_vehicle_position.py` (3 tests AC-11) | OK | `shape_id` representativo = `LineDirection.shape_id`. |
| AC-12 | `test_position_api.py::test_invalid_token_or_unknown_stop_is_the_404_of_the_stops`, `::test_line_and_direction_not_at_the_stop_is_404`; `test_get_vehicle_position.py` (3 tests AC-12) | OK | 404 byte a byte idéntico al de `/stops/{id}/arrivals`, sin peticiones al SAE; token inválido prevalece sobre línea inexistente. |
| AC-13 | `tests/integration/test_shapes_api.py::test_shape_with_its_coordinates_color_and_stops` (3 formas); `test_network_repository.py::test_shape_stops_*`, `::test_shape_line_*`; `test_get_shape.py::test_shape_view_with_coordinates_as_lon_lat` | OK | Esperados leídos de los CSV de `gtfs_mini`, no del repositorio; orden GeoJSON `[lon, lat]`; varios patrones de paradas con feed modificado. |
| AC-14 | `test_shapes_api.py::test_shape_is_cacheable_with_an_etag_of_the_feed_version`, `::test_etag_changes_with_the_feed_version` | OK | `Cache-Control`, `ETag`, `304` sin cuerpo, `ETag` distinto tras reimportar. |
| AC-15 | `test_shapes_api.py::test_unknown_shape_is_404`; `test_get_shape.py::test_unknown_shape_or_shape_without_trips` | OK | `problem+json` con `shape-not-found`, sin `ETag`. |
| AC-16 | `test_shapes_api.py::test_shapes_are_compressed_when_the_client_accepts_gzip`; `test_position_api.py::test_position_responses_are_compressed_only_above_1_kb`; `test_main_position.py` | OK | Comprimido > 1 KB con `Accept-Encoding: gzip`, sin comprimir < 1 KB o con `identity`; `minimum_size=1000` en `main.app`. |
| AC-17 | `tests/integration/test_position_real_session.py` (3 tests) | OK | Ver detalle abajo. |

### Detalle de AC-17 (condición v1.1)

- Recorre los 75 ciclos de `stop_508_peak` cada 20 s con `FakeClock` sobre la API real y la misma
  composición que `main.py`, para (70, 1) y (93, 0) en la 508; 75 peticiones al SAE (una por ciclo).
- **30 m:** todas las posiciones (todas `REALTIME`, comprobado) se miden contra la forma de su
  viaje con una proyección propia del test, independiente de `domain/services/geometry.py`.
- **50 m:** `test_position_real_session.py:178` excluye un par **solo** si
  `after.minutes > before.minutes`; todos los demás (`minutes_{t+1} ≤ minutes_t`) se comprueban.
  Coincide exactamente con AC-17 v1.1 y el design §5. Los pares son observaciones sucesivas del
  mismo `(line, trip_id)`; incluyen pares no consecutivos cuando el viaje desaparece entre medias
  (p. ej. ciclos 58→69). Eso hace la comprobación **más estricta**, no menos: no se excluyen pares
  por otra razón que el aumento de minutos.
- La salida informa del número de pares: "139 pairs checked, 5 excluded because the SAE minutes
  increased". Los 5 excluidos coinciden con la tabla del análisis original de B-01.

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre), salida final "verify: todo en verde", código 0:

- backend: format OK · lint OK · types OK (mypy) · architecture OK (lint-imports) · tests OK
  (969 passed, 6 deselected; cobertura `domain` + `application` 99,39 % ≥ 80 %).
- frontend: format OK · lint OK · types OK · tests OK (35 ficheros, 278 tests) · build OK ·
  e2e + a11y OK (60 passed). El test de desfase del contrato (`openapi.json` / `schema.d.ts`)
  pasa con los ficheros regenerados.
- harness: `feature_list.json` OK · trazabilidad AC→test OK.

Comprobaciones adicionales:

- `git diff origin/develop...HEAD --stat`: 32 ficheros. Código y tests de la feature en
  `backend/`, contrato generado en `frontend/src/shared/api/` y ficheros de progreso y
  `feature_list.json` (orquestador). No cambia nada de `specs/` ni de `docs/` respecto a la base.
- `git diff origin/develop...HEAD -- backend/src | grep datetime.now|time.time|logger|print`:
  sin resultados (no hay reloj real ni logs nuevos).
- `gtfs_import`: las ampliaciones de `SqliteNetworkRepository` (`sqlite_network.py:594-656`) solo
  añaden métodos de lectura y el import de `func`. Ningún método existente cambia. Los 37 tests
  previos de `test_network_repository.py` y los de `test_gtfs_writer.py` /
  `test_import_gtfs_feed.py` siguen en verde: no hay regresión.
- D-08 (rendimiento de `shape_stops`), medido sobre una copia de `data/avisabus.sqlite`
  (94 formas): mediana 7 ms y peor caso 17–24 ms según la ejecución (mejor de 3: 17,4 ms). La
  búsqueda de viajes por `shape_id` cuesta 1,1 ms de media. Ver H-03.

### Encaje de las decisiones locales en el design v1.1

| Decisión | Encaje |
|---|---|
| D-01, D-02 | Design §6 ("implementación concreta de la proyección"). Las utilidades extra (`shape_distances`, `PointOnShape`) no cambian contratos. |
| D-03 | Recogida en el design v1.1 §3. El código (`position_estimator.py:21-30`) usa el octavo parámetro posicional con `None` por defecto y lanza `ValueError` explícito si faltan las coordenadas. |
| D-04 | Coincide con el design v1.1 paso 5 (`s < departure_s[0]`). La precedencia de `AT_STOP` sobre `NOT_STARTED` solo afecta si la parada objetivo es la primera del viaje y `arrival_s[0] ≤ s < departure_s[0]`. Solo cambia la etiqueta: la posición, la distancia, `stops_away` y `next_stop` son idénticas. Ver H-01. |
| D-05, D-06 | Huecos menores sin efecto en el feed de EMT (`arrival = departure`). |
| D-07 | Lectura razonable de "viaje con más viajes de esa forma (empate: trip_id menor)" (literalmente ambigua) como patrón de paradas más frecuente. Probada con un feed modificado. |
| D-08 | Decisión permitida por el design §4. Ver H-03. |
| D-09 | Coherente con el diagrama del design §1 (primero `GetStopArrivals`) y con AC-12 (token inválido indistinguible). |
| D-10 | Extiende el tratamiento "sin viaje → representativo" del design §1 a un viaje sin datos en el feed activo. Ver H-02. |
| D-11, D-12, D-15, D-16 | Dentro del design (§2, §3) y de conventions §3 (errores sin identificadores en el mensaje). |
| D-13 | AC-15: una forma sin viajes no es servible (`ShapeView.line` obligatorio). |
| D-14 | AC-14 + RFC 9110. El `304` lleva `ETag` y `Cache-Control`; los errores llevan `no-store`. |
| D-17 | Sigue el ejemplo JSON del design §3 campo a campo (incluido `vehicle`). |
| D-18 | Ajuste mínimo e inevitable: `test_main_stops.py:43-44` filtra por prefijo `/api/v1/stops` y la nueva ruta entra en ese filtro. No cambia nada más. |

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **H-01 (Problema de spec menor, para la próxima versión; no requiere CP-3 ahora)**:
  `specs/position_estimation/design.md:94` y `requirements.md:52-58`. AC-03 y AC-04 se solapan
  si la parada objetivo es la primera del viaje y `arrival_s[0] ≤ s < departure_s[0]`, y la spec
  no dice cuál prevalece. El código da `AT_STOP` (`position_estimator.py:54-57`, D-04). Solo
  cambia la etiqueta de estado y no ocurre en el feed de EMT (`arrival = departure`).
  Recomendación: fijar la precedencia en la próxima revisión de la spec.
- **H-02 (no bloqueante, robustez)**: `application/get_vehicle_position.py:111-125`. Si una
  parada del viaje no está en el feed activo (`get_stop` → `None`) **y** el viaje no trae
  `shape_dist_traveled`, `estimate_position` lanza `ValueError` y la API responde `500`. Solo
  puede pasar si el feed cambia entre consultas, igual que el caso de D-10, que sí se trata como
  `NO_VEHICLE`. En el feed de EMT siempre hay `shape_dist_traveled`. Conviene tratarlo como en
  D-10 cuando se toque este código.
- **H-03 (no bloqueante, rendimiento, D-08)**: `sqlite_network.py:603-645`. En mi medición, el
  peor caso de `shape_stops` supera a veces los 20 ms del design §4 (17–24 ms; mejor de 3: 17,4
  ms). El implementer midió 1,6–15,7 ms. El coste está en leer los horarios de unos 400 viajes,
  no en buscar los viajes por `shape_id` (1,1 ms), así que el índice `(fv, shape_id)` que prevé
  el design apenas ayudaría. Además, la respuesta de trazado se cachea 24 h con `ETag`. No
  afecta a ningún AC. Se anota para `nfr_validation`.
- **H-04 (no bloqueante, test)**: `tests/integration/test_position_real_session.py:197-200`. La
  última aserción exige que **todo** par excluido retroceda más de 50 m, y `assert excluded`
  exige que haya alguno. AC-17 solo pide que el test informe de cuántos pares excluye: el test
  caracteriza la fixture más de lo que pide la spec y podría fallar con un cambio legítimo del
  `TripMatcher`. No afecta a la validez de la comprobación de AC-17.
- **H-05 (no bloqueante, test)**:
  `tests/integration/test_position_api.py:85-110` y `:146-160`. En AC-09 y AC-10 de
  integración, la posición esperada se calcula con el propio `estimate_position`. Estos tests
  prueban la composición y el mapeo, no el algoritmo. El algoritmo queda cubierto con valores
  calculados a mano en `test_position_estimator.py` y `test_get_vehicle_position.py`, así que no
  falta evidencia.

### Lista de comprobación (docs/verification.md §4)

- Contrato: comportamiento según los AC; endpoints, errores (`problem+json`, tipos) y forma de la
  respuesta según el design §3. OK.
- Arquitectura: `domain/` sin dependencias externas ni I/O (lint-imports OK); los casos de uso
  usan puertos; solo `main.py` / `container.py` instancian `SqliteNetworkRepository`; sin
  `datetime.now()`. OK.
- Tests: sin red (sockets bloqueados), `FakeClock`, fixtures `gtfs_mini` y `stop_508_peak` con
  origen documentado; los tests no son tautológicos (salvo la observación H-05). OK.
- Privacidad y seguridad: no hay logs nuevos; las excepciones nuevas no llevan identificadores en
  el mensaje (comprobado en tests); el token se valida antes de tocar el SAE; no hay
  configuración nueva (nada que añadir a `.env.example`). OK.
- Frontend: solo el contrato generado (`openapi.json`, `schema.d.ts`); no hay textos de interfaz
  ni vistas nuevas. e2e + a11y en verde. N/A u OK.
- Convenciones: glosario (`EstimatedPosition` → `PositionEstimate` según el design), commits
  Conventional Commits con ámbito `position_estimation` y tarea citada. OK.
- Alcance: no hay cambios fuera de la feature, salvo el ajuste justificado D-18. OK.
