# Revisión: occupancy_sensor — v1.2
Ciclo: 1 (v1.2) · Fecha: 2026-11-03 · Agente: reviewer · Spec: `specs/occupancy_sensor/` v1.2 (APPROVED) · Rama: `fix/sae-occupancy-v1.3` (commits `c0dbd32` T-09 y `d3f3d37` T-10 sobre `develop`)

## Veredicto: APPROVED

T-09 y T-10 están hechas. AC-15 (nuevo) tiene un test de composición real: importa `avisabus.main`
en un subproceso con `AVISABUS_OCCUPANCY_*` no estándar. He comprobado por mutación que detecta
una composición que use los valores por defecto. `main.py` no cambia, porque la composición ya
era correcta. Los 15 AC tienen evidencia y `./init.sh verify` está en verde. Ningún hallazgo
bloqueante. Hay un problema de spec no bloqueante (O-02 del implementer) sobre la redacción de
AC-15.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 … AC-14 | `tests/unit/test_occupancy_classifier.py`, `test_occupancy_simulation.py`, `test_simulated_occupancy_sensor.py`, `test_set_occupancy_override.py`; `tests/integration/test_occupancy_override_repository.py`, `test_cli_occupancy.py`, `test_main_composition.py` | OK | Sin cambios desde v1.1 (aprobada). La trazabilidad sigue en verde. |
| **AC-15 (nuevo)** | `tests/integration/test_occupancy_composition.py::test_main_composes_the_sensor_and_the_classifier_with_the_configured_values` (:231), `::test_the_configuration_of_the_test_is_far_enough_from_the_defaults` (:257), `::test_the_cli_container_composes_no_occupancy_sensor_nor_classifier` (:286) | OK | (1) Un subproceso importa `avisabus.main` con capacidad 60, asientos 20, semilla `composition-test` y umbrales 0,30/0,70. Usa un directorio de trabajo sin `.env`, la variable `AVISABUS_*` del entorno filtrada y una copia temporal de una BD con `gtfs_mini` y forzados. Lee con `main.occupancy_sensor` 3 viajes de cada línea forzada (93 FULL, 70 FREE, C2 MEDIUM) y 20 de la 98. Compara cada lectura (capacidad, asientos, ocupados) con la de un `SimulatedOccupancySensor` construido en el test con los valores configurados y `FakeClock`. Comprueba también que `main.occupancy_thresholds` son los configurados y que los forzados dan `override_occupied(nivel, 60, umbrales)` clasificado en su nivel. (2) El test guarda demuestra que dejar cualquiera de los 4 valores en su valor por defecto cambia alguna lectura de referencia, así que el test (1) no puede pasar por casualidad. (3) La CLI no compone sensor ni umbrales (ver SP-1). **Mutación verificada por mí:** con `main.py` mutado para usar la semilla `"avisabus"`, `capacity=90` o `OccupancyThresholds()` por defecto, el test (1) falla por aserción. La copia sin mutar pasa (3 passed). |

## Verificación ejecutada

- `./init.sh verify` → **todo en verde** (exit 0): format, lint, mypy, lint-imports, pytest con
  665 passed y 2 deselected (cobertura `domain`+`application` del 99,52 %), frontend OK,
  `feature_list.json` y trazabilidad (incluido `occupancy_sensor.AC-15`).
- **Mutaciones** de `main.py` en una copia de `src/` en el scratchpad con `PYTHONPATH`, sin tocar
  el repo: `pytest --no-cov tests/integration/test_occupancy_composition.py -k main_composes` da
  1 failed (`AssertionError` en `composed["readings"] == expected`) en cada una de las 3
  mutaciones (semilla, capacidad y umbrales del sensor). La copia de control da 3 passed.
- `git status` limpio tras la revisión.

## Comprobación de `docs/verification.md` §4 (lo nuevo)

- **Contrato:** AC-15 se cumple en `main.py:31-41,54-55`, que pasa `occupancy_capacity`,
  `occupancy_seats`, `occupancy_seed` y `occupancy_thresholds()` de `Settings`.
