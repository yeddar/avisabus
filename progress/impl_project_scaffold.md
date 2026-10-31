# Implementación: project_scaffold
Spec: specs/project_scaffold/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Rama: `feat/project_scaffold`

## Tareas
- [x] T-01 Ficheros de raíz: `.gitignore`, `.env.example`, READMEs de fixtures (commit 0e55b3d)
- [x] T-02 Paquete backend, ruff, mypy, pytest con cobertura, sockets y marcador `spec` (commit 72bcd3c)
- [x] T-03 Contratos de import-linter y test que los rompe (commit 495ccbf)
- [x] T-04 `Clock`, `SystemClock`, `FakeClock` + fixture `fake_clock` (commit 88cd97d)
- [x] T-05 `Settings` con prefijo `AVISABUS_` y `.env.example` completo (commit 8ddbac1)
- [x] T-06 Logging JSON con structlog (structlog + logging estándar/uvicorn) (commit 8dbb04d)
- [x] T-07 App FastAPI, `GET /api/v1/health`, manejador problem+json y `main.py` (commit 880ed4e)
- [x] T-08 CLI Typer `avisabus` y script de proyecto (commit e0c4ae2)
- [x] T-09 Frontend Vite + React + TS estricto, Tailwind, router, ESLint (jsx-a11y,
      react-hooks), Prettier, Vitest + Testing Library, proxy de desarrollo (commit 503f0d9)
- [x] T-10 PWA: manifiesto, iconos y service worker (commit 21bd377)
- [x] T-11 Playwright (iPhone 14, Pixel 7, iPad gen 7 landscape) + axe WCAG 2.1 A/AA (commit ed9519c)
- [x] T-12 `./init.sh verify --e2e` en verde (ver "Verificación")

### Matriz AC → test
| AC | Evidencia |
|---|---|
| AC-01, AC-02 | gate `./init.sh verify` (uv sync, ruff format/check, mypy, pytest) |
| AC-03 | `backend/tests/unit/test_architecture_contracts.py` (domain → application/adapters/background/config y 7 librerías externas) |
| AC-04 | `backend/tests/unit/test_architecture_contracts.py::test_application_cannot_import_adapters` |
| AC-05 | `backend/tests/unit/test_no_network.py` |
| AC-06 | `--cov-fail-under=80` en `pyproject.toml` + `backend/tests/unit/test_domain_errors.py` |
| AC-07, AC-08 | `backend/tests/unit/test_clock.py` |
| AC-09 | `backend/tests/unit/test_settings.py` (incluye comprobación de que `.env.example` documenta todos los campos) |
| AC-10, AC-11 | `backend/tests/integration/test_health.py` |
| AC-12 | `backend/tests/unit/test_logging.py` |
| AC-13 | `backend/tests/integration/test_cli.py` |
| AC-14 | gate `./init.sh verify` (`npm ci` probado manualmente) |
| AC-15 | `frontend/src/__tests__/eslint-a11y.test.ts` + fixture `frontend/tests/lint/img-without-alt.tsx` |
| AC-16 | `frontend/src/app/App.test.tsx` |
| AC-17 | `frontend/e2e/smoke.spec.ts` |
| AC-18 | `frontend/src/__tests__/pwa-manifest.test.ts` |
| AC-19 | revisión: `frontend/vite.config.ts` (`server.proxy`) |
| AC-20 | revisión: `.gitignore` |
| AC-21 | revisión: `backend/tests/fixtures/{gtfs_mini,sae_recordings}/README.md` |
| AC-22 | `./init.sh verify --e2e` (código 0) |

Comprobaciones de no-tautología hechas a mano (y revertidas): el test de AC-05 falla sin
`--disable-socket`; AC-16 falla si `HomePage` usa `<div>` en lugar de `<main>`; AC-15 falla si se
quita `jsxA11y.flatConfigs.recommended`; AC-17 detecta `color-contrast` con `text-gray-300`.

## Decisiones locales
- **Cobertura con capas vacías** (permitida, design §4): `tests/unit/test_domain_errors.py` importa
  `avisabus.domain.errors` para que `--cov-fail-under=80` tenga datos.
- **Versiones** (permitida, design §8): Python 3.12 (`backend/.python-version`), hatchling como
  build backend, FastAPI 0.162, Vite 8, React 19.3, react-router-dom 7, Vitest 5, Playwright 1.64,
  Tailwind 4.3. **ESLint 9.39** (no 10: `eslint-plugin-jsx-a11y` 6.10 solo admite hasta ESLint 9)
  y **TypeScript 6.0** (no 7: `typescript-eslint` exige `<6.1`).
