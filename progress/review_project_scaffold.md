# Revisión: project_scaffold
Ciclo: 1 · Fecha: 2026-10-31 · Agente: reviewer · Rama: `feat/project_scaffold` (12 commits sobre `develop`)

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Los 22 AC tienen evidencia válida. Hay 3 observaciones de spec y
5 mejoras, ninguna bloqueante (ver "Hallazgos").

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | gate `./init.sh verify` (`uv run pytest`: 39 passed) | OK | `uv lock --check` sin cambios: el lock es coherente con `pyproject.toml`. |
| AC-02 | gate (`ruff format --check`, `ruff check`, `mypy`) | OK | `pyproject.toml`: override `strict = true` para `avisabus.domain.*` y `avisabus.application.*`, igual que el design §4. |
| AC-03 | `backend/tests/unit/test_architecture_contracts.py::test_domain_cannot_import_outer_layers_or_external_libraries` (11 casos) + `test_contracts_pass_without_forbidden_imports` | OK | Lo reproduje a mano en copias temporales: `sqlalchemy` y `structlog` → "Domain has no external dependencies BROKEN"; `avisabus.background` → "Hexagonal layers BROKEN"; `import os` → ambos KEPT. El fallo es real, no un error de ejecución. |
| AC-04 | `test_application_cannot_import_adapters` + caso positivo | OK | Reproducido: "Hexagonal layers BROKEN – avisabus.application.offender -> avisabus.adapters". |
| AC-05 | `backend/tests/unit/test_no_network.py` (IPv4 e IPv6) | OK | Espera `SocketBlockedError`; `addopts` incluye `--disable-socket --allow-unix-socket`. |
| AC-06 | `pyproject.toml` `--cov=avisabus.domain --cov=avisabus.application --cov-fail-under=80` + `tests/unit/test_domain_errors.py` | OK | Gate: "Required test coverage of 80% reached. Total coverage: 100.00%". El test mínimo es la decisión local que permite el design §4. |
| AC-07 | `backend/tests/unit/test_clock.py` (5 tests) | OK | Comprueban que `SystemClock` devuelve UTC con zona y que `FakeClock` fija, avanza (`advance`), cambia (`set`) y normaliza a UTC. |
| AC-08 | `test_fake_clock_rejects_naive_start`, `test_fake_clock_rejects_naive_set` | OK | Esperan `ValueError` y que el estado no cambie tras un `set` rechazado. |
| AC-09 | `backend/tests/unit/test_settings.py` (7 tests) | OK | Cubren valores por defecto, prefijo, que se ignoran las variables sin prefijo, `.env` opcional, que el entorno manda sobre `.env`, que se rechaza un `env` inválido y que `.env.example` documenta exactamente los campos de `Settings`. |
| AC-10 | `backend/tests/integration/test_health.py::test_health_returns_ok_and_package_version` | OK | Usa `ASGITransport` en proceso. Comprueba el cuerpo exacto y que `__version__` coincide con la metadata del paquete. |
| AC-11 | `test_unhandled_exception_becomes_problem_json_without_internals` | OK | Comprueba 500, el `content-type` `application/problem+json`, el cuerpo exacto del design y que la respuesta no incluye el mensaje, la traza ni el tipo de la excepción. Ver H-01 sobre los logs. |
| AC-12 | `backend/tests/unit/test_logging.py` (5 tests) | OK | Una línea JSON por evento con `timestamp`/`level`/`event`/`logger`, en structlog y en stdlib (`uvicorn.error`). También cubren el filtro por nivel y las excepciones. |
| AC-13 | `backend/tests/integration/test_cli.py` (2 tests) | OK | Usa `CliRunner` y la entry point `console_scripts`. También lo ejecuté a mano: `uv run avisabus --help` termina con código 0. |
| AC-14 | gate (`format:check`, `lint`, `typecheck`, `test`, `build`) | OK | No ejecuté `npm ci` para no reinstalar `node_modules`. `npm ls --depth=0` no muestra incoherencias con `package-lock.json`. |
| AC-15 | `frontend/src/__tests__/eslint-a11y.test.ts` (3 tests) + `frontend/tests/lint/img-without-alt.tsx` | OK | Espera exactamente un error `jsx-a11y/alt-text` de severidad 2. También tiene un caso positivo y comprueba que están activas las reglas `react-hooks/*`. La fixture está excluida del lint normal (`eslint.config.js:11`). |
| AC-16 | `frontend/src/app/App.test.tsx` | OK | Hay un único `h1` y un único `main`, y el `h1` está dentro del `main`. Ver H-07. |
| AC-17 | `frontend/e2e/smoke.spec.ts` | OK | `./init.sh verify --e2e`: 3 passed (iphone, pixel, tablet-landscape). Los perfiles y tags coinciden con el design §4. |
| AC-18 | `frontend/src/__tests__/pwa-manifest.test.ts` (3 tests) | OK | Comprueba los campos del manifiesto, que los iconos existen en disco (192, 512 y maskable) y que el plugin PWA está montado. El build genera `dist/sw.js` y `manifest.webmanifest`. Con `file` comprobé que los PNG tienen las dimensiones declaradas. |
| AC-19 | revisión de `frontend/vite.config.ts:39-44` | OK | `'/api'` → `http://localhost:8000`, `'/ws'` → `ws://localhost:8000` con `ws: true`, igual que el design. |
| AC-20 | revisión de `.gitignore` + `git check-ignore -v` | OK | `data/`, `.env`, `node_modules/`, `dist/`, `.venv/`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `*.sqlite` y `*.sqlite-*` quedan ignorados. |
| AC-21 | revisión de `backend/tests/fixtures/{gtfs_mini,sae_recordings}/README.md` | OK | Cada README explica el propósito y el origen y remite el comando de regeneración a la feature responsable, como pide el design §6. |
| AC-22 | `./init.sh verify --e2e` | OK | Código 0, "verify: todo en verde". |