- **Arquitectura:** sin cambios de código de producción.
- **Tests:** el proceso de pytest no usa red ni reloj real: la referencia usa `FakeClock`. El
  subproceso sí usa `SystemClock` (es la raíz de composición real), pero el resultado no depende
  de él: las lecturas llevan `at` explícito y los forzados caducan en 2100. Ver NB-1. La BD es
  temporal y nunca se usa `data/` ni un `.env` de desarrollo.
- **Privacidad:** no aplica (sin registros nuevos).
- **Convenciones:** commits `test(occupancy_sensor)` y `chore(occupancy_sensor)` con la tarea.
- **Alcance:** solo un fichero de test nuevo más los ficheros de progreso.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **NB-1 — El subproceso del test de AC-15 queda fuera de las salvaguardas de pytest**
  (`backend/tests/integration/test_occupancy_composition.py:211`).
  - `pytest-socket` no bloquea los sockets de un subproceso, y `main.py` usa `SystemClock`.
  - Hoy no hay riesgo: con `AVISABUS_ENV=test` la fuente de llegadas es replay sobre E-01, y nada
    depende de la hora real.
  - Es el mismo patrón que `test_main_composition.py`, ya aprobado.
  - Lo anoto para que, si `main.py` llega a hacer I/O de red al importarse, el test se revise.

### Problemas de spec (no bloqueantes; para el spec-writer)
- **SP-1 — AC-15 cita "el contenedor de la CLI", pero la CLI no compone sensor ni clasificador**
  (`specs/occupancy_sensor/requirements.md:95`; O-02 en `progress/impl_occupancy_sensor.md`).
  - `CliContainer` (`adapters/inbound/cli/container.py`) solo compone los casos de uso de
    forzado, que guardan el nivel, no plazas.
  - El implementer no ha inventado un sensor para la CLI, y es correcto. El test (3) fija que,
    si algún día lo compone, habrá que escribir un test como el de `main.py`.
  - Propuesta: "(y en el contenedor de la CLI, si compone alguno)", o quitar el paréntesis.

---

# Revisión: occupancy_sensor — v1.1 (revisión anterior)
Ciclo: 1 (v1.1) · Fecha: 2026-11-02 · Agente: reviewer · Spec: `specs/occupancy_sensor/` v1.1 (APPROVED) · Rama: `fix/bloque-1-ajustes` (commits `4d09934` T-07 y `ffb8f9d` T-08 sobre `develop`)

## Veredicto: APPROVED

