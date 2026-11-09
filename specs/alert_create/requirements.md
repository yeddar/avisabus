# Crear solicitud de parada — requirements

> Feature: `alert_create` · Versión: 1.1 · Estado: APPROVED
> Requisitos: RF-16, RF-17, RF-19, RF-20, RF-23, RNF-02, RNF-06, RNF-07 · Casos de uso: CU-03 · Depende de: stop_arrivals_api, realtime_events

## Contexto

El pasajero solicita parada a **un autobús concreto** de los que ve llegar (decisión de la persona,
ADR-016): el que elige en la vista de parada, identificado por el viaje GTFS emparejado con su
llegada (ADR-013). Puede indicar necesidades: rampa, tiempo extra de subida, asiento y
discapacidad visual (RF-17 v1.1). En la interfaz se llama **solicitud de parada**; en código y en
esta spec, **aviso** (`Alert`).

En el bloque 3 todavía no hay conductores (bloque 4): todos los avisos quedan "registrados, sin
conductor conectado" (`PENDING_DRIVER`). El caso de uso ya consulta un puerto `DriverDirectory`
para que `driver_demand` solo tenga que implementarlo.

Esta feature también fija cuándo una llegada **admite** solicitud (`can_alert` de la API de
llegadas): solo si se sabe qué autobús es (viaje emparejado) y llega en 30 min como máximo, porque
el aviso caduca a los 30 min (RF-21).

## Alcance

- Modelo `Alert`, `Need`, `AlertStatus`; repositorio SQLite de avisos.
- Caso de uso `CreateAlert` con validación del autobús, unicidad, límite de peticiones y
  asignación; `ListMyAlerts`.
- Endpoints `POST /api/v1/alerts` y `GET /api/v1/alerts/mine`.
- Proveedor de la instantánea del WebSocket del pasajero con los avisos activos.
- Nueva regla de `can_alert` en `GetStopArrivals` (`stop_arrivals_api` v1.6).

## Fuera de alcance

- Cancelación (`alert_cancel`) y caducidad (`alert_expiry`).
- Entrega real al conductor y vista del conductor (`driver_demand`, bloque 4).
- Interfaz (`passenger_alert_ui`).

## Criterios de aceptación

### Qué llegadas admiten solicitud

- **alert_create.AC-01** — LA API DE LLEGADAS (`GET /stops/{stop_id}/arrivals`) DEBERÁ devolver
  `can_alert = true` solo SI la llegada está en la red (`in_network`), tiene sentido resuelto,
  tiene viaje emparejado (`vehicle` no nulo) y `arrival_at − ahora ≤ 30 min` (configurable); en
  cualquier otro caso, `false`. Vale igual para `REALTIME` y `SCHEDULED`.
  *Verificación:* unit + integration (casos: sin sentido, sin viaje, fuera de red, a 31 min, a
  30 min, horario programado)

### Crear

- **alert_create.AC-02** — CUANDO se hace `POST /api/v1/alerts` con cabecera `X-Device-Id` válida
  y cuerpo `{stop_id, token, line, direction_id, trip_id, service_date, needs}` de una llegada que
  en ese momento tiene `can_alert = true`, LA API DEBERÁ responder `201` con el aviso: `alert_id`
  (UUID v4 aleatorio), `stop_id`, `stop_name`, `line`, `direction_id`, `destination` (la de la
  llegada), `trip_id`, `service_date`, `needs`, `status`, `created_at` y `expires_at`
  (`created_at` + 30 min).
  *Verificación:* integration (`gtfs_mini` + replay de `stop_508_peak`)
- **alert_create.AC-03** — PARA validar el autobús, EL SISTEMA DEBERÁ usar las llegadas que
  calcula `GetStopArrivals` para esa parada (la misma caché del SAE, sin peticiones adicionales);
  SI entre ellas no hay ninguna con esa línea, sentido, `trip_id` y `service_date` y
  `can_alert = true`, ENTONCES LA API DEBERÁ responder `422` (`…/bus-not-requestable`) sin crear
  nada.
  *Verificación:* integration (contador de peticiones de la fuente; autobús inexistente, ya
  pasado y a más de 30 min)
- **alert_create.AC-04** — SI el token es inválido o la parada no existe, ENTONCES LA API DEBERÁ
  responder `404` con el mismo cuerpo que los endpoints de parada (`stop_arrivals_api.AC-02`).
  *Verificación:* integration
- **alert_create.AC-05** — SI falta `X-Device-Id` o no es válido (`realtime_events.AC-04`),
  ENTONCES LA API DEBERÁ responder `400` (`…/invalid-device-id`) en `POST /alerts` y en
  `GET /alerts/mine`.
  *Verificación:* integration
- **alert_create.AC-06** — `needs` DEBERÁ ser una lista, posiblemente vacía, de valores distintos
  de `RAMP`, `EXTRA_TIME`, `SEAT` y `VISUAL`; SI contiene otro valor o repetidos, ENTONCES LA API
  DEBERÁ responder `422`. LA RESPUESTA DEBERÁ devolver `needs` en ese orden canónico.
  *Verificación:* integration

