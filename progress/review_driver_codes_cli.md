# Revisión: driver_codes_cli
Ciclo: 1 de la v1.1 · Fecha: 2026-11-11 · Agente: reviewer
Spec: specs/driver_codes_cli/ v1.1 (APPROVED, PR #60) · Rama: `feat/driver_codes_cli-v1.1` (HEAD e5e2e81), base `origin/develop` · Commits revisados: 10eb266 (T-05), a396770 (T-04 y progreso)

## Veredicto: APPROVED

T-05 cumple AC-03 v1.1: `cli/main.py:14` fija `pretty_exceptions_show_locals=False` de forma
explícita, y hay dos tests que lo comprueban. El de comportamiento falla de verdad si el valor
vuelve a `True`: lo he comprobado con un mutante en una copia fuera del repositorio. La
verificación completa está en verde, los seis AC siguen teniendo tests válidos y no hay cambios
fuera del alcance. N-07 queda cerrado. Hay un hallazgo nuevo, no bloqueante: N-10.

## Matriz AC → evidencia

`U` = `backend/tests/unit/test_driver_codes.py`, `C` = `backend/tests/integration/test_cli_driver_codes.py`,
`R` = `backend/tests/integration/test_driver_code_repository.py`. Entre paréntesis, el número de tests
que citan el AC (`grep -rn 'driver_codes_cli.AC-0n"' backend/tests`).

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 (17) | Los mismos que en la v1.0: U `test_generator_*` (5), `test_create_*` (4); C `test_create_prints_the_code_grouped_with_its_id_and_label`, `test_create_stores_the_generated_code`, `test_create_generates_another_code_when_the_code_exists`, `test_create_fails_cleanly_when_every_retry_collides`; R `test_add_then_get_and_find_by_hash`, `test_add_rejects_*` (3) | OK | Sin cambios en la v1.1. Mutantes de regresión de este ciclo: sin ceros a la izquierda (4 tests fallan), salida 0 al agotar los reintentos (1 test falla). |
| AC-02 (5) | Los mismos que en la v1.0 (U 2, C 3) | OK | Mutantes de regresión: sin `isprintable` (8 tests fallan), límite 41 (2 tests fallan). |
| AC-03 (15) | Los 13 de la v1.0 y dos nuevos de la v1.1 en C: **`test_the_error_trace_does_not_show_the_code_kept_in_a_local_variable`** (`:345`) y **`test_the_cli_sets_show_locals_off_explicitly`** (`:383`) | OK | Detalle en la sección "T-05" de abajo. Mutantes de regresión: `hide_parameters=False` (3 tests fallan, entre ellos el nuevo de la traza), sin `from None` (1 test falla), dominio del dispositivo (6 tests fallan). |
| AC-04 (8) | Los mismos que en la v1.0 (U 1, C 7) | OK | Mutantes de regresión: columna del turno invertida (2 tests fallan), logs a stdout con `--json` (1 test falla). |
| AC-05 (12) | Los mismos que en la v1.0 (U 4, C 5, R 3) | OK | Mutante de regresión: salida 0 si el `code_id` no existe (1 test falla). |
| AC-06 (4) | Los mismos que en la v1.0 (U 3, C 1) | OK | Mutantes de regresión: registrar la etiqueta en `create` (3 tests fallan) y en `revoke` (2 tests fallan). |

Desde la aprobación de la v1.0 (f70a41b), `driver_session` y `driver_gps_simulator` han cambiado
ficheros de esta feature: `cli/container.py` (consulta real del turno abierto), `db.py` (tabla
`driver_session`), `domain/models/driver.py`, `domain/ports/driver.py` y `cli/main.py` (comando
`simulate`). También han añadido a C tres tests de `driver_session.AC-14`. Ningún test que cite
`driver_codes_cli.AC-*` se ha quitado ni debilitado. Esos tests pasan con la consulta real del turno
y siguen detectando los mutantes de arriba.

### T-05 (AC-03 v1.1): la traza sin variables locales

**Lo que hace el test de comportamiento** (`C:345-379`): borra la tabla después de componer, para
que el `INSERT` lance un `OperationalError` real mientras `plain_code = "48210937"` es variable local
de `CreateDriverCode.execute`. Antes de nada comprueba que esa variable local está en la traza
(`:368`), así que el test no puede pasar sin ejercitar el caso. Después pasa la excepción por el
`sys.excepthook` que Typer instala (`:372`) y comprueba cuatro cosas: que la traza muestra el
error, y que no aparecen ni el código (junto o agrupado), ni su *hash*, ni la etiqueta.

**Mutantes en una copia del backend** (scratchpad, con el `.venv` del repositorio y
`PYTHONPATH=<copia>/src`; antes comprobé que `cli/main.py` se importaba desde la copia). Ejecuté los
tres ficheros de test de la feature, 93 tests. El repositorio no se ha tocado: `cmp` de todos los
`.py` de la copia restaurada contra el repositorio sin diferencias, y la copia ya está borrada.

| Mutante en `cli/main.py` | Test de la traza | Test del ajuste explícito |
|---|---|---|
| M1 `pretty_exceptions_show_locals=True` | **Falla** (`AssertionError: '48210937' is contained here: … plain_code = '48210937'`) | Falla |
| M2 sin el argumento (valor por defecto de Typer) | Pasa (es lo correcto: el comportamiento es el mismo) | **Falla** |
| M3 sin el argumento, con `# pretty_exceptions_show_locals=False` como comentario | Pasa | **Pasa**: sobrevive (N-10) |
| M4 `app.pretty_exceptions_show_locals = True` tras construir el `app` | **Falla** | Falla (por `is False`) |
| M5 `show_locals=True` y `pretty_exceptions_short=False` | **Falla** | Falla |

En M1, el test de la traza falla porque en ella aparece el código en claro, no por otro motivo.
Esto confirma que el test cubre la regresión que describía N-07.

**Con el binario real** (`backend/.venv/bin/avisabus`, `AVISABUS_ENV=prod`, la BD en el scratchpad y
puesta en solo lectura después de un primer `create`): `create --label EtiquetaSensible` sale con
1, con la traza de `rich` (149 líneas con marco) y `attempt to write a readonly database`. Ni en
stdout ni en stderr aparecen `plain_code`, ocho dígitos seguidos o agrupados, la etiqueta o un
hexadecimal de 64 caracteres.

### Decisiones locales de la v1.1 (`progress/impl_driver_codes_cli.md`)

| Decisión | Dictamen | Motivo |
|---|---|---|
| Invocar `app([...], prog_name="avisabus")` en lugar de `CliRunner` en el test de la traza | Correcta, sin CP-3 | Lo he comprobado en Typer 0.27.3. `CliRunner.invoke` construye el comando con `get_command(app)` (`typer/testing.py:285`) y no pasa por `Typer.__call__` (`typer/main.py:1133-1154`), que es donde se adjunta `DeveloperExceptionConfig` a la excepción. Sin esa configuración, `except_hook` (`typer/main.py:61-75`) usa la traza estándar de Python, que nunca muestra variables locales, y con `CliRunner` el mutante M1 sobreviviría. Además, el test restaura `sys.excepthook` con `monkeypatch` (`:361`) y quita las dos variables `TYPER_STANDARD_TRACEBACK`. AC-01 pide `CliRunner` para su propia verificación, no para esta. |
| Test que lee el fuente de `cli/main.py` | Aceptable, sin CP-3 | AC-03 v1.1 pide que el valor sea explícito "con un test que lo comprueba", y ningún comportamiento distingue un `False` explícito del valor por defecto (M2). Ya hay un precedente de test sobre ficheros del repositorio (`tests/unit/test_architecture_contracts.py`). La comprobación textual tiene un hueco (M3, N-10), pero la acompaña `app.pretty_exceptions_show_locals is False`, y el test de comportamiento cubre lo que de verdad importa. |
| Depender de `rich` en el test de la traza | Aceptable | `rich` llega como dependencia de `typer` (`uv.lock`) y está instalado. Sin `rich`, Typer usa la traza estándar, que no muestra variables locales: el test pasaría sin ejercitar `show_locals`, pero tampoco habría fuga. No es un riesgo para AC-03. |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e`, con el puerto 4173 libre (`lsof -iTCP:4173 -sTCP:LISTEN` sin
resultados): **exit 0, `verify: todo en verde`**.

| Paso | Resultado |
|---|---|
| backend format / lint | OK (`All checks passed!`) |
| backend `mypy` | OK, sin problemas en 150 ficheros |
| backend `lint-imports` | OK, 2 contratos cumplidos, 0 rotos |
| backend `pytest` (sockets desactivados) | 1915 passed, 12 deselected; cobertura de `domain` + `application` 99,66 % |
| frontend format / lint / types | OK |
| frontend tests | 660 passed, 2 skipped |
| frontend build + bundle | OK, 5 passed |
| frontend e2e + a11y | 132 passed, 12 skipped (no hay cambios en `frontend/` en esta rama) |
| `feature_list.json` y trazabilidad AC→test | OK |

Otros comandos: los tres ficheros de test de la feature en la copia (93 passed sin mutantes), 11
mutantes (ver arriba), la prueba con el binario real y `git diff --stat origin/develop...HEAD`.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes (nuevos)

- **N-10**: `backend/tests/integration/test_cli_driver_codes.py:386`. La expresión regular busca
  `pretty_exceptions_show_locals\s*=\s*False` en todo el fichero, incluidos los comentarios. Si se
  quita el argumento de `Typer(...)` y el texto queda en un comentario (mutante M3), el test sigue
  pasando, y `app.pretty_exceptions_show_locals is False` también, porque es el valor por defecto
  de Typer. Así, la parte "explícito" de AC-03 v1.1 podría perderse sin que falle ningún test. Es
  poco probable y no expone el código: el test de comportamiento sigue cubriendo `True`. Sería más
  robusto recorrer el AST de `cli/main.py` y comprobar que la llamada a `typer.Typer` que crea
  `app` tiene la palabra clave `pretty_exceptions_show_locals` con el valor constante `False`.

### Estado de los no bloqueantes anteriores

| Id | Estado |
|---|---|
| N-01, N-02 | Cerrados en la v1.0 (3dbc8d9). |
| N-03 | Abierto, sin cambios. `backend/src/avisabus/adapters/inbound/cli/driver_codes.py`: el aviso de revocar uno ya revocado va a stderr, mientras que los `AVISO:` de `cli/gtfs.py` van a stdout. La spec no fija el canal. |
| N-04 | Abierto, sin cambios. `backend/src/avisabus/application/driver_codes.py:108-117`: entre `get` y `revoke` no hay atomicidad. Dos `revoke` simultáneos registran `driver_code.revoked` dos veces. Sin impacto real en una CLI de administración. |
| N-05 | **Cerrado**: `progress/current.md:7` y `feature_list.json` dicen los dos `in_review`. |
| N-06 | Abierto (imprecisión de spec, sin CP-3). `specs/driver_codes_cli/design.md` §2 sigue diciendo "IntegrityError de hash → el caso de uso reintenta", y T-01 sigue sin listar `domain/errors.py`. La v1.1 no lo ha corregido. |
| N-07 | **Cerrado** por T-05 (10eb266): el valor es explícito y el mutante `True` hace fallar los dos tests nuevos. |
| N-08 | Abierto, sin cambios. `backend/src/avisabus/adapters/inbound/cli/driver_codes.py:67-76`: un `OperationalError` sale como traza, con el mensaje y el SQL pero sin valores. Un mensaje de error limpio sería más amable para el administrador. |
| N-09 | Abierto (informativo). `backend/src/avisabus/adapters/outbound/persistence/db.py:36`: `hide_parameters` oculta los parámetros, no las filas. Con `sqlalchemy.engine` en `DEBUG` se registrarían filas con *hash* y etiqueta. Hoy nada lo activa. |

## Lista de comprobación (`docs/verification.md` §4)

| Bloque | Resultado |
|---|---|
| Contrato | AC-03 v1.1 se cumple de forma literal: `False` explícito en la aplicación Typer, con un test. Los demás AC no han cambiado y su comportamiento sigue verificado. Sin cambios de interfaz respecto a `design.md`. |
| Arquitectura | `lint-imports` OK. El cambio de código de producción es una línea en el adaptador de entrada (`cli/main.py`), sin `datetime.now()` ni `time.time()`. |
| Tests | Sin red ni `sleep`. El `OperationalError` es real (`DROP TABLE` antes del `INSERT`). `sys.excepthook` y las variables de entorno se restauran con `monkeypatch`. Los tests no son tautológicos: M1, M2, M4 y M5 detectados; M3 sobrevive (N-10). |
| Privacidad y seguridad | Ni la traza de `rich` ni la estándar muestran variables locales. Comprobado en el test y con el binario real, sin código, *hash* ni etiqueta. |
| Frontend | No aplica: no hay cambios en `frontend/`. |
| Convenciones | Commits `fix(driver_codes_cli)`, `chore(driver_codes_cli)` y `chore(progress)`, con el ámbito correcto. Nombres de test que describen el comportamiento y `@pytest.mark.spec("driver_codes_cli.AC-03")`. Código en inglés y progreso en castellano. |
| Alcance | `git diff --stat origin/develop...HEAD`: `cli/main.py` y `test_cli_driver_codes.py` (los dos ficheros de T-05), más `feature_list.json`, `progress/current.md`, `progress/history.md` y `progress/impl_driver_codes_cli.md`. No hay cambios en `specs/` ni en `docs/`. La carpeta `qr/`, sin versionar, y `.env` no se han tocado. |

---

Histórico: la revisión de la v1.0 (ciclos 1 y 2, APPROVED en el ciclo 2) está en el historial de git
de este fichero (`git log -p -- progress/review_driver_codes_cli.md`, versión anterior a esta).