T-07 y T-08 están hechas. AC-03 y AC-11, ampliados en v1.1, tienen tests de ejemplo y de
propiedades (Hypothesis) que comparan con una fuerza bruta independiente, y fallan con las
mutaciones relevantes. Los 14 AC conservan su evidencia y `./init.sh verify` está en verde.
Ningún hallazgo bloqueante; dos observaciones no bloqueantes sobre la cobertura de tests.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01, AC-02 | `tests/unit/test_occupancy_classifier.py` | OK | `classify_occupancy` se reorganiza con `_level` (`occupancy_classifier.py:59-64`) sin cambiar la regla. Los tests de fronteras 0,49/0,50/0,84/0,85 siguen en verde. |
| **AC-03 (v1.1)** | `test_occupancy_classifier.py::test_a_level_without_any_whole_number_of_places_refuses_to_start` (capacidad 3 con 0,50/0,60, que es el ejemplo del design; capacidad 1 con los umbrales por defecto; capacidad 10 con 0,51/0,59), `::test_small_capacities_where_every_level_fits_are_accepted`, `::test_configuration_is_rejected_exactly_when_some_level_is_unreachable` (Hypothesis, 300 ejemplos); los tests de v1.0 (umbrales y `seats > capacity`); `tests/integration/test_main_composition.py` | OK | La propiedad comprueba **si y solo si**: `Settings` rechaza la configuración exactamente cuando algún nivel no es alcanzable, según una fuerza bruta sobre `0…capacidad` con `classify_occupancy` (`tests/support/occupancy.py:13-19`). **Mutación:** sin la comprobación nueva en `config.py:71-79`, fallan 4 tests. |
| AC-04 … AC-10 | `test_simulated_occupancy_sensor.py`, `test_occupancy_simulation.py` | OK | Sin cambios en la simulación. El constructor recibe `thresholds`, y los tests le pasan `OccupancyThresholds()`. |
| **AC-11 (v1.1)** | Unidad: `test_occupancy_classifier.py::test_override_takes_the_middle_of_the_band_of_the_default_thresholds` (22/61/83), `::test_override_follows_the_configured_thresholds` (0,40/0,90 → 20/65/95), `::test_override_is_moved_into_the_band_when_rounding_leaves_it` (capacidad 4 con 0,25/0,50 → MEDIUM 1), `::test_override_is_none_when_the_band_has_no_whole_number`, `::test_override_is_always_classified_as_the_requested_level_when_it_fits` (Hypothesis); `test_simulated_occupancy_sensor.py::test_override_forces_the_level_of_every_trip_of_the_line`, `::test_override_uses_the_configured_thresholds_and_capacity`, `::test_override_level_matches_the_classification_for_any_valid_configuration` (Hypothesis, sensor completo). Integración: `tests/integration/test_cli_occupancy.py` (CLI + BD + `FakeClock`) | OK | Coincide con design §3 "Forzado": punto medio de la banda (0,25 / 0,675 / 0,925 con los valores por defecto) y ajuste de uno en uno. El barrido con Hypothesis que pide el AC está a dos niveles: la función pura y el sensor. **Mutaciones:** sin el ajuste por redondeo fallan 7 tests (incluida la propiedad de `override_occupied`); con un sensor que ignora los umbrales configurados fallan 4. |
| AC-12, AC-13, AC-14 | `test_cli_occupancy.py`, `test_occupancy_override_repository.py`, `test_set_occupancy_override.py`, `test_simulated_occupancy_sensor.py` | OK | Solo cambian los valores esperados (18/58/86 → 22/61/83), como consecuencia de AC-11 v1.1. La lógica de caducidad, `--clear`, `--list` y la caché de 5 s no cambia. |

Corrección de `override_occupied` (`domain/services/occupancy_classifier.py:31-56`): el recorrido
está acotado a `0…capacidad`, porque 0 plazas es siempre FREE (`medium > 0`) y `capacidad`
plazas es siempre FULL (`full ≤ 1`). Como el nivel es monótono en `occupied`, recorrer de uno en
uno visita todos los enteros de la banda, y saltarla (`(rank - target) * step > 0`) equivale a
que la banda no tenga enteros. La validación de `Settings` y el sensor usan la misma función y
la misma regla `_level` que el clasificador, así que no pueden discrepar.

## Verificación ejecutada

- `./init.sh verify` → **todo en verde** (exit 0): 645 passed y 2 deselected, cobertura del
  99,52 % (`occupancy_classifier.py` al 100 %), lint-imports con 2 contratos respetados,
  frontend OK y trazabilidad OK.
- `cd backend && uv run pytest tests/unit/test_sae_cache.py tests/unit/test_simulated_occupancy_sensor.py tests/unit/test_occupancy_classifier.py tests/integration/test_cli_occupancy.py` → 117 passed.
- **Mutaciones** en una copia del backend en el scratchpad:
  - (M5) sin la comprobación de AC-03 v1.1 → 4 failed;
  - (M6) sin el ajuste por redondeo → 7 failed;
  - (M7) un sensor que usa los umbrales por defecto en vez de los configurados → 4 failed;
  - (M8) `main.py` sin `settings.occupancy_thresholds()` → **0 fallos atribuibles**. El único
    fallo, `test_env_example_documents_every_setting`, también falla sin mutar en la copia,
    porque es un artefacto de la ruta de la copia (ver NB-1).

## Comprobación de `docs/verification.md` §4 (lo nuevo)

- **Contrato:** design §3 "Forzado" v1.1 (punto medio, ajuste y rechazo al arrancar) y §5
  (`ConfigurationError` al construir `Settings`) se cumplen.
