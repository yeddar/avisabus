# Eventos en tiempo real — tasks

> Feature: `realtime_events` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-23, RF-28 (base), RNF-02, RNF-06, RNF-07, RNF-12, RNF-13 · Casos de uso: CU-03, CU-04, CU-07 (canal) · Depende de: project_scaffold

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — `Event`, `DeviceId`/`parse_device_id`, `InvalidDeviceIdError`, puertos
  `EventPublisher`/`Subscription`/`DeviceHasher` y `HmacDeviceHasher`.
  - AC: realtime_events.AC-04, AC-05
  - Ficheros: `domain/models/{events,device}.py`, `domain/ports/{events,device}.py`, `domain/errors.py`, `adapters/outbound/security/hmac_device_hasher.py`, `tests/unit/test_device.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_device.py`

- [ ] **T-02** — `InMemoryEventPublisher` con colas acotadas y desbordamiento.
  - AC: realtime_events.AC-01, AC-02, AC-03
  - Ficheros: `adapters/outbound/events/in_memory.py`, `tests/unit/test_in_memory_publisher.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_in_memory_publisher.py`

- [ ] **T-03** — Filtro de excepciones en logs (H-01) y test de privacidad de logs.
  - AC: realtime_events.AC-12
  - Ficheros: `src/avisabus/logging.py`, `adapters/inbound/http/errors.py`, `tests/integration/test_log_privacy.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_log_privacy.py`

- [ ] **T-04** — `/ws/passenger`: protocolo `hello`/instantánea/eventos/`ping`, códigos de
  cierre, `ConnectionRegistry` (máximo, cierre al parar, `ws.stats`), `EmptySnapshotProvider`,
  dependencia `device_hash_from_header` y su error 400; configuración nueva en `Settings` y
  `.env.example`; composición en `main.py` y `create_app`.
  - AC: realtime_events.AC-03, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-13
  - Ficheros: `adapters/inbound/ws/{passenger,connections}.py`, `adapters/inbound/http/{device,errors,app}.py`, `config.py`, `main.py`, `.env.example`, `tests/integration/test_ws_passenger.py`, `tests/unit/test_ws_connections.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_ws_passenger.py tests/unit/test_ws_connections.py`

- [ ] **T-05** — Verificación completa.
  - Verificación: `./init.sh verify`
