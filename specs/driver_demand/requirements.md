# Demanda del conductor — requirements

> Feature: `driver_demand` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-23, RF-27, RF-28, RF-29, RNF-02, RNF-06 · Casos de uso: CU-03 (5a), CU-09, CU-10 (3) · Depende de: realtime_events, alert_create, driver_session

## Contexto

Es el corazón del bloque 4: lo que el conductor ve y cómo le llegan las solicitudes.

- **Entrega:** una solicitud se entrega al turno abierto que lleva **su viaje** (ADR-016,
  ADR-018). Si no hay ninguno, queda "sin conductor conectado" y se entrega en cuanto un conductor
  elija esa salida (CU-03 5a). Si el turno se cierra o cambia de salida, sus solicitudes vuelven a
  "sin conductor conectado" (CU-10 3). El pasajero se entera por su WebSocket.
- **Vista del conductor:** sus próximas paradas con cuántas personas esperan **a su autobús**
  (decisión de la persona: no cuenta a quien eligió otro autobús de la línea) y qué necesidades
  tienen, sus plazas libres y una **alerta de capacidad** si esperan más personas que plazas
  libres (RF-29). Se envía siempre como instantánea completa por `/ws/driver` (ADR-009).

## Alcance

- `SessionDriverDirectory` (implementa `DriverDirectory`) y `DemandSessionListener` (implementa
  `DriverSessionListener`) y `DemandViewNotifier` (implementa `DriverViewNotifier`).
- Entrega y retirada de solicitudes con sus eventos al pasajero.
- Construcción de la vista (`driver.view`) con paradas, demanda, plazas y alertas.
- `/ws/driver` y `GET /api/v1/driver/sessions/current/view`.
- Tarea de fondo que refresca las vistas abiertas.

## Fuera de alcance

- Interfaz y tono de aviso (`driver_ui`).

## Criterios de aceptación

### Entrega de solicitudes

- **driver_demand.AC-01** — CUANDO se crea una solicitud para un viaje que lleva un turno abierto,
  EL SISTEMA DEBERÁ crearla en `DELIVERED` con ese turno (`alert_create.AC-09`), publicar
  `alert.delivered` al pasajero y una vista nueva a ese conductor.
  *Verificación:* integration
- **driver_demand.AC-02** — CUANDO un turno elige una salida, EL SISTEMA DEBERÁ entregarle las
  solicitudes `PENDING_DRIVER` de ese viaje (pasan a `DELIVERED`, `alert.delivered` a cada
  pasajero) y, SI el turno tenía otra salida, ENTONCES las solicitudes entregadas por la anterior
  DEBERÁN volver a `PENDING_DRIVER` con `alert.registered` (y el aviso actualizado) a su pasajero.
  *Verificación:* integration
- **driver_demand.AC-03** — CUANDO un turno se cierra por cualquier motivo, EL SISTEMA DEBERÁ
  devolver sus solicitudes a `PENDING_DRIVER` publicando `alert.registered` a cada pasajero, y
  enviar `{"type": "session.closed", "reason": …}` a sus conexiones `/ws/driver` antes de
  cerrarlas con `1000`.
  *Verificación:* integration
- **driver_demand.AC-04** — CUANDO una solicitud entregada se cancela o caduca
  (`DriverViewNotifier.alert_removed`), EL SISTEMA DEBERÁ publicar una vista nueva a su turno.
  *Verificación:* unit + integration

### Vista del conductor

- **driver_demand.AC-05** — LA VISTA DEBERÁ incluir: la salida (línea, sentido, `headsign`,
  hora de salida), `gps`, `off_route`, `finished` y las próximas paradas de `driver_session` (hasta
  5) con, para cada una, `waiting` (solicitudes entregadas a este turno en esa parada y en esa
  aparición del viaje), el recuento de cada necesidad (`RAMP`, `EXTRA_TIME`, `SEAT`, `VISUAL`) y
  los `alert_id` de esas solicitudes; y `total_waiting` como suma de las paradas mostradas. NO
  DEBERÁ incluir ningún dato del dispositivo del pasajero.
  *Verificación:* unit
- **driver_demand.AC-06** — LA VISTA DEBERÁ incluir `free_places` y `free_seats` del sensor de
  ocupación para el viaje del turno (`null` sin dato) y `capacity_alert = true` SI `total_waiting
  > free_places`, y `seat_alert = true` SI el número de solicitudes con `SEAT` en las paradas
  mostradas > `free_seats` (RF-29, CU-09 2a). Sin dato de ocupación, ambas son `false`.
  *Verificación:* unit (tabla de casos)
- **driver_demand.AC-07** — SIN salida elegida, LA VISTA DEBERÁ tener `service = null`, sin
  paradas y sin alertas.
  *Verificación:* unit

### Canal del conductor

- **driver_demand.AC-08** — CUANDO un cliente abre `/ws/driver`, EL SISTEMA DEBERÁ esperar
  `{"type": "hello", "session_token": …}` en 5 s (`4408` si no llega); SI el token no es de un
  turno abierto, ENTONCES DEBERÁ cerrar con `4401`; si es válido, DEBERÁ suscribirse a
  `driver:<session_id>`, enviar la vista actual y después cada vista nueva, con `ping` cada 25 s
  (mismo protocolo y límites que `realtime_events`).
  *Verificación:* integration
- **driver_demand.AC-09** — EL SISTEMA DEBERÁ publicar una vista nueva a un turno cuando cambie
  algo de lo que muestra (solicitudes, salida, próximas paradas, `gps`, `off_route`, `finished`,
  plazas), como máximo una por segundo por turno (las que lleguen antes se agrupan), y una tarea
  cada 15 s DEBERÁ recalcular las vistas abiertas para reflejar `gps = STALE` y la ocupación.
  *Verificación:* unit (`FakeClock`, contador de publicaciones) + integration
- **driver_demand.AC-10** — CUANDO se hace `GET /api/v1/driver/sessions/current/view` con un
  token válido, LA API DEBERÁ devolver la misma vista (respaldo mientras el WebSocket no
  conecta).
  *Verificación:* integration
- **driver_demand.AC-11** — LA LATENCIA entre crear o cancelar una solicitud y la llegada de la
  vista nueva al conductor DEBERÁ ser ≤ 5 s (RNF-02) en la prueba de integración.
  *Verificación:* integration

### Privacidad

- **driver_demand.AC-12** — LOS LOGS de entrega (`alert.delivered`, `alert.undelivered`) DEBERÁN
  llevar `alert_id` y `session_id`, sin necesidades ni datos del dispositivo; la vista no se
  registra.
  *Verificación:* unit (logger falso)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-23 Entrega / sin conductor | AC-01, AC-02, AC-03 |
| RF-27 Vista con ≥ 3 paradas y necesidades | AC-05, AC-07 |
| RF-28 Actualización en tiempo real | AC-04, AC-08, AC-09 |
| RF-29 Alerta de capacidad | AC-06 |
| RNF-02 ≤ 5 s | AC-11 |
| RNF-06 Privacidad | AC-05, AC-12 |
| CU-03 5a · CU-09 · CU-10 3 | AC-02, AC-05, AC-06, AC-03 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-09 | Versión inicial aprobada (PR #46). | CP-1 del bloque 4. Aprobada por la persona. |
