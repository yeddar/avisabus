# Revisión: stop_arrivals_api — v1.4
Ciclo: 1 · Fecha: 2026-11-03 · Agente: reviewer · Spec: `specs/stop_arrivals_api/` v1.4 (APPROVED) · Rama: `feat/stop_arrivals_api` (13 commits sobre `develop`, de `b4191a9` a `25b47ef`)

## Veredicto: APPROVED

Las tareas T-01 a T-09 (incluidas T-05b y T-05c) están hechas. Los 22 AC tienen tests que
verifican el comportamiento: lo he comprobado leyéndolos y con 17 mutaciones del código, que
fallan todas. `./init.sh verify` está en verde y los tests `slow` (rendimiento y feed real de C1)
también pasan. He comprobado aparte la decisión de dejar `config/direction_overrides.json` vacío:
la reproduzco con el código de producción sobre el feed completo y todas las muestras reales
(139/139 entradas en red de E-01 y E-03 y 1142/1142 contando además las grabaciones de
`tests/fixtures/`), y ningún override cambia el resultado. No hay hallazgos bloqueantes. Quedan
dos problemas de spec no bloqueantes (P-1 y P-2) y cuatro notas menores.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `unit/test_get_stop.py::test_returns_the_stop_with_its_lines`; `integration/test_stops_api.py::test_stop_with_its_lines_in_natural_order` | OK | Usa `gtfs_mini`. Comprueba el nombre GTFS, `line/direction_id/headsign/color/text_color` y el orden `["70","93"]`, y que en la 2070 solo aparece la 98. |
| AC-02 | `test_get_stop.py` (2 tests), `test_get_stop_arrivals.py::test_invalid_token_or_unknown_stop_never_asks_the_sae`, `test_stops_api.py::test_invalid_token_or_unknown_stop_is_the_same_404` | OK | Prueba 12 peticiones (los 2 endpoints × sin token, vacío, longitud ≠ 22, 22 caracteres erróneo, token de otra parada y parada inexistente). Todas dan **el mismo cuerpo byte a byte** (`set` de 1 elemento), `problem+json`, `no-store`, y el SAE recibe 0 llamadas. |
| AC-03 | `test_get_stop.py::test_no_active_feed`, `test_get_stop_arrivals.py::test_no_active_feed`, `test_stops_api.py::test_no_active_feed_is_503` (2 endpoints) | OK | Devuelve `type …/network-unavailable` y el SAE no se consulta. |
| AC-04 | `test_get_stop_arrivals.py::test_realtime_arrivals_are_enriched_and_sorted`; `test_stops_api.py::test_arrivals_response_contract`, `::test_refresh_after_is_the_sae_cache_ttl`, `::test_realtime_arrivals_of_stop_508` (4 instantes), `::test_lines_outside_gtfs_mini_at_stop_2070` | OK | Hay una entrada por llegada del SAE: se compara con un parseo independiente del mismo replay y se comprueba el orden por `arrival_at` y el conjunto exacto de campos. `refresh_after_s` es igual al TTL (20 y 35). |
| AC-05 | `test_direction_resolver.py::test_single_direction_is_assigned_without_comparing_texts` (7 casos reales), `::test_single_direction_with_several_headsigns_wins_over_override_and_departing` | OK | Los casos son reales y el texto no tiene nada que ver con el headsign (2070/99 "La Malva-rosa", 701/C2 "Av. Aragó", 795/C1…). |
| AC-06 | `test_direction_resolver.py` (módulo entero: normalización, Jaccard con prefijos 1 a 1, umbral, estrictamente mayor y `TEXT_CASES`, 15 casos reales de E-01/E-03); `test_stops_api.py::test_real_c2_terminals_resolve_their_direction` | OK | Mutaciones: prefijos no 1 a 1, `>` en vez de `≥` en el umbral, `≥` en vez de `>` entre sentidos y quitar el alias `pass`/`ed`. Fallan todas. Ver P-1 sobre "supere". |
| AC-07 | `test_direction_resolver.py` (sin candidatos, empate, umbral, genérico sin regla de salida); `test_get_stop_arrivals.py::test_unresolved_direction`, `::test_line_in_the_network_that_does_not_serve_the_stop_is_unresolved`; `test_stops_api.py::test_unresolved_direction_is_logged` | OK | Comprueba `direction_id = null`, `can_alert = false`, `vehicle = null`, el evento `arrivals.direction_unresolved` con `stop_id/line/destination` y que no se buscan viajes. |
| AC-08 | `test_get_stop_arrivals.py::test_line_outside_the_network`; `test_stops_api.py::test_lines_outside_gtfs_mini_at_stop_2070` (3 instantes), `::test_duplicate_entries_are_kept` (línea 12 en la 1057) | OK | Caso real de la 2070 (73/95/99), tal como pide la v1.3. Todos los campos de AC-08 salen a `null`/`false`. |
| AC-09 | `test_direction_resolver.py` (4 tests de `resolve_destination`); `test_get_stop_arrivals.py::test_realtime_…`, `::test_unresolved_direction`; `test_stops_api.py::test_realtime_arrivals_of_stop_508` | OK | Con sentido resuelto, `destination` es el headsign GTFS; sin resolver, el texto del SAE. Ver la interpretación 2 más abajo. |
| AC-10 | `test_trip_matcher.py` (11 tests, uno contra **fuerza bruta** exhaustiva con duplicados); `test_get_stop_arrivals.py::test_candidates_are_the_scheduled_passages_around_each_line_and_direction`; `test_stops_api.py::test_two_93_buses_close_together_get_consecutive_trips` | OK | El caso real de la 93 en la 508 (E-02) da `_122/_123`. **Mutación con el matcher voraz:** fallan 6 tests (unit e integration, incluido el caso real). También fallan las mutaciones "sin maximizar el número", "tolerancia exclusiva", "orden no estricto" y "reutilizar viaje". La estabilidad se prueba con las 120 permutaciones de los candidatos. Tolerancia de 10 min inclusiva y configurable. |
| AC-11 | `test_trip_matcher.py::test_arrival_without_trip_within_tolerance_is_unmatched`, `::test_tolerance_is_inclusive`; `test_get_stop_arrivals.py::test_arrival_without_trip_within_tolerance` | OK | Comprueba `vehicle/occupancy = null`, `can_alert = true` y `arrivals.trip_unmatched` a nivel debug. |
| AC-12 | `test_get_stop_arrivals.py::test_realtime_…`, `::test_matched_trip_without_sensor_reading_has_no_occupancy`; `test_stops_api.py::test_realtime_arrivals_of_stop_508`, `::test_matched_trip_without_sensor_reading` | OK | La integración recalcula la ocupación con el sensor simulado y el clasificador, y comprueba que el viaje está a ≤ 10 min. |
| AC-13 | `test_scheduled_arrivals.py` (3); `test_get_stop_arrivals.py::test_fallback_…`, `::test_scheduled_arrival_without_sensor_reading`; `test_stops_api.py::test_fallback_to_the_timetable_when_the_sae_fails` | OK | Máximo 2 pasadas por (línea, sentido) en 90 min, con `CLOCK_TIME`, headsign, `vehicle`, ocupación, `can_alert` y `arrivals.fallback` con el motivo (`no_recording`). El SAE falla de verdad: replay sin grabación de la 508. |
| AC-14 | `test_scheduled_arrivals.py::test_no_passages_in_the_window`; `test_get_stop_arrivals.py::test_fallback_without_scheduled_passages_is_empty`; `test_stops_api.py::test_fallback_without_passages_in_the_window` | OK | Sábado, sin servicio en `gtfs_mini`. |
| AC-15 | `test_get_stop_arrivals.py::test_sae_without_arrivals_is_an_empty_realtime_answer`; `test_stops_api.py::test_sae_without_arrivals_does_not_fall_back` | OK | No consulta el horario ni registra `fallback`. |
| AC-16 | `test_stops_api.py::test_openapi_describes_both_endpoints_with_examples` y `no-store` en los tests de 200/404/503 | OK | Hay ejemplos en `StopResponse` y `StopArrivalsResponse`, 404/503 documentados y parámetros `stop_id`, `t`. |
| AC-17 | `test_stops_api.py::test_cached_stop_never_asks_the_sae_again`; `test_stops_api_perf.py` (`slow`) | OK | 201 peticiones dan 1 llamada al SAE; al cumplirse el TTL, 2. **Ejecutado por mí:** p95 de 2,9 ms (508) y 2,0 ms (2070). |
| AC-18 | `integration/test_network_repository.py::test_scheduled_stop_times_include_the_next_service_day`, `::test_scheduled_stop_times_with_a_window_of_several_days` | OK | Copia de `gtfs_mini` con un viaje sintético a las 00:20 del día siguiente, contrastada con fuerza bruta sobre el CSV. **Mutación** (volver a `D−1, D`): fallan 2 tests. Los tests de `gtfs_import.AC-15` no han cambiado y pasan. |
| AC-19 | `test_direction_resolver.py` (`DEPARTING_CASES`: 1959/C1, 2277/C1, 2230/99, 231/C3 y 346/C2, con y sin regla; prioridad del texto; exactamente uno), `test_get_stop_arrivals.py::test_departing_direction_resolves_a_generic_destination`, `test_network_repository.py` (3 tests de `departing_directions`), `test_stops_api.py::test_real_c2_terminals_resolve_their_direction[346]`, `test_stops_api_real_feed.py` (`slow`, C1 en 1959 y 2277) | OK | **Ejecutado por mí** `test_stops_api_real_feed.py` sobre `data/gtfs/emt/`: pasan los 2. "Cntr.Històric" da 0 en la 1959 y 1 en la 2277, con viaje que empieza en la parada. Mutaciones: sin regla de salida fallan 20 tests; con la consulta por `MAX` en vez de `MIN` fallan 8. Ver P-2 (C1 no está en la suite normal). |
| AC-20 | `test_direction_overrides.py` (3); `test_direction_resolver.py` (3 de override y `test_proposed_overrides_are_not_needed_with_the_v14_algorithm`, 9 casos); `test_get_stop_arrivals.py::test_override_by_line_and_sae_destination_names_a_headsign`; `test_stops_api.py` (validación al arrancar, override aplicado en la 346, fichero entregado vacío, lectura, fichero inutilizable); `test_main_stops.py::test_invalid_overrides_are_logged_without_stopping_the_start_up` | OK | El headsign se traduce al sentido de **cada parada** (prueba con numeración intercambiada). Una entrada inválida da `override_invalid` (`unknown_line`, `unknown_headsign`, `malformed_entry`) y el arranque continúa. El override gana a la regla de salida (integración en la 346). **Mutación** (ignorar el override): fallan 5 tests. |
| AC-21 | `test_get_stop_arrivals.py::test_realtime_…`, `::test_fallback_…`; `test_stops_api.py::test_arrivals_response_contract`, `::test_realtime_arrivals_of_stop_508`, `::test_override_by_headsign_is_applied_at_the_stop`, `::test_fallback_to_the_timetable_when_the_sae_fails` | OK | `sae_destination` es el texto del SAE tal cual (también cuando `destination` es el headsign) y `null` en `SCHEDULED`. Está en el esquema y en el ejemplo OpenAPI. |
| AC-22 | `test_trip_matcher.py::test_duplicate_arrivals_never_share_a_trip` y la fuerza bruta (con repeticiones); `test_get_stop_arrivals.py::test_duplicate_sae_entries_are_kept_and_get_different_trips`; `test_stops_api.py::test_duplicate_entries_are_kept` | OK | El caso real de la 1057 (dos `12 C.Art.Faller - 7 min.`) da dos llegadas. En unit, los duplicados de la 93 se emparejan con `_122` y `_123`. |

