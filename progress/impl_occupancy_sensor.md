# Implementación: occupancy_sensor
Spec: specs/occupancy_sensor/ (v1.2, APPROVED) · Ciclo de revisión: 0 (v1.2) · Agente: implementer · Fecha: 2026-11-03

> **v1.2 (2026-11-03, rama `fix/sae-occupancy-v1.3`):** solo T-09 (AC-15, NB-1 de la revisión
> v1.1) y T-10. T-01…T-08 son de versiones anteriores.

> **v1.1 (2026-11-02, rama `fix/bloque-1-ajustes`):** solo T-07 (SP-01 / O-01) y T-08. T-01…T-06
> son de la v1.0 (revisada y aprobada).

## Tareas
- [x] T-01 Modelos de ocupación, `classify_occupancy` y validación de configuración (AC-01, AC-02, AC-03)
      (commit 4552442)
- [x] T-02 Funciones de simulación puras con tests de propiedades (AC-05, AC-06, AC-07, AC-10;
      también progreso, AC-08) (commit 91181de)
- [x] T-03 Puertos `OccupancySensor` / `OccupancyOverrideRepository` y `NetworkRepository.trip_line`
      (commit 0262aac)
- [x] T-04 `SimulatedOccupancySensor` (AC-04, AC-08, AC-09, AC-11, AC-14) (commit eeace86)
- [x] T-05 Repositorio SQLite de forzados, casos de uso y CLI `occupancy override` (AC-11, AC-12,
      AC-13, AC-14) (commit c5bd661)
- [x] T-06 `.env.example`, composición en `main.py` y verificación completa (commit 4e7aff3 y el
      commit de este fichero)
- [x] T-07 (v1.1, SP-01) Proporciones del forzado derivadas de los umbrales (punto medio de cada
      banda, con ajuste por redondeo); AC-03 ampliado; tests de propiedades (AC-03, AC-11)
      (commit 4d09934)
- [x] T-08 (v1.1) Verificación completa: `./init.sh verify` en verde (commit de este fichero)
- [x] T-09 (v1.2) Test de composición con `AVISABUS_OCCUPANCY_*` no estándar
      (`tests/integration/test_occupancy_composition.py`, AC-15); sin cambios de composición
      (commit c0dbd32)
- [x] T-10 (v1.2) Verificación completa: `./init.sh verify` en verde (commit de este fichero)

Tests nuevos: `tests/unit/test_occupancy_classifier.py`, `tests/unit/test_occupancy_simulation.py`,
`tests/unit/test_simulated_occupancy_sensor.py`, `tests/unit/test_set_occupancy_override.py`,
`tests/integration/test_occupancy_override_repository.py`, `tests/integration/test_cli_occupancy.py`,
`tests/integration/test_main_composition.py`, tests `trip_line` en
`tests/integration/test_network_repository.py`, fakes en `tests/support/occupancy.py`.

## Decisiones locales

### v1.2 (T-09)
- **Cómo se comprueba "el sensor compuesto los usa" (AC-15):** como en
  `test_main_composition.py`, se importa `avisabus.main` en un subproceso (directorio de trabajo
  sin `.env`, `AVISABUS_ENV=test`, replay sobre la sesión E-01) con capacidad 60, asientos 20,
  semilla `composition-test` y umbrales 0,30 / 0,70, sobre una copia de una BD con `gtfs_mini` y
  forzados que no caducan (2100-01-01) para las líneas 93 (`FULL`), 70 (`FREE`) y C2 (`MEDIUM`).
  El subproceso lee con `main.occupancy_sensor` 3 viajes de cada línea forzada y 20 de la 98 (sin
  forzado), a mitad de su recorrido programado, e imprime también `main.occupancy_thresholds`
  (lo que `main.py` expone para el clasificador). El test compara cada lectura (capacidad,
  asientos, ocupados) con la de un `SimulatedOccupancySensor` construido en el propio test con los
  valores configurados, `FakeClock` y los mismos forzados; además, los forzados dan
  `override_occupied(nivel, 60, umbrales)` y se clasifican en su nivel con los umbrales
  configurados.
