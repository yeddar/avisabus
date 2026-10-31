# Convenciones — AvisaBus

> Estado: **APROBADO** (v1.0 · 2026-10-31). Obligatorio para personas y agentes.
> Si una convención entra en conflicto con una spec, manda la spec y se anota en `progress/`.

## 1. Idiomas

| Ámbito | Idioma |
|---|---|
| Código (identificadores, módulos, comentarios, docstrings) | Inglés |
| Mensajes de commit, nombres de rama | Inglés |
| Documentación (`docs/`), specs (`specs/`), progreso (`progress/`) | Castellano |
| Textos de interfaz | Ficheros de traducción `es` y `ca-valencia`; nunca literales en componentes |
| Nombres de paradas y líneas | Tal como vienen en el GTFS (valenciano), sin traducir |

## 2. Glosario (castellano → código)

| Castellano | Código | Nota |
|---|---|---|
| Aviso (de espera) | `Alert` | |
| Necesidad de accesibilidad | `Need` | `RAMP`, `EXTRA_TIME`, `SEAT` |
| Parada | `Stop` | `stop_id` del GTFS = código del SAE |
| Línea | `Line` | Agrupa `route_id` por `route_short_name` |
| Sentido | `Direction` / `direction_id` | |
| Destino (texto del SAE) | `destination` | |
| Llegada / tiempo de llegada | `Arrival` / `eta` | |
| Horario programado | `SCHEDULED` | Origen GTFS |
| Tiempo real | `REALTIME` | Origen SAE |
| Posición estimada | `EstimatedPosition` | |
| Ocupación / nivel | `Occupancy` / `OccupancyLevel` | `FREE`, `MEDIUM`, `FULL` |
| Paso del autobús por la parada | `passage` | |
| Caducidad | `expiry` | Motivos: `PASSED`, `NEXT_STOP`, `TIMEOUT` |
| Conductor / turno | `Driver` / `DriverSession` | |
| Código de conductor | `DriverCode` | |
| Próximas paradas | `upcoming_stops` | |
| Alerta de capacidad | `CapacityAlert` | |
| Identificador de dispositivo | `device_id` (cliente) / `device_hash` (servidor) | |

## 3. Backend (Python)

- **Versión y herramientas:** Python 3.12, `uv` para dependencias y ejecución.
- **Estilo:** `ruff format` + `ruff check` (reglas: E, F, I, B, UP, SIM, N, S, ASYNC). Líneas de 100.
- **Tipado:** `mypy --strict` en `domain/` y `application/`; tipado completo en el resto.
- **Dominio:**
  - Entidades y value objects como `@dataclass(frozen=True, slots=True)`.
  - Puertos como `typing.Protocol`.
  - Prohibido importar FastAPI, Pydantic, SQLAlchemy, httpx o `datetime.now()` en `domain/`.
- **Aplicación:** un módulo por caso de uso (`create_alert.py`), una clase con método `execute(command) -> result`. Los comandos y resultados son dataclasses.
- **Adaptadores inbound:** Pydantic solo aquí (esquemas de API). Mapeo explícito esquema ↔ comando.
- **Errores:** excepciones de dominio en `domain/errors.py`; los routers las traducen a `problem+json`. Nunca devolver trazas al cliente.
- **Tiempo:** siempre a través del puerto `Clock`; `datetime` con zona UTC. Conversión a `Europe/Madrid` solo para interpretar horarios GTFS.
- **Async:** adaptadores y casos de uso que hacen I/O son `async`; los servicios de dominio son funciones puras síncronas.
- **Configuración:** `pydantic-settings`, prefijo `AVISABUS_`, todos los valores con default seguro y documentados en `.env.example`.
- **Logs:** `structlog` en JSON. Nunca registrar `device_id`, código de conductor ni necesidades de accesibilidad asociadas a un identificador.
- **Excepciones en logs:** ninguna excepción no controlada puede llegar a los logs con su
  **mensaje**: se registra solo su tipo (y, como mucho, la traza sin el mensaje). Las excepciones
  de dominio no incluyen identificadores en su mensaje (usan atributos). Starlette relanza las
  excepciones tras responder 500 y uvicorn las registra completas, así que debe existir un
  mecanismo explícito (middleware o filtro de logs) que lo impida. Se especifica en la primera
  feature que maneja identificadores (bloque 3) — hallazgo H-01 de `project_scaffold`.
