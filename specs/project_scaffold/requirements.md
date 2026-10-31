# Esqueleto del proyecto — requirements

> Feature: `project_scaffold` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RNF-09, RNF-10, RNF-11, RNF-13 · Casos de uso: — · Depende de: —

## Contexto

Todas las features se apoyan en una base común: estructura de carpetas, herramientas de calidad
que ejecutan los agentes (`./init.sh verify`), la regla de dependencias de la arquitectura
hexagonal, el reloj inyectable, la configuración y los logs. Esta feature crea esa base sin
ninguna funcionalidad de negocio.

## Alcance

- Paquete backend `avisabus` (Python 3.12, uv) con las capas de `docs/architecture.md` §4 vacías.
- Herramientas backend: ruff, mypy, pytest (+ cobertura, + bloqueo de sockets), import-linter.
- Primitivas comunes: puerto `Clock` con `SystemClock` y `FakeClock`; configuración
  (`Settings`); logs JSON; aplicación FastAPI con endpoint de salud; punto de entrada de CLI.
- Proyecto frontend (React + TS + Vite + PWA) con lint, tipos, tests unitarios, build y E2E con
  axe.
- `.gitignore`, `.env.example`, carpetas de fixtures documentadas.

## Fuera de alcance

- i18n y selector de idioma (feature `frontend_i18n`).
- Base de datos y modelos (feature `gtfs_import`).
- Docker y despliegue (feature `deployment_rpi`).

## Criterios de aceptación

### Backend

- **project_scaffold.AC-01** — CUANDO se ejecuta `uv sync` y después `uv run pytest` en
  `backend/`, EL SISTEMA DEBERÁ instalar las dependencias y pasar los tests sin errores.
  *Verificación:* gate (`./init.sh verify`)
- **project_scaffold.AC-02** — EL SISTEMA DEBERÁ pasar `ruff format --check`, `ruff check` y
  `mypy` (estricto en `domain` y `application`) sin errores.
  *Verificación:* gate (`./init.sh verify`)
- **project_scaffold.AC-03** — SI un módulo de `avisabus.domain` importa algo de
  `avisabus.application`, `avisabus.adapters`, `avisabus.background` o de una librería externa
  no permitida, ENTONCES `uv run lint-imports` DEBERÁ fallar.
  *Verificación:* unit (test que ejecuta import-linter sobre un paquete temporal con una
  importación prohibida y comprueba que falla)
- **project_scaffold.AC-04** — SI un módulo de `avisabus.application` importa
  `avisabus.adapters`, ENTONCES `uv run lint-imports` DEBERÁ fallar.
  *Verificación:* unit (mismo mecanismo que AC-03)
- **project_scaffold.AC-05** — CUANDO un test intenta abrir una conexión de red, EL SISTEMA
  DEBERÁ hacer fallar ese test.
  *Verificación:* unit (test que espera la excepción del bloqueo de sockets)
- **project_scaffold.AC-06** — EL SISTEMA DEBERÁ exigir una cobertura mínima del 80 % sobre
  `avisabus.domain` y `avisabus.application` al ejecutar `uv run pytest`.
  *Verificación:* revisión (configuración `--cov-fail-under=80`) + gate
- **project_scaffold.AC-07** — EL SISTEMA DEBERÁ proporcionar un puerto `Clock` con
  `now() -> datetime` (UTC y con zona), una implementación `SystemClock` y una `FakeClock` que
  permite fijar y avanzar el tiempo.
  *Verificación:* unit
- **project_scaffold.AC-08** — SI se construye un `datetime` sin zona horaria para `FakeClock`,
  ENTONCES EL SISTEMA DEBERÁ lanzar `ValueError`.
  *Verificación:* unit
- **project_scaffold.AC-09** — EL SISTEMA DEBERÁ cargar la configuración desde variables de
  entorno con prefijo `AVISABUS_` (y fichero `.env` opcional), con valores por defecto seguros
  para desarrollo, y `.env.example` DEBERÁ documentar todas las variables.
  *Verificación:* unit (variables sobrescritas en el test) + revisión (`.env.example`)