- **Arquitectura:** `override_occupied` es una función pura de `domain/`, sin I/O. `config.py`
  importa el servicio de dominio, que es una dirección permitida; lint-imports en verde.
- **Tests:** sin red; Hypothesis con `derandomize=True` y `database=None` (reproducible y sin
  escribir `.hypothesis/`); `FakeClock`.
- **Privacidad:** el mensaje de `ConfigurationError` incluye la capacidad y los umbrales, que no
  son datos personales ni secretos.
- **Configuración:** `.env.example` documenta la nueva condición de arranque y el punto medio.
- **Convenciones:** `fix(occupancy_sensor): …` y `chore(progress): …`.
- **Alcance:** `occupancy_classifier.py` y `main.py` no están en la lista de ficheros de T-07. El
  implementer lo anota en sus decisiones locales y ambos son necesarios: la función compartida y
  el cableado de los umbrales configurados. Lo considero dentro del alcance.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **NB-1 — Ningún test comprueba que `main.py` pase al sensor los umbrales configurados.**
  `backend/src/avisabus/main.py:40` (`thresholds=settings.occupancy_thresholds()`). Si se
  cambiara por `OccupancyThresholds()`, todo seguiría en verde (mutación M8): con umbrales no
  por defecto, los forzados de la API se clasificarían con otros umbrales que el resto del
  sistema, que es justo SP-01. Propuesta: en `tests/integration/test_main_composition.py`
  (subproceso), definir unos umbrales no por defecto y un forzado, y comprobar el número de
  plazas que devuelve `main.occupancy_sensor`. O basta con comprobar que el sensor guarda los
  umbrales de `main.settings`.
- **NB-2 — El barrido con Hypothesis del sensor completo no detecta por sí solo la falta del
  ajuste por redondeo.** `backend/tests/unit/test_simulated_occupancy_sensor.py`
  (`test_override_level_matches_the_classification_for_any_valid_configuration`). En la mutación
  M6, ese test sigue en verde con los 300 ejemplos derandomizados. Lo detectan la propiedad
  equivalente sobre `override_occupied` y el caso de ejemplo de capacidad 4, así que AC-11
  sigue cubierto. Solo afectaría si algún día el sensor dejara de usar `override_occupied`. Para
  reforzarlo se puede añadir `@example(...)` con la configuración (4, 0,25, 0,50).

### Problemas de spec

Ninguno.

---

# Revisión: occupancy_sensor — v1.0 (revisión anterior)
Ciclo: 1 · Fecha: 2026-11-01 · Agente: reviewer

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Hay 2 problemas de spec, ninguno bloqueante: SP-01 (O-01 del
implementer) y SP-02. Hay además 6 observaciones no bloqueantes sobre el código (N-01…N-06).