## Verificación ejecutada

- `./init.sh verify --e2e` → **todo en verde**:
  - Backend: format, lint, types (24 ficheros), architecture ("Contracts: 2 kept, 0 broken"), tests (39 passed, cobertura 100 %).
  - Frontend: format, lint, types, tests (3 ficheros / 7 tests), build (PWA generateSW), e2e (3 passed).
  - Harness: `feature_list.json` y trazabilidad AC→test.
- `./init.sh verify` → código de salida 0.
- `uv lock --check` → OK. `uv run avisabus --help` → código 0.
- `npm ls --depth=0` → sin incoherencias.
- `lint-imports` sobre copias temporales con importaciones prohibidas: ver las filas AC-03 y AC-04.
- `git check-ignore -v` sobre rutas representativas → todas ignoradas.
- `grep` de `datetime.now|time.time(|time.sleep|utcnow|device_id` en `src` y tests: el único `datetime.now` está en `SystemClock`, no hay sleeps, y `device_id` solo aparece en un comentario y en el mensaje falso del test de AC-11.
- `python3 scripts/check_traceability.py` → código 0.

### Lista de comprobación (`docs/verification.md` §4)

- **Contrato.** Se cumplen los AC. Las interfaces (`Clock`, `SystemClock`, `FakeClock`, `Settings`, `create_app`, el formato de error y la CLI) coinciden con el design §3. La única desviación es H-02.
- **Arquitectura.**
  - `domain/` no tiene dependencias externas ni I/O, y `lint-imports` está en verde.
  - Solo `SystemClock` lee la hora real.
  - `main.py` es el composition root.
- **Tests.**
  - Los sockets están bloqueados y no hay sleeps.
  - Los tests no son tautológicos: tienen casos positivos y negativos, y reproduje a mano AC-03 y AC-04.
  - Las fixtures están documentadas.
  - Matices en H-04 y H-05.
- **Privacidad y seguridad.**
  - El manejador 500 registra solo el tipo de excepción y el método, y los secretos solo llegan por configuración.
  - RNF-06 no aplica (aún no hay datos efímeros).
  - Ver H-01.
- **Frontend.**
  - `index.html` tiene `lang="es"`, la vista tiene un `h1` y un landmark `main`, axe pasa en móvil y tablet y se respeta `prefers-reduced-motion`.
  - Los textos literales están permitidos de forma temporal por el design §2 (nota ¹); i18n queda fuera de alcance (`frontend_i18n`).
  - Hay que validar el foco visible y el objetivo táctil de 44 px, pero la vista no tiene controles interactivos.
