# Esqueleto del proyecto — tasks

> Feature: `project_scaffold` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RNF-09, RNF-10, RNF-11, RNF-13 · Casos de uso: — · Depende de: —

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Ficheros de raíz: `.gitignore`, `.env.example` (vacío de momento salvo
  cabecera), `backend/tests/fixtures/{gtfs_mini,sae_recordings}/README.md`.
  - AC: project_scaffold.AC-20, AC-21
  - Ficheros: `.gitignore`, `.env.example`, `backend/tests/fixtures/**/README.md`
  - Verificación: `git status --ignored` muestra `data/` ignorado

- [ ] **T-02** — Paquete backend con `pyproject.toml`, estructura de capas vacía, configuración
  de ruff, mypy y pytest (cobertura, `--disable-socket`, marcador `spec`).
  - AC: project_scaffold.AC-01, AC-02, AC-05, AC-06
  - Ficheros: `backend/pyproject.toml`, `backend/src/avisabus/**/__init__.py`,
    `backend/tests/unit/test_no_network.py`
  - Verificación: `cd backend && uv sync && uv run ruff check . && uv run mypy && uv run pytest`

- [ ] **T-03** — Contratos de import-linter y test que demuestra que se rompen con importaciones
  prohibidas.
  - AC: project_scaffold.AC-03, AC-04
  - Ficheros: `backend/.importlinter`, `backend/tests/unit/test_architecture_contracts.py`
  - Verificación: `cd backend && uv run lint-imports && uv run pytest tests/unit/test_architecture_contracts.py`

- [ ] **T-04** — Puerto `Clock`, `SystemClock`, `FakeClock` (en `tests/support`) y tests.
  - AC: project_scaffold.AC-07, AC-08
  - Ficheros: `domain/ports/clock.py`, `adapters/outbound/clock.py`,
    `tests/support/fake_clock.py`, `tests/unit/test_clock.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_clock.py`

- [ ] **T-05** — `Settings` con prefijo `AVISABUS_` y `.env.example` completo.
  - AC: project_scaffold.AC-09
  - Ficheros: `config.py`, `.env.example`, `tests/unit/test_settings.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_settings.py`

- [ ] **T-06** — Logging JSON con structlog.
  - AC: project_scaffold.AC-12
  - Ficheros: `logging.py`, `tests/unit/test_logging.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_logging.py`

- [ ] **T-07** — App FastAPI (`create_app`), ruta de salud, manejador de errores problem+json,
  composition root `main.py`.
  - AC: project_scaffold.AC-10, AC-11
  - Ficheros: `adapters/inbound/http/**`, `main.py`, `tests/integration/test_health.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_health.py`

- [ ] **T-08** — CLI Typer con comando raíz `avisabus` y script de proyecto.
  - AC: project_scaffold.AC-13
  - Ficheros: `adapters/inbound/cli/main.py`, `pyproject.toml`, `tests/integration/test_cli.py`
  - Verificación: `cd backend && uv run avisabus --help && uv run pytest tests/integration/test_cli.py`

- [ ] **T-09** — Proyecto frontend: Vite + React + TS estricto, Tailwind, router, `HomePage`,
  Prettier, ESLint (jsx-a11y, react-hooks), Vitest + Testing Library, proxy de desarrollo.
  - AC: project_scaffold.AC-14, AC-15, AC-16, AC-19
  - Ficheros: `frontend/**` (ver design §2), `frontend/tests/lint/img-without-alt.tsx`
  - Verificación: `cd frontend && npm ci && npm run lint && npm run typecheck && npm run test && npm run build`

- [ ] **T-10** — PWA (vite-plugin-pwa: manifiesto, iconos, service worker) y test del manifiesto.
  - AC: project_scaffold.AC-18
  - Ficheros: `frontend/vite.config.ts`, `frontend/public/icons/*`, `frontend/src/__tests__/pwa-manifest.test.ts`
  - Verificación: `cd frontend && npm run build && npm run test`

- [ ] **T-11** — Playwright con perfiles iPhone, Pixel y tablet horizontal + test de humo con axe.
  - AC: project_scaffold.AC-17
  - Ficheros: `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`
  - Verificación: `cd frontend && npx playwright install --with-deps chromium webkit && npm run e2e`

- [ ] **T-12** — Verificación completa.
  - AC: project_scaffold.AC-22
  - Verificación: `./init.sh verify --e2e`
