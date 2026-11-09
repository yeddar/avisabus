# Códigos de conductor — tasks

> Feature: `driver_codes_cli` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-24, RF-33, RNF-06, RNF-07 · Casos de uso: CU-13 · Depende de: project_scaffold

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — `DriverCode`, puertos, `HmacDriverCodeHasher`, `SecretsCodeGenerator` y casos de
  uso.
  - AC: driver_codes_cli.AC-01, AC-03, AC-06
  - Ficheros: `domain/models/driver.py`, `domain/ports/driver.py`, `application/driver_codes.py`, `adapters/outbound/security/{hmac_driver_code_hasher,secrets_code_generator}.py`, `tests/unit/test_driver_codes.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_driver_codes.py`

- [ ] **T-02** — Tabla `driver_code` y `SqliteDriverCodeRepository`.
  - AC: driver_codes_cli.AC-01, AC-03, AC-05
  - Ficheros: `adapters/outbound/persistence/{sqlite_driver_codes,db}.py`, `tests/integration/test_driver_code_repository.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_driver_code_repository.py`

- [ ] **T-03** — Comandos `driver-codes create/list/revoke` y composición en la CLI.
  - AC: driver_codes_cli.AC-01, AC-02, AC-03, AC-04, AC-05, AC-06
  - Ficheros: `adapters/inbound/cli/{driver_codes,main,container}.py`, `tests/integration/test_cli_driver_codes.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_driver_codes.py`

- [ ] **T-04** — Verificación completa.
  - Verificación: `./init.sh verify`
