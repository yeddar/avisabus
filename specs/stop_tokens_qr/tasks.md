# Tokens de parada y QR — tasks

> Feature: `stop_tokens_qr` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-05, RNF-07 · Casos de uso: CU-12 · Depende de: gtfs_import

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Configuración del secreto (`stop_token_secret`), validación por entorno y
  advertencia de secreto de desarrollo.
  - AC: stop_tokens_qr.AC-04, AC-05
  - Ficheros: `config.py`, `.env.example`, `tests/unit/test_settings_stop_token.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_settings_stop_token.py`

- [ ] **T-02** — Puerto `StopTokenSigner` y `HmacStopTokenSigner` con vector de prueba y casos
  inválidos.
  - AC: stop_tokens_qr.AC-01, AC-02, AC-03
  - Ficheros: `domain/ports/stop_token.py`, `adapters/outbound/security/hmac_stop_token.py`, `tests/unit/test_hmac_stop_token.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_hmac_stop_token.py`

- [ ] **T-03** — `build_stop_url`.
  - AC: stop_tokens_qr.AC-06
  - Ficheros: `domain/services/stop_url.py`, `tests/unit/test_stop_url.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_stop_url.py`

- [ ] **T-04** — Puerto `QrRenderer` y `SegnoQrRenderer` (SVG con etiqueta, PNG ≥ 600 px con
  etiqueta, nivel M, borde 4).
  - AC: stop_tokens_qr.AC-07, AC-09, AC-12
  - Ficheros: `domain/ports/qr.py`, `adapters/outbound/qr/segno_renderer.py`, `tests/integration/test_segno_renderer.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_segno_renderer.py`

- [ ] **T-05** — Caso de uso `GenerateStopQrCodes` (con fakes: paradas existentes, inexistentes,
  sin feed).
  - AC: stop_tokens_qr.AC-08, AC-10, AC-11
  - Ficheros: `application/generate_stop_qr_codes.py`, `domain/errors.py`, `tests/unit/test_generate_stop_qr_codes.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_generate_stop_qr_codes.py`

- [ ] **T-06** — CLI `avisabus qr generate` (escritura de ficheros, `index.csv`, códigos de salida).
  - AC: stop_tokens_qr.AC-07, AC-08, AC-09, AC-10, AC-11
  - Ficheros: `adapters/inbound/cli/qr.py`, `tests/integration/test_cli_qr.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_qr.py`

- [ ] **T-07** — Verificación completa.
  - Verificación: `./init.sh verify`
