# Cancelar solicitud de parada — requirements

> Feature: `alert_cancel` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-22, RF-28 (pasajero), RNF-06, RNF-07 · Casos de uso: CU-04 · Depende de: alert_create

## Contexto

El pasajero puede retirar su solicitud de parada en cualquier momento ("Cancelar solicitud",
CU-04). El aviso se **borra** con sus necesidades (RNF-06) y el resto de pestañas o dispositivos
del mismo pasajero se enteran por el WebSocket. Solo el dispositivo que lo creó puede cancelarlo,
y la respuesta no debe revelar si un `alert_id` existe para otro dispositivo.

La actualización de la vista del conductor llega con `driver_demand` (bloque 4): aquí el caso de
uso solo deja preparado el punto en el que se le notificará.

## Alcance

- Caso de uso `CancelAlert`.
- Endpoint `DELETE /api/v1/alerts/{alert_id}`.
- Evento `alert.cancelled` en el canal del dispositivo.

## Fuera de alcance

- Interfaz (`passenger_alert_ui`).
- Notificación a la vista del conductor (`driver_demand`).

## Criterios de aceptación

- **alert_cancel.AC-01** — CUANDO se hace `DELETE /api/v1/alerts/{alert_id}` con el
  `X-Device-Id` del dispositivo que lo creó, LA API DEBERÁ borrar el aviso (con sus necesidades) y
  responder `204`, y EL SISTEMA DEBERÁ publicar `{"type": "alert.cancelled", "alert_id": …}` en
  el canal del dispositivo.
  *Verificación:* integration (evento recibido por `/ws/passenger`; fila borrada)
- **alert_cancel.AC-02** — SI el aviso no existe, ya caducó o pertenece a otro dispositivo,
  ENTONCES LA API DEBERÁ responder `404` (`…/alert-not-found`) con el mismo cuerpo en los tres
  casos y sin modificar nada.
  *Verificación:* integration
- **alert_cancel.AC-03** — SI falta `X-Device-Id` o no es válido, ENTONCES LA API DEBERÁ
  responder `400` (`…/invalid-device-id`).
  *Verificación:* integration
- **alert_cancel.AC-04** — CUANDO se cancela un aviso que estaba `DELIVERED`, EL SISTEMA DEBERÁ
  llamar al notificador de conductores (`DriverViewNotifier.alert_removed(session_id)`), que en
  el bloque 3 no hace nada.
  *Verificación:* unit (notificador falso)
- **alert_cancel.AC-05** — EL SISTEMA DEBERÁ registrar `alert.cancelled` con `alert_id`, `stop_id`
  y `line`, sin `device_hash` ni necesidades; las respuestas DEBERÁN llevar
  `Cache-Control: no-store` y el endpoint DEBERÁ estar en el OpenAPI.
  *Verificación:* unit (logger falso) + integration

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-22 Cancelar aviso | AC-01, AC-02 |
| RF-28 Actualización en tiempo real | AC-01, AC-04 |
| RNF-06 Borrado de necesidades | AC-01, AC-05 |
| RNF-07 Validación / autorización | AC-02, AC-03 |
| CU-04 flujo 1a | AC-02 |