- **Test guarda:** comprueba que dejar **cualquiera** de los cuatro valores (capacidad, asientos,
  semilla, umbrales) en su valor por defecto cambia alguna lectura de referencia, para que el
  test principal no pueda pasar por casualidad. Lo he comprobado además con 5 mutaciones de
  `main.py` (umbrales del sensor, capacidad, asientos, semilla y `occupancy_thresholds`
  exportado, cada uno a su valor por defecto): las 5 hacen fallar el test principal.
- **Sin "rojo" previo:** la composición ya era correcta (T-07 había cableado los umbrales), así que
  el test pasó a la primera; "ajuste de composición si falla" no ha hecho falta y `main.py` no
  cambia. Las mutaciones anteriores sustituyen al rojo.
- **Reloj en el subproceso:** `main.py` usa `SystemClock` (es la raíz de composición real). El
  resultado no depende de él: las lecturas se piden con `at` explícito y los forzados no caducan
  hasta 2100 (el reloj solo decide la vigencia del forzado y la caché de 5 s).
- **CLI (ver "Bloqueos", O-02):** el contenedor de la CLI no compone ningún sensor ni clasificador
  (solo los casos de uso de forzado, que guardan el nivel, no plazas). Un tercer test lo fija:
  ningún campo de `CliContainer` es un `SimulatedOccupancySensor` ni `OccupancyThresholds` ni se
  llama `*sensor*`/`*threshold*`; si eso cambia, el test obliga a escribir uno como el de
  `main.py`.

### v1.1 (T-07)
- **`override_occupied(level, capacity, thresholds) -> int | None`** es una función pura de
  dominio en `domain/services/occupancy_classifier.py`, junto a `classify_occupancy` (comparten la
  misma regla de clasificación, `_level`). Aplica design §3 "Forzado": `round(capacity × r)` con
  `r` el punto medio de la banda y, si el redondeo saca el valor de la banda, avanza de uno en uno
  hacia ella; devuelve `None` si la salta (banda sin enteros). Se usa en dos sitios para que la
  validación y el sensor no puedan discrepar:
  - `Settings._check_occupancy` (AC-03 v1.1): `ConfigurationError` si algún nivel da `None`. El
    mensaje nombra el nivel y las tres variables con sus valores (no son secretos).
  - `SimulatedOccupancySensor`: precalcula las plazas de cada nivel al construirse.
  El módulo no figura en la lista de ficheros de T-07; lo anoto por eso. Se sustituye la constante
  `OVERRIDE_RATIOS` (0,20 / 0,65 / 0,95) del sensor.
- **`SimulatedOccupancySensor` recibe `thresholds: OccupancyThresholds`** (argumento obligatorio
  por nombre, sin valor por defecto, para que nadie lo cablee sin los umbrales configurados).
  El design no fija el constructor. Cambios derivados:
  - `main.py` (`build_occupancy_sensor`) pasa `settings.occupancy_thresholds()`; `main.py` no está
    en la lista de ficheros de T-07, pero sin él los forzados usarían otros umbrales que la API.
  - Si se construye con una configuración en la que algún nivel no tiene enteros, lanza
    `ValueError` (error de cableado: `Settings` ya la rechaza al arrancar).
- **Redondeo:** `round` de Python (al par en los empates), el mismo que ya usaba la v1.0 y que
  escribe el design. Con los valores por defecto (capacidad 90, umbrales 0,50 / 0,85) los forzados
  dan **22 / 61 / 83** plazas (antes 18 / 58 / 86).
- **Tests actualizados (de esta feature):** los valores fijos 18/58/86 de
  `test_simulated_occupancy_sensor.py` y `test_cli_occupancy.py` pasan a 22/61/83; los sensores de
  `test_cli_occupancy.py` reciben `OccupancyThresholds()`.