Base de la revisión: `develop...feat/occupancy_sensor`, 8 commits (de b591a7c a 9de5a48).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `tests/unit/test_occupancy_classifier.py::test_reading_keeps_its_values_and_derives_free_places_and_free_seats`, `::test_free_seats_never_goes_below_zero` | OK | Cubre los campos, `free_places` y el `max(0, …)` de `free_seats` en 0, 27, 28, 60 y 90. |
| AC-02 | `test_occupancy_classifier.py::test_classifies_by_ratio_with_default_thresholds` (fronteras 0/49/50/84/85/100 sobre capacidad 100), `::test_thresholds_are_configurable`, `::test_default_thresholds_are_half_and_eighty_five_percent`, `::test_status_reports_free_seats_and_free_places`, `::test_status_has_no_free_seats_when_every_seat_is_taken` | OK | Fronteras 0,49 / 0,50 / 0,84 / 0,85 exactas. Umbrales configurables y `has_free_seats` cubiertos. |
| AC-03 | `test_occupancy_classifier.py::test_invalid_thresholds_refuse_to_start` (5 casos), `::test_more_seats_than_capacity_refuses_to_start`, `::test_valid_thresholds_are_accepted`, `::test_as_many_seats_as_capacity_is_accepted`, `::test_occupancy_settings_have_documented_defaults`; `tests/integration/test_main_composition.py::test_application_refuses_to_start_with_invalid_occupancy_configuration` | OK | Se lanza `ConfigurationError` al construir `Settings` (design §5). El test de composición, en un subproceso, comprueba que la API no arranca y que no se crea la BD. |
| AC-04 | `tests/unit/test_simulated_occupancy_sensor.py::test_same_trip_day_and_instant_always_give_the_same_reading`, `::test_the_seed_is_configurable`, `::test_the_service_day_is_part_of_the_vehicle_identity` | OK | Comprueba la misma lectura con la misma instancia y con una nueva (reinicio). La semilla cambia el resultado. |
| AC-05 | `tests/unit/test_occupancy_simulation.py::test_simulate_occupied_never_leaves_zero_to_capacity` (Hypothesis), `::test_simulated_occupancy_is_bounded_for_any_hour_day_and_progress` (Hypothesis, factores reales), `::test_simulated_occupancy_sweep_of_hours_and_progress_is_bounded` (barrido 24 h × 11 avances × 3 días) | OK | Se verifica sobre las funciones puras. El sensor es exactamente esa composición: en `test_simulated_occupancy_sensor.py` las lecturas se igualan a `simulate_occupied(...)`. |
| AC-06 | `test_occupancy_simulation.py::test_rush_hour_occupancy_is_at_least_the_late_evening_one` (horas 7, 8, 17, 18 y 19; minutos 0/30/59; 5 avances; 100 viajes), `::test_rush_hour_is_strictly_busier_than_late_evening_mid_route` | OK | Mismo viaje y avance, día laborable, comparado con las 23:00. |
| AC-07 | `test_occupancy_simulation.py::test_mid_route_is_busier_than_both_ends` (24 h × laborable/domingo × 100 viajes) | OK | Desigualdad estricta frente a los avances 0 y 1. |
| AC-08 | `test_simulated_occupancy_sensor.py::test_occupancy_follows_the_progress_computed_from_the_schedule` (incluye los recortes por debajo y por encima), `::test_progress_uses_first_and_last_arrival_of_the_trip`, `::test_progress_of_a_trip_after_midnight_counts_from_its_service_day`; `test_occupancy_simulation.py::test_progress_*` (6 tests, uno con Hypothesis, más el cambio de hora del 25-10) | OK | Con repositorio fake, como pide la spec. Comprueba que el sensor consulta `trip_stop_times`. |
| AC-09 | `test_simulated_occupancy_sensor.py::test_unknown_trip_has_no_reading`, `::test_unknown_trip_has_no_reading_even_with_overrides` | OK | `SqliteNetworkRepository.trip_stop_times` filtra por el feed activo (`sqlite_network.py:548-555`), así que "red activa" se cumple también en producción. |
| AC-10 | `test_occupancy_simulation.py::test_one_hundred_trips_at_the_same_time_and_progress_give_several_levels` | OK | 100 viajes, misma hora y avance, 3 escenarios. Al menos 2 niveles. |
| AC-11 | `tests/integration/test_cli_occupancy.py::test_override_forces_the_level_of_every_trip_of_the_line` (FREE/MEDIUM/FULL, CLI + BD temporal + FakeClock + `gtfs_mini`), `::test_override_leaves_the_other_lines_simulated`, `::test_override_lasts_thirty_minutes_by_default`, `::test_level_is_case_insensitive`, `::test_override_survives_a_gtfs_reimport`; unit `test_simulated_occupancy_sensor.py::test_override_*`, `::test_expired_override_no_longer_applies`; `test_set_occupancy_override.py`; `test_occupancy_override_repository.py` | OK | Ruta completa CLI → SQLite → sensor con otro engine, clasificada con los umbrales por defecto. Ver SP-01 para umbrales no por defecto. |
| AC-12 | `test_cli_occupancy.py::test_sensor_returns_to_simulation_when_the_override_expires`, `::test_clear_returns_the_line_to_simulation`, `::test_clear_of_a_line_without_override_says_so`, `::test_clear_of_an_unknown_line_exits_2`; `test_occupancy_override_repository.py::test_active_excludes_expired_overrides`, `::test_clear_removes_only_that_line` | OK | Vuelve a la simulación tanto al caducar como con `--clear`. El otro forzado se mantiene. |
| AC-13 | `test_cli_occupancy.py::test_list_shows_the_active_overrides_with_their_expiry`, `::test_list_without_active_overrides`; `test_set_occupancy_override.py::test_list_returns_active_overrides_in_natural_line_order` | OK | Salida exacta con la caducidad. Los caducados desaparecen. |
| AC-14 | `test_cli_occupancy.py::test_running_sensor_sees_cli_changes_within_five_seconds` (engine distinto, 4,999 s cacheado / 5 s refrescado); `test_simulated_occupancy_sensor.py::test_override_changes_are_seen_within_five_seconds`, `::test_overrides_are_queried_at_most_once_every_five_seconds`; `test_occupancy_override_repository.py::test_overrides_are_shared_between_engines_of_the_same_database` | OK | Simula otro proceso con un engine independiente. La caché se mide con FakeClock. |

