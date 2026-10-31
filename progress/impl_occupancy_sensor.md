# Implementación: occupancy_sensor
Spec: specs/occupancy_sensor/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-10-31

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

Tests nuevos: `tests/unit/test_occupancy_classifier.py`, `tests/unit/test_occupancy_simulation.py`,
`tests/unit/test_simulated_occupancy_sensor.py`, `tests/unit/test_set_occupancy_override.py`,
`tests/integration/test_occupancy_override_repository.py`, `tests/integration/test_cli_occupancy.py`,
`tests/integration/test_main_composition.py`, tests `trip_line` en
`tests/integration/test_network_repository.py`, fakes en `tests/support/occupancy.py`.

## Decisiones locales
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
Ninguno que impida cerrar la feature. Hay una observación para la persona, por si quiere una spec v1.1:

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
