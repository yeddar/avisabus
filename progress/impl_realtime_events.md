# Implementación: realtime_events
Spec: specs/realtime_events/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-04

## Tareas
- [x] T-01 `Event`, `DeviceId`/`parse_device_id`, `InvalidDeviceIdError`, puertos
      `EventPublisher`/`Subscription`/`DeviceHasher` y `HmacDeviceHasher` (AC-04, AC-05)
- [ ] T-02 `InMemoryEventPublisher` con colas acotadas y desbordamiento (AC-01, AC-02, AC-03)
- [ ] T-03 Filtro de excepciones en logs (H-01) y test de privacidad de logs (AC-12)
- [ ] T-04 `/ws/passenger`, `ConnectionRegistry`, `EmptySnapshotProvider`,
      `device_hash_from_header`, configuración y composición (AC-03, AC-05…AC-13)
- [ ] T-05 Verificación completa

## Decisiones locales
- T-01: `Event.message()` implementa la serialización del design (`{"type": type, **payload}`).
- T-01: `SubscriptionOverflowError` (la que lanza `Subscription.next_event`, design §3) vive en
  `domain/errors.py` junto a `InvalidDeviceIdError`, como excepción del contrato del puerto.

## Bloqueos

## Verificación
