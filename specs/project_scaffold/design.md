# Esqueleto del proyecto — design

> Feature: `project_scaffold` · Versión: 1.1 · Estado: DRAFT
> Requisitos: RNF-09, RNF-10, RNF-11, RNF-13 · Casos de uso: — · Depende de: —

## 1. Resumen

Se crean `backend/` y `frontend/` con la estructura de `docs/architecture.md` §4 y §10, las
herramientas de `docs/conventions.md` y las primitivas transversales (`Clock`, `Settings`,
logging, app FastAPI, CLI Typer).

## 2. Componentes

### Backend

```
backend/
├── pyproject.toml
├── .importlinter                     # contratos (ver §4)
├── src/avisabus/
│   ├── __init__.py                   # __version__ = "0.1.0"
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── errors.py                 # class DomainError(Exception)
│   │   ├── models/__init__.py
│   │   ├── services/__init__.py
│   │   └── ports/
│   │       ├── __init__.py
│   │       └── clock.py              # Clock (Protocol)
│   ├── application/__init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── inbound/
│   │   │   ├── http/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── app.py            # create_app(settings) -> FastAPI
│   │   │   │   ├── errors.py         # handlers problem+json
│   │   │   │   └── routes/health.py
│   │   │   ├── ws/__init__.py
│   │   │   └── cli/
│   │   │       ├── __init__.py
│   │   │       └── main.py           # app = typer.Typer(name="avisabus")
│   │   └── outbound/
│   │       ├── __init__.py
│   │       └── clock.py              # SystemClock
│   ├── background/__init__.py
│   ├── config.py                     # Settings (pydantic-settings)
│   ├── logging.py                    # configure_logging(level)
│   └── main.py                       # composition root: app = create_app(Settings())
└── tests/
    ├── conftest.py                   # fixtures: settings, fake_clock, api_client
    ├── support/fake_clock.py         # FakeClock
    ├── unit/
    ├── integration/
    └── fixtures/
        ├── gtfs_mini/README.md
        └── sae_recordings/README.md
```

`FakeClock` vive en `tests/support/` (no es código de producción).

### Frontend

```
frontend/
├── package.json · tsconfig*.json · vite.config.ts · eslint.config.js · .prettierrc
├── playwright.config.ts · vitest.config.ts (o sección test en vite.config.ts)
├── index.html                     # <html lang="es">
├── public/icons/                  # icon-192.png, icon-512.png, maskable
├── src/
│   ├── main.tsx
│   ├── app/App.tsx                # router + layout
│   ├── app/routes/HomePage.tsx    # <main><h1>AvisaBus</h1></main>  (texto temporal¹)
│   ├── features/.gitkeep
│   └── shared/.gitkeep
├── tests/lint/                    # fixture inválida para AC-15
└── e2e/smoke.spec.ts
```

¹ El texto literal del `h1` es temporal; `frontend_i18n` lo sustituye por una clave de traducción
y activa la regla `i18next/no-literal-string`.

## 3. Interfaces

```python
# domain/ports/clock.py
from datetime import datetime
from typing import Protocol

class Clock(Protocol):
    def now(self) -> datetime: ...          # siempre tz-aware UTC

# adapters/outbound/clock.py
class SystemClock:
    def now(self) -> datetime: return datetime.now(UTC)

# tests/support/fake_clock.py
class FakeClock:
    def __init__(self, start: datetime) -> None: ...   # ValueError si start.tzinfo is None
    def now(self) -> datetime: ...
    def advance(self, delta: timedelta) -> None: ...
    def set(self, value: datetime) -> None: ...        # ValueError si naive
```

```python
# config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AVISABUS_", env_file=("../.env", ".env"),
                                      extra="ignore")
    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite:///../data/avisabus.sqlite"
    public_base_url: str = "http://localhost:5173"
```

**Fichero `.env` (v1.1, AC-23).** Hay un único `.env` de referencia en la **raíz** del repositorio
(lo crea `./init.sh setup` desde `.env.example` y lo usará Docker Compose en `deployment_rpi`).
El backend se ejecuta desde `backend/`, por eso `env_file = ("../.env", ".env")`: pydantic-settings
carga ambos si existen y **el último prevalece**, así que `backend/.env` (opcional, para ajustes
locales) se impone a la raíz, y las variables de entorno del proceso se imponen a los dos.

```python
# adapters/inbound/http/app.py
def create_app(settings: Settings) -> FastAPI: ...
# GET /api/v1/health -> {"status": "ok", "version": avisabus.__version__}
```

Formato de error (RFC 9457) en `adapters/inbound/http/errors.py`:

```json
{"type": "about:blank", "title": "Internal Server Error", "status": 500}
```

CLI: `[project.scripts] avisabus = "avisabus.adapters.inbound.cli.main:app"`.

## 4. Configuración de herramientas

**`pyproject.toml`** (extracto de lo obligatorio):

```toml
[project]
requires-python = ">=3.12"
dependencies = ["fastapi", "uvicorn[standard]", "pydantic>=2", "pydantic-settings",
                "typer", "structlog", "httpx"]
[dependency-groups]
dev = ["pytest", "pytest-asyncio", "pytest-cov", "pytest-socket", "ruff", "mypy",
       "import-linter"]

[tool.pytest.ini_options]
addopts = "--disable-socket --allow-unix-socket --cov=avisabus.domain --cov=avisabus.application --cov-fail-under=80 -m 'not slow'"
asyncio_mode = "auto"
markers = ["spec(id): acceptance criterion verified by the test", "slow: excluded by default"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "N", "S", "ASYNC"]
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]

[tool.mypy]
packages = ["avisabus"]
strict = false
[[tool.mypy.overrides]]
module = ["avisabus.domain.*", "avisabus.application.*"]
strict = true
```

