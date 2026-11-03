# Implementación: position_estimation
Spec: specs/position_estimation/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-03

## Tareas
- [x] T-01 Geometría: `haversine_m`, `cumulative_distances`, `shape_distances`, `point_at_distance`,
      `bearing_deg`, `project_onto_shape` (monótona) (AC-05, AC-06) (commit 211dfa8)
- [x] T-02 Modelos de posición y `estimate_position` (AC-01, AC-02, AC-03, AC-04, AC-06, AC-07,
      AC-08)
- [ ] T-03 Ampliación de `NetworkRepository`: `trip_shape_id`, `shape_stops`, `shape_line`
- [ ] T-04 `GetVehiclePosition`
- [ ] T-05 `GetShape` y endpoint `/shapes/{shape_id}`
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

## Bloqueos

Ninguno.

## Verificación

Pendiente (T-08).