- **Convenciones.**
  - Los 12 commits siguen Conventional Commits con ámbito `project_scaffold`, uno por tarea, y citan `T-xx`.
  - Los componentes usan exportaciones con nombre, uno por fichero.
  - El código está en inglés y el progreso en castellano.
- **Alcance.**
  - `git diff develop...HEAD` solo toca `backend/`, `frontend/`, `.gitignore`, `.env.example` y `progress/impl_project_scaffold.md`.
  - El único cambio sin commit es `feature_list.json` (`spec_approved → in_review`), que hizo el orquestador y queda fuera del diff del implementer.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **H-01 — Privacidad: las excepciones no controladas se siguen registrando con su mensaje a través del servidor.**
  - Dónde: `backend/src/avisabus/adapters/inbound/http/errors.py:25-32`.
  - Qué pasa: el manejador de `Exception` se ejecuta dentro del `ServerErrorMiddleware` de Starlette. Ese middleware relanza la excepción después de responder (`starlette/middleware/errors.py:186`, "We always continue to raise the exception"), y uvicorn la registra en `uvicorn.error` con traza y mensaje. Con el formatter de `logging.py` acaba en el JSON (`format_exc_info`). El cuidado de registrar solo `error_type` se anula: si una feature futura lanza una excepción con un `device_id` o un código en el mensaje, ese dato llegaría a los logs.
  - Qué incumple: AC-11 se cumple, porque la respuesta está limpia. El riesgo es para la regla de privacidad de AGENTS.md §6 y `docs/conventions.md` §3 (Logs).
  - Recomendación: que la primera feature que maneje identificadores, o una tarea transversal, lo cubra en su spec. Por ejemplo, con un middleware propio que capture la excepción antes del `ServerErrorMiddleware`, o con un filtro de logs.
- **H-02 — Problema de spec (menor): falta `include_external_packages = True` en el extracto del design.**
  - Dónde: `backend/.importlinter:3` frente a `specs/project_scaffold/design.md` §4.
  - Qué pasa: el implementer añadió esa línea porque import-linter no ejecuta un contrato `forbidden` con módulos externos sin ella. Lo comprobé: con la línea, el contrato detecta `sqlalchemy` y `structlog`. No cambia la semántica de los contratos.
  - Propuesta: incorporar la línea al design §4 (lo decide spec-writer o la persona). No requiere cambios de código.
- **H-03 — Problema de spec (menor): el `.env` de la raíz no se lee.**
  - Dónde: `backend/src/avisabus/config.py:12` (`env_file=".env"`, relativo al directorio de trabajo), `init.sh:44` y `init.sh:89`.
  - Qué pasa: `init.sh:44` copia `.env.example` a `<raíz>/.env`, pero `init.sh:89` arranca el backend desde `backend/`, así que ese fichero no se carga. El código sigue el design al pie de la letra y AC-09 se cumple, porque las variables de entorno y un `.env` en el directorio de trabajo sí funcionan. El implementer ya lo anota en su progreso.
  - Propuesta: que la persona decida, en CP-3 o al especificar `deployment_rpi`, si `env_file` debe ser `("../.env", ".env")` o si el `.env` debe vivir en `backend/`.
- **H-04 — El test de contratos solo mira el código de salida.**
  - Dónde: `backend/tests/unit/test_architecture_contracts.py:40`.
  - Qué pasa: `assert code != 0` también se cumpliría si `lint-imports` fallara por un error de configuración. El caso positivo de la línea 45 lo mitiga, y lo verifiqué a mano.
  - Sugerencia: comprobar además que `stdout` contiene `BROKEN` y el nombre del contrato esperado.
- **H-05 — mypy no revisa los tests.**
  - Dónde: `backend/pyproject.toml` (`[tool.mypy] packages = ["avisabus"]`).
  - Qué pasa: la función `_read(clock: Clock)` de `test_clock.py:12` sugiere una comprobación estática de que `FakeClock` y `SystemClock` cumplen el puerto, pero mypy no la ejecuta. En tiempo de ejecución el test es válido.
  - Sugerencia: añadir `tests` a la configuración de mypy en una feature posterior.
- **H-06 — Aviso de deprecación de pytest-asyncio.**
  - Qué pasa: `asyncio_default_fixture_loop_scope` no está fijado, y pytest-asyncio emite un `PytestDeprecationWarning` en cada ejecución.
  - Sugerencia: fijarlo a `"function"` en `[tool.pytest.ini_options]`.
