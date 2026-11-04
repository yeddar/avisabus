# API de parada y llegadas — requirements

> Feature: `stop_arrivals_api` · Versión: 1.6 · Estado: APPROVED
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
  headsign más parecido, siempre que la similitud alcance el umbral (≥ 0,2 por defecto) y la mejor
  similitud de ese sentido sea estrictamente mayor que la mejor de cualquier otro sentido. El orden
  completo de resolución está en design §3 (sentido único → override → texto → sentido que sale →
  sin resolver).
  *Verificación:* unit (casos reales de E-01 y E-03: `progress/explore_destinations.md` H-2 y H-7)
- **stop_arrivals_api.AC-07** — SI no se puede resolver el sentido, ENTONCES la llegada DEBERÁ
  devolverse con `direction_id = null` y `can_alert = false`, y EL SISTEMA DEBERÁ registrar
  `arrivals.direction_unresolved` con línea y destino.
  *Verificación:* unit + integration
- **stop_arrivals_api.AC-08** — SI la línea de una llegada no existe en el GTFS (p. ej. nocturnas),
  ENTONCES la llegada DEBERÁ devolverse con su tiempo, `in_network = false`,
  `direction_id = null`, `vehicle = null`, `occupancy = null` y `can_alert = false`.
  *Verificación:* integration (grabación con línea fuera de red: en `gtfs_mini` solo la 98 de las
  líneas de la parada 2070 es de la red, así que la 73, la 95 y la 99 de la sesión grabada sirven
  como caso **real** de línea fuera de red)
- **stop_arrivals_api.AC-09** — EL SISTEMA DEBERÁ devolver como `destination` un `headsign` del
  GTFS cuando el sentido está resuelto, y el texto del SAE en otro caso. El headsign se elige
  según cómo se resolvió el sentido:
  - sentido único: el headsign más frecuente de ese sentido entre los viajes que paran allí;
  - *override*: el headsign del *override*;
  - texto o sentido que sale: el headsign de ese sentido más parecido al texto del SAE (misma
    similitud de AC-06); a igualdad, el más frecuente en la parada.
  *Verificación:* unit
- **stop_arrivals_api.AC-10** — CUANDO hay llegadas con sentido resuelto, EL SISTEMA DEBERÁ
  emparejar, por cada línea y sentido, el **conjunto** de sus llegadas con viajes programados
  mediante una asignación óptima que: (1) maximice el número de llegadas emparejadas; (2) a
  igualdad, minimice la suma de `|hora programada − arrival_at|`; (3) use cada viaje como máximo
  una vez; (4) conserve el orden (a llegadas posteriores, viajes con hora programada posterior); y
  (5) solo empareje dentro de una tolerancia de **10 min** (configurable). EL EMPAREJAMIENTO DEBERÁ
  ser estable: con los mismos datos de entrada da siempre el mismo resultado.
  *Verificación:* unit (incluido el caso real de dos autobuses seguidos de la 93 en la 508, en el
  que la asignación voraz elegía un viaje a −12 min, y el caso de entradas duplicadas)
- **stop_arrivals_api.AC-11** — SI no hay viaje dentro de la tolerancia, ENTONCES la llegada
  DEBERÁ devolverse con `vehicle = null` y `occupancy = null`. (v1.6) `can_alert` sigue la regla
  de `alert_create.AC-01`: sin viaje emparejado es `false`.
  *Verificación:* unit
- **stop_arrivals_api.AC-12** — CUANDO una llegada tiene viaje emparejado, LA API DEBERÁ incluir
  `vehicle = {trip_id, service_date}` y `occupancy = {level, has_free_seats, free_seats}` según
  el sensor y el clasificador; SI el sensor no devuelve lectura, ENTONCES `occupancy = null`.
  *Verificación:* integration

- **stop_arrivals_api.AC-19** — SI el sentido no se resuelve por sentido único, override ni
  texto, Y exactamente uno de los sentidos de la línea tiene viajes que **empiezan** en esa parada,
  ENTONCES EL SISTEMA DEBERÁ asignar ese sentido ("sentido que sale"): en una cabecera, el autobús
  al que se sube el pasajero es el que sale.
  *Verificación:* unit (cabeceras de C1, 1959 y 2277, con el texto genérico real "Cntr.Històric" y
  candidatos tomados del feed real) + integration (`gtfs_mini` no contiene la C1: el caso de
  integración se ejecuta con el feed completo en un test marcado `slow`)
- **stop_arrivals_api.AC-20** — LOS *OVERRIDES* DE SENTIDO DEBERÁN expresarse como
  `"{línea}|{destino SAE}" → "{headsign GTFS}"` (no por número de sentido, que puede cambiar al
  importar un feed nuevo) y resolverse a sentido en cada consulta a partir de los headsigns de la
  parada; SI al arrancar algún override nombra una línea o un headsign inexistentes en la red
  activa, ENTONCES EL SISTEMA DEBERÁ registrar `arrivals.override_invalid` con la entrada y
  ignorarla (sin impedir el arranque). SI el fichero de *overrides* configurado no existe o no es
  un JSON válido con ese formato, ENTONCES EL SISTEMA DEBERÁ negarse a arrancar con un error de
  configuración. La validación contra la red se hace **solo al arrancar** (limitaciones en design
  §4).
  *Verificación:* unit + integration
- **stop_arrivals_api.AC-21** — CADA LLEGADA DEBERÁ incluir `sae_destination` con el texto de
  destino tal como lo da el SAE (`null` si `source = "SCHEDULED"`), además de `destination`
  (AC-09), para que la interfaz pueda mostrar lo que rotula el autobús.
  *Verificación:* integration
