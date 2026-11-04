# Implementación: alert_cancel
Spec: specs/alert_cancel/ (v1.0, APPROVED) · Ciclo de revisión: 0
Rama: `feat/alert_cancel` (apilada sobre `feat/alert_create` y `feat/realtime_events`).

## Tareas
- [x] T-01 `AlertNotFoundError` y `CancelAlert` (commit de este fichero; ver `git log`)
- [ ] T-02 Endpoint `DELETE /alerts/{alert_id}`, error 404 y composición
- [ ] T-03 Contrato del frontend (`npm run gen:api`) y verificación completa

## Decisiones locales
- T-01: `AlertNotFoundError` no lleva atributos ni identificadores en el mensaje
  (`"alert not found"`), igual que `BusNotRequestableError`: el 404 no los necesita.
- T-01: la constante `ALERT_CANCELLED = "alert.cancelled"` (nombre del evento y del log) vive en
  `application/cancel_alert.py`, el fichero que fija la tarea, y no en `alert_events.py`.
- T-01: "ya caducó" (AC-02) se modela como aviso ausente: los avisos caducados se borran
  (`AlertRepository`: "every stored alert is active") y `CancelAlert` no recibe `Clock` en el
  design §3. La carrera con la caducidad (`delete` → `False`) también da `AlertNotFoundError`, sin
  evento, sin notificar al conductor y sin log.
- T-01: un `404` no se registra en el log (el design §4 solo lista `alert.cancelled`).

## Bloqueos
Ninguno.

## Verificación
Pendiente (T-03).