## Verificación ejecutada

- `./init.sh verify` → **todo en verde** (exit 0): format, lint, mypy, lint-imports (2 contratos
  sin romper), pytest con 853 passed y 6 deselected (cobertura de `domain`+`application` del 99,66 %),
  frontend format/lint/types/tests (7)/build, `feature_list.json` y trazabilidad AC→test (de AC-01
  a AC-22). Hay 2 warnings, los esperados de `test_no_network.py`.
- `uv run pytest -m slow tests/integration/test_stops_api_perf.py tests/integration/test_stops_api_real_feed.py`
  → 4 passed (con los sockets desactivados por `addopts`). AC-17: p95 de 2,9 ms y 2,0 ms.
- **Comprobación independiente de los overrides** (script propio en el scratchpad que usa el
  código de producción: `SqliteNetworkRepository.headsigns_at_stop`, `departing_directions` y
  `resolve_destination`, con `DEFAULT_ALIASES` y umbral 0,2, **sin overrides**). Importé
  `data/gtfs/emt/` en una SQLite del scratchpad con la CLI (42 líneas, 20 598 viajes, sin tocar
  `data/avisabus.sqlite`) y recorrí todas las entradas de
  `progress/explore_destinations_samples/{night_20261102,day_20261103}`:
  - **139/139 entradas en red resueltas**. Añadiendo las grabaciones de `tests/fixtures/sae_recordings/`: 1142/1142.
  - Las 16 observaciones de los 8 *overrides* de `proposal_full_v2.json` resuelven al **mismo sentido** que el override, sin él:
    - 6 por sentido único: 2070, 1679, 605, 2281 ×2 y 701. Ahí el override ni siquiera se consulta (regla 1).
    - 6 por texto: 1751 (0,333), 1265 (0,667), 1266 (0,2), 229 (0,25) y 2014 ×2 (0,25 y 0,5).
    - 3 por sentido que sale: 2230, 231 y 346.
  - En los casos que resuelve el texto, el sentido que sale coincide además con el del texto, así que no dependen de un empate en el umbral.
  - Los candidatos y los sentidos que salen escritos a mano en `test_direction_resolver.py` (`PROPOSED_OVERRIDES`, `REAL_CASES`) **coinciden exactamente** con los del feed real en todas las paradas citadas.
  - También es correcta la afirmación del implementer de que traducir cada override con el headsign "principal" del sentido sería erróneo en C2 y C3. Ejemplo: `C2|Av. Aragó` daría "Blasco Ibáñez - Facultat de Geografia", que no está en la 346.