- **H-07 — AC-16 se prueba sobre `routes` y no sobre `App`.**
  - Dónde: `frontend/src/app/App.test.tsx:7-10`.
  - Qué pasa: el test monta `routes` con `createMemoryRouter`, no `App` (que usa `createBrowserRouter`). Es correcto y la e2e de AC-17 cubre el árbol real con `getByRole('main')` y un único `h1`, así que es solo una observación.
- **H-08 — Entorno: versiones de Node y avisos de `npm audit`.**
  - Node: el local es v26 y la convención es Node 22 LTS. `.nvmrc` y `engines` fijan 22, así que no es un problema del código.
  - `npm audit`: hay 12 avisos moderados en dependencias de desarrollo, según el progreso del implementer. No afectan al bundle de producción.

---

# Revisión: project_scaffold — v1.1
Ciclo: 2 · Fecha: 2026-10-31 · Agente: reviewer · Rama: `feat/project_scaffold-v1.1` (2 commits sobre `develop`: `83d5398` T-13 y `cc22c78` progreso T-13/T-14)

## Veredicto: APPROVED

No hay hallazgos bloqueantes. AC-23 tiene evidencia válida y los tests fallan si se rompe la
prioridad de los ficheros (comprobado con mutaciones). `.importlinter` coincide con el design §4
v1.1. Los AC-01…AC-22 siguen en verde (`./init.sh verify --e2e`, código 0).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-23 | `backend/tests/integration/test_settings_env_file.py`: `test_root_dotenv_is_loaded_when_running_from_backend`, `test_backend_dotenv_takes_precedence_over_root_dotenv`, `test_process_environment_takes_precedence_over_both_dotenv_files`, `test_defaults_apply_when_no_dotenv_file_exists` | OK | Reproduce el escenario del AC: `tmp_path/root/` y `tmp_path/root/backend/`, `chdir` a `backend/`, limpieza de `AVISABUS_*` del entorno. Cubre las tres reglas del AC: se carga la raíz, `backend/.env` prevalece sobre la raíz (y la raíz rellena los campos que `backend/.env` no define) y el entorno prevalece sobre ambos. **Mutaciones** en una copia en el scratchpad: `env_file=".env"` → 2 fallos; `env_file=(".env", "../.env")` (orden invertido) → 1 fallo; `env_file="../.env"` → 1 fallo; código real → 4 passed. Ver H-09 sobre "o la CLI". |
| AC-03 (design §4 v1.1) | `test_architecture_contracts.py` (13 casos, sin cambios) | OK | `backend/.importlinter:3` tiene `include_external_packages = True`, y el resto del fichero coincide línea a línea con el extracto del design §4 v1.1. `lint-imports`: "Contracts: 2 kept, 0 broken". Cierra H-02 del ciclo 1. |
| AC-09 | `backend/tests/unit/test_settings.py` (7 tests, sin cambios) | OK | Siguen pasando con la tupla `env_file`. `.env.example` documenta todas las variables (`test_env_example_documents_every_setting`) y su cabecera explica ahora la ubicación y la prioridad (`.env.example:2-5`). Ver H-10. |
| AC-01, AC-02, AC-04…AC-08, AC-10…AC-21 | Mismos tests que en el ciclo 1, sin cambios | OK | El diff de la v1.1 no toca su código ni sus tests. 43 passed en backend (39 + 4 nuevos), 7 en frontend, 3 en e2e. |
| AC-22 | `./init.sh verify --e2e` | OK | Código 0, "verify: todo en verde". |

## Verificación ejecutada

- `./init.sh verify` → código 0. Backend: format, lint, types (24 ficheros), architecture
  ("2 kept, 0 broken"), tests (43 passed, cobertura de domain+application 100 % ≥ 80 %). Frontend:
  format, lint, types, tests (3 ficheros / 7 tests), build (PWA generateSW). Harness:
  `feature_list.json` y trazabilidad AC→test.
- `./init.sh verify --e2e` → código 0; e2e + a11y: 3 passed (iPhone, Pixel, tablet horizontal).
- `uv lock --check` → OK. `uv run avisabus --help` → código 0.
- Mutaciones de `env_file` sobre una copia de `backend/src` y `backend/tests` en el scratchpad
  (`PYTHONPATH` a la copia, `-o addopts=""`); resultados en la fila AC-23. El repositorio no se
  ha modificado.