- **stop_arrivals_api.AC-22** — SI el SAE devuelve entradas duplicadas (misma línea, destino y
  tiempo), ENTONCES EL SISTEMA DEBERÁ conservarlas como llegadas distintas y el emparejamiento NO
  DEBERÁ asignar el mismo viaje a las dos.
  *Verificación:* unit

### Respaldo por horario (RF-09)

- **stop_arrivals_api.AC-13** — SI el SAE no está disponible (`ArrivalsUnavailableError`),
  ENTONCES LA API DEBERÁ responder `200` con `source = "SCHEDULED"` y, por cada par (línea,
  sentido) de la parada, como máximo las 2 próximas pasadas programadas en los 90 min siguientes,
  con `kind = "CLOCK_TIME"`, `destination` = headsign, `vehicle` del viaje programado, ocupación y
  `can_alert` según `alert_create.AC-01` (v1.6: `true` si llega en ≤ 30 min); y EL SISTEMA DEBERÁ registrar `arrivals.fallback` con el motivo.
  *Verificación:* integration (fuente que falla + FakeClock)
- **stop_arrivals_api.AC-14** — SI no hay pasadas programadas en esa ventana, ENTONCES LA API
  DEBERÁ responder `200` con la lista vacía y `source = "SCHEDULED"`.
  *Verificación:* integration
- **stop_arrivals_api.AC-15** — CUANDO el SAE responde sin llegadas, LA API DEBERÁ responder con la
  lista vacía y `source = "REALTIME"`, sin recurrir al horario.
  *Verificación:* integration

- **stop_arrivals_api.AC-18** — CUANDO la ventana de horarios consultada (respaldo por horario o
  candidatos del emparejamiento de viajes) cruza el cambio de día, EL SISTEMA DEBERÁ incluir las
  pasadas de todos los días de servicio que caen en la ventana, también las del día de servicio
  siguiente (p. ej. a las 23:45 con ventana de 90 min, un viaje del día siguiente con hora 00:20).
  *Verificación:* integration (copia de `gtfs_mini` con un viaje sintético a las 00:20 del día de
  servicio siguiente)

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
| RF-09 Respaldo por horario | AC-13, AC-14, AC-18 |
| RF-11 Normalización y líneas fuera del GTFS | AC-04, AC-08, AC-15 |
| RF-15 Nivel de ocupación y asientos | AC-12 |
| RF-32 Nombres del GTFS | AC-01, AC-09 |
| RNF-01 Rendimiento | AC-17 |
| RNF-08 Uso respetuoso del SAE | AC-17 |
| R-02 Destino SAE ↔ sentido GTFS | AC-05, AC-06, AC-07, AC-19, AC-20 |
| ADR-013 Identidad por viaje | AC-10, AC-11, AC-22 |
| RF-32 / UX: destino rotulado | AC-09, AC-21 |
| Contrato API (ADR-010) | AC-16 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-10-31 | Versión inicial aprobada (PR #2) | — |
| 1.1 | 2026-10-31 | `tasks.md` E-01: pregunta explícita sobre el destino que da el SAE en las circulares C1, C2 y C3. Sin cambios en AC ni en el diseño. | Riesgo señalado en `progress/explore_gtfs_feed.md`. Aprobada por la persona. |
| 1.2 | 2026-10-31 | AC-18: horarios que cruzan el cambio de día (incluye el día de servicio siguiente). T-05b modifica `SqliteNetworkRepository.scheduled_stop_times` (código de `gtfs_import`). | Hallazgo N-07 de `progress/review_gtfs_import.md`: la consulta solo miraba `D − 1` y `D`. Aprobada por la persona. |
| 1.3 | 2026-11-02 | AC-08 y design §7: en `gtfs_mini`, las líneas 73, 95 y 99 de la parada 2070 son un caso real de línea fuera de red en los tests. Sin cambios de código ni de tareas. | Observación del orquestador tras `sae_arrivals_source` (la sesión grabada incluye la 2070). Aprobada por la persona. |
| 1.4 | 2026-11-03 | Orden de resolución del sentido con la regla del **sentido que sale** (AC-19); overrides por headsign y validados (AC-20); umbral 0,2; alias revisados (sin `c → carrer`, con palabras vacías y abreviaturas de E-01); emparejamiento **óptimo con orden** y tolerancia de 10 min (AC-10); `sae_destination` (AC-21); entradas duplicadas (AC-22). T-02, T-03, T-05c, T-06 y T-07 ampliadas. | CP-3 tras las exploraciones E-01, E-02 y E-03 (`progress/explore_destinations.md`). Aprobada por la persona. |
| 1.5 | 2026-11-03 | Solo documentación, sin cambios de código ni tareas nuevas: AC-06 "alcanza" (≥) el umbral, como design §3; AC-09 fija qué headsign se devuelve según cómo se resolvió el sentido (lo implementado); AC-19 aclara que la C1 se cubre con muestras reales y un test `slow` (no está en `gtfs_mini`); AC-20 recoge el error de configuración con fichero ilegible y la validación solo al arrancar; design §3 con el headsign real de la 93, §4 con limitaciones de los *overrides* y §6 con la ruta relativa a `backend/`. | Hallazgos P-1, P-2, O-1…O-4 y NB-3 de la revisión de `stop_arrivals_api`. Aprobada por la persona (PR #7). |
| 1.6 | 2026-11-04 | AC-11 y AC-13: `can_alert` pasa a definirse en `alert_create.AC-01` (requiere viaje emparejado y llegada en ≤ 30 min). El código y sus tests los cambia `alert_create` T-01; `alert_expiry` T-02 añade `GetStopArrivals.for_stop`. | Bloque 3: la solicitud va al autobús elegido (ADR-016) y caduca a los 30 min. Aprobada por la persona (PR #37). |