- **Iconos PWA provisionales** (permitida, design §8): generados por script (autobús blanco
  sobre azul `#0b3d91`), `icon-192`, `icon-512`, `maskable-512` y `apple-touch-icon-180`.
- **Fixtures de `conftest.py`** (permitida, design §8): `fake_clock`, `settings` (sin `.env`,
  `env="test"`) y `api_client` (`httpx.AsyncClient` + `ASGITransport(raise_app_exceptions=False)`).
- Detalles de implementación dentro del diseño, sin cambiar contratos:
  - `mypy_path = "src"` en `[tool.mypy]`: sin él mypy no encuentra el paquete (layout `src/`).
  - `main.py` se creó en T-03 como módulo vacío para que existiera la capa `avisabus.main` del
    contrato `layers`; en T-07 se completó (`configure_logging(settings.log_level)` + `create_app`).
  - `FakeClock` normaliza a UTC los `datetime` con zona distinta (el puerto exige UTC).
  - Manejador de 500: registra `unhandled_exception` solo con el tipo de excepción y el método
    (sin ruta ni mensaje, que podrían contener identificadores).
  - Tailwind 4 requiere `@tailwindcss/vite` (dependencia de desarrollo añadida a la lista del
    design). Para los tipos de Node en tests se añadió `@types/node` y `globals` para ESLint.
  - TS dividido en `tsconfig.app.json` (código), `tsconfig.test.json` (tests de `src/`, con tipos
    de Node) y `tsconfig.node.json` (`vite.config.ts`, `playwright.config.ts`, `e2e/`).
  - Rutas en `src/app/routes.tsx` (exportadas) para que el test de AC-16 use
    `createMemoryRouter`; `App.tsx` usa `createBrowserRouter`.
  - PWA: `registerType: 'autoUpdate'`, `injectRegister: 'auto'` y
    `workbox.navigateFallbackDenylist` para `/api/` y `/ws` (el SW nunca sirve la API).
  - Playwright: `webServer` = `npm run build && npm run preview -- --port 4173 --strictPort`.
  - `frontend/.nvmrc` = 22 y `engines.node >= 22` (convenciones: Node 22 LTS).

## Desviaciones respecto al design (para que el reviewer y la persona las validen)
- **`include_external_packages = True` en `backend/.importlinter`.** El extracto del design
  §4 no lo incluye, pero import-linter se niega a ejecutar el contrato `domain-pure` sin él
  ("The top level configuration must have include_external_packages=True when there are
  external forbidden modules"). Es la única forma de que el contrato prohíba librerías externas,
  como exige AC-03. No cambia la semántica de los contratos. **Propuesta:** añadir la línea al
  extracto de `specs/project_scaffold/design.md` §4.

## Bloqueos
Ninguno.

### Observaciones no bloqueantes (propuestas para spec/docs)
- **Ubicación de `.env`:** `Settings` usa `env_file=".env"`, relativo al directorio de trabajo.
  `./init.sh setup` copia `.env.example` a la raíz (`.env`), pero el backend se ejecuta desde
  `backend/` (`./init.sh dev`, `uv run …`), así que ese `.env` de la raíz **no se lee**. Las
  variables de entorno sí funcionan. Propuesta: que `deployment_rpi`/una futura revisión de la
  spec decida si `env_file` apunta a `("../.env", ".env")` o si `.env` vive en `backend/`.
- **Entorno local:** Node v26 instalado (convenciones: Node 22 LTS). Todo pasa con 26; `.nvmrc`
  fija 22 para quien use nvm.
- `npm audit`: 12 avisos moderados de `minimatch` en dependencias de desarrollo del lint
  (`eslint-plugin-jsx-a11y`, `typescript-eslint`); sin impacto en el bundle de producción.
- El manifiesto PWA (`name`, `description`) está en castellano y fuera de los ficheros de
  traducción; la i18n queda para `frontend_i18n`.

## Verificación
`./init.sh verify --e2e` (2026-10-31) → código de salida 0:

```
OK   backend: format
OK   backend: lint
OK   backend: types
OK   backend: architecture        Contracts: 2 kept, 0 broken.
OK   backend: tests               39 passed; cobertura domain+application 100 % (≥ 80 %)
OK   frontend: format
OK   frontend: lint
OK   frontend: types
OK   frontend: tests              3 ficheros, 7 tests
OK   frontend: build              PWA v2.0.0 generateSW (sw.js, manifest.webmanifest)
OK   frontend: e2e + a11y         3 passed (iphone, pixel, tablet-landscape)
OK   harness: feature_list.json
OK   harness: trazabilidad AC→test
OK   verify: todo en verde
```
