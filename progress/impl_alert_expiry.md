# Implementación: alert_expiry
Spec: specs/alert_expiry/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04
Rama: `feat/alert_expiry` (apilada sobre `feat/alert_cancel`, `feat/alert_create` y
`feat/realtime_events`). Exploración usada: `progress/explore_passage.md` (E-01).

## Tareas
- [x] T-01 `ExpiryReason`, `observe_passage` y `expiry_reason` (AC-01, AC-02, AC-05, AC-06, AC-07)
- [ ] T-02 `GetStopArrivals.for_stop`, `ExpireAlert`, `WatchPassages` y `ExpireDueAlerts`
- [ ] T-03 `run_periodic`, `lifespan`, configuración y `.env.example`
- [ ] T-04 Integración
- [ ] T-05 Sesión real `stop_508_peak`
- [ ] T-06 Verificación completa

## Cambios en código de otras features

## Decisiones locales
- T-01: `AVISABUS_PASSAGE_WINDOW_MIN` se queda en **2 min** (valor por defecto del design; E-01:
  4 de 6 pasos reales detectados y 0 prematuros, el primer prematuro aparece con 4 min). El `≤` de
  AC-02 es inclusivo (E-01: la 70 desaparece con exactamente 120 s).
- T-01: `PassageObservation` lleva valores por defecto `None` en `arrival_at` y `delay_s` (ausente
  = `PassageObservation(False)`). Si el viaje está presente pero su aparición en la parada
  (`stop_sequence` del aviso) ya no está en el feed activo (carrera con una reimportación),
  `delay_s = None` y `observe_passage` conserva el `last_delay_s` anterior. Presente sin
  `arrival_at` → `ValueError` (error de programación).
- T-01: el cálculo de `next_stop_scheduled_at` del design §3 vive como función pura
  `next_stop_scheduled_at(stop_times, stop_sequence, service_date)` en
  `domain/services/expiry_policy.py` (lo prueba `test_expiry_policy.py` con hora > 24 h, como pide
  el design §6). La siguiente parada es la entrada de menor `stop_sequence` mayor que la del aviso.

## Bloqueos
Ninguno.

## Verificación
