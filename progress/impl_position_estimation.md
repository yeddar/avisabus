# Implementación: position_estimation
Spec: specs/position_estimation/ (v1.4, APPROVED; T-01…T-06 hechas con la v1.0, T-07 con la v1.1, T-09 con la v1.2, T-10 con la v1.3, T-11 con la v1.4) · Ciclo de revisión: 0 (de la v1.4) · Agente: implementer · Fecha: 2026-11-09 (v1.4; antes 2026-11-04 y 2026-11-03)

## Tareas
- [x] T-01 Geometría: `haversine_m`, `cumulative_distances`, `shape_distances`, `point_at_distance`,
      `bearing_deg`, `project_onto_shape` (monótona) (AC-05, AC-06) (commit 211dfa8)
- [x] T-02 Modelos de posición y `estimate_position` (AC-01, AC-02, AC-03, AC-04, AC-06, AC-07,
      AC-08) (commit 29f1ad1)
- [x] T-03 Ampliación de `NetworkRepository`: `trip_shape_id`, `shape_stops`, `shape_line`
      (soporte de AC-09 y AC-13) (commit 74f6739)
- [x] T-04 `GetVehiclePosition` y `LineNotAtStopError` (AC-09, AC-10, AC-11, AC-12) (commit d09eec9)
- [x] T-05 `GetShape`, `ShapeNotFoundError` y endpoint `/shapes/{shape_id}` con `ETag`, `304` y
      `Cache-Control` (AC-13, AC-14, AC-15) (commit 62641a7)
- [x] T-06 Endpoint de posición, `GZipMiddleware(minimum_size=1000)`, composición en `main.py`
      (AC-09, AC-10, AC-11, AC-12, AC-16) (commit 686c359)
- [x] T-07 (v1.1) Test de coherencia con la sesión real `stop_508_peak`
      (`tests/integration/test_position_real_session.py`, AC-17): 75 ciclos × (70/1, 93/0); todas
      las posiciones `REALTIME` a < 30 m de su forma; 139 pares sucesivos del mismo viaje con
      minutos del SAE no crecientes sin aumento > 50 m; 5 pares excluidos (minutos que suben) y
      listados en la salida. Antes, la v1.1 alinea la firma de `estimate_position` (commit
      0b32f39). (commit f031c21)
- [x] T-09 (v1.2) `AT_STOP` cuando la parada objetivo es la primera del viaje (AC-04, prevalece
      AC-03) y posición no estimable → `NO_VEHICLE` con el `shape_id` representativo y
      `position.estimate_failed` (`trip_id`, `shape_id`, `reason`), nunca `500` (AC-11)
      (commit adab10e)
- [x] T-10 (v1.3) Dos tests unitarios nuevos (AC-04, AC-11) (commit ad41c2c):
      `test_position_estimator.py::test_with_the_target_as_the_second_stop_the_rule_of_the_first_stop_does_not_apply`
      (objetivo `B`, `k = 1`: `NOT_STARTED` en `A` antes de la salida, también con 5 min de
      retraso, y `EN_ROUTE` entre `A` y `B`; nunca `AT_STOP` antes de su hora) y
      `test_get_vehicle_position.py::test_the_failure_is_logged_with_the_shape_of_the_trip`
      (para `missing_stop_times`, `empty_shape`, `missing_stop_coordinates` y
      `target_not_in_trip`: el log lleva `shape_93_trip`, el del viaje, y la respuesta
      `shape_93`, el representativo). Pasan a la primera con el código actual (comportamiento ya
      implementado en T-09); ver "Mutaciones de T-10".
- [x] T-11 (v1.4) Distancias en metros reales (AC-06) (commit 1ca3b69): `feed_to_metres(shape,
      feed_values)` en `geometry.py`, forma siempre con `cumulative_distances`, proyección también
      si la forma no trae `shape_dist_traveled`, `max` acumulado y retirada de `shape_distances`.
      Tests con el feed escalado ×3 y con escala distinta por tramo, e integración sobre
      `gtfs_mini` frente a la medida directa sobre la forma. Ver "Pruebas de T-11".