Todos los AC tienen al menos un test que los cita y que fallaría si se rompiera el
comportamiento: las aserciones comparan valores calculados o la salida exacta, no solo que no se
lance una excepción.

## Verificación ejecutada

- `./init.sh verify`, desde la raíz el 2026-11-01. Código de salida 0, todo en verde.
  - backend format, lint (`ruff`: All checks passed) y types (`mypy`: Success, 56 source files): OK.
  - architecture (`lint-imports`: Hexagonal layers KEPT; Domain has no external dependencies KEPT): OK.
  - backend tests: 422 passed, 2 deselected (slow). Cobertura `domain` + `application` 99,44 % (≥ 80 %).
  - frontend format, lint, types, tests (7 passed) y build: OK.
  - harness `feature_list.json` y trazabilidad AC→test: OK.
- `grep -rn "occupancy_sensor.AC-" backend/tests`: los 14 AC están citados (entre 1 y 13 citas cada uno).
- Listado de `data/` antes y después de la verificación: sin cambios. Los tests usan `tmp_path`, y
  `test_main_composition.py` usa un subproceso con `cwd` y BD temporales.
- `git status`: solo `feature_list.json` modificado (lo cambió el orquestador al pasar a `in_review`).
- `git diff --stat develop...HEAD`: todos los ficheros tocados están en `tasks.md` o son
  necesarios para la composición (`db.py`, `cli/container.py`, `cli/main.py`, `domain/errors.py`,
  `pyproject.toml`/`uv.lock` por `hypothesis`, design §7).
- Comprobación ad hoc de las proporciones de forzado frente a los umbrales por defecto, para
  capacidades de 1 a 500: solo falla `capacity = 1` con MEDIUM (`round(0,65) = 1`, que es FULL).
  Ver SP-01.

## Valoración de las decisiones locales señaladas

| Decisión | Valoración |
|---|---|
| `MetaData` propio para `occupancy_override` (`sqlite_occupancy_override.py:16-24`, `db.py:46-49`) | **Cabe en el design.** Design §4 solo exige la tabla y `create_all` (ADR-011), y las dos se cumplen. La justificación es real: `VERSIONED_TABLES` se deriva del `metadata` de red (`network_tables.py:181`) y se usa para purgar versiones (`sqlite_network.py:223,230`). Con el `metadata` compartido, la reimportación del GTFS borraría o rompería la tabla de forzados. Hay un test de que el forzado sobrevive a la reimportación. |
| Firma `progress(trip_stop_times, service_date, at)` (`occupancy_simulation.py:68`) | **Aceptable.** El propio design dice "con el día de servicio", y sin la fecha la función no se puede calcular. Es una función interna sin consumidores fuera de la feature. La imprecisión de la firma se anota en SP-02. |
| Filtro de caducidad sobre la caché (`simulated_sensor.py:84`) | **Cabe en el design** (§8, "estructura interna de la caché"). Hace que la caducidad sea exacta (AC-12) sin cambiar la ventana de 5 s para cambios externos (AC-14). Los tests cubren los dos bordes. |
| `NetworkRepository.trip_line` (`domain/ports/network.py:51-56`, `sqlite_network.py:561-566`) | **Previsto por la spec.** Design §3 define expresamente esta ampliación del puerto y T-03 la asigna con sus ficheros. Solo consulta el feed activo y tiene tests de feed activo, viaje inexistente, BD vacía y agrupación por `route_short_name`. mypy confirma que no rompe otros implementadores. |
| Nombres expuestos en `main.py` (`main.py:37-41`) | **Aceptable, no bloqueante** (ver N-01). Es la composición que pide T-06. No se inventa un mecanismo de inyección, que decidirá `stop_arrivals_api`. |

