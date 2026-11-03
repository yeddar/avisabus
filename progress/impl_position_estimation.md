# Implementación: position_estimation
Spec: specs/position_estimation/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-03

## Tareas
- [x] T-01 Geometría: `haversine_m`, `cumulative_distances`, `shape_distances`, `point_at_distance`,
      `bearing_deg`, `project_onto_shape` (monótona) (AC-05, AC-06) (commit 211dfa8)
- [x] T-02 Modelos de posición y `estimate_position` (AC-01, AC-02, AC-03, AC-04, AC-06, AC-07,
      AC-08) (commit 29f1ad1)
- [x] T-03 Ampliación de `NetworkRepository`: `trip_shape_id`, `shape_stops`, `shape_line`
      (soporte de AC-09 y AC-13) (commit 74f6739)
- [x] T-04 `GetVehiclePosition` y `LineNotAtStopError` (AC-09, AC-10, AC-11, AC-12) (commit d09eec9)
- [x] T-05 `GetShape`, `ShapeNotFoundError` y endpoint `/shapes/{shape_id}` con `ETag`, `304` y
      `Cache-Control` (AC-13, AC-14, AC-15)
- [ ] T-06 Endpoint de posición, `GZipMiddleware`, composición en `main.py`
- [ ] T-07 Test de coherencia con la sesión real `stop_508_peak`
- [ ] T-08 Contrato del frontend (`npm run gen:api`) y verificación completa

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
  firma del design §3.
- **D-04 (T-02) Frontera de `NOT_STARTED`:** AC-04 dice "anterior a la salida del viaje" (estricto,
  salida) y el design §3 paso 5 escribe `s ≤ arrival_s[0]`. Se sigue el AC (manda sobre el
  design): `NOT_STARTED` si `s < departure_s[0]`; en `s = departure_s[0]` el autobús está
  `EN_ROUTE` en `d_0`. La posición es la misma en ambas lecturas (solo cambia la etiqueta en el
  instante exacto de salida; en el feed de EMT `arrival = departure`). Se comprueba `AT_STOP`
  antes que `NOT_STARTED` (AC-03), lo que solo importa si la parada objetivo es la primera.
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

## Bloqueos

Ninguno.

## Verificación

Pendiente (T-08).
