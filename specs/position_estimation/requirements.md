# Estimación de la posición del autobús — requirements

> Feature: `position_estimation` · Versión: 1.4 · Estado: APPROVED
> Requisitos: RF-12, RNF-01 · Casos de uso: CU-02 · Depende de: gtfs_import, stop_arrivals_api

## Contexto

EMT València no publica la posición de sus autobuses (ADR-005, LIM-03). El sistema la **estima**
combinando:

- el tiempo de llegada a la parada que da el SAE (o el horario, si el SAE no está disponible);
- el viaje GTFS emparejado con esa llegada (`TripMatcher`, ADR-013);
- los horarios programados del viaje y la distancia recorrida en cada parada
  (`shape_dist_traveled`, en metros en el feed de EMT);
- el trazado (`shapes`).

Idea: si el autobús va a llegar a mi parada con δ minutos de retraso respecto a su horario,
supongo que lleva ese mismo retraso en todo el recorrido; con ello sé entre qué dos paradas está
ahora y en qué punto del trazado, interpolando por tiempo.

Esta feature ofrece la estimación por API (para el mapa de `passenger_map_view`) y el trazado de
las líneas.

## Alcance

- Servicio de dominio `estimate_position` y utilidades geométricas (interpolación sobre la forma,
  distancias, rumbo, proyección de paradas cuando falte `shape_dist_traveled`).
- Caso de uso `GetVehiclePosition` y endpoint de posición.
- Caso de uso `GetShape` y endpoint de trazado con caché HTTP.
- Compresión gzip de respuestas.

## Fuera de alcance

- Interfaz del mapa (`passenger_map_view`).
- Posiciones medidas (AVL / GTFS-Realtime): preparadas para el futuro por el diseño, no
  implementadas.
- Posición de todos los autobuses de una línea (solo el próximo que llega a la parada consultada).

## Criterios de aceptación

### Algoritmo (dominio)

- **position_estimation.AC-01** — CUANDO el instante actual, desplazado por el retraso
  `δ = arrival_at − hora programada en la parada objetivo`, cae entre las horas programadas de dos
  paradas consecutivas `i` e `i+1` anteriores a la parada objetivo, EL SISTEMA DEBERÁ situar el
  autobús en la distancia `d = d_i + f · (d_{i+1} − d_i)` del trazado, con
  `f = (t − s_i) / (s_{i+1} − s_i)` (o `f = 0` si `s_i = s_{i+1}`), y estado `EN_ROUTE`.
  *Verificación:* unit (viaje sintético)
- **position_estimation.AC-02** — EL SISTEMA DEBERÁ aplicar el retraso: un autobús que llegará
  3 min más tarde de lo programado DEBERÁ situarse donde el horario lo situaría 3 min antes.
  *Verificación:* unit
- **position_estimation.AC-03** — SI el instante desplazado es igual o posterior a la hora
  programada en la parada objetivo, o la llegada es de 0 min, ENTONCES EL SISTEMA DEBERÁ situar el
  autobús en la parada objetivo con estado `AT_STOP`.
  *Verificación:* unit
- **position_estimation.AC-04** — SI el instante desplazado es anterior a la salida del viaje,
  ENTONCES EL SISTEMA DEBERÁ situar el autobús en la primera parada del viaje con estado
  `NOT_STARTED`. (v1.2) SI la parada objetivo es la primera del viaje, ENTONCES prevalece AC-03
  (`AT_STOP`): el autobús que aún no ha salido está en la parada del pasajero.
  *Verificación:* unit
- **position_estimation.AC-05** — EL SISTEMA DEBERÁ convertir la distancia `d` en coordenadas
  interpolando linealmente entre los dos puntos de la forma cuyo `shape_dist_traveled` la
  contienen, y calcular el rumbo (0–360°) del segmento.
  *Verificación:* unit (error < 1 m en forma sintética)