- **Mutaciones** (copia de `backend/` en el scratchpad con `PYTHONPATH`, sin tocar el repo). Las 17 fallan: hay al menos un test que las detecta.
  - `trip_matcher`: voraz (6 tests), sin maximizar el número (1), tolerancia exclusiva (1), orden no estricto (1) y reutilizar viaje (1).
  - `direction_resolver`: sin regla de salida (20), prefijos no 1 a 1 (1), umbral `>` (2), sentidos con `≥` (1), ignorar el override (5), `c → carrer` (1), sin `ed` (1) y sin `pass` (1).
  - `sqlite_network`: días `D−1, D` (2) y `MAX(stop_sequence)` (8).
- Los cuerpos de `tests/fixtures/sae_recordings/samples/day_2026-11-03/*` son idénticos a los de `progress/explore_destinations_samples/day_20261103/*`, también en `captured_at`. Lo comprobé con un script.
- Alcance (`git diff develop..HEAD`): no hay cambios en `specs/` ni en `docs/`.
  - `feature_list.json`, `progress/current.md` y `progress/history.md` solo cambian en los commits `chore(progress)` del orquestador.
  - El código de `gtfs_import` solo cambia lo que autorizan T-05b y T-05c: `_service_days`, `departing_directions` y el docstring del puerto.
  - Los commits siguen Conventional Commits con el ámbito de la feature y citan la tarea.
