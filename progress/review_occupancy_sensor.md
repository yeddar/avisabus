# Revisión: occupancy_sensor
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