Mientras `domain` y `application` estén vacíos, la cobertura se mide igualmente; si
`--cov-fail-under` falla por "no data", se añade un test mínimo que importe `avisabus.domain.errors`
(decisión local permitida: cómo garantizar que la medición tenga datos).

**`.importlinter`**:

```ini
[importlinter]
root_package = avisabus
include_external_packages = True

[importlinter:contract:layers]
name = Hexagonal layers
type = layers
layers =
    avisabus.main
    avisabus.adapters | avisabus.background
    avisabus.application
    avisabus.domain

[importlinter:contract:domain-pure]
name = Domain has no external dependencies
type = forbidden
source_modules = avisabus.domain
forbidden_modules = fastapi
    pydantic
    pydantic_settings
    sqlalchemy
    httpx
    typer
    structlog
    avisabus.config
```

`include_external_packages = True` es obligatorio: sin él import-linter no puede evaluar un
contrato `forbidden` que incluye librerías externas (v1.1, hallazgo H-02).

`avisabus.config` y `avisabus.logging` quedan fuera de las capas (los usan adaptadores y `main`).

**Frontend `package.json` scripts:**

| Script | Comando |
|---|---|
| `dev` | `vite` |
| `build` | `tsc -b && vite build` |
| `typecheck` | `tsc -b --noEmit` |
| `lint` | `eslint .` |
| `format` / `format:check` | `prettier --write .` / `prettier --check .` |
| `test` | `vitest run` |
| `e2e` | `playwright test` |

Dependencias: `react`, `react-dom`, `react-router-dom`; dev: `vite`, `@vitejs/plugin-react`,
`vite-plugin-pwa`, `typescript`, `eslint`, `typescript-eslint`, `eslint-plugin-jsx-a11y`,
`eslint-plugin-react-hooks`, `prettier`, `vitest`, `jsdom`, `@testing-library/react`,
`@testing-library/jest-dom`, `@playwright/test`, `@axe-core/playwright`, `tailwindcss`.

**Playwright** (`playwright.config.ts`): `webServer` = `npm run build && npm run preview`;
proyectos `devices['iPhone 14']`, `devices['Pixel 7']`, `devices['iPad (gen 7) landscape']`.
El test de humo usa `new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa'])`.

**Vite**: `server.proxy = { '/api': 'http://localhost:8000', '/ws': { target: 'ws://localhost:8000', ws: true } }`.

## 5. Logging

`configure_logging(level)` configura `structlog` con `TimeStamper(fmt="iso", utc=True)`,
`add_log_level`, `add_logger_name` y `JSONRenderer`, y redirige `logging` estándar (uvicorn)
al mismo formato.

## 6. Ficheros de repositorio

- `.gitignore` (raíz): `data/`, `.env`, `**/node_modules/`, `**/dist/`, `**/.venv/`,
  `**/__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `coverage/`,
  `playwright-report/`, `test-results/`, `*.sqlite`, `*.sqlite-*`.
- `.env.example` (raíz): todas las variables de `Settings` con comentario.
- `tests/fixtures/*/README.md`: propósito, origen de los datos, comando de regeneración
  (los comandos los añaden las features `gtfs_import` y `sae_arrivals_source`).

## 7. Estrategia de test

| AC | Test |
|---|---|
| AC-03, AC-04 | `tests/unit/test_architecture_contracts.py`: copia el paquete a `tmp_path`, añade un módulo con importación prohibida y ejecuta `lint-imports --config` sobre él; espera código ≠ 0. Un segundo caso sin la importación espera 0. |
| AC-05 | `tests/unit/test_no_network.py`: `pytest.raises(SocketBlockedError)` al abrir un socket. |
| AC-07, AC-08 | `tests/unit/test_clock.py` |
| AC-09 | `tests/unit/test_settings.py` con `monkeypatch.setenv` |
| AC-10, AC-11 | `tests/integration/test_health.py` con `httpx.AsyncClient(transport=ASGITransport(app))`; para AC-11 se monta una ruta de prueba que lanza excepción |
| AC-12 | `tests/unit/test_logging.py` con `capsys` |
| AC-13 | `tests/integration/test_cli.py` con `typer.testing.CliRunner` |
| AC-15 | `frontend/src/__tests__/eslint-a11y.test.ts`: `new ESLint().lintFiles(['tests/lint/img-without-alt.tsx'])` espera error de `jsx-a11y/alt-text` |
| AC-16 | `frontend/src/app/App.test.tsx` |
| AC-17 | `frontend/e2e/smoke.spec.ts` |
| AC-18 | `frontend/src/__tests__/pwa-manifest.test.ts` (lee la configuración del plugin PWA exportada desde `vite.config.ts`) |

El fichero `tests/lint/` se excluye del lint normal (`ignores` en `eslint.config.js`).

## 8. Decisiones locales permitidas

- Versiones exactas de dependencias (las últimas estables compatibles).
- Estructura interna de `conftest.py` y nombres de fixtures.
- Iconos PWA provisionales (generados, sin marcas de terceros).

## 9. Preguntas abiertas

Ninguna.