- **Nombres:** módulos `snake_case`, clases `PascalCase`, constantes `UPPER_SNAKE`. Adaptadores con sufijo del puerto (`SqliteAlertRepository`, `SaeHttpArrivalsSource`).

## 4. Frontend (TypeScript / React)

- **Herramientas:** Node 22 LTS, `npm`, Vite, TypeScript `strict`.
- **Estilo:** ESLint (`typescript-eslint`, `react-hooks`, `jsx-a11y`, `i18next/no-literal-string`) + Prettier.
- **Componentes:** funcionales, exportaciones con nombre (sin `export default`), un componente por fichero `PascalCase.tsx`.
- **Organización:** por feature (`features/passenger/stop/…`). Lo compartido va en `shared/`.
- **Datos:** TanStack Query para REST; los tipos de API se generan con `openapi-typescript` (`npm run gen:api`) y no se editan a mano.
- **i18n:** claves jerárquicas `area.view.element` (p. ej. `passenger.stop.arrivals.title`). Toda clave nueva se añade a **ambos** idiomas en el mismo commit.
- **Accesibilidad (obligatorio):**
  - HTML semántico; un `h1` por vista; landmarks.
  - Todo control interactivo con nombre accesible.
  - Actualizaciones de ETA anunciadas con `aria-live="polite"`; confirmaciones y alertas de capacidad con `role="status"` / `role="alert"`.
  - Ningún dato transmitido solo por color (ocupación y alertas llevan texto + icono).
  - Objetivos táctiles ≥ 44×44 px; contraste AA; foco visible.
  - Animaciones desactivadas con `prefers-reduced-motion`.
- **Estado local del dispositivo:** solo `device_id`, idioma y perfil de accesibilidad, en `localStorage`, encapsulado en `shared/device`.

## 5. API

- Prefijo `/api/v1`, JSON `snake_case`, errores RFC 9457.
- Recursos en plural; verbos HTTP estándar; `201` al crear, `200` si el aviso ya existía (idempotente), `429` por rate limit.
- Todo cambio de contrato se refleja en el `design.md` de la feature antes de implementarse.

## 6. Tests

- **Sin red y sin reloj real.** SAE vía `SaeReplayArrivalsSource` y `tests/fixtures/sae_recordings/`; GTFS vía `tests/fixtures/gtfs_mini/`; tiempo vía `FakeClock`.
- **Backend:** `pytest`, `pytest-asyncio`. Carpetas `unit/` (dominio y aplicación con fakes) e `integration/` (adaptadores, API con `httpx.AsyncClient`). Cobertura de `domain/` + `application/` ≥ 80 %.
- **Frontend:** Vitest + Testing Library (unitarios); Playwright + `@axe-core/playwright` (E2E y accesibilidad, perfiles iPhone, Pixel y tablet horizontal).
- **Trazabilidad:** cada criterio de aceptación de una spec tiene ID `<feature_id>.AC-<n>` (p. ej. `alert_create.AC-03`). Cada test que lo verifica lo cita:
  - Python: `@pytest.mark.spec("alert_create.AC-03")`
  - TypeScript: en el nombre del test, `it("[alert_create.AC-03] rejects a second alert…")`
- Nombres de test que describen comportamiento: `test_rejects_alert_with_invalid_stop_token`.

## 7. Git

- Rama por feature: `feat/<feature_id>`.
- Conventional Commits con la feature como ámbito: `feat(alert_create): reject duplicate alerts per device`.
- Un commit por tarea de `tasks.md` cuando sea razonable; el mensaje cita la tarea (`T-03`).
- No se hace merge sin pasar la verificación de `docs/verification.md`.

## 8. Comandos canónicos

| Acción | Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|---|
| Instalar | `uv sync` | `npm ci` |
| Formatear | `uv run ruff format .` | `npm run format` |
| Lint | `uv run ruff check .` | `npm run lint` |
| Tipos | `uv run mypy` | `npm run typecheck` |
| Arquitectura | `uv run lint-imports` | — |
| Tests | `uv run pytest` | `npm run test` |
| E2E + a11y | — | `npm run e2e` |
| Todo | `./init.sh verify` (raíz) | |