- **project_scaffold.AC-10** — CUANDO se hace `GET /api/v1/health`, LA API DEBERÁ responder
  `200` con `{"status": "ok", "version": "<versión del paquete>"}`.
  *Verificación:* integration (cliente HTTP en proceso)
- **project_scaffold.AC-11** — SI una ruta lanza una excepción no controlada, ENTONCES LA API
  DEBERÁ responder `500` con cuerpo `application/problem+json` sin traza ni detalles internos.
  *Verificación:* integration
- **project_scaffold.AC-12** — EL SISTEMA DEBERÁ emitir los logs en JSON (una línea por evento)
  con al menos `timestamp`, `level`, `event` y `logger`.
  *Verificación:* unit (captura de salida)
- **project_scaffold.AC-13** — CUANDO se ejecuta `uv run avisabus --help`, LA CLI DEBERÁ
  mostrar la ayuda y terminar con código 0.
  *Verificación:* integration (CliRunner)

### Frontend

- **project_scaffold.AC-14** — CUANDO se ejecutan `npm ci`, `npm run lint`,
  `npm run typecheck`, `npm run test`, `npm run format:check` y `npm run build` en `frontend/`,
  EL SISTEMA DEBERÁ terminar todos sin errores.
  *Verificación:* gate (`./init.sh verify`)
- **project_scaffold.AC-15** — EL SISTEMA DEBERÁ incluir ESLint con `jsx-a11y` (reglas
  recomendadas) y `react-hooks`; SI un componente tiene una imagen sin `alt`, ENTONCES
  `npm run lint` DEBERÁ fallar.
  *Verificación:* unit (test que ejecuta ESLint sobre un fichero de ejemplo inválido)
- **project_scaffold.AC-16** — CUANDO se abre la ruta `/`, LA APLICACIÓN DEBERÁ renderizar una
  página con un único `h1` y landmark `main`.
  *Verificación:* unit (Testing Library)
- **project_scaffold.AC-17** — CUANDO se ejecuta `npm run e2e`, EL SISTEMA DEBERÁ abrir la ruta
  `/` en los perfiles iPhone, Pixel y tablet horizontal y comprobar que axe no reporta
  violaciones WCAG 2.1 A/AA.
  *Verificación:* e2e
- **project_scaffold.AC-18** — EL SISTEMA DEBERÁ generar un build PWA con manifiesto
  (`name`, `short_name`, `lang`, `start_url`, `display: standalone`, iconos) y service worker.
  *Verificación:* unit (test que inspecciona la configuración del manifiesto PWA)
- **project_scaffold.AC-19** — MIENTRAS se ejecuta `npm run dev`, EL SISTEMA DEBERÁ redirigir
  `/api` y `/ws` al backend local (`http://localhost:8000`).
  *Verificación:* revisión (`vite.config.ts`)

### Repositorio

- **project_scaffold.AC-20** — EL SISTEMA DEBERÁ ignorar en git `data/`, `.env`,
  `node_modules/`, `dist/`, `.venv/`, cachés y ficheros de base de datos `*.sqlite*`.
  *Verificación:* revisión (`.gitignore`)
- **project_scaffold.AC-21** — EL SISTEMA DEBERÁ incluir `backend/tests/fixtures/gtfs_mini/` y
  `backend/tests/fixtures/sae_recordings/` con un `README.md` que explique su origen y cómo
  regenerarlas.
  *Verificación:* revisión
- **project_scaffold.AC-22** — CUANDO se ejecuta `./init.sh verify` en el repositorio con esta
  feature completa, EL SISTEMA DEBERÁ ejecutar todas las comprobaciones de backend, frontend y
  harness y terminar con código 0.
  *Verificación:* gate (`./init.sh verify --e2e`)

## Trazabilidad

| Requisito | AC |
|---|---|
| RNF-09 Mantenibilidad (hexagonal) | AC-03, AC-04, AC-07 |
| RNF-10 Testabilidad | AC-05, AC-06, AC-07, AC-08, AC-21 |
| RNF-11 Despliegue / entorno | AC-01, AC-09, AC-13, AC-14, AC-19, AC-20, AC-22 |
| RNF-13 Observabilidad | AC-11, AC-12 |
| RNF-03 / RNF-05 (base) | AC-15, AC-16, AC-17, AC-18 |
