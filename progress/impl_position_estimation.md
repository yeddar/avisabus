# Implementación: position_estimation
Spec: specs/position_estimation/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-03

## Tareas
- [x] T-01 Geometría: `haversine_m`, `cumulative_distances`, `shape_distances`, `point_at_distance`,
      `bearing_deg`, `project_onto_shape` (monótona) (AC-05, AC-06)
- [ ] T-02 Modelos de posición y `estimate_position`
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

## Bloqueos

Ninguno.

## Verificación

Pendiente (T-08).