## Hallazgos

### Bloqueantes

Ninguno.

### Problemas de spec (→ CP-3 a criterio de la persona; ninguno bloquea esta revisión)

- **SP-01 — AC-11 frente a design §3 "Forzado" (O-01 del implementer). No bloqueante.**
  - **Lugar:** `specs/occupancy_sensor/requirements.md` (AC-11) y `design.md` §3. En el código,
    `simulated_sensor.py:24-28`.
  - **Contradicción:** AC-11 exige que la lectura forzada quede "clasificada como FULL/FREE/MEDIUM".
    El design fija `r = 0,20 / 0,65 / 0,95`, que no depende de los umbrales. AC-02 y AC-03, en
    cambio, permiten umbrales configurables con solo `0 < medio < lleno ≤ 1`. Así, con umbrales
    válidos distintos de los por defecto, AC-11 no se cumple. Por ejemplo, con `full = 0,99` un
    FULL forzado se clasifica como MEDIUM. Lo mismo pasa con `medium ≤ 0,20` o `medium > 0,65`.
    Con los umbrales por defecto también falla en el caso degenerado `capacity = 1` con MEDIUM.
  - **El código es correcto respecto al design:** lo implementa al pie de la letra y no inventa
    contrato.
  - **No bloquea:**
    - con la configuración por defecto (y cualquier capacidad ≥ 2) AC-11 se cumple y está probado;
    - el forzado es una herramienta de demo.
  - **Riesgo:** una demo de alerta de capacidad (`driver_demand`) con umbrales cambiados no
    mostraría FULL.
  - **Propuesta para la v1.1** (la elige la persona):
    - (c), la mínima: acotar AC-11 a los umbrales por defecto;
    - (b): que AC-03 restrinja `0,20 < medium ≤ 0,65 < full ≤ 0,95`, cuidando el redondeo;
    - (a): calcular `r` a partir de los umbrales. Exige inyectar `OccupancyThresholds` en el sensor,
      lo que cambia el design (hoy el sensor devuelve una lectura cruda y la clasificación es aparte).
- **SP-02 — Firma de `progress` en design §3. No bloqueante.**
  - El design escribe `progress(trip_stop_times, at)`, pero el texto requiere el día de servicio,
    y su regla de inicio (mediodía − 12 h, Europe/Madrid) no está escrita en la spec.
  - Propuesta: en la v1.1, `progress(trip_stop_times, service_date, at)` y una referencia a la
    regla de día de servicio de `gtfs_import`.

### No bloqueantes

- **N-01 — `main.py:37-41`: efectos de importación y nombres sin consumidor.**
  - Al importar `avisabus.main` ahora se crea el engine y se ejecuta `init_db`. Con la URL por
    defecto, eso crea `../data/avisabus.sqlite`, que es lo esperado al arrancar la API.
  - `occupancy_sensor` y `occupancy_thresholds` quedan como nombres de módulo que nadie consume
    todavía. El engine no se libera al apagar.
  - Es aceptable para esta fase. Se recomienda que `stop_arrivals_api` defina en su spec el
    mecanismo de inyección y el ciclo de vida (lifespan) del engine.
  - Que ningún test importe `avisabus.main` dentro del proceso es una condición que hay que
    mantener: hoy solo lo importa el subproceso de `test_main_composition.py`.