- [x] T-08 Contrato del frontend (`npm run gen:api`: sin cambios respecto a T-06; en la v1.2,
      la v1.3 y la v1.4 tampoco cambia) y verificación completa `CI=1 ./init.sh verify --e2e` en
      verde (commit de este fichero; v1.3: re-ejecutada tras T-10; v1.4: re-ejecutada tras T-11)

## Decisiones locales

- **D-01 (T-01) Proyección de paradas sobre la forma** (design §6, "implementación concreta de la
  proyección"): programación dinámica sobre (parada, tramo) que minimiza la suma de distancias
  parada–tramo con la restricción de que el tramo de cada parada no es anterior al de la anterior;
  dentro de un mismo tramo se fuerza la monotonía con `max(d, d_anterior)`. Distancias medidas en
  un plano equirrectangular local (escala de ciudad). Evita el fallo del "más cercano" en líneas
  circulares (la última parada coincide con la primera).
- **D-02 (T-01) Utilidades auxiliares no listadas en el design:** `shape_distances(shape)` (usa
  `dist_traveled` si todos los puntos lo tienen; si no, `cumulative_distances`) y el valor
  `PointOnShape(lat, lon, bearing_deg)` que devuelve `point_at_distance`. Puntos repetidos (tramos
  de longitud 0): rumbo del siguiente tramo real (o del anterior al final); forma de un solo punto:
  `bearing_deg = None`.
- **D-03 (T-02) Coordenadas de las paradas para la proyección:** la firma de `estimate_position`
  del design §3 no recibe coordenadas de las paradas, pero el paso 2 del algoritmo (AC-06) las
  necesita para proyectarlas sobre la forma cuando faltan `shape_dist_traveled`. Se añade un
  parámetro **opcional y solo por nombre** `stop_coordinates: Mapping[str, tuple[float, float]] |
  None = None` (`(lat, lon)` por parada); los siete parámetros del design no cambian. Sin
  distancias y sin coordenadas, `ValueError`. Lo interpreto como parte de "la implementación
  concreta de la proyección" (design §6). **Propuesta para la spec:** añadir el parámetro a la
  firma del design §3. **v1.1:** el design lo incorpora como octavo parámetro posicional con
  `None` por defecto (sin `*`); se quita el "solo por nombre" para que coincida exactamente
  (commit de alineación v1.1, con test que lo llama en posición).
- **D-04 (T-02) Frontera de `NOT_STARTED`:** AC-04 dice "anterior a la salida del viaje" (estricto,
  salida) y el design §3 paso 5 escribe `s ≤ arrival_s[0]`. Se sigue el AC (manda sobre el
  design): `NOT_STARTED` si `s < departure_s[0]`; en `s = departure_s[0]` el autobús está
  `EN_ROUTE` en `d_0`. La posición es la misma en ambas lecturas (solo cambia la etiqueta en el
  instante exacto de salida; en el feed de EMT `arrival = departure`). Se comprueba `AT_STOP`
  antes que `NOT_STARTED` (AC-03), lo que solo importa si la parada objetivo es la primera.
  **v1.1:** el design §3 paso 5 ya dice `s < departure_s[0]` → `NOT_STARTED`, igual que el
  código. El paso 5 lista `NOT_STARTED` antes que `AT_STOP`, pero no fija cuál prevalece. Solo
  difieren si la parada objetivo es la **primera** del viaje y el autobús está entre su llegada y
  su salida (`arrival_s[0] ≤ s < departure_s[0]`). En ese caso el código da `AT_STOP` (AC-03:
  el instante desplazado ya alcanzó la hora de la parada objetivo). En el feed de EMT no ocurre
  (`arrival = departure`). Se mantiene sin cambios; se anota para el reviewer.
  **v1.2 (H-01):** la spec fija que, si la parada objetivo es la primera del viaje (`k = 0`),
  prevalece `AT_STOP` siempre (también con `s < arrival_s[0]`, el autobús aún no ha salido).
  El código comprueba `k == 0 or s >= arrival_s[k]` antes que `NOT_STARTED` (T-09).
- **D-05 (T-02) Autobús detenido en una parada intermedia** (entre `arrival_s` y `departure_s` de
  la parada `i`, hueco del paso 5 del design): `EN_ROUTE` en `d_i`. En el feed de EMT no ocurre
  (`arrival = departure`). `f = 0` también si `s_{i+1} ≤ s_i` (datos incoherentes).
- **D-06 (T-02)** `next_stop.name` sale de `stop_names` (cadena vacía si falta, no ocurre con el
  caso de uso). Forma vacía: `ValueError`.
- **D-07 (T-03) "Viaje más frecuente con esa forma"** (`shape_stops`, design §3): se agrupan los
  viajes de la forma por su secuencia de paradas (patrón); gana el patrón con más viajes y, a
  igualdad, el que contiene el `trip_id` menor; las paradas y sus `sequence` son las del `trip_id`
  menor de ese patrón. En `gtfs_mini` y en el feed real cada forma tiene un único patrón; el caso
  con varios se prueba con un feed modificado. `shape_line`: la línea con más viajes de la forma
  (empate: nombre menor).
- **D-08 (T-03) Sin índice nuevo** (design §4): `shape_stops` consulta primero los viajes de la
  forma y luego sus horarios por clave primaria (el `JOIN` directo recorría todos los horarios de
  la versión: 110–260 ms). Medido sobre una copia de la BD real (`data/avisabus.sqlite`, 94
  formas): 1,6–15,7 ms, por debajo de los 20 ms del design, así que no se añade el índice
  `(fv, shape_id)`.
- **D-09 (T-04) Orden de las comprobaciones:** el constructor del design no recibe el firmante,
  así que `GetVehiclePosition` llama primero a `GetStopArrivals.execute` (token → feed → parada,
  antes del SAE) y después comprueba la línea y el sentido con `lines_at_stop`. Un token inválido
  gana siempre a una línea que no pasa (404 indistinguible, AC-12). Con línea inexistente se
  consulta la caché del SAE de la parada igualmente (la misma petición que haría la vista de
  llegadas).
- **D-10 (T-04) Viaje emparejado sin datos en el feed activo** (sin horarios, sin `shape_id` o con
  forma vacía; solo si el feed cambia entre consultas): se trata como `NO_VEHICLE` (posición
  `null`, forma representativa), igual que una llegada sin viaje (AC-11). **v1.2:** además se
  registra `position.estimate_failed` (ver D-21).
- **D-11 (T-04) Nombres y coordenadas de las paradas del viaje:** con `get_stop` por cada parada
  distinta del viaje (no hay consulta en bloque en el puerto); las coordenadas se pasan como
  `stop_coordinates` (D-03). `now` de la estimación: `clock.now()`; `generated_at` y
  `refresh_after_s`: los de `GetStopArrivals`.
- **D-12 (T-04)** `LineNotAtStopError(stop_id, line, direction_id)`: atributos, mensaje sin
  identificadores (conventions §3).
- **D-13 (T-05) Forma sin viajes:** `GetShape` responde `ShapeNotFoundError` (404
  `shape-not-found`) si la forma no tiene puntos **o** ningún viaje del feed activo la usa (no
  tendría línea; `ShapeView.line` es obligatorio). En el feed real y en `gtfs_mini` todas las
  formas tienen viajes. `color`: el de la línea (`None` solo si viniera vacío).
- **D-14 (T-05) `If-None-Match`:** comparación débil (RFC 9110): admite lista separada por comas,
  prefijo `W/` y `*`. El `304` lleva `ETag` y `Cache-Control`; los errores (`404`, `503`) llevan
  `Cache-Control: no-store` y no llevan `ETag`.
- **D-15 (T-05) Composición:** nuevo `PositionUseCases(get_vehicle_position, get_shape)` y
  `build_position_use_cases(stops, engine, clock)` en `adapters/inbound/http/container.py`
  (reutiliza `stops.get_stop_arrivals`, misma caché del SAE); `create_app(..., positions=...)`
  registra los routers (también con `schema_only`). Helper de tests `tests/support/position.py`.
- **D-16 (T-05/T-06) Contrato del frontend:** `npm run gen:api` se ejecuta en cada tarea que
  cambia la API (T-05 y T-06) para que el test de desfase de `passenger_stop_view` (AC-02) siga en
  verde en cada commit; T-08 lo comprueba de nuevo.
- **D-17 (T-06) Forma de la respuesta de posición:** se sigue el ejemplo del design §3: `arrival`
  con `kind`, `minutes`, `arrival_at`, `destination` y `sae_destination` (`null` con
  `NO_ARRIVAL`), `vehicle` aparte (`{trip_id, service_date}` o `null`) y `stop` con `stop_id`,
  `name`, `lat`, `lon`. `position.lat`/`lon` a 6 decimales y `distance_to_stop_m` entero;
  `bearing_deg` sin redondear (el design no lo fija). `Cache-Control: no-store` en la respuesta
  y en sus errores, como la API de llegadas. `direction_id` es obligatorio (sin él, `422` de
  FastAPI).
- **D-18 (T-06) Test de otra feature ajustado:** `tests/integration/test_main_stops.py`
  (stop_arrivals_api) lista las rutas que empiezan por `/api/v1/stops`; la nueva ruta
  `/api/v1/stops/{stop_id}/lines/{line}/position` entra en ese filtro, así que se añade a la
  lista esperada (sin cambiar nada más del test). Nuevo `test_main_position.py` para la
  composición de esta feature.
- **D-19 (T-09) Logger de `GetVehiclePosition`:** el design v1.2 pide que el caso de uso
  registre `position.estimate_failed`, pero el constructor del design §3 solo recibe
  `(stop_arrivals, network, clock)`. Como en `GetStopArrivals`, la capa de aplicación no importa
  `structlog`: se inyecta el protocolo `Logger` (`application/get_stop_arrivals.py`) como **cuarto
  parámetro obligatorio** `logger`. `build_position_use_cases` le pasa
  `structlog.get_logger("avisabus.position")` (`POSITION_LOGGER`). Obligatorio y sin valor por
  defecto para que la composición no pueda olvidarlo en silencio. **Propuesta para la spec:**
  añadir `logger: Logger` a la firma del design §3.
- **D-20 (T-09) Tipo del error "posición no estimable"** (design §3, "tipo: decisión local"):
  `PositionNotEstimableError(DomainError, ValueError)` en `domain/errors.py`, con atributo
  `reason` y mensaje `position not estimable (<reason>)` sin identificadores (conventions §3).
  `estimate_position` lo lanza con `reason = "missing_stop_coordinates"` (horarios sin
  `shape_dist_traveled` y alguna parada sin coordenadas) y `"empty_shape"` (forma vacía). Sigue
  siendo un `ValueError`, así que el contrato anterior (error explícito) no cambia. El caso de
  uso captura **solo** este tipo; cualquier otro error (incluido un `ValueError` genérico) se
  propaga, como pide el design ("otros errores inesperados no se capturan"; test con
  `monkeypatch`).
- **D-21 (T-09) Qué se registra como `position.estimate_failed`:** AC-11 v1.2 da la falta de
  coordenadas solo como ejemplo ("p. ej.") de datos incoherentes. Se registra, con nivel
  `warning`, en todos los casos en que hay viaje emparejado y no hay posición: `missing_stop_times`,
  `missing_shape`, `empty_shape` (los de D-10), `missing_stop_coordinates` (el del design) y
  `target_not_in_trip` (el viaje no pasa por la parada; solo si el feed cambia). En el log,
  `shape_id` es el del **viaje** (`None` si no tiene). En la respuesta, el representativo de la
  línea y sentido. `trip_id` y `shape_id` son datos de la red, no personales. La respuesta
  (`NO_VEHICLE`, `position = null`, `vehicle` y `arrival` tal como vienen de `GetStopArrivals`)
  es la misma que la de D-10.
- **D-23 (T-11) Dónde se aplica el `max` acumulado:** el design §3 paso 2 lo describe como un
  paso posterior a `feed_to_metres` o `project_onto_shape`, así que `feed_to_metres` convierte
  cada valor de forma independiente y `_stop_distances` aplica `accumulate(metres, max)` a
  ambos resultados. **Aviso para `driver_session`:** al reutilizar `feed_to_metres` tiene que
  aplicar también el `max` acumulado (en el feed real y en `gtfs_mini` ninguna secuencia decrece).
- **D-24 (T-11) `feed_to_metres` con datos incompletos:** el design no fija qué hacer si algún
  punto de la forma no trae `dist_traveled`; lanza `ValueError` en ese caso y con la forma vacía.
  `estimate_position` no llega a ese error: comprueba antes los datos y proyecta, o lanza
  `PositionNotEstimableError` (D-20). Un cambio observable que pide el paso 2 del design: si los
  horarios traen `shape_dist_traveled` pero la forma no, ahora se proyecta y hacen falta las
  coordenadas de las paradas (`missing_stop_coordinates` si faltan).
- **D-25 (T-11) Valores iguales en la escala del feed:** un valor que coincide con un tramo de
  longitud 0 en el feed se resuelve con el último punto de esos iguales (`bisect_right`). El feed
  real y `gtfs_mini` no tienen tramos así; se prueba con una forma sintética.
- **D-02 (actualización v1.4):** `shape_distances` deja de existir (T-11); `PointOnShape` sigue.
- **D-22 (T-09) Test de AC-07 ajustado a la v1.2:**
  `test_a_repeated_target_uses_the_occurrence_closest_to_the_arrival` comprobaba `NOT_STARTED`
  para la **primera** aparición de la parada repetida (la primera parada del viaje). Con AC-04
  v1.2 es `AT_STOP`. Se cambia solo esa aserción; la distancia (0) y la próxima parada (`A`) no
  cambian.

### Mutaciones de T-10 (v1.3)

Aplicadas a mano de una en una sobre el código de producción, suite completa del backend
(`uv run pytest --no-cov`), y revertidas con `git checkout` (árbol limpio después):

| Mutante | Cambio | Resultado |
|---|---|---|
| M02 (H-02 de la revisión v1.2) | `position_estimator.py:57`: `if k == 0 or …` → `if k <= 1 or …` | **Muerto**: 6 failed, 992 passed. Fallan solo los 6 casos del test nuevo de T-10 (antes sobrevivía a toda la suite). |
| Log con la forma representativa | `get_vehicle_position.py:115` (solo la llamada a `warning`): `shape_id=shape_id` → `shape_id=direction.shape_id` | **Muerto**: 7 failed, 991 passed. Fallan los 4 casos del test nuevo y 3 tests anteriores de AC-11 (que ya fijaban el `shape_id` del viaje en el log). |

### Pruebas de T-11 (v1.4)

**Tests en rojo antes del cambio** (commit 5c8a7f5, código sin tocar):

- `test_geometry.py`: error de recogida, `ImportError` de `feed_to_metres`.
- `test_position_estimator.py`: 7 fallos por aserción (p. ej. `assert 6000.0 == 2000` en el test
  de no decrecer).
- `test_position_api.py::test_distance_to_the_stop_matches_the_length_measured_on_the_shape`:
  `distance_to_stop_m` 5158 frente a 1700,3 m medidos sobre la forma (viaje
  `70_1058_601_500_2030_3_070`).

**Mutaciones** (a mano, una a una, con `-k "geometry or position"`, restauradas después):

| Mutante | Resultado |
|---|---|
| `feed_to_metres` devuelve el valor del feed | Muerto: 9 failed |
| Sin acotar el extremo final de la forma | Muerto: 2 failed |
| Sin `max` acumulado | Muerto: 1 failed |
| Se usa el feed de las paradas aunque la forma no lo traiga | Muerto: 2 failed |
| Forma con `dist_traveled` en vez de `cumulative_distances` | Muerto: 8 failed |

**Efecto en AC-17:** se cumple sin cambios en sus cifras: 139 pares comprobados y 5 excluidos, los
mismos. Esos recuentos dependen de `trip_id` y de los minutos del SAE, no de la escala. Sí bajan
las distancias de los 5 pares excluidos: 0→1496 (antes 0→4765), 0→458 (antes 0→1288), 0→485
(antes 0→1380), 0→981 (antes 0→2752) y 967→1447 (antes 2707→4729).

**Comprobación con el feed real** (`data/gtfs/emt`, script local, sin red): 94 patrones de
parada, 2281 paradas; ninguna secuencia decrece. La distancia con `feed_to_metres` y la proyección
de las coordenadas difieren en mediana 0,59 m, p95 7,2 m, p99 18,7 m y máximo 337,9 m. Ver las
observaciones de "Bloqueos".

## Bloqueos

v1.2, v1.3 y v1.4: ninguno que impida continuar.

### Observaciones de la v1.4 (no bloquean; para la persona o el spec-writer)

- **O-01 Fixtures del frontend con distancias antiguas.** Son respuestas del backend anterior a la
  v1.4 y quedan incoherentes. Ninguna tarea pide cambiarlas, así que no se han tocado:
  `position-en-route.json` dice 3403 m y la longitud sobre la forma es de unos 1248 m;
  `position-not-started.json` dice 4251 m y son unos 1839 m (medidas aproximadas, al vértice más
  cercano). Están en `frontend/e2e/fixtures/` y `frontend/src/test/fixtures/api/`. Los textos
  "3,4 km" de los tests del mapa dependen de esas fixtures, y siguen pasando porque son datos
  simulados. La aplicación real mostrará las distancias correctas.
- **O-02 Redacción residual de la spec.** `requirements.md` conserva "`shape_dist_traveled`, en
  metros en el feed de EMT" (Contexto) y AC-05 habla de los puntos "cuyo `shape_dist_traveled`"
  contienen `d`. AC-06 v1.4 y el design §3 (pasos 1 y 6) fijan la interpretación, que es la
  implementada; conviene corregir el texto.
- **O-03 Alcance de la tolerancia de AC-06.** El test de integración cubre la parada 508 (la de
  la sesión grabada), y mide la parada proyectando sus coordenadas. En otras paradas, la posición
  que da el feed (y por tanto AC-06) puede alejarse de esa proyección: hasta 39,5 m en `gtfs_mini`
  (parada 2372, forma `994_488_2271`). Con un autobús a menos de ~2 km de esa parada se superaría
  el 2 % si la referencia fuese la proyección; AC-06 define la distancia de la parada por
  interpolación del feed, de modo que la diferencia viene de los datos. En el feed real, el máximo
  (337,9 m, parada 1282, forma `1030_2278_1282`) corresponde a la cabecera final, donde el feed y
  el final de la forma coinciden y la proyección elige un tramo anterior; no afecta al código
  (solo se proyecta si falta `shape_dist_traveled`).

### B-01 (CP-3) — RESUELTO (spec v1.1, PR #25, opción 1 elegida por la persona)

AC-17 limita ahora la propiedad de distancia a los pares sucesivos en que los minutos del SAE no
aumentan; el design v1.1 incorpora `stop_coordinates` (D-03) y la frontera de `NOT_STARTED` (D-04).
Se deja abajo el análisis original como registro.

#### Análisis original de B-01 — AC-17: la distancia a la parada de un mismo viaje sí aumenta más de 50 m con `stop_508_peak`

**AC afectado:** `position_estimation.AC-17`, segunda propiedad: "para un mismo viaje en instantes
sucesivos de la reproducción, la distancia a la parada NO DEBERÁ aumentar más de 50 m".

**Qué se hizo (sin escribir el test de T-07):** recorrer la sesión `stop_508_peak` con `gtfs_mini`,
el `FakeClock` desde `started_at` avanzando 20 s (75 instantes, offsets 0…1480) y la API real de
posición (misma composición que `main.py`, `tests/support/position.py`) para la 93 (sentido 0) y la
70 (sentido 1) en la parada 508; para cada `vehicle.trip_id` se compara `distance_to_stop_m` con su
observación anterior.

**Resultado:**

- Primera propiedad (a menos de 30 m de la forma): **se cumple**; todas las posiciones son
  `REALTIME` y la peor está a 0,05 m de la forma de su viaje (redondeo a 6 decimales).
- Segunda propiedad: **5 incumplimientos**, todos en instantes en que **los minutos del SAE
  aumentan**:

| Línea | Viaje (`trip_id`) | Offsets | `distance_to_stop_m` | Minutos SAE | Causa en los datos |
|---|---|---|---|---|---|
| 93 | `93_994_561_488_2271_2_122` | 280 → 300 | 0 → 4765 | 0 → 7 | El autobús a 0 min desaparece; el siguiente (7 min) se empareja con el mismo viaje (`TripMatcher`) |
| 70 | `70_1058_601_500_2030_3_070` | 460 → 480 | 0 → 1288 | 0 → 2 | El SAE vuelve de 0 a 2 min |
| 70 | `70_1058_601_500_2030_3_071` | 1080 → 1100 | 0 → 1380 | 0 → 2 | El SAE vuelve de 0 a 2 min |
| 70 | `70_1058_601_500_2030_3_071` | 1160 → 1380 (no consecutivos) | 0 → 2752 | 0 → 4 | Reemparejamiento del mismo viaje con otro autobús |
| 70 | `70_1058_601_500_2030_3_072` | 1400 → 1420 | 2707 → 4729 | 4 → 7 | El SAE sube la ETA 3 min en 20 s |

Respuestas brutas del SAE que lo muestran (parada 508, `parse_qrphp_html`): offset 280
`93 0 min`, 300 `70 3 min, 93 7 min` (sin la 93 a 0 min); 1400 `70 4 min`, 1420 `70 7 min`; 1080
`70 0 min`, 1100 `70 2 min`.

**Por qué no es un fallo de la implementación:** con el modelo de AC-01/AC-02 (el retraso en la
parada se aplica a todo el recorrido), si el SAE retrasa la llegada Δ más que el tiempo
transcurrido, el instante desplazado retrocede y el autobús retrocede por el trazado (3 min de
horario ≈ 2 km en la 70). Es lo que piden AC-01 y AC-02; y el `trip_id` de una llegada lo decide
el `TripMatcher` de `stop_arrivals_api` en cada consulta, sin identidad estable del autobús entre
instantes. Cumplir AC-17 tal como está exigiría inventar un comportamiento no especificado
(suavizado o memoria de posiciones por viaje, contrario a una función pura) o alterar la fixture.

**Comprobación de la alternativa:** en los 138 pares de instantes consecutivos del mismo viaje en
que los minutos del SAE **no aumentan**, la distancia nunca aumenta (ni siquiera 1 m): con
minutos iguales, `arrival_at` avanza lo mismo que el reloj y la posición se queda quieta; con
minutos menores, avanza.

**Propuestas (elige la persona / spec-writer):**

1. **(Recomendada)** Reformular la segunda propiedad de AC-17: "para un mismo viaje en instantes
   sucesivos de la reproducción **en los que la llegada del SAE no se retrasa** (sus minutos no
   aumentan), la distancia a la parada NO DEBERÁ aumentar más de 50 m", y añadir, si se quiere,
   que el test **documente** los retrocesos observados cuando el SAE retrasa la llegada (los 5 de
   la tabla). Con esta redacción el test se puede escribir ya y pasa.
2. Especificar un suavizado (p. ej., no retroceder más de X m para el mismo `trip_id` durante
   Y s), lo que exige estado por viaje (caché) fuera del dominio puro: cambio de design y de
   alcance; mejor en una versión posterior o en `passenger_map_view` (presentación).
3. Quitar la segunda propiedad y dejar solo la de los 30 m.

(Estado tras la v1.1: T-07 hecha con la propuesta 1; el test excluye y lista exactamente esos 5
pares.)

## Verificación

`CI=1 ./init.sh verify --e2e` (2026-11-09, spec v1.4, tras T-11; puerto 4173 libre; salida
"verify: todo en verde", código 0):

- backend: format OK · lint OK · types OK (mypy, 129 ficheros) · architecture OK · tests OK
  (1426 passed, 6 deselected; cobertura 99,56 %). AC-17: "139 pairs checked, 5 excluded because
  the SAE minutes increased".
- frontend: format OK · lint OK · types OK · tests OK (55 ficheros, 563 passed y 2 skipped) ·
  build + bundle OK (5 tests) · e2e + a11y OK (126 passed)
- harness: `feature_list.json` OK · trazabilidad AC→test OK
- `cd backend && uv run pytest -m slow --no-cov`: 6 passed (ninguno es de esta feature).
- T-11 por separado: `cd backend && uv run pytest -k "geometry or position"`: 140 passed, pero el
  comando sale con error por cobertura (78,75 % < 80 %) al ejecutar solo ese subconjunto; con la
  suite completa la cobertura es 99,56 %.
- `npm run gen:api`: `openapi.json` y `schema.d.ts` sin cambios (git limpio).

Ejecución anterior (v1.3, tras T-10):

`CI=1 ./init.sh verify --e2e` (2026-11-04, spec v1.3, tras T-10; antes `npm run build` en
`frontend/`; puerto 4173 libre; salida "verify: todo en verde", código 0):

- backend: format OK · lint OK · types OK (mypy, 92 ficheros) · architecture OK · tests OK
  (998 passed, 6 deselected; cobertura 99,46 %). AC-17 sin cambios: "139 pairs checked, 5
  excluded because the SAE minutes increased".
- frontend: format OK · lint OK · types OK · tests OK (44 ficheros, 409 tests) · build OK ·
  e2e + a11y OK (87 passed; `test:bundle` 4 passed)
- harness: `feature_list.json` OK · trazabilidad AC→test OK
- T-10 por separado: `cd backend && uv run pytest -k position` → 102 passed. `npm run gen:api`:
  `openapi.json` y `schema.d.ts` sin cambios (git limpio). Código de producción sin cambios en
  la v1.3.

Ejecución anterior (v1.2, tras T-09):

`CI=1 ./init.sh verify --e2e` (2026-11-04, spec v1.2, tras T-09; puerto 4173 libre; salida "verify:
todo en verde", código 0):

- backend: format OK · lint OK · types OK (mypy, 92 ficheros) · architecture OK (2 contratos) ·
  tests OK (988 passed, 6 deselected; cobertura `domain`+`application` 99,46 %). AC-17 sin
  cambios: "139 pairs checked, 5 excluded because the SAE minutes increased".
- frontend: format OK · lint OK · types OK · tests OK (44 ficheros, 395 tests) · build OK ·
  e2e + a11y OK (87 passed)
- harness: `feature_list.json` OK · trazabilidad AC→test OK
- T-09 por separado: `cd backend && uv run pytest -k position` → 92 passed. `npm run gen:api`:
  `openapi.json` y `schema.d.ts` sin cambios (git limpio).
- Observación (fuera del alcance de la feature, para el orquestador): la primera ejecución falló
  en `frontend: tests` por
  `src/__tests__/bundle-budget.test.ts` (`passenger_map_view.AC-02`): el test lee
  `frontend/dist/` y `init.sh` ejecuta los tests **antes** del build, así que se evaluó un
  `dist/` antiguo (sin el chunk `MapPage`). Tras el build de esa misma ejecución, el test pasa y
  la segunda ejecución sale en verde. El frontend no se ha tocado en la v1.2.

Ejecución anterior (v1.1, 2026-11-03, tras T-07; salida "verify: todo en verde"):

- backend: format OK · lint OK · types OK (mypy) · architecture OK (2 contratos) · tests OK
  (969 passed, 6 deselected; cobertura `domain`+`application` 99,39 %). Salida de AC-17:
  "139 pairs checked, 5 excluded because the SAE minutes increased".
- frontend: format OK · lint OK · types OK · tests OK (35 ficheros, 278 tests) · build OK ·
  e2e + a11y OK (60 passed)
- harness: `feature_list.json` OK · trazabilidad AC→test OK

Ejecución anterior (v1.0, tras T-06): todo en verde salvo la trazabilidad de AC-17 (B-01).
