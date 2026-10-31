# API de parada y llegadas — requirements

> Feature: `stop_arrivals_api` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-06, RF-09, RF-11, RF-15, RF-32, RNF-01, RNF-08 · Casos de uso: CU-01 · Depende de: gtfs_import, stop_tokens_qr, sae_arrivals_source, occupancy_sensor

## Contexto

Es el backend de la vista de parada (CU-01). Une las piezas del bloque 1:

1. valida el token del QR (`stop_tokens_qr`);
2. obtiene los datos de la parada de la red GTFS (`gtfs_import`);
3. obtiene las llegadas del SAE (`sae_arrivals_source`) y las **enriquece**:
   - resuelve el **sentido** GTFS a partir del texto de destino del SAE (riesgo R-02);
   - empareja cada llegada con un **viaje GTFS** (`TripMatcher`, ADR-013), que da identidad al
     autobús para la ocupación y, en features posteriores, para la posición y los avisos;
   - añade la **ocupación** (`occupancy_sensor`);
4. si el SAE no está disponible, responde con el **horario programado** (RF-09).

## Alcance

- Servicios de dominio `DirectionResolver` y `TripMatcher`.
- Casos de uso `GetStop` y `GetStopArrivals`.
- Endpoints `GET /api/v1/stops/{stop_id}` y `GET /api/v1/stops/{stop_id}/arrivals`.
- Respaldo por horario (`ScheduledArrivalsProvider`).

## Fuera de alcance

- Interfaz (feature `passenger_stop_view`).
- Posición estimada (feature `position_estimation`).
- Creación de avisos (feature `alert_create`); aquí solo se indica si una llegada admite aviso.

## Criterios de aceptación

### Parada

- **stop_arrivals_api.AC-01** — CUANDO se hace `GET /api/v1/stops/{stop_id}?t={token}` con token
  válido de una parada existente, LA API DEBERÁ responder `200` con `stop_id`, el nombre de la
  parada tal como viene en el GTFS y la lista de líneas que la sirven (`line`, `direction_id`,
  `headsign`, `color`, `text_color`) en orden natural de línea.
  *Verificación:* integration (gtfs_mini)
- **stop_arrivals_api.AC-02** — SI el token es inválido o falta, o la parada no existe, ENTONCES
  LA API DEBERÁ responder `404` con el mismo cuerpo `problem+json` en todos los casos (sin revelar
  cuál de ellos ocurre), tanto en `/stops/{stop_id}` como en `/stops/{stop_id}/arrivals`.
  *Verificación:* integration
- **stop_arrivals_api.AC-03** — SI no hay ningún feed GTFS activo, ENTONCES LA API DEBERÁ
  responder `503` (`problem+json`, `type` = `…/network-unavailable`).
  *Verificación:* integration

### Llegadas en tiempo real

- **stop_arrivals_api.AC-04** — CUANDO se hace `GET /api/v1/stops/{stop_id}/arrivals?t={token}` y
  el SAE responde, LA API DEBERÁ devolver `source = "REALTIME"`, `generated_at`,
  `refresh_after_s` (igual al TTL de la caché del SAE) y una entrada por llegada del SAE, ordenadas
  por `arrival_at`, con: `line`, `destination`, `direction_id`, `in_network`, `kind`, `minutes`,
  `arrival_at`, `line_color`, `line_text_color`, `vehicle`, `occupancy` y `can_alert`.
  *Verificación:* integration (replay de la parada 508)
- **stop_arrivals_api.AC-05** — CUANDO la línea de una llegada pasa por la parada en un único
  sentido según el GTFS (sentidos derivados en la importación, ver `gtfs_import` AC-24/AC-25), EL
  SISTEMA DEBERÁ asignar ese `direction_id` sin comparar textos.
  *Verificación:* unit
- **stop_arrivals_api.AC-06** — CUANDO la línea pasa por la parada en más de un sentido, EL
  SISTEMA DEBERÁ comparar el destino del SAE con **todos** los headsigns de los viajes de esa
  línea que paran allí (`NetworkRepository.headsigns_at_stop`), tras normalizar (minúsculas, sin
  acentos ni puntuación, abreviaturas expandidas según la tabla de alias), y elegir el sentido del
  headsign más parecido, siempre que la similitud supere el umbral y la mejor similitud de ese
  sentido sea estrictamente mayor que la mejor de cualquier otro sentido.
  *Verificación:* unit (casos reales obtenidos en E-01)
- **stop_arrivals_api.AC-07** — SI no se puede resolver el sentido, ENTONCES la llegada DEBERÁ
  devolverse con `direction_id = null` y `can_alert = false`, y EL SISTEMA DEBERÁ registrar
  `arrivals.direction_unresolved` con línea y destino.
  *Verificación:* unit + integration
