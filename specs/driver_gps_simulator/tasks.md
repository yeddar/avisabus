# Simulador de recorrido del conductor — tasks

> Feature: `driver_gps_simulator` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-34, RNF-07 · Casos de uso: CU-14 · Depende de: driver_session

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — `simulate_route`.
  - AC: driver_gps_simulator.AC-02
  - Ficheros: `domain/services/route_simulation.py`, `tests/unit/test_route_simulation.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_route_simulation.py`

- [ ] **T-02** — Comando `simulate` con cliente HTTP, cierre garantizado y salida por consola.
  - AC: driver_gps_simulator.AC-01, AC-03, AC-04, AC-05
  - Ficheros: `adapters/inbound/cli/{simulate,main}.py`, `tests/integration/test_cli_simulate.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_simulate.py`

- [ ] **T-03** — Verificación completa.
  - Verificación: `./init.sh verify`
