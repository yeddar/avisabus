# Sensor de ocupación — tasks

> Feature: `occupancy_sensor` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-14, RF-15 · Casos de uso: CU-01 · Depende de: project_scaffold, gtfs_import

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Modelos de ocupación y `classify_occupancy`; validación de configuración.
  - AC: occupancy_sensor.AC-01, AC-02, AC-03
  - Ficheros: `domain/models/occupancy.py`, `domain/services/occupancy_classifier.py`, `config.py`, `tests/unit/test_occupancy_classifier.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_occupancy_classifier.py`

- [ ] **T-02** — Funciones de simulación puras (factores, progreso, ocupados) con tests de
  propiedades.
  - AC: occupancy_sensor.AC-05, AC-06, AC-07, AC-10
  - Ficheros: `domain/services/occupancy_simulation.py`, `tests/unit/test_occupancy_simulation.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_occupancy_simulation.py`

- [ ] **T-03** — Puertos `OccupancySensor` y `OccupancyOverrideRepository`; ampliación
  `NetworkRepository.trip_line`.
  - AC: (base)
  - Ficheros: `domain/ports/occupancy.py`, `domain/ports/network.py`, `adapters/outbound/persistence/sqlite_network.py`, `tests/integration/test_network_repository.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_network_repository.py -k trip_line`

- [ ] **T-04** — `SimulatedOccupancySensor` (determinismo, progreso desde horarios, viaje
  inexistente, forzado con caché de 5 s).
  - AC: occupancy_sensor.AC-04, AC-08, AC-09, AC-11, AC-14
  - Ficheros: `adapters/outbound/occupancy/simulated_sensor.py`, `tests/unit/test_simulated_occupancy_sensor.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_simulated_occupancy_sensor.py`

- [ ] **T-05** — Repositorio SQLite de forzados, casos de uso y CLI `occupancy override`.
  - AC: occupancy_sensor.AC-11, AC-12, AC-13
  - Ficheros: `adapters/outbound/persistence/sqlite_occupancy_override.py`, `application/set_occupancy_override.py`, `adapters/inbound/cli/occupancy.py`, `tests/integration/test_cli_occupancy.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_occupancy.py`

- [ ] **T-06** — Variables en `.env.example`, composición en `main.py` y verificación completa.
  - Verificación: `./init.sh verify`