- `git diff --stat develop...HEAD` → `.env.example`, `backend/src/avisabus/config.py`,
  `backend/tests/integration/test_settings_env_file.py`, `progress/impl_project_scaffold.md`.
  Único cambio sin commit: `feature_list.json` (`spec_approved → in_review`, del orquestador).
- `grep` de `env_file` en `backend/src` y `backend/tests`: solo `config.py:15` y
  `conftest.py:23` (`_env_file=None` en la fixture `settings`, que aísla los tests de la API del
  `.env` local).

### Lista de comprobación (`docs/verification.md` §4), limitada al cambio de la v1.1

- **Contrato.** `Settings.model_config` coincide con el design §3 v1.1
  (`env_prefix="AVISABUS_", env_file=("../.env", ".env"), extra="ignore"`). Los campos y sus
  valores por defecto no cambian.
- **Arquitectura.** `config.py` sigue fuera de las capas y prohibido para `domain`; no aparece
  ningún `datetime.now`/`time.time` nuevo.
- **Tests.** Sin red ni reloj; solo usan `tmp_path`, `monkeypatch.chdir` y `monkeypatch.delenv/setenv`.
  No son tautológicos (mutaciones).
- **Privacidad y seguridad.** Sin logs nuevos. Los secretos siguen llegando solo por configuración.
- **Frontend.** No aplica (sin cambios).
- **Convenciones.** Los commits son Conventional Commits con ámbito `project_scaffold` y citan
  T-13/T-14. Código y docstrings en inglés; `.env.example` y progreso en castellano, como ya estaba.
- **Alcance.** Solo los ficheros que lista T-13, más el progreso. No hay refactors ajenos.
  `.importlinter` no se ha tocado, como indica T-13.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **H-09 — AC-23 dice "el backend o la CLI", pero se prueba solo sobre `Settings`.**
  - Dónde: `backend/tests/integration/test_settings_env_file.py`;
    `backend/src/avisabus/adapters/inbound/cli/main.py` (la CLI aún no construye `Settings`).
  - Qué pasa: el backend (`main.py:10`) y la futura CLI obtienen la configuración de `Settings()`,
    así que probar `Settings` desde `backend/` cubre el comportamiento. Hoy la CLI no lee
    configuración, de modo que no hay nada más que probar.
  - Sugerencia: cuando una feature añada el primer subcomando que use `Settings` (p. ej.
    `gtfs_import`), que construya `Settings()` en la CLI y no una configuración propia.
- **H-10 — Los tests de AC-09 consultan ahora también `tmp_path/../.env`.**
  - Dónde: `backend/tests/unit/test_settings.py:18` (`monkeypatch.chdir(tmp_path)`).
  - Qué pasa: con la tupla, `Settings()` lee además el `.env` del directorio base de pytest. Nadie
    escribe ahí (los tests de AC-23 escriben en `tmp_path/root/`), así que los resultados son
    correctos, pero el aislamiento depende de una convención implícita. El implementer ya lo anota.
  - Sugerencia: si en el futuro algún test escribe en el directorio base, que los tests de AC-09
    hagan `chdir` a un subdirectorio de `tmp_path`.
- **H-11 — `../.env` depende del directorio de trabajo.**
  - Dónde: `backend/src/avisabus/config.py:15`.
  - Qué pasa: la ruta es relativa al CWD. Desde `backend/` (`init.sh dev`, CLI) es la raíz del
    repositorio, como dice el AC. Desde otro directorio (p. ej. `WORKDIR` en un contenedor)
    `../.env` apunta a otro sitio. Es lo que pide el design §3 y el AC acota el caso a `backend/`.
  - Sugerencia: que `deployment_rpi` tenga en cuenta que en Docker el `.env` llega por
    `env_file`/variables de Compose y no por la lectura de `../.env`.
- **Pendientes del ciclo 1 (fuera del alcance de la v1.1, siguen abiertos):** H-01 (mensajes de
  excepción en los logs de uvicorn; ya recogido en `docs/conventions.md` §3), H-04, H-05, H-06
  (sigue apareciendo el `PytestDeprecationWarning` de `asyncio_default_fixture_loop_scope`),
  H-07 y H-08. **Cerrados:** H-02 (design §4 v1.1) y H-03 (AC-23).