- **Tests nuevos:**
  - AC-03 (`test_occupancy_classifier.py`): casos sin enteros en MEDIUM (capacidad 3 con
    0,50/0,60, el ejemplo del design; capacidad 1 con los umbrales por defecto; capacidad 10 con
    0,51/0,59), capacidades pequeñas válidas, y una propiedad con Hypothesis: `Settings` rechaza
    la configuración **si y solo si** algún nivel no es alcanzable, comprobado por fuerza bruta
    sobre `0 … capacidad` con `classify_occupancy`.
  - AC-11: valores con los umbrales por defecto y con 0,40/0,90, el caso de ajuste (capacidad 4,
    0,25/0,50: el MEDIUM pasa de 2, que es FULL, a 1), banda vacía → `None`, y dos barridos con
    Hypothesis (capacidad 1–200, umbrales en milésimas con `0 < medio < lleno ≤ 1`): sobre
    `override_occupied` y sobre el sensor completo con un forzado; el nivel forzado coincide
    siempre con la clasificación cuando la configuración es válida.
  - Generador `threshold_configurations` y `reachable_levels` (fuerza bruta) en
    `tests/support/occupancy.py`, compartidos por ambos ficheros.
- **`.env.example`:** el comentario de los umbrales añade la nueva condición de arranque y que los
  forzados usan el punto medio de cada banda.
- Las capacidades de 1 plaza con los umbrales por defecto pasan a ser inválidas (no hay ningún
  entero MEDIUM). Es lo que pide AC-03 v1.1.

### v1.0
- **`ConfigurationError`** se define en `avisabus/config.py` y la lanza un `model_validator` de
  `Settings` (AC-03). Es el mismo nombre y sitio que usa la rama `feat/stop_tokens_qr`, sin depender
  de ella; al fusionar ambas habrá un conflicto trivial en `config.py`. La spec no trata
  `capacity <= 0` ni `seats < 0`: se rechazan con restricciones de `Field` (`gt=0`, `ge=0`), como
  `gtfs_batch_size`, y dan `ValidationError` de Pydantic.
- **`.env.example` en T-01 y no en T-06.** El test existente `test_env_example_documents_every_setting`
  exige documentar cada campo de `Settings` en el mismo commit que lo añade.
- **Firma de `progress`.** El design la escribe `progress(trip_stop_times, at)`, pero también dice
  "con el día de servicio". Queda `progress(trip_stop_times, service_date, at)`. El inicio del día de
  servicio es "mediodía local − 12 h" en Europe/Madrid, la misma regla que el `service_day_start` del
  adaptador de `gtfs_import`. Se reimplementa en `domain/services/occupancy_simulation.py` para que
  el dominio siga puro y no tocar el adaptador. Casos que la spec no fija:
  - viaje con una sola hora (`último ≤ primero`): `p = 1` si `s_at ≥ primero` y `0` si no;
  - lista vacía: `ValueError`. El sensor devuelve `None` antes de llegar aquí.
- **`hour_factor`.** Los `datetime` con zona se convierten a Europe/Madrid y los naive se toman como
  hora local. El fin de semana se mira en el día local. Los festivos no se tienen en cuenta: la
  spec no los menciona.
- **`trip_factor`.** `u` son los primeros 8 bytes (big-endian) de `sha256(f"{seed}:{trip_id}:{service_date}")`
  divididos entre 2⁶⁴. La fecha va en ISO.
- **Caché de forzados (decisión permitida, design §8).**
  - Guarda una instantánea `{línea: forzado}` con su `fetched_at`.
  - Se refresca cuando han pasado ≥ 5 s según `Clock`, o si el reloj retrocede.
  - Además, los forzados cacheados se filtran por `expires_at > clock.now()`, así que la caducidad
    es exacta aunque caiga dentro de la ventana de 5 s.
  - `trip_line` solo se consulta si hay forzados activos.
  - La caducidad se compara con `clock.now()`, no con `at`.
  - `measured_at = at`.