### Unicidad y límites

- **alert_create.AC-07** — SI el dispositivo ya tiene un aviso activo en esa parada y esa línea
  (para cualquier autobús), ENTONCES LA API DEBERÁ responder `200` con ese aviso sin modificarlo,
  sin crear otro y sin emitir eventos (RF-19, CU-03 4a). Dos peticiones simultáneas DEBERÁN dejar
  un único aviso.
  *Verificación:* integration (incluida la concurrencia: dos `POST` en paralelo)
- **alert_create.AC-08** — EL SISTEMA DEBERÁ limitar las peticiones a `POST /alerts` a 10 por
  dispositivo y 30 por dirección IP en 10 minutos (ventana deslizante, configurable), contando
  las que superan la validación de la petición (cabecera y cuerpo: las respondidas con `400` o con
  el `422` de validación no cuentan) salvo las que se responden con `200` por AC-07; SI se supera, ENTONCES LA API DEBERÁ
  responder `429` (`…/rate-limited`) con la cabecera `Retry-After` en segundos. Los contadores
  DEBERÁN vivir solo en memoria y no registrarse en logs.
  *Verificación:* unit (`FakeClock`) + integration

### Asignación y confirmación

- **alert_create.AC-09** — CUANDO se crea un aviso, EL SISTEMA DEBERÁ consultar `DriverDirectory`
  con el viaje del aviso; SI no hay conductor (siempre en el bloque 3), ENTONCES el aviso DEBERÁ
  quedar en `PENDING_DRIVER` y publicarse `alert.registered` con el aviso en el canal del
  dispositivo; SI hay conductor, ENTONCES DEBERÁ quedar en `DELIVERED` con su sesión y publicarse
  `alert.delivered`.
  *Verificación:* unit (directorio falso con y sin conductor) + integration (evento recibido por
  `/ws/passenger` en ≤ 5 s, RNF-02)
- **alert_create.AC-10** — CUANDO se hace `GET /api/v1/alerts/mine`, LA API DEBERÁ devolver
  `{"alerts": [...]}` con los avisos activos del dispositivo en todas las paradas, ordenados por
  `created_at`, con el mismo esquema que AC-02.
  *Verificación:* integration
- **alert_create.AC-11** — CUANDO un dispositivo envía `hello` a `/ws/passenger`, la instantánea
  `alerts.snapshot` DEBERÁ contener sus avisos activos con el mismo esquema que AC-10.
  *Verificación:* integration

### Datos y privacidad

- **alert_create.AC-12** — LOS AVISOS DEBERÁN guardarse en SQLite (sobreviven a un reinicio) con
  `device_hash` y nunca con el `X-Device-Id` en claro; las necesidades solo se guardan dentro del
  aviso.
  *Verificación:* integration (reinicio simulado con la misma BD; inspección de la tabla)
- **alert_create.AC-13** — EL SISTEMA DEBERÁ registrar `alert.created` con `alert_id`, `stop_id`,
  `line`, `direction_id` y `status`, y `alert.rejected` con `reason` (`bus_not_requestable`,
  `rate_limited`); NINGÚN log DEBERÁ incluir `device_hash`, la IP ni las necesidades.
  *Verificación:* unit (logger falso) + integration (logs capturados)
- **alert_create.AC-14** — LAS RESPUESTAS de `/alerts` DEBERÁN llevar `Cache-Control: no-store`
  y estar descritas en el OpenAPI con ejemplos; el contrato del frontend se regenera
  (`npm run gen:api`).
  *Verificación:* integration (cabecera; esquemas en el OpenAPI; test de desfase de
  `passenger_stop_view.AC-02`)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-16 Crear aviso desde la parada | AC-02, AC-03, AC-04 |
| RF-17 Necesidades (incluida la visual) | AC-06 |
| RF-19 Un aviso por dispositivo, parada y línea | AC-05, AC-07 |
| RF-20 Autobús elegido, ≤ 30 min | AC-01, AC-03 |
| RF-23 Confirmación / sin conductor | AC-09, AC-11 |
| RNF-02 Confirmación ≤ 5 s | AC-09 |
| RNF-06 Privacidad | AC-12, AC-13 |
| RNF-07 Rate limiting y validación | AC-05, AC-06, AC-08 |
| RNF-08 Sin peticiones extra al SAE | AC-03 |
| CU-03 flujos 4a, 4b, 5a | AC-07, AC-08, AC-09 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-04 | Versión inicial aprobada (PR #37). | CP-1 del bloque 3. Aprobada por la persona. |
| 1.1 | 2026-11-09 | AC-08: las peticiones rechazadas por validación (`400`, `422` de FastAPI) no cuentan para el límite, como fija el design (el limitador está en el caso de uso). | H-2 de la revisión de `alert_create`. Pendiente de aprobación. |
