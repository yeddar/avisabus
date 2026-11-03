# Implementación: position_estimation
Spec: specs/position_estimation/ (v1.1, APPROVED; T-01…T-06 hechas con la v1.0) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-03

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
- [ ] T-07 Test de coherencia con la sesión real `stop_508_peak` — **BLOQUEADA (CP-3, ver
      Bloqueos B-01)**: la segunda propiedad de AC-17 no se cumple con los datos reales.
- [ ] T-08 Contrato del frontend (`npm run gen:api`) y verificación completa — contrato ya
      regenerado en T-05 y T-06 (D-16); la verificación completa falla solo por la trazabilidad de
      AC-17 (pendiente de B-01).

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
  `null`, forma representativa), igual que una llegada sin viaje (AC-11).
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

## Bloqueos

### B-01 (CP-3) — AC-17: la distancia a la parada de un mismo viaje sí aumenta más de 50 m con `stop_508_peak`

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

Hasta que se resuelva, T-07 queda sin hacer y `./init.sh verify` falla en la trazabilidad
(`position_estimation.AC-17: ningún test lo cita`). T-01…T-06 están completas y en verde.

## Verificación

`CI=1 ./init.sh verify --e2e` (2026-11-03, tras T-06):

- backend: format OK · lint OK · types OK (mypy, 92 ficheros) · architecture OK (2 contratos) ·
  tests OK (965 passed, 6 deselected; cobertura `domain`+`application` 99,39 %)
- frontend: format OK · lint OK · types OK · tests OK (35 ficheros, 278 tests) · build OK ·
  e2e + a11y OK (60 passed)
- harness: `feature_list.json` OK · **trazabilidad FAIL**: `position_estimation.AC-17: ningún
  test lo cita` (bloqueo B-01).