- `git status` limpio antes de escribir este fichero.

### Sobre la conclusión "ningún override es necesario" (petición de la persona)

Está **bien demostrada** y no se apoya en un test débil:
- El test `test_proposed_overrides_are_not_needed_with_the_v14_algorithm` prueba cada override propuesto **sin** él, sobre su caso real, y su aserción discriminante es `without_override == expected`. Cubre todas las paradas de varios sentidos donde se observó cada clave. En las de un solo sentido el override nunca se consulta, por la regla 1.
- Su debilidad es que los candidatos y los sentidos que salen están transcritos a mano (el feed completo no se versiona). La he cubierto comprobando la transcripción contra el feed real: coincide en todo.
- Además lo respaldan casos con datos reales de extremo a extremo: la 346/C2 con `gtfs_mini` en la suite normal y la 1959/2277/C1 con el feed real en `slow`.

## Interpretaciones locales del implementer (¿caben en el design?)

Todas caben en el design o rellenan huecos sin cambiar ningún contrato:

| # | Interpretación | Valoración |
|---|---|---|
| 1 | Prefijos 1 a 1: primero los exactos, después voraz por (longitud, alfabético) | Cabe en design §3 ("emparejados 1 a 1 de forma voraz"). Está fijada con tests. |
| 2 | Headsign mostrado: con override, el del override; con sentido que sale, el más parecido dentro del sentido (si empatan, el más frecuente) | Cabe en design §3 "API" ("el headsign ganador, el más parecido"). Rellena un hueco (O-3). |
| 3 | Desempate lexicográfico, con la llegada emparejada antes que la no emparejada | Cabe en design §3 ("lexicográfico por trip_id"). Solo actúa entre asignaciones con el mismo número y la misma desviación. |
| 4 | Una consulta por (línea, sentido) con la ventana de design §3 | Es literalmente lo que dice el design. |
| 5 | Ocupación leída en `clock.now()` | El design no lo fija; es razonable. |
| 6 | `refresh_after_s = ceil(TTL)`, también en `SCHEDULED` | Cumple AC-04. |
| 7 | Comprobaciones en orden token → feed → parada | Correcto: con token inválido nunca revela que no hay feed (AC-02). |
| 8–9 | Niveles de log; las líneas fuera de red no registran `direction_unresolved` | Coherente con design §5 y AC-08. |
| 10 | `departing_directions` con consulta directa sobre todos los viajes del feed activo, sin filtrar por calendario | Es una decisión local permitida (design §3). Lo he comprobado en el feed real: las medidas están por debajo de 20 ms. |
| 11 | Validación con `FeedInfoSource.direction_report()` | Comprobado: `_REPORT_HEADSIGNS` incluye **todos** los headsigns de cada sentido, como pide "headsign existente en algún sentido". |
| 12 | Fichero de overrides ilegible → `ConfigurationError` y la API no arranca | Hueco de la spec (O-4). Coherente con `AVISABUS_SAE_REPLAY_DIR`. Ver NB-3. |
| 13–16 | Configuración, `container.py`, `Logger` como `Protocol`, `service_day_start` | Hay precedente para `container.py` (`adapters/inbound/cli/container.py`). Las capas se respetan (lint-imports). |
| 17 | Fixture `samples/day_2026-11-03/` | Cuerpos idénticos a los originales y documentada en el README. |
| 18 | AC-19 con C1 solo en `slow` | Ver P-2. |

