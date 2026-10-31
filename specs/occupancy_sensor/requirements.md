# Sensor de ocupación — requirements

> Feature: `occupancy_sensor` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-14, RF-15 · Casos de uso: CU-01 (y, más adelante, CU-09) · Depende de: project_scaffold, gtfs_import

## Contexto

EMT València no publica la ocupación de sus autobuses (LIM-04). El sistema obtiene la ocupación
a través de un puerto `OccupancySensor`, con una implementación **simulada** determinista y
verosímil, preparada para sustituirse por sensores reales (OBJ-08). Como el SAE no identifica
vehículos, la identidad del autobús es el **viaje GTFS** emparejado con su ETA (ADR-013); ese
emparejamiento lo hace `stop_arrivals_api`.

La ocupación se muestra al pasajero como nivel (libre / medio / lleno) e indicación de asientos
libres (RF-15), y al conductor como plazas libres (RF-29, feature `driver_demand`).

## Alcance

- Modelos `VehicleRef`, `OccupancyReading`, `OccupancyLevel`, `OccupancyStatus`.
- Puerto `OccupancySensor` y servicio de dominio `classify_occupancy`.
- `SimulatedOccupancySensor` (determinista, según hora del día, día de la semana y avance del viaje).
- Forzado manual de nivel por línea para demos (CLI) con caducidad.

## Fuera de alcance

- Presentación en la interfaz (features `passenger_stop_view`, `driver_ui`).
- Sensores reales.

## Criterios de aceptación

### Modelo y clasificación

- **occupancy_sensor.AC-01** — EL SISTEMA DEBERÁ representar una lectura con `capacity`,
  `seats`, `occupied` y `measured_at`, y derivar `free_places = capacity − occupied` y
  `free_seats = max(0, seats − occupied)`.
  *Verificación:* unit
- **occupancy_sensor.AC-02** — EL SISTEMA DEBERÁ clasificar una lectura como `FREE` si
  `occupied / capacity < 0,50`, `MEDIUM` si es `< 0,85` y `FULL` en otro caso, con umbrales
  configurables, e indicar si hay asientos libres (`free_seats > 0`).
  *Verificación:* unit (valores frontera 0,49 / 0,50 / 0,84 / 0,85)
- **occupancy_sensor.AC-03** — SI los umbrales configurados no cumplen `0 < medio < lleno ≤ 1`,
  o `seats > capacity`, ENTONCES EL SISTEMA DEBERÁ negarse a arrancar con un error de
  configuración.
  *Verificación:* unit

### Simulación

- **occupancy_sensor.AC-04** — CUANDO se pide la ocupación de un mismo viaje y día de servicio en
  el mismo instante, EL SENSOR SIMULADO DEBERÁ devolver siempre la misma lectura (determinista
  con semilla configurable).
  *Verificación:* unit
- **occupancy_sensor.AC-05** — EL SENSOR SIMULADO DEBERÁ cumplir siempre
  `0 ≤ occupied ≤ capacity`.
  *Verificación:* unit (barrido de horas, días y avance; prueba basada en propiedades con
  Hypothesis)
- **occupancy_sensor.AC-06** — Para un mismo viaje y avance, EL SENSOR SIMULADO DEBERÁ dar una
  ocupación mayor o igual en hora punta (07:00–09:00 y 17:00–20:00, día laborable) que a las
  23:00 del mismo día.
  *Verificación:* unit
- **occupancy_sensor.AC-07** — Para un mismo viaje e instante base, EL SENSOR SIMULADO DEBERÁ dar
  una ocupación mayor a mitad de recorrido (avance 0,5) que al inicio (avance 0) y al final
  (avance 1).
  *Verificación:* unit
- **occupancy_sensor.AC-08** — EL SENSOR SIMULADO DEBERÁ calcular el avance del viaje a partir de
  sus horarios programados (`NetworkRepository.trip_stop_times`) y del instante pedido, limitado
  al intervalo [0, 1].
  *Verificación:* unit (repositorio fake)
- **occupancy_sensor.AC-09** — SI el viaje no existe en la red activa, ENTONCES EL SENSOR DEBERÁ
  devolver `None`.
  *Verificación:* unit
- **occupancy_sensor.AC-10** — En un muestreo de 100 viajes distintos a la misma hora y avance,
  EL SENSOR SIMULADO DEBERÁ producir al menos dos niveles distintos (variación entre viajes).
  *Verificación:* unit

### Forzado para demos

- **occupancy_sensor.AC-11** — CUANDO el administrador ejecuta
  `avisabus occupancy override --line 93 --level FULL --minutes 30`, EL SISTEMA DEBERÁ guardar el
  forzado y, mientras no caduque, EL SENSOR DEBERÁ devolver para cualquier viaje de la línea 93
  una lectura clasificada como `FULL` (y análogamente para `FREE` y `MEDIUM`).
  *Verificación:* integration (BD temporal, FakeClock)
- **occupancy_sensor.AC-12** — CUANDO caduca el forzado o el administrador ejecuta
  `avisabus occupancy override --line 93 --clear`, EL SENSOR DEBERÁ volver a la simulación normal.
  *Verificación:* integration
- **occupancy_sensor.AC-13** — CUANDO se ejecuta `avisabus occupancy override --list`, LA CLI
  DEBERÁ mostrar los forzados activos con su caducidad.
  *Verificación:* integration
- **occupancy_sensor.AC-14** — EL SENSOR DEBERÁ ver los cambios de forzado hechos desde la CLI
  (otro proceso) en un máximo de 5 segundos sin reiniciar la aplicación.
  *Verificación:* integration (caché de 5 s con FakeClock)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-14 Ocupación por vehículo tras interfaz, simulada | AC-01, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-13, AC-14 |
| RF-15 Nivel de ocupación y asientos libres | AC-02, AC-03 |
| OBJ-08 Desacoplamiento | AC-01 (puerto), AC-09 |