- **position_estimation.AC-06** — (v1.4) LAS DISTANCIAS a lo largo de la forma DEBERÁN estar en
  **metros reales**: las de los puntos de la forma, como distancia acumulada (haversine), aunque
  el feed traiga `shape_dist_traveled` (que no está en metros, `gtfs_import` v1.4). LA DISTANCIA
  DE CADA PARADA DEBERÁ obtenerse interpolando su `shape_dist_traveled` entre los
  `shape_dist_traveled` de los puntos de la forma y tomando la distancia en metros
  correspondiente; SI los horarios o la forma no traen `shape_dist_traveled`, ENTONCES
  proyectándola sobre la forma. En ambos casos las distancias resultantes no DEBERÁN decrecer a lo
  largo del viaje, y `distance_to_stop_m` DEBERÁ quedar a menos del 2 % (o de 10 m) de la
  distancia haversine acumulada medida sobre la forma.
  *Verificación:* unit (forma sintética con `shape_dist_traveled` escalado ×3 y con escala
  distinta por tramo) + integration (`gtfs_mini`: `distance_to_stop_m` frente a la medida directa
  sobre la forma)
- **position_estimation.AC-07** — CUANDO la parada objetivo aparece más de una vez en el viaje
  (líneas circulares), EL SISTEMA DEBERÁ usar la aparición cuya hora programada esté más próxima a
  `arrival_at`.
  *Verificación:* unit
- **position_estimation.AC-08** — EL SISTEMA DEBERÁ calcular la distancia por el trazado hasta la
  parada objetivo (`d_objetivo − d`, nunca negativa), el número de paradas intermedias que le
  faltan al autobús antes de la parada objetivo y la próxima parada que alcanzará.
  *Verificación:* unit

### API de posición

- **position_estimation.AC-09** — CUANDO se hace
  `GET /api/v1/stops/{stop_id}/lines/{line}/position?direction_id={d}&t={token}`, LA API DEBERÁ
  usar la primera llegada de esa línea y sentido calculada por `GetStopArrivals` (la misma caché del
  SAE, **sin** peticiones adicionales) y devolver `status`, `source`, `generated_at`,
  `refresh_after_s`, la llegada (con `destination` y `sae_destination`, como en la API de
  llegadas), el viaje, `shape_id` del viaje, la parada, el `headsign` de esa línea y sentido en la
  parada (el de `lines` de `GET /stops/{stop_id}`, para titular la vista aunque no haya llegada) y
  la posición (`lat`, `lon`, `bearing_deg`, `distance_to_stop_m`, `stops_away`, `next_stop`).
  *Verificación:* integration (replay + contador de peticiones)
- **position_estimation.AC-10** — CUANDO la llegada procede del horario programado, LA API DEBERÁ
  devolver `source = "SCHEDULED"` con la posición calculada sobre el horario (`δ = 0`).
  *Verificación:* integration
- **position_estimation.AC-11** — SI no hay ninguna llegada de esa línea y sentido, ENTONCES LA API
  DEBERÁ responder `200` con `status = "NO_ARRIVAL"`, `position = null` y el `shape_id`
  representativo de la línea y sentido; SI hay llegada pero sin viaje emparejado, ENTONCES
  `status = "NO_VEHICLE"`, con el mismo tratamiento. (v1.2) SI hay viaje emparejado pero su
  posición no se puede estimar por datos incoherentes de la red activa (p. ej. horarios sin
  `shape_dist_traveled` y alguna parada sin coordenadas), ENTONCES LA API DEBERÁ responder igual
  que con `NO_VEHICLE` (nunca `500`) y EL SISTEMA DEBERÁ registrar `position.estimate_failed`
  con `trip_id`, `shape_id` y el motivo.
  *Verificación:* integration
- **position_estimation.AC-12** — SI el token es inválido o la parada no existe, ENTONCES LA API
  DEBERÁ responder igual que `stop_arrivals_api` (404 indistinguible); SI la línea y el sentido no
  pasan por la parada, ENTONCES DEBERÁ responder `404` con `type = …/line-not-at-stop`.
  *Verificación:* integration

### API de trazado

- **position_estimation.AC-13** — CUANDO se hace `GET /api/v1/shapes/{shape_id}`, LA API DEBERÁ
  devolver las coordenadas de la forma en orden y en formato GeoJSON (`[lon, lat]`), el color de
  la línea y las paradas del viaje más frecuente con esa forma (`stop_id`, nombre, `lat`, `lon`,
  `sequence`).
  *Verificación:* integration