## Hallazgos

### Bloqueantes

Ninguno.

### Problemas de spec (no bloqueantes → CP-3 ligero para el spec-writer)

- **P-1 — AC-06 frente a design §3, umbral en el límite.**
  - `specs/stop_arrivals_api/requirements.md:65` dice "siempre que la similitud **supere** el umbral", es decir, estrictamente mayor.
  - `specs/stop_arrivals_api/design.md:102` dice `best[d*] ≥ min_score`.
  - El código sigue el design (`backend/src/avisabus/domain/services/direction_resolver.py:154`) y lo fija `test_best_score_must_reach_the_threshold`.
  - En los datos reales hay un caso exactamente en 0,2: 1266/C3 "C. Benlloch". Con cualquiera de las dos lecturas da el mismo sentido, porque la regla de salida también da 1. Por eso no cambia ningún resultado observado.
  - Propuesta: cambiar en AC-06 "supere" por "alcance" (o "sea mayor o igual que").
- **P-2 — AC-19, verificación "integration (cabeceras de C1, 1959 y 2277)".**
  - `requirements.md:105` pide esa verificación, pero `gtfs_mini` no tiene C1. Por eso la integración con C1 solo existe en `tests/integration/test_stops_api_real_feed.py`, que está marcado `slow` y se omite si no está `data/gtfs/emt/`. En la suite normal, AC-19 se verifica en integración con la cabecera real 346 de C2.
  - Lo he ejecutado y pasa.
  - Propuesta: ajustar la verificación de AC-19 (C2 en `gtfs_mini` + C1 en `slow` con el feed real) o ampliar `gtfs_mini` con C1. Es la O-5 del implementer.