- **Tabla `occupancy_override` con su propio `MetaData`** (`occupancy_metadata`). `init_db` la crea
  junto a la de red con `create_all`. Ir al `metadata` compartido rompía dos invariantes de
  `gtfs_import` (tests de `test_db.py`):
  - el `metadata` de red solo tiene tablas versionadas por `feed_version_id`;
  - `VERSIONED_TABLES` sale de ese `metadata` y se usa para purgar.

  Un test comprueba que un forzado sobrevive a una reimportación del GTFS.
- **Repositorio SQLite.** `set` es un upsert por línea. `active(now)` filtra en Python comparando
  `datetime`, no texto ISO, para no depender de la precisión. Las filas caducadas no se borran: la
  spec no lo pide.
- **Casos de uso.**
  - Los tres van en `application/set_occupancy_override.py` (design §2) y son `async`.
  - Dependen de un `Protocol` local `LineCatalog`, que es el subconjunto `get_line` de
    `NetworkRepository`.
  - La línea se valida con `get_line` tanto al forzar como al limpiar. Así se aplica design §5
    ("Línea inexistente en `override`" → error, código 2) a todo modo con `--line`.
  - `minutes ≤ 0` lanza `ValueError`. En la CLI, `--minutes` lleva `min=1`, así que da código 2.
  - `UnknownLineError(DomainError)` está en `domain/errors.py`, con la línea en un atributo y no en el
    mensaje.
- **CLI.**
  - Las combinaciones inválidas salen con código 2 (`typer.BadParameter`): `--list` con otras
    opciones, `--clear` con `--level`/`--minutes`, falta `--line` o falta `--level`.
  - `--level` no distingue mayúsculas.
  - Los mensajes van en castellano, como `gtfs`.
  - La caducidad se muestra en UTC (`AAAA-MM-DD HH:MM UTC`), como `gtfs info`.
  - `--list` ordena las líneas en orden natural.
  - `--clear` sin forzado previo informa y sale con 0.
- **`main.py`.**
  - Construye `occupancy_sensor` (`build_occupancy_sensor`) y `occupancy_thresholds` como nombres
    del módulo, para que `stop_arrivals_api` los inyecte en su caso de uso. No se añade
    `app.state` ni otro mecanismo de inyección: lo decidirá esa feature.
  - Llama a `init_db` al arrancar la API, para que `occupancy_override` exista aunque no se haya
    ejecutado la CLI tras actualizar.
  - Se prueba en un subproceso con BD y directorio temporales: no toca `data/` ni el `.env` del
    desarrollador.
- **Hypothesis.** Es dependencia de desarrollo (design §7). Se usa con `derandomize=True` y
  `database=None`: los resultados son reproducibles y no se crea `.hypothesis/`.

## Bloqueos
Ninguno abierto.

- **O-02 (v1.2, no bloqueante; para la persona/spec-writer y el reviewer).** AC-15 y T-09 dicen
  que el sensor y el clasificador se componen "en `main.py` (y en el contenedor de la CLI)", pero
  el contenedor de la CLI (`adapters/inbound/cli/container.py`) no construye ni sensor ni
  clasificador: `occupancy override` solo guarda el nivel forzado y su caducidad, y ningún
  comando lee ocupaciones. Lo he leído como "allí donde se compongan", que en la CLI se cumple
  sin nada que pasar; no he añadido un sensor a la CLI porque ningún comando lo usaría (sería
  inventar comportamiento). Lo cubre el test guarda de la CLI. Propuesta: precisar en AC-15
  "(y en el contenedor de la CLI, si compone alguno)" o quitar el paréntesis.

- **O-01 — RESUELTA en la spec v1.1** (SP-01 de la revisión; opción (a), punto medio de cada banda,
  más la ampliación de AC-03). Implementada en T-07. Texto original:

- **O-01 (AC-11 frente a design §3 "Forzado" con umbrales no por defecto).**
  - AC-11 exige que, con un forzado activo, la lectura quede "clasificada como `FULL`" (y lo mismo
    para `FREE` y `MEDIUM`).
  - El design fija `r = 0,20 / 0,65 / 0,95` con independencia de los umbrales.
  - Con los umbrales por defecto (0,50 / 0,85) se cumple siempre. Con umbrales válidos según AC-03
    pero distintos, no. Por ejemplo, `full = 0,99` hace que el `FULL` forzado (0,95) se clasifique
    como `MEDIUM`. Lo mismo pasa con `medium ≤ 0,20` o `medium > 0,65`.
  - Se ha implementado tal como dice el design. Los tests de AC-11 usan los umbrales por defecto.
  - Propuestas (a elegir):
    - (a) calcular `r` a partir de los umbrales (p. ej., el punto medio de cada banda);
    - (b) que AC-03 restrinja los umbrales para que las `r` fijas caigan en su banda;
    - (c) aclarar en AC-11 que se refiere a los umbrales por defecto.

## Verificación

### v1.2 (2026-11-03, rama `fix/sae-occupancy-v1.3`, tras el commit c0dbd32)
- T-09: `uv run pytest tests/integration/test_occupancy_composition.py` → 3 passed (ejecutado
  solo, falla el umbral global de cobertura, como siempre con los comandos de tarea).
- T-10: `./init.sh verify` → **todo en verde**: format, lint, mypy (75 ficheros), lint-imports
  (2 contratos), pytest 665 passed / 2 deselected (cobertura `domain`+`application` 99,52 %);
  frontend format/lint/types/tests (7)/build; `feature_list.json` y trazabilidad AC→test OK
  (incluido `occupancy_sensor.AC-15`).

### v1.1 (2026-11-02, rama `fix/bloque-1-ajustes`, tras el commit 4d09934)
- T-07: `uv run pytest tests/unit/test_simulated_occupancy_sensor.py` → 27 passed (ejecutado solo,
  el umbral de cobertura global falla, como ya pasaba con los comandos de tarea: `addopts` mide
  `domain`+`application` sobre la suite completa). Los tests nuevos fallaban antes del cambio
  (error de importación de `override_occupied` y valores 18/58/86).
- T-08: `./init.sh verify` → **todo en verde**: format, lint, mypy (75 ficheros), lint-imports
  (2 contratos), pytest 645 passed / 2 deselected (cobertura `domain`+`application` 99,52 %;
  `occupancy_classifier.py` al 100 %); frontend format/lint/types/tests (7)/build;
  `feature_list.json` y trazabilidad AC→test OK.

### v1.0
`./init.sh verify` (2026-10-31, tras el commit 4e7aff3): **todo en verde**.

```
OK   backend: format
OK   backend: lint            (ruff: All checks passed!)
OK   backend: types           (mypy: no issues, 56 source files)
OK   backend: architecture    (lint-imports: 2 kept, 0 broken)
OK   backend: tests           (422 passed, 2 deselected [slow]; cobertura domain+application 99.44 %)
OK   frontend: format / lint / types / tests (7 passed) / build
OK   harness: feature_list.json
OK   harness: trazabilidad AC→test  (occupancy_sensor.AC-01…AC-14 citados)
OK   verify: todo en verde
```

Prueba manual de la CLI con una BD temporal en el scratchpad (nunca en `data/`), con `gtfs_mini`
importado:
- `--line 93 --level FULL --minutes 30`, `--line C2 --level free` y `--list` muestran los forzados
  con su caducidad;
- `--line 999 --level FULL` sale con código 2;
- `--line 93 --clear` elimina el forzado;
- con `AVISABUS_OCCUPANCY_SEATS=100`, la CLI no arranca (`ConfigurationError`).