- **stop_arrivals_api.AC-08** — SI la línea de una llegada no existe en el GTFS (p. ej. nocturnas),
  ENTONCES la llegada DEBERÁ devolverse con su tiempo, `in_network = false`,
  `direction_id = null`, `vehicle = null`, `occupancy = null` y `can_alert = false`.
  *Verificación:* integration (grabación con línea fuera de red, real o derivada)
- **stop_arrivals_api.AC-09** — EL SISTEMA DEBERÁ devolver como `destination` el `headsign` del
  GTFS cuando el sentido está resuelto, y el texto del SAE en otro caso.
  *Verificación:* unit
- **stop_arrivals_api.AC-10** — CUANDO una llegada tiene sentido resuelto, EL SISTEMA DEBERÁ
  emparejarla con el viaje programado de esa línea y sentido cuya hora en la parada sea la más
  próxima a `arrival_at`, dentro de una tolerancia de 20 min (configurable); SI varias llegadas de
  la misma línea y sentido compiten por viajes, ENTONCES cada viaje DEBERÁ asignarse como máximo
  a una llegada, respetando el orden temporal.
  *Verificación:* unit
- **stop_arrivals_api.AC-11** — SI no hay viaje dentro de la tolerancia, ENTONCES la llegada
  DEBERÁ devolverse con `vehicle = null` y `occupancy = null`, manteniendo `can_alert = true` si
  el sentido está resuelto.
  *Verificación:* unit
- **stop_arrivals_api.AC-12** — CUANDO una llegada tiene viaje emparejado, LA API DEBERÁ incluir
  `vehicle = {trip_id, service_date}` y `occupancy = {level, has_free_seats, free_seats}` según
  el sensor y el clasificador; SI el sensor no devuelve lectura, ENTONCES `occupancy = null`.
  *Verificación:* integration

### Respaldo por horario (RF-09)

- **stop_arrivals_api.AC-13** — SI el SAE no está disponible (`ArrivalsUnavailableError`),
  ENTONCES LA API DEBERÁ responder `200` con `source = "SCHEDULED"` y, por cada par (línea,
  sentido) de la parada, como máximo las 2 próximas pasadas programadas en los 90 min siguientes,
  con `kind = "CLOCK_TIME"`, `destination` = headsign, `vehicle` del viaje programado, ocupación y
  `can_alert = true`; y EL SISTEMA DEBERÁ registrar `arrivals.fallback` con el motivo.
  *Verificación:* integration (fuente que falla + FakeClock)
- **stop_arrivals_api.AC-14** — SI no hay pasadas programadas en esa ventana, ENTONCES LA API
  DEBERÁ responder `200` con la lista vacía y `source = "SCHEDULED"`.
  *Verificación:* integration
- **stop_arrivals_api.AC-15** — CUANDO el SAE responde sin llegadas, LA API DEBERÁ responder con la
  lista vacía y `source = "REALTIME"`, sin recurrir al horario.
  *Verificación:* integration

### Contrato y rendimiento

- **stop_arrivals_api.AC-16** — LAS RESPUESTAS de ambos endpoints DEBERÁN incluir
  `Cache-Control: no-store`, y su esquema DEBERÁ estar descrito en el OpenAPI con ejemplos.
  *Verificación:* integration (cabecera; presencia de esquemas en `/openapi.json`)
- **stop_arrivals_api.AC-17** — MIENTRAS el dato del SAE de una parada esté en caché, 200
  peticiones secuenciales a `/arrivals` de esa parada en el equipo de desarrollo DEBERÁN tener un
  p95 inferior a 100 ms y no generar ninguna consulta adicional al SAE.
  *Verificación:* integration (contador de la fuente) + medición `slow` anotada en el progreso
  (el objetivo de 500 ms en la Raspberry se valida en `nfr_validation`)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-06 Mostrar parada y líneas desde el QR | AC-01, AC-02, AC-03 |
| RF-09 Respaldo por horario | AC-13, AC-14 |
| RF-11 Normalización y líneas fuera del GTFS | AC-04, AC-08, AC-15 |
| RF-15 Nivel de ocupación y asientos | AC-12 |
| RF-32 Nombres del GTFS | AC-01, AC-09 |
| RNF-01 Rendimiento | AC-17 |
| RNF-08 Uso respetuoso del SAE | AC-17 |
| R-02 Destino SAE ↔ sentido GTFS | AC-05, AC-06, AC-07 |
| ADR-013 Identidad por viaje | AC-10, AC-11 |
| Contrato API (ADR-010) | AC-16 |