- **N-02 — `occupancy_simulation.py:84-89` duplica `service_day_start` de `sqlite_network.py:694-697`.**
  - Está justificado para mantener el dominio puro sin tocar `gtfs_import` (regla de alcance).
  - Candidato a unificar en `domain/services/gtfs_time.py` cuando una tarea lo permita.
- **N-03 — `set_occupancy_override.py:78`: `--clear` valida que la línea exista en la red activa.**
  - Si una línea desaparece tras reimportar el GTFS, su forzado no se puede borrar desde la CLI
    (código 2), aunque siga en `--list` hasta caducar. El efecto es inocuo: el sensor ya no
    encuentra viajes de esa línea.
  - Design §5 no distingue modos. La decisión del implementer es defendible.
  - Conviene aclararlo en la v1.1 (p. ej., permitir `--clear` de líneas con forzado aunque no
    existan).
- **N-04 — `simulated_sensor.py:78-86`: la vigencia del forzado se evalúa con `clock.now()`, no con `at`.**
  - Si el sensor se consulta para un instante futuro (p. ej. el ETA de un autobús que llega en
    20 min), se aplica el forzado vigente ahora.
  - Coherente con el design ("con forzado activo") y con la caché por `Clock`. Hay que tenerlo
    presente al integrar en `stop_arrivals_api`.
- **N-05 — `progress/impl_occupancy_sensor.md` (sección Hypothesis) afirma que "no se crea `.hypothesis/`".**
  - Existe `backend/.hypothesis/`, con `constants/` y `unicode_data/` desde el 2026-10-31 23:49.
    Hypothesis genera esa caché aunque `database=None`.
  - Se autoexcluye con su propio `.gitignore` y no aparece en `git status`, así que no afecta al
    repositorio. Solo es inexacta la afirmación.
- **N-06 — `test_simulated_occupancy_sensor.py:70`: el fake de red se pasa con `# type: ignore[arg-type]`.**
  - `FakeTripNetwork` solo implementa `trip_stop_times` y `trip_line`.
  - Mejora opcional: que el sensor dependa de un `Protocol` mínimo, como hace `LineCatalog` en los
    casos de uso. No cambia el contrato del design.

## Lista de comprobación (docs/verification.md §4)

- **Contrato.** Comportamiento acorde a los AC. Interfaces, tabla, CLI, errores y configuración
  coinciden con el design. Excepciones: la firma de `progress` (SP-02) y SP-01.
- **Arquitectura.**
  - `domain/` es puro: lint-imports en verde, y `zoneinfo`/`hashlib` son de la biblioteca estándar.
  - Fuera de `main.py` y de los contenedores de la CLI se usan puertos.
  - No hay `datetime.now()` ni `time.time()` fuera de `SystemClock`.
  - Los repositorios síncronos llamados desde código `async` se ajustan a ADR-012.
- **Tests.**
  - Sin red ni sleeps: todo el tiempo pasa por `FakeClock`. Hypothesis es determinista
    (`derandomize=True`).
  - Fixtures: `gtfs_mini` (origen ya documentado) y los fakes de `tests/support/occupancy.py`.
- **Privacidad y seguridad.**
  - Los ficheros nuevos no añaden logs.
  - `UnknownLineError` lleva la línea en un atributo, no en el mensaje.
  - Las entradas de la CLI se validan (`min=1`, enum, combinaciones).
  - No hay datos personales: RNF-06 no aplica.
- **Frontend.** No aplica.
- **Convenciones.**
  - Glosario: `Occupancy`/`OccupancyLevel`, `FREE`/`MEDIUM`/`FULL`.
  - Conventional Commits con el ámbito `occupancy_sensor` y la tarea citada.
  - Las variables nuevas están documentadas en `.env.example`.
  - Código en inglés y progreso en castellano.
- **Alcance.** No hay cambios fuera de la feature.