- **position_estimation.AC-14** — LA RESPUESTA DE TRAZADO DEBERÁ incluir
  `Cache-Control: public, max-age=86400` y un `ETag` que cambie con la versión del feed; CUANDO la
  petición trae `If-None-Match` con ese `ETag`, LA API DEBERÁ responder `304` sin cuerpo.
  *Verificación:* integration
- **position_estimation.AC-15** — SI la forma no existe en el feed activo, ENTONCES LA API DEBERÁ
  responder `404` con `type = …/shape-not-found`.
  *Verificación:* integration
- **position_estimation.AC-16** — LA API DEBERÁ comprimir con gzip las respuestas de más de 1 KB
  cuando el cliente lo acepte.
  *Verificación:* integration

### Coherencia con datos reales

- **position_estimation.AC-17** — CON la red de `gtfs_mini` y la reproducción de `stop_508_peak`,
  todas las posiciones `REALTIME` estimadas para la parada 508 DEBERÁN estar a menos de 30 m de la
  forma de su viaje y, para un mismo viaje en dos instantes sucesivos de la reproducción **en los
  que los minutos del SAE para esa llegada no aumentan**, la distancia a la parada NO DEBERÁ
  aumentar más de 50 m. (v1.1) Cuando el SAE retrasa una llegada entre dos consultas, el autobús
  estimado puede retroceder: es consecuencia de AC-01/AC-02 y de que el SAE no identifica
  vehículos (LIM-03, ADR-013), y se acepta sin suavizado.
  *Verificación:* integration (propiedades sobre toda la sesión; el test informa además del
  número de pares excluidos por aumento de minutos)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-12 Estimar la posición sobre el trazado | AC-01 … AC-08, AC-09, AC-10, AC-11, AC-17 |
| RF-13 (soporte) Trazado para el mapa | AC-13, AC-14, AC-15 |
| RNF-01 Rendimiento | AC-09 (sin peticiones extra al SAE), AC-14, AC-16 |
| CU-02 flujos 1a y 1b | AC-11, AC-10 |
| LIM-03 Posición estimada | AC-01 … AC-08 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-03 | Versión inicial aprobada (PR #7), con la guía visual `docs/design.md`. | CP-1 del bloque 2. Aprobada por la persona. |
| 1.1 | 2026-11-03 | AC-17: la propiedad de distancia no creciente se limita a pares sucesivos en que los minutos del SAE no aumentan (los retrocesos por retraso del SAE se aceptan); design §3: parámetro `stop_coordinates` de `estimate_position` (AC-06) y frontera de `NOT_STARTED` según AC-04. | CP-3 de `position_estimation` (T-07): en `stop_508_peak` la distancia aumenta 5 veces, todas cuando el SAE sube los minutos. D-03 y D-04 del implementer. Aprobada por la persona (PR #25). |
| 1.2 | 2026-11-04 | AC-04: con la parada objetivo como primera del viaje prevalece `AT_STOP` (AC-03); AC-11: posición no estimable por datos incoherentes → `NO_VEHICLE` y `position.estimate_failed`, nunca `500`. T-09. | Hallazgos H-01 y H-02 de la revisión de `position_estimation` 1.1. Aprobada por la persona (PR #29). |
| 1.3 | 2026-11-04 | Solo design y tests: firma de `GetVehiclePosition` con `logger`; en `position.estimate_failed`, `shape_id` es el del viaje (puede ser `null`) y la respuesta lleva el `shape_id` representativo, conserva `arrival` y `vehicle` y `position = null`. T-10 (test con la segunda parada como objetivo). | Hallazgos H-01…H-03 de la revisión de `position_estimation` 1.2. Aprobada por la persona (PR #33). |
| 1.4 | 2026-11-09 | AC-06: distancias siempre en metros reales (haversine sobre la forma); la de cada parada, interpolando su `shape_dist_traveled` en los de la forma o proyectando si falta. Corrige `distance_to_stop_m`, inflado ~×3 en el feed de EMT. T-11. | P-02 de `driver_session` (CP-3): `shape_dist_traveled` del feed no está en metros. Pendiente de aprobación. |