- (Para tener en cuenta, no requiere acción ahora.) La O-2 del implementer es correcta: con el formato `línea|destino → headsign`, `C3|Campanar` no se puede expresar en una sola entrada. Hoy no tiene efecto porque no hay overrides.

### No bloqueantes

- **NB-1 — Cifras inexactas en el progreso.** En `progress/impl_stop_arrivals_api.md:67` pone "1751: texto (0,25 ≥ 0,2)" y en la línea 68 "229: texto (0,2)". Con el código, las similitudes reales son **0,333** y **0,25**. La conclusión no cambia (ambas superan 0,2); solo afecta a la exactitud del registro.
- **NB-2 — Acoplamiento entre tests.** `backend/tests/unit/test_direction_overrides.py:9` importa `FakeLogger` de `tests.unit.test_get_stop_arrivals`. Convendría moverlo a `tests/support/`.
- **NB-3 — Ruta relativa del fichero de overrides.**
  - `.env.example:103` apunta `AVISABUS_DIRECTION_OVERRIDES_FILE` a `config/direction_overrides.json`, relativo a `backend/`. Si el `.env` se copia tal cual y la API arranca desde otro directorio, no arranca (`ConfigurationError`, `backend/src/avisabus/config.py:141`).
  - Sigue la misma convención que `AVISABUS_SAE_REPLAY_DIR` y está documentado. Conviene tenerlo en cuenta en `deploy/`.
- **NB-4 — Overrides validados solo al arrancar** (la O-1 del implementer). Se ajusta a AC-20 ("al arrancar"). Tras importar un feed nuevo con la API en marcha, los overrides no se revalidan hasta reiniciar. Hoy no tiene efecto (fichero vacío).

---
**Resumen para el orquestador:**
- **APPROVED** (ciclo 1). `./init.sh verify` en verde (853 passed, cobertura 99,66 %) y los tests `slow` pasan (AC-17 p95 2,9 ms; C1 en 1959/2277 con el feed real). Los 22 AC tienen tests válidos y las 17 mutaciones fallan, incluido el matcher voraz.
- El fichero de overrides vacío está bien demostrado: con el código de producción y el feed completo, 139/139 entradas reales se resuelven sin overrides, y los 8 propuestos darían el mismo sentido que sin ellos. La transcripción del test coincide con el feed real.
- Sin bloqueantes. Hay 2 problemas de spec menores para CP-3 ligero (P-1 "supere" frente a `≥` en AC-06; P-2 verificación de AC-19 con C1 fuera de `gtfs_mini`) y 4 notas menores.
