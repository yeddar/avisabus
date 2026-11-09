# Revisión: position_estimation
Ciclo: 1 (v1.4) · Fecha: 2026-11-09 · Agente: reviewer
Spec revisada: `specs/position_estimation/` v1.4 (APPROVED, PR #51) · Rama:
`feat/position_estimation-v1.4` (HEAD `e49dc19`; código y tests en `1ca3b69`) · Base:
`origin/develop` (`7b7660e`). Alcance de esta revisión: T-11 y la re-verificación de T-08 de la
v1.4. Las revisiones de la v1.3, la v1.2 y la v1.1 se conservan más abajo, sin cambios.

## Veredicto: APPROVED

No hay hallazgos bloqueantes. `distance_to_stop_m` está en metros reales: sobre el feed real, las
8070 estimaciones que recalculé por mi cuenta coinciden con el código, y las paradas quedan donde
dice su geometría (mediana de 3,9 m hasta la parada real). AC-17 sigue con 139 pares y 5 excluidos,
y las distancias bajan en la proporción esperada. `CI=1 ./init.sh verify --e2e` está en verde.
Hay 6 observaciones no bloqueantes. Las tres del implementer son **notas, ninguna es un CP-3**
(N-01…N-03). La más visible para la persona es N-01: las capturas del mapa muestran "3,4 km" donde
el backend v1.4 daría unos 1,2 km.

## Matriz AC → evidencia (v1.4)

La v1.4 solo cambia el comportamiento de AC-06. Los demás AC conservan la evidencia de las matrices
anteriores y sus tests vuelven a pasar. AC-05 y AC-17 se añaden por el efecto del cambio.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-06, forma en metros aunque el feed traiga `shape_dist_traveled` | `backend/tests/unit/test_position_estimator.py:332` (`uniform` y `by_segment`), `:360`, `:374` | OK | Con el feed ×3 y con escala distinta por kilómetro, el resultado es el mismo: 2500 m recorridos y 1500 m a la parada. Valores esperados calculados a mano. El mutante E1 (forma con los valores del feed) muere. |
| AC-06, parada interpolada entre los valores del feed de la forma | `backend/tests/unit/test_geometry.py:94`, `:101`, `:113`; `test_position_estimator.py:345` | OK | Cubren escala uniforme, escala por tramo, forma con esquina y paradas dentro de un tramo. G1 (escala global), G7 y G8 (unidades del feed) mueren. |
| AC-06, acotado a los extremos y casos degenerados | `test_geometry.py:121`, `:130`, `:142`, `:149` | OK | Valores antes y después de la forma, punto único, lista vacía, forma vacía y punto sin valor. G2, G3, G4, G9, G10 y G11 mueren. Ver N-05 para los valores iguales. |
| AC-06, proyección si los horarios o la forma no traen el dato | `test_position_estimator.py:259`, `:276`, `:360`, `:374`, `:390`, `:473` | OK | E4 y E6 mueren. El caso de horarios **parcialmente** sin dato no tiene test (N-04), aunque el código lo resuelve bien. |
| AC-06, distancias no decrecientes | `test_position_estimator.py:398`; `test_geometry.py:229`, `:250` | OK | La parada C retrocede en el feed y se mantiene en la distancia de B. E2 (sin `max`) muere. |
| AC-06, tolerancia de 2 % o 10 m frente a la medida sobre la forma | `backend/tests/integration/test_position_api.py:143` | OK | Replay de 75 ciclos con las líneas 70 y 93, y haversine propia del test. Exige más de 100 comparaciones y alguna distancia de más de 1000 m. Por sí solo detecta un error de escala del 3 % (E7). Cubre solo la parada 508; ver N-03. |
| AC-05 (tests adaptados a metros) | `test_geometry.py:165-208` | OK | Pasan `cumulative_distances` en lugar de `shape_distances`, sin cambiar las aserciones. Redacción de AC-05: N-02. |
| AC-17 | `backend/tests/integration/test_position_real_session.py:147`, `:160`, `:167` | OK | **139 pares y 5 excluidos**, igual que en `origin/develop`. Ver la tabla de abajo. |

**AC-17 antes y después** (ejecutado en una copia de `origin/develop` y en esta rama):

| Par excluido | `develop` | v1.4 | Cociente |
|---|---|---|---|
| 93, ciclos 14→15 | 0→4765 | 0→1496 | 3,19 |
| 70, ciclos 23→24 | 0→1288 | 0→458 | 2,81 |
| 70, ciclos 54→55 | 0→1380 | 0→485 | 2,85 |
| 70, ciclos 58→69 | 0→2752 | 0→981 | 2,81 |
| 70, ciclos 70→71 | 2707→4729 | 967→1447 | 2,80 y 3,27 |

Los cocientes encajan con la escala de las formas de `gtfs_mini` (entre 2,69 y 3,40; forma de la 93:
2,79; formas de la 70: 3,27 y 3,40) y con que la escala varía a lo largo de cada forma.

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e`, con el puerto 4173 libre: **"verify: todo en verde", código 0**.
  - backend: format, lint, types y architecture OK; tests OK (1426 passed, 6 deselected).
  - frontend: format, lint y types OK; tests OK (55 ficheros, 563 passed y 2 skipped); build + bundle
    OK (5 tests); e2e + a11y OK (126 passed).
  - harness: `feature_list.json` y trazabilidad OK.
- Tras la verificación, `git status` solo muestra `qr/`, que estaba antes.
- Sin cambios fuera del alcance: el diff respecto a `origin/develop` toca `geometry.py`,
  `position_estimator.py`, sus tres ficheros de tests y los ficheros de progreso y estado. No toca
  `frontend/`, `specs/` ni `docs/`. Los commits siguen Conventional Commits y citan la tarea.

### Comprobación con el feed real (`data/gtfs/emt`, solo lectura)

Scripts en el scratchpad, con haversine e interpolación propias:
`/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/real_feed_check.py`
y
`/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/real_feed_e2e.py`.

| Comprobación | Resultado |
|---|---|
| Datos | 103 formas, 20 598 viajes, 94 patrones, 2281 paradas |
| Escala del feed frente a la longitud real | mín. 1,64, mediana 2,97, máx. 4,25 (coincide con `gtfs_import` v1.4) |
| Precondiciones | 0 formas con valores decrecientes, 0 tramos de longitud 0 en el feed, 0 secuencias de paradas decrecientes; 1 parada más allá del final de su forma |
| `feed_to_metres` frente a mi interpolación por recorrido lineal | diferencia máxima 0,0 m |
| `estimate_position` en 8070 instantes (viaje, parada objetivo, tramo) frente a mi cálculo | `distance_to_stop_m` y posición: diferencia máxima 0,0 m. Comprueba la implementación, no la interpretación de la spec: uso la misma fórmula de AC-06 |
| Distancia antigua frente a la nueva, por estimación | mediana 3,05, entre 1,06 y 9,92. La escala varía mucho por tramo, y por eso hace falta interpolar por tramo |
| **Punto que da el feed frente a la parada real** (comprobación geométrica independiente de la fórmula) | mediana 3,9 m, p95 10,5 m, p99 19,0 m, máximo 54,8 m |
| Parada según el feed frente a su proyección | mediana 0,59 m, p95 7,2 m, p99 18,7 m, máximo 337,9 m (confirma las cifras del implementer) |

### Otros usos de `shape_dist_traveled` en `backend/src`

No queda ninguno tratado como metros.

- Solo importan y leen el valor `gtfs_rows.py:168,198`, `sqlite_network.py:130,153,573,592` y los
  modelos. Su único consumidor es `position_estimator.py:117-119`, a través de `feed_to_metres`.
- `get_stop_arrivals`, `watch_passages` y `trip_matcher` no usan distancias.
- `shape_distances` ya no aparece en el código ni en los tests.
- El contrato sigue igual y ahora es correcto: `routes/position.py:53` documenta "in metres", y
  `openapi.json` y `schema.d.ts` no cambian.
- `passenger_map_view` solo da formato al valor (`summary.ts:107`). `NOT_STARTED` no lo muestra.

### Pruebas de mutación (copia en el scratchpad)

Copia con `git archive` de `HEAD` en
`/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/v14/`,
ejecutada con el `.venv` del repositorio y `PYTHONPATH` apuntando a la copia (comprobado con
`avisabus.__file__`). Script:
`/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/mutate_v14.py`.
Cada mutante se ejecuta con `-k "geometry or position"`, y los supervivientes con la suite completa.
Al final, `diff -r` confirma que `src/` de la copia coincide con el repositorio.

| Mutante | Resultado |
|---|---|
| G1 escala global de la forma | Muerto |
| G2 sin acotar al inicio | Muerto |
| G3 sin acotar al final | Muerto |
| G4 `value > feed[last]` | Muerto |
| G5 `value < feed[0]` | **Sobrevive** (N-05): solo difiere con un tramo de longitud 0 al inicio |
| G6 `bisect_left` | **Sobrevive** (N-05): difiere con valores iguales en el interior de la forma |
| G7 fracción 0 | Muerto |
| G8 interpolar en unidades del feed | Muerto |
| G9 punto único devuelve el feed | Muerto |
| G10 acepta puntos sin valor | Muerto |
| G11 sin comprobar forma vacía | Muerto |
| G12 sin `min(…, last - 1)` | Sobrevive: equivalente con el feed no decreciente |
| E1 forma con los valores del feed | Muerto |
| E2 sin `max` acumulado | Muerto |
| E3 acepta horarios con valores parciales | **Sobrevive** (N-04) |
| E4 sin condición sobre la forma | Muerto |
| E5 proyectar siempre que haya coordenadas | Muerto (por los tests de `get_vehicle_position` y de la API; el test de tolerancia solo no lo detecta, como cabe esperar) |
| E6 `any` en lugar de `all` | Muerto |
| E7 `distance_to_stop_m` ×1,03 | Muerto, también por el test de integración solo |

15 de 19 detectados; de los 4 supervivientes, G12 es equivalente y los otros 3 se describen en N-04
y N-05.

### Lista de comprobación (`docs/verification.md` §4)

| Bloque | Resultado |
|---|---|
| Contrato | OK: AC-06 y design §3 (pasos 1, 2 y 7). `feed_to_metres` sustituye a `shape_distances`, como pide el design §2 |
| Arquitectura | OK: `domain/` solo usa la biblioteca estándar; `lint-imports` en verde; sin reloj real |
| Tests | OK: sin red ni reloj real; los tests de AC-06 calculan los valores esperados a mano y fallan con mutantes de escala |
| Privacidad y seguridad | No aplica: sin identificadores nuevos ni logs nuevos |
| Frontend | Sin cambios de código; ver N-01 |
| Convenciones | OK |

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **N-01 (O-01) Las fixtures y las capturas del mapa muestran una distancia engañosa. Nota, no
  CP-3.** La spec es correcta y ningún AC fija estos datos; es un resto de datos de prueba.
  - Medí sobre `shape-93.json`: `position-en-route.json:31` dice 3403 m y son **1242 m**;
    `position-not-started.json:31` dice 4251 m y son **1835 m**. El implementer daba unos 1248 m y
    1839 m porque medía hasta el vértice más cercano; el orden de magnitud es el mismo.
  - **Sí hay valores engañosos en lo que se ve.** Las capturas que muestran el resumen en ruta dicen
    "3,4 km", y el backend v1.4 daría unos 1,2 km: lo vi en
    `frontend/test-results/passenger_map_view/pixel/map-en-route-es.png`. Las generan
    `map-en-route-{es,ca}`, `map-focused-es` y `map-zoom-focused-es` (`frontend/e2e/map-view.spec.ts:248,406,420`)
    en los tres perfiles. No están versionadas, pero son la evidencia de `passenger_map_view.AC-15`
    y se revisan en CP-6. `map-not-started-es` no muestra la distancia.
  - **También engaña el texto de origen.** `frontend/e2e/fixtures/index.ts:6-9` y
    `frontend/src/test/fixtures/api/index.ts:6-9` presentan estas fixtures como "answers of the real
    backend", lo que ya no es cierto para las distancias.
  - Los tests **no** dan una falsa garantía: los "3,4 km" (`map-view.spec.ts:52,66`,
    `summary.test.ts:35,41,155`, `PositionSummary.test.tsx:28,37`, `MapPage.test.tsx:153,348,364,394`)
    solo comprueban el formato y la sustitución del dato simulado. Ningún test compara las fixtures
    con el backend.
  - T-11 no incluye `frontend/`, así que no era su alcance. Recomendación: regenerar las dos fixtures
    y ajustar esos textos en una tarea aparte, antes de la demo de CP-6.
- **N-02 (O-02) Texto residual en la spec. Nota, "Problema de spec" de redacción, no CP-3.**
  `specs/position_estimation/requirements.md:13-14` dice "`shape_dist_traveled`, en metros en el feed
  de EMT", lo que es falso según `gtfs_import` v1.4 y `docs/vision.md:77`. AC-05 (`:61-63`) dice
  literalmente que se interpola entre los puntos "cuyo `shape_dist_traveled`" contienen `d`, y `d`
  ya está en metros. No queda ninguna decisión abierta: AC-06 v1.4 ("aunque el feed traiga
  `shape_dist_traveled`") y el design §3 (pasos 1 y 6) fijan la interpretación, y el código la
  sigue. Conviene corregir esas dos frases en la próxima revisión de la spec, porque `driver_session`
  remite a esta.
- **N-03 (O-03) Alcance de la tolerancia de AC-06. Nota, no CP-3.** AC-06 tiene una lectura
  coherente, y es la implementada: primero define dónde está cada parada (interpolando el feed), y la
  tolerancia comprueba que la distancia hasta ese punto está en metros. Con esa lectura el error es
  0 m. Si la referencia fuera la proyección geométrica de la parada, ninguna implementación que siga
  AC-06 podría cumplir la tolerancia en todos los casos:
  - 290 de 28 993 pares de paradas (1,0 %) quedan fuera de 2 % o 10 m.
  - Sin la parada 1282 son 264 pares, con un error máximo de 91 m.
  - Con la cabecera 1282 (forma `1030_2278_1282`), el error llega a 339 m (un 12,6 % en ese par).

  He comprobado el caso de la 1282: la forma pasa a 27,4 m de la parada en el metro 5025, da una
  vuelta a la manzana y termina a 49,6 m de la parada, en el metro 5419. El feed sitúa la parada al
  final de la forma. Los 337,9 m salen de que la proyección de la cabecera queda fijada en la parada
  anterior, la 1283 (metro 5081,5), por la restricción monótona. Por tanto, la distancia del feed no
  es un error del código y el impacto se limita a una cabecera final. Si se quiere evitar la duda, basta con añadir a AC-06 "hasta el
  punto que da su `shape_dist_traveled`" en la próxima revisión.
- **N-04 Test ausente para horarios con valores parciales.** El mutante E3
  (`position_estimator.py:118`, sin `len(feed) == len(ordered)`) sobrevive a toda la suite. El código
  es correcto: lo comprobé con horarios parciales, que se proyectan si hay coordenadas y dan
  `missing_stop_coordinates` si no. El feed real no tiene este caso. Bastaría un test parametrizado.
- **N-05 D-25 no está cubierta por tests y no se aplica al inicio de la forma.** D-25 dice que el
  caso de un valor igual a un tramo de longitud 0 "se prueba con una forma sintética", pero
  `test_geometry.py:130` solo tiene valores iguales al final, que resuelve la cota final, no
  `bisect_right`. Por eso G6 sobrevive (con el feed 0, 100, 100, 200 y el valor 100, el código da
  2000 m como dice D-25, pero ningún test lo fija). Además, con el tramo de longitud 0 al inicio
  (`geometry.py:75`), el código devuelve el **primer** punto, y no el último como dice D-25 (G5
  sobrevive). El feed real no tiene tramos de longitud 0 (0 en 103 formas), así que no tiene efecto.
- **N-06 Reutilización en `driver_session`.** `feed_to_metres` sirve tal cual (`geometry.py:57`,
  misma firma que pide el design), pero quien la reutilice debe tener en cuenta tres cosas:
  1. Aplicar el `max` acumulado, que está fuera de la función (D-23; el mutante E2 confirma que hace
     falta).
  2. Comprobar antes que todos los puntos de la forma traen el dato, porque si no lanza `ValueError`
     (`geometry.py:67-68`), que no es `PositionNotEstimableError`.
  3. La función asume que el feed de la forma no decrece, sin decirlo en su docstring. Con una forma
     decreciente el resultado no es fiable; el feed real cumple la condición (0 de 103).

  Como `_stop_distances` es privada y `specs/driver_session/design.md:101-103` pide hacerlo
  "exactamente como" aquí, el riesgo es duplicar esa lógica. Conviene que la tarea de `driver_session`
  que la use la reutilice o la mueva a `geometry.py`, sin cambiar el comportamiento.

---

# Revisión: position_estimation
Ciclo: 1 (v1.3) · Fecha: 2026-11-04 · Agente: reviewer
Spec revisada: `specs/position_estimation/` v1.3 (APPROVED, PR #33) · Rama:
`feat/position_estimation-v1.3` (HEAD `088025e`; tests en `ad41c2c`) · Base: `origin/develop`
(`8757a9f`). Alcance de esta revisión: T-10 y la re-verificación de T-08 de la v1.3. Las
revisiones de la v1.2 y la v1.1 se conservan más abajo, sin cambios.

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Los dos tests de T-10 verifican lo que dicen. El de la segunda parada
mata el mutante `k <= 1` (H-02 de la v1.2), que sin él sigue sobreviviendo a la suite completa. El
del log fija el `shape_id` del viaje frente al representativo. Mis 16 mutantes mueren todos.
`CI=1 ./init.sh verify --e2e` está en verde, con 998 tests en el backend y AC-17 sin cambios. No hay
cambios de código de producción, contrato, `specs/`, `docs/` ni `frontend/`. Los hallazgos H-01…H-03
de la v1.2 quedan resueltos por la spec v1.3 y T-10. Hay 3 observaciones no bloqueantes.

## Matriz AC → evidencia (v1.3)

La v1.3 solo cambia el design y los tests. Solo tienen evidencia nueva AC-04 y AC-11. AC-01 se
añade porque el test nuevo también lo cita. Los demás AC conservan la evidencia de las matrices de
la v1.2 y la v1.1 (más abajo), y sus tests vuelven a pasar en esta ejecución.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-04 (regla `k = 0` limitada a la primera parada) | **Nuevo:** `backend/tests/unit/test_position_estimator.py:214-236` `test_with_the_target_as_the_second_stop_the_rule_of_the_first_stop_does_not_apply` (6 casos). Siguen `:169` (objetivo `E`, `NOT_STARTED`), `:193` y `:207` (objetivo `A`, `AT_STOP`) | OK | El objetivo es `B` (`k = 1`). Antes de la salida (`-600`, `-1`) y con 5 min de retraso que dejan `s = −200` (`100, 420`), el resultado es `NOT_STARTED` en `d_0 = 0`, con `distance_to_stop_m = 1000`, `stops_away = 0` y `next_stop = B`. Los valores esperados salen del viaje sintético (paradas cada 1000 m y 120 s), no del código. Fija que `AT_STOP` solo prevalece con `k = 0`, como dice el paso 5 del design. |
| AC-01 | El mismo test, casos `(0,120)`, `(60,120)`, `(119,120)` | OK | `EN_ROUTE` entre `A` y `B`: `d = 0`, `500` y `1000·119/120` (`f = (t − s_0)/(s_1 − s_0)`), y `distance_to_stop_m = 1000 − d`. El caso `0` fija la frontera `s = departure_s[0]` → `EN_ROUTE` (mata E6). |
| AC-11 (`shape_id` del viaje en `position.estimate_failed`, design §3 v1.3) | **Nuevo:** `backend/tests/unit/test_get_vehicle_position.py:363-392` `test_the_failure_is_logged_with_the_shape_of_the_trip` (4 casos: `missing_stop_times`, `empty_shape`, `missing_stop_coordinates`, `target_not_in_trip`). Siguen `:244` y `:278` (forma del viaje `null` → `shape_id: None` en el log), `:297`, `:330` y la integración `tests/integration/test_position_api.py:274` | OK | Con el viaje `93_122` (forma `shape_93_trip`, `:151`), cada motivo da `NO_VEHICLE`, `estimate = None` y la respuesta con `shape_93` (representativo). El test comprueba además que la forma del viaje es distinta de la representativa, para que la aserción no pueda pasar por casualidad. El log se compara como lista exacta: un solo evento `warning` con `{trip_id, shape_id: "shape_93_trip", reason}`. El caso `missing_stop_times` con forma no nula es nuevo: antes solo estaba con `93_123`, que no tiene forma. Que la respuesta conserve `arrival` y `vehicle` (design v1.3) no lo comprueba este test, pero sí `:249-250`, `:306-307` y la integración `:274`. |

### Pruebas de mutación (copia en el scratchpad, suite completa del backend)

Copia de `backend/` (más `frontend/src/shared/api/openapi.json` y `.env.example`, que leen dos
tests por ruta relativa) en
`/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/repo/`.
Se ejecuta con el `.venv` del repositorio y `PYTHONPATH` apuntando al `src/` de la copia (lo he
comprobado con `avisabus.__file__`). Base de la copia: 998 passed. Script:
`/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/mutate_v13.py`.
Cada mutante se aplica, se ejecuta `pytest --no-cov` completo y se revierte. Al final, `diff -r`
confirma que la copia coincide con el repositorio. El repositorio no se toca (`git status` limpio).

| Mutante | Fallan (tests de T-10 / otros) | Resultado |
|---|---|---|
| E1 `k == 0` → `k <= 1` (`position_estimator.py:57`) | 6 / 0 | **Detectado solo por el test nuevo.** Sin él (`--deselect` del test nuevo, en una segunda copia): 992 passed, el mutante sobrevive. Confirma H-02 de la v1.2 y su cierre. |
| E2 `k == 0` → `k in (0, 1)` | 6 / 0 | Detectado solo por el test nuevo |
| E3 quitar `k == 0 or` | 0 / 7 | Detectado (tests v1.2 de la primera parada y AC-07) |
| E4 `NOT_STARTED` en `d_k` | 3 / 4 | Detectado |
| E5 `NOT_STARTED` → `AT_STOP` | 3 / 3 | Detectado |
| E6 frontera `s < departure_s[0]` → `<=` | 1 / 2 | Detectado |
| E7 `stops_away` con `range(k + 1)` | 6 / 10 | Detectado |
| E8 `AT_STOP` para `k = 1` desde 60 s después de la salida | 2 / 0 | Detectado solo por el test nuevo |
| L1 log con `direction.shape_id` (el representativo) | 4 / 3 | Detectado |
| L2 log con `shape_id=None` | 4 / 3 | Detectado |
| L3 log con `shape_id or direction.shape_id` | 0 / 2 | Detectado por `:244` y `:278`. El test nuevo no lo detecta porque todos sus casos tienen forma de viaje, y esa cobertura ya existía. |
| L4 respuesta con la forma del viaje | 4 / 3 | Detectado |
| L5 `trip_id=None` en el log | 4 / 4 | Detectado |
| L6 `reason` constante | 4 / 5 | Detectado |
| L7 nivel `info` | 4 / 4 | Detectado |
| L8 `status = NO_ARRIVAL` | 4 / 5 | Detectado |

16/16 detectados. 3 (E1, E2, E8) los detecta solo el test nuevo de AC-04.

## Verificación ejecutada

1. Puerto 4173 libre (`lsof -iTCP:4173 -sTCP:LISTEN` sin resultados). `npm run build` en
   `frontend/`: OK (PWA, 11 entradas precacheadas).
2. `CI=1 ./init.sh verify --e2e`: salida "verify: todo en verde", código 0.
   - backend: format OK · lint OK · types OK · architecture OK · tests OK (998 passed, 6
     deselected; cobertura `domain` + `application` 99,46 %).
   - AC-17: "139 pairs checked, 5 excluded because the SAE minutes increased". Son los mismos 5
     pares que en la v1.1 y la v1.2, así que no hay regresión.
   - frontend: format OK · lint OK · types OK · tests OK (44 ficheros, 409 tests) · build OK ·
     e2e + a11y OK (87 passed; `test:bundle` 4 passed).
   - harness: `feature_list.json` OK · trazabilidad AC→test OK.
3. Alcance (`git diff --stat origin/develop..HEAD`): 6 ficheros. Hay 2 de tests
   (`backend/tests/unit/test_position_estimator.py` +25 y `backend/tests/unit/test_get_vehicle_position.py`
   +52), `progress/impl_position_estimation.md` y 3 del orquestador (`feature_list.json`,
   `progress/current.md`, `progress/history.md`). `git diff --name-only origin/develop..HEAD --
   backend/src frontend deploy docs specs` no devuelve nada. Así que no hay cambios de producción
   ni de contrato: el snapshot OpenAPI (`tests/integration/test_openapi_snapshot.py`) pasa contra
   `frontend/src/shared/api/openapi.json` sin cambios.
4. Spec frente a código (cierre de los hallazgos de la v1.2):
   - H-01: el design §3 v1.3 declara `logger: Logger`, igual que
     `backend/src/avisabus/application/get_vehicle_position.py:49-55`.
   - H-02: cerrado por el test nuevo de AC-04 (E1).
   - H-03: el design §3 v1.3 fija que el log lleva el `shape_id` del viaje (puede ser `null`) y que
     la respuesta lleva el representativo y conserva `arrival` y `vehicle`. El código lo cumple
     (`get_vehicle_position.py:106,111-118`) y los tests lo fijan.
5. Lista de `docs/verification.md` §4:
   - Arquitectura: sin cambios de código.
   - Tests: sin red ni reloj real (instantes sintéticos y `FakeClock` del `World`), y no son
     tautológicos (mutaciones).
   - Privacidad: el evento solo lleva `trip_id`, `shape_id` y `reason`, y la aserción de lista
     exacta impide añadir campos.
   - Frontend, a11y e i18n: no aplica, porque no hay cambios de frontend.
   - Commits: `test(position_estimation): …` y `chore(progress): …`, en Conventional Commits.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **N-01 (tests, redundancia menor).** En `backend/tests/unit/test_get_vehicle_position.py:363-392`,
  los casos `_without_coordinates` y `_without_the_target` repiten el montaje y las aserciones de
  `:297` `test_a_position_that_cannot_be_estimated_has_no_vehicle` y de `:330`
  `test_a_paired_trip_without_the_stop_has_no_vehicle`. Los cuatro afirman lo mismo sobre el log y
  la respuesta. No es incorrecto ni lo pide T-10. Se podrían eliminar los dos tests antiguos en una
  limpieza futura. No hay que hacer nada ahora.
- **N-02 (harness, ya anotado como H-04 en la v1.2, no pertenece a esta feature).** Sigue abierto:
  `bundle-budget.test.ts` lee `frontend/dist/` antes de que `init.sh` construya. Esta vez se
  ejecutó `npm run build` antes de `verify`, como se pidió, y todo está en verde.
- **N-03 (para el orquestador, fuera del alcance del reviewer).** Hay dos desajustes en
  `progress/current.md`:
  - Dice "`implementing` (solo T-10)", pero `feature_list.json` ya está en `in_review` (commit
    `088025e`).
  - La sección "Pendiente para specs futuras" sigue listando H-01…H-03 de la v1.2, que esta v1.3
    resuelve. Conviene limpiarla al pasar a `done`.

---

# Revisión: position_estimation
Ciclo: 1 (v1.2) · Fecha: 2026-11-04 · Agente: reviewer
Spec revisada: `specs/position_estimation/` v1.2 (APPROVED, PR #29) · Rama:
`feat/position_estimation-v1.2` (HEAD `1685a69`; código en `adab10e`) · Base: `origin/develop`
(`a5c9ca7`). Alcance de esta revisión: T-09 y T-08 de la v1.2. La revisión de la v1.1 se conserva
más abajo, sin cambios.

## Veredicto: APPROVED

No hay hallazgos bloqueantes. AC-04 v1.2 y AC-11 v1.2 tienen tests que los verifican de verdad,
y 15 de 16 mutaciones del código nuevo se detectan. `CI=1 ./init.sh verify --e2e` está en verde y
AC-17 sigue en 139 pares comprobados y 5 excluidos. Las decisiones D-19…D-22 caben en la spec y
ninguna requiere CP-3. D-19 deja la firma del constructor del design §3 desfasada: es un problema
de spec menor, no bloqueante. Hay 4 observaciones no bloqueantes. Una es del harness y no
pertenece a esta feature.

## Matriz AC → evidencia (v1.2)

Solo cambian AC-04 y AC-11. Los demás AC conservan la evidencia de la matriz de la v1.1 (más
abajo) y sus tests vuelven a pasar en esta ejecución. AC-03 y AC-07 se tocan de forma indirecta y
se incluyen.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-04 (v1.2) | `tests/unit/test_position_estimator.py:193` `test_with_the_target_as_the_first_stop_the_bus_is_at_the_stop` (6 casos), `:207` `test_with_the_target_as_the_first_stop_a_dwelling_bus_is_at_the_stop` (5 casos); siguen `:169` `test_before_the_departure_the_bus_is_at_the_first_stop` y `:181` `test_at_the_departure_the_bus_is_en_route` | OK | Con la parada objetivo `A` (primera), `AT_STOP` en `d_0` con `distance_to_stop_m = 0`, `stops_away = 0` y `next_stop = A`. Cubre `s` muy anterior a la salida (`-600`), justo antes (`-1`), un retraso que deja `s < 0` (`-30, 120`), un adelanto (`-300, -60`), la hora exacta y un instante posterior. El caso con parada de espera (`dwell_s = 30`) cubre `s < arrival_s[0]` y `arrival_s[0] ≤ s < departure_s[0]`, el hueco que dejaba la v1.1 (D-04). La regla base (objetivo `E`, `s < departure_s[0]`, `NOT_STARTED`) sigue probada en `:169`. Código: `position_estimator.py:57` (`k == 0 or s >= arrival_s[k]`, antes que `NOT_STARTED`), igual que el paso 5 del design v1.2. |
| AC-03 | Los de la v1.1 y `:193` (también marcado `AC-03`) | OK | Sin cambios de comportamiento para `k > 0`. |
| AC-07 | `test_position_estimator.py:281` `test_a_repeated_target_uses_the_occurrence_closest_to_the_arrival` | OK | D-22: para la primera aparición de la parada repetida (la primera del viaje), la aserción pasa de `NOT_STARTED` a `AT_STOP`, como exige AC-04 v1.2. La distancia (0) y `next_stop` (`A`) no cambian. La segunda aparición sigue `EN_ROUTE`. |
| AC-11 (v1.2) | `tests/integration/test_position_api.py:274` `test_a_position_that_cannot_be_estimated_is_no_vehicle_not_500`; `tests/unit/test_get_vehicle_position.py:244` (`missing_stop_times`, `empty_shape`), `:278` (`missing_shape`), `:297` (`missing_stop_coordinates`), `:329` (`target_not_in_trip`), `:344` `test_other_errors_of_the_estimation_are_not_hidden`; `test_position_estimator.py:251`, `:259`, `:268`; siguen los de la v1.1 (`NO_ARRIVAL`, `NO_VEHICLE` sin viaje) | OK | La integración reproduce el ejemplo del AC sobre la BD `gtfs_mini` real con API real. Pone `shape_dist = NULL` en los horarios del viaje emparejado, borra su primera parada de `gtfs_stop` entre dos peticiones y comprueba: `200`, el contrato completo (`set(body) == RESPONSE_FIELDS`), `status = NO_VEHICLE`, `position = null`, `shape_id` representativo (`LineDirection.shape_id`) y `vehicle`/`arrival` iguales a los de la petición anterior. También comprueba **exactamente** un evento `position.estimate_failed` de nivel `warning` con `{trip_id, shape_id, reason}` y ningún otro campo. Los unitarios cubren cada motivo. Otro `ValueError` no se oculta: se propaga y no se registra (design: "Otros errores inesperados no se capturan"). |

### Pruebas de mutación (copia en el scratchpad, `pytest -k position`)

Script: `/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/mutate.py`.
Se aplica cada mutante sobre una copia de `backend/` (sin tocar el repositorio).

| Mutante | Resultado | Test que lo detecta |
|---|---|---|
| M01 quitar `k == 0 or` | Detectado | `test_with_the_target_as_the_first_stop_the_bus_is_at_the_stop` |
| M02 `k <= 1` en lugar de `k == 0` | **Sobrevive** (también a la suite completa) | — (ver H-02) |
| M03 `NOT_STARTED` para `k = 0` antes de la salida | Detectado | ídem M01 |
| M04 relanzar `PositionNotEstimableError` (500) | Detectado | integración AC-11 |
| M05 no registrar el evento | Detectado | integración AC-11 |
| M06 nivel `info` en lugar de `warning` | Detectado | integración AC-11 |
| M07 registrar el `shape_id` representativo en lugar del del viaje | Detectado | `test_a_paired_trip_without_timetable_or_shape_has_no_vehicle` |
| M08 registrar sin `reason` | Detectado | integración AC-11 |
| M09 añadir `stop_id` al evento | Detectado | integración AC-11 (dict exacto) |
| M10 responder `NO_ARRIVAL` | Detectado | integración AC-11 |
| M11 responder con el `shape_id` del viaje | Detectado | unitario AC-11 |
| M12 capturar cualquier `ValueError` | Detectado | `test_other_errors_of_the_estimation_are_not_hidden` |
| M13 el estimador lanza `ValueError` genérico | Detectado | integración AC-11 |
| M14 `reason` constante | Detectado | integración AC-11 |
| M15 forma vacía → `None` (sin motivo propio) | Detectado | unitario AC-11 |
| M16 `estimate is None` → otra excepción | Detectado | `test_a_paired_trip_without_the_stop_has_no_vehicle` |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` (2026-11-04, puerto 4173 libre antes de empezar), salida final
"verify: todo en verde", código 0, en la **primera** ejecución (el `dist/` local ya estaba
construido desde este código):

- backend: format OK · lint OK · types OK (mypy) · architecture OK (lint-imports) · tests OK
  (988 passed, 6 deselected; cobertura `domain` + `application` 99,46 % ≥ 80 %).
- AC-17: "139 pairs checked, 5 excluded because the SAE minutes increased". Los 5 son los mismos
  de la v1.1: 93 ciclos 14→15; 70 `…_070` 23→24; 70 `…_071` 54→55 y 58→69; 70 `…_072` 70→71.
  No hay regresión. Ninguna llegada de la 508 en la sesión tiene la 508 como primera parada del
  viaje, así que la regla `k = 0` no altera la sesión.
- frontend: format OK · lint OK · types OK · tests OK (44 ficheros, 395 tests) · build OK ·
  e2e + a11y OK (87 passed; `test:bundle` 4 passed).
- harness: `feature_list.json` OK · trazabilidad AC→test OK.

Comprobaciones adicionales:

- `git diff --stat origin/develop..HEAD`: 11 ficheros. 7 de `backend/` (código y tests de la
  feature), `progress/impl_position_estimation.md` y 3 ficheros del orquestador
  (`feature_list.json`, `progress/current.md`, `progress/history.md`). No cambia `specs/`,
  `docs/` ni `frontend/`. El contrato OpenAPI no cambia: `logger` no forma parte de la API.
- Arquitectura: `domain/services/position_estimator.py` solo importa `domain.errors` (dentro del
  dominio). `application/get_vehicle_position.py` no importa `structlog` y usa el protocolo
  `Logger` de `get_stop_arrivals.py`. `structlog` solo entra en la composición
  (`adapters/inbound/http/container.py:30,94`). Sin `datetime.now()` ni `time.time()` nuevos.
- Privacidad (AGENTS.md §6, conventions §3): el evento lleva solo `trip_id`, `shape_id` y `reason`,
  que son datos de la red y no personales. No registra token, `stop_id`, `device_id` ni IP. En el
  backend nadie llama a `bind_contextvars` (solo está `merge_contextvars` en `logging.py:18`), así
  que no se cuelan campos de contexto. El mensaje de `PositionNotEstimableError`
  (`domain/errors.py:69`) es `position not estimable (<reason>)`, sin identificadores. Lo
  comprueba `test_position_estimator.py:259` (`"B" not in str(error)`). La aserción de dict
  exacto en la integración impide añadir campos sin romper el test (M09).
- Robustez frente a otros datos incoherentes: `geometry.py` trata la forma de un punto
  (`point_at_distance`, `project_onto_shape`) y las distancias parciales (`shape_distances`). La
  forma vacía llega antes como `empty_shape`. No he encontrado otra vía de datos de red que
  produzca un `500` en la estimación.
- Commits: `feat(position_estimation): …`, `chore(position_estimation): …`, `chore(progress): …`
  (Conventional Commits).

### Encaje de las decisiones locales D-19…D-22

| Decisión | Encaje | ¿CP-3? |
|---|---|---|
| D-19 `logger: Logger` como cuarto parámetro obligatorio de `GetVehiclePosition` | La spec v1.2 obliga al caso de uso a registrar `position.estimate_failed` (AC-11, design §3 "API"), pero la firma del constructor (design §3) no se actualizó. Como `application/` no importa `structlog`, inyectar el protocolo `Logger`, igual que `GetStopArrivals`, es la única forma coherente con la arquitectura. Que sea obligatorio evita olvidarlo en la composición. Es el mismo caso que D-03 en la v1.0, que la v1.1 incorporó a la firma. | No. Es un problema de spec menor (H-01): se arregla en la próxima revisión de la spec. |
| D-20 `PositionNotEstimableError(DomainError, ValueError)` con `reason` | El design dice literalmente "error explícito (tipo: decisión local)". Hereda de `ValueError`, así que el contrato anterior (`ValueError`) se mantiene. El caso de uso captura solo este tipo (M12 lo comprueba). Está en `domain/errors.py`, como pide conventions §3. No tiene manejador HTTP propio y nunca sale del caso de uso. | No |
| D-21 registrar el evento en todos los casos de viaje emparejado sin posición (`missing_stop_times`, `missing_shape`, `empty_shape`, `missing_stop_coordinates`, `target_not_in_trip`) | AC-11 v1.2 habla de "datos incoherentes de la red activa (p. ej. …)". El ejemplo no agota los casos, y un viaje emparejado sin horarios, sin forma o que no pasa por la parada es justo eso. La respuesta era ya `NO_VEHICLE` desde la v1.0 (D-10), así que no cambia. Solo se añade el registro, con nivel `warning`, sin identificadores personales. El design limita la captura a "el error de `estimate_position`", pero los tres motivos que lanza el propio caso de uso (`_estimate`) usan el mismo tipo y antes ya devolvían `NO_VEHICLE` sin `500`. No amplía lo que se oculta. | No. Ver H-03, sobre qué `shape_id` va en el log. |
| D-22 aserción de AC-07 de `NOT_STARTED` a `AT_STOP` | Es consecuencia directa de AC-04 v1.2: la primera aparición de la parada repetida es la primera parada del viaje. Solo cambia esa aserción, y el test sigue verificando AC-07 (se elige la aparición más cercana). | No |

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **H-01 (problema de spec menor, D-19).** `specs/position_estimation/design.md` §3 declara
  `GetVehiclePosition.__init__(self, stop_arrivals, network, clock)`. El código tiene un cuarto
  parámetro `logger: Logger` (`backend/src/avisabus/application/get_vehicle_position.py:49-59`),
  que la propia v1.2 hace necesario. Propuesta para la próxima revisión de la spec: añadir
  `logger: Logger` a la firma del design §3. No requiere CP-3 ahora, porque no cambia ningún
  contrato externo (API, eventos ni errores).
- **H-02 (tests, AC-04/AC-01).** El mutante M02 (`k <= 1` en lugar de `k == 0`,
  `backend/src/avisabus/domain/services/position_estimator.py:57`) sobrevive a toda la suite. No
  hay ningún caso con la **segunda** parada como objetivo (`k = 1`) antes de su hora. Por eso nada
  fija que la regla v1.2 se limite a la primera parada. El hueco viene de la v1.0: los tests de
  AC-01, AC-04 y AC-08 usan objetivos `C`, `D` y `E`. Propuesta: en
  `backend/tests/unit/test_position_estimator.py`, añadir un caso con `target="B"` antes de la
  salida (`NOT_STARTED` en `A`) y otro entre `A` y `B` (`EN_ROUTE`). No bloquea porque el
  comportamiento del AC está verificado y el código es correcto.
- **H-03 (ambigüedad menor de spec, D-21).** AC-11 pide registrar "`trip_id`, `shape_id` y el
  motivo" sin decir qué `shape_id`. El código registra el del **viaje** (`None` si no tiene), y la
  respuesta lleva el representativo (`get_vehicle_position.py:106,112-118`). Es la lectura más útil
  para diagnosticar y la fijan los tests (M07). Conviene que la próxima versión de la spec lo
  diga. Además, la respuesta conserva `vehicle` (`trip_id`, `service_date`) aunque el estado sea
  `NO_VEHICLE` (`test_position_api.py:274`, `body["vehicle"] == before["vehicle"]`). AC-11 dice
  "igual que con `NO_VEHICLE`", y con `NO_VEHICLE` sin viaje el campo `vehicle` es `null`. El
  design solo fija `status`, `position` y `shape_id`, y el frontend
  (`frontend/src/features/passenger/map/summary.ts:82`) decide por `status`/`position`, así que no
  hay efecto visible. Se anota para que la spec lo aclare.
- **H-04 (harness, no pertenece a `position_estimation`).** Confirmado:
  `frontend/src/__tests__/bundle-budget.test.ts:105-124` lee `frontend/dist/` si existe
  (`skipIf(!existsSync(...))`). `init.sh:64-65` ejecuta `frontend: tests` **antes** de
  `frontend: build`, así que la primera ejecución de `verify` evalúa el `dist/` que haya en disco.
  Lo he reproducido en una copia del frontend en el scratchpad: al quitar el chunk `MapPage-*.js`
  del `dist/` (un `dist/` anterior al mapa), falla
  `[passenger_map_view.AC-02] Leaflet and the map are in a chunk loaded on demand…` con
  `expected [] to have a length of 1 but got +0`. Tras `npm run build` en la misma copia, los 4
  tests pasan. Con `--e2e` el problema queda tapado, porque `npm run e2e` termina con
  `test:bundle` (build y después el test). Pero `./init.sh verify` sin `--e2e` puede dar un falso
  rojo, o un falso verde con un `dist/` antiguo que cumpla por casualidad. Origen:
  `passenger_map_view` T-06 (commit `9a9a9dd`, el test que falla). El patrón de leer `dist/`
  dentro de `npm run test` viene de `passenger_stop_view` T-09 (commit `2114105`,
  `passenger_stop_view.AC-21`). Corresponde a `passenger_map_view`. Arreglarlo exige cambiar el
  test (sacar de `npm run test` las aserciones sobre `dist/` real y dejarlas solo en
  `test:bundle`) o el orden de `init.sh` (harness, lo decide una persona). No bloquea esta
  feature: la v1.2 no toca el frontend.
- **Nota para el orquestador (fuera del alcance del reviewer).** `progress/current.md` dice
  "`implementing` (solo T-09)" y fecha 2026-11-03, pero `feature_list.json` ya está en
  `in_review` (commit `1685a69`).

---

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
